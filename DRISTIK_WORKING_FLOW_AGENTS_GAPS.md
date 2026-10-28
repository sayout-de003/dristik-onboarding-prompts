# Dristik — Working Flow, Agents, Drawbacks, and Improvement Plan

**Verified against the live tree on 3 October 2026.**
**Source of truth:** `backend/app/orchestration/orchestrator.py`, `backend/app/agents/runtime/registry.py`, `backend/app/orchestration/agent_pool.py`, `backend/app/scoring/engine.py`, `backend/app/scoring/weights.py`, `backend/app/external_authority/`, `frontend/src/lib/pillarSynthesis.ts`.

Older maps in `AI_ARCHITECTURE_AND_AGENTS.md`, `README.md`, and `DRISTIK_PRODUCT_REPORT.md` still describe a 6-wave pool and a seal path that never measured AI visibility. Those statements are out of date. This file is the current working map.

---

## 1. What Dristik is

Dristik is a FastAPI + React website-intelligence auditor. A run crawls a public site, stores hashed observations, runs deterministic analyzers and a 105-specialist agent pool across 12 domains and 7 pipeline workflow sections, then seals an executive report with findings, scores, a 7/30/90 roadmap, and a developer patch pack.

The product rule is evidence. An LLM may interpret stored observations. It may not invent Core Web Vitals, backlinks, Search Console clicks, live ChatGPT citations, or a universal authority score. Unmeasured pillars stay unmeasured. Trust is omitted and the other category weights are renormalized when no external-authority evidence is connected. AI visibility stays blank unless a live engine measurement exists.

The crawl is a **representative sample**, not a full-site crawl. The crawler fills role slots first: homepage, primary commercial page, high-intent page (pricing or contact), a second commercial page, then a proof page (about). Default `MAX_CRAWL_PAGES` is **10**. Named tiers are quick 10, standard 50, deep and enterprise 500. Findings are scoped `PAGE_VERIFIED`, `SAMPLE_VERIFIED`, or `SITE_INFERRED`. A five- or ten-page run is a product limit. It is not an external-authority coverage gap. Backlinks, search performance, analytics, and brand mentions come only from connected providers.

---

## 2. Architecture planes

| Plane | Where it lives | What it owns |
|---|---|---|
| Ingestion | `backend/app/crawl/` | SSRF guard, httpx fetch, Playwright / Firecrawl when a page is thin, robots, sitemap, role-slot sampling |
| Deterministic evidence | `backend/app/crawl/analyzers/`, `backend/app/analyzers/`, `backend/app/evidence/` | DOM, meta, schema, links, TTFB, headers, `ev_NNN` tokens, `snap_<sha256>` bodies |
| External telemetry | `backend/app/evidence/enrichment.py` | DNS, TLS, security headers, CrUX when a key exists. Writes `ext_NNN`. Fail open. |
| External authority | `backend/app/external_authority/` | GSC, GA4, Bing, Ahrefs, Semrush, Majestic, DataForSEO, SerpAPI, Google Business Profile, citations, brand mentions. Separate SQLite. No universal score. |
| Cognitive blackboard | `backend/app/cognition/` | Shared claims, site facts, findings, contradictions for one run |
| Specialist workforce | `backend/app/orchestration/runtime/` | 105 registered agents in 12 domains, 7 pipeline workflow sections |
| Page copy fleet | `backend/app/agents/page/intelligence.py` | Per-URL SEO report plus 5 copywriting task cards. Not in the pool. |
| Scoring | `backend/app/scoring/engine.py`, `weights.py`, `calibration.py` | Eight categories. Guesses do not deduct. Floor 20. |
| Report seal | `backend/app/audit/manifest.py`, `backend/app/reports/validation_gate.py` | `manifest.json` pins report UUID, evidence, snapshots, and agent-call hashes |
| Product shell | `frontend/src/` | Hash routes, audit tabs, pillar cards blended from engine scores |

Side clocks that do not have to finish inside one sealed audit: keyword SERP tracking (`intelligence/serp_tracker.py`), GEO pipeline snapshots (`geo_aeo_pipeline.db`), radar DOM diffs, 30/60/90 outcome rechecks, competitor bakeoff.

---

## 3. Full working flow

### 3.1 What the user does

1. Sign in. Starting an audit requires `mission:create`. Viewers cannot start one.
2. Submit a public URL, crawl depth, optional site type and notes, optional competitor URLs, optional country and language. Country and language are stored. They are not a live geo-rank input.
3. `POST /api/v1/analyses` queues `AnalysisOrchestrator.execute_analysis_pipeline`.
4. The UI follows `GET /analyses/{id}/stream` (SSE): queued, ingesting, deterministic analysis, planning, specialist execution, adversarial verification, executive synthesis, scoring, completed or failed.
5. A finished run is an `ExecutiveReport`. The user can open the report, evidence ledger, page inspector, patch ZIP, roadmap, external-authority tab, competitors tab, and cost ledger.
6. Optional follow-ons: connect a provider, track keywords, run a competitor bakeoff, subscribe to radar, pay through Razorpay.

App views (`frontend/src/routes/navigation.ts`): home (audits), pricing, login, signup, forgot, reset, account, contact, team, system. Audit tabs inside home: overview, SEO, GEO, AEO, CRO, competitors, external authority, page inspector, evidence ledger, cost ledger, patch pack, roadmap, verification, report, plans.

### 3.2 Pipeline inside one audit

This is the order in `AnalysisOrchestrator.execute_analysis_pipeline`. The user can pause between stages. A checkpoint can reuse an already crawled page set.

| Step | Name | What happens |
|---|---|---|
| 1 | Mission | `MissionDirector.create_mission` with `audit_type=standard_growth`. Capability lists are selected. The workforce runs 105 specialist agents across 12 domains and 7 pipeline workflow sections. |
| 2 | Crawl | SSRF check, then `CrawlerService.crawl_site_and_analyze`. httpx first. Playwright or Firecrawl when the HTML is thin and rendering is enabled. Robots and sitemap are fetched. Role slots are filled before the rest of the budget. |
| 3 | Evidence graph | Site, page, and H1 nodes. Every observation is copied in with a SHA-256 and a selector. |
| 4 | Checkpoint 1 | Pages and evidence items are written. A failure here is logged and the run continues. |
| 5 | Wave-0 site facts | Business-name candidates, CTAs, schemas, `sameAs`, FAQs, pricing-present, HTTPS, nav. No model call. |
| 6 | External evidence plane | `ExternalEvidenceEnricher.enrich_domain` writes `ext_NNN` for DNS, TLS, headers, and CrUX when configured. A connector error does not fail the audit. |
| 7 | Tier-1 capabilities | `$0` pre-pass: discovery, semantic structure, indexability, links, performance, security, assets, mobile, schema syntax, Open Graph, readability, cannibalization. |
| 8 | Entity resolve | `UniversalEntityResolver` sets a canonical name and industry from crawled pages. |
| 9 | Business understanding | `BusinessUnderstandingOrchestrator` compares the declared site type with the detected one and can emit an identity contradiction. |
| 10 | 105-agent workforce & 7 workflow sections | `AgentPool.execute_all` and Modular DAG. Kahn waves. Parallel inside a wave. `allow_fallback=False`. A missing model key yields `unavailable`, not a canned claim. |
| 11 | Checkpoint 3 | Claims are persisted. |
| 12 | Page intelligence | `PageIntelligenceAgent` writes a per-URL SEO report and runs the five copywriting cards. |
| 13 | Integrity and rubric | Dangling evidence refs are purged. Each claim becomes CERTAIN, LIKELY, or GUESSING. A GUESSING claim that is also CRITICAL is sent back through `verification.adversarial.v3` before it can enter the executive narrative. |
| 14 | Gaps, causes, hypotheses | Evidence-gap detector, causal bottleneck pass, hypothesis evaluation, opportunity detector. |
| 15 | Commercial simulation | `worker_simulator` runs six buyer questions. Output is simulation unless a live tracker already measured them. |
| 16 | Narrative | Synthesizer runs only when `story_summary` is still empty. `strategy.executive.v3` may already have written one inside the pool. |
| 17 | Post-DAG analyzers | Canonicals, HTTP status, headings, media, click depth and orphans, meta rollup, forms, schema rich results, WCAG screening, local SEO, international SEO, topical authority, indexation classifier, host and redirect probe, security headers, competitor SEO parity on crawled pages. |
| 18 | Findings and first score | Decision engine plus deterministic rules plus entity-graph findings. Deduped. **`ScoringEngine.calculate_scores` runs here, before live visibility and before external authority.** |
| 19 | Confidence | Coverage and model confidence are attached to that first score object. |
| 20 | Remediation | Remediation planner, patch engine, 7/30/90 roadmap, top-10 actions. These use the findings from step 18, so later findings are missing from the roadmap. |
| 21 | Twin and timeline | In-memory digital twin and audit timeline for the domain. |
| 22 | Narrative assembly | `NarrativeGenerator` over the same finding set. |
| 23 | Live AI visibility | `run_audit_visibility` when engines are configured. On success with `status=MEASURED`, citation rate becomes the visibility score. Otherwise the latest GEO pipeline snapshot is used when it measured at least one engine. Otherwise visibility stays unmeasured. |
| 24 | GEO readiness | On-page extractability. Visibility is attached only from step 23. A later LLM enrichment can add citation copy. It must not invent a visibility number from HTML. |
| 25 | Honest scores | `calculate_honest_scores` recomputes categories with the live citation score. It hardcodes `external_authority_connected=False`. Human, Google, and AI-readiness views are blends. AI visibility stays null when nothing was measured. |
| 26 | Copy, WhatsApp, graph, seal | Character-safe title and meta, WhatsApp one-pager, evidence graph resync, manifest seal, outcome jobs at 30/60/90 days. |
| 27 | Visual, regression, UX, lifecycle | Chart payload, regression against the in-memory twin, visual UX inspection, lifecycle revenue. Lifecycle is called with GSC, GA4, and CRM all disconnected. |
| 28 | More rollups | Per-engine on-page GEO matrix, evidence taxonomy. |
| 29 | External authority attachment | Reads stored snapshots. Does not call providers (`EXTERNAL_SYNC_ON_AUDIT` defaults off). Findings are appended **after** scores, roadmap, and the seal inputs above. A failure leaves a placeholder and does not change the crawl. |
| 30 | Competitive layer | Competitive evidence graph and competitive report from the business profile, crawled pages, and any observatory records. |
| 31 | Second causal pass | Root-cause chains again, now with competitive graph and observatory records. The first causal pass already ran at step 14. |
| 32 | Report and validation gate | `ExecutiveReport` is built. `ValidationGate` can fail the run. Claims ledger is attached. Run status becomes completed and is persisted. |

SSE progress percentages are approximate. Several late stages still emit the `specialist_execution` or `scoring` label.

### 3.3 What a sealed report contains

- Business profile and resolved entity
- Eight category scores plus honest Human / Google / AI-readiness views
- `ai_visibility_score` only when step 23 measured it
- Findings with evidence tokens, four axes (technical severity, business impact, confidence, blocking), and scope labels
- Exploratory hypotheses kept out of executive severity counts
- Per-page SEO and copy reports
- Code patches and a ZIP (`schema.jsonld`, `metadata.html`, `faq.html`, `llms.txt`, `robots.txt`, install notes)
- 7/30/90 roadmap and top 10 actions
- GEO readiness, commercial Q&A, AI search matrix, per-engine on-page matrix
- External-authority payload (coverage states, vendor-named metrics, no combined authority score)
- Crawl summary, contradictions, evidence graph, visual charts, telemetry, manifest id
- WCAG screening, local SEO, international SEO, topical authority, indexation rollup
- Competitive report and causal diagnostic chains

### 3.4 Work that is real but not inside every sealed audit

| Product | Trigger | Store |
|---|---|---|
| External authority sync | User connects a provider and a job runs. Plans: FREE (GSC, GA4, Bing, Business Profile), STANDARD (plus citations and mentions), ADVANCED (Ahrefs, Semrush, Majestic, DataForSEO, SerpAPI). | `external_authority.db` |
| Keyword tracking | `POST /intelligence/keywords` and a scheduler. Daily SERP history, competitor ranks, keyword gap. | Keyword tables on the authority database |
| Live citation tracker and GEO pipeline | On demand, or the audit monitor when keys exist | `geo_aeo_pipeline.db` and the visibility scorecard |
| Competitor bakeoff and discovery | On demand. Peers must be crawled. No invented category giants. | Report fields and competitor registry |
| Radar | DOM changelog on a saved prompt set. Refuses a fake baseline. | Monitoring store |
| Outcomes | Scheduled on seal. Rechecks the original finding ids at 30/60/90 days. Correlation is not causation. | Outcome SQLite |
| CMS patch apply | WordPress, GitHub, Shopify, Webflow, generic. Human in the loop. | Connector state |
| Payments | Razorpay and GST invoices. Plan catalog exists. | Payments module |

---

## 4. Agent flow

### 4.1 One specialist

`SpecialistAgent.run` in `backend/app/agents/runtime/specialist.py`:

1. Pull up to 60 evidence items for the agent. If the retriever returns nothing, use the first 60 items in the store.
2. Adversarial agent falsifies claims that have no evidence. Contradiction agent routes contested claims. These two do not hard-stop when a dependency result is missing (`_deps_unmet` returns false for the whole `VERIFICATION` domain).
3. Any other agent whose dependencies all failed to record a result returns `unavailable` and writes no claims.
4. Deterministic agents (`allowed_models` is only `deterministic`) audit the crawl with rules. Hybrid agents run rules and then the model, and merge. Everyone else calls the model.
5. The prompt is the specialist system text, the task card, forbidden operations, and prior blackboard context.
6. Model tier follows the registry. On Groq, routine agents are forced to the fast model and the token budget is capped at 1,000. Elsewhere, `judge_model` wins over `reasoning_model` over `fast_slm`.
7. `generate_structured(..., allow_fallback=False)`. No key, invalid JSON, or an explicit unavailable status produces no claims.
8. A claim is kept only when it has a statement and at least one evidence id that exists in the slice or in external evidence. `not_in_evidence` items are dropped. At most eight claims per agent.
9. The claim is registered, bound to ground truth, and rubric-scored. The result is stored on `blackboard.blackboard_state["agent_results"]`.

Low-confidence and GUESSING claims do not reduce category scores. Only Verified or High confidence, or the legacy Certain and Likely labels, deduct. The same root cause is charged in full once and at half after that. Category score is `clamp(100 − deductions, 20, 100)`.

Blocking status is separate from severity. Only sitewide `noindex`, `Disallow: /`, a fetch failure, or HTTP 5xx can be blocking, and only for indexation.

### 4.2 Nine Kahn waves

Computed by `topological_waves(SPECIALIST_AGENTS_V3)` on 3 October 2026. Counts: **21 + 4 + 1 + 2 + 3 + 1 + 1 + 1 + 1 = 35**.

```
Wave 1 (21, parallel)
  business.discovery
  seo.crawl, seo.indexability, seo.html, seo.internal_links,
  seo.performance, seo.security, seo.assets
  schema.validation, entity.graph
  content.depth, content.eeat, content.quality,
  content.topic_coverage, content.cannibalization
  geo.extractability, geo.information_gain, geo.structure
  ux.experience, cro.conversion, trust.authority

Wave 2 (4)
  business.icp, business.intent, business.commercial
  entity.knowledge_graph

Wave 3 (1)
  business.semantic_strategist

Wave 4 (2)
  geo.citation_readiness
  ai_search.discoverability

Wave 5 (3)
  ai_search.chatgpt, ai_search.perplexity, ai_search.google

Wave 6 (1)
  ai_search.cross_engine

Wave 7 (1)
  verification.adversarial

Wave 8 (1)
  verification.contradiction

Wave 9 (1)
  strategy.executive
```

Dependency edges that create this order:

- `business.discovery` → ICP, intent, commercial → semantic strategist
- `entity.graph` → knowledge graph
- strategist + entity graph + content quality → citation readiness
- strategist → AI discoverability → ChatGPT, Perplexity, Google AI → cross-engine
- cross-engine + citation readiness + ICP, commercial, E-E-A-T, content quality, trust, performance → adversarial
- adversarial → contradiction → executive

SEO, schema validation, content depth, GEO structure, and UX agents have no dependencies. They all sit in wave 1 and cannot see the business strategist’s output.

### 4.3 Workers that sit around the pool

| Worker | When | Job |
|---|---|---|
| `MissionDirector` | Before crawl | Budget, objective, capability lists. Lists do not shrink the pool. |
| `TeamOrchestrator` tier-1 | Before the pool | Deterministic capability wave. Overlaps the SEO agents. |
| `BusinessUnderstandingOrchestrator` | Before the pool | Second business-identity pass. Overlaps the five business agents. |
| `PageIntelligenceAgent` | After the pool | Per-URL report and five copywriters. |
| Integrity gate + rubric | After page intelligence | Drops dangling refs. Holds GUESSING+CRITICAL. |
| Causal engine | Twice | Once before simulation, once after the competitive graph. |
| Hypothesis engine and opportunity detector | Mid-pipeline | Pre-registered hypotheses, then evidence evaluation. |
| AI search simulator worker | After the pool | Six commercial questions. Separate from the five AI-search agents. |
| Synthesizer worker | If narrative empty | C-suite story from verified claims. |
| `ScoringEngine` | Twice | Category scores before visibility. Honest views after visibility, still without external authority. |
| `ValidationGate` | Last | Can fail the run. |
| Legacy classes in `agents/legacy/` | Not the pool | Old single-file agents kept for imports and tests. |

---

## 5. Agent list

Mode is how the registry is allowed to run: **Rules** means `deterministic` only, **Hybrid** means rules plus a model, **Model** means a model call with no rules path.

### 5.1 Business intelligence

| Id | Wave | Mode | What it does | Drawback |
|---|---|---|---|---|
| `business.discovery.v3` | 1 | Model | Company name, products, services, industry, customer, model, value proposition from homepage, nav, hero, footer. Must not guess pricing. | Runs before ICP and commercial agents, and in parallel with SEO. A second identity pass already ran in `BusinessUnderstandingOrchestrator`. |
| `business.icp.v3` | 2 | Model | Buyer type, company size, roles, pain points. Asks for case studies and external ground truth. | ICP from a 10-page sample is an interpretation. External ground truth is often absent, so the claim stays single-source. |
| `business.intent.v3` | 2 | Model | Labels informational, commercial, transactional, navigational, and comparison intent from headings, metas, and URLs. | No keyword corpus and no Search Console queries unless a provider was synced earlier. Intent is inferred from copy. |
| `business.commercial.v3` | 2 | Model | Pricing model, packages, CTA friction, trials, commercial trust. Forbidden from inventing prices. | If the pricing URL was not in the role sample, the agent reports absence. Absence on a sample is not “the site has no pricing.” |
| `business.semantic_strategist.v3` | 3 | Model | Merges the four business agents and flags identity, positioning, audience, product, or commercial conflicts. | It is one model judging other models. Conflicts can be phrasing differences, not business facts. |

### 5.2 Technical SEO

| Id | Wave | Mode | What it does | Drawback |
|---|---|---|---|---|
| `seo.crawl.v3` | 1 | Rules | Robots, sitemap, status codes, redirects, depth, orphans from the crawl manifest. | Sees only fetched URLs plus a short sitemap sample. It cannot see log-file crawl budget or the uncrawled site. |
| `seo.indexability.v3` | 1 | Hybrid | `noindex`, canonicals, `X-Robots-Tag`, parameter duplicates. | No Google index coverage export unless GSC URL Inspection is explicitly enabled. “Indexable in HTML” is not “indexed.” |
| `seo.html.v3` | 1 | Rules | Titles, metas, H1–H6, landmarks. | Per crawled page. Sitewide missing-title counts like an agency PDF need a deep crawl. |
| `seo.internal_links.v3` | 1 | Hybrid | Link graph, orphans, depth, anchor concentration. | The graph is the sample, not the site. An “orphan” may be linked from a page that was not fetched. |
| `seo.performance.v3` | 1 | Rules | TTFB, payload, render-blocking hints. Forbidden from inventing LCP, INP, or CLS. | Lab TTFB is not field Core Web Vitals. CrUX is a separate enricher and is `NOT_CONFIGURED` without a key. |
| `seo.security.v3` | 1 | Rules | HTTPS, TLS, HSTS, CSP, `X-Frame-Options`, mixed content. | Header baseline. It is not a penetration test, and a missing HSTS header is not an SEO, conversion, or citation failure. |
| `seo.assets.v3` | 1 | Hybrid | Alt text, dimensions, modern formats, lazy-load, video metadata on fetched pages. | Does not download every image byte or run a Lighthouse filmstrip unless that path is separately enabled. |

### 5.3 Structured data and entity

| Id | Wave | Mode | What it does | Drawback |
|---|---|---|---|---|
| `schema.validation.v3` | 1 | Hybrid | JSON-LD, microdata, and RDFa syntax and required properties. | Syntax validity is not rich-result eligibility. Google’s rich-results test and the post-DAG schema auditor can disagree with this agent. |
| `entity.graph.v3` | 1 | Model | Organization, person, product, service, and place nodes and relations. | Entity resolution from one sample can merge the wrong brand when the name is generic. |
| `entity.knowledge_graph.v3` | 2 | Model | `sameAs`, author identity, disambiguation. Forbidden from claiming Knowledge Graph inclusion without external proof. | `sameAs` links are not checked live against Wikidata unless a SERP provider returned a knowledge-graph element. |

### 5.4 Content

| Id | Wave | Mode | What it does | Drawback |
|---|---|---|---|---|
| `content.depth.v3` | 1 | Model | Breadth, depth, missing subtopics, fluff versus substance. | No SERP competitor corpus. “Thin” is the model’s reading of the sample, not a MarketMuse-style coverage score. |
| `content.eeat.v3` | 1 | Model | Observable authors, credentials, citations, editorial policy, first-hand experience. | E-E-A-T is not a Google score. Off-page reputation is unmeasured until mentions or reviews are connected. |
| `content.quality.v3` | 1 | Model | Clarity, originality, utility, repetition. | Originality without a web-scale duplicate index is a local judgment. |
| `content.topic_coverage.v3` | 1 | Model | Topic tree and gaps from headings and body. | Runs in parallel with depth and quality, so the three content agents can file the same gap three times. Dedup happens later, at half weight. |
| `content.cannibalization.v3` | 1 | Model | Overlapping titles and intents inside the sample. | Cannibalization that matters is query-level and needs rank and impression data. Title overlap on ten pages is a hint. |

### 5.5 GEO (on-page extractability)

These agents score whether a page is easy to quote. They do not measure whether an answer engine quoted it.

| Id | Wave | Mode | What it does | Drawback |
|---|---|---|---|---|
| `geo.extractability.v3` | 1 | Model | Definitions, lists, tables, short answers. | Overlaps the deterministic GEO readiness scorer that runs again after the pool. |
| `geo.information_gain.v3` | 1 | Model | Original data, methods, benchmarks. High risk level in the registry. | “Original” without an external corpus is a claim about tone. Easy to overstate. |
| `geo.citation_readiness.v3` | 4 | Model | Maps claim to evidence to source. Depends on the strategist, the entity graph, and content quality. | Readiness is still on-page. A high score here must not be shown as citation share. |
| `geo.structure.v3` | 1 | Model | TL;DR, answer-first openings, FAQ blocks, entity-dense snippets. | FAQ copy that is easy to extract can still be absent from Perplexity or AI Overviews. |

### 5.6 AI search

| Id | Wave | Mode | What it does | Drawback |
|---|---|---|---|---|
| `ai_search.discoverability.v3` | 4 | Model | Builds a synthetic prompt matrix: best-of, alternatives, versus. | Prompts are generated, not taken from GSC or a keyword set, unless that data was already on the blackboard. |
| `ai_search.chatgpt.v3` | 5 | Model | Scenario for ChatGPT. Must label unverified runs `SIMULATION_ONLY`. Forbidden from fabricating citations. | This is not a ChatGPT API call with browsing. The live monitor is a different code path (`intelligence/geo/audit_monitor.py` and `geo/adapters/`). |
| `ai_search.perplexity.v3` | 5 | Model | Scenario for Perplexity source eligibility. Same fabrication ban. | A simulated “would cite” line is not a citation. |
| `ai_search.google.v3` | 5 | Model | AI Overview and featured-snippet readiness. Must separate observed from inferred. | Does not query Google AI Overviews or AI Mode unless the live monitor did. |
| `ai_search.cross_engine.v3` | 6 | Model | Compares the three simulations and may mention Gemini and Claude. | Consensus of simulations is not cross-engine share of voice. Gemini and Claude have no dedicated pool agent. Capability ids `29_gemini_scenario` and `30_claude_scenario` are mapped onto the Google agent and this cross-engine agent. |

Live engines that exist as adapters, outside this pool: OpenAI search, Perplexity, Claude, Gemini, Groq. The product standard also names Google AI Overviews / AI Mode and Bing / Copilot, with availability detection so a run does not query every engine every time. Query classes for a real measurement are brand, category, problem, service, comparison, and buyer. Metrics that count are mention rate, citation rate, citation accuracy, competitor visibility, and entity accuracy.

### 5.7 UX, conversion, trust

| Id | Wave | Mode | What it does | Drawback |
|---|---|---|---|---|
| `ux.experience.v3` | 1 | Hybrid | Nav, readability, mobile friction, information architecture from DOM. | No session replay, no heatmaps, no real-device lab. Mobile is markup and viewport, plus a later visual UX pass. |
| `cro.conversion.v3` | 1 | Model | CTA verbs, placement, form fields, offer clarity. | Heuristic unless GA4 is connected. The sealed lifecycle block is currently called with analytics disconnected, so this audit does not become a measured funnel by itself. |
| `trust.authority.v3` | 1 | Model | Testimonials, logos, badges, contact, privacy, terms. | On-page trust signals. Referring domains and reviews stay in the external-authority pillar and are `NOT_CONNECTED` until a provider snapshot exists. |

### 5.8 Verification and strategy

| Id | Wave | Mode | What it does | Drawback |
|---|---|---|---|---|
| `verification.adversarial.v3` | 7 | Model | Tries to falsify claims. Checks that evidence exists and was not over-extended. Re-run after the pool for held GUESSING+CRITICAL items. | It does not hard-fail when a dependency agent was unavailable. A judge model can also be wrong, and there is no second human review on the default path. |
| `verification.contradiction.v3` | 8 | Model | Cross-page and cross-agent conflicts, and a root-cause note. Forbidden from crowning a winner between DOM and external evidence. | The causal engine runs its own root-cause pass later. Two explanations of the same conflict can both ship. |
| `strategy.executive.v3` | 9 | Model | Narrative, priority, and 7/30/90 from verified findings. | The orchestrator may overwrite or ignore this narrative and build another one in `NarrativeGenerator`. Roadmap items are built again from findings after this agent. |

### 5.9 Copywriting fleet (not in the pool)

`PageIntelligenceAgent` loads these task cards once per crawled URL.

| Id | What it does | Drawback |
|---|---|---|
| `copywriting.seo.v3` | Titles at 50–60 characters and metas at 140–160, aligned to the inferred intent. | No live SERP, no current ranking title, no query impression data. The rewrite can target the wrong query. |
| `copywriting.geo.v3` | 40–60 word definitions and FAQ Q&A aimed at answer engines. | Optimizes for extractability. It cannot know which sentence an engine will cite. |
| `copywriting.cro.v3` | Hook, objection line, and CTA microcopy. | No experiment result and no click-through on the proposed CTA. |
| `copywriting.clarity.v3` | Cuts buzzwords, targets grade 7–9, names the ICP. | Grade level is a proxy. Some categories (legal, clinical, developer docs) should not be forced to grade 8. |
| `copywriting.section.v3` | Rebuilds the page as hero, problem, solution, proof, FAQ, and close, with a full rewrite. | Highest token cost in the fleet. A modular rewrite of a page the crawler only partly rendered will invent structure. |

### 5.10 Capability ids

`CAPABILITY_AGENT_MAP` has 35 ids (`01_discovery` through `35_contradiction_resolution`). They are labels for routing and for the tier-1 pre-pass. They are not a second workforce. Two mappings are misleading: `29_gemini_scenario` points at `ai_search.google.v3`, and `30_claude_scenario` points at `ai_search.cross_engine.v3`.

---

## 6. Drawbacks by section and subsection

### 6.1 Ingestion and crawl

The crawler is careful (SSRF, role slots, content-addressed bodies, optional rendering) and small on purpose. A technical-SEO buyer who expects Screaming Frog, Sitebulb, Lumar, or Botify will not get sitewide issue counts from the default run.

| Subsection | Drawback |
|---|---|
| Role sampling | Homepage, commercial, high-intent, second commercial, proof. Blog templates, faceted URLs, paginated archives, and parameter variants are easy to miss. |
| Sitemap | A short sitemap sample. Child sitemaps are not exhausted. An `http://` sitemap on an `https://` site is stored, and a dedicated rule for that mismatch is thin. |
| Rendering | Playwright and Firecrawl run when a page looks thin. There is no raw-versus-rendered diff as a first-class finding the way Lumar and Botify ship it. |
| Logs | No server-log or CDN-log ingestion. Crawl budget, Googlebot status mix, and wasted crawl are invisible. |
| Host variants | A host and redirect probe runs late. It is not a full matrix of www, apex, http, and https with chain lists on every hop. |
| Concurrency | Crawl concurrency defaults to 3 and timeout to 15 seconds. Deep tier (500) will be slow and still far below an enterprise crawler. |
| Scope labels | The taxonomy can mark `PAGE_VERIFIED`. Agents in wave 1 still speak as if the sample were the site unless the later gate rewrites them. |

### 6.2 Deterministic analyzers

The crawl analyzers (HTML, meta, DOM, schema, links, performance, security, visible text, dynamic CMS) and the post-DAG auditors (canonical, HTTP status, headings, media, link depth, meta rollup, forms, schema rich results, local, international, topical, indexation, WCAG) are the strongest part of the product. They are also run more than once.

| Subsection | Drawback |
|---|---|
| Double and triple evaluation | The same title, canonical, or H1 can be judged in the crawler, in tier-1 capabilities, in an SEO agent, and again in a post-DAG analyzer. Dedup is by root cause after the fact. |
| Meta and heading rollups | Buckets exist (missing, short, long, duplicate) for the fetched set. They are not a sitewide pie chart. Publishing them next to a “site audit” label over-claims. |
| Forms | Labels, field count, and thank-you hints from HTML. No submitted-form test, no spam check, no CRM delivery check. |
| International | Hreflang is analyzed on the sample. A multi-market site needs the alternate URLs in the crawl. `country` and `language` on the request are not that crawl. |
| Local | NAP and local schema on the sample. Business Profile impressions are a different pillar and stay disconnected by default. |
| Topical authority | Computed from the sample’s internal links and headings. It is not a corpus authority metric. |
| WCAG | `DeepWcagAuditor` is automated screening. It is not an audit certification and it is not a full human accessibility audit. |
| Security headers | HSTS, CSP, frame options, content type. No TLS configuration scan, no cookie flags beyond what headers show, no dependency CVE scan. |
| Performance | TTFB and payload. Field LCP, INP, and CLS stay empty without CrUX. |

### 6.3 Evidence, integrity, and the blackboard

Hashed snapshots, `ev_NNN` / `ext_NNN`, a rubric, and a validation gate are the real difference from a checklist PDF. The machinery is heavier than the decisions it protects.

| Subsection | Drawback |
|---|---|
| Token vocabulary | `ev_`, `ext_`, snapshots, graph nodes, claim ledger, and the external-authority database are five stores for proof. A maintainer can write into the wrong one. |
| Integrity gate | Drops dangling refs. It does not check that a claim’s prose matches the cited snippet. |
| Rubric | CERTAIN / LIKELY / GUESSING is sound. Low confidence does not deduct, which is correct, and it also means a stack of real-but-uncertain issues leaves the score near 100. |
| Score floor | `clamp(..., 20, 100)` stops a collapse and also hides how bad a thin sample can be. |
| Blackboard size | Agents see 60 evidence rows. A 500-page crawl silently truncates what the model is allowed to read. |
| Persistence | Crawl, claims, findings, and run rows are checkpointed. Digital twins and timelines used for regression live on the orchestrator process. A restart weakens regression history. |
| Older connector package | `backend/app/connectors/` is not the external-authority engine. Those older connectors can still return fixture numbers for older tests. Two honesty regimes in one repo is a standing risk. |

### 6.4 Specialist pool

| Subsection | Drawback |
|---|---|
| Cost and latency | Up to 105 model calls (across 12 domains), then copywriting per URL, then a simulator, then a synthesizer. Groq caps routine agents at 1,000 tokens, which makes the reasoning agents shallow exactly when the cheap provider is selected. |
| Wave 1 blindness | Twenty-one agents cannot read the business strategist. SEO and content findings are not conditioned on ICP. |
| Quick audits | `MissionDirector` can shrink capability lists for `audit_type=quick`. `AgentPool.execute_all` still runs every specialist. |
| Duplicate business layer | Entity resolver, business-understanding orchestrator, and five business agents all name the company. |
| Duplicate AI layer | Five AI-search agents simulate engines. Then `worker_simulator` simulates six buyer questions. Then `run_audit_visibility` may query live engines. Three answers to one question. |
| Verification softness | Verification agents do not refuse to run when a dependency returned `unavailable`. The executive narrative can be confident about a hole. |
| Legacy tree | `agents/legacy/` still exists beside the registry. Two implementations of the business agent will drift. |
| Capability names | Gemini and Claude capability ids do not point at Gemini and Claude agents. |

### 6.5 Scoring and the UI

Live category shares before intent multipliers, from `weights.py`: Technical 15, On-page 10, Content 15, GEO 15, AI Search 15, Schema 10, UX 10, Trust 10. Intent multipliers are renormalized to 1. Deductions use diminishing steps (Critical 25/12/8/5, High 15/9/6/4, Medium 8/5/3/2, Low 3/2/1/1) times business-impact and confidence scales.

`scoring_rubric.py` still publishes five pillars at 25 / 25 / 20 / 20 / 10. The engine does not score those five pillars. The frontend (`pillarSynthesis.ts`) blends engine categories again, for example SEO as technical 0.45 + on-page 0.35 + content 0.20. The radar and the rubric modal can show a third set of numbers. A buyer can see three SEO scores for one run.

| Subsection | Drawback |
|---|---|
| Score timing | Category scores and the roadmap are built before external-authority findings are appended. Those findings show up in the list and do not move the number. |
| Honest-score gate | `calculate_honest_scores` always passes `external_authority_connected=False`, so Trust stays unmeasured on that pass even when a snapshot was about to be attached. |
| AI Search gate | The category stays unmeasured until `live_citation_score` is set. The first `calculate_scores` call does not receive that score. The honest pass does. `report.scores` and `report.honest_scores` can disagree. |
| Display blends | Pillar cards are not the engine weights. The rubric modal still teaches 25/25/20/20/10. |
| Single overall | Honest overall is human 0.35 + Google 0.35 + AI readiness 0.30. That is a display blend. It is easy to mistake for a certified score. |
| Causal language | Calibration forbids writing that missing HSTS freezes SEO. Narrative templates and agent recommendations can still imply a ranking or revenue outcome the model did not establish. |

### 6.6 GEO and live visibility

| Subsection | Drawback |
|---|---|
| Two products in one report | GEO readiness is on-page. AI visibility is live. Per-engine GEO matrix is another on-page view. The pillar card blends them. |
| Measurement is optional | No API keys means a blank visibility score. That is correct. The simulated matrix still renders beside it, and a reader can treat the simulation as the measurement. |
| Engine coverage | Adapters exist for several vendors. AI Overviews and Bing Copilot are named in the product standard and are not dedicated pool agents. The report must say which engines were actually called. |
| Repeats | The product standard wants repeated queries, not one answer. The sealed path uses whatever `run_audit_visibility` returned. A single successful response is a weak share-of-voice number. |
| Competitor share of voice | Observatory records can feed the competitive graph. There is no scheduled share-of-voice history as the default screen. |
| Citation accuracy | The metric is specified. The sealed path mostly has a citation rate. Accuracy against the page text is not a first-class column in the scorecard the orchestrator stores. |

### 6.7 External authority and keywords

This pillar follows the evidence rule. Vendor metrics keep the vendor name. Missing providers are `NOT_CONNECTED` or `NOT_APPLICABLE`. Crawl depth does not limit it. Snapshots are read at seal time. A dead provider cannot fail the crawl.

| Subsection | Drawback |
|---|---|
| Empty by default | `EXTERNAL_SYNC_ON_AUDIT` is off. A new account’s audit shows an empty authority section until someone connects a provider and a job finishes. Competitors open on a backlink index they already own. |
| No owned index | Ahrefs, Semrush, and Majestic numbers appear only when those APIs are connected and the plan is ADVANCED. Dristik does not have a referring-domain graph of its own. |
| Row caps | GSC rows default to a cap (250). Hitting it marks `PARTIALLY_MEASURED`. That is honest and easy to under-read in the UI. |
| URL Inspection | Off unless `GSC_URL_INSPECTION_ENABLED`. Index coverage remains a sample of analytics rows, not a coverage report. |
| Citations | NAP is compared only to directories the user listed. The product does not ship a directory index. |
| Mentions | Linked versus unlinked is stored. Sentiment stays off unless a provider that returns sentiment is enabled. |
| Keyword tracker | Daily SERP and keyword gap exist as endpoints. They are not an input to `business.intent` or the copywriters on the sealed path. Rank tracking depends on DataForSEO or SerpAPI credits. |
| Encryption setup | Customer tokens require `EXTERNAL_INTEGRATION_ENCRYPTION_KEY`. A missing key blocks the pillar. That is safe, and it means local and demo environments look broken rather than empty. |
| Score join | Attaching the report after scoring means a measured Domain Rating never changes category math. That matches “no universal authority score.” The findings list and the score header then tell two stories. |

### 6.8 Competitive intelligence

| Subsection | Drawback |
|---|---|
| Declared rivals | The competitive report uses competitor domains on the profile. Discovery of peers exists, and it is not the default sealed input. |
| Homepage parity | The SEO parity matrix compares crawled pages. It is not a keyword-gap overlap table unless the keyword engine was run. |
| Bakeoff | Six questions against one crawled rival. Useful as a writing exercise. It is not a SERP landscape. |
| Semantic gap | Embedding coverage exists (`e5-small`, 384 dimensions, local by default). A small local model will miss nuances a content-optimization suite gets from SERP embeddings. |

### 6.9 Remediation, monitoring, and outcomes

| Subsection | Drawback |
|---|---|
| Patch pack | JSON-LD, meta, FAQ, `llms.txt`, and robots are concrete. They are templates from the sample, not a diff against the customer’s repository unless the GitHub connector is used. |
| Closed loop | CMS apply is human-approved. There is no automatic deploy-recrawl-confirm on the default path. Outcome jobs recheck later and do not ship the patch. |
| Roadmap timing | Built before external-authority findings and before the second causal pass. The top 10 can omit the highest-business-impact item found later. |
| Radar | DOM diffs and saved prompts. It does not consume citation snapshots as its primary series. |
| Regression | Compared with the in-memory twin. A new process starts a new history. |
| Outcomes | 30/60/90 rechecks are scheduled. External metric deltas arrive only when those snapshots exist. |
| Lifecycle block | Hardcoded disconnected. The report section can imply a funnel model with no GSC, GA4, or CRM rows. |

### 6.10 Frontend, tenancy, and operations

| Subsection | Drawback |
|---|---|
| Hash routing | Works for a single-page audit shell. Deep links and document titles are weaker than a path router for an agency handing a URL to a client. |
| Pillar math in the client | `pillarSynthesis.ts` recomputes scores. A future engine change will not match the cards until this file is updated. |
| Entitlements | Plans and vouchers exist. Crawl depth and ADVANCED providers need a server-side check on every start and every sync. A catalog that does not gate `POST /analyses` is a billing gap. |
| Tenancy | Org, workspace, project, and RBAC roles exist. External-authority calls fall back to `org_default` when the run has no org id, which can mix snapshots. |
| Email | Password reset and radar alerts are not a finished mailer in every environment. |
| Deploy | `Dockerfile` and `docker-compose.yml` are in the tree. Production still depends on SQLite files (`dristik.db`, `dristik_audits.db`, `external_authority.db`, `geo_aeo_pipeline.db`) rather than one migrated Postgres. |
| Complexity | Mission graph, unused DAG helpers, legacy agents, and three GEO paths raise the cost of every change. The test suite is large, which is a strength, and it freezes some of that duplication in place. |

---

## 7. Industry comparison and the gaps

Dristik is an evidence-backed sample audit that refuses to invent off-page numbers. The tools below are the usual set a buyer already knows.

### 7.1 Full-site technical crawlers

**Screaming Frog, Sitebulb, Lumar, Botify, Oncrawl.**

They crawl hundreds of thousands of URLs, diff raw HTML and rendered DOM, ingest logs, export indexation issue lists, and chart redirect chains, duplicate clusters, and crawl depth for the whole host.

Dristik already covers the checklist those tools use on the pages it fetched: status, canonicals, robots, sitemap, titles, headings, hreflang signals, images, links, security headers, structured data.

| Gap | What the buyer expects | What Dristik does now |
|---|---|---|
| Coverage | Every indexable URL, or a stated statistical sample with a margin | A role sample. Default 10 pages. Deep tier caps at 500. |
| Rendering diff | Side-by-side raw and rendered, with the words that appear only after JavaScript | Render fallback when the first response looks thin. No systematic diff finding. |
| Logs | Googlebot and Bingbot hit mix, status, response time | Not ingested. |
| Issue inventory | Large title and meta counts with a URL export | Counts inside the fetch set. |
| Segmentation | Templates, indexability buckets, search demand joined to the URL | Template detection is page-type keywords in the path. |

Use a full-site crawler when the job is the rest of a large URL set. Use Dristik when the job is what to fix on the pages that sell, with proof.

### 7.2 SEO suites and link indexes

**Ahrefs, Semrush, Moz, SE Ranking.**

They own keyword and backlink indexes, rank tracking, site audit, and a content brief in one login. Domain Rating, Authority Score, and Domain Authority are their numbers. They are not Google’s numbers. Dristik already labels vendor metrics that way when a provider is connected.

| Gap | Suite behavior | Dristik behavior |
|---|---|---|
| Backlinks | Instant referring-domain graph, lost links, anchors, intersect | Only after an ADVANCED provider sync. No intersect or disavow workflow of suite depth. |
| Keywords | Large keyword database, difficulty, volume, CPC | DataForSEO or SerpAPI when connected. Gap engine exists and is not on the sealed agent path. |
| Rank tracking | Daily ranks for a project’s keyword set | `serp_tracker.py` and keyword routes exist. Not the default audit input. |
| Site audit | Broader crawl, less evidence discipline, one health score | Sample crawl, evidence discipline, several competing scores. |
| Brand SERP | Knowledge panel, sitelinks, reviews as observed SERP features | Stored when a SERP payload contains them. |

A suite shows a number in the first minute because it already crawled the web. Dristik shows `NOT_CONNECTED` until the customer brings a key.

### 7.3 Content optimization

**Surfer, Clearscope, MarketMuse, Frase.**

They score a draft against the current top-ranking pages for one query: headings, entities, word bands, and related questions.

Dristik’s content agents and the section copywriter read the customer’s pages. They do not pull the current top 10 for the target query unless a SERP provider was synced and that payload is handed to the agent. Today it is not handed to the agent.

Gap: query-level content briefs with competitor headings and a term checklist.

### 7.4 AI visibility and GEO tools

**Profound, Peec, Scrunch, Otterly, AthenaHQ, Goodie, plus Ahrefs Brand Radar and Semrush AI Visibility.**

Their product is the measurement: scheduled prompts, many engines, mention rate, citation rate, sentiment, competitor share, and a trend. Methods differ enough that two tools disagree on the same brand.

Dristik’s rule (blank unless measured, repeated runs, several engines, mention and citation and accuracy and competitor visibility and entity accuracy) is stricter than most of that category. The implementation is split across pool simulations, a commercial simulator, a live monitor, and a pipeline snapshot.

| Gap | Category leaders | Dristik |
|---|---|---|
| Default experience | Open the product and see last week’s share of voice | Open the product and see on-page readiness, with visibility blank until keys and a monitor run |
| Prompt operations | A managed prompt library per brand, tagged by buyer stage | Discoverability agent invents a matrix. Six commercial questions. Query classes are specified and not all enforced on the seal path |
| Engines | ChatGPT, Perplexity, Gemini, AI Overviews, often Copilot | Adapters for OpenAI search, Perplexity, Claude, Gemini, Groq. Overviews and Copilot are named and not first-class pool agents |
| History | Weekly trend is the screen | Pipeline snapshots and radar exist. Radar’s primary series is still the DOM |
| Accuracy | Some tools check whether the cited span supports the sentence | Citation rate can be stored. Accuracy is not the headline field on the seal |
| Separation of concerns | They rarely pretend the measurement is an on-page score | The UI pillar blend can put readiness and visibility in one GEO card |

### 7.5 CRO, accessibility, and security specialists

| Category | Typical product | Dristik | Gap |
|---|---|---|---|
| CRO | Hotjar, Microsoft Clarity, FullStory, Contentsquare, VWO. Replay, heatmaps, experiments. | DOM heuristics and a visual UX pass. GA4 provider exists and is not wired into the sealed lifecycle call. | No replay, no experiment, no measured conversion rate on the default report. |
| Accessibility | axe, WAVE, Siteimprove, deque. Rule engines plus a human audit and a VPAT. | Automated screening, explicitly not a certification. | No maintained rule-engine parity claim, no manual audit workflow, no VPAT. |
| Security | Mozilla Observatory, SecurityHeaders.com, and a real test team. | Header and TLS presence. | A header baseline. Buyers who want a penetration test need a different product. The report should say that every time. |

### 7.6 Agency PDF audits

A white-label checklist such as the sample compared in `docs/sample-seo-audit-vs-dristik.md` covers indexing, sitemap, SSL, robots, redirects, titles, headings, speed words, and mobile placeholders. It often asserts that a check is set up correctly without a URL list, and it promises rankings and sales the evidence does not support.

Dristik is ahead of that PDF on evidence tokens, scope labels, patch files, GEO, and the refusal to invent metrics. It is behind that PDF on a single sitewide count for every template. The improvement is a deep-crawl export for the technical sections, not a return to unsupported sales claims.

### 7.7 Enterprise SEO platforms

**Conductor, BrightEdge, seoClarity.**

They combine rank, content, technical monitoring, and workflow at account scale, with SSO, audit logs, and a customer-success motion. Dristik has RBAC, org and workspace routes, SSO-related tests, and an audit log surface. It does not have their crawl fleet, their keyword warehouse, or their engagement workflow (assignments, client approvals, recurring business reviews as a product).

### 7.8 Where Dristik is already ahead

- A claim without an evidence id is dropped.
- Visibility is not copied from on-page GEO readiness.
- Vendor authority metrics are not merged into a fake Google score.
- Trust can be omitted instead of invented.
- Technical severity, business impact, confidence, and blocking status stay independent.
- The patch ZIP gives a developer something to ship in the same week.
- Representative-sample scope is an explicit product decision.

---

## 8. Improvement plan

Each item names the change and the main files. Ship P0 before P2. P0 is what makes one report agree with itself.

### P0 — Make one run tell one story

1. **Score after the evidence is complete.** Move `calculate_scores` and `calculate_honest_scores` to after external-authority attachment, the second causal pass, and live visibility. Pass `external_authority_connected` from the attachment instead of hardcoding `False`. Rebuild the 7/30/90 roadmap and the top 10 from that same finding list.
   Files: `orchestration/orchestrator.py`, `scoring/engine.py`.

2. **One score on screen.** Publish the eight engine categories as the numbers. Make Human / Google / AI-readiness views that are clearly labeled blends. Point `pillarSynthesis.ts` and `ScoringRubricModal.tsx` at those categories. Update `scoring_rubric.py` so it no longer teaches 25/25/20/20/10 as if the engine used those weights.
   Files: `scoring/scoring_rubric.py`, `frontend/src/lib/pillarSynthesis.ts`, `frontend/src/components/ScoringRubricModal.tsx`.

3. **Label simulation and measurement in the report body.** The AI-search agents and the six-question simulator stay `SIMULATION_ONLY`. The visibility card renders only `run_audit_visibility` or a pipeline snapshot, with engine names, query count, and repeat count. Put the simulated matrix in an appendix titled as a writing exercise.
   Files: `agents/runtime/registry.py` task cards, `intelligence/geo/audit_monitor.py`, the GEO report components.

4. **Stop the lifecycle block from looking measured.** Call `lifecycle_service` with the real GSC, GA4, and CRM connection flags, or omit the section when all three are false.
   Files: `orchestration/orchestrator.py`, `connectors/lifecycle_revenue.py`.

5. **Scope line on every finding.** Wave-1 agents and post-DAG auditors set `PAGE_VERIFIED`, `SAMPLE_VERIFIED`, or `SITE_INFERRED` before the narrative is written. The executive summary states the page limit in the first paragraph.
   Files: `evidence/taxonomy.py`, the narrative generator under `reports/`.

### P1 — Close the gaps a buyer will demo

6. **Hand real inputs to the agents that claim to use them.** When a GSC, keyword, or SERP snapshot exists, put query and rank rows on the blackboard before wave 2 so intent, cannibalization, and the SEO copywriter can cite them. When it does not exist, those agents say so and skip query-level advice.
   Files: `external_authority/audit_bridge.py`, `agents/runtime/specialist.py`, `agents/page/intelligence.py`.

7. **Make live visibility a small observatory.** A saved prompt set per brand, the six query classes, at least two repeats, availability detection per engine, and stored mention rate, citation rate, citation accuracy, competitor visibility, and entity accuracy. Radar’s timeline should plot those snapshots next to DOM diffs.
   Files: `intelligence/geo/audit_monitor.py`, `intelligence/geo/adapters/`, `intelligence/monitoring/radar.py`.

8. **Content brief from a SERP, behind the ADVANCED plan.** For each priority query, fetch the current top results through the connected SERP provider and produce a heading and entity checklist. Do this as a separate action. Leave the brief empty when the provider is down.
   Files: `external_authority/providers/serp.py`, `intelligence/competitive/semantic_gap.py`.

9. **Technical export for deep tier.** When crawl depth is standard or deep, emit title, meta, H1, status, canonical, and indexability as CSV for every fetched URL. Keep the sample caveat on quick tier.
   Files: `analyzers/meta_rollup.py`, `analyzers/heading_analyzer.py`, a report export route.

10. **Wire GA4 into CRO or keep CRO qualitative.** If the GA4 snapshot has landing pages and key events, the CRO section shows those rates and labels them GA4. If not, the section title stays “heuristic from the crawled pages.”
    Files: `external_authority/providers/ga4.py`, `intelligence/ux/visual_ux_tester.py`.

11. **Enforce plan limits on start and on sync.** `POST /analyses` checks crawl tier. Authority jobs check FREE, STANDARD, and ADVANCED. A missing encryption key returns a clear not-configured state in the UI.
    Files: `api/routes/audits/analyses.py`, `external_authority/service.py`.

12. **Fix capability identity.** Give Gemini and Claude their own agent ids, or rename capabilities `29` and `30` so the map matches the agent that runs.
    File: `agents/runtime/registry.py`.

### P2 — Durability and a shorter architecture

13. **One database story.** Move audit runs, twins, timelines, outcomes, and external authority toward one migrated store so regression history survives a restart. Keep SQLite for local development if that remains the choice, and stop splitting truth across process memory and four files.
    Files: `persistence/`, `intelligence/monitoring/`, `external_authority/store.py`.

14. **Delete duplicate work on the hot path.** Pick one business-identity writer. Pick one causal pass, after competitive data exists. Pick one narrative writer. Route tier-1 capability ids through the same rules the SEO agents use, or stop running both. Archive `agents/legacy/` once tests import the registry.
    Files: `orchestration/orchestrator.py`, `intelligence/business/understanding.py`, `agents/legacy/`.

15. **Respect quick mode.** When the mission is quick, run the deterministic analyzers, business discovery, GEO readiness, and the executive step. Skip the full 105-agent workforce. Record which agents were skipped.
    Files: `mission/director.py`, `orchestration/agent_pool.py`.

16. **Evidence window.** For crawls over a few dozen pages, retrieve evidence by agent and by page sample, not the first 60 rows in the store.
    File: `agents/runtime/specialist.py`.

17. **Org binding.** Do not fall back to `org_default` for authority snapshots. A run without an org fails the attachment with an explicit empty state.
    File: `external_authority/audit_bridge.py`.

18. **Closed-loop patch check.** After a GitHub or CMS apply, schedule one recrawl of the touched URLs and attach the result to the outcome job as cleared or still present, with the new snapshot hash.
    Files: `remediation/`, `intelligence/outcomes/`.

### P3 — After the report is coherent

19. Rendered-versus-raw diff as a finding type, still inside the page budget.
20. Optional log-file upload (status, user agent, URL) joined to the crawled URL list. Do not infer the rest of the site.
21. Accessibility: run a maintained rule engine and keep the “screening, not certification” label.
22. White-label report export that uses the engine categories and the scope paragraph, for the agency plan.
23. Prompt-library sharing across a workspace so the observatory is not rebuilt per audit.

### What not to add

- A single 0–100 authority or GEO rank that mixes on-page readiness, simulations, and vendor Domain Rating.
- Sitewide issue counts from a 10-page crawl.
- A penetration test, a WCAG certificate, or a revenue forecast from missing headers.
- Fabricated search volume, backlinks, or citations when a provider is down. Fail open and leave the metric blank.

---

## 9. How to read a run after these facts

A finished audit is trustworthy when three sentences are true in the report the customer sees:

1. These pages were fetched, and the findings are about that set unless a provider snapshot says otherwise.
2. AI visibility is a measured citation rate with engine names, or it is blank.
3. The category numbers on the screen are the eight engine scores, and Trust is either measured from a connected provider or omitted.

Until the P0 items land, trust the evidence ledger, the crawl summary, and the external-authority coverage states. Treat the headline overall, the five-pillar modal, and any simulated engine matrix as display layers that can disagree with the engine.
