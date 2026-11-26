"""Shared persistence and extraction for adapter posts and pasted posts."""
import json
from .extraction import extract, extraction_fingerprint
from .store import now


def ingest_posts(store, source, posts, budget=None, should_stop=None, quick=False):
    settings = store.settings()
    budget = budget if budget is not None else {"remaining": settings.get("extraction_batch_limit", 5)}
    seen = []
    for raw in posts:
        if should_stop and should_stop():
            raise InterruptedError("Discovery interrupted between posts")
        with store.db() as db:
            row = db.execute("SELECT payload FROM opportunities WHERE id=?", (raw["id"],)).fetchone()
        previous = json.loads(row["payload"]) if row else None
        fingerprint = extraction_fingerprint(raw, settings)
        if (previous and (previous.get("extraction_fingerprint") == fingerprint or quick and previous.get("raw_text")==raw["raw_text"] and all(previous.get(k)==raw[k] for k in ("title","application_link") if raw.get(k))) and
                (previous.get("extraction_engine") != "regex_fallback" or settings.get("extraction_provider") == "regex")):
            item = previous
        else:
            selected = settings
            if quick or settings.get("extraction_provider") == "regex":
                selected = {**settings, "extraction_provider": "regex"} if quick else settings
            elif budget["remaining"] <= 0 or budget.get("unavailable"):
                selected = {**settings, "extraction_provider": "regex"}
            else:
                budget["remaining"] -= 1
            item = extract(raw, selected)
            if selected is not settings:
                item["extraction_fallback_reason"] = "fast_scan" if quick else "batch_budget" if not budget.get("unavailable") else "provider_unavailable"
                item["extraction_fingerprint"] = fingerprint
            elif item["extraction_engine"] == "regex_fallback" and item.get("extraction_fallback_reason") in {"OSError", "URLError", "HTTPError", "TimeoutError", "ConnectionError"}:
                budget["unavailable"] = True
        stamp = now()
        with store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT payload FROM opportunities WHERE id=?", (item["id"],)).fetchone()
            current = json.loads(current["payload"]) if current else None
            if (item["extraction_engine"] == "regex_fallback" and current and
                    current.get("extraction_fingerprint") == fingerprint and current.get("extraction_engine") != "regex_fallback"):
                item = current
            db.execute("""
                INSERT INTO opportunities VALUES (?, ?, ?, ?, ?, ?, 'Listed')
                ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,
                    checked=excluded.checked, state='Listed'
            """, (item["id"], source, item["source_link"], json.dumps(item, ensure_ascii=False), stamp, stamp))
        seen.append(item["id"])
    return seen
