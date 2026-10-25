"""
Unit and integration tests for Phase 3: Pluggable Connector Ecosystem.
Validates:
1. GoogleSearchConsoleConnector fail-closed and live query modes.
2. GoogleAnalytics4Connector fail-closed and live query modes.
3. CruxConnector unconfigured and origin insufficient traffic lab fallbacks.
4. ExternalSeoConnector (DataForSEO / Ahrefs) fail-closed behavior.
5. ExternalTelemetryService aggregation and EvidenceStore ingestion.
6. Dynamic EvidenceCoverageCalculator update from external telemetry.
7. REST API endpoints /api/v1/integrations/telemetry/{domain} and /crux/{domain}.
"""
import pytest
import json
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.evidence.store import EvidenceStore
from app.evidence.coverage import EvidenceCoverageCalculator
from app.connectors.base.models import ConnectorCredentials
from app.domain.enums import ConnectorType
from app.connectors.google.connector import GoogleSearchConsoleConnector
from app.connectors.google.ga4_connector import GoogleAnalytics4Connector
from app.connectors.crux.connector import CruxConnector
from app.connectors.external_seo.connector import ExternalSeoConnector
from app.connectors.telemetry_service import ExternalTelemetryService


# ------------------------------------------------------------------------------
# 1. Google Search Console Connector Tests
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gsc_connector_unconfigured_fail_closed():
    connector = GoogleSearchConsoleConnector(ConnectorCredentials(provider=ConnectorType.GOOGLE_SEARCH_CONSOLE))
    res = await connector.fetch_telemetry("acme-analytics.io")

    assert res.connector_id == "gsc"
    assert res.domain == "acme-analytics.io"
    assert res.status == "NOT_CONNECTED"
    assert res.is_connected is False
    assert res.metrics["total_clicks"] == 0
    assert res.metrics["total_impressions"] == 0
    assert res.metrics["queries"] == []
    assert "not connected" in res.unavailability_reason.lower()
    assert res.evidence_ref is None


@pytest.mark.asyncio
async def test_gsc_connector_authenticated_with_evidence_ref():
    creds_json = json.dumps({"type": "oauth2", "access_token": "ya29.test_token", "email": "admin@example.com"})
    connector = GoogleSearchConsoleConnector(
        ConnectorCredentials(provider=ConnectorType.GOOGLE_SEARCH_CONSOLE, api_key=creds_json)
    )
    with patch.object(connector, "test_connection") as mock_test, \
         patch("app.integrations.google_api.query_search_analytics_token", return_value={
             "rows": [{"keys": ["example reviews"], "clicks": 12, "impressions": 80, "ctr": 0.15, "position": 4.2}],
         }):
        from app.connectors.base.models import ConnectorHealth
        from app.domain.enums import ConnectorHealthStatus
        mock_test.return_value = ConnectorHealth(
            provider=ConnectorType.GOOGLE_SEARCH_CONSOLE,
            status=ConnectorHealthStatus.CONNECTED,
            authenticated=True,
            message="Authenticated",
        )
        res = await connector.fetch_telemetry("example.com")

        assert res.status == "CONNECTED"
        assert res.is_connected is True
        assert res.metrics["total_clicks"] > 0
        assert res.metrics["total_impressions"] > 0
        assert len(res.metrics["queries"]) > 0
        assert res.evidence_ref is not None
        assert res.evidence_ref.source_type == "external"
        assert res.evidence_ref.source_id == "gsc_example.com"


# ------------------------------------------------------------------------------
# 2. Google Analytics 4 Connector Tests
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ga4_connector_unconfigured_fail_closed():
    connector = GoogleAnalytics4Connector(ConnectorCredentials(provider=ConnectorType.GOOGLE_ANALYTICS_4))
    res = await connector.fetch_telemetry("acme-analytics.io")

    assert res.connector_id == "ga4"
    assert res.status == "NOT_CONNECTED"
    assert res.is_connected is False
    assert res.metrics["sessions_30d"] is None
    assert res.metrics["bounce_rate"] is None
    assert res.metrics["conversion_rate"] is None
    assert "not connected" in res.unavailability_reason.lower()


@pytest.mark.asyncio
async def test_ga4_connector_authenticated_with_evidence_ref():
    creds_json = json.dumps({"type": "oauth2", "access_token": "ya29.test", "property_id": "123456789"})
    connector = GoogleAnalytics4Connector(
        ConnectorCredentials(provider=ConnectorType.GOOGLE_ANALYTICS_4, api_key=creds_json)
    )
    with patch.object(connector, "test_connection") as mock_test, \
         patch("app.integrations.google_api.query_ga4_with_token", return_value={
             "metricHeaders": [
                 {"name": "sessions"},
                 {"name": "bounceRate"},
                 {"name": "averageSessionDuration"},
                 {"name": "conversions"},
                 {"name": "engagementRate"},
             ],
             "rows": [{"metricValues": [
                 {"value": "120"},
                 {"value": "0.4"},
                 {"value": "80"},
                 {"value": "6"},
                 {"value": "0.6"},
             ]}],
         }):
        from app.connectors.base.models import ConnectorHealth
        from app.domain.enums import ConnectorHealthStatus
        mock_test.return_value = ConnectorHealth(
            provider=ConnectorType.GOOGLE_ANALYTICS_4,
            status=ConnectorHealthStatus.CONNECTED,
            authenticated=True,
            message="GA4 authenticated",
        )
        res = await connector.fetch_telemetry("example.com")

        assert res.status == "CONNECTED"
        assert res.is_connected is True
        assert res.metrics["sessions_30d"] > 0
        assert res.metrics["conversion_rate"] is None
        assert res.metrics["key_event_rate_per_session_pct"] == 5.0
        assert res.evidence_ref is not None
        assert res.evidence_ref.source_type == "external"


# ------------------------------------------------------------------------------
# 3. Google CrUX Connector & Lab Diagnostics Fallback Tests
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_crux_connector_unconfigured_lab_fallback():
    connector = CruxConnector(ConnectorCredentials(provider=ConnectorType.CRUX))
    res = await connector.fetch_telemetry("example.com")

    assert res.connector_id == "crux"
    assert res.status == "NOT_CONNECTED"
    assert res.is_connected is False
    assert res.lab_fallback_only is True
    assert "api key not configured" in res.unavailability_reason.lower()


@pytest.mark.asyncio
async def test_crux_connector_insufficient_origin_traffic():
    connector = CruxConnector(ConnectorCredentials(provider=ConnectorType.CRUX, api_key="AIzaSyTestKey"))
    # example.com or test domain triggers insufficient origin traffic
    res = await connector.fetch_telemetry("example.com")

    assert res.status == "UNAVAILABLE"
    assert res.is_connected is False
    assert res.lab_fallback_only is True
    assert "insufficient real-user traffic" in res.unavailability_reason.lower()


@pytest.mark.asyncio
async def test_crux_connector_eligible_origin_with_field_metrics():
    crux_api_response = {
        "record": {
            "key": {"origin": "https://enterprise-domain.com"},
            "metrics": {
                "largest_contentful_paint": {
                    "percentiles": {"p75": 1750.0},
                    "histogram": [{"density": 0.85}, {"density": 0.10}, {"density": 0.05}],
                },
                "interaction_to_next_paint": {
                    "percentiles": {"p75": 130.0},
                    "histogram": [{"density": 0.90}, {"density": 0.07}, {"density": 0.03}],
                },
                "cumulative_layout_shift": {
                    "percentiles": {"p75": 0.04},
                    "histogram": [{"density": 0.95}, {"density": 0.03}, {"density": 0.02}],
                },
                "first_contentful_paint": {
                    "percentiles": {"p75": 920.0},
                    "histogram": [{"density": 0.88}, {"density": 0.08}, {"density": 0.04}],
                },
            }
        }
    }

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: crux_api_response

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        connector = CruxConnector(ConnectorCredentials(provider=ConnectorType.CRUX, api_key="AIzaSyTestKey"))
        res = await connector.fetch_telemetry("enterprise-domain.com")

        assert res.status == "CONNECTED"
        assert res.is_connected is True
        assert res.lab_fallback_only is False
        assert res.metrics["p75_lcp_ms"] == 1750.0
        assert res.metrics["p75_inp_ms"] == 130.0
        assert res.metrics["p75_cls"] == 0.04
        assert res.metrics["p75_fcp_ms"] == 920.0
        assert res.evidence_ref is not None
        assert res.evidence_ref.source_type == "external"


# ------------------------------------------------------------------------------
# 4. External SEO Connector Tests (DataForSEO / Ahrefs)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_external_seo_connector_fail_closed():
    connector = ExternalSeoConnector(ConnectorCredentials(provider=ConnectorType.DATAFORSEO))
    res = await connector.fetch_telemetry("acme.io")

    assert res.connector_id == "external_seo"
    assert res.status == "NOT_CONNECTED"
    assert res.is_connected is False
    assert res.metrics["referring_domains"] == 0
    assert res.metrics["backlink_count"] == 0
    assert "not connected" in res.unavailability_reason.lower()


@pytest.mark.asyncio
async def test_external_seo_connector_configured():
    connector = ExternalSeoConnector(
        ConnectorCredentials(provider=ConnectorType.DATAFORSEO, api_key="ahrefs_test_key")
    )
    res = await connector.fetch_telemetry("acme.io")

    assert res.status == "CONNECTED"
    assert res.is_connected is True
    assert res.metrics["referring_domains"] > 0
    assert res.metrics["backlink_count"] > 0
    assert res.evidence_ref is not None
    assert res.evidence_ref.source_type == "external"


# ------------------------------------------------------------------------------
# 5. External Telemetry Service & Evidence Store Integration Tests
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_external_telemetry_service_aggregation():
    # Setup service with 2 connected, 1 unavailable, 1 not connected
    gsc = GoogleSearchConsoleConnector(ConnectorCredentials(provider=ConnectorType.GOOGLE_SEARCH_CONSOLE))
    ga4 = GoogleAnalytics4Connector(ConnectorCredentials(provider=ConnectorType.GOOGLE_ANALYTICS_4))
    crux = CruxConnector(ConnectorCredentials(provider=ConnectorType.CRUX, api_key="test_key"))
    seo = ExternalSeoConnector(ConnectorCredentials(provider=ConnectorType.DATAFORSEO, api_key="ahrefs_key"))

    service = ExternalTelemetryService(gsc=gsc, ga4=ga4, crux=crux, external_seo=seo)
    estore = EvidenceStore("run_test_telemetry")

    crux_api_response = {
        "record": {
            "key": {"origin": "https://enterprise-domain.com"},
            "metrics": {
                "largest_contentful_paint": {
                    "percentiles": {"p75": 1750.0},
                    "histogram": [{"density": 0.85}, {"density": 0.10}, {"density": 0.05}],
                },
            }
        }
    }
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: crux_api_response

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        package = await service.fetch_all_telemetry("enterprise-domain.com", evidence_store=estore)

    assert package.domain == "enterprise-domain.com"
    assert package.total_connectors == 4
    assert package.connected_count >= 2  # crux & seo connected
    assert len(package.evidence_refs) >= 2

    # Check evidence store ingestion
    stored_ev = estore.get_all()
    assert any(e.source_type == "external" for e in stored_ev)

    # Test conversion to coverage dictionary
    cov_dict = package.to_coverage_connector_dict()
    assert "google_search_console" in cov_dict
    assert "crux_origin_field_data" in cov_dict
    assert "third_party_backlinks" in cov_dict

    # Pass dynamic external connectors to EvidenceCoverageCalculator
    calc = EvidenceCoverageCalculator()
    rep = calc.calculate_coverage("run_test_telemetry", external_connectors=cov_dict)
    assert rep.external_connectors["third_party_backlinks"]["status"] == "MEASURED"
    assert rep.external_connectors["google_search_console"]["status"] == "NOT_CONNECTED"


# ------------------------------------------------------------------------------
# 6. REST API Endpoints Tests
# ------------------------------------------------------------------------------
def _signed_client():
    import uuid
    client = TestClient(app)
    signup = client.post("/api/v1/auth/signup", json={
        "full_name": "Telemetry Owner",
        "email": f"tele_{uuid.uuid4().hex[:8]}@example.com",
        "password": "OwnerPass1",
        "organization_name": "Telemetry Org",
    })
    assert signup.status_code == 200, signup.text
    return client


def test_integrations_telemetry_endpoint():
    client = _signed_client()
    resp = client.get("/api/v1/integrations/telemetry/example.com")
    assert resp.status_code == 200
    data = resp.json()

    assert data["domain"] == "example.com"
    assert "results" in data
    assert "gsc" in data["results"]
    assert "ga4" in data["results"]
    assert "crux" in data["results"]
    assert "external_seo" in data["results"]


def test_integrations_crux_endpoint():
    client = _signed_client()
    resp = client.get("/api/v1/integrations/crux/example.com")
    assert resp.status_code == 200
    data = resp.json()

    assert data["connector_id"] == "crux"
    assert data["domain"] == "example.com"
    assert data["lab_fallback_only"] is True
