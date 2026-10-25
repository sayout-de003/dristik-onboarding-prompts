"""Regression tests for the customer-facing composite score contract."""
import math

import pytest

from app.domain.scoring.displayed_score import (
    align_story_score,
    displayed_composite,
    grade_for_displayed,
    story_matches_composite,
)


def report(*, categories=None, honest=None, geo=None, visibility=None):
    return {
        "scores": {"category_scores": categories or {}},
        "honest_scores": honest or {},
        "geo_readiness": geo or {},
        "ai_visibility_scorecard": visibility or {},
    }


def test_one_measured_pillar_is_normalized_without_inventing_missing_pillars():
    payload = report(categories={
        "TECHNICAL_SEO": {"score": 73.25, "status": "MEASURED"}
    })
    assert displayed_composite(payload) == 73.3


@pytest.mark.parametrize("invalid", [-1, 100.1, math.inf, math.nan, True, "80"])
def test_invalid_category_score_is_not_counted_as_measured(invalid):
    payload = report(categories={
        "TECHNICAL_SEO": {"score": invalid, "status": "MEASURED"}
    })
    assert displayed_composite(payload) is None


@pytest.mark.parametrize("status", ["NOT_MEASURED", "UNAVAILABLE", "NOT_CONNECTED", "NOT_CONFIGURED", "SIMULATION_ONLY"])
def test_unavailable_category_score_is_excluded_even_if_numeric(status):
    payload = report(categories={
        "TECHNICAL_SEO": {"score": 0, "status": status}
    })
    assert displayed_composite(payload) is None


def test_measured_zero_is_valid_and_not_treated_as_missing():
    payload = report(categories={
        "TECHNICAL_SEO": {"score": 0, "status": "MEASURED"}
    })
    assert displayed_composite(payload) == 0.0


def test_simulation_without_live_engine_response_does_not_create_ai_visibility_score():
    payload = report(visibility={"simulation_only": True, "citation_rate_pct": 99})
    assert displayed_composite(payload) is None


def test_live_measured_zero_citation_rate_is_counted_when_engine_response_exists():
    payload = report(visibility={
        "successful_runs": 1,
        "citation_rate_pct": 0,
        "observatory_records": [{"engine_id": "engine_a", "status": "success"}],
    })
    assert displayed_composite(payload) == 0.0


def test_story_score_alignment_uses_same_composite():
    story = "Overall score 55/100. Technical SEO score 82/100."
    aligned = align_story_score(story, 55, 71.4)
    assert "71.4/100 (grade C)" in aligned
    assert story_matches_composite(aligned, 71.4)
    assert grade_for_displayed(71.4) == "C"
