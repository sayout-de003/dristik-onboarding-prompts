# Dristik Backend - Comprehensive Directory Structure & Architecture

> **Repository:** Dristik (Enterprise AI Search, GEO, AEO, SEO & CRO Intelligence Platform)  
> **Backend Framework:** FastAPI, SQLAlchemy, Pydantic, Playwright, Celery / Async Worker  
> **Location:** `backend/`

---

## 1. Executive Architecture Overview

The Dristik backend is an enterprise-grade intelligence platform that audits web properties across 5 core pillars (**SEO, GEO, AEO, CRO, Crawling**) plus **Remediation** and **Reporting**. It operates as a deterministic, evidence-led system:

- **Representative Crawling:** Crawls representative pages (default: 5-page critical path) with Playwright headless rendering, computing content-addressable hashes.
- **Evidence-First Ledger & Graph:** All claims and findings require raw HTML/DOM evidence snapshots. Unmeasured indicators remain unmeasured (strictly zero fakes/hallucinations).
- **105-Agent Specialist Workforce Across 12 Domains & 7 Workflows:** Coordinated via a Modular DAG execution engine (`app/orchestration/pipeline_dag.py`), leveraging domain specialists for deep technical, semantic, conversational, competitive, and generative analysis.
- **Transparent Multi-Engine Scoring:** Calibrated rubric scoring across Google Search, OpenAI Search / SearchGPT, Perplexity, Claude, and Gemini.
- **Actionable Remediation & Patches:** Generates concrete AST-validated code, markup, and schema patches with automated git/CMS branch and rollback integration.

---

## 2. Root-Level Backend Directory Layout

```
backend/
├── app/                  # Core FastAPI application & domain modular monoliths
│   ├── main.py           # FastAPI application entrypoint & middleware configuration
│   ├── api/              # Platform Package: Modular HTTP routes, SSE streaming, authentication, & platform endpoints
│   ├── seo/              # Domain Modular Monolith: SEO pillar, 16 specialist agents, analyzers, competitive, reports
│   ├── geo/              # Domain Modular Monolith: GEO pillar, 12 specialist agents, adapters, citations, scoring, reports
│   ├── aeo/              # Domain Modular Monolith: AEO pillar, 10 specialist agents, engine, reports, 55-point taxonomy
│   ├── cro/              # Domain Modular Monolith: CRO pillar, 8 specialist agents, accessibility, analyzers, metrics, reports
│   ├── crawl/            # Domain Modular Monolith: Playwright crawler, URL frontier, audit ledger, knowledge, discovery
│   ├── remediation/      # Domain Modular Monolith: AST validator, diff engine, patch generator, verifier loop
│   ├── reports/          # Domain Modular Monolith: Core audit books, PDF generator, HTML renderer, presentation decks
│   ├── connectors/       # Platform Package: Third-party integrations (Google, Crux, DataForSEO, Authority, CMS, Repos)
│   ├── core/             # Platform Package: Config, security, logging, monitoring, observability, & multi-LLM inference
│   ├── db/               # Platform Package: Relational database models, repositories, session & CAS storage
│   ├── domain/           # Platform Package: Domain models, enums, contracts, scoring, evidence, capabilities, & commercial
│   ├── identity/         # Platform Package: Authentication, JWT, OAuth, RBAC enforcement, & tenancy/white-labeling
│   ├── orchestration/    # Platform Package: Dependency-directed DAG execution, mission control, cognition, & agent runtime
│   └── workers/          # Platform Package: Async background worker engine, Celery app, and scheduled tasks

├── deployment/           # Production containerization & proxy configuration
│   ├── Dockerfile        # Backend container build (Playwright + Python 3.12/3.14)
│   ├── docker-compose.yml# Local & production compose orchestration
│   └── nginx/            # Nginx reverse proxy configuration
├── docs/                 # Architectural specifications and engineering contracts
│   ├── architecture.md   # Domain boundaries, pillar registration, package map
│   ├── api.md            # HTTP route inventory and contract specifications
│   ├── agent-catalog.md  # 105-agent specialist registry across 12 domains and responsibilities
│   ├── scoring-methodology.md # Calibrated composite score formulation
│   ├── evidence-policy.md# Zero-fake, provenance, and grounding rules
│   └── report-specification.md # Multi-chapter audit book structure
├── migrations/           # Alembic database migration scripts
├── reports/              # Generated audit books (HTML / PDF exports)
├── scripts/              # Administrative, migration, and CLI utility scripts
│   ├── create_or_reset_admin.py # Superuser credential provisioner
│   ├── migrate.py        # Database migration runner
│   ├── validate_registry.py # Agent and pillar registry contract validator
│   └── reprocess_alienhouse_audit.py # Ground-truth benchmark auditor
├── tests/                # Comprehensive test suite (159+ test modules)
│   ├── unit/             # Core unit tests (scoring, dag, crawlers, evidence)
│   ├── contract/         # Schema, API, and pillar contract validations
│   ├── integration/      # End-to-end audit, crawl, and reporting pipelines
│   ├── security/         # SSRF, RBAC, tenant isolation, token security
│   ├── geo/              # AI search readiness, citation matrices, Per-engine eval
│   └── fixtures/         # Golden corpus & ground-truth audit fixtures
├── alembic.ini           # Alembic database migration configuration
├── app_settings.json     # Dynamic platform runtime configuration
├── conftest.py           # Pytest test fixtures and test environment setup
├── dristik.db            # SQLite persistence database (default local storage)
├── pyproject.toml        # Build system configuration & packaging
├── pytest.ini            # Pytest configuration flags and markers
├── requirements.txt      # Python package dependencies
└── README.md             # Backend development and execution instructions
```

---

## 3. Comprehensive Module Breakdown (`backend/app/`)

### 3.1 Application Entrypoint & Core Routing (`app/main.py` & `app/api/`)
Handles HTTP requests, streaming Server-Sent Events (SSE), authentication guards, and response serializations.

- **`app/main.py`**: The FastAPI application factory. Registers middlewares (CORS, SSRF boundary, security headers, request tracing), mounts `/api` routes, and configures lifecycle handlers.
- **`app/api/router.py`**: Root router registering all modular sub-routers.
- **`app/api/dependencies.py`**: FastAPI dependency injection providers (database session, current authenticated user, tenant context, rate limiters).
- **`app/api/routes/`**:
  - `audits/`:
    - `public_grader.py`: High-speed public preliminary site grader (lead magnet).
    - `stream.py`: Real-time SSE streaming for live audit execution progress, agent states, and logs.
    - `analyses.py`: Detailed audit retrieval, pillar breakdowns, and diagnostic drill-downs.
  - `identity/`:
    - `auth.py`: JWT-based user authentication, passwordless magic links, session refresh.
    - `orgs.py`: Multi-tenant organization management, workspace creation, member role assignments.
  - `intelligence/`:
    - `geo.py`: Generative Engine Optimization readiness, AI engine citation share, and prompt simulation endpoints.
    - `keywords.py`: AI search demand, conversational query tracking, and keyword gap analysis.
    - `radar.py`: Real-time visibility pulse, daily engine drift, and sentiment tracking.
    - `strategic.py`: Causal hypotheses, competitive Moat analysis, and strategic recommendations.
    - `outcomes.py`: Historical ROI tracking and remediation impact analysis.
  - `integrations/`:
    - `connectors.py`: Integration lifecycle (OAuth handshakes, API credential encryption, health checks).
    - `google.py`: Google Search Console (GSC) and Google Analytics (GA4) synchronizers.
    - `external_authority.py`: Backlink, SERP, and mention data synchronization.
  - `platform/`:
    - `commercial.py`: Tier plans, license entitlements, and feature gating.
    - `payments.py`: Razorpay and Stripe checkout sessions, webhooks, and GST-compliant invoicing.
    - `workspaces.py`: Multi-tenant workspace configuration and white-label branding.
    - `system.py`: System health, resource telemetry, and queue diagnostics.
    - `contact.py` & `meta.py`: Public lead capture and platform metadata.
  - `remediation/`:
    - `patches.py`: Remediation diff inspection, approval workflows, and downloadable patch packs.
  - `crawling.py`, `findings.py`, `reports.py`, `scores.py`: High-level domain entity endpoints.
- **`app/api/v1/`**: Backward-compatible v1 endpoints and schema bindings.

---

### 3.2 Audit Pillars (`app/pillars/`)
The foundational domain boundaries for the platform, orchestrating analysis across the 6 audit dimensions.

| Pillar Directory | Primary Class | Engine / Target | Responsibility |
| :--- | :--- | :--- | :--- |
| **`pillars/crawling/`** | `CrawlingPillar` | `app/crawl/` | Frontier management, Playwright HTML rendering, DOM capture, screenshot generation |
| **`pillars/seo/`** | `SeoPillar` | `app/agents/seo/` | Technical SEO, Schema, Indexability, On-page semantics, Internal linking |
| **`pillars/geo/`** | `GeoPillar` | `app/agents/geo/` | Generative Engine Optimization, AI citations, Share of Model (SoM) |
| **`aeo/`** | `AeoPillar` | `app/aeo/` | Answer Engine Optimization, direct answers, voice/conversational intent, 55-section audit |
| **`cro/`** | `CroPillar` | `app/cro/` | Conversion rate friction, trust factors, form abandonment, CTA visibility |
| **`pillars/remediation/`**| `RemediationPillar` | `app/remediation/`| AST-verified code, JSON-LD, Robots, and CMS patch generation |
| **`pillars/reporting/`** | `ReportingPillar` | `app/reports/` | Executive report synthesis, PDF book compilation, chapter rendering |
| **`pillars/registry.py`** | `PillarRegistry` | Unified Pillar Map | Maps `PillarId` enums to registered pillar services and execution plans |

---

### 3.2.1 Consolidated Modular SEO Domain (`app/seo/`)
Unifies all SEO logic, agents, deterministic analyzers, reports, and audit engine in a single modular monolith package:

- **`app/seo/__init__.py`**: Clean domain entrypoint exposing `SeoPillar`, agents, analyzers, report generators, and orchestrator.
- **`app/seo/pillar.py`**: Domain pillar executor implementing `SeoPillar` wave execution and scoring.
- **`app/seo/specialists.py`**: SEO specialist agent registry and factory.
- **`app/seo/agents/`**: Core specialist reasoning agents (`technical`, `content`, `internal_linking`, `structured_data`, `performance`, `specialized_seo`).
- **`app/seo/analyzers/`**: 16 Algorithmic analyzers (canonicals, headings, redirects, HTTP status, link depth, media assets, meta rollups, rendering disparity, schema, SERP, sitemaps, topical authority, local, international, ecommerce).
- **`app/seo/reporting/`**: Full SEO report book compiler, Jinja2 template renderer (`seo_audit_book.html`), visual charts, print reports, and PDF engine.
- **`app/seo/audit/`**: Master 30-agent SEO audit DAG, crawler routers, discovery engines, evidence ledgers, and remediation contracts.

---

### 3.2.2 Consolidated Modular CRO Domain (`app/cro/`)
Unifies all Conversion Rate Optimization (CRO), behavioral UX, form friction, pricing trust, reporting, and 55-section intelligence in a single modular monolith package:

- **`app/cro/__init__.py`**: Clean domain entrypoint exposing `CroPillar`, agents, `CroAnalyzer`, reporting, and engine.
- **`app/cro/pillar.py`**: Domain pillar executor implementing `CroPillar` wave execution, scoring, and `evaluate_friction`.
- **`app/cro/agents.py`**: Specialist CRO reasoning agents (`CroConversionAgent`, `VisualUxFrictionAgent`, `FormAbandonmentAgent`, `PricingTrustAgent`).
- **`app/cro/analyzer.py`**: Multi-page deterministic conversion friction analyzer (`CroAnalyzer`, `analyze_cro`, CTA rewrites).
- **`app/cro/engine.py`**: Deep 55-section CRO intelligence audit engine (`build_cro_intelligence`, `build_from_executive_report`).
- **`app/cro/taxonomy.py`**: Master 55-section CRO audit taxonomy (checklists, evidence states, parts, specialists).
- **`app/cro/metrics.py`**: Conversion metric formulas, lift calculations, and measurement rules.
- **`app/cro/reporting.py`**: Agency-grade HTML/JSON CRO intelligence reports and audit book compiler (`render_cro_audit_book`).

---

### 3.2.3 Consolidated Modular AEO Domain (`app/aeo/`)
Unifies all Answer Engine Optimization (AEO), featured snippet extractability, conversational intent, 16-specialist registry, 55-section master taxonomy, decoupled scoring, report generation, and 5 certified CSV exports in a single modular monolith package:

- **`app/aeo/__init__.py`**: Clean domain entrypoint exposing `AeoPillar`, specialist agents, contracts, 55-section taxonomy, decoupled scoring, report generators, and CSV exporters.
- **`app/aeo/pillar.py`**: Domain pillar executor implementing `AeoPillar` wave execution, scoring, and lifecycle contracts.
- **`app/aeo/specialists.py`**: 16-Specialist Modules Registry (`AeoSpecialistRegistry`, `AeoFindingRecord`, `SpecialistResult`) and specialist builder (`AEO_SPECIALISTS`, `build_aeo_agents`).
- **`app/aeo/agents.py`**: Specialist reasoning agents (`DirectAnswerAgent`, `ConversationalIntentAgent`, `EntityConsensusAgent`).
- **`app/aeo/contracts.py`**: Unified measurement contracts, evidence envelope schemas, and question registry definitions (`NormalizedEvidenceRecord`, `SharedResultEnvelope`, `QuestionRegistry`).
- **`app/aeo/taxonomy.py`**: Canonical 55-Section Master Taxonomy, 7 Parts, and 15 Appendices (`AEO_SECTIONS_55`, `AEO_PARTS`, `AEO_APPENDICES_15`, `DISCIPLINE_TAXONOMY`).
- **`app/aeo/analysis.py`**: Evidence grounding, claim support ratios, and anti-fabrication remediation proposals (`ClaimGroundingEvaluator`, `RemediationPlanner`).
- **`app/aeo/scoring.py`**: 4-tier decoupled metrics calculator & evidence states (`AeoMetricsCalculator`, `EvidenceState`, `MetricScore`).
- **`app/aeo/reporting/`**:
  - `generator.py`: Complete 55-section AEO report generator in HTML and structured JSON (`CompleteAeoReportGenerator`, `aeo_report_generator`).
  - `audit_book.py`: 55-section evidence book renderer (`render_aeo_audit_book`, `aeo_cover_figure`).
  - `audit_index.json`: Master 55-section index specification.
  - `exports.py`: 5 dedicated AEO CSV export deliverables (Remediation Tracker, Question-to-Page Dataset, Live Benchmark, Brand Facts, Evidence Ledger).
- **`app/aeo/router.py`**: Dedicated FastAPI router for AEO reporting and export endpoints.

---

### 3.3 Autonomous Specialist Agents (`app/agents/`)
Houses the 105-agent specialist workforce across 12 domains that performs autonomous audit reasoning.

- **`agents/runtime/`**:
  - `base_agent.py`: Abstract Base Agent enforcing deterministic input/output contracts.
  - `reasoner.py`: Grounded reasoning engine matching findings against evidence ledgers.
  - `registry.py`: Central 105-agent registry and dynamic lookup by task capability.
  - `execution_context.py`: Thread-safe audit run context holding page snapshots and facts.
  - `task_cards.py`: Standardized agent prompt definitions and scoring rubrics.
- **`agents/seo/`**:
  - `technical.py` / `technical_seo_agent.py`: Server headers, status codes, canonicals, redirects.
  - `content.py` / `content_seo_agent.py`: Thin content, keyword cannibalization, entity density.
  - `internal_linking.py` / `internal_linking_agent.py`: PageRank flow, orphan pages, anchor relevance.
  - `structured_data.py`: Schema.org JSON-LD hierarchy validation.
  - `performance_agent.py`: Core Web Vitals (LCP, FID, CLS, INP) analysis.
- **`agents/geo/`**:
  - `citation_analyzer.py`: Tracks authoritative source citations across LLM engines.
  - `readiness_analyzer.py`: Computes LLM extractability and factual chunk clarity.
  - `information_gain_agent.py`: Evaluates unique data points and original insights vs web corpus.
  - `engine_analyzer.py`: Multi-model sentiment and recommendation strength.
- **`agents/aeo/`**:
  - `direct_answers.py`: Zero-click search extractability and snippet formatting.
  - `conversational_intent.py`: Long-tail conversational query intent matching.
  - `consensus_analyzer.py`: Verification of entity consensus and factual contradiction.
- **`cro/agents.py`**: Consolidated specialist agents (`CroConversionAgent`, `VisualUxFrictionAgent`, `FormAbandonmentAgent`, `PricingTrustAgent`).
- **`agents/discovery/`**:
  - `brand_discovery.py`: Brand entity disambiguation, Wikipedia/Wikidata presence.
  - `business_discovery.py`: Business model classification, ICP identification, value proposition.
  - `product_perspective_agent.py`: Catalog structure, transactional intent mapping.
  - `crawl_discovery.py`: Representative URL sampling and high-value path prioritization.
- **`agents/deck/`**:
  - `slide_builder.py`, `pptx_generator.py`, `narrative_synthesizer.py`: Generates executive presentation slide decks (.pptx) summarizing audit conclusions.
- **`agents/legacy/`**:
  - Backward compatibility wrappers ensuring legacy endpoint calls resolve to new specialist agents.

---

### 3.4 Web Crawling & DOM Extraction (`app/crawl/`)
The foundational data ingestion engine.

- **`url_frontier.py`**: Priority queue governing crawl order, depth limits, and canonical dedup.
- **`browser.py`**: Playwright browser automation pool with resource blocking and screenshot capture.
- **`deduplication.py`**: Content-addressable hashing (SimHash / SHA-256) preventing redundant crawls.
- **`sitemap.py`**: XML sitemap, sitemap index, and robots.txt parsing.
- **`vector_store.py`**: Semantic embeddings of extracted page chunks for retrieval.
- **`app/crawl/analyzers/`**:
  - `html_parser.py` & `html.py`: Resilient DOM parsing and element extraction.
  - `visible.py`: Extracted human-visible text discarding boilerplate/navigation.
  - `metadata.py`: OpenGraph, Twitter cards, meta robots, canonicals.
  - `link_graph.py`: Complete in-degree/out-degree directed graph of internal links.
  - `security.py`: Mixed content, SSL/TLS validation, security headers (CSP, HSTS).

---

### 3.5 Intelligence & Multi-Engine Evaluators (`app/intelligence/`)
Domain intelligence services providing deep semantic calculations.

- **`intelligence/geo/`**:
  - Per-engine evaluators (`openai_search.py`, `perplexity.py`, `claude.py`, `gemini.py`, `groq.py`).
  - `benchmark_generator.py`: Generates representative prompt queries based on business taxonomy.
  - `attribution_engine.py`: Measures citation attribution probability.
  - `buyer_surfaces.py`: Identifies high-intent B2B/B2C conversational buyer queries.
- **`intelligence/aeo/`**:
  - `taxonomy_55.py`: 55-question authoritative conversational intent taxonomy.
  - `claim_grounding.py`: Maps engine responses to grounded site claims.
- **`intelligence/business/`**:
  - `understanding.py`: Synthesizes industry, market, and business model understanding.
  - `entity_resolver.py`: Resolves brand entities against authoritative knowledge graphs.
  - `intent_graph.py`: Builds search intent journey maps (Awareness -> Decision).
- **`intelligence/competitive/`**:
  - `benchmark.py` & `engine.py`: Side-by-side comparative benchmarking against identified competitors.
  - `semantic_gap.py`: Identifies missing topics and topical authority deficits.
  - `causal_explainer.py`: Explains why competitors outrank target in AI engines.
- **`intelligence/knowledge/`**:
  - `website_knowledge_graph.py`: Extracts entity-relation graph (Subject-Predicate-Object).
  - `evidence_sufficiency.py`: Verifies if claims have sufficient on-page proof.
- **`intelligence/monitoring/`**:
  - `radar.py`: Daily/weekly engine visibility monitoring.
  - `regression_detector.py`: Detects loss of citations or ranking drops.
  - `visual_intelligence.py`: Visual screenshot regression and UX drift analyzer.
- **`cro/engine.py`**: Conversion rate friction modeling, heuristics, and 55-section audit engine.
- **`intelligence/accessibility/`**: Deep WCAG 2.1 compliance evaluation.

---

### 3.6 Evidence Ledger & Graph (`app/evidence/`)
Guarantees zero-hallucination compliance across all findings.

- **`graph.py`**: Directed Evidence Graph linking Page -> Fragment -> Claim -> Finding.
- **`claim_ledger.py`**: Immutable ledger recording verified facts extracted from DOM snapshots.
- **`store.py`**: High-performance persistent storage for raw snapshots and parsed trees.
- **`contradiction_detector.py`**: Identifies contradictory statements across different site pages.
- **`evidence_validator.py`**: Enforces that no finding is created without an attached evidence pointer.
- **`site_facts.py`**: Consolidated repository of confirmed domain metadata.

---

### 3.7 Scoring & Calibration Engine (`app/scoring/`)
Calculates composite and granular scores with complete mathematical transparency.

- **`engine.py`**: Master scoring engine aggregating scores across the 5 pillars.
- **`scoring_rubric.py` & `scoring_rubric_v5.json`**: Explicit weights, penalties, and thresholds.
- **`calibration_v5.py`**: Curve normalization to prevent score inflation or false penalties.
- **`score_explanations.py`**: Plain-English explanations of score deductions and improvement potential.
- **`curves.py`**: Mathematical decay and distribution curves.

---

### 3.8 Pipeline Orchestration (`app/orchestration/`)
Governs the DAG execution lifecycle.

- **`dag.py`**: Dependency-directed acyclic graph defining step-by-step audit phases.
- **`planner.py`**: Dynamic execution planner adjusting crawl depth and agent selection.
- **`agent_pool.py`**: Concurrency-controlled execution pool for specialist agents.
- **`dynamic_team.py`**: Assembles tailored agent clusters based on site archetype.
- **`integrity_gate.py`**: Pre-publish gate verifying findings against evidence before completion.
- **`public_grader.py`**: Lightweight, rapid orchestration for public audit evaluations.

---

### 3.9 Remediation & Patch Generation (`app/remediation/`)
Translates audit findings into concrete, production-ready code modifications.

- **`patch_engine.py`**: Generates AST-verified patches across HTML, JavaScript, JSON-LD, and config files.
- **`patch_pack.py`**: Bundles patches into downloadable `.zip` archives or GitHub pull requests.
- **`diff_engine.py`**: Unified diff generator showing clear before/after modifications.
- **`ast_validator.py`**: Syntactic validation ensuring generated patches cannot break target code.
- **`verification.py`**: Re-crawls and verifies whether applied patches successfully resolved findings.
- **`rollback.py`**: Generates safe reversion scripts for any deployed patch.
- **`approval.py`**: Enterprise human-in-the-loop review and approval workflows.

---

### 3.10 Reporting & Executive Books (`app/reports/`)
Generates high-fidelity, agency-grade audit reports.

- **`seo_audit_book.py` / `geo_audit_book.py` / `aeo_audit_book.py` / `cro/reporting.py`**: Specialized multi-page audit books for each domain.
- **`adaptive_audit_book.py`**: Dynamically adapts chapter depth based on discovered issues.
- **`html_renderer.py`**: Jinja2 templating engine compiling reports with responsive CSS.
- **`pdf_generator.py`**: Headless browser rendering compiling print-ready executive PDFs.
- **`plain_english_engine.py`**: Translates technical jargon into executive summaries for C-level leadership.
- **`roadmap.py`**: Synthesizes 30-60-90 day prioritized engineering and content roadmaps.
- **`section_exports.py`**: Modular export service (JSON, CSV, Markdown, PPTX).

---

### 3.11 Third-Party Connectors (`app/connectors/`)
Pluggable integrations for CMS, code repositories, and analytics platforms.

- **CMS Platforms:** `wordpress/`, `webflow/`, `shopify/`.
- **Code Repositories:** `github/` (Automated PR creation, branch management).
- **Search & Analytics:** `google/` (GSC, GA4), `crux/` (Chrome User Experience Report), `dataforseo/`.
- **CRM:** `crm/` (HubSpot / Salesforce lead synchronization).
- **Base Interfaces:** `base/interface.py`, `base/telemetry_interface.py`, `base/permissions.py`.

---

### 3.12 LLM Inference & Policy (`app/inference/`)
Abstracts multi-LLM provider communication.

- **`llm_client.py`**: Unified async client for OpenAI, Anthropic Claude, Together AI, Groq, OpenRouter.
- **`model_router.py`**: Intelligent routing matching task complexity to cost-efficient models.
- **`prompt_compiler.py`**: Assembles prompts with inject-safe evidence context.
- **`fallback.py`**: Automatic multi-provider failover with exponential backoff.
- **`json_repair.py`**: Resilient parser fixing truncated or malformed JSON responses.
- **`budget_manager.py` & `pricing.py`**: Real-time token tracking and audit cost accounting.
- **`prompts/`**: Curated, versioned system and specialist prompt templates.

---

### 3.13 Persistence & Relational Models (`app/persistence/` & `app/db/`)
Data storage, repositories, and ORM models.

- **`persistence/storage_cas.py`**: Content-Addressable Storage (CAS) for HTML snapshots and assets.
- **`persistence/repository.py`**: Abstract repository interface for audits, pages, and findings.
- **`db/models/`**:
  - `finding.py`: Finding entity with severity, pillar, evidence pointer, and remediation ID.
  - `audit.py`: Audit run lifecycle, status, target URL, and execution metadata.
  - `scorecard.py`: Historical score snapshots and pillar breakdowns.
  - `user.py` & `organization.py`: User accounts, organization memberships, API keys.
  - `integration.py`: Connected platform tokens and configuration state.
- **`db/session.py`**: SQLAlchemy async session manager and connection pooling.

---

### 3.14 Enterprise Tenancy & Security (`app/tenancy/`, `app/identity/`, `app/core/security/`)
Enterprise security, compliance, and white-labeling.

- **`tenancy/`**: Strict tenant isolation, agency multi-client management, and custom branding/logos.
- **`identity/`**: JWT authentication, OAuth2 providers, SAML/SCIM SSO, and RBAC role enforcement.
- **`core/security/ssrf.py`**: Comprehensive SSRF protection preventing access to internal network IPs.
- **`core/security/trust_boundary.py`**: Strict sanitization of external crawl data.
- **`core/security/enterprise_audit_logger.py`**: Immutable compliance audit trail.

---

### 3.15 Background Workers & Tasks (`app/workers/` & `app/tasks/`)
Asynchronous execution infrastructure.

- **`workers/distributed_engine.py`**: In-process concurrent async worker orchestrator.
- **`workers/celery_app.py`**: Celery worker definitions for distributed cluster deployments.
- **`workers/scheduler.py`**: Scheduled recurring audits and continuous monitoring runs.
- **`tasks/`**: Concrete task implementations (`crawl_tasks.py`, `audit_tasks.py`, `report_tasks.py`).

---

## 4. Test Suite Structure (`backend/tests/`)

The backend maintains an extensive automated testing suite comprising 159+ test files:

- **`tests/unit/`**:
  - `test_dag.py`: Verifies pipeline DAG step dependencies and execution order.
  - `test_scoring.py` & `test_score_engine.py`: Verifies calibration and score calculation.
  - `test_crawler.py`: Frontier, deduplication, and extraction parsing tests.
  - `test_evidence.py`: Evidence graph consistency and claim verification.
- **`tests/contract/`**:
  - `test_contracts.py` & `test_api_contracts.py`: Verifies Pydantic DTO and REST API schemas.
  - `test_pillar_contracts.py`: Validates that each pillar conforms to the standard lifecycle contract.
- **`tests/security/`**:
  - `test_ssrf.py`: Validates URL frontier blocks internal IP ranges (127.0.0.1, 169.254.169.254, RFC1918).
  - `test_tenant_isolation.py`: Enforces data segregation across organizations.
  - `test_authorization.py` & `test_security_tokens.py`: RBAC and JWT validation tests.
- **`tests/geo/`**:
  - `test_readiness.py`, `test_citations.py`: AI search extractability and citation tracking tests.
- **`tests/integration/`**:
  - `test_audit_pipeline.py`: End-to-end audit execution from crawl to scoring.
  - `test_crawl_pipeline.py`: Playwright browser ingestion pipeline.
  - `test_reporting.py`: HTML and PDF report rendering validation.
- **`tests/fixtures/`**:
  - Golden corpus and ground truth fixtures (`alienhouse_ground_truth.json`).

---

## 5. Deployment & Configuration

- **`backend/deployment/Dockerfile`**: Optimized multi-stage Docker build installing Python runtime, Chromium, and Playwright dependencies.
- **`backend/deployment/docker-compose.yml`**: Full-stack container topology (FastAPI API, Celery worker, Redis queue, SQLite/PostgreSQL volume).
- **`backend/deployment/nginx/nginx.conf`**: Reverse proxy with SSE buffering disabled (`proxy_buffering off;`) for real-time audit streaming.
- **`backend/app_settings.json`**: Dynamic runtime configuration for model temperatures, crawl limits, and scoring weights.
