# OpportunityOS upgrade verification — November 27, 2026

| Check | Result | Evidence |
| --- | --- | --- |
| Build / syntax | PASS | Python compileall; JavaScript node --check |
| Types | Not configured | Plain Python/JavaScript; no project type-checker configuration |
| Lint | Not configured | Syntax and git diff --check passed; no project linter configured |
| Automated tests | PASS | 60 tests, zero failures, 35.993 seconds; includes real Playwright on a disposable local form |
| Coverage | Not collected | No coverage tool configured; no percentage claimed |
| Credential scan | PASS | No credential-shaped literals in changed source/tests/docs; private files excluded |
| Diff review | PASS | Source allow-list, approval gate, cancellation, persistence, duplicate prevention and error outcomes reviewed; store.py/workflow.py unchanged |
| Browser UI | PASS | Nine pages at 1440 × 1000 and 390 × 844; no overflow or JavaScript/CSP errors; existing favicon 404 retained |
| Approval UI | PASS | Form/Gmail previews, one-use tokens, refresh/close/approve, connection and browser fallback; all action requests intercepted |
| Target deployment | VERIFIED | macOS LaunchAgent, localhost:8765, runtime files match checkout; installed Codex 0.169.0-alpha.11.1 |

## Live evidence

- Public discovery: nine genuine feeds, 111 posts, 10.5 seconds; no inference in discovery. The dashboard publishes source results as they finish.
- Cloud package: a real Notion internship plus existing verified profile/CV produced a package in 34.7 seconds. It identified a graduation requirement conflict and missing facts. No application was submitted.
- Public portal: a real Notion/Ashby form exposed 41 visible controls; four synthetic known fields were filled and six unresolved required fields were identified. Application writes were blocked.
- Authorized local form: CV upload, explicit approval and one confirmed submission passed; changed profile and ambiguous confirmation were refused. No external application was submitted by these tests.
- Existing Gmail connector: actual mailbox/draft access and an unsent self-addressed setup message with the user's CV were verified. Read-back reached Awaiting approval, one attachment, no missing fields. Its approval was invalidated after the demonstration. No Gmail message was sent.
- Official app-server gate: a declined create_draft did not execute; an accepted harmless draft with a text attachment and no recipient returned actual draft/message IDs. Sending was tested with a synthetic mailbox, never a real recipient.
- Deployed Gmail connection: Connected through the installed service without another login.
- Final idle state: manual discovery, cloud provider selected, no loaded Ollama model. No heavy work starts on login or service restart.

Screenshots and private tool evidence remain in ignored output/private application directories. They are not GitHub artifacts because they can contain profile or CV information.

## Limits

Real external form submission and Gmail delivery still require the user's explicit approval of that prepared application. Unsupported portal widgets, CAPTCHA, login restrictions, missing facts and plan limits can interrupt a workflow. Browser Gmail delivery has not been authenticated or tested; it is an optional fallback. Response monitoring remains the separate metadata-only OAuth integration. Website-wide reliability is not inferred from successful local tests.

Local checks: PASS. Target installation and Gmail draft acceptance: VERIFIED. Real external delivery: NOT PERFORMED; the next permitted step is approval of a specific reviewed application or email.
