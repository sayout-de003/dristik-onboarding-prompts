"""
50-agent workforce pool and dependency DAG executor.

Instantiates every specialist in SPECIALIST_AGENTS_V3 and runs them in
topological waves. Independent agents in a wave run concurrently.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from app.core.config import settings
from app.orchestration.runtime.registry import SPECIALIST_AGENTS_V3, AgentDefinition, get_agent_definition
from app.orchestration.runtime.specialist import SpecialistAgent
from app.orchestration.runtime.reasoners import (
    TechnicalReasonerAgent,
    GeoAeoReasonerAgent,
    CroExperienceReasonerAgent,
    CrossAnalystAgent,
    CriticAgent,
    SynthesizerAgent,
)
from app.domain.evidence.coverage import EvidenceCoverageCalculator
from app.orchestration.cognition.blackboard import CognitiveBlackboard
from app.orchestration.agent_contracts import validate_agent_result

logger = logging.getLogger("dristik.agent_pool")

ProgressCb = Optional[Callable[[str, int, str, Dict[str, Any]], Awaitable[None]]]


def topological_waves(definitions: Dict[str, AgentDefinition]) -> List[List[str]]:
    """Build deterministic Kahn waves and fail closed on invalid dependencies."""
    ids = list(definitions.keys())
    id_set = set(ids)
    unknown_dependencies = sorted({
        str(dep)
        for defn in definitions.values()
        for dep in (defn.dependencies or [])
        if dep not in id_set
    })
    if unknown_dependencies:
        raise ValueError(
            "agent DAG contains dependencies that are not registered: "
            + ", ".join(unknown_dependencies[:30])
        )

    incoming: Dict[str, int] = {agent_id: 0 for agent_id in ids}
    edges: Dict[str, List[str]] = defaultdict(list)
    for agent_id, definition in definitions.items():
        for dependency in definition.dependencies or []:
            edges[dependency].append(agent_id)
            incoming[agent_id] += 1

    ready = deque([agent_id for agent_id in ids if incoming[agent_id] == 0])
    waves: List[List[str]] = []
    seen_ids: set[str] = set()
    while ready:
        wave = list(ready)
        ready.clear()
        waves.append(wave)
        seen_ids.update(wave)
        next_wave: List[str] = []
        for node in wave:
            for child in edges[node]:
                incoming[child] -= 1
                if incoming[child] == 0:
                    next_wave.append(child)
        ready.extend(next_wave)

    if len(seen_ids) != len(ids):
        cyclic = sorted(set(ids) - seen_ids)
        raise ValueError(
            "agent DAG contains a dependency cycle involving: "
            + ", ".join(cyclic[:30])
        )
    return waves

PILLAR_DOMAINS: Dict[str, Set[str]] = {
    "seo": {"TECHNICAL_SEO", "STRUCTURED_DATA", "CONTENT"},
    "geo": {"GEO"},
    "aeo": {"AI_SEARCH", "AEO"},
    "cro": {"EXPERIENCE", "UX_CONVERSION"},
}
CORE_ALWAYS_DOMAINS: Set[str] = {"BUSINESS", "VERIFICATION", "COMPETITOR"}


class AgentPool:
    """Creates and runs the full 50-agent specialist workforce."""

    def __init__(self, model_router):
        self.model_router = model_router
        self.agents: Dict[str, SpecialistAgent] = {
            agent_id: SpecialistAgent(defn, model_router)
            for agent_id, defn in SPECIALIST_AGENTS_V3.items()
        }
        self.waves = topological_waves(SPECIALIST_AGENTS_V3)

        # Streamlined Specialist Reasoner Fleet
        self.tech_reasoner = TechnicalReasonerAgent(model_router)
        self.geo_reasoner = GeoAeoReasonerAgent(model_router)
        self.cro_reasoner = CroExperienceReasonerAgent(model_router)
        self.cross_analyst = CrossAnalystAgent()
        self.critic = CriticAgent()
        self.synthesizer = SynthesizerAgent()
        self.coverage_calc = EvidenceCoverageCalculator()

    def __len__(self) -> int:
        return len(self.agents)

    def get(self, agent_id: str) -> Optional[SpecialistAgent]:
        if agent_id in self.agents:
            return self.agents[agent_id]
        defn = get_agent_definition(agent_id)
        if defn and defn.agent_id in self.agents:
            return self.agents[defn.agent_id]
        return None

    async def execute_all(
        self,
        blackboard: CognitiveBlackboard,
        progress_cb: ProgressCb = None,
        base_progress: int = 40,
        end_progress: int = 88,
        active_pillars: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        total = max(len(self.agents), 1)
        completed = 0
        summary: Dict[str, Any] = {
            "agents_declared": total,
            "agents_ran": 0,
            "completed": 0,
            "partial": 0,
            "unavailable": 0,
            "skipped": 0,
            "errors": 0,
            "waves": len(self.waves),
            "results": {},
        }

        # Determine active domains if selective pillars specified
        normalized_pillars = {p.lower().strip() for p in (active_pillars or set()) if p}
        allowed_domains: Optional[Set[str]] = None
        if normalized_pillars and normalized_pillars != {"seo", "geo", "aeo", "cro"}:
            allowed_domains = set(CORE_ALWAYS_DOMAINS)
            for p in normalized_pillars:
                allowed_domains.update(PILLAR_DOMAINS.get(p, set()))

        # Limit parallel agent tasks per wave to prevent scheduling bursts
        pool_concurrency = max(2, getattr(settings, "LLM_MAX_CONCURRENCY", 2) * 2)
        sem = asyncio.Semaphore(pool_concurrency)

        async def _bounded_run(aid: str) -> Dict[str, Any]:
            if allowed_domains is not None:
                defn = SPECIALIST_AGENTS_V3.get(aid)
                dom = defn.domain if defn else "UNKNOWN"
                if dom not in allowed_domains:
                    return {
                        "agent_id": aid,
                        "status": "skipped",
                        "unavailable_reason": f"Pillar excluded (active pillars: {', '.join(sorted(normalized_pillars))})",
                        "claims": [],
                    }
            async with sem:
                return await self._run_one(aid, blackboard)

        for wave_index, wave in enumerate(self.waves):
            tasks = [_bounded_run(agent_id) for agent_id in wave]
            packed = await asyncio.gather(*tasks, return_exceptions=True)
            for agent_id, payload in zip(wave, packed):
                completed += 1
                if isinstance(payload, Exception):
                    record = {
                        "agent_id": agent_id,
                        "status": "error",
                        "unavailable_reason": str(payload),
                        "claims": [],
                    }
                    blackboard.blackboard_state.setdefault("agent_results", {})[agent_id] = record
                    summary["errors"] += 1
                    summary["results"][agent_id] = record
                else:
                    payload = validate_agent_result(agent_id, payload)
                    status = payload["status"]
                    blackboard.blackboard_state.setdefault("agent_results", {})[agent_id] = payload
                    summary["agents_ran"] += 1
                    if status == "unavailable":
                        summary["unavailable"] += 1
                    elif status == "skipped":
                        summary["skipped"] += 1
                    elif status in {"error", "failed"}:
                        summary["errors"] += 1
                    elif status == "partial":
                        summary["partial"] += 1
                    else:
                        summary["completed"] += 1
                    summary["results"][agent_id] = payload

                if progress_cb:
                    pct = base_progress + int((completed / total) * (end_progress - base_progress))
                    name = SPECIALIST_AGENTS_V3[agent_id].agent_name
                    await progress_cb(
                        "specialist_execution",
                        pct,
                        f"Specialist {completed}/{total}: {name}",
                        {
                            "agent_id": agent_id,
                            "wave": wave_index + 1,
                            "waves": len(self.waves),
                            "status": summary["results"][agent_id].get("status"),
                        },
                    )

        blackboard.blackboard_state["agent_pool_summary"] = {
            k: summary[k] for k in ("agents_declared", "agents_ran", "completed", "partial", "unavailable", "skipped", "errors", "waves")
        }
        return summary

    async def _run_one(self, agent_id: str, blackboard: CognitiveBlackboard) -> Dict[str, Any]:
        agent = self.agents[agent_id]
        active_prov = ""
        if hasattr(self.model_router, "client") and hasattr(self.model_router.client, "provider"):
            active_prov = self.model_router.client.provider or ""
        if not active_prov:
            from app.core.config import settings
            active_prov = settings.get_active_provider()

        # Under Groq free tier, 429 backoffs can be up to 30s. Provide a generous outer buffer.
        # Non-Groq providers maintain their standard fast timeout.
        if (active_prov or "").lower() == "groq":
            timeout_sec = max(60.0, float(getattr(agent.definition, "timeout_sec", 60) or 60) + 35.0)
        else:
            timeout_sec = float(getattr(agent.definition, "timeout_sec", 60) or 60) + 15.0
        try:
            return await asyncio.wait_for(agent.run(blackboard), timeout=timeout_sec)
        except asyncio.TimeoutError:
            logger.warning("[AgentPool] Specialist agent '%s' timed out after %.1fs", agent_id, timeout_sec)
            record = {
                "agent_id": agent_id,
                "status": "unavailable",
                "unavailable_reason": f"timeout_after_{timeout_sec:.0f}s",
                "claims": [],
            }
            blackboard.blackboard_state.setdefault("agent_results", {})[agent_id] = record
            return record
        except Exception as e:
            logger.error("[AgentPool] Specialist agent '%s' failed: %s", agent_id, e)
            record = {
                "agent_id": agent_id,
                "status": "error",
                "unavailable_reason": str(e),
                "claims": [],
            }
            blackboard.blackboard_state.setdefault("agent_results", {})[agent_id] = record
            return record

    async def execute_streamlined_fleet(
        self,
        blackboard: CognitiveBlackboard,
        progress_cb: ProgressCb = None,
        base_progress: int = 46,
        end_progress: int = 78,
    ) -> Dict[str, Any]:
        """
        Executes the streamlined, zero-hallucination specialist workforce:
        1. 3 Specialist Reasoners (Technical, GEO/AEO, CRO/Experience) in parallel.
        2. CrossAnalystAgent for cross-pillar causal bottlenecks.
        3. CriticAgent for adversarial verification against EvidenceRef.
        4. SynthesizerAgent for surface/priority ranking and actionable remediation.
        5. EvidenceCoverageCalculator for transparent observability audit.
        """
        manifest = blackboard.crawl_manifest
        pages = blackboard.pages or (manifest.pages if manifest else [])

        if progress_cb:
            await progress_cb(
                "streamlined_reasoning",
                base_progress,
                "Deploying 3 Specialist Reasoners (Technical, GEO, CRO)...",
                {"reasoners": 3}
            )

        # Step 1: Execute 3 Specialist Reasoners in parallel
        tech_task = self.tech_reasoner.reason(manifest, pages, blackboard.evidence_store)
        geo_task = self.geo_reasoner.reason(manifest, pages, blackboard.evidence_store)
        cro_task = self.cro_reasoner.reason(manifest, pages, blackboard.evidence_store)

        reasoner_results = await asyncio.gather(tech_task, geo_task, cro_task, return_exceptions=True)

        specialist_findings: List[Finding] = []
        for r in reasoner_results:
            if isinstance(r, list):
                specialist_findings.extend(r)
            elif isinstance(r, Exception):
                logger.error("[AgentPool] Reasoner exception: %s", r)

        if progress_cb:
            mid_progress = base_progress + int((end_progress - base_progress) * 0.4)
            await progress_cb(
                "cross_analyst",
                mid_progress,
                "Running CrossAnalystAgent for cross-pillar causal synthesis...",
                {"raw_findings": len(specialist_findings)}
            )

        # Step 2: CrossAnalyst causal synthesis
        cross_findings = await self.cross_analyst.analyze(specialist_findings, manifest)
        all_raw_findings = specialist_findings + cross_findings

        if progress_cb:
            critic_progress = base_progress + int((end_progress - base_progress) * 0.7)
            await progress_cb(
                "adversarial_critic",
                critic_progress,
                "CriticAgent auditing findings against EvidenceRef provenance...",
                {"findings_to_audit": len(all_raw_findings)}
            )

        # Step 3: Critic adversarial verification
        audit_res = self.critic.audit_findings(all_raw_findings)
        verified_findings = audit_res.get("verified", [])

        # Step 4: Synthesizer prioritization
        final_findings = self.synthesizer.synthesize(verified_findings)

        # Step 5: Save findings & register claims onto blackboard
        blackboard.findings = final_findings
        for f in final_findings:
            blackboard.claim_registry.register_claim(
                agent_id=f"reasoner_{f.category.value if hasattr(f.category, 'value') else f.category}",
                statement=f.description or f.title,
                category=f.category,
                severity=f.severity,
                confidence=f.confidence,
                recommendation=f.recommendation,
                evidence_refs=list(f.evidence_refs or []),
            )

        # Step 6: Evidence Coverage Metric
        coverage_report = self.coverage_calc.calculate_coverage(
            run_id=blackboard.run_id,
            manifest=manifest,
            pages=pages,
            evidence_store=blackboard.evidence_store
        )
        blackboard.blackboard_state["evidence_coverage"] = coverage_report.model_dump()

        summary: Dict[str, Any] = {
            "mode": "streamlined_fleet",
            "specialist_reasoners": 3,
            "total_findings_generated": len(all_raw_findings),
            "critic_verified": len(verified_findings),
            "critic_rejected": len(audit_res.get("rejected", [])),
            "critic_demoted": len(audit_res.get("demoted", [])),
            "final_findings_count": len(final_findings),
            "overall_evidence_coverage_pct": coverage_report.overall_coverage_pct,
            "pillars_coverage": {k: v.coverage_pct for k, v in coverage_report.pillars.items()},
        }
        blackboard.blackboard_state["streamlined_fleet_summary"] = summary

        if progress_cb:
            await progress_cb(
                "streamlined_reasoning",
                end_progress,
                f"Streamlined reasoner fleet completed: {len(final_findings)} verified findings ({coverage_report.overall_coverage_pct}% evidence coverage).",
                summary
            )

        return summary
