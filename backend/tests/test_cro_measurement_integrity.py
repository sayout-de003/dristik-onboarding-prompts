"""Regression tests for evidence-safe CRO analytics and metric semantics."""
from app.cro.engine import _parse_page, _read_analytics, _read_search, build_cro_intelligence
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

def test_revenue_per_visitor_requires_users_not_sessions():
    report = build_cro_intelligence(
        pages=[],
        analytics={
            "state": "MEASURED",
            "sessions": 100,
            "revenue": 500.0,
            "orders": 5,
        },
    )
    metric = _metric(report, "Revenue per visitor")
    assert metric.status == "DATA_UNAVAILABLE"
    assert metric.value is None
    assert "sessions are not substituted for visitors" in metric.note


def test_revenue_per_visitor_uses_eligible_users_denominator():
    report = build_cro_intelligence(
        pages=[],
        analytics={
            "state": "MEASURED",
            "sessions": 150,
            "eligible_users": 100,
            "revenue": 500.0,
            "orders": 5,
        },
    )
    metric = _metric(report, "Revenue per visitor")
    assert metric.status == "MEASURED"
    assert metric.value == 5.0
    assert metric.denominator == "eligible users"


def test_search_console_invalid_click_totals_are_not_cast_or_published():
    for value in (-1, float("nan"), float("inf"), True, 2.5, "10"):
        result = _read_search({"state": "MEASURED", "clicks": value})
        assert result["state"] == "INVALID_DATA"
        assert result["clicks"] is None


def test_cro_report_discloses_sample_and_unverified_rendering_and_journeys():
    report = build_cro_intelligence(
        pages=[{"url": "https://example.com/", "raw_html": "<html><head><meta name='viewport' content='width=device-width'></head><body><h1>Example</h1><a class='cta' href='/demo'>Book a demo</a></body></html>"}],
        discovered_urls=4,
    )
    assert report.coverage["status"] == "PARTIAL_SAMPLE"
    assert report.coverage["inspected_pages"] == 1
    assert report.coverage["discovered_urls"] == 4
    assert report.coverage["sample_coverage_pct"] == 25.0
    assert report.coverage["rendered_dom_status"] == "NOT_VERIFIED_BY_CRO_ENGINE"
    assert report.coverage["journey_execution_status"] == "NOT_EXECUTED"


def test_static_html_parser_detects_form_friction_and_ctas():
    page = _parse_page(
        {
            "url": "https://example.com/contact",
            "raw_html": (
                "<html><head><title>Contact</title></head><body>"
                "<a class='cta' href='/demo'>Book a demo</a>"
                "<form><input type='text' name='email' placeholder='Email address'>"
                "<button type='submit'>Send</button></form>"
                "</body></html>"
            ),
        },
        None,
    )
    assert any(item["text"] == "Book a demo" for item in page["ctas"])
    assert len(page["forms"]) == 1
    assert page["forms"][0]["missing_labels"] == 1
    assert page["forms"][0]["placeholder_only"] == 1
    assert page["forms"][0]["has_submit"] is True

