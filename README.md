# OpportunityOS

A local opportunity desk with an evidence-backed discovery feed and application review queue.

## Start on this Mac

The dashboard on this Mac is already installed as a login service. Open http://127.0.0.1:8765. The manual command below is for running with the login service stopped. Use Python 3.10 or newer. The dashboard and discovery require no packages.

```sh
./start.sh --data /absolute/path/to/private-data
```

Open http://127.0.0.1:8765. This installation's private data directory already contains the first live discovery run and the onboarding facts, which are unverified until you confirm them in Profile. Keep the data directory outside the checkout. On a fresh installation, omit the data argument to use `~/Library/Application Support/OpportunityOS`, then click **Run now**. A terminal-only refresh is available with `./start.sh --discover`. To refresh the existing installation from the terminal, include its data argument.

1. Verify facts and import any supporting files in **Profile**.
2. In **Discover**, filter listings, open their evidence and check the official listing and public portal questions where available.
3. Enter the actual prompt and word limit. Prepare a draft, edit it in **Review Center**, then mark it ready.
4. Apply on the official portal. Record its confirmation in **Applications** and track the outcome there.

## Run at macOS login

This Mac uses a per-user LaunchAgent to keep the dashboard available. To install it on another Mac from the checkout directory, run `python3 -m opportunityos.service install`. Pass `--data /path/to/private/data` when using an existing database. Stop any foreground server on the same port before installing. Use `python3 -m opportunityos.service status`, `restart`, or `uninstall` to manage the service. Keep the checkout at its installed location, or reinstall the service after moving it. The app still respects its discovery window and the Mac's sleep state.

## Optional components

- **Local AI.** Start Ollama separately and configure an installed model in Settings. OpportunityOS calls its loopback API only when drafting from a question and verified facts. It falls back to an offline outline if Ollama is unavailable. Review the draft for unsupported claims and the actual word count.
- **Browser sandbox.** With Python 3.14, create a venv and install `requirements-browser.txt`. Run `python -m opportunityos.browser --submit-test` in that environment while the dashboard is running. The adapter uses installed Chrome if available, otherwise run `python -m playwright install chromium`. This workflow uses synthetic data and is restricted to the bundled loopback form.
- **Gmail.** Install `requirements-gmail.txt` in a venv. Enable Gmail API in Google Cloud and create a desktop OAuth client. Keep the downloaded JSON outside the repository. Create a dedicated Gmail label called OpportunityOS, then label application messages. Run `python -m opportunityos.gmail --data /absolute/path/to/private-data --authorize /path/to/client.json`. For later scans omit `--authorize`. The connector uses the metadata-only scope and Keychain through keyring, fetches subjects for the first page of the selected label, and displays inferred signals in Applications. It never changes Gmail or automatically changes application status. An HKU account can use a different `--account` label. Live OAuth requires your Google consent and remains unverified. [Google's desktop OAuth quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) · [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- **ChatGPT Plus.** OpenAI documents eligible local personal apps using Sign in with ChatGPT for account-specific models and eligible streaming Responses API calls. Usage shares the Plus five-hour allowance across connected apps and can also be subject to app-specific limits and available credits. The preview supports model-dependent text, images and files, with no hosted file search, code execution, computer use or access to existing ChatGPT chats. This release uses offline/Ollama drafting and does not ship the ChatGPT OAuth adapter. [OpenAI cookbook](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt) · [Usage limits](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions) · [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

## How it works

- Python's standard library serves a loopback-only dashboard and JSON API. SQLite stores facts, discovery evidence, settings, and application history. Local documents are private file copies. The app uses owner-only data permissions, same-origin mutation checks, an asset CSP and escaped UI output. Use OS disk encryption for encrypted storage. A process already running under your macOS account is trusted by this local app.
- The discovery adapter reads five public employer Greenhouse feeds. It deduplicates by source ID and URL, keeps removed postings for history, and excludes old snapshots from active ranking. A board's public listing is a discovery signal. Use the official portal to confirm open status and the exact requirements. [Greenhouse Job Board API](https://docs.greenhouse.io/job-board)
- Ranking uses title-based alignment and degree clues, official-board evidence and disclosed pay text. Citizenship, age, work authorization, and many other criteria remain manual checks. Scores indicate relative priority and do not estimate acceptance odds.
- The foreground scheduler checks every 30 seconds and defaults to Monday, Wednesday and Friday, 7–9 p.m. Hong Kong time. It runs while the server is running and the Mac is awake, with an optional AC-only setting. Missed windows defer to the next permitted window. Stop and Pause take effect between source fetches and are reset on process restart.

## Tests

```sh
python3 -m unittest discover -s tests -v
PYTHONPATH=. python tests/browser_smoke.py /absolute/path/to/private-data
```

The second command requires the browser environment. It copies the database to a temporary directory before making changes.

See [PROGRESS.md](PROGRESS.md) for the implementation and test record.

## Telegram and Google Form slice

Settings accepts up to 20 public channel usernames. Run now fetches the latest public preview page per channel. Posts outside that rolling page remain in the evidence history. The adapters return raw posts, then a separate deterministic extractor identifies application links, deadline text, explicit eligibility restrictions and requested documents. Unsupported wording remains unknown and the raw text is available in opportunity details.

Expired deadlines are hidden from Discover, including its expanded history filter. Verified citizenship, location and academic level are compared against recognized explicit restrictions before scoring. Location currently supplies country of study as requested, so verify that it records your study location. Unrecognized restrictions still require review.

Each opportunity has Apply automatically, Review first and Skip preferences. In this first slice, both application preferences allow preparation. Skip removes the item from recommendations. There is no live submission endpoint. The Google adapter uses a source allow-list plus the user's Prefill action, without depending on the legacy blocker tuple in the preserved workflow module. The next submission phase must add a separate approval for each concrete submission. Email CV drafts and the visual redesign are later phases.

To prefill, put a source such as `telegram:opportunity_alerts` in the form allow-list. Verify the desired facts and allow sharing of them in Profile. Open a Google Form opportunity and click Prefill. Only recognized text/email fields are mapped, leaving choices, uploads, essays, multi-page navigation and declarations for manual review. Every browser write request is blocked. The filled browser stays visible for up to ten minutes, and a local screenshot and field report remain available in the review output. Closing and reopening the original URL starts a fresh form.

The service uses the existing Python Playwright environment on this Mac. Other installations need requirements-browser.txt and Chrome or a Playwright Chromium installation. Authentication-required and closed forms return an attention message.

The repeatable real-source demonstration is `PYTHONPATH=. python tests/telegram_browser_smoke.py` with Playwright installed. It reads public opportunity_alerts posts into a disposable database and fills a real summit registration form using synthetic verified name/email values. It sends no form response. Source content and form availability can change.
