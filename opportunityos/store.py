import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = json.loads((ROOT / "config.example.json").read_text())
PROFILE = dict.fromkeys(("citizenship", "age_context", "university", "program", "academic_level",
                         "interests", "experience", "name", "email", "hku_email", "phone", "location",
                         "work_authorization", "skills", "projects", "awards", "languages", "availability",
                         "links"), "")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, directory):
        self.directory = Path(directory).expanduser().resolve()
        if self.directory.is_relative_to(ROOT):
            raise ValueError("Choose a data directory outside the source checkout")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.stat().st_uid != os.getuid() or self.directory.stat().st_mode & 0o077:
            raise ValueError("Data directory must belong to you and have permissions 0700")
        with self.db() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS facts (
                    key TEXT PRIMARY KEY, value TEXT, source TEXT, verified INTEGER,
                    share INTEGER, updated TEXT);
                CREATE TABLE IF NOT EXISTS opportunities (
                    id TEXT PRIMARY KEY, source TEXT, url TEXT UNIQUE, payload TEXT,
                    discovered TEXT, checked TEXT, state TEXT);
                CREATE TABLE IF NOT EXISTS applications (
                    opportunity TEXT PRIMARY KEY REFERENCES opportunities(id),
                    payload TEXT, status TEXT, updated TEXT);
                CREATE TABLE IF NOT EXISTS activity (at TEXT, message TEXT);
                CREATE TABLE IF NOT EXISTS health (
                    source TEXT PRIMARY KEY, checked TEXT, status TEXT, count INTEGER);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS mail_events (
                    id TEXT PRIMARY KEY, kind TEXT, subject TEXT, at TEXT);
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, name TEXT, size INTEGER, added TEXT);
            """)
            db.executemany("INSERT OR IGNORE INTO facts VALUES (?, ?, ?, 0, 0, ?)",
                           [(key, value, "Onboarding brief" if value else "", now())
                            for key, value in PROFILE.items()])

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.directory / "opportunity.sqlite", timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def settings(self):
        with self.db() as db:
            stored = {row["key"]: json.loads(row["value"]) for row in db.execute("SELECT * FROM settings")}
        return {**DEFAULTS, **stored}

    def log(self, message):
        with self.db() as db:
            db.execute("INSERT INTO activity VALUES (?, ?)", (now(), message))

    def facts(self):
        with self.db() as db:
            return {row["key"]: dict(row) for row in db.execute("SELECT * FROM facts ORDER BY rowid")}
