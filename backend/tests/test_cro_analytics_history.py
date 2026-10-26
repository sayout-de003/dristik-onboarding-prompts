"""History serialization must keep CRO scores distinct from the overall site score."""
from app.api.routes.audits.analyses import _listed_cro_metrics, _listed_cro_score
from app.cro.engine import build_cro_intelligence


def test_cro_history_reads_explicit_cro_audit_score():
    assert _listed_cro_score({"cro_audit": {"overall_cro_score": 71.5}}) == 71.5


def test_cro_history_reads_ux_conversion_category_score():
    report = {"scores": {"category_scores": {"UX_CONVERSION": {"score": 64}}}}
    assert _listed_cro_score(report) == 64.0


def test_cro_history_accepts_serialized_stored_report():
    assert _listed_cro_score('{"cro_audit":{"overall_cro_score":82}}') == 82.0


def test_cro_history_never_falls_back_to_site_wide_score():
    report = {"scores": {"overall_score": 94}, "cro_audit": {"overall_cro_score": None}}
    assert _listed_cro_score(report) is None


def test_cro_history_rejects_invalid_or_out_of_range_scores():
    assert _listed_cro_score({"cro_audit": {"overall_cro_score": True}}) is None
    assert _listed_cro_score({"cro_audit": {"overall_cro_score": 101}}) is None
    assert _listed_cro_score({"cro_audit": {"overall_cro_score": "unknown"}}) is None



def test_experience_dimension_formula_uses_only_observed_pass_fail_checks():
    report = build_cro_intelligence(
        pages=[{
            "url": "https://example.com/",
            "raw_html": (
                "<html><head><meta name='viewport' content='width=device-width'></head>"
                "<body><h1>Example service</h1><a href='/demo'>Book a demo</a>"
                "<form><input type='email' name='email'><button type='submit'>Send</button></form>"
                "</body></html>"
            ),
        }],
        discovered_urls=1,
    )
    experience = next(item for item in report.dimensions if item.id == "experience")
    observed = experience.passed_checks + experience.failed_checks
    assert observed > 0
    assert experience.score == round(100 * experience.passed_checks / observed, 1)
    assert experience.excluded_checks >= 0
    assert "not a conversion rate" in experience.note


def test_no_observed_pass_fail_checks_remain_unmeasured_not_zero():
    report = build_cro_intelligence(pages=[])
    experience = next(item for item in report.dimensions if item.id == "experience")
    assert experience.score is None
    assert experience.status == "UNMEASURED"



def test_history_exposes_only_metric_observations_stored_in_report():
    report = {
        "cro_audit": {
            "intelligence": {
                "metrics": [
                    {
                        "metric": "Conversion rate",
                        "formula": "Unique converters / eligible users",
                        "status": "MEASURED",
                        "value": 0.12,
                        "display": "12%",
                        "numerator": "unique converters",
                        "denominator": "eligible users",
                        "window": "last 28 days",
                        "note": "Measured",
                    },
                    {
                        "metric": "Revenue per visitor",
                        "formula": "Revenue / eligible visitors",
                        "status": "DATA_UNAVAILABLE",
                        "value": None,
                        "display": "Not measured",
                    },
                ]
            }
        }
    }
    metrics = _listed_cro_metrics(report)
    assert len(metrics) == 2
    assert metrics[0]["value"] == 0.12
    assert metrics[0]["denominator"] == "eligible users"
    assert metrics[1]["status"] == "DATA_UNAVAILABLE"
    assert metrics[1]["value"] is None


def test_history_does_not_create_metric_observations_when_missing():
    assert _listed_cro_metrics({"cro_audit": {"intelligence": {"metrics": None}}}) == []
    assert _listed_cro_metrics({"cro_audit": {}}) == []
