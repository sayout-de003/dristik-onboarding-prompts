"""
Dristik AI Connectors API Routes
Endpoints for registering, managing, and inspecting external platform integrations
(WordPress, GitHub, Shopify, Webflow, Generic Website).
"""
import os
import json
import urllib.parse
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
import httpx

from app.domain.models import Integration
from app.domain.enums import ConnectorType, ConnectorHealthStatus
from app.identity.authorizer import Authorizer, UserIdentity
from app.identity.deps import get_current_user, require_permission
from app.connectors.base.models import ConnectorCredentials, ConnectorHealth
from app.core.config import settings
from app.connectors.store import connector_store
from app.connectors.oauth_providers import router as oauth_router
from app.connectors.platform_registry import registry_payload
from app.connectors.webhook_security import body_sha256, verify_meta_signature, verify_shared_secret, verify_slack_signature, webhook_event_key

router = APIRouter(prefix="/connectors", tags=["Platform Connectors"])
router.include_router(oauth_router)

@router.get("/webhooks/whatsapp/{integration_id}")
async def verify_whatsapp_webhook(integration_id: str, request: Request):
    """Meta webhook challenge verification for a specific tenant connection."""
    integration = connector_store.get_integration(integration_id)
    if not integration or integration.provider != ConnectorType.WHATSAPP_BUSINESS:
        raise HTTPException(status_code=404, detail="WhatsApp Business integration not found.")
    verify_token = settings.META_WEBHOOK_VERIFY_TOKEN or ""
    if not verify_token:
        raise HTTPException(status_code=503, detail="META_WEBHOOK_VERIFY_TOKEN is not configured.")
    mode = request.query_params.get("hub.mode", "")
    supplied = request.query_params.get("hub.verify_token", "")
    challenge = request.query_params.get("hub.challenge", "")
    if mode != "subscribe" or not challenge or not verify_shared_secret(verify_token, supplied):
        raise HTTPException(status_code=403, detail="Webhook verification challenge rejected.")
    return PlainTextResponse(challenge)


@router.post("/webhooks/slack/{integration_id}")
async def receive_slack_webhook(integration_id: str, request: Request):
    """Verify Slack signatures and deduplicate incoming events before acknowledging."""
    secret = settings.SLACK_SIGNING_SECRET or ""
    if not secret:
        raise HTTPException(status_code=503, detail="SLACK_SIGNING_SECRET is not configured.")
    raw_body = await request.body()
    timestamp = request.headers.get("x-slack-request-timestamp", "")
    signature = request.headers.get("x-slack-signature", "")
    if not verify_slack_signature(secret, timestamp, signature, raw_body):
        raise HTTPException(status_code=401, detail="Slack signature is invalid or stale.")
    integration = connector_store.get_integration(integration_id)
    if not integration or integration.provider != ConnectorType.SLACK:
        raise HTTPException(status_code=404, detail="Slack integration not found.")
    try:
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type:
            form = urllib.parse.parse_qs(raw_body.decode("utf-8", errors="replace"))
            raw_payload = (form.get("payload") or ["{}"])[0]
            payload = json.loads(raw_payload)
        else:
            payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="Slack webhook body is not valid JSON/form payload.")
    if isinstance(payload, dict) and payload.get("type") == "url_verification" and payload.get("challenge"):
        return {"challenge": payload["challenge"]}
    credentials = connector_store.get_credentials(integration_id)
    expected_team = (credentials.account_id if credentials else None) or (integration.settings or {}).get("account_id")
    event_payload = payload.get("event") if isinstance(payload, dict) and isinstance(payload.get("event"), dict) else {}
    team_payload = payload.get("team") if isinstance(payload, dict) and isinstance(payload.get("team"), dict) else {}
    actual_team = (payload.get("team_id") if isinstance(payload, dict) else None) or event_payload.get("team_id") or team_payload.get("id")
    if not expected_team:
        raise HTTPException(status_code=409, detail="Slack webhook cannot be tenant-bound until its authorized team ID is recorded.")
    if not actual_team or str(actual_team) != str(expected_team):
        raise HTTPException(status_code=403, detail="Slack webhook team does not match this integration.")
    event_type = str(payload.get("type") or (payload.get("event") or {}).get("type") or "unknown") if isinstance(payload, dict) else "unknown"
    event_key = webhook_event_key("slack", payload, raw_body)
    digest = body_sha256(raw_body)
    inserted = connector_store.record_webhook_event(integration.org_id, "slack", integration_id, event_key, event_type, digest)
    connector_store.record_event(
        org_id=integration.org_id, action="WEBHOOK_RECEIVED",
        result="VERIFIED" if inserted else "DUPLICATE",
        integration_id=integration_id,
        details={"provider": "slack", "event_type": event_type, "payload_sha256": digest},
    )
    return {"ok": True, "verified": True, "duplicate": not inserted}


@router.post("/webhooks/whatsapp/{integration_id}")
async def receive_whatsapp_webhook(integration_id: str, request: Request):
    """Verify Meta webhook signatures and deduplicate WhatsApp Business events."""
    secret = settings.META_APP_SECRET or ""
    if not secret:
        raise HTTPException(status_code=503, detail="META_APP_SECRET is not configured.")
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    if not verify_meta_signature(secret, signature, raw_body):
        raise HTTPException(status_code=401, detail="Meta webhook signature is invalid.")
    integration = connector_store.get_integration(integration_id)
    if not integration or integration.provider != ConnectorType.WHATSAPP_BUSINESS:
        raise HTTPException(status_code=404, detail="WhatsApp Business integration not found.")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Meta webhook body is not valid JSON.")
    credentials = connector_store.get_credentials(integration_id)
    expected_phone_id = (credentials.repository if credentials else None) or (credentials.account_id if credentials else None)
    phone_ids = []
    if isinstance(payload, dict):
        for entry in payload.get("entry") or []:
            if not isinstance(entry, dict):
                continue
            for change in entry.get("changes") or []:
                value = change.get("value") if isinstance(change, dict) else None
                metadata = value.get("metadata") if isinstance(value, dict) else None
                if isinstance(metadata, dict) and metadata.get("phone_number_id"):
                    phone_ids.append(str(metadata["phone_number_id"]))
    if not expected_phone_id:
        raise HTTPException(status_code=409, detail="WhatsApp webhook cannot be tenant-bound until its Phone Number ID is recorded.")
    if not phone_ids or str(expected_phone_id) not in phone_ids:
        raise HTTPException(status_code=403, detail="WhatsApp webhook phone number does not match this integration.")
    event_type = str(payload.get("object") or "unknown") if isinstance(payload, dict) else "unknown"
    event_key = webhook_event_key("whatsapp_business", payload, raw_body)
    digest = body_sha256(raw_body)
    inserted = connector_store.record_webhook_event(integration.org_id, "whatsapp_business", integration_id, event_key, event_type, digest)
    connector_store.record_event(
        org_id=integration.org_id, action="WEBHOOK_RECEIVED",
        result="VERIFIED" if inserted else "DUPLICATE",
        integration_id=integration_id,
        details={"provider": "whatsapp_business", "event_type": event_type, "payload_sha256": digest},
    )
    return {"ok": True, "verified": True, "duplicate": not inserted}


@router.post("/webhooks/telegram/{integration_id}")
async def receive_telegram_webhook(integration_id: str, request: Request):
    """Validate Telegram's configured secret-token header and deduplicate updates."""
    integration = connector_store.get_integration(integration_id)
    if not integration or integration.provider != ConnectorType.TELEGRAM:
        raise HTTPException(status_code=404, detail="Telegram integration not found.")
    credentials = connector_store.get_credentials(integration_id)
    expected_secret = credentials.webhook_secret if credentials else None
    if not expected_secret:
        raise HTTPException(status_code=503, detail="A Telegram webhook secret has not been configured for this connection.")
    supplied_secret = request.headers.get("x-telegram-bot-api-secret-token", "")
    if not verify_shared_secret(expected_secret, supplied_secret):
        raise HTTPException(status_code=401, detail="Telegram webhook secret token is invalid.")
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Telegram webhook body is not valid JSON.")
    event_type = "callback_query" if isinstance(payload, dict) and payload.get("callback_query") else ("message" if isinstance(payload, dict) and payload.get("message") else "unknown")
    event_key = webhook_event_key("telegram", payload, raw_body)
    digest = body_sha256(raw_body)
    inserted = connector_store.record_webhook_event(integration.org_id, "telegram", integration_id, event_key, event_type, digest)
    connector_store.record_event(
        org_id=integration.org_id, action="WEBHOOK_RECEIVED",
        result="VERIFIED" if inserted else "DUPLICATE",
        integration_id=integration_id,
        details={"provider": "telegram", "event_type": event_type, "payload_sha256": digest},
    )
    return {"ok": True, "verified": True, "duplicate": not inserted}


@router.get("/audit-events")
async def connector_audit_events(limit: int = 100, user: UserIdentity = Depends(get_current_user)):
    """Return connector lifecycle events for the current organization only."""
    if not Authorizer.can_perform(user, "mission:read"):
        raise HTTPException(status_code=403, detail="You do not have permission to view connector audit history.")
    return {"events": connector_store.list_events(user.org_id, limit=limit)}


@router.get("/registry")
async def connector_registry(user: UserIdentity = Depends(get_current_user)):
    """List all planned providers with honest adapter and per-organization connection state."""
    if not Authorizer.can_perform(user, "mission:read"):
        raise HTTPException(status_code=403, detail="You do not have permission to view connectors.")
    integrations = connector_store.list_integrations(org_id=user.org_id)
    by_provider = {}
    for integration in integrations:
        by_provider[integration.provider.value] = integration
    items = registry_payload()
    for item in items:
        integration = by_provider.get(item["id"])
        if integration:
            item["connection_status"] = integration.status.value.upper()
            item["integration_id"] = integration.integration_id
            item["last_synced_at"] = integration.last_synced_at
            item["target_url"] = integration.target_url
    return {"providers": items, "total": len(items)}


class ConnectorActionRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=80)
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    approval_confirmed: bool = False
    payload: Dict[str, Any] = Field(default_factory=dict)


class ConnectorCredentialUpdateRequest(BaseModel):
    name: Optional[str] = None
    target_url: Optional[str] = None
    api_url: Optional[str] = None
    username: Optional[str] = None
    app_password: Optional[str] = None
    api_key: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    account_id: Optional[str] = None
    project_id: Optional[str] = None
    github_token: Optional[str] = None
    repository: Optional[str] = None
    branch: Optional[str] = None
    scopes: Optional[List[str]] = None


class ConnectPlatformRequest(BaseModel):
    provider: ConnectorType
    name: str = Field(..., description="Friendly name for integration")
    target_url: str = Field(..., description="Target website or store URL")
    api_url: Optional[str] = None
    username: Optional[str] = None
    app_password: Optional[str] = None
    api_key: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    account_id: Optional[str] = None
    project_id: Optional[str] = None
    github_token: Optional[str] = None
    repository: Optional[str] = None
    branch: Optional[str] = "main"
    scopes: List[str] = Field(default_factory=list)
    org_id: str = "org_default"
    workspace_id: str = "ws_default"
    

class ConnectPlatformResponse(BaseModel):
    success: bool
    integration: Integration
    health: ConnectorHealth
    message: str

def _actor_id(user: UserIdentity) -> Optional[str]:
    value = getattr(user, "user_id", None) or getattr(user, "id", None) or getattr(user, "email", None)
    return str(value) if value is not None else None


def _owned_integration(integration_id: str, user: UserIdentity) -> Integration:
    integration = connector_store.get_integration(integration_id)
    if not integration or not Authorizer.can_access_org(user, integration.org_id):
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


@router.get("", response_model=List[Integration])
async def list_integrations(user: UserIdentity = Depends(get_current_user)):
    """List platform connectors for the caller's organization."""
    if not Authorizer.can_perform(user, "mission:read"):
        raise HTTPException(status_code=403, detail="You do not have permission to view connectors.")
    return connector_store.list_integrations(org_id=user.org_id)

@router.post("/connect", response_model=ConnectPlatformResponse)
async def connect_platform(
    req: ConnectPlatformRequest,
    user: UserIdentity = Depends(require_permission("patches:generate")),
):
    """Register and verify a new platform connector for the caller's organization."""
    req.org_id = user.org_id
    # Workspace identifiers supplied by clients are not trusted for authorization.
    req.workspace_id = str(getattr(user, "workspace_id", None) or "ws_default")
    api_key = req.api_key
    if req.provider == ConnectorType.CRUX and not (api_key and str(api_key).strip()):
        api_key = (
            settings.CRUX_API_KEY
            or os.getenv("CRUX_API_KEY")
            or os.getenv("PAGESPEED_API_KEY")
            or settings.GOOGLE_API_KEY
            or os.getenv("GOOGLE_API_KEY")
        )
        if not (api_key and str(api_key).strip()):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Google CrUX needs a Chrome UX Report API key. Set CRUX_API_KEY in the server environment, "
                    "or paste a key. The Google OAuth client id does not authorize CrUX."
                ),
            )
    creds = ConnectorCredentials(
        provider=req.provider,
        api_url=req.api_url or req.target_url,
        username=req.username,
        app_password=req.app_password,
        api_key=api_key,
        access_token=req.access_token,
        refresh_token=req.refresh_token,
        webhook_secret=req.webhook_secret,
        account_id=req.account_id,
        project_id=req.project_id,
        github_token=req.github_token,
        repository=req.repository,
        branch=req.branch or "main",
        scopes=[]  # Client-declared scopes are not evidence of provider-granted permissions.
    )

    integration = connector_store.add_integration(
        provider=req.provider,
        name=req.name,
        target_url=req.target_url,
        credentials=creds,
        repository=req.repository,
        branch=req.branch,
        org_id=req.org_id,
        workspace_id=req.workspace_id
    )

    connector = connector_store.get_connector(integration.integration_id)
    if not connector:
        raise HTTPException(status_code=500, detail="Failed to instantiate connector")

    health = await connector.test_connection()
    integration.status = health.status
    connector_store.persist(integration)
    connector_store.record_event(
        org_id=user.org_id, action="CONNECT_ATTEMPT",
        result="SUCCESS" if health.authenticated else health.status.value.upper(),
        integration_id=integration.integration_id, actor_id=_actor_id(user),
        details={"provider": req.provider.value, "authenticated": health.authenticated, "http_api_handshake": True},
    )

    if health.authenticated and req.provider in (ConnectorType.GOOGLE_ANALYTICS_4, ConnectorType.GOOGLE_ANALYTICS):
        try:
            from app.integrations.google_connectors import ga4_connector
            ga4_connector._connected = True
        except Exception:
            pass
    elif health.authenticated and req.provider == ConnectorType.GOOGLE_SEARCH_CONSOLE:
        try:
            from app.integrations.google_connectors import gsc_connector
            gsc_connector._connected = True
        except Exception:
            pass

    return ConnectPlatformResponse(
        success=health.authenticated,
        integration=integration,
        health=health,
        message=f"Connected to {req.provider.value.title()}: {health.message}"
    )

@router.put("/{integration_id}/credentials")
async def update_integration_credentials(
    integration_id: str,
    req: ConnectorCredentialUpdateRequest,
    user: UserIdentity = Depends(require_permission("patches:generate")),
):
    """Update encrypted credentials and immediately re-test the live provider API."""
    integration = _owned_integration(integration_id, user)
    existing = connector_store.get_credentials(integration_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Integration credentials not found")
    updates = req.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Provide at least one field to update.")
    previous_name = integration.name
    previous_target_url = integration.target_url
    if "name" in updates:
        integration.name = updates.pop("name")
    if "target_url" in updates:
        integration.target_url = updates.pop("target_url")
    credential_fields = {
        "api_url", "username", "app_password", "api_key", "access_token",
        "refresh_token", "webhook_secret", "account_id", "project_id", "github_token",
        "repository", "branch", "scopes",
    }
    credential_updates = {key: value for key, value in updates.items() if key in credential_fields}
    credentials = existing.model_copy(update=credential_updates)
    try:
        connector_store.update_credentials(integration_id, credentials)
        connector_store.persist(integration)
    except Exception as exc:
        integration.name = previous_name
        integration.target_url = previous_target_url
        connector_store.persist(integration)
        raise HTTPException(status_code=500, detail="Credential update could not be persisted; previous credentials were retained.") from exc
    connector = connector_store.get_connector_for_org(integration_id, user.org_id)
    if not connector:
        raise HTTPException(status_code=500, detail="Could not initialize connector after credential update.")
    health = await connector.test_connection()
    integration.status = health.status
    connector_store.persist(integration)
    connector_store.record_event(
        org_id=integration.org_id, action="UPDATE_CREDENTIALS",
        result="SUCCESS" if health.authenticated else health.status.value.upper(),
        integration_id=integration_id, actor_id=_actor_id(user),
        details={"provider": integration.provider.value, "authenticated": health.authenticated},
    )
    return {"success": health.authenticated, "integration": integration, "health": health}


@router.post("/{integration_id}/refresh")
async def refresh_integration_credentials(
    integration_id: str,
    user: UserIdentity = Depends(require_permission("patches:generate")),
):
    """Refresh OAuth credentials when the provider supports a refresh flow, then re-test."""
    integration = _owned_integration(integration_id, user)
    if (integration.settings or {}).get("auth_mode") != "oauth2":
        raise HTTPException(status_code=409, detail="This integration was not connected through the configured OAuth flow.")
    provider_key = str((integration.settings or {}).get("oauth_provider") or "")
    credentials = connector_store.get_credentials(integration_id)
    if credentials is None:
        raise HTTPException(status_code=404, detail="Integration credentials not found")
    from app.connectors.oauth_providers import refresh_provider_credentials
    token_data = await refresh_provider_credentials(provider_key, credentials)
    stored = {}
    if credentials.api_key:
        try:
            parsed = json.loads(credentials.api_key)
            if isinstance(parsed, dict):
                stored = parsed
        except (TypeError, ValueError):
            stored = {}
    stored.update({
        "type": "oauth2",
        "provider": provider_key,
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token") or credentials.refresh_token or stored.get("refresh_token") or "",
    })
    updated_credentials = credentials.model_copy(update={
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token") or credentials.refresh_token,
        "api_key": json.dumps(stored),
    })
    connector_store.update_credentials(integration_id, updated_credentials)
    connector = connector_store.get_connector_for_org(integration_id, user.org_id)
    if not connector:
        raise HTTPException(status_code=500, detail="Could not initialize connector after token refresh.")
    health = await connector.test_connection()
    integration.status = health.status
    connector_store.persist(integration)
    connector_store.record_event(
        org_id=integration.org_id, action="OAUTH_TOKEN_REFRESH",
        result="SUCCESS" if health.authenticated else health.status.value.upper(),
        integration_id=integration_id, actor_id=_actor_id(user),
        details={"provider": provider_key, "authenticated": health.authenticated},
    )
    return {"success": health.authenticated, "integration": integration, "health": health}


@router.post("/{integration_id}/reconnect")
async def reconnect_integration(
    integration_id: str,
    user: UserIdentity = Depends(require_permission("patches:generate")),
):
    """Run a fresh live provider handshake; never assume reconnect succeeded."""
    integration = _owned_integration(integration_id, user)
    connector = connector_store.get_connector_for_org(integration_id, user.org_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Integration not found")
    health = await connector.test_connection()
    integration.status = health.status
    connector_store.persist(integration)
    connector_store.record_event(
        org_id=integration.org_id, action="RECONNECT",
        result="SUCCESS" if health.authenticated else health.status.value.upper(),
        integration_id=integration_id, actor_id=_actor_id(user),
        details={"provider": integration.provider.value, "authenticated": health.authenticated},
    )
    return {"success": health.authenticated, "integration": integration, "health": health}


@router.post("/{integration_id}/revoke")
async def revoke_integration_credentials(
    integration_id: str,
    user: UserIdentity = Depends(require_permission("patches:generate")),
):
    """Remove local credentials; external token revocation depends on provider support."""
    integration = _owned_integration(integration_id, user)
    empty = ConnectorCredentials(provider=integration.provider, api_url=integration.target_url)
    connector_store.update_credentials(integration_id, empty)
    integration.status = ConnectorHealthStatus.DISCONNECTED
    connector_store.persist(integration)
    connector_store.record_event(
        org_id=integration.org_id, action="REVOKE_LOCAL_CREDENTIALS",
        result="SUCCESS", integration_id=integration_id, actor_id=_actor_id(user),
        details={"provider": integration.provider.value, "remote_revocation": "not_attempted"},
    )
    return {
        "success": True,
        "status": "DISCONNECTED",
        "message": "Local credentials removed. Revoke provider-issued OAuth/API credentials in the provider console unless a provider-specific remote revocation flow is documented.",
        "remote_revocation": "NOT_ATTEMPTED",
    }


@router.get("/{integration_id}/health", response_model=ConnectorHealth)
async def check_integration_health(integration_id: str, user: UserIdentity = Depends(get_current_user)):
    """Test live connectivity and health of a specific integration."""
    _owned_integration(integration_id, user)
    connector = connector_store.get_connector_for_org(integration_id, user.org_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Integration not found")
    health = await connector.test_connection()
    integration = connector_store.get_integration(integration_id)
    if integration:
        integration.status = health.status
        connector_store.persist(integration)
        connector_store.record_event(
            org_id=integration.org_id, action="HEALTH_CHECK",
            result="SUCCESS" if health.authenticated else health.status.value.upper(),
            integration_id=integration_id, actor_id=_actor_id(user),
            details={"provider": integration.provider.value, "authenticated": health.authenticated, "latency_ms": health.latency_ms},
        )
    return health

@router.get("/{integration_id}/discover", response_model=Dict[str, Any])
async def discover_integration_structure(integration_id: str, user: UserIdentity = Depends(get_current_user)):
    """Discover resources through the provider API and record non-secret provenance."""
    integration = _owned_integration(integration_id, user)
    connector = connector_store.get_connector_for_org(integration_id, user.org_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Integration not found")
    result = await connector.discover_site_structure()
    evidence = result.get("evidence") if isinstance(result, dict) else None
    connector_store.record_event(
        org_id=integration.org_id, action="RESOURCE_DISCOVERY",
        result=str(result.get("discovery_status", "COMPLETED")) if isinstance(result, dict) else "COMPLETED",
        integration_id=integration_id, actor_id=_actor_id(user),
        details={
            "provider": integration.provider.value,
            "resource_count": result.get("resource_count") if isinstance(result, dict) else None,
            "source": evidence.get("source") if isinstance(evidence, dict) else None,
            "observed_at": evidence.get("observed_at") if isinstance(evidence, dict) else None,
            "response_sha256": evidence.get("response_sha256") if isinstance(evidence, dict) else None,
            "verification_status": evidence.get("verification_status") if isinstance(evidence, dict) else "NOT_REPORTED",
        },
    )
    return result

@router.get("/{integration_id}/resources/{resource}")
async def read_connector_resource(
    integration_id: str,
    resource: str,
    limit: int = 25,
    user: UserIdentity = Depends(require_permission("mission:read")),
):
    """Read a provider-specific allowlisted resource and record response provenance."""
    integration = _owned_integration(integration_id, user)
    connector = connector_store.get_connector_for_org(integration_id, user.org_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Integration not found")
    reader = getattr(connector, "read_resource", None)
    if not callable(reader):
        raise HTTPException(
            status_code=501,
            detail="This provider has no registered resource-read operation. Its directory presence is not proof of support.",
        )
    result = await reader(resource, limit=limit)
    evidence = result.get("evidence") if isinstance(result, dict) else None
    status_label = str(result.get("status", "UNAVAILABLE")) if isinstance(result, dict) else "UNAVAILABLE"
    connector_store.record_event(
        org_id=integration.org_id, action="RESOURCE_READ",
        result=status_label, integration_id=integration_id, actor_id=_actor_id(user),
        details={
            "provider": integration.provider.value, "resource": resource,
            "limit": max(1, min(int(limit), 100)),
            "resource_count": result.get("resource_count") if isinstance(result, dict) else None,
            "source": evidence.get("source") if isinstance(evidence, dict) else None,
            "observed_at": evidence.get("observed_at") if isinstance(evidence, dict) else None,
            "response_sha256": evidence.get("response_sha256") if isinstance(evidence, dict) else None,
            "verification_status": evidence.get("verification_status") if isinstance(evidence, dict) else "NOT_REPORTED",
        },
    )
    return result


@router.post("/{integration_id}/actions")
async def execute_connector_action(
    integration_id: str,
    req: ConnectorActionRequest,
    user: UserIdentity = Depends(require_permission("patches:generate")),
):
    """Run an explicitly confirmed, idempotent provider action with a live preflight."""
    if not req.approval_confirmed:
        raise HTTPException(status_code=400, detail="Confirm this action explicitly before Dristik sends a provider write.")
    integration = _owned_integration(integration_id, user)
    connector = connector_store.get_connector_for_org(integration_id, user.org_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Integration not found")
    action_runner = getattr(connector, "perform_action", None)
    if not callable(action_runner):
        raise HTTPException(status_code=501, detail="No provider action adapter is registered for this integration.")
    reservation = connector_store.begin_action(user.org_id, integration_id, req.idempotency_key, req.action)
    if not reservation.get("created"):
        if reservation.get("action") != req.action:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for a different action.")
        if reservation.get("status") == "SUCCEEDED":
            return {"idempotent_replay": True, "result": reservation.get("result")}
        if reservation.get("status") == "RUNNING":
            raise HTTPException(status_code=409, detail="This action is already running; do not retry with a new key until its outcome is reconciled.")
        raise HTTPException(status_code=409, detail="This idempotency key already has a non-success outcome. Reconcile the provider state before starting a new action.")

    try:
        health = await connector.test_connection()
    except Exception as exc:
        result = {"status": "PREFLIGHT_FAILED", "provider": integration.provider.value, "action": req.action, "message": f"Live preflight raised {type(exc).__name__}; no action was sent."}
        connector_store.complete_action(user.org_id, integration_id, req.idempotency_key, "FAILED", result)
        connector_store.record_event(
            org_id=integration.org_id, action="PROVIDER_ACTION", result="PREFLIGHT_FAILED",
            integration_id=integration_id, actor_id=_actor_id(user),
            details={"provider": integration.provider.value, "action": req.action, "idempotency_key": req.idempotency_key},
        )
        raise HTTPException(status_code=502, detail=result["message"]) from exc
    integration.status = health.status
    connector_store.persist(integration)
    if not health.authenticated:
        result = {"status": "PREFLIGHT_FAILED", "provider": integration.provider.value, "action": req.action, "message": health.message}
        connector_store.complete_action(user.org_id, integration_id, req.idempotency_key, "FAILED", result)
        connector_store.record_event(
            org_id=integration.org_id, action="PROVIDER_ACTION", result="PREFLIGHT_FAILED",
            integration_id=integration_id, actor_id=_actor_id(user),
            details={"provider": integration.provider.value, "action": req.action, "idempotency_key": req.idempotency_key},
        )
        raise HTTPException(status_code=409, detail={"message": "Provider preflight failed; no action was sent.", "health": health.model_dump(mode="json")})

    try:
        result = await action_runner(req.action, req.payload)
    except Exception as exc:
        # The remote side effect may have happened before the exception. Persist UNKNOWN
        # and require reconciliation instead of silently inviting a duplicate retry.
        result = {
            "status": "UNKNOWN", "provider": integration.provider.value, "action": req.action,
            "message": f"Action outcome is unknown after {type(exc).__name__}; reconcile the provider before retrying.",
        }
    action_status = str(result.get("status", "FAILED")) if isinstance(result, dict) else "FAILED"
    durable_status = "SUCCEEDED" if action_status == "SUCCEEDED" else ("UNKNOWN" if action_status == "UNKNOWN" else "FAILED")
    safe_result = result if isinstance(result, dict) else {"status": "FAILED", "message": "Provider action returned an invalid response."}
    connector_store.complete_action(user.org_id, integration_id, req.idempotency_key, durable_status, safe_result)
    evidence = safe_result.get("evidence") if isinstance(safe_result, dict) else None
    connector_store.record_event(
        org_id=integration.org_id, action="PROVIDER_ACTION", result=durable_status,
        integration_id=integration_id, actor_id=_actor_id(user),
        details={
            "provider": integration.provider.value, "action": req.action,
            "idempotency_key": req.idempotency_key,
            "external_id": safe_result.get("external_id") if isinstance(safe_result, dict) else None,
            "response_sha256": evidence.get("response_sha256") if isinstance(evidence, dict) else None,
            "verification_status": evidence.get("verification_status") if isinstance(evidence, dict) else "NOT_REPORTED",
        },
    )
    return {"idempotent_replay": False, "result": safe_result}


@router.delete("/{integration_id}")
async def delete_integration(integration_id: str, user: UserIdentity = Depends(require_permission("patches:generate"))):
    """Disconnect and remove an integration owned by the caller's organization."""
    integration = _owned_integration(integration_id, user)
    connector_store.record_event(
        org_id=integration.org_id, action="DISCONNECT",
        result="REQUESTED", integration_id=integration_id, actor_id=_actor_id(user),
        details={"provider": integration.provider.value},
    )
    success = connector_store.delete_integration(integration_id)
    if not success:
        raise HTTPException(status_code=404, detail="Integration not found")
    return {"success": True, "message": f"Integration {integration_id} disconnected"}

@router.get("/wordpress/download-plugin")
async def download_wp_bridge_plugin():
    """Download the official Dristik WordPress Bridge Plugin as a .zip file."""
    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    php_code = """<?php
/**
 * Plugin Name: Dristik AI SEO & GEO Bridge
 * Plugin URI: https://dristik.ai
 * Description: Secure bridge allowing Dristik AI to read pages and inject Schema.org JSON-LD, metadata, and robots.txt directives.
 * Version: 1.0.0
 * Author: Dristik AI
 * License: GPL-2.0+
 */

if (!defined('ABSPATH')) exit;

class Dristik_Bridge_Plugin {
    const OPTION_KEY = 'dristik_bridge_api_key';

    public function __construct() {
        add_action('admin_menu', array($this, 'add_admin_menu'));
        add_action('rest_api_init', array($this, 'register_rest_routes'));
    }

    public function add_admin_menu() {
        add_options_page('Dristik AI Bridge', 'Dristik AI Bridge', 'manage_options', 'dristik-bridge', array($this, 'render_settings_page'));
    }

    public function render_settings_page() {
        if (!current_user_can('manage_options')) return;
        $key = get_option(self::OPTION_KEY);
        if (!$key) {
            $key = 'dstk_live_' . bin2hex(random_bytes(16));
            update_option(self::OPTION_KEY, $key);
        }
        ?>
        <div class="wrap">
            <h1>Dristik AI SEO &amp; GEO Bridge</h1>
            <p>Use this API Key in your Dristik Audit Dashboard to establish a secure 2-way connection without needing Application Passwords.</p>
            <table class="form-table">
                <tr>
                    <th scope="row">Bridge API Key</th>
                    <td>
                        <input type="text" readonly value="<?php echo esc_attr($key); ?>" class="regular-text" style="font-family: monospace; font-size: 14px;" onclick="this.select();" />
                        <p class="description">Copy and paste this key into Dristik &gt; Connectors &gt; WordPress.</p>
                    </td>
                </tr>
            </table>
        </div>
        <?php
    }

    public function register_rest_routes() {
        register_rest_route('dristik/v1', '/site', array(
            'methods' => 'GET',
            'callback' => array($this, 'get_site_info'),
            'permission_callback' => array($this, 'verify_key')
        ));
    }

    public function verify_key($request) {
        $header = $request->get_header('x-dristik-plugin-key');
        $stored = get_option(self::OPTION_KEY);
        return ($header && $stored && hash_equals($stored, $header));
    }

    public function get_site_info() {
        return array(
            'status' => 'connected',
            'plugin_version' => '1.0.0',
            'site_url' => get_site_url(),
            'site_name' => get_bloginfo('name'),
            'permissions_granted' => array('read_seo', 'update_schema', 'update_metadata', 'update_robots')
        );
    }
}

new Dristik_Bridge_Plugin();
"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dristik-bridge/dristik-bridge.php", php_code)
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=dristik-bridge.zip"}
    )

# =========================================================================
# Google Search Console 1-Click OAuth Flow
# =========================================================================
class GoogleOAuthQuickConnectRequest(BaseModel):
    domain: str
    property_url: Optional[str] = None
    account_email: Optional[str] = None

def _get_gsc_redirect_uri(request: Optional[Request] = None) -> str:
    configured = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI") or settings.GOOGLE_OAUTH_REDIRECT_URI
    if configured:
        if "localhost" in configured and request:
            host = request.headers.get("x-forwarded-host") or request.headers.get("host")
            if host and not host.startswith("localhost") and not host.startswith("127.0.0.1"):
                scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
                return f"{scheme}://{host}/api/v1/connectors/google/oauth/callback"
        return configured
    if request:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if host:
            scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
            return f"{scheme}://{host}/api/v1/connectors/google/oauth/callback"
    return "http://localhost:8000/api/v1/connectors/google/oauth/callback"


@router.get("/google/oauth/status")
async def google_oauth_status(request: Request, user: UserIdentity = Depends(get_current_user)):
    del user
    """Returns whether Google OAuth credentials are configured on the server."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID") or settings.GOOGLE_CLIENT_ID
    redirect_uri = _get_gsc_redirect_uri(request)
    return {
        "configured": bool(client_id),
        "client_id": (client_id[:8] + "...") if client_id else None,
        "redirect_uri": redirect_uri
    }

@router.get("/google/oauth/authorize")
async def google_oauth_authorize(
    request: Request,
    domain: str = "example.com",
    service: str = "search_console",
    provider: Optional[str] = None,
    user: UserIdentity = Depends(get_current_user),
):
    del user
    """
    Shared Google OAuth authorize route for Search Console and Google Analytics.
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID") or settings.GOOGLE_CLIENT_ID
    if not client_id:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET. Mock consent codes are not issued.",
        )
    clean_domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    target_provider = provider or ("google_analytics_4" if service in ("analytics", "ga4", "google_analytics", "google_analytics_4") else "google_search_console")
    return RedirectResponse(
        url=f"/api/v1/connectors/oauth/{target_provider}/authorize?domain={urllib.parse.quote(clean_domain)}",
        status_code=302,
    )

@router.get("/google_analytics/oauth/authorize")
async def google_analytics_oauth_authorize(
    request: Request,
    domain: str = "example.com",
    property_id: str = "",
    user: UserIdentity = Depends(get_current_user),
):
    del user
    client_id = os.environ.get("GOOGLE_CLIENT_ID") or settings.GOOGLE_CLIENT_ID
    if not client_id:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET. Mock consent codes are not issued.",
        )
    clean_domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    query_params = {"domain": clean_domain}
    if property_id:
        query_params["property_id"] = property_id
    query_str = urllib.parse.urlencode(query_params)
    return RedirectResponse(
        url=f"/api/v1/connectors/oauth/google_analytics_4/authorize?{query_str}",
        status_code=302,
    )

@router.get("/google/oauth/callback", response_class=HTMLResponse)
async def google_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """
    Handles Google OAuth redirect, exchanges code for tokens, and notifies window.opener.
    """
    target_domain = state or "example.com"
    target_domain = target_domain.replace("https://", "").replace("http://", "").split("/")[0]

    if error:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Google Authorization Failed</title></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 48px; background: #efe8dc; color: #1f3d36;">
            <div style="max-width: 480px; margin: 0 auto; background: #fbf7ee; border: 1px solid #dcd2c0; border-radius: 12px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.06);">
                <div style="font-size: 32px; margin-bottom: 12px;">✕</div>
                <h2 style="margin: 0 0 8px; font-size: 20px;">Authorization Cancelled</h2>
                <p style="color: #666; font-size: 14px; margin-bottom: 24px;">{error}</p>
                <button onclick="window.close()" style="background: #1f3d36; color: #fbf7ee; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600;">Close Window</button>
            </div>
        </body>
        </html>
        """, status_code=400)

    client_id = os.environ.get("GOOGLE_CLIENT_ID") or settings.GOOGLE_CLIENT_ID
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET") or settings.GOOGLE_CLIENT_SECRET
    redirect_uri = _get_gsc_redirect_uri(request)

    def _oauth_error(message: str) -> HTMLResponse:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>Google Authorization Failed</title></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 48px; background: #efe8dc; color: #1f3d36;">
            <div style="max-width: 480px; margin: 0 auto; background: #fbf7ee; border: 1px solid #dcd2c0; border-radius: 12px; padding: 32px;">
                <h2 style="margin: 0 0 8px; font-size: 20px;">Authorization Failed</h2>
                <p style="color: #666; font-size: 14px;">{message}</p>
            </div>
        </body>
        </html>
        """, status_code=400)

    if not code or code.startswith("mock_"):
        return _oauth_error("Mock OAuth codes are rejected. Complete the Google consent screen.")
    if not client_id or not client_secret:
        return _oauth_error("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required to exchange this code.")

    user_email = ""
    tokens = None
    try:
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri
                }
            )
            if not token_res.is_success:
                return _oauth_error("Google rejected the authorization code. No connector was saved.")
            token_data = token_res.json()
            access_token = token_data.get("access_token")
            if not access_token:
                return _oauth_error("Google did not return an access token. No connector was saved.")
            tokens = {
                "type": "oauth2",
                "domain": target_domain,
                "access_token": access_token,
                "refresh_token": token_data.get("refresh_token") or "",
                "email": "",
            }
            userinfo_res = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if userinfo_res.is_success:
                user_email = userinfo_res.json().get("email") or ""
                tokens["email"] = user_email
    except Exception as exc:
        return _oauth_error(f"Token exchange failed: {exc}")

    if not tokens or not tokens.get("access_token"):
        return _oauth_error("No access token was returned. No connector was saved.")

    # Save to connector store
    creds = ConnectorCredentials(
        provider=ConnectorType.GOOGLE_SEARCH_CONSOLE,
        api_url=f"https://{target_domain}",
        api_key=json.dumps(tokens)
    )
    integration = connector_store.add_integration(
        provider=ConnectorType.GOOGLE_SEARCH_CONSOLE,
        name=f"Google Search Console ({target_domain})",
        target_url=f"https://{target_domain}",
        credentials=creds,
        settings={"auth_mode": "oauth2", "email": user_email}
    )
    integration.status = ConnectorHealthStatus.CONNECTED
    connector_store.persist(integration)
    try:
        from app.integrations.google_connectors import gsc_connector
        gsc_connector._connected = True
    except Exception:
        pass

    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Google Search Console Connected</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 48px; background: #efe8dc; color: #1f3d36;">
        <div style="max-width: 480px; margin: 0 auto; background: #fbf7ee; border: 1px solid #dcd2c0; border-radius: 12px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.06);">
            <div style="font-size: 36px; margin-bottom: 12px; color: #137547;">✓</div>
            <h2 style="margin: 0 0 8px; font-size: 22px; font-weight: 700;">Google Search Console Connected!</h2>
            <p style="color: #4a5568; font-size: 13px; line-height: 1.5; margin-bottom: 20px;">
                Successfully authorized property for <strong>{target_domain}</strong> via Google OAuth (<code>{user_email}</code>).
            </p>
            <p id="close-msg" style="color: #718096; font-size: 12px;">Returning to Dristik in this tab…</p>
            <button id="close-btn" onclick="window.close()" style="display: none; margin-top: 14px; background: #137547; color: #fff; border: none; padding: 8px 18px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600;">Return to App</button>
        </div>
        <script>
            (function() {{
                var payload = {{
                    type: 'GSC_OAUTH_SUCCESS',
                    domain: '{target_domain}',
                    email: '{user_email}',
                    timestamp: Date.now()
                }};
                function finish() {{
                    window.location.replace('/?connector=connected&provider=google_search_console');
                }}
                try {{
                    if (window.opener && !window.opener.closed) {{
                        window.opener.postMessage(payload, '*');
                    }}
                }} catch (e) {{}}
                try {{
                    var bc = new BroadcastChannel('dristik_gsc_auth');
                    bc.postMessage(payload);
                    bc.close();
                }} catch (e) {{}}
                try {{
                    localStorage.setItem('dristik_gsc_auth_sync', JSON.stringify(payload));
                }} catch (e) {{}}
                var closed = false;
                try {{
                    if (window.opener && !window.opener.closed) {{
                        window.close();
                        closed = !!window.closed;
                    }}
                }} catch (e) {{}}
                var btn = document.getElementById('close-btn');
                if (btn) {{
                    btn.style.display = 'inline-block';
                    btn.onclick = finish;
                }}
                if (!closed) setTimeout(finish, 400);
            }})();
        </script>
    </body>
    </html>
    """)

@router.post("/google/oauth/quick-connect")
async def google_oauth_quick_connect(req: GoogleOAuthQuickConnectRequest):
    """Refuses to mint tokens. OAuth must go through Google's consent screen."""
    raise HTTPException(
        status_code=400,
        detail="Instant OAuth is disabled. Open /api/v1/connectors/google/oauth/authorize after setting GOOGLE_CLIENT_ID.",
    )

