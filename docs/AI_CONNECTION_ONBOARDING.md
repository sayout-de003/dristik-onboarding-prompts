# AI connection onboarding (copy/paste workflow)

The API adds a secure onboarding flow at both `/api/v1/connect/ai-onboarding` and `/api/connect/ai-onboarding`.

## 1. Create a connection kit

Authenticated organization owner/admin:

```http
POST /api/v1/connect/ai-onboarding/kit
Content-Type: application/json
```

```json
{
  "name": "Claude growth assistant",
  "provider": "claude",
  "grant_profile": "audit_operator",
  "expires_in_days": 30,
  "goal": "Discover Dristik tools and verify messaging."
}
```

The response includes a Dristik-issued one-time API key, connection identity, actual MCP endpoint, authorized tool summary, and provider-specific copy/paste prompt. `prompt` matches the requested provider. `prompts` contains one prompt for every supported provider so a client can switch the copy target without issuing another key. Show/store the key only in a trusted secret field; do not paste it into a public AI chat or embed it in source code. Keys are hashed in the database and cannot be retrieved after creation. Choose the least-privileged grant profile needed.

The Connect page uses this kit when the operator clicks **Generate credentials**. It shows the prompt for the selected AI client and a copy button. The API key stays in the credential fields and is left out of the prompt.

To show the prompt again for a connection that already exists, call `POST /api/v1/connect/ai-onboarding/prompt` with `connection_id`, `provider`, and an optional `goal`. The response has the same prompt fields and does not return or rotate the API key. The Connect page loads it from **Onboarding prompt** on a saved connection.

Supported prompt targets: `chatgpt`, `claude`, `gemini`, `grok`, `deepseek`, `kimi`, `openrouter`, `custom`. This is a label for the user's selected AI surface, not a claim that every surface can act as an MCP client. The generated prompt explicitly requires the AI to state its actual limitations.

## 2. Paste the AI response back

Submit structured JSON to `POST /api/v1/connect/ai-onboarding/response`:

```json
{
  "connection_id": "dai_...",
  "provider": "claude",
  "summary": "Proposed MCP client setup",
  "files": [{"path": "config/mcp.json", "content": "{...}"}],
  "setup_commands": ["python -m pytest"],
  "dependencies": ["mcp"],
  "environment_variable_names": ["DRISTIK_MCP_TOKEN"],
  "test_plan": ["Initialize MCP", "Call tools/list", "Call dristik_ping"],
  "limitations": ["Requires a local MCP-capable host"]
}
```

Response files are path-validated, size-limited, scanned for obvious secret material, hashed, and persisted tenant-scoped with status `awaiting_review`. Inspect submissions using `GET /api/v1/connect/ai-onboarding/submissions` and `GET /api/v1/connect/ai-onboarding/submissions/{submission_id}`.

## Safety and current scope

- This tranche **does not execute returned code or shell commands**. It deliberately stages proposals for review. No production terminal execution is implemented by these endpoints.
- Do not treat a successful provider text response as proof of MCP connectivity. A real MCP-capable client must authenticate with the issued key and connection email, run `initialize` and `tools/list`, then call an authorized tool such as `dristik_ping`.
- Inbound callback/webhook support is not inferred. Add it only for a real provider/runtime that supports it, with signature verification and replay protection.
- The current secret scan is a guardrail, not a complete secret detector. Keep secrets out of submitted files regardless.
- To complete safe implementation automation, add a dedicated disposable runner with no host mounts or Docker socket, egress allowlisting, CPU/memory/time limits, pinned dependencies, static analysis, test capture, human approval, and rollback. Never run untrusted returned code inside the FastAPI process or directly on the production host.
