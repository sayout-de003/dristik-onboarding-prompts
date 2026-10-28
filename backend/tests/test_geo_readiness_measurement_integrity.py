"""Regression tests for fail-closed GEO readiness scoring."""
from app.geo.readiness import (
    _compute_composite,
    _score_ai_engine_visibility,
    _score_citation_readiness,
    _score_external_authority,
    _score_factual_grounding,
    _score_retrieval_accessibility,
    evaluate_geo_readiness,
)


def test_empty_crawl_has_no_readiness_score_or_questions():
    report = evaluate_geo_readiness(website_url="https://example.com", pages=[])
    assert report.extractability_score is None
    assert report.questions_total == 0
    assert report.questions == []
    assert report.dimension_scores == {}
    assert "No analyzed pages" in report.headline


def test_unavailable_dimensions_have_null_score_and_unmeasured_state():
    dimensions = [
        _score_citation_readiness(None),
        _score_external_authority(None),
        _score_ai_engine_visibility(False, None, None),
        _score_retrieval_accessibility("https://example.com", None),
        _score_factual_grounding(None, 0),
    ]
    assert all(d.score is None for d in dimensions)
    assert all(d.is_measured is False for d in dimensions)
    assert all(d.band == "unmeasured" for d in dimensions)


def test_composite_is_null_when_no_weighted_dimensions_were_measured():
    assert _compute_composite({}) is None
    assert _compute_composite({
        "unavailable": _score_citation_readiness(None),
    }) is None


def test_legacy_readiness_entry_point_does_not_blend_citation_and_sentiment():
    from app.geo.scoring.geo_readiness import calculate_geo_readiness

    assert calculate_geo_readiness(75.0, 80.0) is None
