"""
Tests for the 5 specialized copywriting agents and section-wise page copy intelligence.
"""
import pytest
from app.orchestration.runtime.registry import (
    COPYWRITING_AGENTS_V3,
    AGENT_REGISTRY,
    list_copywriting_specialists,
    get_agent_definition,
)
from app.orchestration.runtime.task_cards import ALL_TASK_CARDS, task_card_for
from app.domain.models import BusinessProfile, PageEvidence, PageSeoAudit
from app.crawl.page_intelligence import fallback_copy_audit, _fallback_suggested


def test_5_copywriting_agents_registered():
    specialists = list_copywriting_specialists()
    assert len(specialists) == 5
    expected_ids = {
        "copywriting.seo.v3",
        "copywriting.geo.v3",
        "copywriting.cro.v3",
        "copywriting.clarity.v3",
        "copywriting.section.v3",
    }
    assert set(COPYWRITING_AGENTS_V3.keys()) == expected_ids
    for aid in expected_ids:
        defn = get_agent_definition(aid)
        assert defn is not None
        assert defn.domain == "COPYWRITING"
        assert defn.worker_type == "analyst_worker"
        assert len(defn.capabilities) >= 2
        assert len(defn.required_evidence) >= 2


def test_copywriting_task_cards_present():
    for aid in [
        "copywriting.seo.v3",
        "copywriting.geo.v3",
        "copywriting.cro.v3",
        "copywriting.clarity.v3",
        "copywriting.section.v3",
    ]:
        card = task_card_for(aid)
        assert card != "Audit only what the evidence pack contains. Cite [ev_xxx]. Invent nothing."
        assert len(card) > 50


def test_page_intelligence_generates_sections_and_faqs():
    page = PageEvidence(
        url="https://acme-analytics.io/",
        page_type="homepage",
        title="Acme Analytics — Unified Data Platform",
        meta_description="Acme Analytics provides enterprise data intelligence and real-time observability.",
        h1=["Unified Data Platform for Modern Engineering Teams"],
        h2=["Automated Data Pipelines", "Real-Time Observability", "Enterprise Governance"],
        ctas=["Start Free Trial", "Book a Demo"],
        word_count=320,
        readability_score=68.0,
    )
    profile = BusinessProfile(
        business_name="Acme Analytics",
        value_proposition="Real-time data intelligence and automated pipeline observability",
        target_audience="VP of Engineering & Data Platform Leads",
        primary_intent="saas",
    )
    seo = PageSeoAudit(score=82.0)

    audit = fallback_copy_audit(page, profile, seo)
    assert audit.score > 0
    assert audit.geo_score > 0
    assert audit.seo_score == 82.0

    # Specialist insights
    assert "seo" in audit.specialist_insights
    assert "geo" in audit.specialist_insights
    assert "cro" in audit.specialist_insights
    assert "clarity" in audit.specialist_insights
    assert "sections" in audit.specialist_insights

    # Suggested copy sections
    sug = audit.suggested
    assert len(sug.sections) >= 4
    section_ids = [s.section_id for s in sug.sections]
    assert "hero" in section_ids
    assert "problem" in section_ids
    assert "solution" in section_ids
    assert "geo_faq" in section_ids
    assert "cta_banner" in section_ids

    # GEO extractable snippet
    assert sug.geo_snippet
    assert "Acme Analytics" in sug.geo_snippet

    # FAQ items for AI Answer Engines
    assert len(sug.faq_items) >= 2
    for faq in sug.faq_items:
        assert faq.question
        assert faq.answer
        assert faq.target_engine

    # Evidence-only: do not invent a generic pain story or fake implementation SLA
    blob = " ".join(
        [sug.geo_snippet or "", sug.notes or ""]
        + [s.suggested_copy for s in sug.sections]
        + [f.answer for f in sug.faq_items]
    ).lower()
    assert "fragmented tooling" not in blob
    assert "under 15 minutes" not in blob
    assert "enterprise intelligence platform" not in blob
    problem = next(s for s in sug.sections if s.section_id == "problem")
    assert "NOT_IN_EVIDENCE" in problem.suggested_copy or "NOT_IN_EVIDENCE" in (problem.current_preview or "")
    assert sug.primary_cta == "Start Free Trial"



def test_copywriting_agents_receive_cross_domain_and_trend_policy():
    """All copy specialists must use evidence-backed trends and page-level change decisions."""
    for agent_id in COPYWRITING_AGENTS_V3:
        prompt = task_card_for(agent_id)
        assert "CROSS-DOMAIN CONTEXT AND KEYWORD FRESHNESS" in prompt
        assert "NO_CHANGE_NEEDED" in prompt
        assert "INSUFFICIENT_EVIDENCE" in prompt
        assert "never invent search volume" in prompt.lower()
        assert "page-by-page" in prompt.lower()


def test_non_copywriting_agents_do_not_receive_copywriting_policy():
    prompt = task_card_for("business.discovery.v3")
    assert "CROSS-DOMAIN CONTEXT AND KEYWORD FRESHNESS" not in prompt
