# Dristik Output Publication Standard

**Status:** Design contract for report and presentation templates  
**Applies to:** Master PDF; SEO, GEO, CRO and AEO PDF/PPT; competitor analysis PPT; remediation pack; improvement plan PDF/PPT.

## Design principles

1. **One design system, distinct report families.** Shared typography, spacing, evidence labels, footers, page numbering and table rules. Each deliverable has its own content hierarchy; no duplicated generic report with only its title changed.
2. **Editorial, not dashboard-dense.** White paper pages, ink/navy text, restrained teal accent, neutral dividers, and semantic severity colors only where needed. No decorative rainbow palettes, excessive gradients, giant KPI tiles or dense tiny text.
3. **Evidence before interpretation.** Every material finding separates what was observed, evidence/source and scope, what it means in plain English, why it matters, recommended action, acceptance test, and verification state.
4. **Measured is not inferred.** Label observations as PAGE_VERIFIED, SAMPLE_VERIFIED, SITE_INFERRED, EXTERNAL_VERIFIED, DERIVED, ESTIMATED, SIMULATION_ONLY, NOT_CONFIGURED, UNAVAILABLE or DATA_UNAVAILABLE as applicable. Missing integrations never render as zero, a pass, or an invented benchmark.
5. **Explain every visual.** Every chart/table has a title, units, date/window, coverage note and a plain-English takeaway. Never rely on color alone.
6. **Pagination is a correctness requirement.** Generate final page numbers from the rendered PDF, resolve TOC entries in a second pass, add PDF bookmarks, and QA the actual output. Never print estimated page numbers as final.
7. **Executive and practitioner views complement each other.** Start with decisions and business implications; provide evidence, affected URLs, technical detail, owners and verification in later sections or appendices.
8. **No unsupported assurance language.** Do not claim independent assurance, certification or measured ROI unless the relevant process/data exists and is evidenced.

## Shared publication shell

### PDF / audit book
- Cover: client/domain, deliverable title, reporting period/run timestamp, scope, crawl coverage, data-connection status, report reference and confidentiality label. Show a score only if the canonical score is available and validated.
- Executive brief: 3–5 evidence-backed takeaways, business consequence, highest-priority decision and explicit limitations.
- Scope and method: URLs sampled/crawled, locale/device where applicable, integrations used, integrations unavailable, run date, sampling limits and evidence-state legend.
- Contents: hierarchical chapters with final physical page numbers; bookmarks must match the TOC.
- Chapter body: consistent hierarchy, readable tables, page-safe charts, URL-level detail and plain-English explanations.
- Finding card: ID/title; severity and rationale; affected scope/URL; observation; evidence and timestamp; confidence/scope; meaning; business/search/visitor impact; recommended fix; owner/effort/dependencies where known; acceptance criteria; verification state.
- Closing: prioritized next actions, measurement plan, evidence/data limitations, appendices and reproducibility reference.
- Footer: shortened domain, deliverable family, report/run reference, page number and classification.

### PPT / decision deck
- 16:9 widescreen; one key message per slide; large readable typography; short evidence labels; chart/table source and time window visible.
- Standard sequence: title and scope → executive decision → baseline/coverage → key findings → implications → priority actions → implementation sequence → success/verification measures → limitations/appendix.
- Do not paste PDF pages into slides. Re-compose the story for presentation and keep detailed URL evidence in appendix/linked report.
- Avoid fabricated uplift, market-share estimates, competitor claims, dates, cost estimates and ROI. Mark unknown values as unavailable.

## Deliverable-specific templates

### 1. Master PDF — Complete Website Intelligence Audit
1. Cover and publication metadata
2. Executive decision brief
3. Scope, coverage, data connections and methodology
4. Cross-pillar overview: SEO, GEO, AEO, CRO and competitor context; show only measured/validated values
5. Canonical priority register and issue concentration
6. Technical and crawl/indexability foundation
7. SEO: content, intent, on-page, internal links, performance, structured data, local/international/e-commerce as applicable
8. GEO: source extractability, entity consistency, answer readiness and separately measured live visibility
9. AEO: question coverage, answer passages, entities/facts, schema and live benchmark evidence where measured
10. CRO: journey, usability, trust, forms and heuristic-vs-analytics distinction
11. Competitor comparison and coverage parity
12. Remediation roadmap and dependencies
13. Verification and measurement plan
14. Evidence ledger, glossary, limitations and appendices

### 2. SEO PDF and PPT
- PDF chapters: crawl coverage; robots/indexability; canonical/redirect/status; rendering; site architecture/internal links; metadata/headings; content quality/search intent; image/media; structured data; performance/Core Web Vitals when measured; mobile; local SEO; international/hreflang; ecommerce/facets; migrations; GSC/SERP/backlink evidence only when connected; page-level findings; prioritized remediation.
- PPT: search opportunity and coverage → technical blockers → content/intent gaps → architecture/template patterns → prioritized fixes → measurement plan.
- Clearly distinguish crawl observations from Google indexing/ranking data.

### 3. GEO PDF and PPT
- PDF chapters: entity/brand facts; source and passage extractability; content grounding and citation-ready structure; topical/source coverage; freshness and trust signals; robots/access constraints relevant to AI crawlers; engine-specific live visibility, citations and competitor substitution only when actually measured; reproducible query/engine/locale/timestamp ledger.
- PPT: what can be retrieved → what is supported by evidence → observed live engine outcomes → gaps → source/content changes → repeatable benchmark plan.
- Simulated model evaluation must be labelled SIMULATION_ONLY and never represented as live visibility.

### 4. CRO PDF and PPT
- PDF chapters: audience/task assumptions; landing-page message match; navigation and information scent; mobile usability; form/checkout friction; trust/proof; accessibility observations; experiment hypotheses; analytics funnel only when connected; experiment design and validation.
- PPT: conversion journey → evidenced friction → affected segment/page → hypotheses → experiment backlog → primary/guardrail metrics.
- Heuristic scores are not conversion rates. Revenue/uplift claims require analytics, CRM or experiment evidence.

### 5. AEO PDF and PPT
- PDF chapters: target questions and intent; direct-answer coverage; answer passage clarity; entity/fact registry; factual consistency; structured data validity; question-to-page mapping; answer-source evidence; live answer-engine benchmark with query/engine/model/locale/date and citations when measured; remediation and retest.
- PPT: question coverage → answer quality → fact/entity reliability → live benchmark findings → page-level actions → retest protocol.
- Never fabricate query volume, citations, mention rate, recommendation share or answer-engine visibility.

### 6. Competitor Analysis PPT
1. Decision and comparison question
2. Competitor set, selection rationale and date
3. Comparison scope: markets, languages, devices, page types, intent and sample sizes
4. Coverage and data-source parity matrix
5. SEO technical/content/architecture comparison
6. GEO/AEO live results with engine/query evidence, where available
7. CRO experience patterns, separating observed UX from measured outcomes
8. Target wins, competitor wins and ties only where comparable observations exist
9. Evidence-backed strategic opportunities and counter-moves
10. Unknowns, confidence and next validation steps
- Do not compare a deep crawl with a homepage-only sample without prominently flagging non-equivalence. Missing evidence is UNKNOWN, not a competitor loss or zero.

### 7. Remediation Pack
- Summary of critical/high-priority fixes and blockers
- One ticket per deduplicated finding with stable ID, evidence reference, affected URL/template, severity rationale, root cause, exact recommended change, implementation notes, dependencies, owner role, effort only if estimated transparently, acceptance test and rollback/side-effect notes where relevant
- Group repeat issues by template/pattern without hiding affected URLs
- Include code/config suggestions only when supported by observed site state
- Lifecycle: OPEN → IN_PROGRESS → IMPLEMENTED_UNVERIFIED → VERIFIED_LIVE or FAILED_VERIFICATION
- “Fixed is not Verified”: a patch proposal or developer assertion never becomes VERIFIED_LIVE without a fresh check and recorded before/after evidence.

### 8. Improvement Plan PDF and PPT
- PDF: baseline and limitations; outcome objectives; workstreams; 0–30 / 31–60 / 61–90 day sequencing (dates may be calendarized only when run date and capacity are known); dependencies; roles; implementation acceptance criteria; measurement design; risks; review cadence; validation gates.
- PPT: target outcomes → prioritized workstreams → phased plan → owners/dependencies → leading/lagging measures → decision requests.
- No invented budgets, resource capacity, ROI or guaranteed ranking/revenue gains. Label estimates and assumptions.

## Quality gates before publishing

- All displayed scores reconcile to the canonical report score and source categories.
- Every displayed number has a source, unit, date/window and coverage statement.
- Every material finding has evidence or is explicitly labelled inference/estimate.
- Unavailable integrations are visible as unavailable; no fallback demo data in production exports.
- Competitor comparisons declare coverage and comparability.
- TOC, page numbers, bookmarks, charts, tables and cross-references are checked against the final PDF.
- PPT slides pass overflow/readability checks and include sources/limitations.
- Exports are deterministic for the same sealed report version; regenerated templates do not silently mutate the sealed audit.
- A failed QA gate prevents the export from being labelled publication-ready.
