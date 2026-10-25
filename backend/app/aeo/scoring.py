"""
Dristik AEO 4-Pillar Decoupled Measurement & Core Metrics Engine (2026 Master Standard).

Governing Principle:
Strict separation of:
  A. Content Readiness (source quality)
  B. Technical Eligibility (accessibility & machine readability)
  C. Observed Answer Visibility (empirically recorded live tests)
  D. Business Outcomes (commercial attribution)

Zero Conflation & Zero Fabrication:
Never blend these four into an unexplained single score.
When external API runs or analytics connectors are absent, visibility and business
outcomes are marked NOT_TESTED or DATA_UNAVAILABLE.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EvidenceState(str, Enum):
    VERIFIED = "VERIFIED"
    SAMPLE_VERIFIED = "SAMPLE_VERIFIED"
    INFERRED = "INFERRED"
    NOT_TESTED = "NOT_TESTED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class MetricScore:
    name: str
    code: str
    value: Optional[float]
    unit: str  # "%", "count", "score_100", "currency"
    numerator: Optional[int] = None
    denominator: Optional[int] = None
    formula: str = ""
    state: EvidenceState = EvidenceState.VERIFIED
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if hasattr(self.state, "value") else str(self.state)
        return d


@dataclass
class ContentReadinessPillar:
    """Pillar A: Measures the quality and depth of the source material."""
    question_coverage_pct: Optional[float] = None
    answer_completeness_pct: Optional[float] = None
    clarity_extractability_score: Optional[float] = None
    factual_support_pct: Optional[float] = None
    freshness_consistency_score: Optional[float] = None
    composite_readiness_score: Optional[float] = None
    state: EvidenceState = EvidenceState.VERIFIED
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if hasattr(self.state, "value") else str(self.state)
        return d


@dataclass
class TechnicalEligibilityPillar:
    """Pillar B: Measures whether relevant sources can be crawled, rendered, and understood."""
    crawlability_score: Optional[float] = None
    indexability_score: Optional[float] = None
    internal_discovery_score: Optional[float] = None
    structured_data_validity_score: Optional[float] = None
    url_stability_score: Optional[float] = None
    composite_eligibility_score: Optional[float] = None
    state: EvidenceState = EvidenceState.VERIFIED
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if hasattr(self.state, "value") else str(self.state)
        return d


@dataclass
class ObservedAnswerVisibilityPillar:
    """Pillar C: Measures actual outcomes from defined empirical tests."""
    brand_mention_rate_pct: Optional[float] = None
    brand_recommendation_rate_pct: Optional[float] = None
    citation_rate_pct: Optional[float] = None
    citation_share_pct: Optional[float] = None
    citation_accuracy_pct: Optional[float] = None
    brand_fact_accuracy_pct: Optional[float] = None
    benchmark_coverage_pct: Optional[float] = None
    repeat_run_consistency_pct: Optional[float] = None
    engines_tested: List[str] = field(default_factory=list)
    state: EvidenceState = EvidenceState.NOT_TESTED
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if hasattr(self.state, "value") else str(self.state)
        return d


@dataclass
class BusinessOutcomesPillar:
    """Pillar D: Measures whether answer visibility contributes to measurable commercial results."""
    answer_page_visits: Optional[int] = None
    ai_referral_sessions: Optional[int] = None
    qualified_leads: Optional[int] = None
    assisted_conversions: Optional[int] = None
    attributed_revenue: Optional[float] = None
    ai_referral_conversion_rate_pct: Optional[float] = None
    state: EvidenceState = EvidenceState.DATA_UNAVAILABLE
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if hasattr(self.state, "value") else str(self.state)
        return d


@dataclass
class AeoFourPillarsScorecard:
    """Consolidated 4-Pillar Scorecard strictly preserving independence."""
    pillar_a_content_readiness: ContentReadinessPillar
    pillar_b_technical_eligibility: TechnicalEligibilityPillar
    pillar_c_observed_visibility: ObservedAnswerVisibilityPillar
    pillar_d_business_outcomes: BusinessOutcomesPillar
    core_metrics: List[MetricScore] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pillar_a_content_readiness": self.pillar_a_content_readiness.to_dict(),
            "pillar_b_technical_eligibility": self.pillar_b_technical_eligibility.to_dict(),
            "pillar_c_observed_visibility": self.pillar_c_observed_visibility.to_dict(),
            "pillar_d_business_outcomes": self.pillar_d_business_outcomes.to_dict(),
            "core_metrics": [m.to_dict() for m in self.core_metrics],
        }


class AeoMetricsCalculator:
    """
    Computes the 4-Pillar measurement metrics and the 10 Core Formulas
    from crawled page reports, geo evidence, and connected data sources.
    """

    @classmethod
    def calculate(cls, report: Any) -> AeoFourPillarsScorecard:
        g = getattr(report, "geo_readiness", None)
        v_card = getattr(report, "ai_visibility_scorecard", None)
        page_reports = getattr(report, "page_reports", []) or []
        findings = getattr(report, "findings", []) or []

        # -------------------------------------------------------------
        # Pillar A: Content Readiness
        # -------------------------------------------------------------
        q_total = getattr(g, "questions_total", 0) if g else 0
        q_supp = getattr(g, "questions_supported", 0) if g else 0
        q_part = getattr(g, "questions_partial", 0) if g else 0
        q_unsupp = getattr(g, "questions_unsupported", 0) if g else 0

        # Formula 1: Question coverage
        if q_total > 0:
            q_cov_pct = round(((q_supp + (0.5 * q_part)) / q_total) * 100.0, 1)
            q_cov_state = EvidenceState.SAMPLE_VERIFIED
        else:
            q_cov_pct = None
            q_cov_state = EvidenceState.NOT_TESTED

        # Formula 2: Answer completeness
        # Weighted required answer elements satisfied / required elements assessed
        if q_total > 0:
            ans_comp_pct = round((q_supp / q_total) * 100.0, 1)
        else:
            ans_comp_pct = None

        # Do not substitute question coverage for extractability: they are different
        # measurements. Missing metrics remain unavailable rather than becoming defaults.
        extract_score = getattr(g, "extractability_score", None) if g else None

        # Factual support requires an explicit assessed-claims denominator. A list of
        # contradictions alone cannot establish a factual-accuracy percentage.
        contradictions = getattr(report, "contradictions", []) or []
        claims_assessed = getattr(report, "claims_assessed", None)
        supported_claims = getattr(report, "supported_claims", None)
        if (
            isinstance(claims_assessed, int) and claims_assessed > 0
            and isinstance(supported_claims, int) and 0 <= supported_claims <= claims_assessed
        ):
            fact_support_pct = round((supported_claims / claims_assessed) * 100.0, 1)
        else:
            fact_support_pct = None

        # Freshness is not inferable from the absence of a "stale" finding. Require
        # a value explicitly produced by a freshness evaluator.
        freshness_score = getattr(g, "freshness_consistency_score", None) if g else None

        # A composite is published only when every declared component is measured.
        # This avoids silently changing weights based on which data happened to exist.
        comp_readiness = None
        readiness_components = (q_cov_pct, ans_comp_pct, extract_score, fact_support_pct)
        if all(isinstance(v, (int, float)) for v in readiness_components):
            comp_readiness = round(
                (q_cov_pct * 0.30) + (ans_comp_pct * 0.20)
                + (extract_score * 0.30) + (fact_support_pct * 0.20), 1
            )

        pillar_a = ContentReadinessPillar(
            question_coverage_pct=q_cov_pct,
            answer_completeness_pct=ans_comp_pct,
            clarity_extractability_score=extract_score,
            factual_support_pct=fact_support_pct,
            freshness_consistency_score=freshness_score,
            composite_readiness_score=comp_readiness,
            state=q_cov_state,
            notes="Evaluated directly against crawled first-party DOM passages.",
        )

        # -------------------------------------------------------------
        # Pillar B: Technical Eligibility
        # -------------------------------------------------------------
        n_pages = len(page_reports)
        if n_pages > 0:
            # Only calculate a dimension when its underlying observations are present.
            known_statuses = [getattr(p, "status_code", None) for p in page_reports]
            known_indexability = [getattr(p, "is_indexable", None) for p in page_reports]
            known_schema_validity = [getattr(p, "schema_valid", None) for p in page_reports]
            known_discovery = [getattr(p, "internal_discovery_verified", None) for p in page_reports]
            known_url_stability = [getattr(p, "url_stability_verified", None) for p in page_reports]

            crawl_score = (
                round(sum(1 for code in known_statuses if isinstance(code, int) and 200 <= code < 400)
                      / sum(1 for code in known_statuses if isinstance(code, int)) * 100.0, 1)
                if any(isinstance(code, int) for code in known_statuses) else None
            )
            index_score = (
                round(sum(1 for value in known_indexability if value is True)
                      / sum(1 for value in known_indexability if isinstance(value, bool)) * 100.0, 1)
                if any(isinstance(value, bool) for value in known_indexability) else None
            )
            schema_score = (
                round(sum(1 for value in known_schema_validity if value is True)
                      / sum(1 for value in known_schema_validity if isinstance(value, bool)) * 100.0, 1)
                if any(isinstance(value, bool) for value in known_schema_validity) else None
            )
            internal_disc_score = (
                round(sum(1 for value in known_discovery if value is True)
                      / sum(1 for value in known_discovery if isinstance(value, bool)) * 100.0, 1)
                if any(isinstance(value, bool) for value in known_discovery) else None
            )
            url_stab_score = (
                round(sum(1 for value in known_url_stability if value is True)
                      / sum(1 for value in known_url_stability if isinstance(value, bool)) * 100.0, 1)
                if any(isinstance(value, bool) for value in known_url_stability) else None
            )

            eligibility_components = (crawl_score, index_score, schema_score, internal_disc_score, url_stab_score)
            comp_eligibility = None
            if all(isinstance(value, (int, float)) for value in eligibility_components):
                comp_eligibility = round(
                    crawl_score * 0.25 + index_score * 0.25 + schema_score * 0.20
                    + internal_disc_score * 0.15 + url_stab_score * 0.15, 1
                )
            technical_state = (
                EvidenceState.VERIFIED if comp_eligibility is not None
                else EvidenceState.SAMPLE_VERIFIED if any(value is not None for value in eligibility_components)
                else EvidenceState.DATA_UNAVAILABLE
            )
            pillar_b = TechnicalEligibilityPillar(
                crawlability_score=crawl_score,
                indexability_score=index_score,
                internal_discovery_score=internal_disc_score,
                structured_data_validity_score=schema_score,
                url_stability_score=url_stab_score,
                composite_eligibility_score=comp_eligibility,
                state=technical_state,
                notes="Metrics are computed only from explicit page-level observations; missing dimensions remain unavailable.",
            )
        else:
            pillar_b = TechnicalEligibilityPillar(
                crawlability_score=None,
                indexability_score=None,
                composite_eligibility_score=None,
                state=EvidenceState.DATA_UNAVAILABLE,
                notes="No crawled pages available in analysis payload.",
            )

        # -------------------------------------------------------------
        # Pillar C: Observed Answer Visibility
        # -------------------------------------------------------------
        v_status = getattr(v_card, "status", "NOT_MEASURED") if v_card else "NOT_MEASURED"
        engines_measured = getattr(v_card, "engines_measured", 0) if v_card else 0
        measured_cit_rate = getattr(report, "ai_visibility_score", None)

        if v_status == "MEASURED" and engines_measured > 0:
            # MEASURED is not sufficient by itself: never invent values for fields
            # absent from the actual scorecard or response ledger.
            mention_rate = getattr(v_card, "mention_rate_pct", None)
            rec_rate = getattr(v_card, "recommendation_rate_pct", None)
            cit_rate = measured_cit_rate * 100.0 if measured_cit_rate is not None else getattr(v_card, "citation_rate_pct", None)
            cit_share = getattr(v_card, "citation_share_pct", None)
            cit_acc = getattr(v_card, "citation_accuracy_pct", None)
            fact_acc = getattr(v_card, "brand_fact_accuracy_pct", None)
            bm_cov = getattr(v_card, "benchmark_coverage_pct", None)
            consistency = getattr(v_card, "repeat_consistency_pct", None)
            engines_list = getattr(v_card, "platforms", []) or []
            has_any_measurement = any(
                isinstance(value, (int, float))
                for value in (mention_rate, rec_rate, cit_rate, cit_share, cit_acc, fact_acc, bm_cov, consistency)
            )
            c_state = EvidenceState.SAMPLE_VERIFIED if has_any_measurement else EvidenceState.DATA_UNAVAILABLE
            c_notes = (
                f"Partial measurements recorded for {engines_measured} answer platforms; unmeasured metrics are omitted."
                if has_any_measurement
                else "The visibility run is marked measured but contains no numeric metric values."
            )
        else:
            mention_rate = None
            rec_rate = None
            cit_rate = None
            cit_share = None
            cit_acc = None
            fact_acc = None
            bm_cov = None
            consistency = None
            c_state = EvidenceState.NOT_TESTED
            c_notes = "Live visibility requires connected external engine APIs. Direct observations not yet recorded."
            engines_list = []

        pillar_c = ObservedAnswerVisibilityPillar(
            brand_mention_rate_pct=mention_rate,
            brand_recommendation_rate_pct=rec_rate,
            citation_rate_pct=cit_rate,
            citation_share_pct=cit_share,
            citation_accuracy_pct=cit_acc,
            brand_fact_accuracy_pct=fact_acc,
            benchmark_coverage_pct=bm_cov,
            repeat_run_consistency_pct=consistency,
            engines_tested=engines_list,
            state=c_state,
            notes=c_notes,
        )

        # -------------------------------------------------------------
        # Pillar D: Business Outcomes
        # -------------------------------------------------------------
        # In absence of Google Analytics / Search Console OAuth credentials, report DATA_UNAVAILABLE
        pillar_d = BusinessOutcomesPillar(
            answer_page_visits=None,
            ai_referral_sessions=None,
            qualified_leads=None,
            assisted_conversions=None,
            attributed_revenue=None,
            ai_referral_conversion_rate_pct=None,
            state=EvidenceState.DATA_UNAVAILABLE,
            notes="Requires authenticated Google Analytics 4 or Search Console connector. Zero synthetic conversions reported.",
        )

        # -------------------------------------------------------------
        # 10 Core Formulas Registry
        # -------------------------------------------------------------
        core_metrics = [
            # 1. Question coverage
            MetricScore(
                name="Question Coverage",
                code="AEO-MET-01",
                value=q_cov_pct,
                unit="%",
                numerator=round(q_supp + (0.5 * q_part)) if q_total > 0 else None,
                denominator=q_total if q_total > 0 else None,
                formula="Relevant questions with a usable, verified answer ÷ relevant questions assessed",
                state=q_cov_state,
                notes="Assessed against first-party crawled DOM content.",
            ),
            # 2. Answer completeness
            MetricScore(
                name="Answer Completeness",
                code="AEO-MET-02",
                value=ans_comp_pct,
                unit="%",
                numerator=q_supp if q_total > 0 else None,
                denominator=q_total if q_total > 0 else None,
                formula="Weighted required answer elements satisfied ÷ required elements assessed",
                state=q_cov_state,
                notes="Evaluates presence of direct answer passage, context, and caveats.",
            ),
            # 3. Brand mention rate
            MetricScore(
                name="Brand Mention Rate",
                code="AEO-MET-03",
                value=mention_rate,
                unit="%",
                numerator=None,
                denominator=None,
                formula="Valid tested responses mentioning the brand ÷ valid responses",
                state=c_state,
                notes="Live test runs across external answer engines.",
            ),
            # 4. Brand recommendation rate
            MetricScore(
                name="Brand Recommendation Rate",
                code="AEO-MET-04",
                value=rec_rate,
                unit="%",
                numerator=None,
                denominator=None,
                formula="Valid responses recommending the brand ÷ valid responses",
                state=c_state,
                notes="Tests where brand is specifically endorsed rather than merely listed.",
            ),
            # 5. Citation rate
            MetricScore(
                name="Citation Rate",
                code="AEO-MET-05",
                value=cit_rate,
                unit="%",
                numerator=None,
                denominator=None,
                formula="Valid responses containing at least one qualifying citation to brand's domain ÷ valid responses",
                state=c_state,
                notes="Empirical live citation capture.",
            ),
            # 6. Citation share
            MetricScore(
                name="Citation Share",
                code="AEO-MET-06",
                value=cit_share,
                unit="%",
                numerator=None,
                denominator=None,
                formula="Qualifying citations to brand ÷ qualifying citations to all tracked domains",
                state=c_state,
                notes="Competitive citation proportion.",
            ),
            # 7. Citation accuracy
            MetricScore(
                name="Citation Accuracy",
                code="AEO-MET-07",
                value=cit_acc,
                unit="%",
                numerator=None,
                denominator=None,
                formula="Verified relevant and correctly attributed citations ÷ citations assessed",
                state=c_state,
                notes="Verifies cited URL genuinely contains the asserted claim.",
            ),
            # 8. Brand fact accuracy
            MetricScore(
                name="Brand Fact Accuracy",
                code="AEO-MET-08",
                value=fact_acc,
                unit="%",
                numerator=None,
                denominator=None,
                formula="Verified correct brand claims ÷ brand claims assessed",
                state=c_state,
                notes="Checks for hallucinated pricing, features, or company facts.",
            ),
            # 9. Benchmark coverage
            MetricScore(
                name="Benchmark Coverage",
                code="AEO-MET-09",
                value=bm_cov,
                unit="%",
                numerator=None,
                denominator=None,
                formula="Completed valid test cases ÷ planned test cases",
                state=c_state,
                notes="Planned multi-engine test suite execution rate.",
            ),
            # 10. AI referral conversion rate
            MetricScore(
                name="AI Referral Conversion Rate",
                code="AEO-MET-10",
                value=None,
                unit="%",
                numerator=None,
                denominator=None,
                formula="Attributed conversions ÷ eligible AI referral sessions",
                state=EvidenceState.DATA_UNAVAILABLE,
                notes="Requires Google Analytics 4 integration.",
            ),
        ]

        return AeoFourPillarsScorecard(
            pillar_a_content_readiness=pillar_a,
            pillar_b_technical_eligibility=pillar_b,
            pillar_c_observed_visibility=pillar_c,
            pillar_d_business_outcomes=pillar_d,
            core_metrics=core_metrics,
        )
