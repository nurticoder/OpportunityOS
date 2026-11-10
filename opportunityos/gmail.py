"""Opt-in, read-only Gmail scan for an application label."""
import argparse
import hashlib
import re
from pathlib import Path

from .store import Store, now

SCOPE = ["https://www.googleapis.com/auth/gmail.metadata"]
SERVICE = "OpportunityOS Gmail"
EVENTS = (
    ("Archived", r"not selected|unsuccessful|unable to offer|application (?:was )?declined|regret to inform"),
    ("Interview", r"interview"),
    ("Selected", r"offer letter|accepted into|congratulations"),
    ("Document request", r"missing document|additional document|document request"),
    ("Deadline update", r"deadline|extended"),
    ("Confirmation", r"application received|application confirmation|submission confirmation"),
    ("Status update", r"application update|status update"),
)


def classify(subject):
    return next((name for name, pattern in EVENTS if re.search(pattern, subject, re.I)), None)


def scan(service, store, label, account):
    inbox = service.users()
    labels = inbox.labels().list(userId="me").execute().get("labels", [])
    target = next((entry["id"] for entry in labels
                   if entry["name"] == label and entry.get("type") == "user"), None)
    if target is None:
        raise ValueError("Create a dedicated Gmail label and apply it to application messages")
    messages = inbox.messages()
    page = messages.list(userId="me", labelIds=[target], maxResults=100).execute()
    inserted = 0
    with store.db() as db:
        for item in page.get("messages", []):
            ident = hashlib.sha256((account + ":" + item["id"]).encode()).hexdigest()
            if db.execute("SELECT 1 FROM mail_events WHERE id=?", (ident,)).fetchone():
                continue
            message = messages.get(userId="me", id=item["id"], format="metadata",
                                   metadataHeaders=["Subject"]).execute()
            headers = message.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")[:300]
            event = classify(subject)
            inserted += db.execute("INSERT OR IGNORE INTO mail_events VALUES (?, ?, ?, ?)",
                                   (ident, event or "Unclassified", subject if event else "", now())).rowcount
    return inserted


def main():
    import keyring
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    parser = argparse.ArgumentParser(description="Scan subjects in a Gmail application label")
    parser.add_argument("--data", required=True)
    parser.add_argument("--account", default="personal", help="Local account label, e.g. personal or HKU")
    parser.add_argument("--label", default="OpportunityOS")
    parser.add_argument("--authorize", type=Path, help="Desktop OAuth client JSON outside the checkout")
    args = parser.parse_args()
    store = Store(args.data)
    if args.authorize:
        from .store import ROOT
        if args.authorize.resolve().is_relative_to(ROOT):
            parser.error("Keep OAuth client JSON outside the source checkout")
        flow = InstalledAppFlow.from_client_secrets_file(str(args.authorize), SCOPE, autogenerate_code_verifier=True)
        credentials = flow.run_local_server(host="127.0.0.1", port=0, authorization_prompt_message=None, timeout_seconds=180)
    else:
        saved = keyring.get_password(SERVICE, args.account)
        if not saved:
            parser.error("Authorize with a Google desktop OAuth client JSON first")
        import json
        credentials = Credentials.from_authorized_user_info(json.loads(saved), SCOPE)
        if not credentials.valid:
            credentials.refresh(Request())
    keyring.set_password(SERVICE, args.account, credentials.to_json())
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    print(f"Scanned {scan(service, store, args.label, args.account)} new message subjects.")


if __name__ == "__main__":
    main()
