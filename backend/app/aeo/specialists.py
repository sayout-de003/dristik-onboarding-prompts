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

        pages = getattr(report, "page_reports", []) or []
        findings = []
        if total == 0 and pages:
            findings.append(AeoFindingRecord(
                finding_id="AEO-QDISC-001",
                priority="P1",
                evidence_state=EvidenceState.SAMPLE_VERIFIED,
                question="What core customer questions does the brand solve?",
                observed_issue="No customer questions were present in the generated question inventory for the available crawl sample.",
                evidence_url=getattr(report, "website_url", ""),
                evidence_excerpt="Question inventory returned zero entries; this does not establish that the site has no answers.",
                collection_timestamp=datetime.now(timezone.utc).isoformat(),
                scope="Available crawled page sample; consult the audit's URL coverage before generalizing.",
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
            status=(
                EvidenceState.SAMPLE_VERIFIED if total > 0
                else EvidenceState.SAMPLE_VERIFIED if pages
                else EvidenceState.NOT_TESTED
            ),
            summary=(
                f"Discovered {total} customer queries across analyzed page corpus."
                if total else
                "No question inventory was available; no site-wide absence claim was made."
                if not pages else
                "No explicit customer questions were found in the available crawl sample."
            ),
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
            status=EvidenceState.SAMPLE_VERIFIED if questions else EvidenceState.NOT_TESTED,
            summary=(
                f"Applied keyword-based intent heuristics to {len(questions)} questions across {len(intents_found)} intent labels."
                if questions else "No questions were available for intent classification."
            ),
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
            status=EvidenceState.SAMPLE_VERIFIED if questions else EvidenceState.NOT_TESTED,
            summary=(
                f"Grouped {len(questions)} questions by existing category labels into {len(clusters)} groups; this is not semantic clustering."
                if questions else "No questions were available for clustering."
            ),
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
            status=(
                EvidenceState.SAMPLE_VERIFIED
                if getattr(g, "questions_total", 0) > 0
                else EvidenceState.NOT_TESTED
            ),
            summary=(
                "Reviewed answer-support counts from the available question evaluation; passage-level quality evidence is not attached by this specialist."
                if getattr(g, "questions_total", 0) > 0
                else "Answer quality was not tested because no assessed question inventory is available."
            ),
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
            status=EvidenceState.SAMPLE_VERIFIED if contradictions else EvidenceState.NOT_TESTED,
            summary=(
                f"Recorded {len(contradictions)} contradiction record(s); underlying claims still require source review."
                if contradictions else
                "No contradiction records were supplied; this does not establish that all factual claims were verified."
            ),
            findings=findings,
            metadata={"contradiction_count": len(contradictions)},
        )


class EntityConsistencySpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-06"
    specialist_name = "Entity Consistency"
    responsibility = "Detect conflicting brand, product, and leadership facts across schema and DOM"

    def evaluate(self, report: Any) -> SpecialistResult:
        g = getattr(report, "geo_readiness", None)
        entity_name = getattr(g, "entity_name", None) if g else None
        # A report/domain name is not independent corroboration of entity identity.
        # This specialist currently has no source-comparison evidence contract.
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.NOT_TESTED,
            summary="Cross-source entity consistency was not tested by this specialist; a first-party name alone is insufficient.",
            findings=[],
            metadata={"entity_name": entity_name, "measurement_status": "NOT_TESTED"},
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
        # Missing indexability data is unknown, not indexable and not non-indexable.
        noindex_pages = [p for p in pages if getattr(p, "is_indexable", None) is False]
        findings = []
        if noindex_pages:
            findings.append(AeoFindingRecord(
                finding_id="AEO-TECH-001",
                priority="P0",
                evidence_state=EvidenceState.SAMPLE_VERIFIED,
                question="Can answer engines access and index all key answer pages?",
                observed_issue=f"{len(noindex_pages)} analyzed page(s) are explicitly marked non-indexable in the crawl data; the cause requires directive-level confirmation.",
                evidence_url=getattr(noindex_pages[0], "url", "") if noindex_pages else "",
                evidence_excerpt=f"Observed is_indexable=False for {getattr(noindex_pages[0], 'url', 'analyzed page')}; inspect meta robots, X-Robots-Tag, and robots.txt before remediation.",
                collection_timestamp=datetime.now(timezone.utc).isoformat(),
                scope="Crawl indexability.",
                why_it_matters="A confirmed exclusion directive can prevent search indexing; this observation alone does not prove the underlying cause or guarantee how an answer engine retrieves the page.",
                recommended_fix="Remove accidental noindex tags from public question and documentation pages.",
                validation="HTTP headers and meta robots show 'index, follow'.",
                success_metrics="Indexability score = 100%.",
                limitations="Google may take several days to re-crawl.",
            ))

        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=(
                EvidenceState.SAMPLE_VERIFIED
                if pages and any(getattr(p, "is_indexable", None) is not None or getattr(p, "status_code", None) is not None for p in pages)
                else EvidenceState.NOT_TESTED
            ),
            summary=(
                f"Inspected {len(pages)} URL record(s); only explicit crawl observations are counted."
                if pages else "No page records were available for technical eligibility checks."
            ),
            findings=findings,
            metadata={"pages_audited": len(pages), "noindex_count": len(noindex_pages)},
        )


class SourceAttributionSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-09"
    specialist_name = "Source Attribution"
    responsibility = "Trace asserted claims to primary documentation, original data, or credible third-party references"

    def evaluate(self, report: Any) -> SpecialistResult:
        # This module does not yet resolve claims to source passages. Do not label
        # the capability verified until claim-to-source links are actually assessed.
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.NOT_TESTED,
            summary="Claim-to-source attribution was not tested; no source-to-claim evidence map was produced.",
            findings=[],
            metadata={"measurement_status": "NOT_TESTED"},
        )


class LiveBenchmarkSpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-10"
    specialist_name = "Live Benchmark"
    responsibility = "Execute documented external engine tests across ChatGPT, Perplexity, Gemini, Copilot, and retain raw responses"

    def evaluate(self, report: Any) -> SpecialistResult:
        v_card = getattr(report, "ai_visibility_scorecard", None)
        v_status = getattr(v_card, "status", "NOT_MEASURED") if v_card else "NOT_MEASURED"

        raw_responses = (
            getattr(v_card, "raw_responses", None)
            or getattr(v_card, "responses", None)
            or getattr(report, "ai_visibility_responses", None)
            or []
        ) if v_card or report else []
        if v_status == "MEASURED" and raw_responses:
            status = EvidenceState.SAMPLE_VERIFIED
            summary = f"Live benchmark status is measured and {len(raw_responses)} response record(s) are available for inspection."
        else:
            status = EvidenceState.NOT_TESTED
            summary = "No inspectable live response records were available; status metadata alone is not proof of an executed benchmark."

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
        raw_responses = (
            getattr(v_card, "raw_responses", None)
            or getattr(v_card, "responses", None)
            or getattr(report, "ai_visibility_responses", None)
            or []
        ) if v_card or report else []
        has_citation_data = any(
            getattr(response, "citations", None) or
            (isinstance(response, dict) and response.get("citations"))
            for response in raw_responses
        )
        status = EvidenceState.SAMPLE_VERIFIED if has_citation_data else EvidenceState.NOT_TESTED
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=status,
            summary=(
                f"Found citation records in {len(raw_responses)} live response(s); claim-to-source validity still requires evaluation."
                if has_citation_data else
                "Citation analysis was not executed because inspectable response citation records are unavailable."
            ),
            findings=[],
            metadata={"response_count": len(raw_responses), "has_citation_data": bool(has_citation_data)},
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
            summary=(
                "Competitor report data is present; comparability of engines, queries, regions, and run windows has not been independently established here."
                if comp else "No competitor answer dataset was available for comparison."
            ),
            findings=[],
            metadata={"has_competitor_data": bool(comp)},
        )


class BrandAccuracySpecialist(BaseAeoSpecialist):
    specialist_id = "SPEC-13"
    specialist_name = "Brand Accuracy"
    responsibility = "Detect incorrect brand facts, outdated pricing, and unsupported recommendations in engine answers"

    def evaluate(self, report: Any) -> SpecialistResult:
        # No engine-answer claims are compared against an authoritative brand-fact
        # register in this method yet; report the gap honestly.
        return SpecialistResult(
            specialist_id=self.specialist_id,
            specialist_name=self.specialist_name,
            responsibility=self.responsibility,
            status=EvidenceState.NOT_TESTED,
            summary="Brand-fact accuracy was not tested because no claim-to-authoritative-fact comparison was performed.",
            findings=[],
            metadata={"measurement_status": "NOT_TESTED"},
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
            status=EvidenceState.SAMPLE_VERIFIED if findings else EvidenceState.NOT_TESTED,
            summary=(
                f"Counted {len(findings)} existing findings ({p0} P0 critical, {p1} P1 high); root-cause ranking and evidence validation are not performed by this specialist."
                if findings else "No findings were available to plan remediation against."
            ),
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
            status=EvidenceState.NOT_TESTED,
            summary="No remediation recrawl or acceptance-criteria retest was executed by this specialist.",
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
