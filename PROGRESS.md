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
