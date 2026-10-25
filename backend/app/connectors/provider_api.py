"""Provider-specific live authentication probes for integrations without legacy adapters.

This module deliberately separates an authenticated API handshake from business data
collection and publishing. A green handshake does not imply that every operation in the
provider directory is available to the connected account.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict
from urllib.parse import urlparse

import httpx

from app.connectors.base.interface import BaseConnector
from app.connectors.base.models import ConnectorCredentials, ConnectorHealth, PatchApplicationResult, RollbackResult
from app.domain.enums import ConnectorHealthStatus, ConnectorType
from app.domain.models import RemediationPatch


def _token(credentials: ConnectorCredentials) -> str | None:
    return (
        getattr(credentials, "access_token", None)
        or credentials.api_key
        or credentials.github_token
        or credentials.app_password
    )


def _origin(value: str | None, fallback: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        return fallback
    return f"{parsed.scheme}://{parsed.netloc}"


class ProviderApiConnector(BaseConnector):
    """Minimal, real provider API probes with explicit unsupported-write behavior."""

    def _probe(self, token: str) -> tuple[str, str, dict[str, str], dict[str, str], str]:
        provider = self.credentials.provider
        base = _origin(self.credentials.api_url, "")
        headers: dict[str, str] = {"Accept": "application/json"}
        params: dict[str, str] = {}
        method = "GET"
        body: dict[str, Any] | None = None
        url = ""
        if provider == ConnectorType.OPENAI_SEARCH:
            url = "https://api.openai.com/v1/models"
            headers["Authorization"] = f"Bearer {token}"
        elif provider == ConnectorType.PERPLEXITY:
            url = "https://api.perplexity.ai/models"
            headers["Authorization"] = f"Bearer {token}"
        elif provider == ConnectorType.CLAUDE:
            url = "https://api.anthropic.com/v1/models"
            headers.update({"x-api-key": token, "anthropic-version": "2023-06-01"})
        elif provider == ConnectorType.GEMINI:
            url = "https://generativelanguage.googleapis.com/v1beta/models"
            params["key"] = token
        elif provider == ConnectorType.HUBSPOT:
            url = "https://api.hubapi.com/crm/v3/objects/contacts"
            headers["Authorization"] = f"Bearer {token}"
            params["limit"] = "1"
        elif provider == ConnectorType.STRIPE:
            url = "https://api.stripe.com/v1/account"
            headers["Authorization"] = f"Bearer {token}"
        elif provider == ConnectorType.SLACK:
            url = "https://slack.com/api/auth.test"
            headers["Authorization"] = f"Bearer {token}"
        elif provider == ConnectorType.TELEGRAM:
            url = f"https://api.telegram.org/bot{token}/getMe"
        elif provider == ConnectorType.LINKEDIN:
            url = "https://api.linkedin.com/v2/userinfo"
            headers["Authorization"] = f"Bearer {token}"
        elif provider == ConnectorType.X:
            url = "https://api.x.com/2/users/me"
            headers["Authorization"] = f"Bearer {token}"
        elif provider == ConnectorType.TIKTOK:
            url = "https://open.tiktokapis.com/v2/user/info/"
            headers["Authorization"] = f"Bearer {token}"
            params["fields"] = "open_id,display_name"
        elif provider == ConnectorType.INSTAGRAM:
            url = "https://graph.facebook.com/v22.0/me"
            params.update({"fields": "id,username", "access_token": token})
        elif provider == ConnectorType.WHATSAPP_BUSINESS:
            phone_id = (self.credentials.repository or "").strip()
            if not phone_id:
                return "", "", {}, {}, "WhatsApp requires a Phone Number ID in the account/resource field."
            url = f"https://graph.facebook.com/v22.0/{phone_id}"
            params.update({"fields": "id,display_phone_number,verified_name", "access_token": token})
        elif provider == ConnectorType.SALESFORCE:
            if not base:
                return "", "", {}, {}, "Salesforce requires the authorized instance URL."
            url = f"{base}/services/data/v60.0/"
            headers["Authorization"] = f"Bearer {token}"
        elif provider == ConnectorType.SANITY:
            project_id = (self.credentials.repository or "").strip()
            dataset = (self.credentials.branch or "").strip()
            if not project_id or not dataset:
                return "", "", {}, {}, "Sanity requires project ID in repository and dataset in branch/resource."
            url = f"https://{project_id}.api.sanity.io/v2021-06-07/data/query/{dataset}"
            headers["Authorization"] = f"Bearer {token}"
            params["query"] = "*[_id == \"___dristik_connection_probe_never_exists\"][0]._id"
        elif provider == ConnectorType.FRAMER:
            return "", "", {}, {}, "Framer is not marked connected until its supported API capability and account access are configured."
        elif provider == ConnectorType.WIX:
            return "", "", {}, {}, "Wix requires an approved app/API token flow; no live probe is configured for this connection."
        else:
            return "", "", {}, {}, f"No provider-specific live API probe is registered for {provider.value}."

        return method, url, headers, params, ""

    async def test_connection(self) -> ConnectorHealth:
        provider = self.credentials.provider
        token = _token(self.credentials)
        if not token:
            return ConnectorHealth(
                provider=provider, status=ConnectorHealthStatus.DISCONNECTED,
                authenticated=False, message="Credentials are not configured; no provider request was sent.",
                permissions_missing=["provider credentials"],
            )
        method, url, headers, params, config_error = self._probe(token)
        if config_error:
            return ConnectorHealth(
                provider=provider, status=ConnectorHealthStatus.ERROR,
                authenticated=False, message=config_error,
                permissions_missing=["configured provider API capability"],
            )
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False) as client:
                response = await client.request(method, url, headers=headers, params=params)
            latency = round((time.perf_counter() - started) * 1000, 2)
            if response.status_code in (401, 403):
                status = ConnectorHealthStatus.UNAUTHORIZED
                authenticated = False
                message = f"Provider rejected credentials or permissions (HTTP {response.status_code})."
            elif response.status_code == 429:
                status = ConnectorHealthStatus.ERROR
                authenticated = False
                message = "Provider rate-limited the connection test; retry after its reset window."
            elif response.status_code >= 500:
                status = ConnectorHealthStatus.ERROR
                authenticated = False
                message = f"Provider service returned HTTP {response.status_code}."
            elif response.status_code >= 400:
                status = ConnectorHealthStatus.ERROR
                authenticated = False
                message = f"Provider API returned HTTP {response.status_code}; verify resource identifiers and granted scopes."
            else:
                payload: Any = {}
                try:
                    payload = response.json()
                except ValueError:
                    pass
                if provider == ConnectorType.SLACK and isinstance(payload, dict) and payload.get("ok") is False:
                    status = ConnectorHealthStatus.UNAUTHORIZED
                    authenticated = False
                    message = "Slack auth.test rejected the token or required scopes."
                elif provider == ConnectorType.TELEGRAM and isinstance(payload, dict) and payload.get("ok") is False:
                    status = ConnectorHealthStatus.UNAUTHORIZED
                    authenticated = False
                    message = "Telegram getMe rejected the bot token."
                else:
                    status = ConnectorHealthStatus.CONNECTED
                    authenticated = True
                    message = f"Live {provider.value} API handshake succeeded (HTTP {response.status_code})."
            return ConnectorHealth(
                provider=provider, status=status, latency_ms=latency,
                authenticated=authenticated, message=message,
                permissions_granted=["api_handshake"] if authenticated else [],
                permissions_missing=[] if authenticated else ["valid credentials and required scopes"],
            )
        except httpx.TimeoutException:
            return ConnectorHealth(
                provider=provider, status=ConnectorHealthStatus.ERROR,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                authenticated=False, message="Provider connection timed out after 15 seconds.",
                permissions_missing=["reachable provider API"],
            )
        except httpx.HTTPError as exc:
            return ConnectorHealth(
                provider=provider, status=ConnectorHealthStatus.ERROR,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                authenticated=False, message=f"Provider network error: {type(exc).__name__}.",
                permissions_missing=["reachable provider API"],
            )

    async def discover_site_structure(self) -> Dict[str, Any]:
        health = await self.test_connection()
        return {
            "provider": self.credentials.provider.value,
            "discovery_status": "AVAILABLE" if health.authenticated else "UNAVAILABLE",
            "health": health.model_dump(mode="json"),
            "resources": [],
            "message": "Handshake only. Resource discovery is not reported until a provider-specific read operation is implemented.",
        }

    async def preview_patch(self, patch: RemediationPatch) -> Dict[str, Any]:
        return {
            "supported": False, "patch_id": patch.patch_id,
            "provider": self.credentials.provider.value,
            "reason": "This provider adapter has no reviewed write mapping. No changes were sent.",
        }

    async def apply_patch(self, patch: RemediationPatch) -> PatchApplicationResult:
        return PatchApplicationResult(
            success=False, patch_id=patch.patch_id, provider=self.credentials.provider,
            applied_at=datetime.now(timezone.utc).isoformat(), target_resource=patch.target_url,
            message="Write operation is not implemented for this provider adapter; no request was sent.",
            rollback_supported=False,
        )

    async def rollback_patch(self, patch: RemediationPatch) -> RollbackResult:
        return RollbackResult(
            success=False, patch_id=patch.patch_id,
            rolled_back_at=datetime.now(timezone.utc).isoformat(),
            message="Rollback is unavailable because this adapter did not apply a write.",
        )
