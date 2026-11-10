import subprocess
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from .discovery import BOARDS, refresh
from .store import now

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

    def start(self, scheduled=False):
        with self.condition:
            if self.worker and self.worker.is_alive():
                if self.state == "Paused" and not scheduled:
                    self.state = "Running"
                    self.condition.notify_all()
                    return
                raise ValueError("Discovery is already active")
            settings = self.store.settings()
            if settings["ac_only"] and not on_ac():
                raise ValueError("Waiting for AC power")
            self.enabled = True
            self.state = "Running"
            self.worker = threading.Thread(target=self.run, args=(scheduled, settings), daemon=True)
            self.worker.start()

    def control(self, action):
        with self.condition:
            if action == "stop":
                self.enabled = False
                self.state = "Stopping" if self.state in {"Running", "Paused"} else "Stopped"
            elif action == "pause":
                self.enabled = False
                self.state = "Paused"
            self.condition.notify_all()

    def run(self, scheduled, settings):
        self.store.log("Scheduled discovery started" if scheduled else "Discovery started")
        failed = 0
        completed = True
        try:
            for board in settings["enabled_sources"]:
                with self.condition:
                    while self.state == "Paused":
                        if scheduled and not permitted(settings, datetime.now(HK)):
                            break
                        self.condition.wait(20)
                    if self.state in {"Stopping", "Stopped", "Paused"} or (
                        scheduled and not permitted(settings, datetime.now(HK))
                    ) or (settings["ac_only"] and not on_ac()):
                        completed = False
                        break
                try:
                    refresh(self.store, board)
                except (OSError, ValueError, KeyError, TypeError) as error:
                    failed += 1
                    with self.store.db() as db:
                        db.execute("INSERT OR REPLACE INTO health VALUES (?, ?, ?, 0)",
                                   (board, now(), type(error).__name__))
                    self.store.log(f"{BOARDS[board]} · fetch unavailable ({type(error).__name__})")
            if scheduled and completed and failed == 0:
                with self.store.db() as db:
                    db.execute("INSERT OR REPLACE INTO settings VALUES ('last_scheduled', json_quote(?))",
                               (datetime.now(HK).date().isoformat(),))
        finally:
            with self.condition:
                if self.state == "Stopping":
                    self.state = "Stopped"
                elif self.state != "Paused":
                    self.state = "Idle"
            self.store.log("Discovery finished" if completed else "Discovery deferred at source boundary")

    def tick(self, moment):
        settings = self.store.settings()
        if not self.enabled or self.state != "Idle" or not permitted(settings, moment):
            return
        today = moment.date().isoformat()
        if settings.get("last_scheduled") == today or getattr(self, "attempted", None) == today:
            return
        try:
            self.start(scheduled=True)
            self.attempted = today
        except ValueError:
            pass

    def schedule(self):
        while True:
            self.tick(datetime.now(HK))
            threading.Event().wait(30)
