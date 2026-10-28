"""
Tests for Zero Fake Data, Evidence-First Truth, and Fail-Closed Production Hardening.
Verifies that all analytical systems return machine-readable capability states,
nullable scores when unmeasured, and refuse to simulate or fabricate results.
"""
import pytest
from app.capabilities.registry import capability_registry, CapabilityDeclaration
from app.domain.enums import CapabilityStatus, VerificationStatus, PatchRiskLevel, ConnectorHealthStatus
from app.domain.models import RemediationPatch, Finding, Category, Severity, BusinessProfile
from app.inference.fallback import DeterministicFallbackEngine
from app.inference.schemas.compat import legacy_adapt
from app.verification.verifier import VerificationEngine
from app.intelligence.citations.tracker import AiCitationTracker
from app.intelligence.competitive.bakeoff import CommercialBakeoffEngine
from app.connectors.base.models import ConnectorCredentials
from app.connectors.github.client import GitHubClient
from app.connectors.shopify.connector import ShopifyConnector
from app.connectors.webflow.connector import WebflowConnector
from app.core.config import settings
from app.tenancy.agency import AgencyManager


def test_capabilities_registry_definitions():
    """Ensure capability declarations are registered and inspectable."""
    assert capability_registry.is_declared("live_ai_citations")
    assert capability_registry.is_declared("commercial_bakeoff")
    assert capability_registry.is_declared("patch_verification")

    decl = capability_registry.get("live_ai_citations")
    assert decl is not None
    assert decl.required_connector == "search_ai_provider"


def test_heuristic_fallback_audit_fail_closed():
    """Fallback audit must not invent scores, brand names, or fake citation probabilities."""
    engine = DeterministicFallbackEngine()
    # 1. Business capability fallback
    biz = engine.execute_fallback("business_intelligence", [])
    assert biz["business_name"] == "Unknown Brand"
    assert biz["services"] == []
    assert biz["primary_cta"] is None

    # 2. GEO capability fallback
    geo = engine.execute_fallback("geo_analysis", [])
    assert geo["status"] == "UNAVAILABLE"
    assert geo["extractability_score"] is None
    assert geo["citation_readiness_score"] is None

    # 3. AI Search capability fallback
    ai_search = engine.execute_fallback("ai_search_simulation", [])
    assert ai_search["status"] == "UNAVAILABLE"
    assert ai_search["evaluations"] == []


def test_compat_schema_preserves_bands_without_numeric_hallucination():
    """Compat mapping preserves qualitative bands but sets unmeasured numeric fields to None."""
    biz_out = {
        "five_second_clarity": {"band": "clear"},
        "cac_impact": {"mechanism": "friction on checkout"}
    }
    adapted_biz = legacy_adapt("business", biz_out)
    assert adapted_biz["five_second_clarity_band"] == "clear"
    assert adapted_biz["five_second_clarity_score"] is None
    assert adapted_biz["cac_impact_risk"] == "friction on checkout"

    geo_out = {}
    adapted_geo = legacy_adapt("geo", geo_out)
    assert adapted_geo["entity_clarity_score"] is None
    assert adapted_geo["direct_answer_density_score"] is None

    search_out = {"evaluations": [{"buyer_query": "pricing"}]}
    adapted_search = legacy_adapt("ai_search", search_out)
    assert adapted_search["evaluations"][0]["citation_probability"] is None
    assert adapted_search["aggregate_citation_probability"] is None


@pytest.mark.asyncio
async def test_connectors_fail_closed_on_missing_credentials():
    """Connectors must return UNAUTHORIZED / ERROR when auth credentials are missing."""
    gh = GitHubClient(ConnectorCredentials(provider="github", repository="user/repo", github_token=""))
    conn_gh = await gh.test_health()
    assert conn_gh.status == ConnectorHealthStatus.UNAUTHORIZED

    shopify = ShopifyConnector(ConnectorCredentials(provider="shopify", api_url="https://store.myshopify.com"))
    conn_sh = await shopify.test_connection()
    assert conn_sh.status == ConnectorHealthStatus.UNAUTHORIZED

    wf = WebflowConnector(ConnectorCredentials(provider="webflow", api_url="site123"))
    conn_wf = await wf.test_connection()
    assert conn_wf.status == ConnectorHealthStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_verification_engine_fails_closed_when_snippet_missing():
    """Closed-loop verifier must not award fake 24 points or mark resolved if snippet missing."""
    engine = VerificationEngine()
    patch = RemediationPatch(
        patch_id="patch_test_1",
        finding_id="F-TEST",
        title="Schema Injection",
        category="SCHEMA",
        risk_level=PatchRiskLevel.SAFE_AUTO,
        after_snippet="window.__DRISTIK_VERIFIED_SIGNATURE__ = 'xyz123';",
        explanation="Test patch",
        metadata_payload={"target_url": "https://httpbin.org/get"}
    )
    res = await engine.verify_remediation(patch)
    assert res.is_resolved is False
    assert res.status == "PENDING_VERIFICATION"
    assert res.after_score is None
    assert res.score_delta is None


@pytest.mark.asyncio
async def test_ai_citation_tracker_offline_honest_return(monkeypatch):
    """When live search keys are absent, AI citation tracker reports UNAVAILABLE honestly."""
    for key in (
        "PERPLEXITY_API_KEY",
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
        "CLAUDE_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
        monkeypatch.setattr(settings, key, "", raising=False)
    tracker = AiCitationTracker()
    res = await tracker.track_buyer_queries(
        domain="unconfigured-test-domain.com",
        biz_name="Test Company",
        niche="Logistics"
    )
    assert res.is_live is False
    assert res.overall_ai_citation_score is None
    assert res.tracked_queries == []
    assert "UNAVAILABLE" in (res.status_message or "") or "API key" in (res.status_message or "")


def test_agency_client_defaults_fail_closed():
    """Newly registered agency clients must start in PENDING_AUDIT with null scores."""
    mgr = AgencyManager()
    client = mgr.add_client("Acme Inc", "acme.com")
    assert client.status == "PENDING_AUDIT"
    assert client.human_score is None
    assert client.google_score is None
    assert client.ai_citation_score is None
    assert client.overall_health is None
    assert client.total_findings == 0
