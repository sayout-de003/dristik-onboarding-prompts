"""
Dristik Modular Monolith: AEO Domain Pillar.

Orchestrates direct answers, conversational intent, and entity consensus
within the Dristik multi-agent blackboard cognitive loop.
"""
from __future__ import annotations

from typing import Any, List, Optional, Set

from app.aeo.specialists import AEO_SPECIALISTS, build_aeo_agents
from app.cognition.blackboard import CognitiveBlackboard
from app.domain.models import Finding
from app.domain.pillar import PillarId, PillarScoreResult


class AeoPillar:
    pillar_id = PillarId.AEO
    domains: Set[str] = {"AI_SEARCH", "AEO"}

    def __init__(self, model_router: Any = None):
        self.model_router = model_router
        self.agents = build_aeo_agents(model_router)

    async def execute_wave(
        self,
        wave_index: int,
        blackboard: CognitiveBlackboard,
        active_agents: Set[str],
    ) -> List[Finding]:
        findings: List[Finding] = []
        for agent_id, agent in self.agents.items():
            if agent and agent_id in active_agents:
                res = await agent.run(blackboard)
                if isinstance(res, list):
                    findings.extend(res)
        return findings

    def calculate_pillar_score(
        self,
        findings: List[Finding],
        blackboard: Optional[CognitiveBlackboard] = None,
    ) -> PillarScoreResult:
        aeo_findings = [
            finding for finding in findings
            if getattr(finding, "pillar", None) == "aeo" or getattr(finding, "category", "") in self.domains
        ]
        count = len(aeo_findings)
        # Finding volume is not a quality/readiness measurement: a better detector
        # can discover more issues and otherwise make the audited site look worse.
        # Preserve the legacy numeric field for API compatibility, but explicitly
        # mark the score as unavailable instead of manufacturing a grade.
        return PillarScoreResult(
            pillar_id=self.pillar_id,
            score=0.0,
            grade="N/A",
            confidence=0.0,
            measured_findings_count=count,
            metrics={
                "findings_count": count,
                "score_status": "NOT_MEASURED",
                "score_reason": "AEO readiness must be calculated from the four-pillar measurement scorecard, not finding count.",
            },
        )


__all__ = [
    "AeoPillar",
    "AEO_SPECIALISTS",
    "build_aeo_agents",
]
