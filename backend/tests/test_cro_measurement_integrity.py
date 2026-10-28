"""Regression tests for evidence-safe CRO analytics and metric semantics."""
from app.cro.engine import _Obs, _Rules, _parse_page, _read_analytics, _read_search, build_cro_intelligence
from app.cro.metrics import experiment_lift, rate
from app.connectors.google.google_report import _analytics_from_payload, map_analytics
from app.cro.reporting import cro_report_generator


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
            "eligible_visitors": 100,
            "revenue": 500.0,
            "orders": 5,
        },
    )
    metric = _metric(report, "Revenue per visitor")
    assert metric.status == "MEASURED"
    assert metric.value == 5.0
    assert metric.denominator == "eligible visitors"


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

def test_generic_ga4_fields_do_not_become_conversion_denominators():
    report = build_cro_intelligence(
        pages=[],
        analytics={
            "state": "MEASURED",
            "sessions": 100,
            "conversions": 20,
            "users": 80,
            "revenue": 500.0,
        },
    )
    assert _metric(report, "Conversion rate").status == "DATA_UNAVAILABLE"
    assert _metric(report, "Conversion rate").value is None
    assert _metric(report, "Revenue per visitor").status == "DATA_UNAVAILABLE"


def test_finding_evidence_includes_the_observed_page_url():
    report = build_cro_intelligence(
        pages=[{
            "url": "https://example.com/landing",
            "raw_html": "<html><head><meta name='viewport' content='width=device-width'></head><body><h1>Our service</h1><p>" + ("Useful service content " * 20) + "</p></body></html>",
        }],
        discovered_urls=1,
    )
    finding = next((item for item in report.findings if "No CTA was found" in item.finding), None)
    assert finding is not None
    assert "https://example.com/landing" in finding.evidence
    assert finding.evidence_state == "SAMPLE_VERIFIED"

def test_ga4_payload_without_conversion_metric_does_not_publish_zero():
    result = _analytics_from_payload(
        "properties/123",
        {
            "metricHeaders": [{"name": "sessions"}],
            "totals": [{"metricValues": [{"value": "42"}]}],
            "rows": [],
        },
    )
    assert result["state"] == "MEASURED"
    assert result["sessions"] == 42
    assert "key_events" not in result
    assert "conversions" not in result


def test_legacy_ga4_summary_does_not_default_missing_conversions_to_zero():
    result = map_analytics({"state": "MEASURED", "sessions": 42, "property_id": "properties/123"})
    assert result["state"] == "MEASURED"
    assert result["sessions"] == 42
    assert "conversions" not in result
    assert "key_events" not in result


def test_html_report_exposes_sample_coverage_and_execution_limits():
    report = build_cro_intelligence(
        pages=[{
            "url": "https://example.com/",
            "raw_html": "<html><head><meta name='viewport' content='width=device-width'></head><body><h1>Example</h1></body></html>",
        }],
        discovered_urls=4,
    )
    html = cro_report_generator.render_html_report(report, domain="example.com")
    assert "Coverage and execution limits" in html
    assert "Scoring calibration" in html
    assert "NOT_BENCHMARK_CALIBRATED" in html
    assert "NOT_VERIFIED_BY_CRO_ENGINE" in html
    assert "NOT_EXECUTED" in html
    assert "25.0%" in html

def test_unmeasured_experience_and_funnel_scores_are_not_zero_scores():
    report = build_cro_intelligence(pages=[])
    experience = next(item for item in report.dimensions if item.id == "experience")
    funnel = next(item for item in report.dimensions if item.id == "funnel")
    assert experience.status == "UNMEASURED"
    assert experience.score is None
    assert funnel.status == "UNMEASURED"
    assert funnel.score is None


def test_report_does_not_claim_experiment_winner_or_uplift_without_experiment():
    report = build_cro_intelligence(
        pages=[{
            "url": "https://example.com/",
            "raw_html": "<html><head><meta name='viewport' content='width=device-width'></head><body><h1>Example</h1></body></html>",
        }],
    )
    html = cro_report_generator.render_html_report(report, domain="example.com")
    assert "No experiment was registered" in html
    assert "No winner is declared" in html
    assert "No implemented change or experiment outcome was supplied" in html

def test_rendered_dom_status_requires_explicit_browser_render_metadata():
    report = build_cro_intelligence(
        pages=[{
            "url": "https://example.com/",
            "state": "RENDERED",
            "rendered": True,
            "rendered_dom": "<html><body><h1>Client-rendered content</h1></body></html>",
        }],
        discovered_urls=1,
    )
    assert report.coverage["rendered_dom_status"] == "RENDERED_DOM_VERIFIED_FOR_SAMPLE"
    assert report.coverage["rendered_pages"] == 1
    assert report.coverage["journey_execution_status"] == "NOT_EXECUTED"

def test_cro_parser_consumes_rendered_dom_from_playwright_result():
    page = _parse_page(
        {
            "url": "https://example.com/checkout",
            "state": "RENDERED",
            "rendered": True,
            "status_code": 200,
            "rendered_dom": "<html><head><title>Checkout</title><meta name='viewport' content='width=device-width'></head><body><h1>Checkout</h1><button>Complete purchase</button></body></html>",
        },
        None,
    )
    assert page["title"] == "Checkout"
    assert page["h1"] == "Checkout"
    assert any(cta["text"] == "Complete purchase" for cta in page["ctas"])
    assert page["status"] == 200


def test_missing_http_status_is_not_rewritten_to_success():
    page = _parse_page(
        {
            "url": "https://example.com/checkout",
            "state": "UNAVAILABLE",
            "rendered": False,
            "status_code": None,
            "rendered_dom": None,
            "error": "Chromium unavailable",
        },
        None,
    )
    assert page["status"] is None
    report = build_cro_intelligence(
        pages=[{
            "url": "https://example.com/checkout",
            "state": "UNAVAILABLE",
            "rendered": False,
            "status_code": None,
            "rendered_dom": None,
            "error": "Chromium unavailable",
        }],
        discovered_urls=1,
    )
    assert not any("returned HTTP 200" in item.evidence for item in report.findings)


def test_rpv_specialist_does_not_use_sessions_as_visitor_denominator():
    obs = _Obs()
    obs.analytics = {
        "state": "MEASURED",
        "sessions": 100,
        "revenue": 500.0,
        "period": "last 30 days",
    }
    check = {
        "check_id": "metric_rpv",
        "section": "metrics",
        "part": "revenue",
        "section_title": "Revenue metrics",
        "label": "Revenue per visitor",
        "specialist": "cro.metrics",
        "key": "metric_rpv",
    }
    result = _Rules(obs).metric_rpv(check)
    assert result["evidence_state"] == "DATA_UNAVAILABLE"
    assert "sessions were not substituted for visitors" in result["summary"]


def test_rpv_specialist_uses_explicit_eligible_visitors():
    obs = _Obs()
    obs.analytics = {
        "state": "MEASURED",
        "sessions": 150,
        "eligible_visitors": 100,
        "revenue": 500.0,
        "period": "last 30 days",
    }
    check = {
        "check_id": "metric_rpv",
        "section": "metrics",
        "part": "revenue",
        "section_title": "Revenue metrics",
        "label": "Revenue per visitor",
        "specialist": "cro.metrics",
        "key": "metric_rpv",
    }
    result = _Rules(obs).metric_rpv(check)
    assert result["evidence_state"] == "VERIFIED"
    assert "500.0 attributed revenue ÷ 100 eligible visitors" in result["summary"]

