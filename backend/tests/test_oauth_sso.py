"""
Tests for 1-Click OAuth SSO for User Authentication & Connector Hub.
Verifies provider status discovery, CSRF state security, auto-provisioning,
account linking, and fail-closed integrity when credentials are absent.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.identity.store import get_store
from app.identity.authorizer import UserRole
from app.identity.security import SESSION_COOKIE
import app.identity.oauth_service as oauth_service

client = TestClient(app)


def test_auth_providers_discovery():
    """Verify /api/v1/auth/providers returns Google and GitHub discovery status."""
    res = client.get("/api/v1/auth/providers")
    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    assert "google" in data["providers"]
    assert "github" in data["providers"]
    assert data["providers"]["google"]["name"] == "Google"
    assert data["providers"]["github"]["name"] == "GitHub"


def test_authorize_unconfigured_fails_closed():
    """When client ID and secret are not configured, authorize endpoints fail closed with 503."""
    with patch.object(settings, "GOOGLE_CLIENT_ID", None), \
         patch.object(settings, "GOOGLE_SSO_CLIENT_ID", None), \
         patch.object(settings, "GOOGLE_CLIENT_SECRET", None), \
         patch.object(settings, "GOOGLE_SSO_CLIENT_SECRET", None), \
         patch.object(settings, "GITHUB_CLIENT_ID", None), \
         patch.object(settings, "GITHUB_SSO_CLIENT_ID", None), \
         patch.object(settings, "GITHUB_CLIENT_SECRET", None), \
         patch.object(settings, "GITHUB_SSO_CLIENT_SECRET", None):

        res_g = client.get("/api/v1/auth/oauth/google/authorize", follow_redirects=False)
        assert res_g.status_code == 503
        assert "Google OAuth SSO is not configured" in res_g.json()["detail"]

        res_gh = client.get("/api/v1/auth/oauth/github/authorize", follow_redirects=False)
        assert res_gh.status_code == 503
        assert "GitHub OAuth SSO is not configured" in res_gh.json()["detail"]


def test_authorize_redirects_when_configured():
    """When configured, authorize returns 307/302 redirecting to provider consent with HMAC state."""
    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-id"), \
         patch.object(settings, "GOOGLE_CLIENT_SECRET", "mock-google-sec"):
        res = client.get("/api/v1/auth/oauth/google/authorize", follow_redirects=False)
        assert res.status_code in (302, 307)
        loc = res.headers["location"]
        assert "accounts.google.com/o/oauth2/v2/auth" in loc
        assert "client_id=mock-google-id" in loc
        assert "state=" in loc


def test_state_signature_tampering_rejected():
    """Tampering with state payload or signature results in rejection."""
    valid_state = oauth_service._sign_state({"provider": "google", "redirect": "/"})
    raw_part, sig_part = valid_state.split(".", 1)
    tampered_state = f"{raw_part}.fake_sig_12345"

    with pytest.raises(Exception) as exc:
        oauth_service._unsign_state(tampered_state)
    assert "signature verification failed" in str(exc.value).lower()


def test_oauth_sso_callback_missing_params():
    """Callback without code or state renders failure HTML page."""
    res = client.get("/api/v1/auth/oauth/google/callback")
    assert res.status_code == 200
    assert "Sign-In Failed" in res.text


def test_oauth_sso_signup_and_login_flow():
    """
    Mocking provider profile retrieval:
    1. New user is auto-provisioned with organization and receives a session cookie.
    2. Subsequent login with same OAuth ID logs in the user and updates last_login_at.
    """
    mock_profile = {
        "provider": "google",
        "oauth_id": "google_sub_987654321",
        "email": "sarah.connor@cyberdyne-audit.com",
        "full_name": "Sarah Connor",
        "avatar_url": "https://lh3.googleusercontent.com/a/mock-avatar",
    }
    state = oauth_service._sign_state({"provider": "google", "redirect": "/dashboard"})

    with patch("app.identity.oauth_service.exchange_and_get_profile", return_value=(mock_profile, "/dashboard")):
        # First sign-in (auto-signup)
        res = client.get(
            f"/api/v1/auth/oauth/google/callback?code=mock_code&state={state}&format=json"
        )
        assert res.status_code == 200
        data = res.json()
        assert "user" in data
        assert data["user"]["email"] == "sarah.connor@cyberdyne-audit.com"
        assert data["user"]["full_name"] == "Sarah Connor"
        assert data["user"]["role"] == UserRole.OWNER.value
        assert "token" not in data
        session_token = res.cookies.get(SESSION_COOKIE)
        assert session_token

        # Verify session is valid via /me
        me_res = client.get("/api/v1/auth/me", cookies={SESSION_COOKIE: session_token})
        assert me_res.status_code == 200
        assert me_res.json()["user"]["email"] == "sarah.connor@cyberdyne-audit.com"

        # Second sign-in with same OAuth ID (login existing)
        res2 = client.get(
            f"/api/v1/auth/oauth/google/callback?code=mock_code_2&state={state}&format=json"
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["user"]["user_id"] == data["user"]["user_id"]


def test_oauth_sso_links_to_existing_email():
    """
    If a user already registered with email/password, signing in via OAuth with the same email
    links the OAuth identity to the existing account rather than creating duplicate.
    """
    store = get_store()
    existing_email = "link_test_user@example.com"
    if not store.email_taken(existing_email):
        org = store.create_organization("Existing Org", "existing-org-unique-slug")
        store.create_user(org["org_id"], existing_email, "Existing Name", "Password123!", UserRole.OWNER)

    user_before = store.get_user_by_email(existing_email)
    assert user_before is not None

    mock_profile = {
        "provider": "github",
        "oauth_id": "gh_12345678",
        "email": existing_email,
        "full_name": "GitHub Existing Name",
        "avatar_url": "https://avatars.githubusercontent.com/u/12345678",
    }
    state = oauth_service._sign_state({"provider": "github", "redirect": "/"})

    with patch("app.identity.oauth_service.exchange_and_get_profile", return_value=(mock_profile, "/")):
        res = client.get(
            f"/api/v1/auth/oauth/github/callback?code=gh_code&state={state}&format=json"
        )
        assert res.status_code == 200
        data = res.json()
        assert data["user"]["user_id"] == user_before.user_id
        assert data["user"]["email"] == existing_email

        # Verify in store that oauth_id was recorded
        user_after = store.get_user(user_before.user_id)
        assert user_after.oauth_id == "gh_12345678"
        assert user_after.auth_provider == "github"


def test_connectors_oauth_providers_status():
    """Verify connector hub lists all OAuth connectors including Search Console."""
    res = client.get("/api/v1/connectors/oauth/providers")
    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    providers = data["providers"]
    for expected in [
        "google_search_console",
        "google_analytics_4",
        "github",
        "shopify",
        "webflow",
        "hubspot",
        "salesforce",
        "stripe",
        "wordpress",
    ]:
        assert expected in providers, f"Missing connector provider: {expected}"


def test_search_console_authorize_uses_registered_google_redirect():
    """Search Console must send the redirect URI registered on the Google client."""
    import uuid
    secure_client = TestClient(app, base_url="https://testserver")
    email = f"gsc_{uuid.uuid4().hex[:8]}@example.com"
    signup = secure_client.post("/api/v1/auth/signup", json={
        "full_name": "Search Owner",
        "email": email,
        "password": "OwnerPass1",
        "organization_name": "Search Org",
    })
    assert signup.status_code == 200, signup.text
    login = secure_client.post("/api/v1/auth/login", json={"email": email, "password": "OwnerPass1"})
    assert login.status_code == 200, login.text
    registered = "https://octaos.org/api/v1/external-authority/oauth/callback"
    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-google-id"), \
         patch.object(settings, "GOOGLE_CLIENT_SECRET", "mock-google-sec"), \
         patch.object(settings, "AUTH_SECRET", "test-oauth-state-signing-secret-0123456789abcdef"), \
         patch.object(settings, "ENVIRONMENT", "test"), \
         patch.object(settings, "GOOGLE_OAUTH_REDIRECT_URI", registered), \
         patch.object(settings, "EXTERNAL_OAUTH_REDIRECT_URI", None), \
         patch.object(settings, "OAUTH_REDIRECT_URI", "https://octaos.org/api/v1/connectors/oauth/callback"):
        res = secure_client.get(
            "/api/v1/connectors/google/oauth/authorize?domain=example.com",
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert "/api/v1/connectors/oauth/google_search_console/authorize" in res.headers["location"]

        followed = secure_client.get(res.headers["location"], follow_redirects=False)
        assert followed.status_code in (302, 307)
        location = followed.headers["location"]
        assert "accounts.google.com" in location
        assert "external-authority%2Foauth%2Fcallback" in location or "external-authority/oauth/callback" in location

        sso = secure_client.get("/api/v1/auth/oauth/google/authorize", follow_redirects=False)
        assert sso.status_code in (302, 307)
        assert "external-authority%2Foauth%2Fcallback" in sso.headers["location"] or "external-authority/oauth/callback" in sso.headers["location"]


def test_registered_google_callback_completes_sso():
    """Google returns sign-in to the one registered callback. That route must finish SSO."""
    state = oauth_service._sign_state({"provider": "google", "nonce": "abc", "redirect": "/"})
    mock_profile = {
        "provider": "google",
        "oauth_id": "goog_registered_callback",
        "email": "registered.callback@example.com",
        "full_name": "Registered Callback",
        "avatar_url": None,
    }
    with patch("app.identity.oauth_service.exchange_and_get_profile", return_value=(mock_profile, "/")):
        res = client.get(
            f"/api/v1/external-authority/oauth/callback?code=mock_code&state={state}"
        )
    assert res.status_code == 200
    assert "Signed in as Registered Callback" in res.text
    assert "dristik_session=" in res.headers.get("set-cookie", "")


def test_oauth_sso_callback_html_broadcast_channel():
    """Verify HTML callback sends BroadcastChannel and localStorage events without force-navigating popups."""
    state = oauth_service._sign_state({"provider": "google", "redirect": "/#audit-view"})
    mock_profile = {
        "provider": "google",
        "oauth_id": "goog_test_broadcast",
        "email": "broadcast.test@example.com",
        "full_name": "Broadcast Test User",
        "avatar_url": None,
    }
    with patch("app.identity.oauth_service.exchange_and_get_profile", return_value=(mock_profile, "/#audit-view")):
        res = client.get(
            f"/api/v1/auth/oauth/google/callback?code=mock_code&state={state}"
        )
        assert res.status_code == 200
        html = res.text
        assert "BroadcastChannel('dristik_auth')" in html
        assert "dristik_auth_sync" in html
        assert "window.close()" in html
        assert "window.location.replace" in html
        assert "/#audit-view" in html
        assert "Return to Dristik" in html
        assert "dristik_session=" in res.headers.get("set-cookie", "")


def test_oauth_sso_callback_format_redirect():
    """Verify format=redirect performs 302 redirect directly back to the preserved redirect_target."""
    target_path = "/#deep-audit-456"
    state = oauth_service._sign_state({"provider": "google", "redirect": target_path})
    mock_profile = {
        "provider": "google",
        "oauth_id": "goog_test_redirect",
        "email": "redirect.test@example.com",
        "full_name": "Redirect Test User",
        "avatar_url": None,
    }
    with patch("app.identity.oauth_service.exchange_and_get_profile", return_value=(mock_profile, target_path)):
        res = client.get(
            f"/api/v1/auth/oauth/google/callback?code=mock_code&state={state}&format=redirect",
            follow_redirects=False,
        )
        assert res.status_code == 302
        assert res.headers["location"] == target_path
        assert "dristik_session=" in res.headers.get("set-cookie", "")


def test_ga4_connector_oauth_hosted_redirect_and_connect():
    """Verify GA4 1-click OAuth flow on hosted server preserves host, saves connected status, and updates status endpoint."""
    import uuid
    secure_client = TestClient(app, base_url="https://testserver")
    from app.connectors.oauth_providers import _sign
    from app.connectors.store import connector_store
    from app.domain.enums import ConnectorType, ConnectorHealthStatus

    email = f"ga4_{uuid.uuid4().hex[:8]}@example.com"
    signup = secure_client.post("/api/v1/auth/signup", json={
        "full_name": "GA4 Owner",
        "email": email,
        "password": "OwnerPass1",
        "organization_name": "GA4 Org",
    })
    assert signup.status_code == 200, signup.text
    login = secure_client.post("/api/v1/auth/login", json={"email": email, "password": "OwnerPass1"})
    assert login.status_code == 200, login.text
    org_id = signup.json()["user"]["org_id"]

    # 1. Authorize on a hosted domain with X-Forwarded-Host
    with patch.object(settings, "GOOGLE_CLIENT_ID", "mock-ga4-id"), \
         patch.object(settings, "GOOGLE_CLIENT_SECRET", "mock-ga4-sec"), \
         patch.object(settings, "AUTH_SECRET", "test-oauth-state-signing-secret-0123456789abcdef"), \
         patch.object(settings, "ENVIRONMENT", "test"), \
         patch.object(settings, "GOOGLE_OAUTH_REDIRECT_URI", None), \
         patch.object(settings, "EXTERNAL_OAUTH_REDIRECT_URI", None), \
         patch.object(settings, "OAUTH_REDIRECT_URI", "http://localhost:8000/api/v1/connectors/oauth/callback"):
        res = secure_client.get(
            "/api/v1/connectors/oauth/google_analytics_4/authorize?domain=acme-store.com",
            headers={"Host": "hosted-app.dristik.ai", "X-Forwarded-Proto": "https"},
            follow_redirects=False,
        )
        assert res.status_code in (302, 307)
        loc = res.headers["location"]
        assert "accounts.google.com/o/oauth2/v2/auth" in loc
        assert "https%3A%2F%2Fhosted-app.dristik.ai%2Fapi%2Fv1%2Fconnectors%2Foauth%2Fcallback" in loc

    # 2. Callback completion
    state = _sign({
        "provider": "google_analytics_4",
        "domain": "acme-store.com",
        "redirect_uri": "https://hosted-app.dristik.ai/api/v1/connectors/oauth/callback",
    })
    mock_token_data = {
        "access_token": "ya29.mock_ga4_token",
        "refresh_token": "mock_refresh_token",
    }
    with patch("app.connectors.oauth_providers._exchange", return_value=mock_token_data), \
         patch.object(settings, "GOOGLE_CLIENT_ID", "mock-ga4-id"), \
         patch.object(settings, "GOOGLE_CLIENT_SECRET", "mock-ga4-sec"):
        res = secure_client.get(
            f"/api/v1/connectors/oauth/callback?code=test_code_123&state={state}",
            headers={"Host": "hosted-app.dristik.ai", "X-Forwarded-Proto": "https"},
        )
        assert res.status_code == 200
        html_text = res.text
        assert "Connected" in html_text
        assert "Google Analytics" in html_text
        assert "Return to Dashboard" in html_text
        assert "BroadcastChannel('dristik_connector_oauth')" in html_text
        assert "dristik_connector_oauth_sync" in html_text
        assert "connector=connected" in html_text
        assert "window.location.replace" in html_text

        # 3. Verify saved integration in connector_store has CONNECTED status
        integrations = connector_store.list_integrations(org_id)
        ga4_integs = [i for i in integrations if i.provider == ConnectorType.GOOGLE_ANALYTICS_4]
        assert len(ga4_integs) > 0
        latest_ga4 = ga4_integs[-1]
        assert latest_ga4.status == ConnectorHealthStatus.CONNECTED

        # 4. Verify /api/v1/integrations/status reflects connected == True
        status_res = secure_client.get("/api/v1/integrations/status")
        assert status_res.status_code == 200
        data = status_res.json()
        assert data["google_analytics_4"]["connected"] is True


@pytest.mark.asyncio
async def test_ga4_connector_test_connection_oauth():
    """Verify GA4 connector test_connection returns CONNECTED and authenticated=True when OAuth credentials exist."""
    from app.connectors.google.ga4_connector import GoogleAnalytics4Connector
    from app.connectors.base.models import ConnectorCredentials
    from app.domain.enums import ConnectorType, ConnectorHealthStatus

    creds = ConnectorCredentials(
        provider=ConnectorType.GOOGLE_ANALYTICS_4,
        api_key=json.dumps({"type": "oauth2", "access_token": "ya29.sample_oauth_token", "property_id": "123456789"}),
    )
    connector = GoogleAnalytics4Connector(creds)
    health = await connector.test_connection()
    assert health.status == ConnectorHealthStatus.CONNECTED
    assert health.authenticated is True

