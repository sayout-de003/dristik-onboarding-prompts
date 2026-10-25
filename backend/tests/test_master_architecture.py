"""
Dristik AI Master Architecture Integration Tests
Validates the 35-capability taxonomy, Evidence Graph, Dynamic Worker Pool,
and Adaptive Information-Gain Planner.
"""
import pytest
from app.domain.capability import CAPABILITY_REGISTRY, CapabilityDomain, ExecutionTier, get_capability
from app.evidence.graph import EvidenceGraph, GraphNodeType, GraphEdgeType
from app.orchestration.planner import AdaptiveMissionPlanner
from app.orchestration.capability_router import CapabilityRouter
from app.orchestration.dynamic_team import DynamicTeamBuilder
from app.inference.model_router import ModelRouter
from app.cognition.blackboard import CognitiveBlackboard
from app.domain.models import CrawlManifest, PageEvidence

def test_35_capability_taxonomy_registry():
    assert len(CAPABILITY_REGISTRY) == 35
    
    # Check domain representation
    domains = {cap.domain for cap in CAPABILITY_REGISTRY.values()}
    assert CapabilityDomain.TECHNICAL in domains
    assert CapabilityDomain.STRUCTURED_DATA in domains
    assert CapabilityDomain.BUSINESS in domains
    assert CapabilityDomain.CONTENT in domains
    assert CapabilityDomain.GEO in domains
    assert CapabilityDomain.AI_SEARCH in domains
    assert CapabilityDomain.EXPERIENCE in domains
    assert CapabilityDomain.VERIFICATION in domains

    # Check deterministic vs cognitive tiers
    deterministic_caps = [c for c in CAPABILITY_REGISTRY.values() if c.tier == ExecutionTier.TIER_A_DETERMINISTIC]
    assert len(deterministic_caps) >= 10

def test_evidence_graph_nodes_and_contradictions():
    graph = EvidenceGraph(run_id="test_run_001")
    
    # Add page and elements
    graph.add_node("page_0", GraphNodeType.PAGE, "Homepage", url="https://example.com")
    graph.add_node("elem_h1", GraphNodeType.ELEMENT, "H1: Enterprise Platform", url="https://example.com")
    graph.add_edge("page_0", "elem_h1", GraphEdgeType.CONTAINS_ELEMENT)
    
    # Add contradictory claims
    graph.add_node("claim_1", GraphNodeType.CLAIM, "Targets Fortune 500 Enterprises")
    graph.add_node("claim_2", GraphNodeType.CLAIM, "Self-Serve SMB $19/mo Only")
    graph.add_edge("claim_1", "claim_2", GraphEdgeType.CONTRADICTS_CLAIM, metadata={"reason": "Pricing vs positioning mismatch"})

    assert len(graph.nodes) == 4
    assert len(graph.edges) == 2
    
    contradictions = graph.get_contradictions()
    assert len(contradictions) == 1
    assert contradictions[0]["reason"] == "Pricing vs positioning mismatch"

@pytest.mark.asyncio
async def test_dynamic_team_builder_and_planner():
    planner = AdaptiveMissionPlanner()
    model_router = ModelRouter()
    team_builder = DynamicTeamBuilder(model_router)
    blackboard = CognitiveBlackboard(run_id="test_run_002", website_url="https://example.com")
    
    manifest = CrawlManifest(
        domain="example.com",
        base_url="https://example.com",
        total_pages_discovered=1,
        pages=[PageEvidence(url="https://example.com", title="Example Enterprise", h1=["Example Platform"])],
        sitemap_found=True,
        robots_txt_found=True,
        crawl_health={"missing_h1_count": 0, "broken_links_count": 0}
    )
    
    mission_plan = planner.plan_mission(manifest)
    assert mission_plan["total_capabilities"] == 35
    assert len(mission_plan["tier_1_deterministic"]) > 0

    # Execute deterministic suite
    det_results = await team_builder.execute_team_capabilities(mission_plan["tier_1_deterministic"], manifest, blackboard)
    assert len(det_results) > 0

def test_35_specialist_agents_registry():
    from app.agents.runtime.registry import SPECIALIST_AGENTS_V3, AGENT_REGISTRY, list_all_specialists
    specialists = list_all_specialists()
    assert len(specialists) == len(SPECIALIST_AGENTS_V3)
    assert len(SPECIALIST_AGENTS_V3) >= 50

    # Check key agents from each domain
    assert "business.discovery.v3" in SPECIALIST_AGENTS_V3
    assert "business.semantic_strategist.v3" in SPECIALIST_AGENTS_V3
    assert "seo.crawl.v3" in SPECIALIST_AGENTS_V3
    assert "seo.performance.v3" in SPECIALIST_AGENTS_V3
    assert "schema.validation.v3" in SPECIALIST_AGENTS_V3
    assert "content.depth.v3" in SPECIALIST_AGENTS_V3
    assert "geo.information_gain.v3" in SPECIALIST_AGENTS_V3
    assert "ai_search.chatgpt.v3" in SPECIALIST_AGENTS_V3
    assert "ux.experience.v3" in SPECIALIST_AGENTS_V3
    assert "verification.adversarial.v3" in SPECIALIST_AGENTS_V3
    assert "strategy.executive.v3" in SPECIALIST_AGENTS_V3

    # Check worker types
    valid_workers = {"analyst_worker", "research_worker", "extractor_worker", "critic_worker", "verifier_worker", "strategist_worker", "remediation_worker", "synthesizer_worker"}
    for agent in specialists:
        assert agent.worker_type in valid_workers
        assert agent.token_budget > 0
        assert len(agent.capabilities) > 0

def test_claim_state_machine_and_evidence_hierarchy():
    from app.domain.enums import EvidenceLevel, ClaimState, VerificationStatus, Category
    from app.cognition.claims import ClaimRegistry

    registry = ClaimRegistry(run_id="test_state_machine_001")
    claim = registry.register_claim(
        agent_id="seo.indexability.v3",
        statement="Homepage has noindex meta directive",
        category=Category.TECHNICAL_SEO,
        evidence_level=EvidenceLevel.E4_FIRST_PARTY_DOM,
        evidence_refs=["EV-001"]
    )
    assert claim.claim_state == ClaimState.CREATED
    assert claim.evidence_level == EvidenceLevel.E4_FIRST_PARTY_DOM

    # Advance state to ADVERSARIAL_REVIEW then VERIFIED
    updated = registry.advance_claim_state(
        claim_id=claim.id,
        new_state=ClaimState.ADVERSARIAL_REVIEW
    )
    assert updated.claim_state == ClaimState.ADVERSARIAL_REVIEW

    finalized = registry.advance_claim_state(
        claim_id=claim.id,
        new_state=ClaimState.VERIFIED,
        new_status=VerificationStatus.VERIFIED,
        notes="Corroborated by raw DOM meta tag",
        adjusted_confidence=0.99
    )
    assert finalized.claim_state == ClaimState.VERIFIED
    assert finalized.verification_status == VerificationStatus.VERIFIED
    assert finalized.confidence == 0.99

