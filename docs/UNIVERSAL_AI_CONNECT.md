# Dristik Connect — implementation status

## What this branch adds

- Tenant-scoped connection registration and listing.
- Capability discovery with explicit `available` versus `not_wired` statuses.
- SQLite-backed task and message records.
- Opaque artifact upload/download with size limits and SHA-256 metadata.
- Authenticated JSON-RPC endpoint at `/api/v1/mcp` and `/api/mcp` with `initialize`, `tools/list`, and `tools/call`.
- Authenticated routes mounted under the existing API prefixes.
- Initial regression tests for persistence, tenant isolation, and truthful connection status.

## Important current limits

This is a foundation, not yet the complete universal collaboration product. Connection registration does not validate remote endpoints or credentials. No provider-specific outbound adapter is enabled by this change. Messages are stored but not remotely delivered. The website-audit capability is deliberately marked `not_wired` until it is connected to the canonical Dristik audit orchestration service. Artifact storage is local disk by default and should be moved to tenant-aware object storage for multi-instance production deployments.

## API quick start

All endpoints require an authenticated Dristik session or bearer token.

- `GET /api/v1/connect/connections`
- `POST /api/v1/connect/connections`
- `GET /api/v1/connect/capabilities`
- `POST /api/v1/connect/tasks`
- `GET /api/v1/connect/tasks`
- `GET /api/v1/connect/tasks/{task_id}`
- `POST /api/v1/connect/tasks/{task_id}/messages`
- `POST /api/v1/connect/tasks/{task_id}/artifacts` (raw request body; set `X-Filename`)
- `GET /api/v1/connect/artifacts/{artifact_id}`
- MCP JSON-RPC: `POST /api/v1/mcp`

The MCP endpoint currently uses Dristik's existing authenticated session/bearer-token mechanism. It is not a full OAuth authorization-server implementation, and client compatibility must be tested against each target MCP client before claiming broad interoperability.

## Configuration

- `DRISTIK_CONNECT_DB_PATH`: SQLite database path; default `backend/data/universal_connect.sqlite3`.
- `DRISTIK_CONNECT_ARTIFACT_DIR`: artifact directory; default sibling `artifacts` directory.
- `DRISTIK_CONNECT_MAX_ARTIFACT_BYTES`: upload size limit; default 25 MiB.

## Next required engineering steps

1. Wire task claiming/execution to the canonical audit orchestrator and durable worker runtime.
2. Implement real MCP client transport with DNS-rebinding/SSRF protection, tool-schema validation, timeouts, cancellation, and permission scoping.
3. Implement provider adapters using the existing inference abstraction, plus credential encryption and secret redaction.
4. Move artifacts to production object storage and add malware scanning/retention controls.
5. Add durable outbound delivery, retries, idempotency keys, dead-letter handling, and webhook reconciliation.
6. Add frontend Connect Hub, collaboration timeline, capability diagnostics, and artifact browser.
7. Run the focused tests and the full backend test suite in CI and verify deployment behavior.


## Provider adapters and Connect UI (follow-up implementation)

The Connect workspace is available at the application route `#connect` and in the command palette for signed-in users. It provides provider registration, a live prompt test, and collaboration task visibility.

Supported provider adapters use fixed HTTPS API hosts:
- OpenAI-compatible: OpenAI, xAI/Grok, DeepSeek, OpenRouter.
- Anthropic Messages API.
- Google Gemini generateContent API.

Configure a Fernet key before storing provider credentials:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set the output as `DRISTIK_CONNECT_FERNET_KEY` in the backend deployment secret store. Do not commit the key or put it in frontend configuration. Losing the key makes stored credentials unreadable; rotating it requires an explicit credential re-encryption/rotation procedure.

Provider endpoints:
- `GET /api/v1/connect/providers`
- `POST /api/v1/connect/providers` with provider, label, model and api_key.
- `POST /api/v1/connect/providers/{provider_id}/invoke` with prompt, optional system and max_tokens.

A website audit task can now be submitted to the existing canonical audit route:
- `POST /api/v1/connect/tasks/{task_id}/execute-audit`
- The task inputs must contain `url` or `website_url`.
- The existing audit route still applies Dristik's normal entitlement and active-LLM configuration gates. The task records the resulting analysis ID.

The current provider implementation is a first production-oriented adapter slice, not complete certification: provider-specific API behavior and model names must be verified in CI with mocked HTTP responses and in deployment with each tenant's own keys. Remote MCP client execution, OAuth, retries/DLQ and object storage remain outstanding.
