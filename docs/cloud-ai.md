# Cloud AI without local inference

OpportunityOS uses the official Codex CLI `exec` structured-output mode and the user's existing ChatGPT sign-in. This is a local personal automation, not a proxy for public or untrusted users. It does not copy tokens or call undocumented ChatGPT endpoints.

- Official authentication: https://learn.chatgpt.com/docs/auth
- Official non-interactive and JSON-schema output: https://learn.chatgpt.com/docs/non-interactive-mode
- Reviewed computer-use reference: https://github.com/openai/openai-cua-sample-app (requires an API key and API credits; not installed as a hidden paid dependency).

On this Mac the installed CLI is already signed in. On another Mac, install Codex, run `codex login` with ChatGPT, and use Check ChatGPT connection in Settings. API-key sessions are refused. Plan limits still apply; no unlimited use is promised. CLI binary discovery supports PATH and the installed macOS ChatGPT bundle. This integration requires CLI support for the flags used; an incompatible CLI reports a connection/request error rather than falling back to paid API calls.

Requests use an empty temporary working directory, read-only sandbox, disabled shell/apps/browser/computer tools, disabled hooks, ignored user config, ephemeral sessions, and a JSON output schema. The OpenAI API-key environment variables are removed from the subprocess. Only public posts or, for application preparation, the selected post plus share-approved verified profile facts and master CV text are sent. Temporary files are private and removed after each request. CV files and generated packages remain in private application storage and are never committed.

Fast discovery never runs inference. There is one cloud request at a time, a bounded timeout, and process-group cancellation. A provider failure reports Needs attention; it does not present a generic offline outline as a successful AI application. The original legacy workflow is preserved for compatibility, but the new Prepare application controls use the cloud package service.
