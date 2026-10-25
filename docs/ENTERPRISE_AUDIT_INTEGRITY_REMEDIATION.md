# Enterprise Audit Integrity Remediation Plan

## Status and scope

This document is an engineering acceptance contract for the next Dristik hardening tranche. It is not evidence that the listed fixes have already shipped. Production code and test results must be verified independently before any capability is labelled complete.

## Non-negotiable evidence policy

1. Every customer-facing numeric metric must carry a value state: MEASURED, DERIVED, ESTIMATED, SIMULATION_ONLY, NOT_CONFIGURED, UNAVAILABLE, or DATA_UNAVAILABLE.
2. MEASURED requires a source record, collection timestamp, scope, and reproducible raw observation or provider response reference.
3. DERIVED requires the formula, inputs, units, and source references.
4. ESTIMATED and SIMULATION_ONLY must never be presented as measured live outcomes.
5. Missing, timed-out, unauthorized, stale, or malformed provider data must not be replaced by constants, canned examples, random values, or optimistic defaults.
6. Evidence references must resolve to stored evidence for the same audit and tenant. Invalid references reject or quarantine the claim; they are not silently removed while the claim remains reportable.
7. Fixtures and synthetic examples are allowed only in explicitly marked test/demo environments and must not enter production reports.
8. Confidence is not evidence. An LLM's confidence or fluent explanation cannot upgrade an unsupported claim.

## Required implementation work

### P0 — Establish truth at the boundary
- Inventory every customer-facing score, count, chart, benchmark, and competitor statement across API schemas, persistence, report assembly, and frontend fallbacks.
- Trace each field to a deterministic analyzer or a real connector response.
- Replace hard-coded fallbacks with typed nullable values plus explicit status and reason.
- Make production configuration fail closed when a demo/mock provider is selected.
- Add tenant/run ownership checks to evidence lookup and report assembly.
- Ensure cache keys include tenant, audit, provider, scope, and freshness dimensions.

### P0 — Correct pipeline dependency ordering
- Complete crawling, deterministic analysis, configured live integrations, competitor collection, and all finding-producing passes before final scoring.
- Deduplicate and validate findings before computing category scores.
- Build remediation plans only from the final validated finding set.
- Generate the final narrative, charts, manifest, and report from the same immutable final snapshot.
- Seal only after report validation; do not append findings or alter scores after sealing.
- If an upstream stage fails, preserve the failure state and explicit coverage gaps.

### P1 — Specialist agent contracts
Every agent must declare:
- stable ID and version;
- purpose and audit domain;
- required input fields and evidence types;
- permitted data sources and tools;
- output schema with typed status;
- deterministic checks versus model-generated interpretation;
- evidence requirements per claim;
- timeout, retry, budget, and unavailable behaviour;
- validation rules, duplicate suppression, and regression tests.

Agents must not infer that a missing signal is a negative signal. They must not claim to have checked a provider, engine, page, or competitor that was not actually queried.

### P1 — SEO audit coverage
- Crawl/indexability: status codes, redirects, canonicals, robots directives, sitemap inclusion, crawl depth, orphan pages, pagination, faceted URLs, and parameter handling.
- Rendering: compare raw HTML with rendered DOM when browser rendering is enabled; disclose pages where rendering was not verified.
- On-page: titles, descriptions, headings, internal links, image alternatives, duplicate templates, and content/page intent.
- Technical: mobile viewport, HTTPS, response timing, resource errors, structured-data syntax and eligibility checks, and observed security headers.
- Content: topic coverage, intent match, duplication/cannibalization candidates, freshness signals, authorship and first-party evidence.
- International/local/e-commerce: hreflang clusters, locale consistency, local NAP/profile evidence, product/variant/schema coverage, and faceted navigation.
- Search performance and backlinks: only from configured authoritative providers; otherwise show unavailable, never inferred counts.

Coverage must disclose attempted, fetched, rendered, analyzed, failed, skipped, and sampled URLs. Site-wide conclusions require site-wide evidence or explicit inference labels.

### P1 — GEO and AEO
- Separate on-page answer extractability/readiness from observed AI-engine visibility.
- Live citation/mention metrics require real queries against a configured provider or documented collection workflow, timestamps, engine/model, locale, query set, and retained source/citation URLs.
- A simulation must be labelled SIMULATION_ONLY and must not populate live visibility scores.
- Analyze entity clarity, direct-answer quality, source attribution, original information, passage structure, and supported structured data from collected page evidence.
- Report query coverage and engine coverage; do not generalize a small sample into universal visibility.

### P1 — CRO
- Use observed DOM and, when configured, browser/viewport evidence to inspect CTA presence, forms, navigation, mobile usability, friction, trust signals, and accessibility indicators.
- Distinguish heuristic usability findings from measured conversion outcomes.
- Conversion rate, revenue, funnel loss, CAC, and uplift require connected analytics/CRM or a controlled experiment. Never fabricate an uplift estimate as a measured outcome.
- Each recommendation must identify the observed issue, affected URL/component, evidence, hypothesis, proposed change, validation method, and expected direction of impact (not an invented numeric promise).

### P1 — Competitor analysis
- Discover and confirm competitors explicitly; retain the source and confidence for each competitor identity.
- Compare equivalent page types, market, language, device, intent, crawl scope, and collection window.
- Record parity and coverage for every comparison. Missing competitor observations must be UNKNOWN, not zero.
- Compare technical SEO, content/topic coverage, entity/schema, local/international signals, visible conversion paths, and live search/AI visibility only where equivalent evidence exists.
- Distinguish observed gaps from hypotheses. Do not label a competitor's inferred backlink authority, traffic, AI citations, or conversion performance as measured.
- Generate prioritized opportunities with target URL, competitor evidence, Dristik evidence, business rationale, effort, dependencies, validation criteria, and source links.

### P2 — Improvement plans and verification
- Every finding includes: what was observed, where, evidence, why it matters, confidence/scope, recommended fix, implementation owner/type, priority rationale, dependencies, acceptance test, and verification state.
- Prioritize by severity, affected page/business importance, evidence confidence, effort, and dependency—not a fabricated ROI.
- Separate proposed, approved, applied, and VERIFIED_LIVE states. Applying a patch is not proof it worked.
- Re-crawl or re-query the relevant source after remediation and compare before/after evidence.
- Recalculate scores and roadmaps from the verified final snapshot only.

## Required automated acceptance tests

1. Unconfigured provider -> NOT_CONFIGURED with no numeric metric.
2. Timeout, 401/403, malformed response, and stale response -> explicit unavailable state; no canned fallback.
3. Fake evidence ID, cross-audit evidence ID, and cross-tenant evidence ID -> claim rejected and report seal blocked or claim quarantined.
4. SIMULATION_ONLY AI result -> cannot populate live visibility fields.
5. Missing analytics/backlink data -> no fabricated zeros, traffic, authority, conversion, or ROI values.
6. A finding added in a late pipeline stage appears in the final score and remediation plan.
7. No finding or score mutation is permitted after manifest sealing.
8. Competitor with partial crawl -> coverage disclosed and no unsupported parity conclusion.
9. Duplicate findings from agents/rules are deduplicated without deleting distinct evidence.
10. Re-running the same evidence snapshot and policy version produces reproducible deterministic scores.
11. Frontend renders null/unavailable states honestly and never replaces them with demo values.
12. Production configuration rejects mock providers and seeded demo fixtures.

## Release gate

Do not call Dristik enterprise-ready until the repository inventory, implementation, and CI results demonstrate these acceptance criteria. Documentation, registered agent count, passing unit tests alone, and a successful demo are not proof of live audit accuracy.
