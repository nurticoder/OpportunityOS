"""Public social previews and text pasted by the user, with no login or browser cookies."""
import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

HOSTS = {"instagram.com", "www.instagram.com", "linkedin.com", "www.linkedin.com"}


def supported_link(value):
    parsed = urlsplit(value)
    return parsed.scheme == "https" and parsed.hostname in HOSTS and not parsed.username and not parsed.password and parsed.port in {None, 443}


class SocialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not supported_link(newurl):
            raise ValueError("Social preview redirected outside the supported platform")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Preview(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.texts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and (attrs.get("property") or attrs.get("name")) in {"og:description", "description"}:
            if attrs.get("content"):
                self.texts.append(attrs["content"])


def prepare_post(content, source_link=""):
    content = str(content).strip()
    if not content or len(content) > 20000:
        raise ValueError("Paste between 1 and 20,000 characters")
    if source_link and not supported_link(source_link):
        raise ValueError("Use an Instagram or LinkedIn source link")
    capture_method = "pasted_text"
    if re.fullmatch(r"https://\S+", content):
        capture_method = "public_preview"
        if not supported_link(content):
            raise ValueError("Paste an Instagram/LinkedIn post URL, or paste its text")
        source_link = content
        try:
            opener = build_opener(SocialRedirect())
            with opener.open(Request(content, headers={"User-Agent": "OpportunityOS/0.3"}), timeout=15) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Public preview exceeds size limit")
            parser = Preview()
            parser.feed(raw.decode("utf-8", errors="replace"))
            content = max(parser.texts, key=len, default="")
        except OSError as error:
            raise ValueError("Public preview unavailable. Paste the post text alongside its source URL.") from error
        if len(content) < 80 or len(content) > 20000 or any(s in content.lower() for s in ("log in to instagram", "sign in to linkedin", "login • instagram")):
            raise ValueError("Public preview unavailable. Paste the post text alongside its source URL.")
    identity = source_link or content
    digest = hashlib.sha256(identity.encode()).hexdigest()
    return {"id": "manual:" + digest, "source": "manual", "raw_text": content, "capture_method": capture_method,
            "source_link": source_link or "urn:opportunityos:paste:" + digest,
            "links": re.findall(r"https://[^\s<>]+", content)}
