# OpportunityOS progress

## Verified on November 10, 2026

- The local dashboard and SQLite backend started successfully on macOS.
- Live discovery stored 95 early-career listings from Waymo (63), Figma (9), Cloudflare (7), Databricks (12), and Scale AI (4).
- A separate 30-link HTTP probe received 9 HTTP 200 responses and 21 HTTP 202 responses. The 202 responses did not verify the listing content. Board publication and eligibility are tracked separately.
- Nine backend tests passed for deduplication, delisting, offline preservation, stale data, degree filtering, draft review and tracking, submission policy, scheduler boundaries, pause/stop and private document import.
- Chrome passed a disposable-database test covering profile verification, filtering live listings, draft creation, review and marking ready. On the sandbox it blocked an incomplete application and verified a synthetic receipt on the complete form. No real application was submitted.
- The preloaded profile and discovery database live outside Git. No personal documents or credentials were supplied.

## Partially implemented

- Coverage is limited to public internship/fellowship listings on five employer boards. Portal question metadata is read-only and may be unavailable. The sandbox is the only browser form adapter.
- Funding uses published pay text. Most structured eligibility criteria, deadline extraction, urgency, competitiveness and fee assessment remain manual. Schedule behavior is tested with synthetic times. A macOS LaunchAgent starts the dashboard at login and keeps it available while logged in. Discovery still waits for the configured work window and does not run during sleep.
- Document import stores copies without extracting facts. Drafting has a tested offline outline and an optional Ollama provider that has not been exercised against an installed model.
- Gmail has a metadata-only CLI and dashboard signals. Real OAuth, Keychain persistence, and Gmail account behavior require a configured client and consent. This connector does not match messages to individual applications or synchronize automatically.

## Next milestones

1. Add official university, research and funded program adapters with structured deadlines, funding and nationality evidence.
2. Validate public form metadata on more portals and add a dedicated adapter only for a destination with explicit automation permission. Prove idempotency and confirmation capture before enabling real automatic submission.
3. Authenticate and test Gmail, add conservative message-to-application matching, and add opt-in Telegram notifications.
4. Implement the documented ChatGPT OAuth flow with protected credentials, user-approved context and visible plan/credit controls.
5. Add a verified launchd setup and per-source retry checkpoints. Consider university deployment after personal workflows and data controls are stable.

## Availability fix

- Installed and verified the per-user macOS service against the existing 95-listing database. Browser polling uses a small heartbeat response between activity changes.

## Telegram to Google Form slice — November 16, 2026

- Preserved store.py, workflow.py and the existing profile/facts UI. The new checkout is in the current Internship OS workspace.
- Replaced discovery.py with sources/greenhouse.py and sources/telegram.py, with extraction.py as a separate step. Existing Greenhouse IDs and stored applications remain compatible.
- Added raw Telegram text, permalink, publication date, extraction fields, missing-criterion flags, explicit profile restrictions before scoring, deadline expiry filtering and persistent application preferences.
- Added a configurable channel list and a source allow-list for prefill. The demonstration channel opportunity_alerts was chosen during implementation and added to local discovery. Form-fill sources remain opt-in.
- Demonstrated 20 live posts through the dashboard to the real 2026 Future of Work Summit Google Form. Synthetic verified name/email values were filled, unresolved questions were shown and the local review screenshot was displayed. No real applicant data or form response was sent in this demonstration.
- 14 backend tests passed, including nationality rejection before scoring and allow-list denial. The live Chrome end-to-end test passed. Node syntax validation passed.
- The Google adapter handles visible recognized text fields on the first page. Uploaded documents, radio choices, subjective answers, login and multi-page progression require manual handling. Raw claims are evidence, not independent verification. Unsupported deadline/eligibility wording stays unknown.
- The legacy blocker function remains byte-for-byte in workflow.py as requested. The new Google Form path does not use it, and cannot submit. Per-submission approvals, Gmail CV drafting and the UI redesign are deferred beyond this first slice.

- Repaired login startup by staging the runtime and copying the existing private database/documents to ~/Library/Application Support/OpportunityOS/data. The original data folder remains as a backup. Confirmed the heartbeat and live service snapshot after installation.

## Evidence-based discovery — November 16, 2026

- Kept store.py, workflow.py and the profile/facts system unchanged.
- Added strict-schema local LLM extraction, per-field model confidence and verbatim evidence. Qwen3:4b is installed and configured as the default. Ollama and local chat-completions providers are configurable. Regex is the labeled fallback. Unknown/unsupported fields remain unknown. New inference is budgeted and successful unchanged extractions are cached.
- Added Sources with immediate/queued Telegram fetching and an Instagram/LinkedIn link/text paste inbox. Browser-tested a live public channel and a Russian pasted test post through local Ollama, including evidence highlighting.
- Discovery now defaults to 30-minute checks while the server is running, with no overlapping runs. Working-window and AC-only modes remain configurable. Last-successful-check indicators are visible globally and source health remains visible. Queue state and attempt timestamps survive restarts.
- Added opt-in Telegram bot notification code for new strong matches and deadlines within 48 hours, persistent deduplication, rate-limit deferral and conservative handling of ambiguous delivery. Bot tokens are stored through macOS Keychain. Real bot delivery remains untested pending the user's bot token and private chat ID.
- 29 automated tests passed. They cover extraction evidence, unknowns, schema failure/offline fallback, caching, source add/dedup, local provider protocol, cadence, notifications and existing workflows.
- Ten fixed-label synthetic multilingual posts were benchmarked on local Qwen3:4b. Final exact agreement was 84/100 fields versus 59/100 for regex. Among populated model fields, 67/70 matched exactly. All 17 gold unknown fields stayed unknown. This small synthetic benchmark is not a real-world accuracy estimate. Results and raw model JSON are recorded in tests/fixtures/benchmark-results.json, with a runnable benchmark command in README.
- Remaining quality limits include abstention on some clear requirements, document naming differences, and a weak Russian PhD case (5/10 exact). Confidence is model-reported and uncalibrated. Posts are source evidence, not independent eligibility verification. Date-only deadlines have unverified cutoff times. Blocked social previews require pasted text.

- Verified a genuine live Telegram post through Qwen3:4b and the shared ingestion path, persisted with model provenance. The measured standalone extraction took 89.5 seconds; the provider timeout is 180 seconds. A bounded one-model-call source refresh checked 20 real posts. The updated runtime is staged in the macOS login service. No synthetic benchmark posts were inserted into the personal database.
- Restart recovery resumes persisted source requests even when an interrupted fetch left its health status as Fetching.

## Manual search and resource use — November 16, 2026

- Changed the default and this Mac’s saved operating schedule to Manual only. Timer ticks, login/restarts, wake, and adding a channel do not start discovery in manual mode. Run search performs one pass; manual pasted-post extraction remains an explicit action.
- Stopped discovery and verified no Ollama models were loaded. Extraction now requests immediate model unloading after each response instead of keeping it resident for two minutes.
- Added a regression test for manual mode, queued sources, and restart behavior. Existing scheduled modes remain available only when selected in Settings.
- Validation: 30 automated tests passed, including the Ollama immediate-unload request contract. Playwright verified Manual only, Run search, and Save source in the deployed dashboard. A 35-second check across a scheduler tick after service restart confirmed no new discovery attempt and no loaded Ollama model.

## Light landscape interface — November 16, 2026

- Replaced the dark vermilion interface with a light blue/white workspace, dark slate text, blue actions, locally bundled typography, consistent line icons, and an existing landscape banner reused from the user's OnePrep-inspired Ikigai project. No image generation or external asset requests.
- Restyled all nine pages, pipeline, source evidence drawer, forms, status indicators and mobile navigation. Today now accurately describes manual-only search instead of claiming a timer is enabled.
- Completed two desktop/mobile screenshot passes for all nine pages plus the evidence drawer. The second pass corrected checkbox alignment and added visible stage jumps to the application board. Screenshots remain local in ignored outputs/light-pass1 and outputs/light-pass2.
- Playwright verified no page overflow at 1440px/390px, local landscape rendering, light colors, manual settings, inbox filtering, evidence drawer, paste controls, profile expansion and source controls. No JavaScript or CSP errors; the existing harmless favicon 404 is recorded separately. No model inference or discovery was launched during these checks.
- Repeatable browser check: PYTHONPATH=. .venv/bin/python tests/ui_browser_smoke.py --data /absolute/path/to/private-data. It tests a temporary database copy. Backend modules, API routes, profile/facts, application logic and manual-only scheduling are unchanged.
- Final checks: 30 backend tests passed, JavaScript syntax and diff checks passed, and the staged macOS service rendered the new landscape dashboard. Additional live layout checks passed at 320px, 768px and 1024px. Agent remained Idle with manual scheduling and no loaded Ollama model.

## Upgrade 1: fast discovery — November 26, 2026

- Discovery now fetches up to three public sources concurrently, publishes each completed source immediately, and performs no local or remote model inference during search. Progress is visible in the header. Manual scheduling is preserved.
- Added official Ashby adapters for OpenAI, Perplexity and Notion; public feeds were verified live. Existing source snapshots and personal data are retained.
- Stale opportunities stay visible with an explicit refresh notice. Duplicate application URLs are grouped in the active feed while preserving source evidence and application history. Fixed logo hash navigation.
- Added tests proving parallel fetches, zero inference in fast scans, duplicate grouping and Ashby response filtering.

## Upgrade 2: cloud-backed application packages — November 26, 2026

- Added official non-interactive Codex structured output using the existing ChatGPT login. Tools, user hooks, browser/computer access and shell execution are disabled in inference calls; sessions are ephemeral, cancellable, and limited to one cloud request at a time. API-key environment variables are removed and non-ChatGPT logins are refused. This uses plan allowance, not unlimited/free API access. No local model is required.
- Added local PDF/DOCX/text CV reading, grounded application packages, source references, actual Greenhouse question inspection, regeneration history, downloadable cover letters, and unsent email files with the master CV attached. Existing verified facts are preserved; CV reading does not auto-verify new facts.
- Added persistent preparation tasks and working Review Center controls, cancel/retry, cloud connection checking, and email editing. The original store.py and workflow.py remain unchanged.
- Fixed extraction validation to reject a deadline date or nationality contradicted by its quote.
- The actual fast source refresh completed 9 feeds / 111 posts in 10.5 seconds. A genuine Notion listing was prepared with the user's existing CV and verified facts through ChatGPT in 34.7 seconds. It flagged a graduation-date conflict and other missing eligibility facts rather than inventing them. No application was sent.
- 41 automated tests passed before the final UI verification, covering CV reading, attachments, history, unsupported evidence, cancellation, restart behavior and the existing pipeline.

## Upgrade 3: browser preparation and explicit submission — November 26, 2026

- Added an isolated, persistent Playwright browser controller for public forms and Gmail. It inspects real fields, maps verified/share-approved facts and prepared answers, and can request bounded cloud mappings for unfamiliar questions. No model-generated code is executed. Unknown, demographic and legal answers are not guessed.
- Preparation can automatically open the supported official portal after cloud drafting. Other destinations require a one-time explicit allowance. The review screen shows fields, destination, screenshots and attachments. A one-use approval is bound to the preview, application content, verified facts and CV hash. Changes invalidate approval; duplicate clicks and duplicate confirmed submissions are blocked.
- Final submission is distinct from preparation. The app only records Submitted after observing destination confirmation. An ambiguous outcome is Unconfirmed and is never retried automatically. Private browser profiles, screenshots and results live outside Git.
- Added Gmail sign-in in an isolated browser without a Google Cloud project or password collection. Gmail drafting uses a normal signed-in browser; sending still requires explicit review and approval. Real authenticated Gmail delivery remains dependent on the user's sign-in and has not been exercised. Downloadable unsent email files remain a fallback.
- The browser was checked against a real Notion/Ashby application using synthetic facts and blocked writes. It rendered 41 visible controls, filled four known fields and identified six unresolved required questions. Allowed only verified public read-only GraphQL queries; application writes remained blocked. This is a prefill check, not evidence of a real submission.
- Playwright tests use a disposable local form to verify approval gating, CV attachment, one confirmed submission, refusal of changed-profile approval, sensitive/legal fields, changed recipients and ambiguous confirmation. External forms with unsupported widgets, multi-page transitions, authentication restrictions, assessments or CAPTCHA can still require human intervention.
- Final validation: 47 tests passed, including real Playwright interactions on the authorized local form. The all-pages browser smoke passed desktop/mobile. A separate UI check verified preview fields, review/close/approve controls, token requests and confirmation rendering using intercepted synthetic responses, so it could not submit anything externally.
- The deployed service's cloud/browser modules matched the checkout. No Ollama model was loaded. Google's sign-in window was opened for the one-time Gmail connection; authenticated Gmail drafting/sending is not claimed tested while that connection is pending.
