"""Live public Telegram to Google Form demonstration with synthetic verified facts."""
import json
import os
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

from opportunityos.store import Store, now
from opportunityos.sources import refresh
from opportunityos.agent import Agent
from opportunityos.__main__ import handler_for

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main():
    os.umask(0o077)
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory)
        with store.db() as db:
            for key, value in {"name": "Test Applicant", "email": "test@example.invalid"}.items():
                db.execute("UPDATE facts SET value=?,verified=1,share=1,source='Synthetic demonstration' WHERE key=?", (value,key))
            for key,value in {"telegram_channels": ["opportunity_alerts"], "enabled_sources": [],
                              "source_allowlist": ["telegram:opportunity_alerts"]}.items():
                db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key,json.dumps(value)))
        count = refresh(store, "telegram:opportunity_alerts")
        server = ThreadingHTTPServer(("127.0.0.1", 0), None)
        server.RequestHandlerClass = handler_for(store, Agent(store), server.server_port)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=CHROME)
                page = browser.new_page(viewport={"width":1300,"height":1000})
                page.goto(f"http://127.0.0.1:{server.server_port}")
                page.get_by_role("button",name="Discover",exact=False).first.click()
                page.get_by_role("searchbox").fill("Future of Work Summit")
                page.get_by_role("button",name="View evidence").click()
                expect(page.locator("#detail")).to_contain_text("google_form")
                page.get_by_role("button",name="Prefill Google Form for review").click()
                expect(page.get_by_role("heading",name="Form prepared · review required")).to_be_visible(timeout=90000)
                expect(page.locator("#prefill-result")).to_contain_text("Filled from verified fact")
                Path("outputs").mkdir(exist_ok=True)
                page.screenshot(path="outputs/telegram-review-demo.png",full_page=True)
                img = page.locator('#prefill-result img')
                ident = img.get_attribute("src").split("/")[-1]
                result = json.loads((store.directory/"reviews"/(ident+".json")).read_text())
                assert sum(f["filled"] for f in result["fields"]) >= 2, result
                assert result["status"] == "Awaiting review"
                import shutil
                shutil.copyfile(store.directory/"reviews"/(ident+".png"),"outputs/form-review-demo.png")
                page.get_by_role("button",name="Close prepared browser").click()
                page.get_by_role("button", name="Close", exact=True).click()
                page.get_by_role("button", name="Review Center", exact=False).first.click()
                page.get_by_role("button", name="Open form review").click()
                expect(page.get_by_role("heading",name="Form prepared · review required")).to_be_visible()
                print(f"PASS: {count} live posts → extracted dashboard → real Google Form, synthetic name/email filled, review shown; no submission")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
