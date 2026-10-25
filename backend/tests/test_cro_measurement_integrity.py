"""Regression tests for evidence-safe CRO analytics and metric semantics."""
from app.cro.engine import _read_analytics, build_cro_intelligence
from app.cro.metrics import experiment_lift, rate


def _metric(report, name):
    return next(item for item in report.metrics if item.metric == name)


def test_unconnected_provider_payload_is_not_treated_as_measured():
    result = _read_analytics({
        "state": "FETCH_FAILED",
        "sessions": 100,
        "key_events": 20,
        "revenue": 500,
    })
    assert result["state"] == "FETCH_FAILED"
    assert result["sessions"] is None
    assert result["key_events"] is None
    assert result["revenue"] is None


def test_key_events_are_not_misreported_as_unique_conversion_rate():
    report = build_cro_intelligence(
        pages=[],
        analytics={
            "state": "MEASURED",
            "sessions": 100,
            "key_events": 125,
            "period": "2026-10-01/2026-10-24",
        },
    )
    conversion = _metric(report, "Conversion rate")
    event_rate = _metric(report, "Key-event rate per session")
    assert conversion.status == "DATA_UNAVAILABLE"
    assert conversion.value is None
    assert event_rate.status == "MEASURED"
    assert event_rate.value == 1.25
    assert "not a unique-user conversion rate" in event_rate.note


def test_conversion_rate_requires_unique_converters_and_eligible_users():
    report = build_cro_intelligence(
        pages=[],
        analytics={
            "state": "MEASURED",
            "sessions": 200,
            "key_events": 50,
            "unique_converters": 20,
            "eligible_users": 100,
        },
    )
    conversion = _metric(report, "Conversion rate")
    assert conversion.status == "MEASURED"
    assert conversion.value == 0.2
    assert conversion.numerator == "unique converters"
    assert conversion.denominator == "eligible users"


def test_invalid_non_finite_or_negative_analytics_are_withheld():
    for payload in (
        {"state": "MEASURED", "sessions": -1},
        {"state": "MEASURED", "sessions": float("nan")},
        {"state": "MEASURED", "sessions": 10, "engagement_rate_pct": 101},
        {"state": "MEASURED", "sessions": 10, "revenue": float("inf")},
    ):
        result = _read_analytics(payload)
        assert result["state"] == "INVALID_DATA"
        assert result["notice"]
        assert result["sessions"] is None
        assert result["key_events"] is None
        assert result["revenue"] is None


def test_math_helpers_reject_non_finite_values():
    assert rate(float("nan"), 10) is None
    assert rate(1, float("inf")) is None
    assert experiment_lift(float("nan"), 0.1) is None
    assert experiment_lift(0.2, float("inf")) is None
