import argparse
import base64
import binascii
import json
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .agent import Agent
from .sources import BOARDS, inspect_form, source_names
from .sources.telegram import channel_name
from .extraction import expired
from .ingestion import ingest_posts
from .social_inbox import prepare_post
from .notifications import save_token
from .google_forms import FormReviews
from .evaluation import evaluate
from .store import DEFAULTS, Store, now
from .workflow import prepare, transition

STATIC = Path(__file__).with_name("static")
MAX_BODY = 14_100_000


def last_checked(store):
    with store.db() as db:
        row = db.execute("SELECT value FROM settings WHERE key='last_discovery_success'").fetchone()
        if row:
            return json.loads(row["value"])
        return db.execute("SELECT MAX(checked) FROM health WHERE status='OK'").fetchone()[0]


def snapshot(store, agent):
    settings = store.settings()
    facts = store.facts()
    stale_before = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    with store.db() as db:
        items = []
        for row in db.execute("SELECT * FROM opportunities"):
            item = {**json.loads(row["payload"]), "id": row["id"], "checked": row["checked"],
                    "state": row["state"], "discovered": row["discovered"], "source": row["source"]}
            if item["state"] == "Listed" and item["checked"] < stale_before:
                item["state"] = "Needs refresh"
            item.update(evaluate(item, facts, settings["weights"]))
            if expired(item):
                item["state"] = "Expired"
            item["choice"] = settings.get("choice:" + item["id"], "review")
            items.append(item)
        apps = [dict(row) | json.loads(row["payload"])
                for row in db.execute("SELECT * FROM applications ORDER BY updated DESC")]
        for app in apps:
            del app["payload"]
        return {"items": sorted(items, key=lambda item: (-item["score"], item["title"])),
                "facts": facts, "apps": apps, "agent": agent.state, "settings": settings,
                "last_checked": last_checked(store),
                "sources": source_names(settings), "health": [dict(r) for r in db.execute("SELECT * FROM health")],
                "documents": [dict(r) for r in db.execute("SELECT * FROM documents ORDER BY added DESC")],
                "mail": [dict(r) for r in db.execute("SELECT kind, subject, at FROM mail_events WHERE kind NOT IN ('Archived', 'Unclassified') ORDER BY rowid DESC LIMIT 20")],
                "revision": db.execute("SELECT COALESCE(MAX(rowid), 0) FROM activity").fetchone()[0],
                "activity": [dict(r) for r in db.execute("SELECT * FROM activity ORDER BY rowid DESC LIMIT 80")]}


def update_settings(store, body):
    start, end = body["start"], body["end"]
    if not all(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", v) for v in (start, end)) or start >= end:
        raise ValueError("Choose a start time earlier than the end time")
    days, sources, weights = body["days"], body["enabled_sources"], body["weights"]
    if (not days or not set(days) <= set(range(7)) or not set(sources) <= set(BOARDS)
            or set(weights) != set(DEFAULTS["weights"]) or not sum(weights.values())
            or not all(type(v) is int and 0 <= v <= 100 for v in weights.values())):
        raise ValueError("Check days, source selection and scoring weights")
    channels = list(dict.fromkeys(channel_name(c) for c in str(body.get("telegram_channels", "")).split() if c))
    if len(channels) > 20:
        raise ValueError("Choose up to 20 public channels")
    allowlist = list(dict.fromkeys(str(body.get("source_allowlist", "")).split()))
    known = set(BOARDS) | {"telegram:" + c for c in channels}
    if not set(allowlist) <= known:
        raise ValueError("Allow-list entries must be enabled sources or configured Telegram channels")
    current_settings = store.settings()
    provider = body.get("extraction_provider", current_settings.get("extraction_provider", "ollama"))
    if provider not in {"ollama", "local_chat", "regex"}:
        raise ValueError("Choose a supported extraction provider")
    interval = int(body.get("discovery_interval_minutes", current_settings.get("discovery_interval_minutes", 30)))
    batch_limit = int(body.get("extraction_batch_limit", current_settings.get("extraction_batch_limit", 5)))
    threshold = float(body.get("extraction_threshold", current_settings.get("extraction_threshold", .8)))
    model = str(body.get("extraction_model", current_settings.get("extraction_model", "qwen3:4b"))).strip()
    endpoint = str(body.get("extraction_endpoint", current_settings.get("extraction_endpoint", "http://127.0.0.1:11434"))).strip()
    parsed = urlsplit(endpoint)
    if (not 5 <= interval <= 1440 or not 1 <= batch_limit <= 20 or not .5 <= threshold <= 1 or not model or len(model)>100 or
            parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or
            parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Check interval, confidence threshold and the local provider endpoint")
    schedule_mode = body.get("discovery_schedule_mode", current_settings.get("discovery_schedule_mode", "manual"))
    if schedule_mode not in {"manual", "always", "window"}:
        raise ValueError("Choose an operating schedule")
    values = {"extraction_batch_limit": batch_limit, "extraction_provider": provider, "extraction_model": model, "extraction_endpoint": endpoint,
              "extraction_threshold": threshold, "discovery_interval_minutes": interval, "discovery_schedule_mode": schedule_mode,
              "telegram_channels": channels, "source_allowlist": allowlist, "start": start, "end": end, "days": days, "enabled_sources": sources,
              "weights": weights, "ac_only": body["ac_only"] is True,
              "essay_style": str(body["essay_style"])[:2000],
              "ollama_model": str(body["ollama_model"]).strip()[:100]}
    with store.db() as db:
        db.executemany("INSERT OR REPLACE INTO settings VALUES (?, ?)",
                       [(key, json.dumps(value)) for key, value in values.items()])


def import_document(store, body):
    name = Path(str(body["name"])).name[:200]
    raw = base64.b64decode(body["content"], validate=True)
    suffix = Path(name).suffix.lower()
    valid = (suffix == ".pdf" and raw.startswith(b"%PDF-") or
             suffix == ".docx" and raw.startswith(b"PK\x03\x04") or
             suffix == ".txt" and b"\x00" not in raw)
    if not valid or not 0 < len(raw) <= 10_000_000:
        raise ValueError("Choose a PDF, DOCX or text document up to 10 MB")
    ident = secrets.token_hex(16)
    folder = store.directory / "documents"
    folder.mkdir(mode=0o700, exist_ok=True)
    path = folder / ident
    try:
        path.write_bytes(raw)
        with store.db() as db:
            db.execute("INSERT INTO documents VALUES (?, ?, ?, ?)", (ident, name, len(raw), now()))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    store.log("Document imported into private storage")


def handler_for(store, agent, port):
    authority = f"127.0.0.1:{port}"
    reviews = FormReviews(store)

    class Handler(BaseHTTPRequestHandler):
        def log_request(self, code="-", size="-"):
            if isinstance(code, int) and code >= 500:
                self.log_message("Local request failed with HTTP %d", code)

        def send(self, data, kind, status=200):
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(data)

        def json(self, data, status=200):
            self.send(json.dumps(data).encode(), "application/json; charset=utf-8", status)

        def do_GET(self):
            if self.headers.get("Host") != authority:
                return self.json({"error": "Use the printed localhost address"}, 403)
            path = urlsplit(self.path).path
            if path.startswith("/api/review/"):
                ident = path.rsplit("/", 1)[-1]
                if not re.fullmatch(r"[a-f0-9]{32}", ident):
                    return self.json({"error": "Invalid review"}, 400)
                image = store.directory / "reviews" / (ident + ".png")
                if image.is_file():
                    return self.send(image.read_bytes(), "image/png")
                return self.json({"error": "Review image unavailable"}, 404)
            if path == "/api/reviews":
                with reviews.lock:
                    return self.json({"reviews": list(reviews.jobs.values())})
            if path == "/api/state":
                return self.json(snapshot(store, agent))
            if path == "/api/heartbeat":
                with store.db() as db:
                    revision = db.execute("SELECT COALESCE(MAX(rowid), 0) FROM activity").fetchone()[0]
                return self.json({"agent": agent.state, "revision": revision, "last_checked": last_checked(store)})
            assets = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"),
                      "/app.js": ("app.js", "text/javascript"), "/sandbox": ("sandbox.html", "text/html"),
                      "/sandbox.js": ("sandbox.js", "text/javascript")}
            if path in assets:
                name, kind = assets[path]
                return self.send((STATIC / name).read_bytes(), kind + "; charset=utf-8")
            self.json({"error": "Page unavailable"}, 404)

        def do_POST(self):
            if (self.headers.get("Host") != authority or self.headers.get("Origin") != f"http://{authority}"
                    or self.headers.get_content_type() != "application/json"):
                return self.json({"error": "Same-origin JSON requests only"}, 403)
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= MAX_BODY:
                    raise ValueError("Invalid request size")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("Invalid request")
                path = urlsplit(self.path).path
                if path == "/api/sources/add":
                    channel = channel_name(body["channel"])
                    with store.db() as db:
                        db.execute("BEGIN IMMEDIATE")
                        row = db.execute("SELECT value FROM settings WHERE key='telegram_channels'").fetchone()
                        channels = json.loads(row["value"]) if row else []
                        channel = next((c for c in channels if c.casefold() == channel.casefold()), channel)
                        if channel not in channels:
                            if len(channels) >= 20:
                                raise ValueError("Up to 20 public channels are supported")
                            channels.append(channel)
                        db.execute("INSERT OR REPLACE INTO settings VALUES ('telegram_channels', ?)", (json.dumps(channels),))
                        db.execute("INSERT OR REPLACE INTO health VALUES (?, ?, 'Queued', 0)", ("telegram:" + channel, now()))
                    status = agent.request_source("telegram:" + channel)
                    store.log("Public channel added to discovery")
                    return self.json({"channel": channel, "status": status})
                if path == "/api/inbox/paste":
                    raw = prepare_post(body["content"], str(body.get("source_link", "")).strip())
                    ingest_posts(store, "manual", [raw])
                    store.log("Pasted post extracted")
                    return self.json({"id": raw["id"]})
                if path == "/api/telegram":
                    chat = str(body.get("chat_id", "")).strip()
                    enabled = body.get("enabled") is True
                    if enabled and (not chat.isdecimal() or int(chat) <= 0):
                        raise ValueError("Enter your numeric private Telegram chat ID")
                    if body.get("token"):
                        save_token(str(body["token"]).strip())
                        with store.db() as db:
                            db.execute("INSERT OR REPLACE INTO settings VALUES ('telegram_configured', 'true')")
                    if enabled and not store.settings().get("telegram_configured"):
                        raise ValueError("Enter a Telegram bot token first")
                    with store.db() as db:
                        db.executemany("INSERT OR REPLACE INTO settings VALUES (?, ?)",
                            [("telegram_chat_id", json.dumps(chat)), ("telegram_notifications", json.dumps(enabled))])
                    return self.json({"ok": True})
                if path == "/api/review-close":
                    with reviews.lock:
                        if body["id"] not in reviews.jobs:
                            raise ValueError("Review unavailable")
                        reviews.cancelled.add(body["id"])
                    return self.json({"ok": True})
                if path == "/api/prefill":
                    item = next((i for i in snapshot(store, agent)["items"] if i["id"] == body["id"]), None)
                    if not item or item["state"] != "Listed" or item["eligibility"] == "Ineligible" or item["choice"] == "skip":
                        raise ValueError("Choose a current eligible opportunity")
                    return self.json({"review": reviews.start(item, store.facts())})
                if path == "/api/form":
                    return self.json({"questions": inspect_form(body["id"])})
                self.mutate(path, body)
            except (KeyError, ValueError, TypeError, binascii.Error) as error:
                return self.json({"error": str(error)}, 400)
            self.json({"ok": True})

        def mutate(self, path, body):
            if path == "/api/agent":
                action = body["action"]
                if action == "run":
                    agent.start()
                elif action in {"pause", "stop"}:
                    agent.control(action)
                else:
                    raise ValueError("Unknown agent action")
            elif path == "/api/fact":
                key, value, source = str(body["key"]), str(body["value"]).strip(), str(body["source"]).strip()
                if key not in store.facts() or len(value) > 5000 or len(source) > 300:
                    raise ValueError("Invalid profile field")
                verified = bool(value and body["verified"] is True)
                with store.db() as db:
                    db.execute("UPDATE facts SET value=?, source=?, verified=?, share=?, updated=? WHERE key=?",
                               (value, source, verified, verified and body["share"] is True, now(), key))
            elif path == "/api/draft":
                with store.db() as db:
                    row = db.execute("SELECT * FROM opportunities WHERE id=?", (body["id"],)).fetchone()
                if not row or row["state"] != "Listed" or datetime.fromisoformat(row["checked"]) < datetime.now(timezone.utc) - timedelta(days=7):
                    raise ValueError("Choose a listed opportunity")
                item = json.loads(row["payload"]) | {"id": row["id"]}
                if evaluate(item, store.facts(), store.settings()["weights"])["eligibility"] == "Ineligible":
                    raise ValueError("This listing conflicts with your verified academic level")
                prompt, words = str(body["prompt"])[:5000], int(body["words"])
                if not 1 <= words <= 1200:
                    raise ValueError("Word limit must be between 1 and 1200")
                prepare(store, item, prompt, words)
            elif path == "/api/choice":
                if body["choice"] not in {"auto", "review", "skip"}:
                    raise ValueError("Invalid application choice")
                with store.db() as db:
                    if not db.execute("SELECT 1 FROM opportunities WHERE id=?", (body["id"],)).fetchone():
                        raise ValueError("Opportunity unavailable")
                    db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)",
                               ("choice:" + body["id"], json.dumps(body["choice"])))
                store.log("Application preference saved")
            elif path == "/api/application":
                transition(store, body["id"], body["action"], body)
            elif path == "/api/settings":
                update_settings(store, body)
            elif path == "/api/document":
                import_document(store, body)
            else:
                raise ValueError("Unknown action")

    return Handler


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="OpportunityOS")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data", default=os.environ.get("OPPORTUNITYOS_DATA", "~/Library/Application Support/OpportunityOS"))
    parser.add_argument("--discover", action="store_true", help="Run live discovery once, then exit")
    parser.add_argument("--no-schedule", action="store_true")
    args = parser.parse_args()
    store = Store(args.data)
    agent = Agent(store)
    if args.discover:
        agent.start()
        agent.worker.join()
        with store.db() as db:
            health = [dict(row) for row in db.execute("SELECT * FROM health")]
        print(json.dumps(health, indent=2))
        return int(any(row["status"] != "OK" for row in health))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(store, agent, args.port))
    if not args.no_schedule:
        threading.Thread(target=agent.schedule, daemon=True).start()
    print(f"OpportunityOS · http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        agent.control("stop")
        if agent.worker:
            agent.worker.join()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
