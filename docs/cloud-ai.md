# Cloud AI without local inference

OpportunityOS uses the official Codex CLI `exec` structured-output mode and the user's existing ChatGPT sign-in. This is a local personal automation, not a proxy for public or untrusted users. It does not copy tokens or call undocumented ChatGPT endpoints.

- Official authentication: https://learn.chatgpt.com/docs/auth
- Official non-interactive and JSON-schema output: https://learn.chatgpt.com/docs/non-interactive-mode
- Reviewed computer-use reference: https://github.com/openai/openai-cua-sample-app (requires an API key and API credits; not installed as a hidden paid dependency).

On this Mac the installed CLI is already signed in. On another Mac, install Codex, run `codex login` with ChatGPT, and use Check ChatGPT connection in Settings. API-key sessions are refused. Plan limits still apply; no unlimited use is promised. CLI binary discovery supports PATH and the installed macOS ChatGPT bundle. This integration requires CLI support for the flags used; an incompatible CLI reports a connection/request error rather than falling back to paid API calls.

Inference requests use an empty temporary working directory, read-only sandbox, disabled shell/apps/browser/computer tools, disabled hooks, ignored user config, ephemeral sessions, and a JSON output schema. The OpenAI API-key environment variables are removed from the subprocess. Only public posts or, for application preparation, the selected post plus share-approved verified profile facts and master CV text are sent. Temporary files are private and removed after each request. CV files and generated packages remain in private application storage and are never committed.

Fast discovery never runs inference. There is one cloud request at a time, a bounded timeout, and process-group cancellation. A provider failure reports Needs attention; it does not present a generic offline outline as a successful AI application. The original legacy workflow is preserved for compatibility, but the new Prepare application controls use the cloud package service.

## Connected Gmail

The Gmail connector is separate from text inference. It uses official app configuration to expose one Gmail action per invocation, with all other apps and Gmail actions disabled. Connector discovery uses Codex's code-mode host; shell and browser/computer tools remain disabled. Read-only invocations use `exec` actual MCP tool receipts. Write invocations use the official app-server JSON-RPC interface, ephemeral threads, and prompt-mode app approvals reviewed by this application. The app matches the connector ID, tool name and exact tool arguments in `mcpServer/elicitation/request` before returning accept. Another tool, modified recipients/body/attachments, an unapproved send or a second invocation is declined. The model's final prose never counts as a tool receipt.

- App-server protocol and approval flow: https://learn.chatgpt.com/docs/app-server
- Per-app and per-tool configuration: https://learn.chatgpt.com/docs/config-file/config-reference

Saved Gmail draft IDs survive application regeneration and restart. Sending rereads the current draft, validates its message ID and content against the preview, rechecks opportunity freshness/eligibility, and uses a ten-minute, one-use approval bound to the profile and CV hashes. External draft edits require a new review; the user should finish editing before approving. An uncertain create/send is not automatically repeated. Connecting or creating a draft does not send mail. Application monitoring through Gmail remains the separate metadata-only OAuth connector; the new connection does not scan unrelated mail automatically.
