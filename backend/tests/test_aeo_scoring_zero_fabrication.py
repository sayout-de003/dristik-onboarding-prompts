"""Regression tests for AEO zero-fabrication scoring behavior."""
from types import SimpleNamespace

from app.aeo.scoring import AeoMetricsCalculator, EvidenceState


def _report(**overrides):
    values = {
        "geo_readiness": None,
        "ai_visibility_scorecard": None,
        "ai_visibility_score": None,
        "page_reports": [],
        "findings": [],
        "contradictions": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_empty_report_does_not_receive_synthetic_readiness_or_technical_scores():
    scorecard = AeoMetricsCalculator.calculate(_report())

    content = scorecard.pillar_a_content_readiness
    technical = scorecard.pillar_b_technical_eligibility
    visibility = scorecard.pillar_c_observed_visibility

    assert content.question_coverage_pct is None
    assert content.answer_completeness_pct is None
    assert content.clarity_extractability_score is None
    assert content.factual_support_pct is None
    assert content.freshness_consistency_score is None
    assert content.composite_readiness_score is None
    assert technical.crawlability_score is None
    assert technical.indexability_score is None
    assert technical.internal_discovery_score is None
    assert technical.url_stability_score is None
    assert technical.composite_eligibility_score is None
    assert visibility.brand_mention_rate_pct is None
    assert visibility.citation_rate_pct is None
    assert visibility.state == EvidenceState.NOT_TESTED


def test_measured_visibility_status_alone_does_not_create_rates():
    visibility_card = SimpleNamespace(status="MEASURED", engines_measured=3)
    scorecard = AeoMetricsCalculator.calculate(
        _report(ai_visibility_scorecard=visibility_card)
    )
    visibility = scorecard.pillar_c_observed_visibility

    assert visibility.brand_mention_rate_pct is None
    assert visibility.brand_recommendation_rate_pct is None
    assert visibility.citation_rate_pct is None
    assert visibility.citation_share_pct is None
    assert visibility.citation_accuracy_pct is None
    assert visibility.brand_fact_accuracy_pct is None
    assert visibility.benchmark_coverage_pct is None
    assert visibility.repeat_run_consistency_pct is None
    assert visibility.engines_tested == []
    assert visibility.state == EvidenceState.DATA_UNAVAILABLE


def test_technical_metrics_use_only_explicit_observations():
    pages = [
        SimpleNamespace(status_code=200, is_indexable=True),
        SimpleNamespace(status_code=404, is_indexable=False),
        SimpleNamespace(),  # missing observations must not default to success
    ]
    scorecard = AeoMetricsCalculator.calculate(_report(page_reports=pages))
    technical = scorecard.pillar_b_technical_eligibility

    assert technical.crawlability_score == 50.0
    assert technical.indexability_score == 50.0
    assert technical.structured_data_validity_score is None
    assert technical.internal_discovery_score is None
    assert technical.url_stability_score is None
    assert technical.composite_eligibility_score is None
    assert technical.state == EvidenceState.SAMPLE_VERIFIED


def test_claim_support_requires_an_explicit_assessed_claim_denominator():
    geo = SimpleNamespace(
        questions_total=4,
        questions_supported=2,
        questions_partial=1,
        questions_unsupported=1,
        extractability_score=70,
    )
    scorecard = AeoMetricsCalculator.calculate(
        _report(geo_readiness=geo, contradictions=[object()])
    )

    # A contradiction count alone is not a factual-accuracy denominator.
    assert scorecard.pillar_a_content_readiness.factual_support_pct is None
    assert scorecard.pillar_a_content_readiness.composite_readiness_score is None


def test_claim_support_is_calculated_from_measured_claim_counts():
    geo = SimpleNamespace(
        questions_total=4,
        questions_supported=2,
        questions_partial=1,
        questions_unsupported=1,
        extractability_score=70,
        freshness_consistency_score=75,
    )
    scorecard = AeoMetricsCalculator.calculate(
        _report(
            geo_readiness=geo,
            claims_assessed=10,
            supported_claims=8,
        )
    )
    content = scorecard.pillar_a_content_readiness

    assert content.factual_support_pct == 80.0
    assert content.composite_readiness_score == 65.8
