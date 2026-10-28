"""Regression tests for the universal MCP audit control-plane contracts."""
from types import SimpleNamespace

from app.api.routes.integrations.universal_connect import (
    _citation_tracking_unavailable_payload,
    _pipeline_status_payload,
)


def test_pipeline_status_summarizes_existing_section_and_node_state():
    run = SimpleNamespace(
        website_url="https://example.test",
        status=SimpleNamespace(value="running"),
        progress_percentage=42,
    )
    section = SimpleNamespace(
        section_id="sec_seo",
        title="SEO",
        description="Search visibility checks",
        order=3,
        node_ids=["node_a", "node_b"],
    )
    graph = {
        "progress_percentage": 50,
        "completed_nodes": 1,
        "total_nodes": 2,
        "is_paused": False,
        "activity_events": [{"node_id": "node_b", "status": "running"}],
        "nodes": {
            "node_a": {"node_id": "node_a", "status": "completed"},
            "node_b": {"node_id": "node_b", "status": "running"},
        },
    }

    result = _pipeline_status_payload("run_test", run, graph, [section])

    assert result["analysis_id"] == "run_test"
    assert result["audit_status"] == "running"
    assert result["audit_progress_percentage"] == 42
    assert result["sections"][0]["status"] == "running"
    assert result["sections"][0]["completed_nodes"] == 1
    assert result["sections"][0]["total_nodes"] == 2
    assert result["recent_activity"] == graph["activity_events"]
    assert "process-local" in result["controller_state_scope"]


def test_pipeline_status_does_not_claim_completion_for_empty_controller_state():
    run = SimpleNamespace(
        website_url="https://example.test",
        status=SimpleNamespace(value="completed"),
        progress_percentage=100,
    )
    section = SimpleNamespace(
        section_id="sec_seo",
        title="SEO",
        description="Search visibility checks",
        order=3,
        node_ids=["node_a"],
    )

    result = _pipeline_status_payload(
        "run_test",
        run,
        {"nodes": {"node_a": {"node_id": "node_a", "status": "pending"}}},
        [section],
    )

    assert result["audit_status"] == "completed"
    assert result["sections"][0]["status"] == "pending"


def test_unconfigured_citation_tracking_never_fabricates_visibility_metrics():
    result = _citation_tracking_unavailable_payload(
        "https://Example.test/path",
        queries=["best example"],
        engines=["openai", "gemini"],
    )

    assert result["domain"] == "example.test"
    assert result["status"] == "NOT_CONFIGURED"
    assert result["metrics_available"] is False
    assert result["overall_citation_score"] is None
    assert result["engines"] == {}
    assert result["requested_queries"] == ["best example"]
    assert result["requested_engines"] == ["openai", "gemini"]
    assert "fabricated" in result["reason"]
