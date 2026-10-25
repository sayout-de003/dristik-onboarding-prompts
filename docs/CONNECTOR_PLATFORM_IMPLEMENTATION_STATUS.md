# Dristik connector platform — implementation status

This document records the current integration-platform tranche. Provider names in the directory are not proof that a provider is connected or fully implemented.

## Shared runtime foundation in this tranche

- A 26-provider registry declares target operations, adapter registration, registered-but-unverified operations, and empty verified-operation lists until contract tests exist.
- New API adapters perform real, provider-specific authentication probes for OpenAI model API, Perplexity model API, Anthropic Models API, Gemini Models API, HubSpot CRM read API, Salesforce REST API version discovery, Stripe Account API, LinkedIn OIDC profile, X user profile, TikTok user info, Instagram Graph API, WhatsApp phone-number metadata, Telegram getMe, Slack auth.test, and Sanity dataset query.
- Framer and Wix are deliberately reported as adapter-required until their supported API and app-permission paths are implemented. They cannot be marked connected by the generic connector form.
- API resource discovery returns bounded summaries and a response SHA-256 / observation timestamp for the provider API response. The connector audit log stores non-secret provenance metadata, not raw tokens or response bodies.
- OAuth callback handling for configured providers now performs a real API handshake before setting a connection to connected. OAuth state requires a strong configured secret and has a 15-minute expiry, nonce, and signature.
- Added OAuth definitions for LinkedIn, Slack, Instagram Professional, and WhatsApp Business; these flows require provider app credentials and the scopes/approval granted by those platforms.
- Connector credential updates are encrypted at rest; reconnect and local credential removal are exposed. The UI calls out that remote token revocation is not attempted unless a provider-specific revocation flow is implemented.
- Added tenant-scoped adapter lookup, organization-scoped audit events, and fail-closed behavior for telemetry construction when an organization ID is not supplied.
- Removed fake default scopes and fake last-sync timestamps from newly created integrations. Persistence failures are no longer silently treated as success.
- Added a full directory UI for the 26 named integration targets plus legacy connector aliases, token entry for API-based providers, OAuth entry points where configured, and test/reconnect/forget/delete actions.

## Explicitly not complete yet

- A provider-specific live handshake is not proof of every operation in the target registry. The registry's `verified_operations` remains empty until sandbox/real API contract tests pass.
- Full CRUD, publishing, analytics, content mutation, post-deployment verification, and rollback are not implemented for every provider. The new generic API adapter refuses writes rather than pretending to support them.
- Framer and Wix need dedicated supported-capability implementations; they are intentionally blocked from a false-success path.
- X and TikTok OAuth/PKCE flows, complete account selection, webhook registration/signature verification, durable background jobs/retries/dead-letter handling, and provider-specific remote token revocation remain to be completed.
- End-to-end tests against provider sandboxes and tenant-isolation tests with real authenticated identities are still required. The API keys/OAuth app secrets and app approvals must be configured by the deployment owner.
- Revenue attribution still needs a persisted cross-system journey model to link analytics events, CRM deals, and Stripe revenue without double counting.
- The existing WordPress, Webflow, Shopify, GitHub, GSC, GA4, CrUX, DataForSEO, CRM, AI-search and Generic Web adapters remain subject to the requested full implementation audit. They are not automatically certified by this registry.

## Acceptance gate

A provider may be labelled fully verified only when a test proves: real authentication, live read behavior, every claimed write behavior, post-write independent verification, credential redaction/encryption, tenant and permission isolation, rate-limit/error handling, webhook security where applicable, disconnect/revocation behavior, and successful/failing contract tests. Until then, show the precise state (`DISCONNECTED`, `DEGRADED`, `AUTH_REQUIRED`, `UNAVAILABLE`, or `CONNECTED`) and the operation-level verification status.
