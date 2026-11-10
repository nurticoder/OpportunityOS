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
