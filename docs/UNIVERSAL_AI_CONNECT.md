# Dristik Connect — implementation status

## What this branch adds

- Tenant-scoped connection registration and listing.
- Capability discovery with explicit `available` versus `not_wired` statuses.
- Dristik-issued external AI credentials with one-time API keys, hashed-key storage, grant profiles, expiry, validation, rotation and revocation.
- MCP authentication using Authorization: Bearer drk_live_... plus X-Dristik-Connection-Email.
- MCP tools for capability discovery, template entry-point discovery, registered-agent discovery, canonical audit start/status and persisted report retrieval.
- SQLite-backed task and message records.
- Opaque artifact upload/download with size limits and SHA-256 metadata.
- Authenticated JSON-RPC endpoint at `/api/v1/mcp` and `/api/mcp` with `initialize`, `tools/list`, and `tools/call`.
- Authenticated routes mounted under the existing API prefixes.
- Initial regression tests for persistence, tenant isolation, and truthful connection status.

## Important current limits

This is a foundation, not yet the complete universal collaboration product. Connection registration does not validate remote endpoints or credentials. No provider-specific outbound adapter is enabled by this change. Messages are stored but not remotely delivered. The website-audit entry point now calls the existing canonical Dristik audit route. The currently exposed template catalog is intentionally limited to that implemented entry point; it does not claim every future report template is registered. Artifact storage is local disk by default and should be moved to tenant-aware object storage for multi-instance production deployments.

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

The MCP endpoint accepts either the existing Dristik authenticated session/bearer token or a Dristik-issued AI connection key paired with X-Dristik-Connection-Email. This is a scoped API-key flow, not a full OAuth authorization-server implementation. Client compatibility must be tested against each target MCP client before claiming broad interoperability.

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


## Dristik-issued AI connection credentials

The Connect Hub can issue a dedicated connection identity and a one-time API key for an external AI/MCP client. The key authenticates that client to Dristik; it is distinct from a provider API key stored for outbound model inference.

### Endpoints

- POST /api/v1/connect/ai-connections — create a connection. Request fields: name, grant_profile (full_access, workflow_admin, audit_operator or read_only), and expires_in_days. The response includes the connection identity and API key once.
- GET /api/v1/connect/ai-connections — list tenant-owned connections without returning keys.
- POST /api/v1/connect/ai-connections/validate — validate a connection identity/key pair.
- POST /api/v1/connect/ai-connections/{id}/rotate — rotate a key; the old key becomes invalid.
- POST /api/v1/connect/ai-connections/{id}/revoke — revoke a connection immediately.
- MCP JSON-RPC: POST /api/v1/mcp.

The create/list/rotate/revoke endpoints require the existing org:manage permission. The MCP connection key is stored as a SHA-256 hash, not plaintext. Keys are shown only at creation and rotation. Every MCP request re-checks connection status, expiry, tenant and grant scope.

### Grant profiles

- read_only: discover permitted capabilities/templates/agents and read authorized audit/report data.
- audit_operator: read results and start audits or create collaboration tasks.
- workflow_admin: audit operations plus registered agent/workflow operations exposed by the gateway.
- full_access: all scopes recognized by Dristik Connect, within the issuing user's organization and platform entitlements.

A profile does not make an operation available if its backend implementation is absent. MCP tool discovery is filtered by the connection grant; each call must still enforce authorization server-side.

### MCP client headers

Configure the MCP client to send:

- Authorization: Bearer <Dristik API key>
- X-Dristik-Connection-Email: <Dristik connection identity>

Set DRISTIK_MCP_PUBLIC_URL to the absolute HTTPS MCP endpoint URL visible to the external client. Set DRISTIK_CONNECT_IDENTITY_DOMAIN to a domain label controlled by the deployment; the generated connection email is an integration identity, not a mailbox.

### Current implementation boundary

Implemented in this slice: credential issuance/listing/validation/rotation/revocation, grant profiles, MCP key authentication, grant-filtered tool discovery, canonical website-audit start/status, actual registered-agent discovery, and persisted report retrieval.

Selected-provider routing is now applied to compatible calls made through the shared ModelRouter during the canonical audit pipeline, using a task-local override and tenant-scoped provider lookup. It does not automatically reroute direct provider integrations that bypass ModelRouter, and end-to-end coverage across every agent/sub-agent still needs verification. Also not yet completed: discovery/execution of every product workflow and template, a general outbound MCP client, durable cancellation/retry/recovery for all connector jobs, redirect-aware DNS-pinned SSRF protection in the crawler/transport, and a real-client end-to-end certification run. Do not describe these as production-verified until implemented and tested.
