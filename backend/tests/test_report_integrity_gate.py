from types import SimpleNamespace

import pytest

from app.report_integrity_gate import validate_final_report


def _finding(finding_id="f_1", title="Missing canonical URL", refs=None, category="TECHNICAL_SEO"):
    return SimpleNamespace(
        finding_id=finding_id,
        title=title,
        finding=title,
        category=category,
        evidence_refs=list(refs or []),
        evidence_ids=[],
        evidence_references=[],
        evidence=[],
        severity="HIGH",
        materiality="MAJOR",
        confidence_rubric="LIKELY",
        source_agreement=1,
    )


def _report(findings=None, evidence=None, score=82.0):
    return SimpleNamespace(
        analysis_id="run_123",
        report_id="report_123",
        findings=list(findings if findings is not None else [_finding(refs=["ev_1"])]),
        evidence_ledger=evidence if evidence is not None else {"ev_1": {"url": "https://example.com/"}},
        scores=SimpleNamespace(overall_score=score, category_scores={}),
        quality_gate_results={},
        certification_status="NOT_ASSESSED",
        withheld_sections=[],
    )


def _manifest(findings=None):
    return SimpleNamespace(
        analysis_id="run_123",
        report_id="report_123",
        findings=list(findings if findings is not None else [SimpleNamespace(finding_id="f_1")]),
    )


def test_final_report_integrity_gate_passes_for_linked_evidence():
    result = validate_final_report(_report(), _manifest())
    assert result["status"] == "PASS"
    assert result["certified"] is True
    assert result["finding_count"] == 1


def test_final_report_integrity_gate_discloses_findings_without_evidence():
    result = validate_final_report(
        _report(findings=[_finding(refs=[])]),
        _manifest(),
    )
    assert result["status"] == "PASS_WITH_EVIDENCE_GAPS"
    assert result["certified"] is False
    assert result["unsupported_finding_ids"] == ["f_1"]


def test_final_report_integrity_gate_rejects_dangling_evidence_reference():
    with pytest.raises(ValueError, match="dangling evidence references"):
        validate_final_report(_report(findings=[_finding(refs=["ev_missing"])]), _manifest())


def test_final_report_integrity_gate_rejects_duplicate_finding_ids():
    findings = [_finding("f_1", "Missing canonical URL", ["ev_1"]),
                _finding("f_1", "Missing robots rule", ["ev_1"])]
    with pytest.raises(ValueError, match="duplicate finding_id"):
        validate_final_report(_report(findings=findings), _manifest())


def test_final_report_integrity_gate_rejects_duplicate_root_cause_keys():
    findings = [_finding("f_1", "Missing canonical URL", ["ev_1"]),
                _finding("f_2", "Missing canonical URL", ["ev_1"])]
    with pytest.raises(ValueError, match="duplicate finding root-cause keys"):
        validate_final_report(_report(findings=findings), _manifest())


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -1, 101, True, None])
def test_final_report_integrity_gate_rejects_invalid_overall_score(score):
    with pytest.raises(ValueError, match="overall score"):
        validate_final_report(_report(score=score), _manifest())


def test_final_report_integrity_gate_rejects_manifest_finding_mismatch():
    with pytest.raises(ValueError, match="manifest finding pins"):
        validate_final_report(_report(), _manifest(findings=[]))


def test_final_report_integrity_gate_rejects_category_weight_sum_mismatch():
    report = _report()
    report.scores.category_scores = {
        "TECHNICAL_SEO": SimpleNamespace(score=80.0, status="MEASURED", weight=0.6, weighted_score=48.0),
        "CONTENT": SimpleNamespace(score=70.0, status="MEASURED", weight=0.3, weighted_score=21.0),
    }
    with pytest.raises(ValueError, match="measured category weights do not sum"):
        validate_final_report(report, _manifest())


def test_final_report_integrity_gate_rejects_weighted_score_mismatch():
    report = _report()
    report.scores.category_scores = {
        "TECHNICAL_SEO": SimpleNamespace(score=80.0, status="MEASURED", weight=1.0, weighted_score=70.0),
    }
    with pytest.raises(ValueError, match="does not reconcile"):
        validate_final_report(report, _manifest())


def test_final_report_integrity_gate_rejects_numeric_score_for_unmeasured_category():
    report = _report()
    report.scores.category_scores = {
        "TECHNICAL_SEO": SimpleNamespace(score=0.0, status="NOT_MEASURED", weight=0.0, weighted_score=0.0),
    }
    with pytest.raises(ValueError, match="NOT_MEASURED but has a numeric score"):
        validate_final_report(report, _manifest())

