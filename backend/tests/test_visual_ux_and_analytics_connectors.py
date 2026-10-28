"""
Unit tests for:
1. Visual UX Testing (Desktop, Tablet, Mobile above-the-fold inspection & defect detection)
2. Grounded CRO Analysis (Observed vs Inferred vs Requires Analytics)
3. Analytics Connectors (GSC, GA4, CRM Lifecycle Revenue Intelligence)
"""
import pytest
from app.domain.enums import Category, Severity, ConnectorType, ConnectorHealthStatus
from app.connectors.base.models import ConnectorCredentials
from app.connectors.google.ga4_connector import GoogleAnalytics4Connector
from app.connectors.crm.connector import CrmRevenueConnector
from app.connectors.lifecycle_revenue import LifecycleRevenueService, lifecycle_service
from app.intelligence.ux.visual_ux_tester import VisualUxTester, visual_ux_tester


@pytest.mark.asyncio
async def test_ga4_connector_lifecycle():
    # Test unauthorized
    conn = GoogleAnalytics4Connector(
        credentials=ConnectorCredentials(provider=ConnectorType.GOOGLE_ANALYTICS_4)
    )
    health = await conn.test_connection()
    assert health.status == ConnectorHealthStatus.UNAUTHORIZED
    assert health.authenticated is False

    # Test authorized with service account
    conn_auth = GoogleAnalytics4Connector(
        credentials=ConnectorCredentials(
            provider=ConnectorType.GOOGLE_ANALYTICS_4,
            api_key='{"property_id": "properties/12345"}',
        )
    )
    health_auth = await conn_auth.test_connection()
    assert health_auth.status == ConnectorHealthStatus.DISCONNECTED
    assert health_auth.authenticated is False

    data = await conn_auth.fetch_attribution_data("example.com")
    assert data.is_connected is False
    assert data.landing_pages == []
    assert data.conversion_rate is None
    assert data.funnels == []


@pytest.mark.asyncio
async def test_crm_connector_lifecycle():
    # Test unauthorized
    conn = CrmRevenueConnector(
        credentials=ConnectorCredentials(provider=ConnectorType.CRM)
    )
    health = await conn.test_connection()
    assert health.status == ConnectorHealthStatus.UNAUTHORIZED

    # Test authorized
    conn_auth = CrmRevenueConnector(
        credentials=ConnectorCredentials(
            provider=ConnectorType.CRM,
            api_key="pat-na1-12345",
        )
    )
    health_auth = await conn_auth.test_connection()
    assert health_auth.status == ConnectorHealthStatus.DISCONNECTED

    data = await conn_auth.fetch_attribution_data("example.com")
    assert data.is_connected is False
    assert data.lead_source == []
    assert data.pipeline_value_inr == 0
    assert data.closed_revenue_inr == 0


def test_lifecycle_revenue_intelligence_service():
    svc = LifecycleRevenueService()
    
    # 1. Unconnected state: metrics must be UNKNOWN
    unconnected = svc.synthesize_lifecycle_intelligence(
        "example.com", gsc_connected=False, ga4_connected=False, crm_connected=False
    )
    assert unconnected.stages["search"]["metrics"]["impressions"] == "UNKNOWN"
    assert unconnected.stages["visitor"]["metrics"]["conversion_rate"] == "UNKNOWN"
    assert unconnected.stages["visitor"]["metrics"]["abandonment_rate"] == "UNKNOWN"
    assert unconnected.stages["revenue"]["metrics"]["pipeline_value_inr"] == "UNKNOWN"

    flagged = svc.synthesize_lifecycle_intelligence(
        "example.com", gsc_connected=True, ga4_connected=True, crm_connected=True
    )
    assert flagged.gsc.is_connected is False
    assert flagged.ga4.is_connected is False
    assert flagged.crm.is_connected is False
    assert flagged.gsc.impressions == 0
    assert flagged.stages["visitor"]["metrics"]["conversion_rate"] == "UNKNOWN"
    assert flagged.stages["search"]["metrics"]["impressions"] == "UNKNOWN"
    assert "unmeasured" in flagged.summary.lower()



def test_lifecycle_revenue_connected_but_missing_nullable_metrics_stay_unknown():
    from app.domain.models import GscAttributionData, Ga4AttributionData, CrmAttributionData

    svc = LifecycleRevenueService()
    result = svc.synthesize_lifecycle_intelligence(
        "example.com",
        gsc_data=GscAttributionData.model_construct(is_connected=True, ctr=None),
        ga4_data=Ga4AttributionData.model_construct(
            is_connected=True,
            engagement_rate=None,
            conversion_rate=None,
        ),
        crm_data=CrmAttributionData.model_construct(is_connected=True, lead_quality_score=None),
    )
    assert result.stages["search"]["metrics"]["ctr"] == "UNKNOWN"
    assert result.stages["visitor"]["metrics"]["engagement_rate"] == "UNKNOWN"
    assert result.stages["visitor"]["metrics"]["conversion_rate"] == "UNKNOWN"
    assert result.stages["lead"]["metrics"]["lead_quality"] == "UNKNOWN"


def test_visual_ux_testing_engine():
    tester = VisualUxTester()
    report = tester.inspect_website_visual_ux("example.com", "https://example.com")

    assert report.viewports == {}
    assert report.overall_visual_ux_score is None
    assert report.critical_visual_defects == []
    assert report.combined_intelligence["status"] == "not_measured"
    blob = str(report.model_dump())
    assert "REQUEST CUSTOM BUILD" not in blob


def test_grounded_cro_finding_uses_crawled_pages_only():
    tester = VisualUxTester()
    assert tester.generate_grounded_cro_finding("example.com", "https://example.com") is None

    class _Page:
        def __init__(self):
            self.ctas = ["Book a demo"]
            self.url = "https://example.com/pricing"
            self.page_type = "pricing"

    finding = tester.generate_grounded_cro_finding(
        "example.com", "https://example.com", pages=[_Page()]
    )
    assert finding is not None and finding.cro_dissection is not None
    facts = " ".join(finding.cro_dissection.observed_facts)
    assert "Book a demo" in facts
    assert "pricing" in facts
    assert "REQUEST CUSTOM BUILD" not in facts
    assert finding.cro_dissection.requires_analytics["actual_abandonment_rate"] == "UNKNOWN"
    assert finding.cro_dissection.analytics_connected is False


@pytest.mark.asyncio
async def test_dataforseo_live_ai_search_and_crux_connectors():
    from app.connectors.dataforseo.connector import DataForSeoConnector
    from app.connectors.ai_search.connector import LiveAiSearchConnector
    from app.connectors.crux.connector import CruxConnector
    from app.connectors.store import connector_store

    # 1. DataForSEO
    dfs = DataForSeoConnector(credentials=ConnectorCredentials(provider=ConnectorType.DATAFORSEO))
    dfs_health = await dfs.test_connection()
    assert dfs_health.provider == ConnectorType.DATAFORSEO
    assert dfs_health.status == ConnectorHealthStatus.UNAUTHORIZED

    # 2. Live AI Search
    ai = LiveAiSearchConnector(credentials=ConnectorCredentials(provider=ConnectorType.LIVE_AI_SEARCH))
    ai_health = await ai.test_connection()
    assert ai_health.provider == ConnectorType.LIVE_AI_SEARCH

    # 3. CrUX
    crux = CruxConnector(credentials=ConnectorCredentials(provider=ConnectorType.CRUX))
    crux_health = await crux.test_connection()
    assert crux_health.provider == ConnectorType.CRUX
    assert crux_health.status == ConnectorHealthStatus.UNAUTHORIZED
    assert crux_health.authenticated is False

    # 4. Connector Store Instantiation
    dfs_integ = connector_store.add_integration(
        provider=ConnectorType.DATAFORSEO,
        name="DataForSEO Test",
        target_url="https://example.com",
        credentials=ConnectorCredentials(provider=ConnectorType.DATAFORSEO)
    )
    instantiated_dfs = connector_store.get_connector(dfs_integ.integration_id)
    assert isinstance(instantiated_dfs, DataForSeoConnector)
    connector_store.delete_integration(dfs_integ.integration_id)

