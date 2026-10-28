"""Representative sampling, grounded query matrix, and repeated live-visibility rates."""
import pytest

from app.crawl.crawler import CrawlerService
from app.domain.enums import Category, EvidenceClass, Severity
from app.domain.models import BusinessProfile, Finding, FindingEvidence, PageEvidence
from app.evidence.taxonomy import assign_evidence_scope
from app.intelligence.geo.adapters.base import BaseGeoEngineAdapter, EngineRawResponse
from app.intelligence.geo.benchmark_generator import benchmark_generator
from app.intelligence.geo.benchmark_runner import benchmark_runner, build_visibility_scorecard
from app.intelligence.geo.readiness import evaluate_geo_readiness
from app.cognition.confidence import CalibratedConfidenceEngine
from app.domain.models import Claim
from app.evidence.store import EvidenceStore


def test_role_order_prefers_commercial_and_pricing_over_blog():
    crawler = CrawlerService()
    urls = [
        "https://example.com/blog/post",
        "https://example.com/pricing",
        "https://example.com/services",
        "https://example.com/",
        "https://example.com/about",
    ]
    ordered = crawler._order_for_roles(urls, crawled_pages=[])
    assert ordered[0].rstrip("/").endswith("example.com")
    assert ordered[1].endswith("/services")
    assert ordered[2].endswith("/pricing")
    assert "/blog/" not in ordered[3]


def test_restaurant_matrix_does_not_invent_a_software_category():
    suite = benchmark_generator.generate_suite(
        domain="example-bistro.com",
        brand_name="Example Bistro",
        industry="Restaurant",
        services=["catering"],
        locations=["Kolkata"],
        mode="comprehensive",
    )
    blob = " ".join(q.query_text for q in suite.queries)
    assert suite.total_queries == 66
    assert suite.matrix_grounding == "profile"
    for banned in ("FastAPI", "PyTorch", "SOC 2", "AI development", "LLM agents"):
        assert banned not in blob


def test_missing_profile_stays_brand_only_and_keeps_concise_coverage():
    suite = benchmark_generator.generate_suite(
        domain="example.com",
        brand_name="Example",
        industry=None,
        services=None,
        mode="concise",
    )
    blob = " ".join(q.query_text for q in suite.queries)
    assert suite.total_queries == 16
    assert suite.matrix_grounding == "brand_only"
    assert suite.matrix_confidence == "low"
    for banned in ("FastAPI", "PyTorch", "SOC 2", "AI development", "Software & Technology"):
        assert banned not in blob


def test_scope_labels_page_sample_and_origin():
    page = Finding(
        finding_id="f1",
        category=Category.ON_PAGE_SEO,
        severity=Severity.MEDIUM,
        title="Missing H1",
        description="The services page has no H1.",
        recommendation="Add an H1.",
        evidence=[FindingEvidence(url="https://example.com/services", selector="h1", element="h1", value="", snippet="")],
        evidence_class=EvidenceClass.OBSERVED,
        evidence_subtype="DOM",
    )
    assign_evidence_scope(page, sample_size=5)
    assert page.evidence_scope == "PAGE_VERIFIED"

    sample = Finding(
        finding_id="f2",
        category=Category.ON_PAGE_SEO,
        severity=Severity.MEDIUM,
        title="Duplicate meta descriptions",
        description="The same description is repeated.",
        recommendation="Write unique descriptions.",
        evidence=[
            FindingEvidence(url="https://example.com/", selector="meta", element="meta", value="", snippet=""),
            FindingEvidence(url="https://example.com/services", selector="meta", element="meta", value="", snippet=""),
        ],
        evidence_class=EvidenceClass.OBSERVED,
        evidence_subtype="DOM",
    )
    assign_evidence_scope(sample, sample_size=5)
    assert sample.evidence_scope == "SAMPLE_VERIFIED"
    assert sample.scope_hit_count == 2
    assert sample.scope_sample_size == 5

    header = Finding(
        finding_id="f3",
        category=Category.TECHNICAL_SEO,
        severity=Severity.HIGH,
        title="Missing CSP",
        description="Content-Security-Policy is absent on the origin response.",
        recommendation="Set a Content-Security-Policy header.",
        evidence=[FindingEvidence(url="https://example.com/", selector="header", element="header", value="", snippet="")],
        evidence_class=EvidenceClass.OBSERVED,
        evidence_subtype="HEADERS",
    )
    assign_evidence_scope(header, sample_size=5)
    assert header.evidence_scope == "ORIGIN_VERIFIED"


def test_five_page_sample_is_not_treated_as_the_whole_site():
    engine = CalibratedConfidenceEngine()
    store = EvidenceStore("scope_run")
    ev = store.add_evidence("meta", "meta_analyzer", url="https://test.com", selector="title", value="Home")
    claims = [Claim(id="cl", agent_id="deterministic_01", statement="Title present", category=Category.TECHNICAL_SEO, evidence_refs=[ev.id])]
    pages = [PageEvidence(url=f"https://test.com/p{i}") for i in range(5)]
    result = engine.calculate_confidence(claims, store, pages, index_url_count=100)
    assert result.evidence_coverage == 1.0
    assert result.index_coverage == 0.05
    assert "not sitewide" in result.summary


def test_live_visibility_uses_the_measured_rate_not_a_placeholder():
    pages = [PageEvidence(url="https://acme.com/", title="Acme", h1=["Acme"], body_text="Acme sells catering.")]
    measured = evaluate_geo_readiness(
        website_url="https://acme.com/",
        pages=pages,
        profile=BusinessProfile(business_name="Acme"),
        visibility_measured=True,
        visibility_score=42,
        visibility_detail="Live citation rate 42.",
    )
    dim = measured.dimension_scores["ai_engine_visibility"]
    assert dim.is_measured is True
    assert dim.score == 42.0

    missing = evaluate_geo_readiness(
        website_url="https://acme.com/",
        pages=pages,
        profile=BusinessProfile(business_name="Acme"),
        visibility_measured=True,
        visibility_score=None,
    )
    unmeasured = missing.dimension_scores["ai_engine_visibility"]
    assert unmeasured.is_measured is False
    assert unmeasured.score != 75.0


class SequenceAdapter(BaseGeoEngineAdapter):
    engine_id = "seq"
    display_name = "Sequence"
    default_model = "seq-1"

    def __init__(self):
        super().__init__(api_key="k")
        self.outputs = [
            "AlienHouse Networks is a caterer.",
            "AlienHouse Networks serves the city.",
            "Another company was recommended instead.",
        ]
        self.calls = 0

    async def execute_query(self, prompt: str, locale: str = "en-US", client=None) -> EngineRawResponse:
        text = self.outputs[self.calls % len(self.outputs)]
        self.calls += 1
        return EngineRawResponse(
            engine_id=self.engine_id,
            engine_name=self.display_name,
            model_version=self.default_model,
            raw_content=text,
            citations=[],
            status_code=200,
            latency_ms=10,
            is_live=True,
        )


class TimeoutThenMentionAdapter(BaseGeoEngineAdapter):
    engine_id = "timeout_engine"
    display_name = "Timeout Engine"
    default_model = "t-1"

    def __init__(self):
        super().__init__(api_key="k")
        self.calls = 0

    async def execute_query(self, prompt: str, locale: str = "en-US", client=None) -> EngineRawResponse:
        self.calls += 1
        if self.calls == 1:
            return EngineRawResponse(
                engine_id=self.engine_id,
                engine_name=self.display_name,
                model_version=self.default_model,
                raw_content="",
                citations=[],
                status_code=504,
                error="Timeout after 18s",
                latency_ms=18000,
            )
        return EngineRawResponse(
            engine_id=self.engine_id,
            engine_name=self.display_name,
            model_version=self.default_model,
            raw_content="AlienHouse Networks was mentioned.",
            citations=["https://alienhouse.ai/"],
            status_code=200,
            latency_ms=20,
            is_live=True,
        )


@pytest.mark.asyncio
async def test_repeated_runs_mention_rate_excludes_timeouts(monkeypatch):
    adapter = SequenceAdapter()
    monkeypatch.setattr(
        "app.intelligence.geo.benchmark_runner.get_adapter",
        lambda engine_id: adapter,
    )
    report = await benchmark_runner.execute_benchmark(
        domain="alienhouse.ai",
        brand_name="AlienHouse Networks",
        services=["catering"],
        mode="concise",
        repeats=3,
        max_queries=1,
        engines=["seq"],
    )
    assert len(report.evaluations) == 3
    assert report.engine_aggregates["seq"].queries_succeeded == 3
    assert report.engine_aggregates["seq"].mention_count == 2
    assert report.overall_mention_rate_pct == 66.7

    card = build_visibility_scorecard(report, services=["catering"])
    assert card.status == "MEASURED"
    assert card.mention_rate_pct == 66.7
    assert card.citation_accuracy_pct is None
    assert card.hallucination_rate_pct in (None, 0.0)

    timeout_adapter = TimeoutThenMentionAdapter()
    monkeypatch.setattr(
        "app.intelligence.geo.benchmark_runner.get_adapter",
        lambda engine_id: timeout_adapter,
    )
    timed = await benchmark_runner.execute_benchmark(
        domain="alienhouse.ai",
        brand_name="AlienHouse Networks",
        mode="concise",
        repeats=2,
        max_queries=1,
        engines=["timeout_engine"],
    )
    assert timed.failed_runs == 1
    assert timed.overall_mention_rate_pct == 100.0
    assert timed.engine_aggregates["timeout_engine"].mention_count == 1
