import json
import os
import tempfile
import unittest
from datetime import datetime
from urllib.error import URLError
from unittest.mock import patch

from opportunityos.__main__ import import_document, snapshot
from opportunityos.agent import Agent, HK, permitted
from opportunityos.discovery import refresh
from opportunityos.evaluation import evaluate
from opportunityos.store import Store
from opportunityos.workflow import BLOCKERS, policy, prepare, transition

ITEM = {"jobs": [{"title": "BS/MS Software Engineer Intern", "id": 100,
                  "absolute_url": "https://example.invalid/jobs/100", "location": {"name": "Remote"},
                  "content": "<p>Compensation $25 per hour</p>"}]}


class Core(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.agent = Agent(self.store)

    def ingest(self, items=ITEM):
        refresh(self.store, "waymo", lambda board: (items, "https://example.invalid/evidence"))
        return snapshot(self.store, self.agent)["items"][0]

    def test_dedup_and_delisting(self):
        first = self.ingest()
        self.ingest()
        self.assertEqual(len(snapshot(self.store, self.agent)["items"]), 1)
        gone = self.ingest({"jobs": []})
        self.assertEqual(gone["state"], "Unlisted")
        self.assertEqual(gone["discovered"], first["discovered"])

    def test_offline_preserves_listings(self):
        self.ingest()
        with patch("opportunityos.agent.refresh", side_effect=URLError("offline")):
            self.agent.start()
            self.agent.worker.join(3)
        data = snapshot(self.store, self.agent)
        self.assertEqual(data["agent"], "Idle")
        self.assertEqual(data["items"][0]["state"], "Listed")
        self.assertTrue(all(h["status"] == "URLError" for h in data["health"]))

    def test_stale_listings_require_refresh(self):
        self.ingest()
        with self.store.db() as db:
            db.execute("UPDATE opportunities SET checked='2025-01-01T00:00:00+00:00'")
        self.assertEqual(snapshot(self.store, self.agent)["items"][0]["state"], "Needs refresh")

    def test_degree_and_funding_evidence(self):
        row = self.ingest()
        self.assertEqual(row["eligibility"], "Needs review")
        self.assertIn("$25", row["funding"])
        with self.store.db() as db:
            db.execute("UPDATE facts SET value='Undergraduate',verified=1 WHERE key='academic_level'")
        self.assertEqual(evaluate({**row, "title": "Summer Intern, MS/PhD, Research"}, self.store.facts(),
                                  self.store.settings()["weights"])["eligibility"], "Ineligible")
        self.assertGreater(row["score"], 0)

    def test_draft_review_submission_archive(self):
        item = self.ingest()
        ident = item["id"]
        self.assertTrue(prepare(self.store, item, "Why this role?", 10))
        self.assertFalse(prepare(self.store, item, "Different prompt", 20))
        with self.assertRaises(ValueError):
            transition(self.store, ident, "ready", {})
        transition(self.store, ident, "save", {"draft": "I am applying for this internship."})
        transition(self.store, ident, "ready", {})
        with self.assertRaises(ValueError):
            transition(self.store, ident, "submitted", {"evidence": ""})
        transition(self.store, ident, "submitted", {"evidence": "test receipt"})
        transition(self.store, ident, "archive", {})
        transition(self.store, ident, "restore", {})
        app = snapshot(self.store, self.agent)["apps"][0]
        self.assertEqual(app["status"], "Submitted")
        self.assertEqual(app["prompt"], "Why this role?")
        self.assertEqual(app["evidence"], "test receipt")

    def test_policy_fails_closed(self):
        complete = dict.fromkeys(BLOCKERS, True)
        self.assertEqual(policy(complete), [])
        for key in BLOCKERS:
            self.assertEqual(policy(complete | {key: None}), [key])
        self.assertCountEqual(policy({}), BLOCKERS)

    def test_schedule_and_stop(self):
        self.assertTrue(permitted(self.store.settings(), datetime(2026, 11, 11, 20, tzinfo=HK)))
        self.assertFalse(permitted(self.store.settings(), datetime(2026, 11, 11, 21, tzinfo=HK)))
        self.agent.control("stop")
        with patch.object(self.agent, "start") as start:
            self.agent.tick(datetime(2026, 11, 11, 20, tzinfo=HK))
            start.assert_not_called()

    def test_pause_and_stop_at_source_boundary(self):
        from threading import Event

        entered, release = Event(), Event()
        def blocking_fetch(store, board):
            entered.set()
            release.wait(3)

        with patch("opportunityos.agent.refresh", side_effect=blocking_fetch) as fetch:
            self.agent.start()
            self.assertTrue(entered.wait(2))
            self.agent.control("pause")
            self.assertEqual(self.agent.state, "Paused")
            self.agent.control("stop")
            release.set()
            self.agent.worker.join(3)
            self.assertEqual(self.agent.state, "Stopped")
            self.assertEqual(fetch.call_count, 1)

    def test_private_document_import(self):
        old = os.umask(0o077)
        try:
            import_document(self.store, {"name": "../demo.txt", "content": "dGVzdA=="})
        finally:
            os.umask(old)
        with self.store.db() as db:
            row = db.execute("SELECT * FROM documents").fetchone()
        self.assertEqual(row["name"], "demo.txt")
        self.assertEqual((self.store.directory / "documents" / row["id"]).stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.store.directory.stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
