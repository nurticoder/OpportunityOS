# OpportunityOS

A local opportunity desk with an evidence-backed discovery feed and application review queue.

## Start on this Mac

The dashboard on this Mac is already installed as a login service. Open http://127.0.0.1:8765. The manual command below is for running with the login service stopped. Use Python 3.10 or newer. Fast discovery does not require a local model. Cloud preparation uses a ChatGPT-authenticated Codex CLI and optional PDF support from requirements-documents.txt.

```sh
./start.sh --data /absolute/path/to/private-data
```

Open http://127.0.0.1:8765. This installation's private data directory already contains the first live discovery run and the onboarding facts, which are unverified until you confirm them in Profile. Keep the data directory outside the checkout. On a fresh installation, omit the data argument to use `~/Library/Application Support/OpportunityOS`, then click **Run search**. A terminal-only refresh is available with `./start.sh --discover`. To refresh the existing installation from the terminal, include its data argument.

1. Verify facts and import any supporting files in **Profile**.
2. In **Discover**, filter listings, open their evidence and check the official listing and public portal questions where available.
3. Enter the actual prompt and word limit. Prepare a draft, edit it in **Review Center**, then mark it ready.
4. Apply on the official portal. Record its confirmation in **Applications** and track the outcome there.

## Run at macOS login

This Mac uses a per-user LaunchAgent to keep the dashboard available. To install it on another Mac from the checkout directory, run `python3 -m opportunityos.service install`. Pass `--data /path/to/private/data` when using an existing database. Stop any foreground server on the same port before installing. Use `python3 -m opportunityos.service status`, `restart`, or `uninstall` to manage the service. Installation stages the runtime and optional virtual-environment packages in Application Support. Run install again from the checkout after source updates. Discovery follows its configured interval or optional work window and pauses while the Mac sleeps.

## Optional components

- **Cloud AI.** Application preparation uses the installed Codex CLI with your existing ChatGPT login. It consumes your plan allowance and refuses API-key logins; no paid API fallback is enabled. Search itself is model-free. Install requirements-documents.txt for PDF CV reading. Local providers are optional legacy choices, never required. See [cloud setup and privacy](docs/cloud-ai.md).
- **Browser sandbox.** With Python 3.14, create a venv and install `requirements-browser.txt`. Run `python -m opportunityos.browser --submit-test` in that environment while the dashboard is running. The adapter uses installed Chrome if available, otherwise run `python -m playwright install chromium`. This workflow uses synthetic data and is restricted to the bundled loopback form.
- **Gmail.** Install `requirements-gmail.txt` in a venv. Enable Gmail API in Google Cloud and create a desktop OAuth client. Keep the downloaded JSON outside the repository. Create a dedicated Gmail label called OpportunityOS, then label application messages. Run `python -m opportunityos.gmail --data /absolute/path/to/private-data --authorize /path/to/client.json`. For later scans omit `--authorize`. The connector uses the metadata-only scope and Keychain through keyring, fetches subjects for the first page of the selected label, and displays inferred signals in Applications. It never changes Gmail or automatically changes application status. An HKU account can use a different `--account` label. Live OAuth requires your Google consent and remains unverified. [Google's desktop OAuth quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) · [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- **ChatGPT Plus.** OpenAI documents eligible local personal apps using Sign in with ChatGPT for account-specific models and eligible streaming Responses API calls. Usage shares the Plus five-hour allowance across connected apps and can also be subject to app-specific limits and available credits. The preview supports model-dependent text, images and files, with no hosted file search, code execution, computer use or access to existing ChatGPT chats. This release uses offline/Ollama drafting and does not ship the ChatGPT OAuth adapter. [OpenAI cookbook](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt) · [Usage limits](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions) · [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

## How it works

- Python's standard library serves a loopback-only dashboard and JSON API. SQLite stores facts, discovery evidence, settings, and application history. Local documents are private file copies. The app uses owner-only data permissions, same-origin mutation checks, an asset CSP and escaped UI output. Use OS disk encryption for encrypted storage. A process already running under your macOS account is trusted by this local app.
- The discovery adapter reads five public employer Greenhouse feeds. It deduplicates by source ID and URL, keeps removed postings for history, and excludes old snapshots from active ranking. A board's public listing is a discovery signal. Use the official portal to confirm open status and the exact requirements. [Greenhouse Job Board API](https://docs.greenhouse.io/job-board)
- Ranking uses title and post alignment, extracted eligibility restrictions, official-board evidence and disclosed pay text. Citizenship, age, work authorization, and many other criteria remain manual checks. Scores indicate relative priority and do not estimate acceptance odds.
- Discovery is manual by default: click Run search. Automatic intervals and working-window operation are optional settings. The optional working window remains Monday, Wednesday and Friday, 7–9 p.m. Hong Kong time. It runs while the server is running and the Mac is awake, with an optional AC-only setting. Missed windows defer to the next permitted window. Stop and Pause take effect between source fetches and are reset on process restart.

## Tests

```sh
python3 -m unittest discover -s tests -v
PYTHONPATH=. python tests/browser_smoke.py /absolute/path/to/private-data
```

The second command requires the browser environment. It copies the database to a temporary directory before making changes.

See [PROGRESS.md](PROGRESS.md) for the implementation and test record.

## Telegram and Google Form slice

Settings accepts up to 20 public channel usernames. Run now fetches the latest public preview page per channel. Posts outside that rolling page remain in the evidence history. The adapters return raw posts, then a separate local-model extractor identifies application links, deadlines, explicit eligibility restrictions and requested documents, with a labeled regex fallback. Unsupported wording remains unknown and the raw text is available in opportunity details.

Expired deadlines are hidden from Discover, including its expanded history filter. Verified citizenship, location and academic level are compared against recognized explicit restrictions before scoring. Location currently supplies country of study as requested, so verify that it records your study location. Unrecognized restrictions still require review.

Each opportunity has Apply automatically, Review first and Skip preferences. In this first slice, both application preferences allow preparation. Skip removes the item from recommendations. There is no live submission endpoint. The Google adapter uses a source allow-list plus the user's Prefill action, without depending on the legacy blocker tuple in the preserved workflow module. The next submission phase must add a separate approval for each concrete submission. Email CV drafts and the visual redesign are later phases.

To prefill, put a source such as `telegram:opportunity_alerts` in the form allow-list. Verify the desired facts and allow sharing of them in Profile. Open a Google Form opportunity and click Prefill. Only recognized text/email fields are mapped, leaving choices, uploads, essays, multi-page navigation and declarations for manual review. Every browser write request is blocked. The filled browser stays visible for up to ten minutes, and a local screenshot and field report remain available in the review output. Closing and reopening the original URL starts a fresh form.

The service uses the workspace .venv with Homebrew Python and Playwright on this Mac. Prepared forms are also accessible in Review Center. Other installations need requirements-browser.txt and Chrome or a Playwright Chromium installation. Authentication-required and closed forms return an attention message.

The repeatable real-source demonstration is `PYTHONPATH=. python tests/telegram_browser_smoke.py` with Playwright installed. It reads public opportunity_alerts posts into a disposable database and fills a real summit registration form using synthetic verified name/email values. It sends no form response. Source content and form availability can change.

On this Mac, active private data is now in ~/Library/Application Support/OpportunityOS/data. The former data folder remains as a backup. The runtime is staged outside Documents because the login process stalled during interpreter initialization there.

## Discovery quality

Cloud Codex is now the default for explicitly requested AI extraction and application preparation. Fast discovery uses source metadata and conservative rules without a model. The following local provider options are optional legacy integrations: Ollama supports qwen3:4b. Run Ollama and install the model with `ollama pull qwen3:4b` on a new Mac. This Mac has the model installed. Settings also supports a local chat-completions server such as LM Studio at `http://127.0.0.1:1234/v1`, or explicit regex-only operation.

Every extracted field has a value, model-reported confidence and a verbatim quote. Unknown or low-confidence fields stay unknown. JSON shape, quote presence, dates, destination links and several common semantic errors are checked before persistence. Confidence is uncalibrated and quotes do not independently verify a source's claims. Failed or unavailable model extraction is labeled as regex fallback. The original post is retained in the evidence drawer.

Discovery defaults to Manual only. It never starts at login, after wake, or from a timer in this mode; click Run search for one pass. Automatic intervals (30 minutes by default) are available only if enabled in Settings. Settings can restrict this to the existing working window and AC-only operation. Missed intervals coalesce into one run after wake. Pause/Stop disable automatic checks until resumed. Checks never overlap. Unchanged successful extractions are cached. Discovery fetches up to three sources concurrently and does not perform LLM inference. Cloud analysis runs when preparing a selected application or explicitly extracting a pasted post. Change the maximum new model extractions per run in Settings for a different budget.

Use **Sources** or **Add source** on Today to paste a public Telegram channel URL. In manual mode it is saved for the next Run search; automatic modes fetch immediately or queue behind the current run. Source health and the last successful check are visible. Private or unavailable channels show source failures.

Use **Inbox → Paste a link or text** for Instagram/LinkedIn. Public metadata is fetched when accessible. If a platform needs authentication or blocks a preview, paste the post text with its original URL. Text-only posts work too. The same extractor and review workflow are used. Repeated submissions update the same saved post.

### Telegram notifications

Install requirements-notifications.txt in the service environment. In Settings, enter the bot token from @BotFather and your numeric private chat ID after starting a chat with your bot. Enable notifications to permit messages containing opportunity titles and source/application links. The bot credential is kept in macOS Keychain and never returned in dashboard state.

The notifier sends newly qualifying strong matches and closing dates within 48 hours. Date-only cutoffs are explicitly labeled unverified. Notifications are deduplicated persistently across restarts and repeated source posts. Rate-limited requests are deferred. Ambiguous delivery is retained without automatic retries to avoid duplicates. Live delivery requires your own credentials and has not been tested with a real account in this implementation.

### Extraction benchmark

```sh
PYTHONPATH=. .venv/bin/python tests/benchmark_extraction.py --provider ollama --model qwen3:4b
PYTHONPATH=. .venv/bin/python tests/benchmark_extraction.py --provider regex --output outputs/extraction-regex.json
.venv/bin/python -m unittest discover -s tests -v
```

The fixture file contains ten **synthetic**, realistic English, Russian and mixed-language posts with fixed expected labels. Scores count exact agreement across ten fields per post, including correct unknowns. The benchmark saves raw model JSON, confidence, evidence, errors and timings. This small benchmark measures these examples and does not establish real-world accuracy.

Recorded results for all ten examples, including expected and extracted values, are in [the extraction accuracy report](docs/extraction-accuracy.md).

Manual mode keeps the dashboard available without background discovery. Ollama unloads its extraction model after each response to release model memory. Explicitly pasting a post for extraction or generating a draft may still run local AI because those are user-triggered actions.

## One-click application preparation

Open an opportunity and click **Prepare application**, or choose **Apply** in triage. Review Center shows progress and the resulting package. The app rechecks stale official feeds, reads your existing master CV locally, fetches supported official question metadata, and sends the selected listing, share-approved verified facts and CV text to ChatGPT. CV claims remain document-sourced and require review; imported documents never silently change verification flags. Drafts include missing requirements and source references. Regeneration retains previous drafts. Submitted applications and duplicate destinations cannot be regenerated as new applications.

The cloud path does not invoke Ollama. You can cancel preparation using its task control or Stop. Only one cloud request runs at a time; the process is terminated on cancellation. An interrupted job stays interrupted after restart until you explicitly retry. Download the cover letter or, for a source-provided email destination, an unsent email file with the master CV attached. No email is sent by downloading it.

## Browser applications and Gmail

**Prepare application** now creates a grounded package and attempts to open its supported application in an isolated browser. Official Greenhouse/Ashby destinations are supported directly; unfamiliar destinations need explicit permission from the opportunity editor. The agent fills recognized standard controls and grounded answers. Sensitive/demographic questions and legal declarations are left for you. Missing work authorization, unavailable information, CAPTCHA or unsupported widgets are shown as exact requirements rather than guessed.

In Review Center, inspect the browser preview, complete genuinely missing questions in the opened browser, and click **Refresh review**. **Approve and submit** appears only for a complete preview. Its one-use token is bound to the current fields, draft, profile and CV. The controller requires a new review after changes and records Submitted only after a confirmation appears. If confirmation is ambiguous, check the destination; the agent blocks automatic retry to prevent duplicate applications. Browser sessions close after ten minutes and can be stopped from the dashboard. Complex multi-page portals and unsupported widgets may still require manual completion.

For email applications, click **Connect Gmail** in Settings and sign in once in Google's browser flow. OpportunityOS uses its own private Chrome profile, never copies your personal Chrome profile, and never asks for your password in chat. Once signed in, it can compose an unsent draft with the selected CV. Each send requires explicit approval and observed confirmation. This browser connector depends on Gmail's current UI and may stop if Google restricts automated access; it never bypasses those restrictions. The legacy metadata-only OAuth CLI remains separate. An unsent .eml download is available even when Gmail is not connected.

All private browser data and generated application artifacts stay in the application's private directory. The browser workflow runs only on request; it is not a background computer-control daemon.

Browser verification commands (Chrome and requirements-browser.txt required):

```sh
.venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=. .venv/bin/python tests/ui_browser_smoke.py --data /absolute/path/to/private-data
PYTHONPATH=. .venv/bin/python tests/browser_review_ui_smoke.py
```

The submission integration tests run only against their own disposable loopback form. The review UI test intercepts all submission calls and never submits to a real destination. Gmail or a real portal requires an authenticated, permitted session and an explicit per-application approval; those credentials and approvals cannot be fabricated by the test suite.
