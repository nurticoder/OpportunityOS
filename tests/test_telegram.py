import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from opportunityos.sources.telegram import Posts, channel_name
from opportunityos.extraction import extract, expired
from opportunityos.evaluation import evaluate
from opportunityos.google_forms import fact_key, allowed_link
from opportunityos.store import Store
from opportunityos.sources import refresh


class TelegramSlice(unittest.TestCase):
    def test_nested_post_text_and_evidence(self):
        parser = Posts()
        parser.feed('<div data-post="publicchannel/42"><div class="tgme_widget_message_text"><b>Internship</b><br>Apply <a href="https://forms.gle/abc">here</a></div><a>99 views</a><time datetime="2026-11-15"></time></div>')
        post = parser.posts[0]
        self.assertEqual(post["raw_text"], "Internship\nApply here")
        item = extract(post, {"extraction_provider": "regex"})
        self.assertEqual(item["apply_method"], "google_form")
        self.assertEqual(item["evidence"], "https://t.me/publicchannel/42")
        self.assertEqual(item["application_link"], "https://forms.gle/abc")
        self.assertEqual(item["organization"], "Unknown")

    def test_extract_and_hard_filter_before_scoring(self):
        raw = {"id": "telegram:channel/1", "source_link": "https://t.me/channel/1",
               "raw_text": "AI Internship\nOrganization: Example\nDeadline: 3 December 2026\nNationality: India\nCountry of study: Hong Kong\nLevel: Undergraduate\nCV required\nhttps://forms.gle/abc"}
        item = extract(raw, {"extraction_provider": "regex"})
        self.assertEqual(item["deadline"], "2026-12-03")
        self.assertEqual(item["required_documents"], ["CV"])
        with tempfile.TemporaryDirectory() as d:
            facts = Store(d).facts()
        for key, value in {"citizenship": "Kyrgyzstan", "location": "Hong Kong", "academic_level": "Undergraduate"}.items():
            facts[key].update(value=value, verified=True)
        result = evaluate(item, facts, {})
        self.assertEqual(result["score"], 0)  # Empty weights prove scoring was never reached.
        self.assertEqual(result["eligibility"], "Ineligible")

    def test_unknowns_and_expiry(self):
        item = extract({"raw_text": "Deadline: 10 Nov\nNationality: excellent applicants from all regions",
                        "source_link": "https://t.me/channel/2"}, {"extraction_provider": "regex"})
        self.assertIsNone(item["deadline"])
        self.assertFalse(expired(item))
        self.assertTrue(expired({"deadline": "2020-01-01"}))

    def test_source_allowlist(self):
        from opportunityos.google_forms import FormReviews
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            with self.assertRaisesRegex(ValueError, "allow-list"):
                FormReviews(store).start({"id": "telegram:channel/1", "source": "telegram:channel",
                                         "application_link": "https://forms.gle/example"}, {})

    def test_form_and_channel_validation(self):
        self.assertEqual(channel_name("https://t.me/s/examplechannel"), "examplechannel")
        for bad in ["../../etc", "https://localhost/test", "examplechannel?before=1"]:
            with self.assertRaises(ValueError):
                channel_name(bad)
        self.assertFalse(allowed_link("https://docs.google.com.evil.example/forms/d/1"))
        self.assertFalse(allowed_link("http://forms.gle/id"))
        self.assertEqual(fact_key("Your full name *"), "name")
        self.assertIsNone(fact_key("Explain your leadership experience"))


if __name__ == "__main__":
    unittest.main()
