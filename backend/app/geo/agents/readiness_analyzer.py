"""Compatibility wrapper for canonical, evidence-backed GEO readiness.

This agent does not infer extractability or live visibility from heading presence
or page length. It forwards a canonical readiness report when one is supplied;
otherwise it returns an explicit unmeasured state and no factual claims.
"""
from typing import Any, Dict

from app.agents.runtime.base import BaseAgent
from app.cognition.blackboard import CognitiveBlackboard


class GeoReadinessAgent(BaseAgent):
    """Expose canonical readiness without maintaining a second scoring formula."""

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

        if canonical is None:
            return {
                "agent_id": self.agent_id,
                "domain": "geo",
                "specialty": "geo_readiness",
                "status": "UNMEASURED",
                "observations": {
                    "total_analyzed_pages": len(pages),
                    "readiness_status": "UNMEASURED",
                    "canonical_report_available": False,
                    "measurement_note": (
                        "No canonical GEO readiness report was supplied. Heading presence "
                        "and word count alone do not establish answer extractability or live AI visibility."
                    ),
                },
                "claims": [],
            }

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

        return {
            "agent_id": self.agent_id,
            "domain": "geo",
            "specialty": "geo_readiness",
            "status": status,
            "observations": {
                "total_analyzed_pages": len(pages),
                "readiness_status": status,
                "canonical_report_available": True,
                "measured_dimensions": len(measured),
                "dimension_scores": dimensions,
                "interpretation_disclaimer": payload.get(
                    "interpretation_disclaimer",
                    "Readiness is not a live AI citation or recommendation rank.",
                ),
            },
            "claims": [],
        }
