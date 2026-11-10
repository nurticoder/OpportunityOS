"""Playwright adapter for the bundled, explicitly authorized loopback form."""
import argparse
from pathlib import Path

from .workflow import policy

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SAMPLE = {"name": "Test Applicant", "email": "test@example.invalid", "university": "Test University"}


def fill_sandbox(page, port, fields, submit=False):
    from playwright.sync_api import expect

    origin = f"http://127.0.0.1:{int(port)}"
    page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/") else route.abort())
    page.goto(origin + "/sandbox", wait_until="domcontentloaded")
    expect(page.get_by_role("heading", name="Local form-fill sandbox")).to_be_visible()
    names = ("name", "email", "university")
    required = ("name", "email")
    for name in names:
        if fields.get(name):
            page.locator(f'input[name="{name}"]').fill(fields[name])
    if not submit:
        return None
    checks = dict.fromkeys(("destination_allowed", "automation_permitted", "eligible", "free", "verified_fields",
                            "shareable_fields", "no_sensitive_documents", "no_essay", "no_legal_commitment",
                            "routine", "fresh", "unique"), True)
    checks["unique"] = page.locator("#receipt").text_content() == ""
    checks["complete"] = all(fields.get(name) for name in required) and page.locator("form").evaluate("(form) => form.checkValidity()")
    if blockers := policy(checks):
        raise ValueError("Sandbox submission blocked: " + ", ".join(blockers))
    page.get_by_role("button", name="Create test receipt").click()
    receipt = page.locator("#receipt")
    expect(receipt).to_contain_text("LOCAL-TEST-")
    return receipt.text_content()


def main():
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description="Fill the bundled synthetic local form")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--submit-test", action="store_true")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(CHROME) if CHROME.is_file() else None)
        page = browser.new_page()
        print(fill_sandbox(page, args.port, SAMPLE, args.submit_test) or "Sandbox fields filled")
        browser.close()


if __name__ == "__main__":
    main()
