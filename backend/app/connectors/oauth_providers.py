"""
One-click OAuth for connectors that publish a consent screen.

A provider is usable only when its client id and secret are set.
No token is invented, and saving a token does not invent metrics.
"""
import base64
import hashlib
import hmac
import html
import json
import urllib.parse
import logging
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx

from app.connectors.base.models import ConnectorCredentials
from app.connectors.store import connector_store
from app.core.config import settings
from app.domain.enums import ConnectorType, ConnectorHealthStatus
from app.identity.authorizer import UserIdentity
from app.identity.deps import get_current_user
from app.identity.security import SESSION_COOKIE
from app.identity.store import get_store

logger = logging.getLogger(__name__)

router = APIRouter()

_PUBLIC_BASE = "http://localhost:8000/api/v1/connectors/oauth/callback"


def _setting(name: str) -> str:
    return (getattr(settings, name, None) or "").strip()


def _callback(request: Optional[Request] = None) -> str:
    configured = _setting("OAUTH_REDIRECT_URI")
    if configured:
        if "localhost" in configured and settings.ENVIRONMENT.lower() == "production":
            raise HTTPException(status_code=503, detail="Set OAUTH_REDIRECT_URI to the canonical HTTPS production callback URL.")
        if "localhost" in configured and request and settings.ENVIRONMENT.lower() != "production":
            host = request.headers.get("x-forwarded-host") or request.headers.get("host")
            if host and not host.startswith("localhost") and not host.startswith("127.0.0.1"):
                scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
                return f"{scheme}://{host}/api/v1/connectors/oauth/callback"
        return configured
    if settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(status_code=503, detail="OAUTH_REDIRECT_URI must be configured in production.")
    if request:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if host:
            scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
            return f"{scheme}://{host}/api/v1/connectors/oauth/callback"
    return _PUBLIC_BASE


def google_redirect_uri(request: Optional[Request] = None) -> str:
    """Redirect URI Google will accept for this OAuth client.

    When GOOGLE_OAUTH_REDIRECT_URI is the external-authority callback, that
    value is the one registered in Google Cloud. Other connector providers
    keep using OAUTH_REDIRECT_URI.
    """
    configured = settings.registered_google_redirect_uri()
    if not configured:
        return _callback(request)
    if "localhost" in configured and settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(status_code=503, detail="Set GOOGLE_OAUTH_REDIRECT_URI to the canonical HTTPS production callback URL.")
    if "localhost" in configured and request is not None and settings.ENVIRONMENT.lower() != "production":
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if host and not host.startswith("localhost") and not host.startswith("127.0.0.1"):
            scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
            return f"{scheme}://{host}/api/v1/external-authority/oauth/callback"
    return configured


def peek_signed_state(state: str) -> Optional[Dict[str, Any]]:
    """Read an SSO or connector state. Returns None for external-authority states."""
    if not state or "." not in state:
        return None
    try:
        raw, sig = state.split(".", 1)
    except ValueError:
        return None
    auth_secret = (settings.AUTH_SECRET or "").encode()
    if not auth_secret:
        return None
    for secret in (auth_secret,):
        expected = hmac.new(secret, raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            continue
        try:
            data = json.loads(base64.urlsafe_b64decode(raw.encode()))
        except Exception:
            return None
        if isinstance(data, dict) and data.get("provider"):
            return data
        return None
    return None


PROVIDERS: Dict[str, Dict[str, Any]] = {
    "google_search_console": {
        "label": "Google Search Console",
        "connector": ConnectorType.GOOGLE_SEARCH_CONSOLE,
        "client_id": "GOOGLE_CLIENT_ID",
        "client_secret": "GOOGLE_CLIENT_SECRET",
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/webmasters.readonly openid email profile",
        "extra": {"access_type": "offline", "prompt": "consent"},
    },
    "google_analytics_4": {
        "label": "Google Analytics 4",
        "connector": ConnectorType.GOOGLE_ANALYTICS_4,
        "client_id": "GOOGLE_CLIENT_ID",
        "client_secret": "GOOGLE_CLIENT_SECRET",
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/analytics.readonly openid email",
        "extra": {"access_type": "offline", "prompt": "consent"},
    },
    "google_analytics": {
        "label": "Google Analytics",
        "connector": ConnectorType.GOOGLE_ANALYTICS_4,
        "client_id": "GOOGLE_CLIENT_ID",
        "client_secret": "GOOGLE_CLIENT_SECRET",
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/analytics.readonly openid email",
        "extra": {"access_type": "offline", "prompt": "consent"},
    },
    "github": {
        "label": "GitHub",
        "connector": ConnectorType.GITHUB,
        "client_id": "GITHUB_CLIENT_ID",
        "client_secret": "GITHUB_CLIENT_SECRET",
        "authorize": "https://github.com/login/oauth/authorize",
        "token": "https://github.com/login/oauth/access_token",
        "scope": "repo read:user",
    },
    "shopify": {
        "label": "Shopify",
        "connector": ConnectorType.SHOPIFY,
        "client_id": "SHOPIFY_CLIENT_ID",
        "client_secret": "SHOPIFY_CLIENT_SECRET",
        "scope": "read_content,read_themes",
        "needs_shop": True,
    },
    "webflow": {
        "label": "Webflow",
        "connector": ConnectorType.WEBFLOW,
        "client_id": "WEBFLOW_CLIENT_ID",
        "client_secret": "WEBFLOW_CLIENT_SECRET",
        "authorize": "https://webflow.com/oauth/authorize",
        "token": "https://api.webflow.com/oauth/access_token",
        "scope": "sites:read custom_code:read custom_code:write",
    },
    "hubspot": {
        "label": "HubSpot",
        "connector": ConnectorType.HUBSPOT,
        "client_id": "HUBSPOT_CLIENT_ID",
        "client_secret": "HUBSPOT_CLIENT_SECRET",
        "authorize": "https://app.hubspot.com/oauth/authorize",
        "token": "https://api.hubapi.com/oauth/v1/token",
        "scope": "oauth crm.objects.contacts.read crm.objects.deals.read",
    },
    "salesforce": {
        "label": "Salesforce",
        "connector": ConnectorType.SALESFORCE,
        "client_id": "SALESFORCE_CLIENT_ID",
        "client_secret": "SALESFORCE_CLIENT_SECRET",
        "authorize": "https://login.salesforce.com/services/oauth2/authorize",
        "token": "https://login.salesforce.com/services/oauth2/token",
        "scope": "api refresh_token",
    },
    "stripe": {
        "label": "Stripe",
        "connector": ConnectorType.STRIPE,
        "client_id": "STRIPE_CLIENT_ID",
        "client_secret": "STRIPE_CLIENT_SECRET",
        "authorize": "https://connect.stripe.com/oauth/authorize",
        "token": "https://connect.stripe.com/oauth/token",
        "scope": "read_only",
    },
    "linkedin": {
        "label": "LinkedIn",
        "connector": ConnectorType.LINKEDIN,
        "client_id": "LINKEDIN_CLIENT_ID",
        "client_secret": "LINKEDIN_CLIENT_SECRET",
        "authorize": "https://www.linkedin.com/oauth/v2/authorization",
        "token": "https://www.linkedin.com/oauth/v2/accessToken",
        "scope": "openid profile email w_member_social",
    },
    "slack": {
        "label": "Slack",
        "connector": ConnectorType.SLACK,
        "client_id": "SLACK_CLIENT_ID",
        "client_secret": "SLACK_CLIENT_SECRET",
        "authorize": "https://slack.com/oauth/v2/authorize",
        "token": "https://slack.com/api/oauth.v2.access",
        "scope": "chat:write users:read",
    },
    "instagram": {
        "label": "Instagram Professional",
        "connector": ConnectorType.INSTAGRAM,
        "client_id": "INSTAGRAM_CLIENT_ID",
        "client_secret": "INSTAGRAM_CLIENT_SECRET",
        "authorize": "https://www.facebook.com/v22.0/dialog/oauth",
        "token": "https://graph.facebook.com/v22.0/oauth/access_token",
        "scope": "instagram_basic,instagram_content_publish,instagram_manage_insights,pages_show_list,pages_read_engagement",
    },
    "whatsapp_business": {
        "label": "WhatsApp Business Platform",
        "connector": ConnectorType.WHATSAPP_BUSINESS,
        "client_id": "WHATSAPP_BUSINESS_CLIENT_ID",
        "client_secret": "WHATSAPP_BUSINESS_CLIENT_SECRET",
        "authorize": "https://www.facebook.com/v22.0/dialog/oauth",
        "token": "https://graph.facebook.com/v22.0/oauth/access_token",
        "scope": "whatsapp_business_management,whatsapp_business_messaging,business_management",
    },
    "wordpress": {
        "label": "WordPress.com",
        "connector": ConnectorType.WORDPRESS,
        "client_id": "WORDPRESS_CLIENT_ID",
        "client_secret": "WORDPRESS_CLIENT_SECRET",
        "authorize": "https://public-api.wordpress.com/oauth2/authorize",
        "token": "https://public-api.wordpress.com/oauth2/token",
        "scope": "global",
    },
}


def _sign(payload: Dict[str, str]) -> str:
    secret_value = settings.AUTH_SECRET or ""
    if len(secret_value) < 32 or secret_value == "dristik-dev-secret-change-me":
        raise HTTPException(status_code=503, detail="OAuth state signing requires a configured secret of at least 32 characters.")
    state_payload = dict(payload)
    state_payload["iat"] = str(int(time.time()))
    state_payload["nonce"] = secrets.token_urlsafe(24)
    raw = base64.urlsafe_b64encode(json.dumps(state_payload, separators=(",", ":")).encode()).decode()
    secret = secret_value.encode()
    sig = hmac.new(secret, raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def _unsign(state: str) -> Dict[str, str]:
    try:
        raw, sig = state.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="OAuth state is invalid.") from exc
    secret_value = settings.AUTH_SECRET or ""
    if len(secret_value) < 32 or secret_value == "dristik-dev-secret-change-me":
        raise HTTPException(status_code=503, detail="OAuth state signing requires a configured secret of at least 32 characters.")
    secret = secret_value.encode()
    expected = hmac.new(secret, raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="OAuth state signature does not match.")
    data = json.loads(base64.urlsafe_b64decode(raw.encode()))
    if not isinstance(data, dict) or "provider" not in data:
        raise HTTPException(status_code=400, detail="OAuth state is missing the provider.")
    try:
        issued_at = int(data.get("iat", "0"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="OAuth state timestamp is invalid.") from exc
    now = int(time.time())
    nonce = str(data.get("nonce") or "")
    if not nonce or issued_at > now + 60 or now - issued_at > 900:
        raise HTTPException(status_code=400, detail="OAuth state has expired or is incomplete.")
    if not connector_store.consume_oauth_nonce(nonce, issued_at + 900):
        raise HTTPException(status_code=400, detail="OAuth state was already used or has expired.")
    return {str(k): str(v) for k, v in data.items()}


def _state_signing_ready() -> bool:
    secret = settings.AUTH_SECRET or ""
    return len(secret) >= 32 and secret != "dristik-dev-secret-change-me"


def _configured(spec: Dict[str, Any]) -> bool:
    return bool(_setting(spec["client_id"]) and _setting(spec["client_secret"]) and _state_signing_ready())


def provider_status(request: Optional[Request] = None) -> Dict[str, Any]:
    redirect_uri = _callback(request)
    out = {}
    for key, spec in PROVIDERS.items():
        provider_redirect = google_redirect_uri(request) if key.startswith("google") else redirect_uri
        out[key] = {
            "label": spec["label"],
            "configured": _configured(spec),
            "client_id_env": spec["client_id"],
            "client_secret_env": spec["client_secret"],
            "redirect_uri": provider_redirect,
            "needs_shop": bool(spec.get("needs_shop")),
        }
    return {"redirect_uri": redirect_uri, "providers": out}


def _shop_host(shop: str) -> str:
    host = shop.replace("https://", "").replace("http://", "").split("/")[0].strip().lower()
    if host and "." not in host:
        host = f"{host}.myshopify.com"
    if not host.endswith(".myshopify.com"):
        raise HTTPException(status_code=400, detail="Shopify sign-in needs a storename.myshopify.com address.")
    return host


def _authorize_url(provider: str, state: str, shop: str, redirect_uri: Optional[str] = None) -> str:
    spec = PROVIDERS[provider]
    client_id = _setting(spec["client_id"])
    redirect_uri = redirect_uri or _callback()
    if spec.get("needs_shop"):
        host = _shop_host(shop)
        query = urllib.parse.urlencode({
            "client_id": client_id,
            "scope": spec["scope"],
            "redirect_uri": redirect_uri,
            "state": state,
        })
        return f"https://{host}/admin/oauth/authorize?{query}"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": spec["scope"],
        "state": state,
    }
    params.update(spec.get("extra") or {})
    return f"{spec['authorize']}?{urllib.parse.urlencode(params)}"


async def _exchange(provider: str, code: str, shop: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    spec = PROVIDERS[provider]
    client_id = _setting(spec["client_id"])
    client_secret = _setting(spec["client_secret"])
    redirect_uri = redirect_uri or _callback()
    if spec.get("needs_shop"):
        host = _shop_host(shop)
        url = f"https://{host}/admin/oauth/access_token"
        body = {"client_id": client_id, "client_secret": client_secret, "code": code}
    else:
        url = spec["token"]
        body = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        if provider in ("instagram", "whatsapp_business"):
            # Meta OAuth access-token exchange is a GET with query parameters.
            body.pop("grant_type", None)
            response = await client.get(url, params=body, headers=headers)
        else:
            response = await client.post(url, data=body, headers=headers)
    if not response.is_success:
        raise HTTPException(status_code=400, detail="The provider rejected the authorization code. No connector was saved.")
    try:
        data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The provider did not return a token. No connector was saved.") from exc
    token = data.get("access_token")
    if not token:
        raise HTTPException(status_code=400, detail="No access token was returned. No connector was saved.")
    return data


async def refresh_provider_credentials(provider: str, credentials: ConnectorCredentials) -> Dict[str, Any]:
    """Refresh OAuth credentials only for providers with a configured, supported refresh flow."""
    spec = PROVIDERS.get(provider)
    if spec is None:
        raise HTTPException(status_code=409, detail="This connection has no configured OAuth refresh adapter.")
    access_token = credentials.access_token
    refresh_token = credentials.refresh_token
    if not access_token and credentials.api_key:
        try:
            stored = json.loads(credentials.api_key)
            access_token = stored.get("access_token") if isinstance(stored, dict) else None
            refresh_token = refresh_token or (stored.get("refresh_token") if isinstance(stored, dict) else None)
        except (TypeError, ValueError):
            pass
    if provider in ("instagram", "whatsapp_business"):
        if not access_token:
            raise HTTPException(status_code=409, detail="Meta token is missing; reconnect the account.")
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": _setting(spec["client_id"]),
            "client_secret": _setting(spec["client_secret"]),
            "fb_exchange_token": access_token,
        }
        url = spec["token"]
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params, headers={"Accept": "application/json"})
    else:
        if not refresh_token:
            raise HTTPException(status_code=409, detail="No refresh token is available for this connection; reconnect it through OAuth.")
        body = {
            "client_id": _setting(spec["client_id"]),
            "client_secret": _setting(spec["client_secret"]),
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": _callback(),
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(spec["token"], data=body, headers={"Accept": "application/json"})
    if not response.is_success:
        raise HTTPException(status_code=502, detail="The provider rejected the refresh request. Reconnect the account and verify its app configuration.")
    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="The provider returned an invalid refresh response.") from exc
    if not data.get("access_token"):
        raise HTTPException(status_code=502, detail="The provider refresh response did not contain an access token.")
    return data


def _fallback_return(path: str) -> str:
    return (
        "<script>function done(){window.location.replace(%s);}setTimeout(done,600);</script>"
        % json.dumps(path)
    )


def _oauth_fail(detail: str) -> HTMLResponse:
    text = detail if isinstance(detail, str) and detail.strip() else "The connection was not saved."
    return _page(
        "Sign-in failed",
        html.escape(text),
        script=_fallback_return("/?connector=error&reason=rejected"),
        success=False,
    )


def _page(title: str, body: str, script: str = "", success: bool = True) -> HTMLResponse:
    safe_title = html.escape(title)
    icon = "✓" if success else "✕"
    icon_color = "#137547" if success else "#c53030"
    if not script:
        script = _fallback_return("/?connector=connected" if success else "/?connector=error")
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{safe_title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #1a202c;
      background: #f7fafc;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
      padding: 24px;
      box-sizing: border-box;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      padding: 36px 32px;
      max-width: 440px;
      width: 100%;
      text-align: center;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
    }}
    .icon {{
      font-size: 32px;
      line-height: 1;
      color: {icon_color};
      background: {'#f0fdf4' if success else '#fef2f2'};
      width: 56px;
      height: 56px;
      border-radius: 50%;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 16px;
      font-weight: bold;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 700;
      margin: 0 0 8px;
      color: #0f172a;
    }}
    p {{
      font-size: 13px;
      color: #475569;
      line-height: 1.5;
      margin: 0 0 20px;
    }}
    .hint {{
      font-size: 11px;
      color: #94a3b8;
      margin-bottom: 16px;
    }}
    button {{
      display: inline-block;
      background: #0f172a;
      color: #ffffff;
      text-decoration: none;
      border: none;
      padding: 10px 20px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s ease;
    }}
    button:hover {{
      background: #1e293b;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h1>{safe_title}</h1>
    <p>{body}</p>
    <div class="hint" id="status-hint">Returning to Dristik in this tab…</div>
    <button type="button" id="return-btn" onclick="done()">Return to Dashboard</button>
  </div>
  {script}
</body>
</html>""")


@router.get("/oauth/providers")
def list_oauth_providers(request: Request):
    return provider_status(request)


@router.get("/oauth/{provider}/authorize")
def oauth_authorize(
    provider: str,
    request: Request,
    domain: str = "",
    shop: str = "",
    property_id: str = "",
    repository: str = "",
    user: UserIdentity = Depends(get_current_user),
):
    spec = PROVIDERS.get(provider)
    if spec is None:
        raise HTTPException(status_code=404, detail="This connector has no OAuth sign-in.")
    if not _state_signing_ready():
        raise HTTPException(status_code=503, detail="OAuth state signing requires a configured secret of at least 32 characters.")
    if not _configured(spec):
        raise HTTPException(
            status_code=503,
            detail=f"Set {spec['client_id']} and {spec['client_secret']} in the backend env, then restart.",
        )
    redirect_uri = google_redirect_uri(request) if provider.startswith("google") else _callback(request)
    state = _sign({
        "provider": provider,
        "domain": domain,
        "shop": shop,
        "property_id": property_id,
        "repository": repository,
        "redirect_uri": redirect_uri,
        "org_id": user.org_id,
    })
    return RedirectResponse(_authorize_url(provider, state, shop, redirect_uri))


@router.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    shop: Optional[str] = None,
):
    if error:
        return _page(
            "Sign-in cancelled",
            html.escape(error),
            script=_fallback_return("/?connector=error&reason=cancelled"),
            success=False,
        )
    if not code or not state or code.startswith("mock_"):
        return _page(
            "Sign-in failed",
            "The consent screen did not return a real authorization code.",
            script=_fallback_return("/?connector=error&reason=missing"),
            success=False,
        )
    try:
        saved = _unsign(state)
    except HTTPException as exc:
        return _oauth_fail(str(exc.detail))
    provider = saved["provider"]
    spec = PROVIDERS.get(provider)
    if spec is None or not _configured(spec):
        return _page("Sign-in failed", "This OAuth provider is not configured.", success=False)
    shop_host = shop or saved.get("shop") or ""
    redirect_uri = saved.get("redirect_uri") or _callback(request)
    try:
        token_data = await _exchange(provider, code, shop_host, redirect_uri)
    except HTTPException as exc:
        return _oauth_fail(str(exc.detail))
    target = token_data.get("instance_url") or saved.get("domain") or shop_host or saved.get("repository") or spec["label"]

    discovered_prop = saved.get("property_id") or ""
    if provider in ("google_analytics_4", "google_analytics") and not discovered_prop:
        # Auto-discover GA4 property ID via Google Analytics Admin API
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                admin_res = await client.get(
                    "https://analyticsadmin.googleapis.com/v1beta/accountSummaries",
                    headers={"Authorization": f"Bearer {token_data.get('access_token')}"}
                )
                if admin_res.is_success:
                    admin_data = admin_res.json()
                    for acc in admin_data.get("accountSummaries", []):
                        for prop in acc.get("propertySummaries", []):
                            prop_name = str(prop.get("property") or "")
                            clean = prop_name.replace("properties/", "").strip()
                            display = str(prop.get("displayName") or "")
                            if not discovered_prop:
                                discovered_prop = clean
                            if target and target.lower() in display.lower():
                                discovered_prop = clean
                                break
        except Exception as exc:
            logger.warning("[GA4] Could not auto-discover properties via Admin API: %s", exc)

    token = request.cookies.get(SESSION_COOKIE)
    session_user = get_store().user_from_session(token) if token else None
    org_id = saved.get("org_id") or (session_user.org_id if session_user else "")
    if not org_id:
        return _page(
            "Sign-in required",
            "Connect a site from a signed-in workspace. Dristik did not store this token.",
            success=False,
        )

    team_data = token_data.get("team") if isinstance(token_data.get("team"), dict) else {}
    provider_account_id = token_data.get("team_id") or team_data.get("id") or token_data.get("account_id") or saved.get("account_id") or ""
    stored = {
        "type": "oauth2",
        "provider": provider,
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token") or "",
        "property_id": discovered_prop,
        "shop": shop_host,
        "repository": saved.get("repository") or "",
        "account_id": provider_account_id,
    }
    creds = ConnectorCredentials(
        provider=spec["connector"],
        api_url=target if str(target).startswith("http") else f"https://{target}",
        api_key=json.dumps(stored),
        access_token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        account_id=str(provider_account_id) if provider_account_id else None,
        github_token=token_data.get("access_token") if provider == "github" else None,
        repository=saved.get("repository") or None,
        scopes=(token_data.get("scope", "").replace(",", " ").split() if isinstance(token_data.get("scope", ""), str) else []),
    )
    integration = connector_store.add_integration(
        provider=spec["connector"],
        name=f"{spec['label']} ({target})",
        target_url=creds.api_url or target,
        credentials=creds,
        repository=saved.get("repository") or None,
        settings={"auth_mode": "oauth2", "oauth_provider": provider, "property_id": discovered_prop, "account_id": provider_account_id or None},
        org_id=org_id,
    )
    # Authorization is not the same as a working integration. Verify against the real API.
    connector = connector_store.get_connector_for_org(integration.integration_id, org_id)
    if not connector:
        integration.status = ConnectorHealthStatus.ERROR
        connector_store.persist(integration)
        connector_store.record_event(
            org_id=org_id, action="OAUTH_CALLBACK", result="ADAPTER_UNAVAILABLE",
            integration_id=integration.integration_id,
            details={"provider": provider, "token_received": True, "live_verification": "FAILED"},
        )
        return _page("Connection verification failed", "Authorization returned a token, but Dristik could not initialize the provider adapter. The connection was not marked connected.", success=False)

    health = await connector.test_connection()
    integration.status = health.status
    connector_store.persist(integration)
    connector_store.record_event(
        org_id=org_id, action="OAUTH_CALLBACK",
        result="SUCCESS" if health.authenticated else health.status.value.upper(),
        integration_id=integration.integration_id,
        details={"provider": provider, "token_received": True, "live_verification": "PASSED" if health.authenticated else "FAILED"},
    )
    if not health.authenticated:
        return _page(
            "Connection verification failed",
            "Authorization returned a token, but the provider API handshake did not pass: " + html.escape(health.message) + ". The connection remains unverified.",
            success=False,
        )

    # Sync singleton connector references if applicable
    if provider in ("google_analytics_4", "google_analytics"):
        try:
            from app.integrations.google_connectors import ga4_connector
            ga4_connector._connected = True
            if discovered_prop:
                ga4_connector.property_id = discovered_prop
        except Exception:
            pass
    elif provider == "google_search_console":
        try:
            from app.integrations.google_connectors import gsc_connector
            gsc_connector._connected = True
        except Exception:
            pass

    safe_target = html.escape(str(target))
    return_path = "/?connector=connected&provider=" + urllib.parse.quote(provider)
    script = """
    <script>
      function done() {
        window.location.replace(%s);
      }
      (function() {
        var payload = { type: 'OAUTH_SUCCESS', provider: %s, target: %s, timestamp: Date.now() };
        var gscPayload = { type: 'GSC_OAUTH_SUCCESS', domain: %s, provider: %s, timestamp: Date.now() };
        try {
          if (window.opener && !window.opener.closed) {
            window.opener.postMessage(payload, '*');
            window.opener.postMessage(gscPayload, '*');
          }
        } catch (e) {}
        try {
          var bc = new BroadcastChannel('dristik_connector_oauth');
          bc.postMessage(payload);
          bc.close();
        } catch (e) {}
        try {
          var bcGsc = new BroadcastChannel('dristik_gsc_auth');
          bcGsc.postMessage(gscPayload);
          bcGsc.close();
        } catch (e) {}
        try {
          localStorage.setItem('dristik_connector_oauth_sync', JSON.stringify(payload));
          localStorage.setItem('dristik_gsc_auth_sync', JSON.stringify(gscPayload));
        } catch (e) {}
        var closed = false;
        try {
          if (window.opener && !window.opener.closed) {
            window.close();
            closed = !!window.closed;
          }
        } catch (e) {}
        if (!closed) setTimeout(done, 400);
      })();
    </script>
    """ % (
        json.dumps(return_path),
        json.dumps(provider),
        json.dumps(safe_target),
        json.dumps(safe_target),
        json.dumps(spec["label"]),
    )
    return _page(
        "Connected",
        f"The {html.escape(spec['label'])} authorization for <strong>{safe_target}</strong> is verified and saved. "
        "Use the supported resource-read operations to retrieve live data. Other operations remain unavailable until their capability checks pass.",
        script,
        success=True,
    )
