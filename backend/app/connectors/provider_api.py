"""Provider-specific live authentication probes for integrations without legacy adapters.

This module deliberately separates an authenticated API handshake from business data
collection and publishing. A green handshake does not imply that every operation in the
provider directory is available to the connected account.
"""
from __future__ import annotations

import time
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict
from urllib.parse import urlparse

import httpx

from app.connectors.base.interface import BaseConnector
from app.connectors.base.models import ConnectorCredentials, ConnectorHealth, PatchApplicationResult, RollbackResult
from app.domain.enums import ConnectorHealthStatus, ConnectorType
from app.domain.models import RemediationPatch


def _token(credentials: ConnectorCredentials) -> str | None:
    direct = (
        getattr(credentials, "access_token", None)
        or credentials.github_token
        or credentials.app_password
    )
    if direct:
        return direct
    raw = credentials.api_key
    if not raw:
        return None
    try:
        stored = json.loads(raw)
        if isinstance(stored, dict):
            token = stored.get("access_token") or stored.get("token")
            if token:
                return str(token)
    except (TypeError, ValueError):
        pass
    return raw


def _origin(value: str | None, fallback: str) -> str:
    """Accept only HTTPS Salesforce instance hosts; never probe arbitrary user URLs."""
    raw = (value or "").strip()
    if not raw:
        return fallback
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host:
        return fallback
    if not (host == "salesforce.com" or host.endswith(".salesforce.com") or host == "salesforce.mil" or host.endswith(".salesforce.mil")):
        return fallback
    try:
        port = parsed.port
    except ValueError:
        return fallback
    return f"https://{host}" + (f":{port}" if port and port != 443 else "")


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
            url = "https://api.hubapi.com/crm/objects/2026-09/contacts"
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
            url = f"{base}/services/data/"
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
                provider=provider, status=ConnectorHealthStatus.UNAVAILABLE,
                authenticated=False, message=config_error,
                permissions_missing=["configured provider API capability"],
            )
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False) as client:
                response = await client.request(method, url, headers=headers, params=params)
            latency = round((time.perf_counter() - started) * 1000, 2)
            self._last_status_code = response.status_code
            self._last_endpoint = url.replace(token, "[REDACTED]")
            self._last_observed_at = datetime.now(timezone.utc).isoformat()
            try:
                self._last_payload = response.json()
            except ValueError:
                self._last_payload = None
            if response.status_code in (401, 403):
                status = ConnectorHealthStatus.AUTH_REQUIRED
                authenticated = False
                message = f"Provider rejected credentials or permissions (HTTP {response.status_code})."
            elif response.status_code == 429:
                status = ConnectorHealthStatus.DEGRADED
                authenticated = False
                message = "Provider rate-limited the connection test; retry after its reset window."
            elif response.status_code >= 500:
                status = ConnectorHealthStatus.DEGRADED
                authenticated = False
                message = f"Provider service returned HTTP {response.status_code}."
            elif response.status_code >= 300:
                status = ConnectorHealthStatus.ERROR
                authenticated = False
                message = f"Provider API returned HTTP {response.status_code}; redirects are not followed for credential safety."
            else:
                payload: Any = {}
                try:
                    payload = response.json()
                except ValueError:
                    pass
                if provider == ConnectorType.SLACK and isinstance(payload, dict) and payload.get("ok") is False:
                    status = ConnectorHealthStatus.AUTH_REQUIRED
                    authenticated = False
                    message = "Slack auth.test rejected the token or required scopes."
                elif provider == ConnectorType.TELEGRAM and isinstance(payload, dict) and payload.get("ok") is False:
                    status = ConnectorHealthStatus.AUTH_REQUIRED
                    authenticated = False
                    message = "Telegram getMe rejected the bot token."
                elif provider == ConnectorType.TIKTOK and isinstance(payload, dict) and isinstance(payload.get("error"), dict) and payload["error"].get("code") not in (None, "", "ok", "0"):
                    status = ConnectorHealthStatus.AUTH_REQUIRED
                    authenticated = False
                    message = "TikTok rejected the access token or required scopes."
                elif isinstance(payload, dict) and isinstance(payload.get("error"), dict):
                    status = ConnectorHealthStatus.ERROR
                    authenticated = False
                    message = "Provider returned an API-level error despite a successful HTTP status."
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
                provider=provider, status=ConnectorHealthStatus.DEGRADED,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                authenticated=False, message="Provider connection timed out after 15 seconds.",
                permissions_missing=["reachable provider API"],
            )
        except httpx.HTTPError as exc:
            return ConnectorHealth(
                provider=provider, status=ConnectorHealthStatus.DEGRADED,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                authenticated=False, message=f"Provider network error: {type(exc).__name__}.",
                permissions_missing=["reachable provider API"],
            )

    async def discover_site_structure(self) -> Dict[str, Any]:
        health = await self.test_connection()
        payload = getattr(self, "_last_payload", None)
        provider = self.credentials.provider
        resources: list[dict[str, Any]] = []
        if health.authenticated and isinstance(payload, dict):
            if provider in (ConnectorType.OPENAI_SEARCH, ConnectorType.PERPLEXITY, ConnectorType.CLAUDE):
                resources = [{"id": row.get("id"), "type": row.get("type")} for row in (payload.get("data") or [])[:100] if isinstance(row, dict)]
            elif provider == ConnectorType.GEMINI:
                resources = [{"id": row.get("name"), "supported_methods": row.get("supportedGenerationMethods", [])} for row in (payload.get("models") or [])[:100] if isinstance(row, dict)]
            elif provider == ConnectorType.HUBSPOT:
                resources = [{"id": row.get("id"), "available_fields": sorted((row.get("properties") or {}).keys())} for row in (payload.get("results") or [])[:25] if isinstance(row, dict)]
            elif provider == ConnectorType.SALESFORCE:
                resources = [{"name": row.get("name"), "label": row.get("label"), "queryable": row.get("queryable")} for row in (payload.get("sobjects") or [])[:100] if isinstance(row, dict)]
            elif provider == ConnectorType.STRIPE:
                resources = [{"account_id": payload.get("id"), "country": payload.get("country"), "default_currency": payload.get("default_currency"), "livemode": payload.get("livemode")}] if payload.get("id") else []
            elif provider == ConnectorType.LINKEDIN:
                resources = [{"id": payload.get("sub"), "name": payload.get("name"), "locale": payload.get("locale")}] if payload.get("sub") else []
            elif provider == ConnectorType.X:
                row = payload.get("data") or {}
                resources = [{"id": row.get("id"), "username": row.get("username"), "name": row.get("name")}] if row else []
            elif provider == ConnectorType.TIKTOK:
                row = (payload.get("data") or {}).get("user") or {}
                resources = [{"open_id": row.get("open_id"), "display_name": row.get("display_name")}] if row else []
            elif provider == ConnectorType.INSTAGRAM:
                resources = [{"id": payload.get("id"), "username": payload.get("username")}] if payload.get("id") else []
            elif provider == ConnectorType.WHATSAPP_BUSINESS:
                resources = [{"id": payload.get("id"), "display_phone_number": payload.get("display_phone_number"), "verified_name": payload.get("verified_name")}] if payload.get("id") else []
            elif provider == ConnectorType.TELEGRAM:
                row = payload.get("result") or {}
                resources = [{"id": row.get("id"), "is_bot": row.get("is_bot"), "username": row.get("username")}] if row else []
            elif provider == ConnectorType.SLACK and payload.get("ok"):
                resources = [{"team_id": payload.get("team_id"), "team": payload.get("team"), "user_id": payload.get("user_id"), "user": payload.get("user")}]
            elif provider == ConnectorType.SANITY:
                rows = payload.get("result")
                if isinstance(rows, list):
                    resources = [{"id": row.get("_id"), "type": row.get("_type"), "updated_at": row.get("_updatedAt")} for row in rows[:100] if isinstance(row, dict)]
                elif isinstance(rows, dict):
                    resources = [{"id": rows.get("_id"), "type": rows.get("_type")}]
        raw = json.dumps(payload, sort_keys=True, default=str) if payload is not None else ""
        evidence = {
            "source": getattr(self, "_last_endpoint", None),
            "observed_at": getattr(self, "_last_observed_at", None),
            "http_status": getattr(self, "_last_status_code", None),
            "response_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else None,
            "verification_status": "LIVE_API_RESPONSE" if health.authenticated else "UNVERIFIED",
        }
        return {
            "provider": provider.value,
            "discovery_status": "AVAILABLE" if health.authenticated else "UNAVAILABLE",
            "health": health.model_dump(mode="json"),
            "resources": resources,
            "resource_count": len(resources),
            "evidence": evidence,
            "message": "Resource summaries come from the live provider API response. A successful handshake does not prove unsupported writes or AI-search citation visibility.",
        }

    async def read_resource(self, resource: str, limit: int = 25) -> Dict[str, Any]:
        """Read a small allowlisted set of real CRM/CMS resources and attach response provenance."""
        provider = self.credentials.provider
        token = _token(self.credentials)
        bounded_limit = max(1, min(int(limit), 100))
        if not token:
            return {"status": "NOT_CONNECTED", "provider": provider.value, "resource": resource, "records": [], "message": "Credentials are not configured."}
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        params: dict[str, str] = {}
        url = ""
        if provider == ConnectorType.HUBSPOT:
            allowed = {
                "contacts": "firstname,lastname,email,createdate",
                "companies": "name,domain,industry,createdate",
                "deals": "dealname,dealstage,amount,closedate,createdate",
            }
            if resource not in allowed:
                return {"status": "NOT_SUPPORTED", "provider": provider.value, "resource": resource, "records": [], "message": "Allowed resources: contacts, companies, deals."}
            url = f"https://api.hubapi.com/crm/objects/2026-09/{resource}"
            params = {"limit": str(bounded_limit), "properties": allowed[resource]}
        elif provider == ConnectorType.STRIPE:
            allowed = {"customers", "subscriptions", "payment_intents"}
            if resource not in allowed:
                return {"status": "NOT_SUPPORTED", "provider": provider.value, "resource": resource, "records": [], "message": "Allowed resources: customers, subscriptions, payment_intents."}
            url = f"https://api.stripe.com/v1/{resource}"
            params = {"limit": str(min(bounded_limit, 100))}
        elif provider == ConnectorType.SALESFORCE:
            allowed = {
                "accounts": ("Account", "Id,Name,Industry,Website"),
                "leads": ("Lead", "Id,Name,Company,Status,CreatedDate"),
                "opportunities": ("Opportunity", "Id,Name,StageName,Amount,CloseDate"),
                "campaigns": ("Campaign", "Id,Name,Status,StartDate,EndDate"),
            }
            if resource not in allowed:
                return {"status": "NOT_SUPPORTED", "provider": provider.value, "resource": resource, "records": [], "message": "Allowed resources: accounts, leads, opportunities, campaigns."}
            base = _origin(self.credentials.api_url, "")
            if not base:
                return {"status": "UNAVAILABLE", "provider": provider.value, "resource": resource, "records": [], "message": "A valid Salesforce instance URL is required."}
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False) as client:
                    versions_response = await client.get(f"{base}/services/data/", headers=headers)
                    versions_response.raise_for_status()
                    versions = versions_response.json()
                    version_rows = [row for row in versions if isinstance(row, dict) and row.get("version")] if isinstance(versions, list) else []
                    if not version_rows:
                        return {"status": "UNAVAILABLE", "provider": provider.value, "resource": resource, "records": [], "message": "Salesforce did not return API version metadata."}
                    version = max(version_rows, key=lambda row: float(row["version"]))["version"]
                    object_name, fields = allowed[resource]
                    query = f"SELECT {fields} FROM {object_name} LIMIT {bounded_limit}"
                    url = f"{base}/services/data/v{version}/query"
                    params = {"q": query}
            except httpx.HTTPStatusError as exc:
                return {"status": "UNAVAILABLE", "provider": provider.value, "resource": resource, "records": [], "http_status": exc.response.status_code, "message": "Salesforce rejected the read request; check scopes and object permissions."}
            except (httpx.HTTPError, ValueError, KeyError):
                return {"status": "UNAVAILABLE", "provider": provider.value, "resource": resource, "records": [], "message": "Salesforce resource read failed."}
        elif provider == ConnectorType.SANITY and resource == "documents":
            project_id = (self.credentials.repository or "").strip()
            dataset = (self.credentials.branch or "").strip()
            if not project_id or not dataset:
                return {"status": "UNAVAILABLE", "provider": provider.value, "resource": resource, "records": [], "message": "Sanity project ID and dataset are required."}
            url = f"https://{project_id}.api.sanity.io/v2021-06-07/data/query/{dataset}"
            params = {"query": f"*[_type != \"sanity.imageAsset\"][0...{bounded_limit}]{{_id,_type,_updatedAt}}"}
            headers["Authorization"] = f"Bearer {token}"
        else:
            return {"status": "NOT_SUPPORTED", "provider": provider.value, "resource": resource, "records": [], "message": "This resource operation is not implemented for this provider."}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False) as client:
                response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            return {"status": "UNAVAILABLE", "provider": provider.value, "resource": resource, "records": [], "http_status": exc.response.status_code, "message": "Provider rejected the resource read; check credentials, scopes, and resource access."}
        except (httpx.HTTPError, ValueError):
            return {"status": "UNAVAILABLE", "provider": provider.value, "resource": resource, "records": [], "message": "Provider resource read failed."}
        if provider == ConnectorType.SANITY:
            rows = payload.get("result") or []
        elif provider == ConnectorType.SALESFORCE:
            rows = payload.get("records") or []
        else:
            rows = payload.get("results") or payload.get("data") or []
        records = [row for row in rows[:bounded_limit] if isinstance(row, dict)] if isinstance(rows, list) else []
        serialized = json.dumps(payload, sort_keys=True, default=str)
        observed_at = datetime.now(timezone.utc).isoformat()
        return {
            "status": "LIVE_DATA", "provider": provider.value, "resource": resource,
            "records": records, "resource_count": len(records), "observed_at": observed_at,
            "evidence": {
                "source": url, "http_status": response.status_code, "observed_at": observed_at,
                "response_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
                "verification_status": "LIVE_API_RESPONSE",
            },
        }

    async def perform_action(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute only explicitly mapped, user-confirmed provider actions."""
        provider = self.credentials.provider
        token = _token(self.credentials)
        if not token:
            return {"status": "NOT_CONNECTED", "provider": provider.value, "action": action, "message": "Credentials are not configured."}
        url = ""
        method = "POST"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body: Dict[str, Any] = {}
        if provider == ConnectorType.TELEGRAM and action == "send_message":
            if not payload.get("chat_id") or not payload.get("text"):
                return {"status": "INVALID_INPUT", "provider": provider.value, "action": action, "message": "chat_id and text are required."}
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            body = {"chat_id": str(payload["chat_id"]), "text": str(payload["text"])}
        elif provider == ConnectorType.SLACK and action == "post_message":
            if not payload.get("channel") or not payload.get("text"):
                return {"status": "INVALID_INPUT", "provider": provider.value, "action": action, "message": "channel and text are required."}
            url = "https://slack.com/api/chat.postMessage"
            body = {"channel": str(payload["channel"]), "text": str(payload["text"])}
        elif provider == ConnectorType.X and action == "publish_post":
            if not payload.get("text"):
                return {"status": "INVALID_INPUT", "provider": provider.value, "action": action, "message": "text is required."}
            url = "https://api.x.com/2/tweets"
            body = {"text": str(payload["text"])}
        elif provider == ConnectorType.WHATSAPP_BUSINESS and action == "send_template":
            phone_id = (self.credentials.repository or "").strip()
            if not phone_id or not payload.get("to") or not payload.get("template_name"):
                return {"status": "INVALID_INPUT", "provider": provider.value, "action": action, "message": "Phone Number ID, to, and an approved template_name are required."}
            url = f"https://graph.facebook.com/v22.0/{phone_id}/messages"
            headers["Authorization"] = f"Bearer {token}"
            body = {
                "messaging_product": "whatsapp", "to": str(payload["to"]), "type": "template",
                "template": {
                    "name": str(payload["template_name"]),
                    "language": {"code": str(payload.get("language_code") or "en_US")},
                    **({"components": payload["components"]} if isinstance(payload.get("components"), list) else {}),
                },
            }
        elif provider == ConnectorType.INSTAGRAM and action == "publish_image":
            account_id = str(getattr(self.credentials, "account_id", None) or self.credentials.repository or "").strip()
            media_url = str(payload.get("media_url") or "").strip()
            if not account_id or not media_url.startswith("https://"):
                return {"status": "INVALID_INPUT", "provider": provider.value, "action": action, "message": "Instagram Professional account ID and an HTTPS media_url are required."}
            if not media_url or not payload.get("media_url"):
                return {"status": "INVALID_INPUT", "provider": provider.value, "action": action, "message": "media_url is required."}
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0), follow_redirects=False) as client:
                    create = await client.post(
                        f"https://graph.facebook.com/v22.0/{account_id}/media", headers=headers,
                        data={"image_url": media_url, "caption": str(payload.get("caption") or ""), "access_token": token},
                    )
                    create.raise_for_status()
                    creation_id = create.json().get("id")
                    if not creation_id:
                        return {"status": "FAILED", "provider": provider.value, "action": action, "message": "Meta did not return a media container ID."}
                    publish = await client.post(
                        f"https://graph.facebook.com/v22.0/{account_id}/media_publish", headers=headers,
                        data={"creation_id": creation_id, "access_token": token},
                    )
                    publish.raise_for_status()
                    response_payload = publish.json()
                observed_at = datetime.now(timezone.utc).isoformat()
                serialized = json.dumps(response_payload, sort_keys=True, default=str)
                return {
                    "status": "SUCCEEDED" if response_payload.get("id") else "FAILED",
                    "provider": provider.value, "action": action, "external_id": response_payload.get("id"),
                    "observed_at": observed_at, "message": "Instagram media publish response received.",
                    "evidence": {"source": f"https://graph.facebook.com/v22.0/{account_id}/media_publish", "observed_at": observed_at, "http_status": publish.status_code, "response_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(), "verification_status": "PROVIDER_ACCEPTED"},
                }
            except httpx.HTTPStatusError as exc:
                return {"status": "FAILED", "provider": provider.value, "action": action, "http_status": exc.response.status_code, "message": "Instagram rejected the publish request; verify account type, permissions, media URL, and app review."}
            except httpx.HTTPError:
                return {"status": "UNKNOWN", "provider": provider.value, "action": action, "message": "Instagram request outcome is unknown after a network failure. Reconcile the provider account before retrying."}
        else:
            return {"status": "NOT_SUPPORTED", "provider": provider.value, "action": action, "message": "No reviewed action mapping exists for this provider/action pair; no request was sent."}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0), follow_redirects=False) as client:
                response = await client.request(method, url, headers=headers, json=body)
            try:
                response_payload = response.json()
            except ValueError:
                response_payload = {}
            observed_at = datetime.now(timezone.utc).isoformat()
            if response.status_code >= 300:
                return {"status": "FAILED", "provider": provider.value, "action": action, "http_status": response.status_code, "message": "Provider rejected the action; check scopes, account permissions, and required payload fields."}
            if provider == ConnectorType.TELEGRAM:
                accepted = response_payload.get("ok") is True
                result_obj = response_payload.get("result") or {}
                external_id = result_obj.get("message_id")
            elif provider == ConnectorType.SLACK:
                accepted = response_payload.get("ok") is True
                external_id = response_payload.get("ts")
            else:
                accepted = bool((response_payload.get("data") or {}).get("id"))
                external_id = (response_payload.get("data") or {}).get("id")
            serialized = json.dumps(response_payload, sort_keys=True, default=str)
            source = url.replace(token, "[REDACTED]") if provider == ConnectorType.TELEGRAM else url
            return {
                "status": "SUCCEEDED" if accepted else "FAILED", "provider": provider.value, "action": action,
                "external_id": external_id, "observed_at": observed_at,
                "http_status": response.status_code,
                "message": "Provider accepted the action." if accepted else "Provider API did not confirm acceptance.",
                "evidence": {"source": source, "observed_at": observed_at, "http_status": response.status_code, "response_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(), "verification_status": "PROVIDER_ACCEPTED" if accepted else "PROVIDER_REJECTED"},
            }
        except httpx.TimeoutException:
            return {"status": "UNKNOWN", "provider": provider.value, "action": action, "message": "Provider request timed out; reconcile the provider account before retrying with a new idempotency key."}
        except httpx.HTTPError:
            return {"status": "UNKNOWN", "provider": provider.value, "action": action, "message": "Provider request failed at the network layer; reconcile the provider account before retrying."}

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
