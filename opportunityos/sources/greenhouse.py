import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


BOARDS = {"waymo": "Waymo", "figma": "Figma", "cloudflare": "Cloudflare",
          "databricks": "Databricks", "scaleai": "Scale AI"}
EARLY = re.compile(r"\b(intern(?:ship)?|co-op|student researcher|fellowship)\b", re.I)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "div", "br", "li", "ul", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def clean(content):
    parser = PlainText()
    parser.feed(html.unescape(content or ""))
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


def get_json(url, timeout=10):
    with urlopen(Request(url, headers={"User-Agent": "OpportunityOS/0.1", "Accept": "application/json"}), timeout=timeout) as response:
        raw = response.read(20_000_001)
        if len(raw) > 20_000_000:
            raise ValueError("Source response exceeds limit")
        return json.loads(raw)


def greenhouse(board):
    endpoint = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    return get_json(endpoint), endpoint


def normalize(board, data, evidence):
    for job in data["jobs"]:
        title = job["title"].strip()
        if not EARLY.search(title):
            continue
        url = urlsplit(job["absolute_url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            continue
        yield {
            "id": f"greenhouse:{board}:{int(job['id'])}",
            "title": title, "organization": BOARDS[board], "category": "Internship" if not
            re.search("fellowship", title, re.I) else "Fellowship",
            "location": (job.get("location") or {}).get("name") or "Unknown",
            "url": urlunsplit((url.scheme, url.netloc, url.path, url.query, "")),
            "description": clean(job.get("content")),
            "deadline": None, "evidence": evidence, "source_updated": job.get("updated_at"),
        }


def inspect_form(ident):
    """Read question metadata from the employer's public listing API."""
    provider, board, job = ident.split(":")
    if provider != "greenhouse" or board not in BOARDS or not job.isascii() or not job.isdecimal():
        raise ValueError("No supported form metadata source")
    endpoint = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job}?questions=true"
    try:
        detail = get_json(endpoint)
    except OSError as error:
        raise ValueError("Could not read public form metadata. Open the official listing to check its requirements.") from error
    result = []
    for group in ("questions", "location_questions", "compliance", "demographic_questions"):
        questions = detail.get(group) or []
        if isinstance(questions, dict):
            questions = questions.get("questions") or []
        for question in questions:
            result.append({"label": clean(question.get("label") or question.get("title")),
                           "required": question.get("required") is True,
                           "types": [field.get("type") for field in question.get("fields", [])],
                           "group": group})
    return result


def fetch(board):
    data, evidence = greenhouse(board)
    return [dict(item, raw_text=item["description"], source_link=item["url"],
                 application_link=item["url"], source=board)
            for item in normalize(board, data, evidence)]
