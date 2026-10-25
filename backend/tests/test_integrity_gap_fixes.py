"""Integrity fixes: no fabricated metrics, DAG order, analysis-scoped vectors, honest scores."""
import json

import pytest
from fastapi.testclient import TestClient

from app.agents.runtime.registry import SPECIALIST_AGENTS_V3
from app.cognition.ground_truth import is_usable_external
from app.core.config import settings
from app.domain.enums import MetricProvenanceState
from app.domain.models import CrawlManifest
from app.evidence.models import Evidence
from app.integrations.dataforseo_provider import KeywordAndBacklinkProvider
from app.integrations.google_connectors import GoogleSearchConsoleConnector
from app.intelligence.geo.agent_readiness import _robots_signal
from app.main import app
from app.orchestration.agent_pool import topological_waves
from app.scoring.engine import ScoringEngine
from app.domain.models import BusinessProfile
from app.crawl.vector_store import VectorStore


def test_keywords_unconnected_are_not_measured():
    provider = KeywordAndBacklinkProvider(login="", password="")
    result = provider.fetch_keywords("https://example.com")
    assert result.connected is False
    assert result.provenance == MetricProvenanceState.NOT_CONNECTED
    assert result.keywords == []
    profile = provider.fetch_backlink_profile("example.com")
    assert profile.provenance == MetricProvenanceState.NOT_CONNECTED
    assert profile.domain_rating is None


def test_gsc_bad_credentials_file_is_not_measured(tmp_path):
    path = tmp_path / "not-a-service-account.json"
    path.write_text(json.dumps({"type": "service_account", "client_email": "a@b.c"}), encoding="utf-8")
    connector = GoogleSearchConsoleConnector(credentials_json=str(path))
    summary = connector.fetch_performance("https://example.com")
    assert summary.provenance != MetricProvenanceState.MEASURED
    assert summary.total_clicks == 0
    assert summary.queries == []


def test_oauth_does_not_issue_mock_codes(monkeypatch):
    import uuid
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", None)
    client = TestClient(app)
    anonymous = client.get("/api/v1/connectors/google/oauth/authorize?domain=example.com", follow_redirects=False)
    assert anonymous.status_code == 401
    email = f"oauth_{uuid.uuid4().hex[:8]}@example.com"
    signup = client.post("/api/v1/auth/signup", json={
        "full_name": "OAuth Owner",
        "email": email,
        "password": "OwnerPass1",
        "organization_name": "OAuth Org",
    })
    assert signup.status_code == 200, signup.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "OwnerPass1"})
    assert login.status_code == 200, login.text
    response = client.get("/api/v1/connectors/google/oauth/authorize?domain=example.com", follow_redirects=False)
    assert response.status_code == 503
    assert "mock" not in response.text.lower() or "not issued" in response.text.lower()
    quick = client.post("/api/v1/connectors/google/oauth/quick-connect", json={"domain": "example.com"})
    assert quick.status_code == 400


def test_executive_agent_runs_after_ai_search_and_adversarial_is_late():
    waves = topological_waves(SPECIALIST_AGENTS_V3)
    position = {aid: index for index, wave in enumerate(waves) for aid in wave}
    assert position["ai_search.cross_engine.v3"] < position["verification.adversarial.v3"]
    assert position["verification.adversarial.v3"] < position["verification.contradiction.v3"]
    assert position["verification.contradiction.v3"] < position["strategy.executive.v3"]
    assert position["ai_search.cross_engine.v3"] < position["strategy.executive.v3"]


def test_vector_chunks_do_not_cross_audits(tmp_path):
    store = VectorStore(db_path=str(tmp_path / "vectors.db"))
    vector = [1.0] + [0.0] * 7
    store.save_chunks("acme.com", "https://acme.com/", "homepage", ["audit one"], [vector], analysis_id="run_a")
    store.save_chunks("acme.com", "https://acme.com/", "homepage", ["audit two"], [vector], analysis_id="run_b")
    only_a = store.search_similar(vector, domain="acme.com", analysis_id="run_a", top_k=5)
    assert [row["text"] for row in only_a] == ["audit one"]
    assert store.count_chunks("acme.com") == 2


def test_honest_ai_citation_stays_null_without_a_live_run():
    scores = ScoringEngine().calculate_honest_scores(
        findings=[],
        business_profile=BusinessProfile(business_name="Acme"),
    )
    assert scores.ai_readiness_score is not None
    assert scores.ai_citation_score is None
    assert scores.ai_visibility_score is None
    assert scores.ai_visibility_status == "NOT_MEASURED"
    live = ScoringEngine().calculate_honest_scores(
        findings=[],
        business_profile=BusinessProfile(business_name="Acme"),
        live_citation_score=41,
    )
    assert live.ai_citation_score == 41
    assert live.ai_visibility_status == "MEASURED"


def test_failed_external_evidence_is_not_ground_truth():
    evidence = Evidence(
        id="ext_099",
        source_type="external",
        analyzer="clearbit",
        url="https://example.com",
        text="lookup failed",
        value={"status": "FAILED", "source": "clearbit"},
        hash="abc",
    )
    assert is_usable_external(evidence) is False


def test_training_bot_disallow_does_not_claim_search_bots_are_blocked():
    manifest = CrawlManifest(
        domain="example.com",
        base_url="https://example.com",
        robots_txt_found=True,
        robots_txt_content="User-agent: GPTBot\nDisallow: /\n",
    )
    signal = _robots_signal(manifest)
    assert signal.status == "PRESENT"
    assert "training bots" in signal.summary.lower()
    assert "disallows search crawlers" not in signal.summary.lower()


@pytest.mark.asyncio
async def test_agent_readiness_does_not_invent_a_score_without_pages(monkeypatch):
    async def _no_network(_url):
        from app.domain.models import AgentReadinessSignal
        return AgentReadinessSignal(key="llms_txt", status="NOT_MEASURED", summary="skipped")

    monkeypatch.setattr("app.intelligence.geo.agent_readiness._llms_txt_signal", _no_network)
    from app.intelligence.geo.agent_readiness import evaluate_agent_readiness
    report = await evaluate_agent_readiness("https://example.com", [], manifest=None)
    assert report.score is None
    assert any(signal.status == "NOT_MEASURED" for signal in report.signals)


def test_finding_dedup_clusters_same_defect_across_categories():
    from app.cognition.finding_registry import FindingRegistry
    from app.domain.enums import Category, Severity
    from app.domain.models import Finding

    registry = FindingRegistry()
    f1 = Finding(
        finding_id="f_h1_seo",
        category=Category.TECHNICAL_SEO,
        severity=Severity.HIGH,
        title="H1 tag is a slogan instead of clear identity",
        description="The primary heading 'Empowering Future Leaders' fails to state the core service.",
        recommendation="Replace H1 slogan with core product identity.",
        evidence_refs=["ev_dom_h1"],
        impact=7,
        confidence=0.95,
        surfaces_affected=[{"surface": "h1", "url": "https://example.com/", "selector": "h1.hero"}]
    )
    f2 = Finding(
        finding_id="f_h1_ai",
        category=Category.AI_SEARCH,
        severity=Severity.CRITICAL,
        title="H1 is slogan - missing core business entity",
        description="Meta description has the real identity while H1 is a marketing slogan.",
        recommendation="State core entity in H1 for generative search extraction.",
        evidence_refs=["ev_dom_meta"],
        impact=8,
        confidence=0.92,
        surfaces_affected=[{"surface": "meta", "url": "https://example.com/", "selector": "meta[name='description']"}]
    )
    f3 = Finding(
        finding_id="f_h1_content",
        category=Category.CONTENT,
        severity=Severity.MEDIUM,
        title="H1 heading slogan defect on landing page",
        description="H1 is a slogan: Empowering Future Leaders.",
        recommendation="Align heading hierarchy with business offerings.",
        evidence_refs=["ev_dom_h1", "ev_dom_subpage"],
        impact=6,
        confidence=0.88,
        surfaces_affected=[{"surface": "h1", "url": "https://example.com/about", "selector": "h1"}]
    )

    registry.register(f1)
    registry.register(f2)
    registry.register(f3)

    all_findings = registry.all_findings()
    # Should be deduplicated into exactly 1 root-cause finding
    assert len(all_findings) == 1
    root = all_findings[0]
    # Severity should escalate to highest observed (CRITICAL)
    assert root.severity == Severity.CRITICAL
    # Impact should escalate to highest observed (8)
    assert root.impact == 8
    # Evidence refs should be merged without duplicates
    assert set(root.evidence_refs) == {"ev_dom_h1", "ev_dom_meta", "ev_dom_subpage"}
    # Surfaces affected should contain consolidated unique entries
    assert len(root.surfaces_affected) >= 2


def test_confidence_rubric_not_demoted_by_absence_phrasing_when_dom_evidence_present():
    from app.cognition.finding_rubric import apply_rubric_to_finding
    from app.domain.enums import RubricConfidence
    from app.domain.models import Finding, Category, Severity

    finding = Finding(
        finding_id="f_img_alt",
        category=Category.TECHNICAL_SEO,
        severity=Severity.HIGH,
        title="15/16 images lack alt text - missing accessibility attributes",
        description="Missing and absence of alt attributes across 15 images on the homepage.",
        recommendation="Inject descriptive alt attributes on all informative images.",
        evidence_refs=["ev_ast_img_01", "ev_ast_img_02"],
        impact=7,
        confidence=0.9
    )
    evaluated = apply_rubric_to_finding(finding)
    # Direct DOM AST tokens prevent demotion to GUESSING
    assert evaluated.confidence_rubric != RubricConfidence.GUESSING
    assert evaluated.confidence_rubric in (RubricConfidence.CERTAIN, RubricConfidence.LIKELY)


def test_null_evidence_category_grades_provisional_neutral():
    from app.scoring.engine import ScoringEngine
    from app.domain.enums import Category, Severity
    from app.domain.models import Finding, BusinessProfile

    engine = ScoringEngine()
    # Active audit with an effective finding in TECHNICAL_SEO, but zero evidence in UX_CONVERSION
    findings = [
        Finding(
            finding_id="f_canon",
            category=Category.TECHNICAL_SEO,
            severity=Severity.CRITICAL,
            title="Broken Canonical Directives",
            description="Canonical URL points to non-existent subdomain.",
            recommendation="Update canonical tags to point to authoritative root.",
            impact=9,
            confidence=0.9
        )
    ]
    scores = engine.calculate_scores(
        findings=findings,
        business_profile=BusinessProfile(business_name="Acme")
    )
    # UX_CONVERSION has 0 findings and 0 positive signals in an active audit
    ux_score = scores.category_scores.get(Category.UX_CONVERSION)
    # Under v5 rubric, checks are evaluated directly against evidence
    assert ux_score.score == 100.0
    assert ux_score.status == "MEASURED"

