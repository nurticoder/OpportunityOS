"""Read and fill visible Google Form text fields, then return a local review artifact."""
import json
import re
import secrets
import threading
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ALIASES = {
    "name": {"name", "full name", "your name", "your full name", "applicant name"},
    "email": {"email", "email address", "your email", "your email address"},
    "phone": {"phone", "phone number", "phone number (optional)", "mobile number", "contact number"},
    "university": {"university", "university name", "college", "college name", "institution"},
    "program": {"program", "degree program", "course of study"},
    "citizenship": {"citizenship", "nationality"},
    "location": {"location", "country of residence"},
    "academic_level": {"academic level", "education level"},
}


def fact_key(label):
    label = re.sub(r"\s+", " ", label.casefold().strip().strip("*").strip().rstrip(":"))
    return next((key for key, names in ALIASES.items() if label in names), None)


def allowed_link(url):
    parsed = urlsplit(url)
    return parsed.scheme == "https" and not parsed.username and not parsed.password and (
        parsed.hostname == "forms.gle" or parsed.hostname == "docs.google.com" and parsed.path.startswith("/forms/")
    )


class GoogleRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_link(newurl):
            raise ValueError("Google Form redirected to an unsupported destination")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def resolve_form(url):
    if not allowed_link(url):
        raise ValueError("Only public Google Forms are supported")
    if urlsplit(url).hostname == "forms.gle":
        with build_opener(GoogleRedirects()).open(Request(url), timeout=20) as response:
            url = response.geturl()
        if not allowed_link(url) or urlsplit(url).hostname != "docs.google.com":
            raise ValueError("Short link did not resolve to a Google Form")
    return url


def prefill(page, url, facts):
    if not allowed_link(url):
        raise ValueError("Only public Google Forms are supported")
    blocked = []
    def guard(route):
        request = route.request
        host = urlsplit(request.url).hostname or ""
        safe_host = any(host == domain or host.endswith("." + domain)
                        for domain in ("google.com", "googleusercontent.com", "gstatic.com", "forms.gle"))
        if request.method not in {"GET", "HEAD"} or not safe_host:
            blocked.append(request.method)
            route.abort()
        else:
            route.fallback()
    page.route("**/*", guard)
    url = resolve_form(url)
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    if urlsplit(page.url).hostname != "docs.google.com" or "/forms/" not in page.url:
        raise ValueError("Form requires sign-in or redirected away from Google Forms")
    page.wait_for_load_state("networkidle", timeout=20000)
    page.locator('[role="listitem"]').first.wait_for(timeout=15000)
    page.locator('input[type="text"]:enabled, input[type="email"]:enabled, textarea:enabled').first.wait_for(timeout=15000)
    fields = []
    for row in page.locator('[role="listitem"]').all():
        headings = row.locator('[role="heading"]')
        if headings.count() != 1:
            continue
        label = headings.inner_text().strip()
        key = fact_key(label)
        inputs = row.locator('input[type="text"]:not([disabled]), input[type="email"]:not([disabled]), textarea:not([disabled])')
        fact = facts.get(key, {})
        mapped = False
        if inputs.count() == 1 and fact.get("verified") and fact.get("value") and fact.get("share"):
            inputs.fill(fact["value"])
            mapped = True
        fields.append({"label": label, "fact": key, "filled": mapped,
                       "attention": None if mapped else "Verify and allow sharing of the matching fact, or complete manually"})
    # Some Google Forms collect email outside their question cards.
    for field in page.locator('input[type="email"]').all():
        if not field.input_value() and facts.get("email", {}).get("verified") and facts["email"].get("share"):
            field.fill(facts["email"]["value"])
            fields.append({"label": "Email", "fact": "email", "filled": True, "attention": None})
    return {"url": page.url, "title": page.title(), "fields": fields,
            "status": "Awaiting review", "blocked_requests": len(blocked)}


class FormReviews:
    def __init__(self, store):
        self.store = store
        self.jobs = {}
        self.cancelled = set()
        self.lock = threading.Lock()
        folder = store.directory / "reviews"
        if folder.exists():
            for saved in folder.glob("*.json"):
                if re.fullmatch(r"[a-f0-9]{32}", saved.stem):
                    try:
                        result = json.loads(saved.read_text())
                        if result.get("id") == saved.stem:
                            self.jobs[saved.stem] = result
                    except (OSError, ValueError):
                        pass

    def start(self, item, facts):
        source = item["source"]
        if source not in self.store.settings().get("source_allowlist", []):
            raise ValueError("Add this source to the form-fill allow-list in Settings first")
        if not allowed_link(item.get("application_link", "")):
            raise ValueError("This opportunity has no supported Google Form")
        with self.lock:
            if any(job["opportunity"] == item["id"] and job["status"] == "Running" for job in self.jobs.values()):
                raise ValueError("Form prefill is already running")
            ident = secrets.token_hex(16)
            self.jobs[ident] = {"id": ident, "opportunity": item["id"], "status": "Running"}
        threading.Thread(target=self.run, args=(ident, item, facts), daemon=True).start()
        return ident

    def run(self, ident, item, facts):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
                browser = p.chromium.launch(headless=False, executable_path=str(chrome) if chrome.exists() else None)
                try:
                    page = browser.new_page()
                    result = prefill(page, item["application_link"], facts)
                    result.update(id=ident, opportunity=item["id"])
                    folder = self.store.directory / "reviews"
                    folder.mkdir(mode=0o700, exist_ok=True)
                    page.screenshot(path=str(folder / (ident + ".png")), full_page=True)
                    (folder / (ident + ".json")).write_text(json.dumps(result))
                    with self.lock:
                        self.jobs[ident].update(result)
                    self.store.log("Google Form prepared for review")
                    # Keep the filled form visible for review, with all writes still blocked.
                    import time
                    until = time.monotonic() + 600
                    while browser.is_connected() and not page.is_closed() and time.monotonic() < until and ident not in self.cancelled:
                        page.wait_for_timeout(1000)
                finally:
                    browser.close()
            self.store.log("Google Form review window closed")
        except Exception as error:
            with self.lock:
                self.jobs[ident].update(status="Needs attention", error=str(error)[:500])
            self.store.log("Google Form requires attention")
