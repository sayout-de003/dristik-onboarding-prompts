import math

import pytest

from app.seo.audit.scoring.score_engine import ScoreEngine


def test_score_engine_calculation():
    engine = ScoreEngine()
    pillars = {
        "technical": 90.0,
        "content": 80.0,
        "geo": 70.0,
        "authority": 85.0,
        "ux": 90.0,
        "conversion": 80.0,
    }
    assert engine.calculate_overall_score(pillars) == 83.2


def test_missing_pillars_are_excluded_not_defaulted_to_70():
    engine = ScoreEngine()
    assert engine.calculate_overall_score({"technical": 100.0}) == 100.0
    assert engine.calculate_overall_score({"technical": 40.0, "content": None}) == 40.0


def test_no_measured_pillars_returns_no_score_error():
    with pytest.raises(ValueError, match="no measured pillars"):
        ScoreEngine().calculate_overall_score({})

    with pytest.raises(ValueError, match="no measured pillars"):
        ScoreEngine().calculate_overall_score({"technical": None, "geo": None})


@pytest.mark.parametrize("value", [-0.1, 100.1, math.inf, math.nan, True, "90"])
def test_invalid_measured_scores_fail_closed(value):
    with pytest.raises(ValueError, match="finite number from 0 to 100"):
        ScoreEngine().calculate_overall_score({"technical": value})


def test_zero_is_a_valid_measured_score():
    assert ScoreEngine().calculate_overall_score({"technical": 0}) == 0.0


def test_breakdown_discloses_partial_coverage_and_normalized_weights():
    breakdown = ScoreEngine().score_breakdown({"technical": 80, "content": 60})
    assert breakdown["overall_score"] == 71.1
    assert breakdown["score_status"] == "PARTIAL"
    assert breakdown["coverage_pct"] == 33.3
    assert breakdown["measured_pillars"] == ["content", "technical"]
    assert set(breakdown["unmeasured_pillars"]) == {
        "authority", "conversion", "geo", "ux"
    }
    assert sum(breakdown["normalized_weights"].values()) == pytest.approx(1.0, abs=1e-5)
