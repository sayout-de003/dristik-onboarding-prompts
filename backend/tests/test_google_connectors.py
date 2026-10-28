import pytest
from app.integrations.google_connectors import (
    GoogleSearchConsoleConnector,
    GoogleAnalytics4Connector,
    gsc_connector,
    ga4_connector,
)
from app.domain.enums import MetricProvenanceState


def test_gsc_connector_unconfigured_fail_closed():
    """Unconnected GSC must never return fake fixture clicks or queries."""
    connector = GoogleSearchConsoleConnector(credentials_json=None)
    summary = connector.fetch_performance("https://acme-analytics.io", days=90)

    assert summary.domain == "acme-analytics.io"
    assert summary.connected is False
    assert summary.provenance == MetricProvenanceState.NOT_CONFIGURED
    assert summary.total_clicks == 0
    assert summary.total_impressions == 0
    assert summary.average_ctr == 0.0
    assert summary.average_position == 0.0
    assert len(summary.queries) == 0
    assert "not configured" in summary.status_notice.lower()


def test_ga4_connector_unconfigured_fail_closed():
    """Unconnected GA4 must never return fake sessions (18,450) or bounce rates."""
    connector = GoogleAnalytics4Connector(property_id=None)
    summary = connector.fetch_performance("https://acme-analytics.io")

    assert summary.domain == "acme-analytics.io"
    assert summary.connected is False
    assert summary.provenance == MetricProvenanceState.NOT_CONFIGURED
    assert summary.sessions_30d == 0
    assert summary.bounce_rate == 0.0
    assert summary.conversion_rate == 0.0
    assert summary.conversions_count == 0
    assert len(summary.top_landing_pages) == 0
    assert "not connected" in summary.status_notice.lower()


def test_integrations_api_router_zero_synthetic():
    from fastapi.testclient import TestClient
    from app.main import app

    import uuid
    client = TestClient(app, base_url="https://testserver")
    signup = client.post("/api/v1/auth/signup", json={
        "full_name": "Integrations Owner",
        "email": f"integ_{uuid.uuid4().hex[:8]}@example.com",
        "password": "OwnerPass1",
        "organization_name": "Integrations Org",
    })
    assert signup.status_code == 200, signup.text
    status_resp = client.get("/api/v1/integrations/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "google_search_console" in data
    assert "google_analytics_4" in data
    assert "dataforseo_keyword_index" in data

    # Unconfigured GSC endpoint must return NOT_CONFIGURED and 0 clicks
    gsc_resp = client.get("/api/v1/integrations/gsc/performance?domain=example.com")
    assert gsc_resp.status_code == 200
    gsc_data = gsc_resp.json()
    assert gsc_data["domain"] == "example.com"
    assert gsc_data["connected"] is False
    assert gsc_data["provenance"] == "NOT_CONFIGURED"
    assert gsc_data["total_clicks"] == 0
    assert len(gsc_data["queries"]) == 0

    # Unconfigured GA4 endpoint must return NOT_CONFIGURED and 0 sessions
    ga4_resp = client.get("/api/v1/integrations/ga4/performance?domain=example.com")
    assert ga4_resp.status_code == 200
    ga4_data = ga4_resp.json()
    assert ga4_data["domain"] == "example.com"
    assert ga4_data["provenance"] == "NOT_CONFIGURED"
    assert ga4_data["sessions_30d"] == 0

    # Test connect validation fails-closed on invalid credentials
    invalid_gsc = client.post("/api/v1/integrations/gsc/connect", json={"credentials_json_path": "/nonexistent/path.json"})
    assert invalid_gsc.status_code == 400

    invalid_ga4 = client.post("/api/v1/integrations/ga4/connect", json={"property_id": "   "})
    assert invalid_ga4.status_code == 400


def test_google_analytics_connector_alias_and_oauth_routes():
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.config import settings
    from app.domain.enums import ConnectorType
    from app.connectors.store import connector_store
    from app.connectors.base.models import ConnectorCredentials
    import uuid

    client = TestClient(app)
    email = f"ga_{uuid.uuid4().hex[:8]}@example.com"
    signup = client.post("/api/v1/auth/signup", json={
        "full_name": "GA User",
        "email": email,
        "password": "Password123",
        "organization_name": "GA Org",
    })
    assert signup.status_code == 200
    login = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "Password123",
    })
    assert login.status_code == 200, login.text

    # 1. Authorize routes for google_analytics and google_analytics_4
    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-client-id"), \
         patch.object(settings, "GOOGLE_CLIENT_SECRET", "mock-client-sec"), \
         patch.object(settings, "AUTH_SECRET", "test-oauth-state-signing-secret-0123456789abcdef"), \
         patch.object(settings, "ENVIRONMENT", "test"):
        resp_ga = client.get(
            "/api/v1/connectors/oauth/google_analytics/authorize?domain=example.com",
            follow_redirects=False,
        )
        assert resp_ga.status_code in (302, 307)
        assert "accounts.google.com" in resp_ga.headers["location"]
        assert "analytics.readonly" in resp_ga.headers["location"]

        resp_shared = client.get(
            "/api/v1/connectors/google/oauth/authorize?domain=example.com&service=analytics",
            follow_redirects=False,
        )
        assert resp_shared.status_code in (302, 307)
        assert "google_analytics_4/authorize" in resp_shared.headers["location"]

    # 2. Store instantiate connector with GOOGLE_ANALYTICS enum
    integ = connector_store.add_integration(
        provider=ConnectorType.GOOGLE_ANALYTICS,
        name="Google Analytics (example.com)",
        target_url="https://example.com",
        credentials=ConnectorCredentials(provider=ConnectorType.GOOGLE_ANALYTICS, api_key="123456789"),
    )
    conn = connector_store.get_connector(integ.integration_id)
    assert conn is not None
    from app.connectors.google.ga4_connector import GoogleAnalytics4Connector
    assert isinstance(conn, GoogleAnalytics4Connector)
