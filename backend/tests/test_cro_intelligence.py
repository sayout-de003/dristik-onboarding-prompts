"""Evidence rules for the 55-section CRO audit."""
from types import SimpleNamespace

from app.cro import (
    analyze_cro,
    build_cro_intelligence,
    build_from_executive_report,
    cro_report_generator,
    catalog,
    APPENDICES,
    EVIDENCE_STATES,
    METRIC_CATALOG,
    PARTS,
    SPECIALISTS,
)
from app.domain.enums import Category
from app.domain.models import PageEvidence


ALLOWED = set(EVIDENCE_STATES)
FINDING_FIELDS = {
    "finding_id",
    "priority",
    "status",
    "finding",
    "evidence",
    "observed_scope",
    "hypothesis",
    "recommended_action",
    "primary_metric",
    "guardrail_metrics",
    "validation",
    "impact_estimate",
    "owner",
}


def _checks(report):
    return [check for section in report.sections for check in section.checks]


def _section(report, number):
    return next(section for section in report.sections if section.number == f"{number:02d}")


def _metric(report, name):
    return next(item for item in report.metrics if item.metric == name)


def test_taxonomy_shape_and_evidence_states():
    report = build_cro_intelligence(pages=[])
    assert len(report.sections) == 55
    assert len(report.parts) == 7
    assert len(PARTS) == 7
    assert len(report.appendices) == 14
    assert len(APPENDICES) == 14
    assert len(report.specialists) == 16
    assert len(SPECIALISTS) == 16
    assert len(catalog()) == 55
    states = {check.evidence_state for check in _checks(report)}
    assert states <= ALLOWED
    conversion = _metric(report, "Conversion rate")
    assert conversion.value is None
    assert conversion.status == "DATA_UNAVAILABLE"
    experience = next(item for item in report.dimensions if item.id == "experience")
    assert experience.status == "UNMEASURED"
    assert experience.score is None
    assert "No crawled pages" in " ".join(check.summary for check in _checks(report))
    for spec, result in zip(METRIC_CATALOG, report.metrics):
        assert result.metric == spec["metric"]
        assert result.formula == spec["formula"]


def test_passive_cta_and_missing_label_do_not_forecast_lift():
    html = """
    <html><head><title>Offer</title><meta name="viewport" content="width=device-width"></head>
    <body>
      <h1>Plain widgets for teams</h1>
      <a class="btn" href="/next">Learn more</a>
      <form action="/lead"><input type="email" name="email" placeholder="Email"><button type="submit">Send</button></form>
    </body></html>
    """
    page = {"url": "https://example.com/", "raw_html": html}
    report = build_cro_intelligence(pages=[page])
    assert report.findings
    blob = " ".join(item.finding for item in report.findings).lower()
    assert "learn more" in blob or "label" in blob
    for finding in report.findings:
        payload = finding.model_dump()
        assert FINDING_FIELDS <= set(payload)
        assert "Not estimated" in finding.impact_estimate
        assert "%" not in finding.impact_estimate
        assert "lift" not in finding.impact_estimate.lower() or "does not" in finding.impact_estimate.lower()
    assert report.findings[0].finding_id == "CRO-001"
    assert report.findings[0].status == "Needs validation"


def test_ga4_key_event_rate_uses_sessions_and_does_not_invent_conversion_rate():
    measured = build_cro_intelligence(
        pages=[{"url": "https://example.com/", "h1": ["Hello"], "body_text": "A short page.", "viewport": "width=device-width"}],
        analytics={"state": "MEASURED", "sessions": 1000, "key_events": 25, "period": "last 28 days", "property": "GA4"},
    )
    conversion = _metric(measured, "Conversion rate")
    event_rate = _metric(measured, "Key-event rate per session")
    assert conversion.value is None
    assert conversion.status == "DATA_UNAVAILABLE"
    assert event_rate.value == 0.025
    assert event_rate.denominator == "sessions"
    assert "not a unique-user conversion rate" in event_rate.note
    qualified = _metric(measured, "Qualified lead rate")
    assert qualified.value is None
    funnel = next(item for item in measured.dimensions if item.id == "funnel")
    assert funnel.score is None
    assert funnel.status == "UNMEASURED"

    missing = build_cro_intelligence(
        pages=[{"url": "https://example.com/", "body_text": "Hello", "viewport": "width=device-width"}],
        analytics={"state": "MEASURED", "sessions": 1000, "conversions": 9, "period": "last 28 days"},
    )
    assert _metric(missing, "Conversion rate").value is None
    assert _metric(missing, "Key-event rate per session").value == 0.009

    zero = build_cro_intelligence(
        pages=[{"url": "https://example.com/", "body_text": "Hello", "viewport": "width=device-width"}],
        analytics={"state": "MEASURED", "sessions": 40, "key_events": 0, "period": "last 28 days"},
    )
    assert _metric(zero, "Conversion rate").value is None
    assert _metric(zero, "Conversion rate").status == "DATA_UNAVAILABLE"
    assert _metric(zero, "Key-event rate per session").value == 0
    assert _metric(zero, "Key-event rate per session").status == "MEASURED"

    disconnected = build_cro_intelligence(
        pages=[{"url": "https://example.com/", "body_text": "Hello", "viewport": "width=device-width"}],
        analytics={"state": "NOT_CONNECTED", "sessions": 0, "conversions": 0},
        search_console={"state": "MEASURED", "clicks": 500},
    )
    disconnected_rate = _metric(disconnected, "Conversion rate")
    assert disconnected_rate.value is None
    assert disconnected_rate.status == "DATA_UNAVAILABLE"
    assert "%" not in disconnected_rate.display
    measurement = next(item for item in disconnected.dimensions if item.id == "measurement")
    assert measurement.status == "UNMEASURED"
    assert measurement.score is None


def test_business_model_gates_specialized_sections():
    shop = build_cro_intelligence(pages=[{
        "url": "https://shop.example/product/widget",
        "body_text": "Add to cart. Buy now.",
        "h1": ["Widget"],
        "ctas": ["Add to cart"],
        "viewport": "width=device-width",
    }])
    assert "ecommerce" in shop.business_model
    assert "saas" not in shop.business_model
    assert all(check.evidence_state == "NOT_APPLICABLE" for check in _section(shop, 51).checks)
    assert any(check.evidence_state != "NOT_APPLICABLE" for check in _section(shop, 50).checks)

    lead = build_cro_intelligence(pages=[{
        "url": "https://agency.example/contact",
        "body_text": "Request a quote for the engagement.",
        "h1": ["Talk with us"],
        "viewport": "width=device-width",
    }])
    assert "lead_gen" in lead.business_model
    assert "ecommerce" not in lead.business_model
    assert all(check.evidence_state == "NOT_APPLICABLE" for check in _section(lead, 50).checks)

    newsletter = build_cro_intelligence(pages=[{
        "url": "https://notes.example/",
        "raw_html": "<html><body><h1>Notes</h1><form><input name='email'><button>Join</button></form></body></html>",
        "viewport": "width=device-width",
    }])
    assert "lead_gen" not in newsletter.business_model
    assert "ecommerce" not in newsletter.business_model


def test_limits_on_competitors_accessibility_timing_urgency_and_forecasts():
    page = {
        "url": "https://example.com/",
        "h1": ["Hello"],
        "body_text": "Limited time offer on the homepage. Average response is fine.",
        "viewport": "width=device-width",
        "ttfb_ms": 180,
    }
    report = build_cro_intelligence(
        pages=[page],
        competitor_domains=["rival.example"],
        wcag=SimpleNamespace(violations=[], conformance_status="PASS"),
    )
    competitor_text = " ".join(check.summary for check in _checks(report) if check.key == "competitor")
    assert "No competitor conversion rate is stated." in competitor_text
    assert "rival.example" in competitor_text
    assert "%" not in competitor_text
    accessibility = " ".join(
        check.summary for check in _checks(report) if check.key in {"wcag_scope", "ux_a11y_pointer", "contrast"}
    )
    assert "certificate" in accessibility.lower() or "conformance" in accessibility.lower()
    cwv = next(check for check in _checks(report) if check.key == "cwv")
    assert cwv.evidence_state == "DATA_UNAVAILABLE"
    assert cwv.outcome == "unmeasured"
    assert "not Lighthouse" in cwv.summary
    urgency = next(check for check in _checks(report) if check.key == "urgency")
    assert "limited time" in urgency.summary.lower()
    assert "raise" not in urgency.summary.lower()
    forecast = next(check for check in _checks(report) if check.key == "forecast_refused")
    assert "multiply" in forecast.summary
    behavior = next(check for check in _checks(report) if check.key == "behavior_not_clicks")
    assert "click pattern" in behavior.summary
    assert "motivation" in behavior.summary
    assert "representative sample" in report.scope_note.lower()


def test_html_and_json_include_every_section_title():
    report = build_cro_intelligence(
        pages=[{"url": "https://example.com/", "h1": ["Hello"], "body_text": "A page.", "viewport": "width=device-width"}],
        discovered_urls=12,
    )
    html = cro_report_generator.render_html_report(
        report, domain="example.com", website_url="https://example.com/", generated_at="today", analysis_id="run-1"
    )
    payload = cro_report_generator.render_json_report(
        report, domain="example.com", website_url="https://example.com/", generated_at="today", analysis_id="run-1"
    )
    for section in report.sections:
        assert section.title in html
        assert section.title in str(payload["sections"])
    assert "representative sample" in html.lower()
    assert "example.com" in html
    assert "<script" not in report.scope_note.lower()


def test_analyze_cro_keeps_legacy_score_and_stores_intelligence():
    html = "<html><body><h1>Hello</h1><a class=\"btn\" href=\"/pricing\">View pricing</a></body></html>"
    page = PageEvidence(url="https://example.com/", title="Hello", h1=["Hello"], word_count=40, raw_html=html)
    report, findings = analyze_cro([page], raw_html_map={page.url: html})
    assert isinstance(report.overall_cro_score, float)
    assert report.intelligence
    assert report.intelligence["sample_size"] == 1
    assert len(report.intelligence["sections"]) == 55
    assert all(finding.category == Category.UX_CONVERSION for finding in findings)


def test_rebuild_uses_measured_analytics_and_falls_back_to_stored_intelligence():
    page = SimpleNamespace(
        url="https://example.com/",
        title="Hello",
        h1=["Hello"],
        h2=[],
        word_count=20,
        viewport="width=device-width",
        body_text="Hello from the crawl.",
        status_code=200,
        ttfb_ms=0,
    )
    sealed = SimpleNamespace(
        crawl_manifest=SimpleNamespace(pages=[page], total_pages_discovered=8),
        google_performance={"analytics": {"state": "MEASURED", "sessions": 200, "key_events": 10, "period": "May"}, "search_console": {"state": "MEASURED", "clicks": 40}},
        business_profile=None,
        wcag_audit=None,
        competitor_seo_parity=SimpleNamespace(competitors=[SimpleNamespace(domain="example.com", is_target=True), SimpleNamespace(domain="other.example", is_target=False)]),
        cro_audit=None,
    )
    rebuilt = build_from_executive_report(sealed)
    assert rebuilt.sample_size == 1
    assert rebuilt.discovered_urls == 8
    assert _metric(rebuilt, "Conversion rate").value is None
    assert _metric(rebuilt, "Key-event rate per session").value == 0.05
    competitor_text = " ".join(check.summary for check in _checks(rebuilt) if check.key == "competitor")
    assert "other.example" in competitor_text
    assert "example.com" not in competitor_text

    stored = build_cro_intelligence(pages=[])
    fallback = build_from_executive_report(SimpleNamespace(
        crawl_manifest=SimpleNamespace(pages=[], total_pages_discovered=0),
        google_performance=None,
        cro_audit=SimpleNamespace(intelligence=stored.model_dump()),
    ))
    assert fallback.sample_size == 0
    assert len(fallback.sections) == 55
