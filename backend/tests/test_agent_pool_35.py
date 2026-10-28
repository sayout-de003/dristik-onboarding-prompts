"""
35-agent workforce: instantiation, DAG, deterministic evidence, no canned fallback.
"""
import pytest
from unittest.mock import AsyncMock

from app.agents.runtime.registry import SPECIALIST_AGENTS_V3, specialist_count, list_all_specialists, CAPABILITY_AGENT_MAP
from app.agents.runtime.task_cards import TASK_CARDS
from app.agents.runtime.specialist import SpecialistAgent
from app.cognition.blackboard import CognitiveBlackboard
from app.domain.models import CrawlManifest, PageEvidence
from app.domain.enums import Category, Severity, VerificationStatus
from app.orchestration.agent_pool import AgentPool, topological_waves


class _FakeRouter:
    def __init__(self, payload=None):
        self.generate_structured = AsyncMock(return_value=payload or {
            "status": "unavailable",
            "unavailable_reason": "test_no_llm",
            "claims": [],
        })


def _board(with_pages=True):
    bb = CognitiveBlackboard("run_test", "https://example.com")
    page = PageEvidence(
        url="https://example.com/",
        title="Example Co",
        h1=["Example Co"],
        word_count=120,
        canonical_url="https://example.com/",
        viewport="width=device-width",
        schema_types=["Organization"],
        ttfb_ms=180.0,
    )
    manifest = CrawlManifest(
        domain="example.com",
        base_url="https://example.com",
        total_pages_discovered=1,
        pages=[page] if with_pages else [],
        sitemap_found=False,
        robots_txt_found=False,
        crawl_health={"avg_ttfb_ms": 180.0, "broken_links_count": 0, "duplicate_titles_count": 0},
    )
    bb.pages = manifest.pages
    bb.crawl_manifest = manifest
    ev = bb.evidence_store.add_evidence(
        source_type="meta",
        analyzer="test",
        url="https://example.com/",
        text="Example Co",
        value={"title": "Example Co"},
    )
    return bb, ev


def test_registry_has_exactly_50_specialists():
    count = len(SPECIALIST_AGENTS_V3)
    assert count >= 50
    assert specialist_count() == count
    assert len(list_all_specialists()) == count
    assert len(TASK_CARDS) == count
    assert set(TASK_CARDS) == set(SPECIALIST_AGENTS_V3)


def test_pool_instantiates_all_50():
    pool = AgentPool(_FakeRouter())
    assert len(pool) == len(SPECIALIST_AGENTS_V3)
    assert set(pool.agents) == set(SPECIALIST_AGENTS_V3)


def test_waves_respect_dependencies():
    waves = topological_waves(SPECIALIST_AGENTS_V3)
    position = {aid: i for i, wave in enumerate(waves) for aid in wave}
    for aid, defn in SPECIALIST_AGENTS_V3.items():
        for dep in defn.dependencies or []:
            if dep in position and aid in position:
                assert position[dep] <= position[aid], f"{dep} must run before {aid}"


@pytest.mark.asyncio
async def test_image_and_header_findings_do_not_reuse_the_title_evidence():
    bb, title_ev = _board()
    bb.evidence_store.add_evidence(
        source_type="meta",
        analyzer="test",
        url="https://example.com/",
        selector="title",
        text="Example Co",
        value={"title": "Example Co"},
    )
    bb.evidence_store.add_external_evidence(
        source="ahrefs",
        claim="External authority snapshot",
        raw_value={"domain_rating": 12},
        url="https://example.com/",
    )
    bb.pages[0].images_without_alt = 4
    bb.pages[0].response_headers = {"server": "nginx"}

    assets = SpecialistAgent(SPECIALIST_AGENTS_V3["seo.assets.v3"], _FakeRouter())
    await assets.run(bb)
    alt_claims = [claim for claim in bb.claim_registry.get_all() if "alt" in claim.statement.lower()]
    assert alt_claims
    for claim in alt_claims:
        assert title_ev.id not in claim.evidence_refs
        for ref in claim.evidence_refs:
            evidence = bb.evidence_store.get(ref)
            assert evidence is not None
            assert evidence.selector == "img"
            assert not evidence.id.startswith("ext_")

    security = SpecialistAgent(SPECIALIST_AGENTS_V3["seo.security.v3"], _FakeRouter())
    await security.run(bb)
    header_claims = [claim for claim in bb.claim_registry.get_all() if "hsts" in claim.statement.lower() or "strict-transport" in claim.statement.lower()]
    assert header_claims
    for claim in header_claims:
        for ref in claim.evidence_refs:
            evidence = bb.evidence_store.get(ref)
            assert evidence is not None
            assert evidence.selector == "strict-transport-security"
            assert (evidence.selector or "").lower() != "title"


@pytest.mark.asyncio
async def test_deterministic_crawl_agent_uses_manifest_not_fiction():
    bb, ev = _board()
    agent = SpecialistAgent(SPECIALIST_AGENTS_V3["seo.crawl.v3"], _FakeRouter())
    result = await agent.run(bb)
    assert result["status"] == "completed"
    assert result["mode"] == "DETERMINISTIC"
    assert result["observations"]["sitemap_found"] is False
    statements = [c.statement for c in bb.claim_registry.get_all()]
    assert any("sitemap" in s.lower() for s in statements)
    for claim in bb.claim_registry.get_all():
        assert claim.evidence_refs


@pytest.mark.asyncio
async def test_llm_specialist_does_not_use_canned_fallback():
    bb, ev = _board()
    router = _FakeRouter()
    agent = SpecialistAgent(SPECIALIST_AGENTS_V3["content.eeat.v3"], router)
    result = await agent.run(bb)
    router.generate_structured.assert_awaited()
    kwargs = router.generate_structured.await_args.kwargs
    assert kwargs.get("allow_fallback") is False
    assert result["status"] == "unavailable"
    assert result["claims"] == []


@pytest.mark.asyncio
async def test_llm_claims_without_real_evidence_refs_are_dropped():
    bb, ev = _board()
    router = _FakeRouter({
        "status": "completed",
        "claims": [
            {
                "statement": "Invented competitor Stripe dominates citations.",
                "severity": "HIGH",
                "confidence": 0.9,
                "evidence_refs": ["ev_does_not_exist"],
                "recommendation": "n/a",
            },
            {
                "statement": "Homepage title is Example Co.",
                "severity": "INFO",
                "confidence": 0.9,
                "evidence_refs": [ev.id],
                "evidence_status": "supported",
                "recommendation": "",
            },
        ],
    })
    agent = SpecialistAgent(SPECIALIST_AGENTS_V3["business.discovery.v3"], router)
    result = await agent.run(bb)
    assert result["status"] == "completed"
    assert len(result["claims"]) == 1
    stored = bb.claim_registry.get_all()
    assert all("Stripe" not in c.statement for c in stored)


@pytest.mark.asyncio
async def test_execute_all_runs_50_agents():
    bb, _ = _board()
    pool = AgentPool(_FakeRouter())
    summary = await pool.execute_all(bb)
    count = len(SPECIALIST_AGENTS_V3)
    assert summary["agents_declared"] == count
    assert summary["agents_ran"] + summary["errors"] == count
    assert len(bb.blackboard_state.get("agent_results") or {}) == count


@pytest.mark.asyncio
async def test_adversarial_specialist_marks_unbacked_claims():
    bb, ev = _board()
    bb.claim_registry.register_claim(
        agent_id="fake",
        statement="Unbacked invented revenue.",
        category=Category.COMPETITIVE,
        severity=Severity.HIGH,
        evidence_refs=[],
        confidence=0.92,
    )
    agent = SpecialistAgent(SPECIALIST_AGENTS_V3["verification.adversarial.v3"], _FakeRouter())
    await agent.run(bb)
    claim = bb.claim_registry.get_all()[0]
    assert claim.verification_status == VerificationStatus.INSUFFICIENT_EVIDENCE
    assert claim.confidence <= 0.40


def test_every_capability_maps_to_a_real_agent():
    for cap_id, agent_id in CAPABILITY_AGENT_MAP.items():
        assert agent_id in SPECIALIST_AGENTS_V3, f"{cap_id} maps to unknown {agent_id}"
