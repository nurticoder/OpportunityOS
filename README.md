# OpportunityOS

A local opportunity desk with an evidence-backed discovery feed and application review queue.

## Start on this Mac

Use Python 3.10 or newer. The dashboard and discovery require no packages.

```sh
./start.sh --data ../../work/local-data
```

Open http://127.0.0.1:8765. This installation's private data directory already contains the first live discovery run and the onboarding facts, which are unverified until you confirm them in Profile. Keep the data directory outside the checkout. On a fresh installation, omit the data argument to use `~/Library/Application Support/OpportunityOS`, then click **Run now**. A terminal-only refresh is available with `./start.sh --discover`. To refresh the existing installation from the terminal, include its data argument.

1. Verify facts and import any supporting files in **Profile**.
2. In **Discover**, filter listings, open their evidence and check the official listing and public portal questions where available.
3. Enter the actual prompt and word limit. Prepare a draft, edit it in **Review Center**, then mark it ready.
4. Apply on the official portal. Record its confirmation in **Applications** and track the outcome there.

## Optional components

- **Local AI.** Start Ollama separately and configure an installed model in Settings. OpportunityOS calls its loopback API only when drafting from a question and verified facts. It falls back to an offline outline if Ollama is unavailable. Review the draft for unsupported claims and the actual word count.
- **Browser sandbox.** With Python 3.14, create a venv and install `requirements-browser.txt`. Run `python -m opportunityos.browser --submit-test` in that environment while the dashboard is running. The adapter uses installed Chrome if available, otherwise run `python -m playwright install chromium`. This workflow uses synthetic data and is restricted to the bundled loopback form.
- **Gmail.** Install `requirements-gmail.txt` in a venv. Enable Gmail API in Google Cloud and create a desktop OAuth client. Keep the downloaded JSON outside the repository. Create a dedicated Gmail label called OpportunityOS, then label application messages. Run `python -m opportunityos.gmail --data ../../work/local-data --authorize /path/to/client.json`. For later scans omit `--authorize`. The connector uses the metadata-only scope and Keychain through keyring, fetches subjects for the first page of the selected label, and displays inferred signals in Applications. It never changes Gmail or automatically changes application status. An HKU account can use a different `--account` label. Live OAuth requires your Google consent and remains unverified. [Google's desktop OAuth quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) · [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- **ChatGPT Plus.** OpenAI documents eligible local personal apps using Sign in with ChatGPT for account-specific models and eligible streaming Responses API calls. Usage shares the Plus five-hour allowance across connected apps and can also be subject to app-specific limits and available credits. The preview supports model-dependent text, images and files, with no hosted file search, code execution, computer use or access to existing ChatGPT chats. This release uses offline/Ollama drafting and does not ship the ChatGPT OAuth adapter. [OpenAI cookbook](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt) · [Usage limits](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions) · [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

## How it works

- Python's standard library serves a loopback-only dashboard and JSON API. SQLite stores facts, discovery evidence, settings, and application history. Local documents are private file copies. The app uses owner-only data permissions, same-origin mutation checks, an asset CSP and escaped UI output. Use OS disk encryption for encrypted storage. A process already running under your macOS account is trusted by this local app.
- The discovery adapter reads five public employer Greenhouse feeds. It deduplicates by source ID and URL, keeps removed postings for history, and excludes old snapshots from active ranking. A board's public listing is a discovery signal. Use the official portal to confirm open status and the exact requirements. [Greenhouse Job Board API](https://docs.greenhouse.io/job-board)
- Ranking uses title-based alignment and degree clues, official-board evidence and disclosed pay text. Citizenship, age, work authorization, and many other criteria remain manual checks. Scores indicate relative priority and do not estimate acceptance odds.
- The foreground scheduler checks every 30 seconds and defaults to Monday, Wednesday and Friday, 7–9 p.m. Hong Kong time. It runs only while the app is open and the Mac is awake, with an optional AC-only setting. Missed windows defer to the next permitted window. Stop and Pause take effect between source fetches and are reset on process restart.

## Tests

```sh
python3 -m unittest discover -s tests -v
PYTHONPATH=. python tests/browser_smoke.py ../../work/local-data
```

The second command requires the browser environment. It copies the database to a temporary directory before making changes.

See [PROGRESS.md](PROGRESS.md) for the implementation and test record.
