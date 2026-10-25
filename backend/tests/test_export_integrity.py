import csv
import io
from types import SimpleNamespace

from app.domain.enums import Category, Severity
from app.domain.models import Finding
from app.reports.export_service import (
    generate_geo_remediation_csv,
    generate_remediation_tracker_csv,
    generate_urls_csv,
)


def test_url_export_does_not_default_unknown_http_status_to_200():
    page = SimpleNamespace(url="https://example.com/", title=None, meta_description=None)
    report = SimpleNamespace(
        crawl_manifest=SimpleNamespace(pages=[page]),
        page_reports=None,
        serp_appearance=None,
        click_depth=None,
    )
    rows = list(csv.DictReader(io.StringIO(generate_urls_csv(report))))
    assert len(rows) == 1
    assert rows[0]["Status Code"] == ""
    assert rows[0]["Indexability Status"] == "UNKNOWN"
    assert rows[0]["Word Count"] == ""
    assert rows[0]["TTFB (ms)"] == ""
    assert rows[0]["H1 Count"] == ""


def test_remediation_exports_do_not_invent_expected_conditions_or_verification():
    finding = Finding(
        finding_id="f_export_1",
        category=Category.TECHNICAL_SEO,
        severity=Severity.HIGH,
        title="Missing title",
        description="No title was observed.",
        recommendation="Add a unique title.",
        expected_condition=None,
        validation_criteria=None,
        confidence_basis="",
    )
    report = SimpleNamespace(findings=[finding])

    tracker = list(csv.DictReader(io.StringIO(generate_remediation_tracker_csv(report))))
    assert tracker[0]["Expected Condition"] == ""
    assert tracker[0]["Validation Criteria (Acceptance Test)"] == ""
    assert tracker[0]["Confidence Basis"] == ""
    assert "Automated re-crawl confirms zero errors." not in generate_remediation_tracker_csv(report)

    geo = list(csv.DictReader(io.StringIO(generate_geo_remediation_csv(report))))
    assert geo[0]["Reference Baseline (Expected Condition)"] == ""
    assert geo[0]["Validation Criteria (Fixed vs Verified)"] == ""
    assert geo[0]["Confidence & Provenance"] == ""
    assert "Machine observation" not in generate_geo_remediation_csv(report)
