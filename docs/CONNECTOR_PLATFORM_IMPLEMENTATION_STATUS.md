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
- Added provider-aware OAuth token refresh where a configured provider supports refresh tokens (and Meta long-lived-token exchange), followed by live API verification.
- Added durable idempotency records and explicit confirmation for supported Telegram messages, Slack messages, X posts, WhatsApp approved-template messages, and Instagram image publishing. Unknown outcomes are persisted as unknown to prevent silent duplicate retries.
- Added live resource-read endpoints and UI previews for HubSpot contacts/companies/deals, Salesforce accounts/leads/opportunities/campaigns, Stripe customers/subscriptions/payment intents, and Sanity documents.
- Added tenant-scoped adapter lookup, organization-scoped audit events, and fail-closed behavior for telemetry construction when an organization ID is not supplied.
- Added signed inbound webhook verification for Slack (timestamped HMAC), Meta/WhatsApp (SHA-256 HMAC and verification challenge), and Telegram (per-connection secret token), with replay/deduplication records and payload-hash-only storage.
- Removed fake default scopes and fake last-sync timestamps from newly created integrations. Persistence failures are no longer silently treated as success.
- Added a full directory UI for the 26 named integration targets plus legacy connector aliases, token entry for API-based providers, OAuth entry points where configured, and test/reconnect/forget/delete actions.

## Explicitly not complete yet

- A provider-specific live handshake is not proof of every operation in the target registry. The registry's `verified_operations` remains empty until sandbox/real API contract tests pass.
- Full CRUD, publishing, analytics, content mutation, post-deployment verification, and rollback are not implemented for every provider. The new generic API adapter refuses unmapped writes rather than pretending to support them. Only the explicit Telegram, Slack, X, WhatsApp template, and Instagram image actions are currently mapped.
- Framer and Wix need dedicated supported-capability implementations; they are intentionally blocked from a false-success path.
- X and TikTok OAuth/PKCE flows, complete account selection, webhook registration/cleanup and approval-event processing, durable background jobs/retries/dead-letter handling, and provider-specific remote token revocation remain to be completed. Signature verification is currently implemented only for inbound Slack, WhatsApp/Meta, and Telegram webhook endpoints.
- End-to-end tests against provider sandboxes and tenant-isolation tests with real authenticated identities are still required. The API keys/OAuth app secrets and app approvals must be configured by the deployment owner.
- Revenue attribution still needs a persisted cross-system journey model to link analytics events, CRM deals, and Stripe revenue without double counting.
- The existing WordPress, Webflow, Shopify, GitHub, GSC, GA4, CrUX, DataForSEO, CRM, AI-search and Generic Web adapters remain subject to the requested full implementation audit. They are not automatically certified by this registry.

## Required deployment configuration for these paths

- Set a unique `AUTH_SECRET` of at least 32 characters and a canonical HTTPS `OAUTH_REDIRECT_URI`; configure `GOOGLE_OAUTH_REDIRECT_URI` for Google flows.
- Set provider app credentials for each OAuth provider you enable (for example `LINKEDIN_CLIENT_ID/SECRET`, `SLACK_CLIENT_ID/SECRET`, `INSTAGRAM_CLIENT_ID/SECRET`, and `WHATSAPP_BUSINESS_CLIENT_ID/SECRET`).
- Set `SLACK_SIGNING_SECRET` for Slack inbound event signatures.
- Set `META_APP_SECRET` and `META_WEBHOOK_VERIFY_TOKEN` for Meta/WhatsApp webhook verification.
- Telegram webhook ingress requires a per-connection `webhook_secret` that exactly matches the secret configured with Telegram's `setWebhook`. Dristik validates incoming updates but does not register the webhook URL automatically yet.
- Configure provider scopes and app-review permissions in each vendor console. Dristik's successful handshake only proves the endpoint used by that check accepted the credential.

## Acceptance gate

A provider may be labelled fully verified only when a test proves: real authentication, live read behavior, every claimed write behavior, post-write independent verification, credential redaction/encryption, tenant and permission isolation, rate-limit/error handling, webhook security and event-processing behavior where applicable, disconnect/revocation behavior, and successful/failing contract tests. Until then, show the precise state (`DISCONNECTED`, `DEGRADED`, `AUTH_REQUIRED`, `UNAVAILABLE`, or `CONNECTED`) and the operation-level verification status.

## Audit correctness and deep-crawl tranche (in progress)

- Added `app.report_quality`: strict evidence/finding contracts, snapshot SHA-256 validation, affected-URL-to-evidence matching, verified-scope checks, duplicate detection, canonical severity validation, required remediation/verification text, and composite-score reconciliation against declared weights.
- Added `app.crawl_orchestration`: SQLite-persisted deep-crawl job and URL state, normalized URL deduplication, same-origin checks, page/depth budgets, tenant-scoped job access, interruption recovery primitives, cancellation flags, retries/attempt counters, and truthful discovered/eligible/crawled/failed/excluded/remaining coverage counters.
- Added authenticated `POST /api/v1/deep-crawls`, `GET /api/v1/deep-crawls/{job_id}`, and `POST /api/v1/deep-crawls/{job_id}/cancel` routes. The worker discovers same-origin URLs from internal links and XML sitemaps, respects fetched robots rules, does bounded HTTP retries, blocks out-of-scope redirects, and records HTTP-only crawl coverage. The existing five-page Quick Scan entry point was not changed.
- Added contract tests for report validation, score reconciliation, URL normalization, same-origin boundaries, crawl resume/accounting, partial failures and tenant scoping; CI now runs this test file.

### Known limitations that remain open

- These report-quality contracts are available as a reusable gate but are not yet wired into every existing report assembly/PDF export path. The next change must adapt the real finding/evidence objects and enforce the gate before finalization without dropping legacy fields.
- The initial deep-crawl worker runs as a FastAPI background task. URL/job state persists in SQLite, but there is not yet a durable external worker queue or automatic startup recovery of interrupted jobs; do not advertise process-crash auto-resume until that wiring exists.
- The initial worker is HTTP-only. Browser-rendered DOM coverage, robust sitemap-index recursion, DNS/IP-level SSRF defense at connection time, concurrency scheduling, incremental recrawling, and richer per-stage traces are not complete.
- The deep-crawl API has not yet received end-to-end runtime testing in a deployed environment. CI must pass before these endpoints are considered release-ready.
- Connector provider completeness and sandbox validation remain separate outstanding work; this tranche does not mark any provider operation as verified.
