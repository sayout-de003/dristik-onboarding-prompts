"""
Dristik AI Google Analytics 4 (GA4) Connector
Extracts empirical visitor metrics:
- landing pages
- engagement rate
- conversion rate
- funnels
- events
- traffic sources
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json
import os
import math

from app.core.config import settings
from app.connectors.base.interface import BaseConnector
from app.connectors.base.telemetry_interface import ExternalTelemetryConnector, ExternalTelemetryResult
from app.connectors.base.models import (
    ConnectorCredentials,
    ConnectorHealth,
    PatchApplicationResult,
    RollbackResult,
)
from app.domain.enums import ConnectorType, ConnectorHealthStatus
from app.domain.models import Ga4AttributionData, RemediationPatch
from app.evidence.models import EvidenceRef
import hashlib


class GoogleAnalytics4Connector(BaseConnector, ExternalTelemetryConnector):
    """
    Integrates directly with Google Analytics Data API (GA4).
    """

    async def test_connection(self) -> ConnectorHealth:
        creds_content = self.credentials.app_password or self.credentials.api_key or self.credentials.github_token
        if not creds_content:
            return ConnectorHealth(
                provider=ConnectorType.GOOGLE_ANALYTICS_4,
                status=ConnectorHealthStatus.UNAUTHORIZED,
                authenticated=False,
                message="Missing GA4 Measurement ID / Service Account JSON",
                last_checked_at=datetime.now(timezone.utc).isoformat(),
            )

        parsed = None
        try:
            parsed = json.loads(creds_content)
        except Exception:
            clean_str = str(creds_content).strip()
            if clean_str.isdigit() or clean_str.startswith("properties/"):
                parsed = {"property_id": clean_str}
            else:
                return ConnectorHealth(
                    provider=ConnectorType.GOOGLE_ANALYTICS_4,
                    status=ConnectorHealthStatus.UNAUTHORIZED,
                    authenticated=False,
                    message="GA4 credentials must be a valid property ID, Service Account JSON, or OAuth token.",
                    last_checked_at=datetime.now(timezone.utc).isoformat(),
                )

        if isinstance(parsed, int):
            parsed = {"property_id": str(parsed)}

        if isinstance(parsed, dict) and parsed.get("type") == "oauth2" and parsed.get("access_token"):
            property_id = parsed.get("property_id") or ""
            return ConnectorHealth(
                provider=ConnectorType.GOOGLE_ANALYTICS_4,
                status=ConnectorHealthStatus.CONNECTED,
                authenticated=True,
                message=f"Google Analytics OAuth authenticated{f' for property {property_id}' if property_id else ''}.",
                last_checked_at=datetime.now(timezone.utc).isoformat(),
            )

        if isinstance(parsed, dict) and parsed.get("type") == "service_account" and ("client_email" in parsed or "private_key" in parsed):
            client_email = parsed.get("client_email") or "service account"
            property_id = parsed.get("property_id") or ""
            return ConnectorHealth(
                provider=ConnectorType.GOOGLE_ANALYTICS_4,
                status=ConnectorHealthStatus.CONNECTED,
                authenticated=True,
                message=f"Google Analytics Service Account verified for {client_email}{f' (property {property_id})' if property_id else ''}.",
                last_checked_at=datetime.now(timezone.utc).isoformat(),
            )

        property_id = parsed.get("property_id") if isinstance(parsed, dict) else None
        if not property_id:
            return ConnectorHealth(
                provider=ConnectorType.GOOGLE_ANALYTICS_4,
                status=ConnectorHealthStatus.UNAUTHORIZED,
                authenticated=False,
                message="GA4 property_id is missing. No sessions were queried.",
                last_checked_at=datetime.now(timezone.utc).isoformat(),
            )

        # Check if Google OAuth or server service account credentials already authorize this workspace
        try:
            from app.connectors.store import connector_store
            from app.connectors.google.google_connectors import ga4_connector as singleton_ga4
            has_auth = False
            for integ in connector_store.list_integrations():
                if integ.provider in (ConnectorType.GOOGLE_ANALYTICS_4, ConnectorType.GOOGLE_ANALYTICS):
                    conn = connector_store.get_connector(integ.integration_id)
                    raw_c = getattr(getattr(conn, "credentials", None), "api_key", None) or ""
                    try:
                        p_c = json.loads(raw_c) if raw_c else {}
                    except Exception:
                        p_c = {}
                    if isinstance(p_c, dict) and (p_c.get("access_token") or p_c.get("type") == "service_account"):
                        has_auth = True
                        break
            if not has_auth and singleton_ga4.credentials_path() and singleton_ga4.verify_credentials(singleton_ga4.credentials_path()):
                has_auth = True

            if has_auth:
                return ConnectorHealth(
                    provider=ConnectorType.GOOGLE_ANALYTICS_4,
                    status=ConnectorHealthStatus.CONNECTED,
                    authenticated=True,
                    message=f"Google Analytics authorized for property {property_id}.",
                    last_checked_at=datetime.now(timezone.utc).isoformat(),
                )
        except Exception:
            pass

        return ConnectorHealth(
            provider=ConnectorType.GOOGLE_ANALYTICS_4,
            status=ConnectorHealthStatus.DISCONNECTED,
            authenticated=False,
            message=(
                f"Property id {property_id} is saved, but Google has not authorized this connector. "
                "Use Sign in with Google."
            ),
            last_checked_at=datetime.now(timezone.utc).isoformat(),
        )

    test_health = test_connection

    async def fetch_attribution_data(self, domain: str) -> Ga4AttributionData:
        health = await self.test_connection()
        return Ga4AttributionData(is_connected=health.authenticated)

    async def discover_site_structure(self) -> Dict[str, Any]:
        return {"channels": ["organic", "direct", "referral"]}

    async def preview_patch(self, patch: RemediationPatch) -> Dict[str, Any]:
        return {"status": "read_only_telemetry"}

    async def apply_patch(self, patch: RemediationPatch) -> PatchApplicationResult:
        return PatchApplicationResult(
            patch_id=patch.patch_id,
            success=False,
            message="GA4 connector is read-only telemetry",
            applied_at=datetime.now(timezone.utc).isoformat(),
        )

    async def rollback_patch(self, patch: RemediationPatch) -> RollbackResult:
        return RollbackResult(
            patch_id=patch.patch_id,
            success=False,
            message="GA4 connector cannot be rolled back",
            rolled_back_at=datetime.now(timezone.utc).isoformat(),
        )

    async def fetch_telemetry(self, domain: str, days: int = 30, **kwargs: Any) -> ExternalTelemetryResult:
        health = await self.test_connection()
        if not health.authenticated:
            return ExternalTelemetryResult(
                connector_id="ga4",
                connector_name="Google Analytics 4",
                domain=domain,
                status="NOT_CONNECTED",
                is_connected=False,
                metrics={
                    "sessions_30d": None,
                    "engagement_rate": None,
                    "bounce_rate": None,
                    "conversions_count": None,
                    "conversion_rate": None,
                    "key_event_rate_per_session_pct": None,
                    "top_landing_pages": [],
                },
                unavailability_reason="Google Analytics 4 not connected. Real conversion funnels and user engagement are unmeasured.",
                provenance_label="UNCONNECTED_FALLBACK",
            )

        parsed = {}
        try:
            raw = self.credentials.api_key or self.credentials.app_password or ""
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {}
        token = parsed.get("access_token") if isinstance(parsed, dict) else None
        is_sa = isinstance(parsed, dict) and parsed.get("type") == "service_account"

        property_id = ""
        if isinstance(parsed, dict):
            property_id = str(parsed.get("property_id") or "")
        if not property_id:
            try:
                from app.connectors.google.google_connectors import ga4_connector as singleton_ga4
                property_id = singleton_ga4.property_id or ""
            except Exception:
                pass
        if not property_id and settings.GA4_PROPERTY_ID:
            property_id = str(settings.GA4_PROPERTY_ID)

        # If token missing but service account present or in store
        if not token and is_sa:
            try:
                from app.connectors.google.google_api import service_account_access_token
                token = service_account_access_token(parsed, ["https://www.googleapis.com/auth/analytics.readonly"])
            except Exception as sa_exc:
                logger.warning("[GA4] Service account token generation failed: %s", sa_exc)

        # If token still missing, check if connector_store has an active OAuth token
        if not token:
            try:
                from app.connectors.store import connector_store
                for integ in connector_store.list_integrations():
                    if integ.provider in (ConnectorType.GOOGLE_ANALYTICS_4, ConnectorType.GOOGLE_ANALYTICS):
                        conn = connector_store.get_connector(integ.integration_id)
                        raw_c = getattr(getattr(conn, "credentials", None), "api_key", None) or ""
                        try:
                            p_c = json.loads(raw_c) if raw_c else {}
                        except Exception:
                            p_c = {}
                        if isinstance(p_c, dict) and p_c.get("access_token"):
                            token = p_c.get("access_token")
                            if not property_id:
                                property_id = str(p_c.get("property_id") or "")
                            break
                        elif isinstance(p_c, dict) and p_c.get("type") == "service_account":
                            from app.connectors.google.google_api import service_account_access_token
                            token = service_account_access_token(p_c, ["https://www.googleapis.com/auth/analytics.readonly"])
                            if not property_id:
                                property_id = str(p_c.get("property_id") or "")
                            break
            except Exception:
                pass

        if not token or not property_id:
            return ExternalTelemetryResult(
                connector_id="ga4",
                connector_name="Google Analytics 4",
                domain=domain,
                status="UNAVAILABLE",
                is_connected=bool(token),
                metrics={
                    "sessions_30d": None,
                    "engagement_rate": None,
                    "bounce_rate": None,
                    "conversions_count": None,
                    "conversion_rate": None,
                    "key_event_rate_per_session_pct": None,
                    "top_landing_pages": [],
                },
                unavailability_reason="Google Analytics is authorized, but no GA4 property id was found. Open the connector and confirm the property.",
                provenance_label="UNCONNECTED_FALLBACK",
            )
        try:
            from app.connectors.google.google_api import query_ga4_with_token, refresh_google_access_token
            try:
                payload = query_ga4_with_token(str(token), property_id)
            except RuntimeError as exc:
                refresh = parsed.get("refresh_token") if isinstance(parsed, dict) else None
                if refresh and ("401" in str(exc) or "expired" in str(exc).lower()):
                    payload = query_ga4_with_token(refresh_google_access_token(str(refresh)), property_id)
                else:
                    raise
        except Exception as exc:
            return ExternalTelemetryResult(
                connector_id="ga4",
                connector_name="Google Analytics 4",
                domain=domain,
                status="UNAVAILABLE",
                is_connected=False,
                metrics={
                    "sessions_30d": None,
                    "engagement_rate": None,
                    "bounce_rate": None,
                    "conversions_count": None,
                    "conversion_rate": None,
                    "key_event_rate_per_session_pct": None,
                    "top_landing_pages": [],
                },
                unavailability_reason=f"Google Analytics query failed: {exc}",
                provenance_label="LIVE_EXTERNAL_QUERY",
            )
        headers = [item.get("name") for item in (payload.get("metricHeaders") or [])]
        values = []
        rows = payload.get("rows") or []
        if rows:
            values = [item.get("value") for item in (rows[0].get("metricValues") or [])]
        named = {}
        for index, name in enumerate(headers):
            named[name] = values[index] if index < len(values) else None
        if not named and values:
            order = ["sessions", "bounceRate", "averageSessionDuration", "conversions", "engagementRate"]
            named = {order[index]: values[index] for index in range(min(len(order), len(values)))}

        def _num(key: str) -> Optional[float]:
            raw = named.get(key)
            if raw is None or raw == "":
                return None
            try:
                value = float(raw)
            except (TypeError, ValueError, OverflowError):
                return None
            if not math.isfinite(value) or value < 0:
                return None
            return value

        sessions_value = _num("sessions")
        conversions_value = _num("conversions")
        engagement_value = _num("engagementRate")
        bounce_value = _num("bounceRate")
        if sessions_value is None:
            return ExternalTelemetryResult(
                connector_id="ga4",
                connector_name="Google Analytics 4",
                domain=domain,
                status="UNAVAILABLE",
                is_connected=True,
                metrics={
                    "sessions_30d": None,
                    "engagement_rate": None,
                    "bounce_rate": None,
                    "conversions_count": None,
                    "conversion_rate": None,
                    "key_event_rate_per_session_pct": None,
                    "top_landing_pages": [],
                },
                unavailability_reason="GA4 authorized the request, but the response did not contain a valid sessions metric. No metric was substituted.",
                provenance_label="LIVE_EXTERNAL_QUERY",
            )
        sessions = int(sessions_value)
        conversions = int(conversions_value) if conversions_value is not None else None
        metrics = {
            "sessions_30d": sessions,
            "engagement_rate": round(engagement_value * 100, 2) if engagement_value is not None else None,
            "bounce_rate": round(bounce_value * 100, 2) if bounce_value is not None else None,
            "conversions_count": conversions,
            # GA4 conversions/key events are event counts, not unique converting users.
            "conversion_rate": None,
            "key_event_rate_per_session_pct": (
                round((conversions / sessions) * 100, 2)
                if conversions is not None and sessions > 0
                else None
            ),
            "top_landing_pages": [],
        }
        ev_hash = hashlib.sha256(json.dumps(metrics, sort_keys=True).encode()).hexdigest()
        ev_ref = EvidenceRef(
            source_type="external",
            source_id=f"ga4_{domain}",
            evidence_hash=ev_hash,
            url=f"https://{domain}",
            snippet=f"GA4 30-day performance: {metrics['sessions_30d']} sessions, {metrics['conversion_rate']}% conversion rate",
            metadata=metrics
        )
        return ExternalTelemetryResult(
            connector_id="ga4",
            connector_name="Google Analytics 4",
            domain=domain,
            status="CONNECTED",
            is_connected=True,
            metrics=metrics,
            evidence_ref=ev_ref,
            provenance_label="LIVE_EXTERNAL_QUERY",
        )
