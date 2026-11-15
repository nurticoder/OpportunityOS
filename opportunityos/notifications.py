"""Opt-in Telegram bot notifications with persistent deduplication."""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from .store import now
from .evaluation import evaluate
from .extraction import expired

SERVICE = "OpportunityOS Telegram bot"


def save_token(token):
    try:
        import keyring
    except ImportError:
        raise ValueError("Install requirements-notifications.txt to use macOS Keychain") from None
    if not re.fullmatch(r"\d{5,20}:[A-Za-z0-9_-]{20,200}", token):
        raise ValueError("Enter the bot token issued by BotFather")
    try:
        keyring.set_password(SERVICE, "personal", token)
    except Exception:
        raise ValueError("Could not store the bot credential in macOS Keychain") from None


def send_telegram(chat_id, text):
    import keyring
    token = keyring.get_password(SERVICE, "personal")
    if not token:
        raise ValueError("Connect a Telegram bot in Settings")
    body = json.dumps({"chat_id": chat_id, "text": text[:4000],
                       "link_preview_options": {"is_disabled": True}}).encode()
    try:
        with urlopen(Request("https://api.telegram.org/bot" + token + "/sendMessage", body,
                             {"Content-Type": "application/json"}), timeout=12) as response:
            payload = json.loads(response.read(20000))
        if not payload.get("ok") or not payload.get("result", {}).get("message_id"):
            raise ValueError("Telegram did not return delivery evidence")
        return str(payload["result"]["message_id"])
    except HTTPError as error:
        # Do not propagate exception URLs because the Bot API embeds the credential.
        if error.code == 429:
            raise BlockingIOError("Telegram rate limit") from None
        raise ValueError("Telegram rejected the notification (HTTP " + str(error.code) + ")") from None
    except (URLError, TimeoutError, OSError):
        raise TimeoutError("Telegram delivery could not be confirmed") from None


def initialize(store):
    with store.db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS notification_events (
            id TEXT PRIMARY KEY, opportunity TEXT, kind TEXT, status TEXT,
            attempted TEXT, receipt TEXT)""")


def notify(store, sender=None, moment=None, should_stop=None):
    settings = store.settings()
    if not settings.get("telegram_notifications"):
        return 0
    sender = sender or send_telegram
    moment = moment or datetime.now(timezone.utc)
    chat = str(settings.get("telegram_chat_id", ""))
    if not chat.isdecimal() or int(chat) <= 0:
        return 0
    initialize(store)
    facts = store.facts()
    sent = 0
    destination = hashlib.sha256(chat.encode()).hexdigest()[:16]
    with store.db() as db:
        rows = [dict(row) for row in db.execute("SELECT * FROM opportunities WHERE state='Listed'")]
    for row in rows:
        item = json.loads(row["payload"])
        if expired(item) or moment - datetime.fromisoformat(row["checked"]) > timedelta(days=7):
            continue
        if settings.get("choice:" + row["id"]) == "skip":
            continue
        assessment = evaluate(item, facts, settings["weights"])
        if assessment["eligibility"] == "Ineligible":
            continue
        kinds = []
        if (assessment["score"] >= settings.get("notification_min_score", 60) and len(assessment["matches"]) >= 2 and
                moment - datetime.fromisoformat(row["discovered"]) <= timedelta(days=7)):
            kinds.append("strong")
        if item.get("deadline"):
            end = datetime.fromisoformat(item["deadline"] + "T23:59:59+08:00")
            if timedelta(0) < end - moment <= timedelta(hours=48):
                # A year/month/day alone cannot establish an exact cutoff time.
                kinds.append("deadline:" + item["deadline"])
        for kind in kinds:
            if should_stop and should_stop():
                return sent
            evidence = item.get("field_evidence", {})
            required = ("title", "deadline") if kind.startswith("deadline:") else ("title",)
            if not all(evidence.get(k, {}).get("confidence", 0) >= .8 for k in required):
                continue
            target = item.get("application_link") or item["source_link"]
            opportunity_key = hashlib.sha256(target.encode()).hexdigest()
            ident = destination + ":" + kind + ":" + opportunity_key
            with store.db() as db:
                db.execute("BEGIN IMMEDIATE")
                previous = db.execute("SELECT * FROM notification_events WHERE id=?", (ident,)).fetchone()
                if previous:
                    if previous["status"] != "rate_limited" or moment - datetime.fromisoformat(previous["attempted"]) < timedelta(minutes=30):
                        continue
                db.execute("INSERT OR REPLACE INTO notification_events VALUES (?, ?, ?, 'sending', ?, '')",
                           (ident, row["id"], kind, now()))
            title = "Deadline within 48 hours (date-only)" if kind.startswith("deadline:") else "New strong match · check eligibility"
            text = title + "\n" + item["title"] + "\n" + (item.get("source_link") or item["url"])
            if item.get("deadline"):
                text += "\nClosing date: " + item["deadline"] + " · exact cutoff time unverified"
            try:
                receipt = sender(chat, text)
                status = "sent"
            except BlockingIOError:
                receipt, status = "", "rate_limited"
            except Exception:
                receipt, status = "", "unconfirmed"
            with store.db() as db:
                db.execute("UPDATE notification_events SET status=?, receipt=? WHERE id=?", (status, receipt, ident))
            store.log("Telegram notification " + status)
            if status != "sent":
                return sent
            if status == "sent":
                sent += 1
            if sent >= 5:
                return sent
    return sent
