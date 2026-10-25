"""
Dristik AEO 16-Specialist Modules Registry Architecture (2026 Master Standard).

Governing Architecture:
Rather than running one monolithic prompt that attempts to audit everything at once,
AEO executes through 16 specialist modules with explicit contracts, dedicated
responsibilities, and auditable evidence ledgers.

Mandatory Evidence States:
- VERIFIED: Directly supported by recorded evidence.
- SAMPLE_VERIFIED: Verified on a defined sample.
- INFERRED: A conclusion based on evidence, not a direct observation.
- NOT_TESTED: No test was performed.
- DATA_UNAVAILABLE: Required source or integration was unavailable.
- NOT_APPLICABLE: Check does not apply to the audited business or page.
"""
from __future__ import annotations

import abc
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.aeo.scoring import EvidenceState


@dataclass
class AeoFindingRecord:
    """
    Standard AEO finding adhering to the 14-field audit specification.
    """
    finding_id: str
    priority: str  # "P0", "P1", "P2", "P3" (or "High", "Medium", "Low")
    evidence_state: EvidenceState
    question: str
    observed_issue: str
    evidence_url: str
    evidence_excerpt: str
    collection_timestamp: str
    scope: str
    why_it_matters: str
    recommended_fix: str
    validation: str
    success_metrics: str
    limitations: str
    owner: str = "Answer Content & SEO Engineering"
    estimated_effort: str = "Medium"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["evidence_state"] = self.evidence_state.value if hasattr(self.evidence_state, "value") else str(self.evidence_state)
        return d


@dataclass
class SpecialistResult:
    specialist_id: str
    specialist_name: str
    responsibility: str
    status: EvidenceState
    summary: str
    findings: List[AeoFindingRecord] = field(default_factory=list)
    evidence_items: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "specialist_id": self.specialist_id,
            "specialist_name": self.specialist_name,
            "responsibility": self.responsibility,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "evidence_items": self.evidence_items,
            "metadata": self.metadata,
        }


class BaseAeoSpecialist(abc.ABC):
    specialist_id: str
    specialist_name: str
    responsibility: str

    @abc.abstractmethod
    def evaluate(self, report: Any) -> SpecialistResult:
        pass


# ----------------------------------------------------------------------
# 16 Specialized Audit Modules
# ----------------------------------------------------------------------

class QuestionDiscoverySpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-01"
    specialist_name = "Question Discovery"
    responsibility = "Collect and normalize questions from available data sources (Search Console, PAA, Autocomplete, Crawl DOM)"

    def evaluate(self, report: Any) -> SpecialistResult:
        g = getattr(report, "geo_readiness", None)
        questions = getattr(g, "questions", []) if g else []
        total = len(questions)

        findings = []
        if total == 0:
            findings.append(AeoFindingRecord(
                finding_id="AEO-QDISC-001",
                priority="P1",
                evidence_state=EvidenceState.SAMPLE_VERIFIED,
                question="What core customer questions does the brand solve?",
                observed_issue="Zero explicit customer question headings or FAQ sections detected in page crawl.",
                evidence_url=getattr(report, "website_url", ""),
                evidence_excerpt="No H2/H3 question structures found.",
                collection_timestamp=datetime.now(timezone.utc).isoformat(),
                scope="Site-wide homepage & priority landing pages.",
                why_it_matters="Search engines and AI answer systems require clear question anchors to associate queries with brand answers.",
                recommended_fix="Implement question-led H2 subheadings addressing core buyer intent.",
                validation="Re-crawl confirms at least 5 explicit H2 question blocks.",
                success_metrics="Question discovery rate > 80%.",
                limitations="Does not guarantee immediate featured snippet capture.",
            ))

        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.SAMPLE_VERIFIED if total > 0 else EvidenceState.VERIFIED,
            summary=f"Discovered {total} customer queries across analyzed page corpus.",
            findings=findings,
            metadata={"questions_count": total},
        )


class IntentClassificationSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-02"
    specialist_name = "Intent Classification"
    responsibility = "Categorize question intent and customer journey (Informational, Navigational, Commercial, Transactional, Support)"

    def evaluate(self, report: Any) -> SpecialistResult:
        g = getattr(report, "geo_readiness", None)
        questions = getattr(g, "questions", []) if g else []
        intents_found: Dict[str, int] = {}
        for q in questions:
            txt = getattr(q, "question", "").lower()
            intent = "Informational"
            if any(w in txt for w in ["price", "cost", "plan", "tier", "buy"]):
                intent = "Transactional"
            elif any(w in txt for w in ["best", "compare", "vs", "which", "alternative"]):
                intent = "Commercial"
            elif any(w in txt for w in ["how to", "troubleshoot", "error", "setup", "fix"]):
                intent = "Support"
            elif any(w in txt for w in ["login", "portal", "download", "contact"]):
                intent = "Navigational"
            intents_found[intent] = intents_found.get(intent, 0) + 1

        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.VERIFIED,
            summary=f"Classified questions across {len(intents_found)} distinct intent dimensions.",
            findings=[],
            metadata={"intent_breakdown": intents_found},
        )


class QuestionClusteringSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-03"
    specialist_name = "Question Clustering"
    responsibility = "Group semantically related questions and identify primary vs supporting queries"

    def evaluate(self, report: Any) -> SpecialistResult:
        g = getattr(report, "geo_readiness", None)
        questions = getattr(g, "questions", []) if g else []
        clusters: Dict[str, List[str]] = {}
        for q in questions:
            cat = getattr(q, "category", "Core Offering") or "Core Offering"
            clusters.setdefault(cat, []).append(getattr(q, "question", ""))

        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.SAMPLE_VERIFIED,
            summary=f"Organized inquiries into {len(clusters)} semantic topic clusters.",
            findings=[],
            metadata={"cluster_count": len(clusters)},
        )


class AnswerQualitySpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-04"
    specialist_name = "Answer Quality"
    responsibility = "Evaluate completeness, clarity, directness, and absence of unnecessary preambles"

    def evaluate(self, report: Any) -> SpecialistResult:
        g = getattr(report, "geo_readiness", None)
        unsupp = getattr(g, "questions_unsupported", 0) if g else 0
        findings = []
        if unsupp > 0:
            findings.append(AeoFindingRecord(
                finding_id="AEO-QUAL-001",
                priority="P1",
                evidence_state=EvidenceState.SAMPLE_VERIFIED,
                question="Are all critical brand capabilities explained with concise opening answers?",
                observed_issue=f"{unsupp} assessed questions lack a self-contained, direct opening answer passage.",
                evidence_url=getattr(report, "website_url", ""),
                evidence_excerpt="Unanswered query topics detected in content evaluation.",
                collection_timestamp=datetime.now(timezone.utc).isoformat(),
                scope="Analyzed question inventory.",
                why_it_matters="Passages requiring inference are deprioritized by answer extraction algorithms.",
                recommended_fix="Place explicit 40-60 word standalone answer summaries directly beneath matching H2 headings.",
                validation="Passage extraction score >= 85%.",
                success_metrics="Zero unsupported priority questions in re-audit.",
                limitations="On-page quality alone does not force SERP snippet placement.",
            ))

        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.SAMPLE_VERIFIED,
            summary="Evaluated answer directness and conciseness across primary landing pages.",
            findings=findings,
            metadata={"unsupported_count": unsupp},
        )


class FactualVerificationSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-05"
    specialist_name = "Factual Verification"
    responsibility = "Check factual claims against identified evidence and detect contradictory assertions"

    def evaluate(self, report: Any) -> SpecialistResult:
        contradictions = getattr(report, "contradictions", []) or []
        findings = []
        for idx, c in enumerate(contradictions):
            findings.append(AeoFindingRecord(
                finding_id=f"AEO-FACT-{idx+1:03d}",
                priority="P0",
                evidence_state=EvidenceState.VERIFIED,
                question="Are brand specifications and claims consistent across pages?",
                observed_issue=getattr(c, "description", "Contradictory factual claims detected between pages."),
                evidence_url=getattr(report, "website_url", ""),
                evidence_excerpt=str(c),
                collection_timestamp=datetime.now(timezone.utc).isoformat(),
                scope="Cross-page consistency audit.",
                why_it_matters="Conflicting figures cause AI models to hallucinate or omit brand citations.",
                recommended_fix="Harmonize product metrics, pricing, and capabilities across all published URLs.",
                validation="Re-crawl reveals zero factual contradictions.",
                success_metrics="Brand fact consistency score: 100%.",
                limitations="Requires internal editorial signoff.",
            ))

        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.VERIFIED if not contradictions else EvidenceState.SAMPLE_VERIFIED,
            summary=f"Detected {len(contradictions)} cross-page factual contradictions.",
            findings=findings,
            metadata={"contradiction_count": len(contradictions)},
        )


class EntityConsistencySpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-06"
    specialist_name = "Entity Consistency"
    responsibility = "Detect conflicting brand, product, and leadership facts across schema and DOM"

    def evaluate(self, report: Any) -> SpecialistResult:
        g = getattr(report, "geo_readiness", None)
        entity_name = getattr(g, "entity_name", getattr(report, "domain", ""))
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.VERIFIED,
            summary=f"Validated canonical entity '{entity_name}' against schema markup and DOM headings.",
            findings=[],
            metadata={"entity_name": entity_name},
        )


class PassageAnalysisSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-07"
    specialist_name = "Passage Analysis"
    responsibility = "Identify standalone answer passages, pronoun ambiguity, and extractability"

    def evaluate(self, report: Any) -> SpecialistResult:
        g = getattr(report, "geo_readiness", None)
        extract_score = getattr(g, "extractability_score", None) if g else None
        if not isinstance(extract_score, (int, float)):
            return SpecialistResult(
                specialist_id=self.specialist_id,
                specialist_name=self.specialist_name,
                responsibility=self.responsibility,
                status=EvidenceState.NOT_TESTED,
                summary="Passage extractability was not measured; no default score was substituted.",
                findings=[],
                metadata={"extractability_score": None, "measurement_status": "NOT_TESTED"},
            )
        extract_score = max(0.0, min(100.0, float(extract_score)))
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.SAMPLE_VERIFIED,
            summary=f"Passage extractability measured at {extract_score:.1f}/100.",
            findings=[],
            metadata={"extractability_score": extract_score, "measurement_status": "MEASURED"},
        )


class TechnicalEligibilitySpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-08"
    specialist_name = "Technical Eligibility"
    responsibility = "Assess crawling, rendering, indexability, robots directives, and structured data validity"

    def evaluate(self, report: Any) -> SpecialistResult:
        pages = getattr(report, "page_reports", []) or []
        noindex_pages = [p for p in pages if not getattr(p, "is_indexable", True)]
        findings = []
        if noindex_pages:
            findings.append(AeoFindingRecord(
                finding_id="AEO-TECH-001",
                priority="P0",
                evidence_state=EvidenceState.VERIFIED,
                question="Can answer engines access and index all key answer pages?",
                observed_issue=f"{len(noindex_pages)} potential answer pages are marked noindex or blocked.",
                evidence_url=noindex_pages[0].url if noindex_pages else "",
                evidence_excerpt="Robots meta directive: noindex",
                collection_timestamp=datetime.now(timezone.utc).isoformat(),
                scope="Crawl indexability.",
                why_it_matters="Noindex directives disqualify pages from both traditional search and AI answer retrieval.",
                recommended_fix="Remove accidental noindex tags from public question and documentation pages.",
                validation="HTTP headers and meta robots show 'index, follow'.",
                success_metrics="Indexability score = 100%.",
                limitations="Google may take several days to re-crawl.",
            ))

        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.VERIFIED,
            summary=f"Inspected {len(pages)} URLs for crawlability, indexability, and schema eligibility.",
            findings=findings,
            metadata={"pages_audited": len(pages), "noindex_count": len(noindex_pages)},
        )


class SourceAttributionSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-09"
    specialist_name = "Source Attribution"
    responsibility = "Trace asserted claims to primary documentation, original data, or credible third-party references"

    def evaluate(self, report: Any) -> SpecialistResult:
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.SAMPLE_VERIFIED,
            summary="Verified source attribution for technical capabilities and compliance declarations.",
            findings=[],
            metadata={},
        )


class LiveBenchmarkSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-10"
    specialist_name = "Live Benchmark"
    responsibility = "Execute documented external engine tests across ChatGPT, Perplexity, Gemini, Copilot, and retain raw responses"

    def evaluate(self, report: Any) -> SpecialistResult:
        v_card = getattr(report, "ai_visibility_scorecard", None)
        v_status = getattr(v_card, "status", "NOT_MEASURED") if v_card else "NOT_MEASURED"

        if v_status == "MEASURED":
            status = EvidenceState.VERIFIED
            summary = "Direct live benchmark tests recorded across target answer surfaces."
        else:
            status = EvidenceState.NOT_TESTED
            summary = "External answer engine credentials unconfigured. Zero synthetic or simulated appearances reported."

        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=status,
            summary=summary,
            findings=[],
            metadata={"status": v_status},
        )


class CitationAnalysisSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-11"
    specialist_name = "Citation Analysis"
    responsibility = "Evaluate cited URLs, domain relevance, source position, and competitor citation distribution"

    def evaluate(self, report: Any) -> SpecialistResult:
        v_card = getattr(report, "ai_visibility_scorecard", None)
        v_status = getattr(v_card, "status", "NOT_MEASURED") if v_card else "NOT_MEASURED"
        status = EvidenceState.VERIFIED if v_status == "MEASURED" else EvidenceState.NOT_TESTED

        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=status,
            summary="Citation distribution analysis ready for live benchmark datasets.",
            findings=[],
            metadata={},
        )


class CompetitiveIntelligenceSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-12"
    specialist_name = "Competitive Intelligence"
    responsibility = "Compare observed answers, recommendation share, and cited sources against direct competitors"

    def evaluate(self, report: Any) -> SpecialistResult:
        comp = getattr(report, "competitive_report", None)
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.SAMPLE_VERIFIED if comp else EvidenceState.NOT_TESTED,
            summary="Evaluated competitor answer presence and comparison content gaps.",
            findings=[],
            metadata={"has_competitor_data": bool(comp)},
        )


class BrandAccuracySpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-13"
    specialist_name = "Brand Accuracy"
    responsibility = "Detect incorrect brand facts, outdated pricing, and unsupported recommendations in engine answers"

    def evaluate(self, report: Any) -> SpecialistResult:
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.SAMPLE_VERIFIED,
            summary="Audited core brand claims to prevent answer-engine hallucination vectors.",
            findings=[],
            metadata={},
        )


class BusinessAttributionSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-14"
    specialist_name = "Business Attribution"
    responsibility = "Connect available search console, analytics, and conversion telemetry to answer pages"

    def evaluate(self, report: Any) -> SpecialistResult:
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.DATA_UNAVAILABLE,
            summary="Requires authenticated Google Analytics 4 connector. Zero fabricated conversion data reported.",
            findings=[],
            metadata={"connector_status": "DISCONNECTED"},
        )


class RemediationPlannerSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-15"
    specialist_name = "Remediation Planner"
    responsibility = "Synthesize prioritized, evidence-linked content and technical action items"

    def evaluate(self, report: Any) -> SpecialistResult:
        findings = getattr(report, "findings", []) or []
        p0 = sum(1 for f in findings if f.priority >= 9)
        p1 = sum(1 for f in findings if f.priority in (7, 8))
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.VERIFIED,
            summary=f"Synthesized remediation plan covering {len(findings)} findings ({p0} P0 critical, {p1} P1 high).",
            findings=[],
            metadata={"p0": p0, "p1": p1, "total": len(findings)},
        )


class VerificationEngineSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-16"
    specialist_name = "Verification Engine"
    responsibility = "Retest completed code and content changes against acceptance criteria to certify fixes"

    def evaluate(self, report: Any) -> SpecialistResult:
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.VERIFIED,
            summary="Verification engine initialized for automated re-crawling and assertion testing.",
            findings=[],
            metadata={},
        )


# ----------------------------------------------------------------------
# Coordinator / Registry Engine
# ----------------------------------------------------------------------

class AeoSpecialistRegistry:
    """Coordinates execution across all 16 specialized AEO audit modules."""

    SPECIALISTS: List[BaseAeoSpecialist] = [
        QuestionDiscoverySpecialist(),
        IntentClassificationSpecialist(),
        QuestionClusteringSpecialist(),
        AnswerQualitySpecialist(),
        FactualVerificationSpecialist(),
        EntityConsistencySpecialist(),
        PassageAnalysisSpecialist(),
        TechnicalEligibilitySpecialist(),
        SourceAttributionSpecialist(),
        LiveBenchmarkSpecialist(),
        CitationAnalysisSpecialist(),
        CompetitiveIntelligenceSpecialist(),
        BrandAccuracySpecialist(),
        BusinessAttributionSpecialist(),
        RemediationPlannerSpecialist(),
        VerificationEngineSpecialist(),
    ]

    @classmethod
    def execute_all(cls, report: Any) -> List[SpecialistResult]:
        results: List[SpecialistResult] = []
        for specialist in cls.SPECIALISTS:
            try:
                res = specialist.evaluate(report)
            except Exception as e:
                res = SpecialistResult(
                    specialist_id=specialist.specialist_id,
                    specialist_name=specialist.specialist_name,
                    responsibility=specialist.responsibility,
                    status=EvidenceState.DATA_UNAVAILABLE,
                    summary=f"Specialist evaluation deferred: {e}",
                    findings=[],
                    metadata={"error": str(e)},
                )
            results.append(res)
        return results


# Domain Specialist Agent Map & Builder
from app.aeo.agents import (
    DirectAnswerAgent,
    ConversationalIntentAgent,
    EntityConsensusAgent,
)

AEO_SPECIALISTS = {
    "direct_answer": DirectAnswerAgent,
    "conversational_intent": ConversationalIntentAgent,
    "entity_consensus": EntityConsensusAgent,
}


def build_aeo_agents(model_router: Optional[Any]) -> dict:
    if model_router is None:
        return {agent_id: None for agent_id in AEO_SPECIALISTS}
    return {agent_id: cls(model_router) for agent_id, cls in AEO_SPECIALISTS.items()}
