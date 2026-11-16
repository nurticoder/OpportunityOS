import json
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .sources import refresh, source_names
from .store import now
from .notifications import notify

HK = ZoneInfo("Asia/Hong_Kong")


def permitted(settings, moment):
    clock = moment.strftime("%H:%M")
    return moment.weekday() in settings["days"] and settings["start"] <= clock < settings["end"]


def on_ac():
    try:
        return "AC Power" in subprocess.check_output(["/usr/bin/pmset", "-g", "batt"], text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return False


class Agent:
    def __init__(self, store):
        self.store = store
        self.condition = threading.Condition()
        self.state = "Idle"
        self.enabled = True
        self.worker = None

    def request_source(self, source):
        with self.condition:
            with self.store.db() as db:
                row = db.execute("SELECT value FROM settings WHERE key='pending_sources'").fetchone()
                pending = json.loads(row["value"]) if row else []
                if source not in pending:
                    pending.append(source)
                db.execute("INSERT OR REPLACE INTO settings VALUES ('pending_sources', ?)", (json.dumps(pending),))
            if self.store.settings().get("discovery_schedule_mode", "manual") == "manual":
                return "queued"
            if not self.worker or not self.worker.is_alive():
                try:
                    self.start(sources=pending)
                    return "fetching"
                except ValueError:
                    return "deferred"
            return "queued"

    def start(self, scheduled=False, sources=None):
        with self.condition:
            if self.worker and self.worker.is_alive():
                if self.state == "Paused" and not scheduled:
                    self.state = "Running"
                    self.enabled = True
                    self.condition.notify_all()
                    return
                raise ValueError("Discovery is already active")
            settings = self.store.settings()
            if settings["ac_only"] and not on_ac():
                raise ValueError("Waiting for AC power")
            self.enabled = True
            self.state = "Running"
            with self.store.db() as db:
                db.execute("INSERT OR REPLACE INTO settings VALUES ('last_discovery_attempt', ?)", (json.dumps(now()),))
            self.worker = threading.Thread(target=self.run, args=(scheduled, settings, sources), daemon=True)
            self.worker.start()

    def control(self, action):
        with self.condition:
            self.enabled = False
            self.state = ("Stopping" if self.worker and self.worker.is_alive() else "Stopped") if action == "stop" else "Paused"
            self.condition.notify_all()

    def interrupted(self, scheduled, settings):
        return (self.state in {"Stopping", "Stopped", "Paused"} or
                scheduled and settings.get("discovery_schedule_mode", "always") == "window" and not permitted(settings, datetime.now(HK)) or
                settings["ac_only"] and not on_ac())

    def run(self, scheduled, settings, sources=None):
        self.store.log("Discovery started")
        todo = list(sources if sources is not None else ["telegram:" + c for c in settings.get("telegram_channels", [])] + settings["enabled_sources"])
        processed = set()
        budget = {"remaining": settings.get("extraction_batch_limit", 5)}
        try:
            while todo:
                source = todo.pop(0)
                if self.interrupted(scheduled, settings):
                    break
                processed.add(source)
                try:
                    with self.store.db() as db:
                        db.execute("INSERT OR REPLACE INTO health VALUES (?, ?, 'Fetching', 0)", (source, now()))
                    refresh(self.store, source, budget=budget, should_stop=lambda: self.interrupted(scheduled, settings))
                    with self.store.db() as db:
                        db.execute("INSERT OR REPLACE INTO settings VALUES ('last_discovery_success', ?)", (json.dumps(now()),))
                        row = db.execute("SELECT value FROM settings WHERE key='pending_sources'").fetchone()
                        pending = json.loads(row["value"]) if row else []
                        db.execute("INSERT OR REPLACE INTO settings VALUES ('pending_sources', ?)",
                                   (json.dumps([p for p in pending if p != source]),))
                except InterruptedError:
                    self.store.log("Discovery deferred between posts")
                    break
                except (OSError, ValueError, KeyError, TypeError) as error:
                    with self.store.db() as db:
                        db.execute("INSERT OR REPLACE INTO health VALUES (?, ?, ?, 0)", (source, now(), type(error).__name__))
                    self.store.log(f"{source_names(settings).get(source, source)} · unavailable ({type(error).__name__})")
                pending = self.store.settings().get("pending_sources", [])
                todo.extend(p for p in pending if p not in processed and p not in todo)
            if not self.interrupted(scheduled, settings):
                notify(self.store, should_stop=lambda: self.interrupted(scheduled, settings))
        finally:
            with self.condition:
                self.state = "Stopped" if self.state == "Stopping" else "Paused" if self.state == "Paused" else "Idle"
            self.store.log("Discovery finished")

    def tick(self, moment):
        settings = self.store.settings()
        if settings.get("discovery_schedule_mode", "manual") == "manual":
            return
        if not self.enabled or self.state != "Idle":
            return
        if settings.get("discovery_schedule_mode", "always") == "window" and not permitted(settings, moment):
            return
        with self.store.db() as db:
            queued = [row["source"] for row in db.execute("SELECT source FROM health WHERE status='Queued'")]
        queued = list(dict.fromkeys(settings.get("pending_sources", []) + queued))
        if queued:
            try:
                self.start(sources=queued)
            except ValueError:
                pass
            return
        previous = settings.get("last_discovery_attempt")
        if previous and moment.astimezone(timezone.utc) - datetime.fromisoformat(previous) < timedelta(minutes=settings.get("discovery_interval_minutes", 30)):
            return
        try:
            self.start(scheduled=True)
        except ValueError:
            pass

    def schedule(self):
        while True:
            self.tick(datetime.now(HK))
            threading.Event().wait(30)
