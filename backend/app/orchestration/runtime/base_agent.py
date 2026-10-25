"""
Dristik AI Base Agent Interface
Standard cognitive contract for all specialist agents.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.orchestration.cognition.blackboard import CognitiveBlackboard
from app.core.inference.model_router import ModelRouter
from app.domain.evidence.retriever import EvidenceRetriever
from app.domain.models import Claim, Observation
from app.domain.enums import Category, Severity, ClaimType

class BaseAgent(ABC):
    def __init__(self, agent_id: str, capability: str, model_router: ModelRouter):
        self.agent_id = agent_id
        self.capability = capability
        self.model_router = model_router

    @abstractmethod
    async def run(self, blackboard: CognitiveBlackboard) -> Dict[str, Any]:
        """
        Executes the agent task, reading from and writing to the blackboard.
        """
        pass

    def register_claim(
        self,
        blackboard: CognitiveBlackboard,
        statement: str,
        category: Category,
        severity: Severity = Severity.MEDIUM,
        claim_type: ClaimType = ClaimType.FACT,
        evidence_refs: Optional[List[str]] = None,
        confidence: float = 0.85,
        recommendation: Optional[str] = None,
        impact: int = 5,
        effort: int = 5
    ) -> Claim:
        claim = blackboard.claim_registry.register_claim(
            agent_id=self.agent_id,
            statement=statement,
            category=category,
            severity=severity,
            claim_type=claim_type,
            evidence_refs=evidence_refs,
            confidence=confidence,
            recommendation=recommendation,
            impact=impact,
            effort=effort
        )
        from app.orchestration.cognition.ground_truth import apply_ground_truth_to_claim
        from app.orchestration.cognition.finding_rubric import apply_rubric_to_claim
        apply_ground_truth_to_claim(claim, blackboard.evidence_store, blackboard.claim_registry)
        apply_rubric_to_claim(claim, blackboard.evidence_store)
        return claim
