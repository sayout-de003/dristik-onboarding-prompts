"""
Dristik AI Team Orchestrator & Dynamic Workforce Coordinator
Dynamically provisions reusable cognitive workers into task-specific teams,
routes capabilities to optimal execution tiers (Deterministic, SLM, Reasoning, High-Reasoning),
and coordinates parallel execution waves.
"""
import asyncio
from typing import Dict, Any, List, Optional
from app.core.inference.model_router import ModelRouter
from app.orchestration.cognition.blackboard import CognitiveBlackboard
from app.domain.capability import CAPABILITY_REGISTRY, CapabilityDomain, ExecutionTier
from app.domain.models import CrawlManifest
from app.orchestration.capability_router import CapabilityRouter
from app.orchestration.agent_pool import AgentPool
from app.orchestration.runtime.registry import CAPABILITY_AGENT_MAP
from app.workers.extractor_worker import CognitiveExtractorWorker
from app.workers.analyst_worker import CognitiveAnalystWorker
from app.workers.research_worker import CognitiveResearchWorker
from app.workers.critic_worker import CognitiveCriticWorker
from app.workers.strategist_worker import CognitiveStrategistWorker
from app.workers.simulator_worker import CognitiveSimulatorWorker
from app.workers.synthesizer_worker import CognitiveSynthesizerWorker
from app.workers.remediation_worker import CognitiveRemediationWorker

class TeamOrchestrator:
    """
    Manages the 105 specialist agents across 12 domains (via AgentPool) plus cognitive workers for synthesis/remediation.
    """

    def __init__(self, model_router: ModelRouter):
        self.model_router = model_router
        self.capability_router = CapabilityRouter()

        # Dynamic Workforce
        self.worker_extractor = CognitiveExtractorWorker("worker_extractor", model_router)
        self.worker_analyst_1 = CognitiveAnalystWorker("worker_analyst_1", model_router)
        self.worker_analyst_2 = CognitiveAnalystWorker("worker_analyst_2", model_router)
        self.worker_researcher = CognitiveResearchWorker("worker_researcher", model_router)
        self.worker_critic = CognitiveCriticWorker("worker_critic", model_router)
        self.worker_strategist = CognitiveStrategistWorker("worker_strategist", model_router)
        self.worker_simulator = CognitiveSimulatorWorker("worker_simulator", model_router)
        self.worker_synthesizer = CognitiveSynthesizerWorker("worker_synthesizer", model_router)
        self.worker_remediation = CognitiveRemediationWorker("worker_remediation", model_router)
        self.agent_pool = AgentPool(model_router)

    def assign_worker_for_capability(self, capability_id: str):
        """
        Dynamically maps capability to the specialized worker role.
        """
        spec = CAPABILITY_REGISTRY.get(capability_id)
        if not spec:
            return self.worker_analyst_1

        if spec.domain == CapabilityDomain.STRUCTURED_DATA and spec.tier == ExecutionTier.TIER_B_SLM:
            return self.worker_extractor
        elif spec.domain == CapabilityDomain.BUSINESS:
            if capability_id == "16_competitive_differentiation":
                return self.worker_strategist
            return self.worker_analyst_1
        elif spec.domain == CapabilityDomain.AI_SEARCH:
            return self.worker_simulator
        elif spec.domain == CapabilityDomain.GEO:
            return self.worker_analyst_2
        elif spec.domain == CapabilityDomain.EXPERIENCE:
            return self.worker_analyst_2
        elif spec.domain == CapabilityDomain.CONTENT:
            return self.worker_analyst_1
        elif spec.domain == CapabilityDomain.VERIFICATION:
            return self.worker_critic

        return self.worker_analyst_1

    async def execute_capability_wave(
        self,
        capability_ids: List[str],
        manifest: CrawlManifest,
        blackboard: CognitiveBlackboard
    ) -> Dict[str, Any]:
        """
        Executes a wave of capabilities in parallel where safe.
        Deterministic tasks run first without LLM tokens ($0), followed by cognitive workers.
        """
        results = {}
        cognitive_tasks = []

        for cap_id in capability_ids:
            spec = CAPABILITY_REGISTRY.get(cap_id)
            if not spec:
                continue

            # Deterministic execution
            if self.capability_router.is_deterministic(cap_id):
                det_results = self.capability_router.execute_deterministic_capability(cap_id, manifest, blackboard)
                for r in det_results:
                    blackboard.claim_registry.register_claim(
                        agent_id=f"deterministic_{cap_id}",
                        statement=r["statement"],
                        category=r["category"],
                        severity=r["severity"],
                        confidence=r["confidence"],
                        recommendation=r["recommendation"]
                    )
                results[cap_id] = {"type": "deterministic", "claims_count": len(det_results)}
            else:
                agent_id = CAPABILITY_AGENT_MAP.get(cap_id)
                specialist = self.agent_pool.get(agent_id) if agent_id else None
                if specialist:
                    cognitive_tasks.append(self._execute_specialist_task(specialist, cap_id, blackboard))
                else:
                    worker = self.assign_worker_for_capability(cap_id)
                    cognitive_tasks.append(self._execute_worker_task(worker, cap_id, blackboard))

        if cognitive_tasks:
            worker_results = await asyncio.gather(*cognitive_tasks, return_exceptions=True)
            for res in worker_results:
                if isinstance(res, dict) and "capability_id" in res:
                    results[res["capability_id"]] = res

        return results

    async def _execute_worker_task(self, worker, capability_id: str, blackboard: CognitiveBlackboard) -> Dict[str, Any]:
        try:
            res = await worker.execute_task(capability_id, blackboard)
            return {"capability_id": capability_id, "status": "success", "result": res}
        except Exception as e:
            return {"capability_id": capability_id, "status": "error", "error": str(e)}

    async def _execute_specialist_task(self, specialist, capability_id: str, blackboard: CognitiveBlackboard) -> Dict[str, Any]:
        try:
            res = await specialist.run(blackboard)
            return {"capability_id": capability_id, "status": res.get("status", "success"), "result": res}
        except Exception as e:
            return {"capability_id": capability_id, "status": "error", "error": str(e)}
