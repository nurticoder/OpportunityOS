import copy
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch

from opportunityos.extraction import extract,validate_fields,FIELDS
from opportunityos.store import Store,now
from opportunityos.ingestion import ingest_posts
from opportunityos.agent import Agent,HK
from opportunityos.notifications import notify
from opportunityos.social_inbox import prepare_post


TEXT = "AI robotics software engineering Internship\nOrganization: Aurora Lab\nDeadline: 15 December 2026\nCountry of study: Hong Kong\nRequired: CV\nApply: https://forms.gle/demoAurora"
RAW = {"id":"telegram:example/1","source":"telegram:example","raw_text":TEXT,
       "source_link":"https://t.me/example/1","links":["https://forms.gle/demoAurora"]}


def document():
    fields={k:dict(value="unknown",confidence=0,evidence="") for k in FIELDS}
    for key,value,quote in [
        ("title","AI robotics software engineering Internship","AI robotics software engineering Internship"),
        ("organization","Aurora Lab","Organization: Aurora Lab"),
        ("type","internship","Internship"),("deadline","2026-12-15","Deadline: 15 December 2026"),
        ("country_of_study",["Hong Kong"],"Country of study: Hong Kong"),
        ("required_documents",["CV"],"Required: CV"),
        ("application_link","https://forms.gle/demoAurora","https://forms.gle/demoAurora"),
        ("apply_method","google_form","https://forms.gle/demoAurora")
    ]:
        fields[key]=dict(value=value,confidence=.95,evidence=quote)
    return {**{k:v for k,v in fields.items() if k not in {"nationality","country_of_study","level"}},
            "eligibility":{k:fields[k] for k in ("nationality","country_of_study","level")}}


class Quality(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=Store(self.temp.name)

    def test_strict_evidence_and_confidence(self):
        doc=document()
        doc["organization"]=dict(value="Invented Lab",confidence=.99,evidence="not in the post")
        doc["deadline"]["confidence"]=.7
        result=extract(RAW,provider=lambda *args:doc)
        self.assertEqual(result["organization"],"Unknown")
        self.assertIsNone(result["deadline"])
        self.assertEqual(result["field_evidence"]["title"]["confidence"],.95)
        self.assertEqual(result["structured_extraction"]["eligibility"]["nationality"]["value"],"unknown")

    def test_value_must_agree_with_quote(self):
        doc=document()
        doc["organization"]["value"]="Google"
        self.assertEqual(validate_fields(doc,RAW,.8)["organization"]["value"],"unknown")

    def test_schema_and_provider_failure_use_labeled_fallback(self):
        result=extract(RAW,provider=lambda *args:{"bad":True})
        self.assertEqual(result["extraction_engine"],"regex_fallback")
        def unavailable(*args):raise OSError("offline")
        self.assertEqual(extract(RAW,provider=unavailable)["extraction_engine"],"regex_fallback")

    def test_venue_is_not_country_of_study(self):
        raw={**RAW,"raw_text":"Workshop in Hong Kong\nApply https://forms.gle/demoAurora"}
        doc=document()
        doc["eligibility"]["country_of_study"]=dict(value=["Hong Kong"],confidence=.99,evidence="Workshop in Hong Kong")
        self.assertEqual(validate_fields(doc,raw,.8)["country_of_study"]["value"],"unknown")

    def test_unchanged_posts_reuse_successful_extraction(self):
        with patch("opportunityos.extraction.generate",return_value=document()) as provider:
            ingest_posts(self.store,"telegram:example",[RAW])
            ingest_posts(self.store,"telegram:example",[RAW])
        self.assertEqual(provider.call_count,1)

    def test_manual_dedup_and_restricted_urls(self):
        first=prepare_post(TEXT)
        self.assertEqual(first["id"],prepare_post(TEXT)["id"])
        with self.assertRaises(ValueError):prepare_post("https://127.0.0.1/internal")
        with self.assertRaises(ValueError):prepare_post("some text","https://evil.example/")
        with patch("opportunityos.extraction.generate",return_value=document()):
            ingest_posts(self.store,"manual",[first])
            ingest_posts(self.store,"manual",[first])
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0],1)

    def test_thirty_minute_schedule_and_pause(self):
        with self.store.db() as db:
            db.execute("INSERT INTO settings VALUES ('last_discovery_attempt', ?)",(json.dumps(now()),))
        agent=Agent(self.store)
        with patch.object(agent,"start") as start:
            agent.tick(datetime.now(HK)+timedelta(minutes=29))
            start.assert_not_called()
            agent.tick(datetime.now(HK)+timedelta(minutes=31))
            start.assert_called_once_with(scheduled=True)
        agent.control("pause")
        with patch.object(agent,"start") as start:
            agent.tick(datetime.now(HK)+timedelta(hours=1))
            start.assert_not_called()

    def test_notifications_deduplicate_and_no_retry_ambiguous_send(self):
        moment=datetime.now(timezone.utc)
        item=extract(RAW,provider=lambda *args:document())
        item["deadline"]=(moment.astimezone(HK).date()+timedelta(days=1)).isoformat()
        with self.store.db() as db:
            db.execute("INSERT INTO opportunities VALUES (?,?,?,?,?,?,'Listed')",
                       (item["id"],"telegram:example",item["source_link"],json.dumps(item),now(),now()))
            for key,value in {"telegram_notifications":True,"telegram_chat_id":"123","notification_min_score":60}.items():
                db.execute("INSERT INTO settings VALUES (?,?)",(key,json.dumps(value)))
        sent=[]
        def sender(chat,text):sent.append(text);return "test-receipt"
        notify(self.store,sender,moment)
        notify(self.store,sender,moment)
        self.assertEqual(len(sent),1)
        with self.store.db() as db:
            db.execute("DELETE FROM notification_events")
        def uncertain(*args):raise TimeoutError()
        notify(self.store,uncertain,moment)
        notify(self.store,sender,moment)
        self.assertEqual(len(sent),1)

    def test_all_ten_fixtures_are_evaluated(self):
        from pathlib import Path
        cases=json.loads((Path(__file__).parent/"fixtures/multilingual_posts.json").read_text())
        self.assertEqual(len(cases),10)
        self.assertTrue(any("Кыргызстан" in case["text"] for case in cases))
        for case in cases:
            with self.subTest(case=case["id"]):
                result=extract({"raw_text":case["text"],"source_link":"https://example.invalid/"+case["id"]},
                               {"extraction_provider":"regex"})
                self.assertEqual(set(result["field_evidence"]),set(FIELDS))
                for field in result["field_evidence"].values():
                    if field["value"]!="unknown":
                        self.assertIn(field["evidence"],case["text"])



class NotificationsAndQueue(unittest.TestCase):
    def test_restart_resumes_persisted_source_after_interrupted_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory)
            with store.db() as db:
                db.execute("INSERT INTO settings VALUES ('pending_sources', ?)",
                           (json.dumps(["telegram:example"]),))
                db.execute("INSERT INTO health VALUES (?, ?, 'Fetching', 0)",
                           ("telegram:example", now()))
            agent=Agent(store)
            with patch.object(agent,"start") as start:
                agent.tick(datetime.now(HK))
                start.assert_called_once_with(sources=["telegram:example"])

    def test_strong_match_uses_rank_and_eligibility(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory)
            item=extract(RAW,provider=lambda *args:document())
            item["deadline"]=None
            item["eligibility_requirements"]["level"]=["undergraduate"]
            with store.db() as db:
                db.execute("UPDATE facts SET value='AI, robotics, software engineering',verified=1 WHERE key='interests'")
                db.execute("UPDATE facts SET value='Undergraduate',verified=1 WHERE key='academic_level'")
                db.execute("INSERT INTO opportunities VALUES (?,?,?,?,?,?,'Listed')",
                           (item["id"],"telegram:example",item["source_link"],json.dumps(item),now(),now()))
                for key,value in {"telegram_notifications":True,"telegram_chat_id":"123"}.items():
                    db.execute("INSERT INTO settings VALUES (?,?)",(key,json.dumps(value)))
            calls=[]
            notify(store,lambda chat,text:calls.append(text) or "receipt")
            notify(store,lambda chat,text:calls.append(text) or "receipt")
            self.assertEqual(len(calls),1)
            self.assertIn("strong match",calls[0])

    def test_cancelled_deadline_not_retained(self):
        doc=document()
        raw={**RAW,"raw_text":TEXT.replace("Deadline: 15 December 2026","OLD deadline: 15 December 2026 — cancelled")}
        doc["deadline"]["evidence"]="OLD deadline: 15 December 2026 — cancelled"
        self.assertEqual(validate_fields(doc,raw,.8)["deadline"]["value"],"unknown")

    def test_sources_are_queued_and_configuration_is_case_insensitive(self):
        from http.server import ThreadingHTTPServer
        from urllib.request import Request,urlopen
        import threading
        from opportunityos.__main__ import handler_for
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory)
            agent=Agent(store)
            server=ThreadingHTTPServer(("127.0.0.1",0),None)
            server.RequestHandlerClass=handler_for(store,agent,server.server_port)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            address=f"http://127.0.0.1:{server.server_port}"
            try:
                with patch.object(agent,"request_source",return_value="fetching") as enqueue:
                    for channel in ["https://t.me/ExampleChannel","examplechannel"]:
                        request=Request(address+"/api/sources/add",json.dumps({"channel":channel}).encode(),
                                        {"Content-Type":"application/json","Origin":address})
                        with urlopen(request) as response:
                            self.assertEqual(json.load(response)["status"],"fetching")
                    self.assertEqual(store.settings()["telegram_channels"],["ExampleChannel"])
                    self.assertEqual(enqueue.call_count,2)
            finally:
                server.shutdown();server.server_close()

    def test_local_chat_provider_protocol_and_cloud_rejection(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        import threading
        from opportunityos.extraction_provider import generate
        received=[]
        class Provider(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                data=json.dumps({"choices":[{"message":{"content":json.dumps(document())}}]}).encode()
                self.send_response(200);self.end_headers();self.wfile.write(data)
        server=ThreadingHTTPServer(("127.0.0.1",0),Provider)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            item=extract(RAW,{"extraction_provider":"local_chat","extraction_model":"fixture",
                              "extraction_endpoint":f"http://127.0.0.1:{server.server_port}"})
            self.assertEqual(item["extraction_engine"],"local_chat")
            self.assertTrue(received[0]["response_format"]["json_schema"]["strict"])
            with self.assertRaises(ValueError):
                generate([],{},{"extraction_provider":"ollama","extraction_endpoint":"https://outside.example"})
        finally:
            server.shutdown();server.server_close()

    def test_real_unreachable_provider_falls_back(self):
        item=extract(RAW,{"extraction_provider":"ollama","extraction_model":"missing",
                          "extraction_endpoint":"http://127.0.0.1:1","extraction_timeout":1})
        self.assertEqual(item["extraction_engine"],"regex_fallback")


if __name__ == "__main__":
    unittest.main()
