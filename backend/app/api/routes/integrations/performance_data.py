"""Real Google performance-data adapters (CrUX field data and PageSpeed/Lighthouse lab data).

These adapters deliberately return explicit unavailable/error states. They never synthesize
metrics, and keep field data separate from Lighthouse lab measurements.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.identity.authorizer import UserIdentity
from app.identity.deps import get_current_user

router = APIRouter(prefix="/integrations/performance", tags=["Real Performance Data"])


def _public_web_target(value: str, *, allow_path: bool = True) -> str:
    raw = value.strip()
    candidate = raw if "://" in raw else "https://" + raw
    parsed = urlsplit(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("A public HTTP(S) website URL or origin is required.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal", ".test")):
        raise ValueError("Private and local hostnames are not supported.")
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise ValueError("Private or non-public IP addresses are not supported.")
    except ValueError as exc:
        if "not supported" in str(exc):
            raise
        # Host is a DNS name, not an IP literal.
        try:
            answers = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except OSError as dns_exc:
            raise ValueError("Target hostname could not be resolved.") from dns_exc
        if not answers:
            raise ValueError("Target hostname could not be resolved.")
        for answer in answers:
            address = ipaddress.ip_address(answer[4][0])
            if not address.is_global:
                raise ValueError("Target resolves to a private or non-public address.")
    path = parsed.path if allow_path else ""
    return f"{parsed.scheme}://{parsed.netloc}{path}" + (("?" + parsed.query) if allow_path and parsed.query else "")


def _unavailable(provider: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"status": "NOT_CONFIGURED", "provider": provider, "metrics_available": False,
            "metrics": {}, "reason": reason, **extra}


def _error(provider: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"status": "PROVIDER_ERROR", "provider": provider, "metrics_available": False,
            "metrics": {}, "reason": reason, **extra}


def _crux_metrics(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for metric in data.get("record", {}).get("metrics", {}).items():
        name, value = metric
        if not isinstance(value, dict):
            continue
        histogram = value.get("histogram") or []
        percentiles = value.get("percentiles") or {}
        out[name] = {
            "percentiles": percentiles,
            "histogram": histogram,
            "category": value.get("category"),
        }
    return out


async def fetch_crux(origin: str, form_factor: str = "PHONE", url: str | None = None) -> dict[str, Any]:
    provider = "Chrome UX Report API"
    key = os.getenv("GOOGLE_CRUX_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return _unavailable(provider, "Set GOOGLE_CRUX_API_KEY (or GOOGLE_API_KEY) to enable real CrUX field data.")
    try:
        target = _public_web_target(url or origin, allow_path=bool(url))
    except ValueError as exc:
        return {"status": "INVALID_TARGET", "provider": provider, "metrics_available": False, "metrics": {}, "reason": str(exc)}
    body: dict[str, Any] = {"formFactor": form_factor.upper()}
    body["url" if url else "origin"] = target if url else _public_web_target(origin, allow_path=False)
    endpoint = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=5), follow_redirects=False) as client:
            response = await client.post(endpoint, params={"key": key}, json=body)
        if response.status_code == 404:
            return {"status": "DATA_UNAVAILABLE", "provider": provider, "metrics_available": False, "metrics": {},
                    "reason": "CrUX has no record for this URL/origin and form factor.", "target": body.get("url") or body.get("origin"), "form_factor": body["formFactor"]}
        if response.status_code in (401, 403):
            return _error(provider, "Google rejected the API key or its API permissions.", http_status=response.status_code)
        if response.status_code == 429:
            return _error(provider, "Google API quota or rate limit was reached.", http_status=429)
        response.raise_for_status()
        data = response.json()
        metrics = _crux_metrics(data)
        if not metrics:
            return {"status": "DATA_UNAVAILABLE", "provider": provider, "metrics_available": False, "metrics": {},
                    "reason": "Google returned no CrUX metrics for this target.", "target": body.get("url") or body.get("origin"), "form_factor": body["formFactor"]}
        return {"status": "VERIFIED_LIVE", "provider": provider, "metrics_available": True, "metrics": metrics,
                "target": body.get("url") or body.get("origin"), "form_factor": body["formFactor"],
                "collection_period": data.get("record", {}).get("collectionPeriod"),
                "retrieved_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
    except httpx.HTTPStatusError as exc:
        return _error(provider, "Google CrUX API returned an unsuccessful response.", http_status=exc.response.status_code)
    except (httpx.HTTPError, ValueError) as exc:
        return _error(provider, f"CrUX request failed ({type(exc).__name__}); no metrics were inferred.")


async def fetch_google_search(query: str, num: int = 10, start: int = 1) -> dict[str, Any]:
    """Query Google's Programmable Search JSON API; this is not a universal live-SERP rank tracker."""
    provider = "Google Programmable Search JSON API"
    key, cx = os.getenv("GOOGLE_CSE_API_KEY") or os.getenv("GOOGLE_API_KEY"), os.getenv("GOOGLE_CSE_CX")
    if not key or not cx:
        return _unavailable(provider, "Set GOOGLE_CSE_API_KEY (or GOOGLE_API_KEY) and GOOGLE_CSE_CX. This API returns configured Programmable Search results, not a guaranteed universal Google SERP.", results=[])
    clean_query = query.strip()
    if not clean_query:
        return {"status": "INVALID_REQUEST", "provider": provider, "metrics_available": False, "results": [], "reason": "query is required."}
    if len(clean_query) > 500:
        return {"status": "INVALID_REQUEST", "provider": provider, "metrics_available": False, "results": [], "reason": "query must be 500 characters or fewer."}
    num = max(1, min(int(num), 10))
    start = max(1, min(int(start), 91))
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=5), follow_redirects=False) as client:
            response = await client.get("https://www.googleapis.com/customsearch/v1", params={"key": key, "cx": cx, "q": clean_query, "num": num, "start": start})
        if response.status_code in (400, 401, 403):
            return _error(provider, "Google rejected the request, API key, search engine ID, or API access.", http_status=response.status_code)
        if response.status_code == 429:
            return _error(provider, "Google Programmable Search quota or rate limit was reached.", http_status=429)
        response.raise_for_status()
        data = response.json()
        items = data.get("items") or []
        return {
            "status": "VERIFIED_LIVE" if items else "DATA_UNAVAILABLE",
            "provider": provider,
            "data_kind": "PROGRAMMABLE_SEARCH_RESULTS_NOT_UNIVERSAL_SERP_RANKINGS",
            "metrics_available": bool(items),
            "query": clean_query,
            "total_results_estimate": (data.get("searchInformation") or {}).get("totalResults"),
            "results": [{"title": item.get("title"), "url": item.get("link"), "snippet": item.get("snippet"), "display_link": item.get("displayLink")} for item in items],
            "retrieved_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "reason": None if items else "Google returned no results for this configured Programmable Search Engine."
        }
    except httpx.HTTPStatusError as exc:
        return _error(provider, "Google Programmable Search API returned an unsuccessful response.", http_status=exc.response.status_code)
    except httpx.HTTPError as exc:
        return _error(provider, f"Google Search request failed ({type(exc).__name__}); no results were inferred.")


async def fetch_pagespeed(url: str, strategy: str = "mobile", categories: list[str] | None = None) -> dict[str, Any]:
    provider = "Google PageSpeed Insights API / Lighthouse"
    try:
        target = _public_web_target(url)
    except ValueError as exc:
        return {"status": "INVALID_TARGET", "provider": provider, "metrics_available": False, "metrics": {}, "reason": str(exc)}
    api_key = os.getenv("GOOGLE_PAGESPEED_API_KEY") or os.getenv("GOOGLE_API_KEY")
    params: dict[str, Any] = {"url": target, "strategy": strategy.upper()}
    for category in categories or ["PERFORMANCE", "ACCESSIBILITY", "BEST_PRACTICES", "SEO"]:
        params.setdefault("category", [])
        params["category"].append(category.lower())
    if api_key:
        params["key"] = api_key
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=8), follow_redirects=False) as client:
            response = await client.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed", params=params)
        if response.status_code == 429:
            return _error(provider, "Google PageSpeed API quota or rate limit was reached.", http_status=429)
        if response.status_code in (400, 403):
            return _error(provider, "Google PageSpeed rejected the request or API key.", http_status=response.status_code)
        response.raise_for_status()
        data = response.json()
        lighthouse = data.get("lighthouseResult") or {}
        audits = lighthouse.get("audits") or {}
        categories_out = {}
        for key, value in (lighthouse.get("categories") or {}).items():
            categories_out[key] = {"score": value.get("score"), "title": value.get("title")}
        metrics = {}
        for key in ("first-contentful-paint", "largest-contentful-paint", "speed-index", "total-blocking-time", "cumulative-layout-shift", "interactive"):
            item = audits.get(key)
            if item is not None:
                metrics[key] = {"numeric_value": item.get("numericValue"), "display_value": item.get("displayValue"),
                                "score": item.get("score"), "unit": item.get("numericUnit")}
        if not lighthouse:
            return {"status": "DATA_UNAVAILABLE", "provider": provider, "metrics_available": False, "metrics": {},
                    "reason": "Google returned no Lighthouse result."}
        return {"status": "VERIFIED_LIVE", "provider": provider, "metrics_available": True,
                "data_kind": "LAB_DATA_NOT_FIELD_DATA", "target": target, "strategy": strategy.lower(),
                "categories": categories_out, "metrics": metrics,
                "lighthouse_version": lighthouse.get("lighthouseVersion"),
                "fetch_time": lighthouse.get("fetchTime"), "retrieved_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
    except httpx.HTTPStatusError as exc:
        return _error(provider, "Google PageSpeed API returned an unsuccessful response.", http_status=exc.response.status_code)
    except (httpx.HTTPError, ValueError) as exc:
        return _error(provider, f"PageSpeed request failed ({type(exc).__name__}); no metrics were inferred.")


class CruxRequest(BaseModel):
    origin: str = Field(min_length=4, max_length=2048)
    url: str | None = Field(default=None, max_length=2048)
    form_factor: str = Field(default="PHONE", pattern="^(PHONE|DESKTOP|TABLET)$")


class PageSpeedRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    strategy: str = Field(default="mobile", pattern="^(mobile|desktop)$")
    categories: list[str] = Field(default_factory=lambda: ["performance", "accessibility", "best-practices", "seo"], max_length=4)


@router.get("/status")
async def performance_data_status(user: UserIdentity = Depends(get_current_user)):
    return {
        "crux": {"configured": bool(os.getenv("GOOGLE_CRUX_API_KEY") or os.getenv("GOOGLE_API_KEY")),
                 "provider": "Chrome UX Report API", "data_type": "field_data"},
        "pagespeed": {"configured": bool(os.getenv("GOOGLE_PAGESPEED_API_KEY") or os.getenv("GOOGLE_API_KEY")), "provider": "Google PageSpeed Insights API", "api_key_configured": bool(os.getenv("GOOGLE_PAGESPEED_API_KEY") or os.getenv("GOOGLE_API_KEY")), "can_attempt_without_key": True,
                      "data_type": "lighthouse_lab_data"},
        "google_programmable_search": {"configured": bool((os.getenv("GOOGLE_CSE_API_KEY") or os.getenv("GOOGLE_API_KEY")) and os.getenv("GOOGLE_CSE_CX")), "provider": "Google Programmable Search JSON API", "data_type": "configured_search_results_not_universal_serp"},
    }


@router.get("/google-search")
async def google_search_endpoint(q: str = Query(..., min_length=1, max_length=500),
                                 num: int = Query(10, ge=1, le=10),
                                 start: int = Query(1, ge=1, le=91),
                                 user: UserIdentity = Depends(get_current_user)):
    return await fetch_google_search(q, num, start)


@router.post("/crux")
async def crux_endpoint(body: CruxRequest, user: UserIdentity = Depends(get_current_user)):
    return await fetch_crux(body.origin, body.form_factor, body.url)


@router.post("/pagespeed")
async def pagespeed_endpoint(body: PageSpeedRequest, user: UserIdentity = Depends(get_current_user)):
    return await fetch_pagespeed(body.url, body.strategy, body.categories)
