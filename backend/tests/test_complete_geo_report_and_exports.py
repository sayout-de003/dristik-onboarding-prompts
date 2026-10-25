"""
Unit & Integration Tests for Complete GEO Report & CSV Exports (2026 Master Standard)
"""
import pytest
from fastapi.testclient import TestClient

from app.domain.enums import Category, FindingStatus, Severity
from app.domain.models import (
    AiVisibilityScorecard,
    BusinessProfile,
    ExecutiveReport,
    Finding,
    GeoDimension,
    GeoQuestionEvidence,
    GeoReadinessReport,
    OverallScoreResult,
    PageReport,
    ThreeWayComparison,
)
from app.reports.export_service import generate_geo_remediation_csv
from app.geo.reporting.geo_report_generator import geo_report_generator


def _make_dummy_geo_report() -> ExecutiveReport:
    """Helper to build a valid ExecutiveReport fixture with GEO data."""
    page_1 = PageReport(
        url="https://acme.com",
        title="Acme Corp - Enterprise Workflow & AI Solutions",
        meta_description="Acme provides enterprise AI workflow software and cloud automation systems.",
        status_code=200,
        word_count=850,
        h1_tags=["Enterprise AI Workflow Automation"],
        schema_types=["Organization", "FAQPage"],
        ttfb_ms=180.0,
    )

    finding_1 = Finding(
        finding_id="VIS-001",
        category=Category.CONTENT,
        subcategory="Direct Answer Passage Omission",
        affected_urls=["https://acme.com"],
        expected_condition="Primary commercial capability must be summarized in a concise 50-word definition passage.",
        dependencies=["Commercial Copywriting", "FAQ Template"],
        status=FindingStatus.OPEN,
        owner="AI Search & Growth Team",
        severity=Severity.HIGH,
        title="Missing Direct Definition Answer Passage for Workflow Automation",
        description="The homepage lacks a clear, self-contained definition block for workflow automation.",
        recommendation="Deploy an explicit answer definition paragraph formatted for LLM chunk ingestion.",
        why_it_matters="SearchGPT and Perplexity fail to extract direct quotes, citing competitor comparison pages instead.",
        validation_criteria="Automated re-crawl confirms passage extractability and zero entity contradiction.",
        priority=8,
        impact=9,
        effort=3,
        confidence=0.85,
        confidence_basis="Observed DOM Crawl & LLM Chunk Extractor",
    )

    geo_readiness = GeoReadinessReport(
        entity_name="Acme Corp",
        headline="Strong technical extractability with key comparison and pricing passage gaps.",
        extractability_score=86.5,
        questions_total=4,
        questions_supported=2,
        questions_partial=1,
        questions_unsupported=1,
        schema_types=["Organization", "FAQPage"],
        questions=[
            GeoQuestionEvidence(
                question_key="Q-DISC-01",
                question="What tools support workflow automation for enterprise teams?",
                status="SUPPORTED",
                answer="Acme Corp provides automated workflow orchestration.",
                answer_snippet="Acme provides enterprise AI workflow software.",
                recommended_answer="Add ProductOffer JSON-LD to confirm tier pricing.",
            ),
            GeoQuestionEvidence(
                question_key="Q-COMP-02",
                question="How does Acme compare to Zapier and Workato?",
                status="UNSUPPORTED",
                answer="",
                answer_snippet="",
                recommended_answer="Create an objective comparative table with explicit feature rows.",
            ),
        ],
    )

    visibility_scorecard = AiVisibilityScorecard(
        status="NOT_MEASURED",
        measurement_note="Live visibility requires connected search engine credentials. Direct observations not yet recorded.",
        engines_measured=0,
        queries=0,
    )

    return ExecutiveReport(
        report_id="rep_geo_test_001",
        analysis_id="analysis_geo_test_001",
        website_url="https://acme.com",
        domain="acme.com",
        generated_at="October 10, 2026 - 11:30 UTC",
        business_profile=BusinessProfile(business_name="Acme Corp"),
        scores=OverallScoreResult(overall_score=85.0, grade="B", health_label="Good"),
        story_summary="Acme Corp shows excellent semantic crawlability with critical answer comparison gaps.",
        primary_strategic_opportunity="Publish authoritative competitor comparison guides and add ProductOffer schema.",
        consultant_advice_what_to_ignore="Ignore superficial keyword density hacks.",
        three_way_comparison=ThreeWayComparison(
            human_visitor_perspective="Clear value proposition.",
            search_engine_perspective="Clean crawl indexability.",
            ai_answer_engine_perspective="Good entity structure.",
        ),
        findings=[finding_1],
        page_reports=[page_1],
        geo_readiness=geo_readiness,
        ai_visibility_scorecard=visibility_scorecard,
        ai_visibility_score=None,
    )



def test_geo_json_report_covers_all_20_sections():
    report = _make_dummy_geo_report()
    json_data = geo_report_generator.render_json_report(report)

    assert json_data["domain"] == "acme.com"
    assert json_data["analysis_id"] == "analysis_geo_test_001"
    assert json_data["report_type"] == "GEO_MASTER_AUDIT_2026"

    # KPI checks
    kpis = json_data["kpis"]
    assert kpis["extractability_score"] == 86.5
    assert kpis["ai_visibility_status"] == "NOT_MEASURED"
    assert kpis["questions_evaluated"] == 4
    assert kpis["questions_supported"] == 2

    # Check that sections 01 through 20 are present
    sections = json_data["sections"]
    expected_section_keys = [
        "01_executive_summary",
        "02_audit_scope_and_methodology",
        "03_website_and_brand_baseline",
        "04_ai_discoverability_and_crawler_access",
        "05_technical_accessibility_and_content_parity",
        "06_content_extractability_and_answer_readiness",
        "07_entity_and_knowledge_representation",
        "08_information_quality_and_factual_grounding",
        "09_retrieval_simulation_and_relevance_testing",
        "10_live_ai_search_visibility",
        "11_citation_analysis_and_source_attribution",
        "12_answer_accuracy_and_brand_representation",
        "13_competitive_geo_benchmarking",
        "14_query_universe_and_intent_mapping",
        "15_content_gap_and_authority_strategy",
        "16_off_site_sources_and_brand_presence",
        "17_platform_specific_analysis",
        "18_business_impact_and_measurement",
        "19_prioritized_remediation_roadmap",
        "20_appendices_and_evidence_register",
    ]
    for key in expected_section_keys:
        assert key in sections, f"Section '{key}' missing from rendered JSON report."

    # Verify intent mapping
    assert len(sections["14_query_universe_and_intent_mapping"]["intent_stages"]) == 8


def test_geo_html_report_rendering_integrity():
    report = _make_dummy_geo_report()
    html_output = geo_report_generator.render_html_report(report)

    assert "<!DOCTYPE html>" in html_output
    assert "Complete GEO Master Audit &amp; AI Citability Report - acme.com" in html_output or "acme.com" in html_output

    # Verify all 20 section anchor tags exist
    for sec_id, _ in geo_report_generator.SECTIONS:
        assert f'id="{sec_id}"' in html_output, f"Anchor id '{sec_id}' missing in HTML output."
        assert f'href="#{sec_id}"' in html_output, f"Navigation link href='#{sec_id}' missing in sidebar."

    # Verify standardized 14-field GEO finding card
    assert "GEO-VIS-001" in html_output
    assert "Missing Direct Definition Answer Passage" in html_output
    assert "Reference Baseline / Expected Condition" in html_output
    assert "Impact on AI Visibility &amp; Citability" in html_output or "Impact on AI Visibility" in html_output
    assert "Prescriptive GEO Recommendation" in html_output
    assert "Verification Acceptance Criteria" in html_output

    # Verify disclaimers
    assert "Core GEO Architecture Rule" in html_output
    assert "Technical readiness and live AI visibility are strictly separated" in html_output


def test_geo_remediation_csv_export():
    report = _make_dummy_geo_report()
    csv_data = generate_geo_remediation_csv(report)

    assert "Finding ID,Category / Domain" in csv_data
    assert "GEO-VIS-001" in csv_data
    assert "Missing Direct Definition Answer Passage" in csv_data
    assert "AI Search & Growth Team" in csv_data
    assert "Fixed vs Verified" in csv_data


def test_geo_report_fastapi_endpoints():
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock
    from app.main import app
    from app.orchestration.orchestrator import orchestrator

    import uuid
    # Auth cookies are Secure outside DEBUG, so use HTTPS in the test client.
    client = TestClient(app, base_url="https://testserver")
    signup = client.post("/api/v1/auth/signup", json={
        "full_name": "GEO Owner",
        "email": f"geo_{uuid.uuid4().hex[:8]}@example.com",
        "password": "OwnerPass1",
        "organization_name": "GEO Org",
    })
    assert signup.status_code == 200, signup.text
    mock_run = MagicMock()
    mock_run.report = _make_dummy_geo_report()
    mock_run.org_id = signup.json()["user"]["org_id"]
    mock_run.analysis_id = "analysis_geo_test_001"
    mock_run.created_at = "2026-10-10"
    mock_run.domain = "acme.com"
    mock_run.website_url = "https://acme.com"

    original_get_run = orchestrator.get_run
    orchestrator.get_run = MagicMock(return_value=mock_run)

    try:
        # 1. HTML GEO Report
        res_html = client.get("/api/v1/reports/analysis_geo_test_001/geo-report?format=html")
        assert res_html.status_code == 200
        assert "text/html" in res_html.headers["content-type"]
        assert "GEO Master Audit & AI Citability Report" in res_html.text

        # 2. JSON GEO Report
        res_json = client.get("/api/v1/reports/analysis_geo_test_001/geo-report?format=json")
        assert res_json.status_code == 200
        data = res_json.json()
        assert data["report_type"] == "GEO_MASTER_AUDIT_2026"
        assert len(data["sections"]) == 20

        # 3. CSV GEO Remediation Tracker Export
        res_csv = client.get("/api/v1/reports/analysis_geo_test_001/export/geo-remediation-tracker.csv")
        assert res_csv.status_code == 200
        assert "text/csv" in res_csv.headers["content-type"]
        assert "GEO-VIS-001" in res_csv.text
        assert 'filename="acme.com_geo_remediation_tracker.csv"' in res_csv.headers["content-disposition"]
    finally:
        orchestrator.get_run = original_get_run



def test_geo_report_keeps_unmeasured_metrics_and_certification_explicit():
    report = _make_dummy_geo_report()
    data = geo_report_generator.render_json_report(report)

    assert data["certification_status"] == "NOT_ASSESSED"
    assert data["kpis"]["measured_citation_rate"] is None
    citation_section = data["sections"]["11_citation_analysis_and_source_attribution"]
    assert citation_section["distinct_citations_found"] is None
    assert citation_section["citation_count_status"].startswith("NOT_MEASURED")
    accuracy_section = data["sections"]["12_answer_accuracy_and_brand_representation"]
    assert accuracy_section["hallucinations_detected"] is None
    assert accuracy_section["hallucination_status"] == "NOT_ASSESSED"
    crawler_section = data["sections"]["04_ai_discoverability_and_crawler_access"]
    assert crawler_section["ai_bots_audit_status"] == "NOT_ASSESSED"

    html_report = geo_report_generator.render_html_report(report)
    assert "78/100" not in html_report
    assert "0 Critical Brand Hallucinations identified in baseline" not in html_report
    assert "NOT ASSESSED" in html_report
