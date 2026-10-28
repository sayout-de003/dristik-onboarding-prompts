"""GEO readiness agent must not emit heuristic-only factual claims."""
import asyncio
from types import SimpleNamespace

from app.geo.agents.readiness_analyzer import GeoReadinessAgent


def test_readiness_agent_does_not_infer_from_heading_and_word_count():
    agent = GeoReadinessAgent()
    blackboard = SimpleNamespace(
        pages=[SimpleNamespace(h1=["About"], word_count=1200)],
        geo_readiness_report=None,
        geo_readiness=None,
    )
    result = asyncio.run(agent.run(blackboard))
    assert result["status"] == "UNMEASURED"
    assert result["claims"] == []
    assert result["observations"]["canonical_report_available"] is False


def test_readiness_agent_only_marks_canonical_measured_dimensions():
    agent = GeoReadinessAgent()
    blackboard = SimpleNamespace(
        pages=[],
        geo_readiness_report={
            "dimension_scores": {
                "content": {"score": 72, "is_measured": True},
                "visibility": {"score": None, "is_measured": False},
            },
            "interpretation_disclaimer": "Readiness is not live visibility.",
        },
    )
    result = asyncio.run(agent.run(blackboard))
    assert result["status"] == "completed"
    assert result["observations"]["measured_dimensions"] == 1
    assert result["claims"] == []
