"""
Tests for the 3 dedicated PPT deck generation agents and the 70+ slide PowerPoint engine.
Verifies agent registration, task cards, non-repetition guarantees, and native PPTX compilation.
"""
import pytest
from app.agents.runtime.registry import (
    DECK_AGENTS_V1,
    AGENT_REGISTRY,
    SPECIALIST_AGENTS_V3,
    list_deck_specialists,
    specialist_count,
    get_agent_definition,
)
from app.agents.runtime.task_cards import task_card_for
from app.domain.models import (
    ExecutiveReport,
    BusinessProfile,
    OverallScoreResult,
    ThreeWayComparison,
    CrawlManifest,
    PageEvidence,
    Finding,
    Severity,
    Category,
    CategoryScore,
    RoadmapItem,
)
from app.agents.deck.architect import DeckArchitectAgent
from app.agents.deck.data_analyst import DeckDataAnalystAgent
from app.agents.deck.pptx_builder import DeckPptxBuilderAgent
from app.agents.deck.coordinator import generate_executive_pptx_deck


def _build_test_report() -> ExecutiveReport:
    scores = OverallScoreResult(
        overall_score=78.5,
        grade="B+",
        health_label="Calibrated",
        category_scores={
            "TECHNICAL_SEO": CategoryScore(category=Category.TECHNICAL_SEO, score=82.0, summary="Good foundation"),
            "SCHEMA": CategoryScore(category=Category.SCHEMA, score=68.0, summary="Missing entity schema"),
            "CONTENT": CategoryScore(category=Category.CONTENT, score=74.0, summary="Solid content depth"),
            "GEO": CategoryScore(category=Category.GEO, score=62.0, summary="Extraction ambiguity"),
            "UX_CONVERSION": CategoryScore(category=Category.UX_CONVERSION, score=79.0, summary="Minor CTA friction"),
            "COMPETITIVE": CategoryScore(category=Category.COMPETITIVE, score=71.0, summary="Parity with peers"),
        }
    )
    pages = [
        PageEvidence(
            url="https://acme-analytics.io/",
            page_type="homepage",
            title="Acme Analytics — Enterprise Observability & Intelligence",
            meta_description="Real-time telemetry and unified data observability platform for modern engineering teams.",
            word_count=420,
            ttfb_ms=175.0
        ),
        PageEvidence(
            url="https://acme-analytics.io/pricing",
            page_type="pricing",
            title="Pricing & Packaging Plans — Acme Analytics",
            meta_description="Simple transparent pricing for growth teams and global enterprises.",
            word_count=290,
            ttfb_ms=190.0
        ),
        PageEvidence(
            url="https://acme-analytics.io/features",
            page_type="product",
            title="Features & Architecture Capabilities — Acme Analytics",
            meta_description="Automated telemetry pipelines, anomaly detection, and distributed tracing.",
            word_count=510,
            ttfb_ms=160.0
        )
    ]
    manifest = CrawlManifest(
        domain="acme-analytics.io",
        base_url="https://acme-analytics.io",
        total_pages_discovered=3,
        pages=pages,
        sitemap_found=True,
        robots_txt_found=True,
        crawl_health={"avg_ttfb_ms": 175.0, "broken_links_count": 0}
    )
    findings = [
        Finding(
            finding_id="f_001",
            title="Missing Organization Schema Entity Node",
            description="Root homepage lacks structured JSON-LD Organization markup.",
            category=Category.SCHEMA,
            severity=Severity.HIGH,
            impact_score=8,
            recommendation="Deploy Organization JSON-LD with SameAs links."
        ),
        Finding(
            finding_id="f_002",
            title="Weak Call to Action Button Microcopy",
            description="Primary buttons use passive 'Submit' prompts rather than active outcome verbs.",
            category=Category.UX_CONVERSION,
            severity=Severity.MEDIUM,
            impact_score=6,
            recommendation="Replace Submit with Start Free Trial."
        ),
        Finding(
            finding_id="f_003",
            title="Ambiguous Generative Extractability in Hero Copy",
            description="Hero copy uses poetic prose preventing LLM quotation.",
            category=Category.GEO,
            severity=Severity.CRITICAL,
            impact_score=9,
            recommendation="Provide 40-60 word definition block."
        )
    ]
    return ExecutiveReport(
        report_id="rep_test_001",
        analysis_id="an_test_001",
        website_url="https://acme-analytics.io",
        domain="acme-analytics.io",
        generated_at="2026-10-07 18:00:00 UTC",
        business_profile=BusinessProfile(business_name="Acme Analytics"),
        scores=scores,
        story_summary="Independent multi-agent audit executed for Acme Analytics.",
        primary_strategic_opportunity="Deploy Organization JSON-LD schemas and /llms.txt manifests.",
        consultant_advice_what_to_ignore="Ignore cosmetic site redesigns and bulk backlink campaigns.",
        three_way_comparison=ThreeWayComparison(
            human_visitor_perspective="Human visitors perceive strong technical velocity but face CTA friction.",
            search_engine_perspective="Search spiders crawl canonical 200 OK paths cleanly.",
            ai_answer_engine_perspective="Generative answer engines struggle to extract pricing and target personas."
        ),
        crawl_manifest=manifest,
        findings=findings,
        roadmap_7_days=[
            RoadmapItem(
                timeframe="7_days",
                title="Deploy Canonical 301 Rules",
                description="Consolidate duplicate URL variants to protect crawl budget.",
                impact="High",
                effort="Low",
                category=Category.TECHNICAL_SEO,
            )
        ],
        roadmap_30_days=[
            RoadmapItem(
                timeframe="30_days",
                title="Inject Organization JSON-LD Schema",
                description="Anchor corporate entity with SameAs links.",
                impact="Medium",
                effort="Medium",
                category=Category.SCHEMA,
            )
        ],
        roadmap_90_days=[
            RoadmapItem(
                timeframe="90_days",
                title="Establish Closed-Loop Regression Tests",
                description="Automate monthly DOM and answer-engine extraction audits.",
                impact="Medium",
                effort="High",
                category=Category.TECHNICAL_SEO,
            )
        ],
    )


def test_3_deck_agents_registered():
    """Verify that all 3 deck agents are registered and distinct from the 35 DAG specialists."""
    deck_specialists = list_deck_specialists()
    assert len(deck_specialists) == 3
    expected_ids = {
        "deck.architect.v1",
        "deck.data_analyst.v1",
        "deck.pptx_builder.v1"
    }
    assert set(DECK_AGENTS_V1.keys()) == expected_ids

    # Verify each agent definition contract
    for aid in expected_ids:
        defn = get_agent_definition(aid)
        assert defn is not None
        assert defn.domain == "PRESENTATION"
        assert len(defn.capabilities) >= 2
        assert len(defn.required_evidence) >= 2

    # Registry may grow; the invariant is consistency across runtime surfaces.
    assert specialist_count() == len(SPECIALIST_AGENTS_V3)
    assert len(SPECIALIST_AGENTS_V3) >= 50


def test_deck_task_cards_present():
    """Verify detailed task cards exist for all 3 deck agents."""
    for aid in ["deck.architect.v1", "deck.data_analyst.v1", "deck.pptx_builder.v1"]:
        card = task_card_for(aid)
        assert len(card) > 80
        assert "Audit only what the evidence pack contains" not in card


def test_architect_generates_over_70_slides_with_zero_repetition():
    """Verify the architect generates at least 70 unique slides with 0 duplicates."""
    architect = DeckArchitectAgent()
    blueprint = architect.create_blueprint("acme-analytics.io", "2026-10-07")

    assert blueprint.total_slides >= 70
    assert len(blueprint.slides) >= 70
    assert len(blueprint.modules) == 11

    # Verify zero-repetition rule holds
    assert architect.verify_zero_repetition(blueprint) is True

    # Assert uniqueness of all slide attributes
    slide_ids = [s.slide_id for s in blueprint.slides]
    slide_titles = [s.title for s in blueprint.slides]
    thematic_focuses = [s.thematic_focus for s in blueprint.slides]

    assert len(slide_ids) == len(set(slide_ids))
    assert len(slide_titles) == len(set(slide_titles))
    assert len(thematic_focuses) == len(set(thematic_focuses))


def test_data_analyst_binds_charts_and_grounded_metrics():
    """Verify data analyst binds real report scores and generates chart specs."""
    report = _build_test_report()
    architect = DeckArchitectAgent()
    blueprint = architect.create_blueprint(report.domain, report.generated_at)

    analyst = DeckDataAnalystAgent()
    populated = analyst.populate_data(blueprint, report)

    # Check chart presence across modules
    chart_slides = [s for s in populated.slides if s.chart is not None]
    assert len(chart_slides) >= 8

    # Check specific charts
    pillar_slide = next(s for s in populated.slides if s.slide_id == "slide_13_pillars_radar")
    assert pillar_slide.chart is not None
    assert pillar_slide.chart.categories == ["Discoverability", "Semantics", "Content", "GEO", "UX", "Competitive"]
    assert pillar_slide.chart.series[0]["values"] == [82.0, 68.0, 74.0, 62.0, 79.0, 71.0]

    status_slide = next(s for s in populated.slides if s.slide_id == "slide_30_http_status_codes")
    assert status_slide.chart is not None
    assert "200 OK" in status_slide.chart.categories


def test_pptx_builder_creates_valid_presentation_binary():
    """Verify PPTX builder produces valid 16:9 presentation binary bytes."""
    report = _build_test_report()
    pptx_bytes, blueprint = generate_executive_pptx_deck(report)

    assert isinstance(pptx_bytes, bytes)
    assert len(pptx_bytes) > 20000  # Non-trivial presentation size
    # Check standard ZIP / Office OpenXML magic bytes
    assert pptx_bytes.startswith(b"PK\x03\x04")
    assert blueprint.total_slides >= 70


def test_roadmap_cards_binding_with_populated_items():
    """Verify that roadmap items (7-day, 30-day, 90-day) bind descriptions correctly to slide cards."""
    report = _build_test_report()
    item = report.roadmap_7_days[0]
    assert item.rationale == item.description  # Check property compatibility

    architect = DeckArchitectAgent()
    blueprint = architect.create_blueprint(report.domain, report.generated_at)
    analyst = DeckDataAnalystAgent()
    populated = analyst.populate_data(blueprint, report)

    s71 = next(s for s in populated.slides if s.slide_id == "slide_71_phase1_7days")
    assert s71.cards[0].title == "Deploy Canonical 301 Rules"
    assert s71.cards[0].description == "Consolidate duplicate URL variants to protect crawl budget."

    s72 = next(s for s in populated.slides if s.slide_id == "slide_72_phase2_30days")
    assert s72.cards[0].title == "Inject Organization JSON-LD Schema"
    assert s72.cards[0].description == "Anchor corporate entity with SameAs links."

    s73 = next(s for s in populated.slides if s.slide_id == "slide_73_phase3_90days")
    assert s73.cards[0].title == "Establish Closed-Loop Regression Tests"
    assert s73.cards[0].description == "Automate monthly DOM and answer-engine extraction audits."


def test_deck_api_endpoints():
    """Verify API endpoints for deck.pptx, deck-manifest, and existing executive-deck."""
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock
    from app.main import app
    from app.orchestration.orchestrator import orchestrator

    import uuid
    client = TestClient(app)
    signup = client.post("/api/v1/auth/signup", json={
        "full_name": "Deck Owner",
        "email": f"deck_{uuid.uuid4().hex[:8]}@example.com",
        "password": "OwnerPass1",
        "organization_name": "Deck Org",
    })
    assert signup.status_code == 200, signup.text
    mock_run = MagicMock()
    mock_run.report = _build_test_report()
    mock_run.org_id = signup.json()["user"]["org_id"]
    mock_run.analysis_id = "an_test_001"
    mock_run.created_at = "2026-10-07"
    mock_run.domain = "acme-analytics.io"
    mock_run.website_url = "https://acme-analytics.io"

    original_get_run = orchestrator.get_run
    orchestrator.get_run = MagicMock(return_value=mock_run)

    try:
        # 1. Existing PDF/HTML report endpoint must continue to work
        res_exec = client.get("/api/v1/reports/an_test_001/executive-deck?format=json")
        assert res_exec.status_code == 200
        assert res_exec.json()["status"] == "READY"

        # 2. New 76-slide PowerPoint deck download endpoint
        res_pptx = client.get("/api/v1/reports/an_test_001/deck.pptx")
        assert res_pptx.status_code == 200
        assert res_pptx.headers["content-type"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        assert int(res_pptx.headers.get("x-dristik-slide-count", 0)) >= 70
        assert res_pptx.content.startswith(b"PK\x03\x04")

        # 3. Slide manifest endpoint
        res_manifest = client.get("/api/v1/reports/an_test_001/deck-manifest")
        assert res_manifest.status_code == 200
        data = res_manifest.json()
        assert data["total_slides"] >= 70
        assert data["zero_repetition_verified"] is True
        assert len(data["slides"]) == data["total_slides"]
    finally:
        orchestrator.get_run = original_get_run
