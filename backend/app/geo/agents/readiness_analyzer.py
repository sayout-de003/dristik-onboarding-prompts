"""
Compatibility wrapper for the canonical GEO readiness evaluator.

This agent deliberately does not maintain a second, weaker readiness formula.
It surfaces the canonical report if the orchestration layer supplied one; otherwise
it reports that readiness is not measured and emits no unsupported factual claim.
"""
from typing import Any, Dict

from app.agents.runtime.base import BaseAgent
from app.cognition.blackboard import CognitiveBlackboard


class GeoReadinessAgent(BaseAgent):
    """Expose canonical evidence-backed GEO readiness without proxy scoring."""

    def __init__(self, model_router=None):
        super().__init__(
            agent_id="geo.readiness.v3",
            capability="geo_readiness",
            model_router=model_router,
        )

    async def run(self, blackboard: CognitiveBlackboard) -> Dict[str, Any]:
        pages = getattr(blackboard, "pages", []) or []
        canonical = (
            getattr(blackboard, "geo_readiness_report", None)
            or getattr(blackboard, "geo_readiness", None)
        )

        if canonical is not None:
            if hasattr(canonical, "model_dump"):
                payload = canonical.model_dump()
            elif isinstance(canonical, dict):
                payload = canonical
            else:
                payload = {}
            dimensions = payload.get("dimension_scores", {}) or {}
            measured = [
                item for item in dimensions.values()
                if isinstance(item, dict) and item.get("is_measured") is True
            ]
            status = "completed" if measured else "UNMEASURED"
            observations = {
                "total_analyzed_pages": len(pages),
                "readiness_status": status,
                "canonical_report_available": True,
                "measured_dimensions": len(measured),
                "dimension_scores": dimensions,
                "interpretation_disclaimer": payload.get(
                    "interpretation_disclaimer",
                    "Readiness is not a live AI citation or recommendation rank.",
                ),
            }
        else:
            status = "UNMEASURED"
            observations = {
                "total_analyzed_pages": len(pages),
                "readiness_status": "UNMEASURED",
                "canonical_report_available": False,
                "measurement_note": (
                    "No canonical GEO readiness report was provided to this compatibility "
                    "agent. Page length and heading presence are not sufficient to infer "
                    "AI extractability or live AI visibility."
                ),
            }

        return {
            "agent_id": self.agent_id,
            "domain": "geo",
            "specialty": "geo_readiness",
            "status": status,
            "observations": observations,
            "claims": [],
        }
