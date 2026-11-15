"""Conservative deterministic extraction. Unrecognized claims stay in raw evidence."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit


def method(link):
    host = urlsplit(link).hostname
    if host == "forms.gle" or host == "docs.google.com" and "/forms/" in link:
        return "google_form"
    if link.startswith("mailto:"):
        return "email"
    return "portal" if host else "unknown"


def deadline_from(text):
    match = re.search(r"(?:deadline|apply by|closing date)\s*[:–-]?\s*([^\n]+)", text, re.I)
    if not match:
        return None, None
    evidence = match.group(1).strip()[:100]
    for pattern, formats in [
        (r"\b\d{4}-\d{2}-\d{2}\b", ["%Y-%m-%d"]),
        (r"\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b", ["%d %B %Y", "%d %b %Y"]),
        (r"\b[A-Za-z]+\s+\d{1,2},?\s+\d{4}\b", ["%B %d %Y", "%b %d %Y"]),
    ]:
        value = re.search(pattern, evidence)
        if value:
            for fmt in formats:
                try:
                    return datetime.strptime(value[0].replace(",", ""), fmt).date().isoformat(), evidence
                except ValueError:
                    pass
    return None, evidence


def extract(raw):
    text = raw["raw_text"]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    titles = [line for line in lines if re.search(r"[A-Za-z]{3}", re.sub(r"#[\w]+", "", line)) and not line.startswith("https://")]
    links = raw.get("links", []) + re.findall(r"https?://[^\s<>]+|mailto:[^\s<>]+", text)
    links = [link.rstrip(".,)") for link in links if urlsplit(link).scheme in {"https", "mailto"}]
    application = raw.get("application_link") or next((link for link in links if method(link) == "google_form"), None)
    if not application:
        application = next((link for link in links if link.startswith("mailto:")), None)
    if not application:
        application = next((link for link in links if urlsplit(link).hostname not in {"t.me", "telegram.me"}), None)
    explicit = {}
    for key, pattern in {
        "nationality": r"(?:eligible nationalities|nationality|citizenship)\s*:\s*([^\n]+)",
        "country_of_study": r"(?:country of study|studying in)\s*:\s*([^\n]+)",
        "level": r"(?:academic level|education level|eligible levels?|level)\s*:\s*([^\n]+)",
    }.items():
        match = re.search(pattern, text, re.I)
        explicit[key] = re.split(r"\s*(?:,|;|\bor\b|/)\s*", match[1].strip(), flags=re.I) if match else None
    inferred = {
        "nationality": r"(?:only (?:citizens|nationals) of|must be (?:a )?citizen of) ([A-Za-z ]+?)(?:[.\n]|$)",
        "country_of_study": r"(?:must (?:be studying|study) in|only students studying in) ([A-Za-z ]+?)(?:[.\n]|$)",
        "level": r"(?:only|exclusively for) (undergraduate|master|phd|doctoral)(?: students| applicants)",
    }
    for key, pattern in inferred.items():
        if explicit[key] is None:
            match = re.search(pattern, text, re.I)
            if match:
                explicit[key] = [match[1].strip()]
    org = re.search(r"(?:organization|organizer|company|host)\s*:\s*([^\n]+)", text, re.I)
    kind = next((kind.title() for kind in ["internship", "scholarship", "fellowship", "hackathon", "summit", "workshop", "competition"]
                 if re.search(r"\b" + kind + r"\b", text, re.I)), "Unknown")
    deadline, evidence = deadline_from(text)
    documents = [name for name, pattern in {
        "CV": r"\b(?:CV|resume|résumé)\b", "Transcript": r"\btranscripts?\b",
        "Passport": r"\bpassport\b", "Cover letter": r"\bcover letter\b",
        "Recommendation": r"\brecommendation letter\b",
    }.items() if any(re.search(pattern, line, re.I) and
                    re.search(r"required|submit|attach|upload|documents?|materials?|need|send", line, re.I)
                    for line in lines)]
    return {**raw, "title": raw.get("title") or (titles[0][:200] if titles else "Untitled post"),
            "organization": raw.get("organization") or (org[1].strip() if org else "Unknown"),
            "type": kind, "category": raw.get("category", kind), "deadline": deadline,
            "deadline_evidence": evidence, "eligibility_requirements": explicit,
            "required_documents": documents, "application_link": application,
            "apply_method": method(application or ""), "description": text,
            "url": application or raw["source_link"], "evidence": raw["source_link"],
            "location": raw.get("location", "Unknown")}


def expired(item):
    return bool(item.get("deadline") and item["deadline"] < datetime.now(ZoneInfo("Asia/Hong_Kong")).date().isoformat())
