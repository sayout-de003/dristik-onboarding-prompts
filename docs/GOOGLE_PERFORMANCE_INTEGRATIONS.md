# Google search and performance integrations

These adapters use Google's real APIs. They do not manufacture data when credentials are absent or a target has no data.

## Environment variables

- GOOGLE_CRUX_API_KEY: API key with the Chrome UX Report API enabled. GOOGLE_API_KEY is accepted as a fallback.
- GOOGLE_PAGESPEED_API_KEY: API key with PageSpeed Insights API enabled. GOOGLE_API_KEY is accepted as a fallback; PSI can sometimes work without a key but will be quota-limited.
- GOOGLE_CSE_API_KEY: API key for the Custom Search JSON API. GOOGLE_API_KEY is accepted as a fallback.
- GOOGLE_CSE_CX: Programmable Search Engine ID. A CSE result set is not equivalent to a universal, location/device-specific Google SERP ranking report.

Configure keys in the deployment secret manager/environment, never in source control or MCP tool arguments. Google API key restrictions should limit each key to the required APIs and server-side usage where supported.

## Authenticated REST endpoints

All routes are mounted under both /api/v1 and /api and require the application's authenticated user:

- GET /integrations/performance/status
- POST /integrations/performance/crux with JSON body { origin, form_factor }; optionally include a full url for URL-level data.
- POST /integrations/performance/pagespeed with JSON body { url, strategy, categories }
- GET /integrations/performance/google-search?q=example

## MCP tools

Authenticated Universal Connect clients with the connector.read grant can call:

- dristik_crux_query
- dristik_pagespeed_query
- dristik_google_search

The adapters return VERIFIED_LIVE, DATA_UNAVAILABLE, NOT_CONFIGURED, INVALID_TARGET, INVALID_REQUEST, or PROVIDER_ERROR rather than filling missing measurements with zeroes.

## Evidence interpretation

- CrUX is field data aggregated from eligible Chrome users. A missing record is not a zero score.
- PageSpeed Insights/Lighthouse output is lab data; it must not be presented as real-user field data.
- Programmable Search returns results for the configured search engine. It must not be described as universal Google SERP rankings or a precise rank-tracking API.
- Search Console and GA4 remain separate property-authorized integrations. Their metrics require valid property permissions and must not be inferred from these public endpoints.
