"""Seal Search Console and GA4 onto an audit, or an explicit status when they were not retrieved.

Zeros from a disconnected connector are not measurements. This module never
invents clicks, impressions, sessions, or landing pages.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

SEARCH_CONSOLE = "google_search_console"
ANALYTICS = "google_analytics_4"

_NOTICES = {
    SEARCH_CONSOLE: {
        "NOT_CONNECTED": "Google Search Console was not connected for this audit. Clicks, impressions, CTR, average position, queries, pages, and indexing coverage were not retrieved.",
        "NOT_AUTHORIZED": "Google Search Console authorization expired or was refused. Search performance was not retrieved.",
        "NO_DATA": "Google Search Console is connected, and the property returned no rows for this period.",
        "FETCH_FAILED": "The Search Console request failed. No clicks or impressions are shown.",
        "MEASURED": "Retrieved from Google Search Console for this audit.",
    },
    ANALYTICS: {
        "NOT_CONNECTED": "Google Analytics 4 was not connected for this audit. Sessions, landing pages, engagement, and conversions were not retrieved.",
        "NOT_AUTHORIZED": "Google Analytics authorization expired or was refused. Session data was not retrieved.",
        "NO_DATA": "Google Analytics is connected, and the property returned no sessions metric for this period.",
        "FETCH_FAILED": "The Google Analytics request failed. No sessions are shown.",
        "MEASURED": "Retrieved from Google Analytics 4 for this audit.",
    },
}


def _notice(source: str, state: str) -> str:
    return _NOTICES.get(source, {}).get(state, "This Google dataset was not retrieved.")


def _channel(source: str, state: str, **extra: Any) -> Dict[str, Any]:
    payload = {
        "state": state,
        "source": source,
        "notice": extra.pop("notice", None) or _notice(source, state),
    }
    for key, value in extra.items():
        if value is not None:
            payload[key] = value
    return payload


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _provenance(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").upper()


def _percent_points(value: Any) -> Optional[float]:
    number = _num(value)
    if number is None:
        return None
    if 0 <= number <= 1:
        return round(number * 100, 2)
    return round(number, 2)


def map_search_console(report: Any) -> Dict[str, Any]:
    """Map a Search Console attribution result to a status or measured values."""
    if isinstance(report, dict) and report.get("state") in _NOTICES[SEARCH_CONSOLE] and "status" not in report:
        return _channel(SEARCH_CONSOLE, str(report["state"]), property=report.get("property"), period=report.get("period"))
    if report is None:
        return _channel(SEARCH_CONSOLE, "NOT_CONNECTED")

    status = str(_get(report, "status") or "").lower()
    reason = str(_get(report, "reason") or "")
    message = str(_get(report, "connection_status_message") or "")
    provenance = _get(report, "provenance") or {}
    if not isinstance(provenance, dict):
        provenance = {}
    connected = bool(_get(report, "is_connected"))
    unauthorized = "401" in reason or "401" in message or "expired" in message.lower() or "unauthorized" in message.lower()

    if status == "authenticated" and connected and not unauthorized:
        keywords = list(_get(report, "top_ranking_keywords") or [])
        clicks = int(_num(_get(report, "total_monthly_clicks")) or 0)
        impressions = int(_num(_get(report, "total_monthly_impressions")) or 0)
        if not keywords and clicks == 0 and impressions == 0:
            return _channel(
                SEARCH_CONSOLE,
                "NO_DATA",
                property=provenance.get("property"),
                period=provenance.get("date_range"),
            )
        queries = []
        for item in keywords[:8]:
            queries.append({
                "query": _get(item, "query") or "",
                "page": _get(item, "target_page") or "",
                "clicks": int(_num(_get(item, "monthly_clicks")) or 0),
                "impressions": int(_num(_get(item, "monthly_impressions")) or 0),
                "ctr": _num(_get(item, "ctr_percentage")),
                "position": _num(_get(item, "current_position")),
            })
        return _channel(
            SEARCH_CONSOLE,
            "MEASURED",
            property=provenance.get("property") or _get(report, "domain"),
            period=provenance.get("date_range") or "28d",
            clicks=clicks,
            impressions=impressions,
            average_ctr=_num(_get(report, "average_ctr")),
            average_position=_num(_get(report, "average_position")),
            queries=queries,
        )
    if unauthorized:
        return _channel(SEARCH_CONSOLE, "NOT_AUTHORIZED")
    if status == "sync_error":
        return _channel(SEARCH_CONSOLE, "FETCH_FAILED")
    return _channel(SEARCH_CONSOLE, "NOT_CONNECTED")


def _metric_map(headers: List[Any], values: List[Any]) -> Dict[str, float]:
    parsed: Dict[str, float] = {}
    for name, cell in zip(headers, values):
        number = _num(cell.get("value") if isinstance(cell, dict) else None)
        if name and number is not None:
            parsed[str(name)] = number
    return parsed


def _analytics_from_payload(property_id: str, payload: Dict[str, Any], period: str = "last 30 days") -> Dict[str, Any]:
    headers = [item.get("name") for item in (payload.get("metricHeaders") or [])]
    dim_headers = [item.get("name") for item in (payload.get("dimensionHeaders") or [])]
    rows = payload.get("rows") or []
    page_idx = next((i for i, name in enumerate(dim_headers) if name in ("pagePath", "landingPagePlusQueryString")), None)
    totals = payload.get("totals") or []
    total_values = (totals[0].get("metricValues") if totals else None) or None
    if total_values:
        parsed = _metric_map(headers, total_values)
    elif page_idx is None:
        parsed = _metric_map(headers, (rows[0].get("metricValues") if rows else []) or [])
    else:
        parsed = {}
        for row in rows:
            for name, number in _metric_map(headers, row.get("metricValues") or []).items():
                parsed[name] = parsed.get(name, 0) + number
    landing_pages = []
    if page_idx is not None:
        for row in rows:
            dims = row.get("dimensionValues") or []
            metrics = _metric_map(headers, row.get("metricValues") or [])
            page = dims[page_idx].get("value") if page_idx < len(dims) and isinstance(dims[page_idx], dict) else None
            if not page:
                continue
            landing_pages.append({
                "page": page,
                "sessions": int(metrics["sessions"]) if metrics.get("sessions") is not None else None,
                "key_events": int(metrics["conversions"]) if metrics.get("conversions") is not None else None,
            })
    if "sessions" not in parsed:
        return _channel(ANALYTICS, "NO_DATA", property=property_id, period=period)
    sessions = int(parsed["sessions"])
    key_events = int(parsed["conversions"]) if "conversions" in parsed else None
    return _channel(
        ANALYTICS,
        "MEASURED",
        property=property_id,
        period=period,
        sessions=sessions,
        engagement_rate_pct=_percent_points(parsed.get("engagementRate")),
        bounce_rate_pct=_percent_points(parsed.get("bounceRate")),
        average_session_duration_sec=_num(parsed.get("averageSessionDuration")),
        conversions=key_events,
        key_events=key_events,
        landing_pages=landing_pages or None,
    )


def map_analytics(summary: Any) -> Dict[str, Any]:
    """Map a GA4 result to a status or measured values. Disconnected zeros are omitted."""
    if isinstance(summary, dict) and summary.get("state") == "PAYLOAD":
        return _analytics_from_payload(
            str(summary.get("property_id") or ""),
            summary.get("payload") or {},
            str(summary.get("period") or "last 30 days"),
        )
    if (
        isinstance(summary, dict)
        and summary.get("state") in _NOTICES[ANALYTICS]
        and summary.get("state") != "MEASURED"
        and "provenance" not in summary
    ):
        return _channel(
            ANALYTICS,
            str(summary["state"]),
            property=summary.get("property"),
            period=summary.get("period"),
        )
    if summary is None:
        return _channel(ANALYTICS, "NOT_CONNECTED")

    provenance = _provenance(_get(summary, "provenance"))
    notice = str(_get(summary, "status_notice") or _get(summary, "notice") or "")
    unauthorized = "401" in notice or "expired" in notice.lower() or "unauthorized" in notice.lower()
    property_id = _get(summary, "property_id") or _get(summary, "property")
    if provenance == "MEASURED" or _get(summary, "state") == "MEASURED":
        sessions = _num(_get(summary, "sessions_30d"))
        if sessions is None:
            sessions = _num(_get(summary, "sessions"))
        if sessions is None:
            return _channel(ANALYTICS, "NO_DATA", property=property_id, period="last 30 days")
        return _channel(
            ANALYTICS,
            "MEASURED",
            property=property_id,
            period=_get(summary, "period") or "last 30 days",
            sessions=int(sessions),
            engagement_rate_pct=_percent_points(_get(summary, "engagement_rate_pct") if _get(summary, "engagement_rate_pct") is not None else _get(summary, "engagement_rate")),
            bounce_rate_pct=_percent_points(_get(summary, "bounce_rate_pct") if _get(summary, "bounce_rate_pct") is not None else _get(summary, "bounce_rate")),
            average_session_duration_sec=_num(_get(summary, "avg_session_duration_sec") if _get(summary, "avg_session_duration_sec") is not None else _get(summary, "average_session_duration_sec")),
            conversions=(
                int(_num(_get(summary, "conversions") if _get(summary, "conversions") is not None else _get(summary, "conversions_count")))
                if (_get(summary, "conversions") is not None or _get(summary, "conversions_count") is not None)
                and _num(_get(summary, "conversions") if _get(summary, "conversions") is not None else _get(summary, "conversions_count")) is not None
                else None
            ),
            key_events=(
                int(_num(_get(summary, "key_events")))
                if _get(summary, "key_events") is not None
                else (
                    int(_num(_get(summary, "conversions") if _get(summary, "conversions") is not None else _get(summary, "conversions_count")))
                    if (_get(summary, "conversions") is not None or _get(summary, "conversions_count") is not None)
                    else None
                )
            ),
            landing_pages=_get(summary, "landing_pages") or None,
        )
    if unauthorized:
        return _channel(ANALYTICS, "NOT_AUTHORIZED")
    if provenance == "FAILED" or _get(summary, "state") == "FETCH_FAILED":
        return _channel(ANALYTICS, "FETCH_FAILED")
    return _channel(ANALYTICS, "NOT_CONNECTED")


def load_search_console(domain: str) -> Any:
    from app.intelligence.business.search_console import search_console_engine
    return search_console_engine.generate_search_attribution(domain)


def load_analytics(domain: str) -> Any:
    """Read a saved GA4 connection. A missing property or token stays NOT_CONNECTED."""
    try:
        from app.connectors.store import connector_store
        from app.domain.enums import ConnectorType
        from app.connectors.google.google_api import query_ga4_with_token, refresh_google_access_token

        for integ in connector_store.list_integrations():
            if getattr(integ, "provider", None) != ConnectorType.GOOGLE_ANALYTICS_4:
                continue
            connector = connector_store.get_connector(getattr(integ, "integration_id", ""))
            creds = getattr(connector, "credentials", None)
            raw = ""
            if creds is not None:
                raw = getattr(creds, "api_key", None) or getattr(creds, "app_password", None) or ""
            try:
                parsed = json.loads(raw) if raw else {}
            except (TypeError, ValueError):
                parsed = {}
            if not isinstance(parsed, dict):
                parsed = {}
            token = str(parsed.get("access_token") or "")
            refresh = str(parsed.get("refresh_token") or "")
            property_id = str(parsed.get("property_id") or "")
            settings = getattr(integ, "settings", None) or {}
            if not property_id and isinstance(settings, dict):
                property_id = str(settings.get("property_id") or "")
            if not token and not refresh:
                continue
            if not property_id:
                return {"state": "NOT_CONNECTED"}
            try:
                access = token or refresh_google_access_token(refresh)
                payload = query_ga4_with_token(access, property_id)
            except RuntimeError as exc:
                if refresh and "401" in str(exc):
                    try:
                        payload = query_ga4_with_token(refresh_google_access_token(refresh), property_id)
                    except RuntimeError as refresh_exc:
                        if "401" in str(refresh_exc):
                            return {"state": "NOT_AUTHORIZED"}
                        return {"state": "FETCH_FAILED"}
                elif "401" in str(exc):
                    return {"state": "NOT_AUTHORIZED"}
                else:
                    return {"state": "FETCH_FAILED"}
            return {"state": "PAYLOAD", "property_id": property_id, "payload": payload, "period": "last 30 days"}
    except Exception:
        logger.info("GA4 connector lookup failed")
        return {"state": "FETCH_FAILED"}

    try:
        from app.connectors.google.google_connectors import ga4_connector
        return ga4_connector.fetch_performance(domain)
    except Exception:
        logger.info("GA4 service-account lookup failed")
        return {"state": "FETCH_FAILED"}


def _guard(loader: Callable[[str], Any], domain: str, mapper: Callable[[Any], Dict[str, Any]], source: str) -> Dict[str, Any]:
    try:
        return mapper(loader(domain))
    except Exception:
        logger.info("%s seal failed", source)
        return _channel(source, "FETCH_FAILED")


def collect_google_performance(
    domain: str,
    search_console_loader: Optional[Callable[[str], Any]] = None,
    analytics_loader: Optional[Callable[[str], Any]] = None,
) -> Dict[str, Any]:
    """Return search_console and analytics channels. Never raises and never invents metrics."""
    return {
        "search_console": _guard(search_console_loader or load_search_console, domain, map_search_console, SEARCH_CONSOLE),
        "analytics": _guard(analytics_loader or load_analytics, domain, map_analytics, ANALYTICS),
    }
