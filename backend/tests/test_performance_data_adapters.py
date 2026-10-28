"""Unit tests for the real Google performance adapters; no network calls or API keys required."""
from app.api.routes.integrations.performance_data import (
    _crux_metrics,
    _public_web_target,
    fetch_crux,
    fetch_pagespeed,
)


def test_crux_without_key_is_explicitly_not_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_CRUX_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    result = __import__("asyncio").run(fetch_crux("https://example.com"))
    assert result["status"] == "NOT_CONFIGURED"
    assert result["metrics_available"] is False
    assert result["metrics"] == {}


def test_pagespeed_rejects_local_target_without_network(monkeypatch):
    result = __import__("asyncio").run(fetch_pagespeed("http://127.0.0.1/admin"))
    assert result["status"] == "INVALID_TARGET"
    assert result["metrics_available"] is False
    assert result["metrics"] == {}


def test_public_target_rejects_credentials_and_private_ip():
    for target in ("https://user:pass@example.com", "http://127.0.0.1", "http://192.168.1.10"):
        try:
            _public_web_target(target)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected target to be rejected: {target}")


def test_crux_normalizes_only_metrics_returned_by_google():
    result = _crux_metrics({
        "record": {
            "metrics": {
                "largest_contentful_paint": {
                    "percentiles": {"p75": 2100},
                    "histogram": [{"start": "0", "end": "2500", "density": 0.8}],
                    "category": "FAST",
                }
            }
        }
    })
    assert result["largest_contentful_paint"]["percentiles"]["p75"] == 2100
    assert result["largest_contentful_paint"]["category"] == "FAST"
    assert "interaction_to_next_paint" not in result


def test_google_search_without_credentials_is_not_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_CX", raising=False)
    result = __import__("asyncio").run(
        __import__("app.api.routes.integrations.performance_data", fromlist=["fetch_google_search"]).fetch_google_search("site:example.com")
    )
    assert result["status"] == "NOT_CONFIGURED"
    assert result["metrics_available"] is False
    assert result["results"] == []
    assert "not a guaranteed universal Google SERP" in result["reason"]
