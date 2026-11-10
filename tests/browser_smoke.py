"""Run against a disposable copy of the live database."""
import argparse
import os
import sqlite3
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from opportunityos.__main__ import handler_for
from opportunityos.agent import Agent
from opportunityos.browser import CHROME, SAMPLE, fill_sandbox
from opportunityos.store import Store


def main(source):
    os.umask(0o077)
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory)
        with sqlite3.connect(Path(source) / "opportunity.sqlite") as original:
            with store.db() as db:
                original.backup(db)
                db.execute("DELETE FROM applications")
        agent = Agent(store)
        server = ThreadingHTTPServer(("127.0.0.1", 0), None)
        port = server.server_port
        server.RequestHandlerClass = handler_for(store, agent, port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=str(CHROME) if CHROME.is_file() else None)
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}")
                page.get_by_role("button", name="Profile").click()
                page.locator('summary').filter(has_text="university").click()
                form = page.locator('[data-fact="university"]')
                form.get_by_role("textbox", name="Value").fill("Test University")
                form.get_by_role("checkbox", name="I verified this fact").check()
                form.get_by_role("button", name="Save fact").click()
                expect(page.get_by_role("status")).to_have_text("Profile saved")
                page.get_by_role("button", name="Discover", exact=False).first.click()
                page.get_by_role("searchbox").fill("Waymo")
                expect(page.locator("#listings article").first).to_contain_text("Waymo")
                page.get_by_role("button", name="View evidence").first.click()
                page.get_by_role("textbox", name="Application question").fill("Why this position?")
                page.get_by_role("button", name="Prepare draft for review").click()
                expect(page.get_by_role("heading", name="Review Center")).to_be_visible()
                page.locator("[data-app] summary").first.click()
                expect(page.locator("[data-app]").first).to_contain_text("Test University")
                page.get_by_role("textbox", name="Draft", exact=True).fill("I am applying to learn through this internship.")
                page.get_by_role("button", name="Save draft").click()
                expect(page.get_by_role("status")).to_have_text("Application updated")
                page.get_by_role("button", name="Mark ready").click()
                expect(page.get_by_text("No drafts awaiting review.")).to_be_visible()
                page.get_by_role("button", name="Applications", exact=False).first.click()
                page.locator("[data-app] summary").first.click()
                expect(page.locator("[data-app]").first).to_contain_text("Ready")
                sandbox = browser.new_page()
                try:
                    fill_sandbox(sandbox, port, {"name": SAMPLE["name"]}, True)
                except ValueError as error:
                    assert "complete" in str(error), error
                else:
                    raise AssertionError("Incomplete form was submitted")
                sandbox = browser.new_page()
                receipt = fill_sandbox(sandbox, port, SAMPLE, True)
                assert receipt.startswith("LOCAL-TEST-"), receipt
                print("Chrome smoke passed: profile verification, discovery filter, draft, review, sandbox policy and receipt")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    main(parser.parse_args().source)
