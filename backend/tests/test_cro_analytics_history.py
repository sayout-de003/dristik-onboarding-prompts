"""History serialization must keep CRO scores distinct from the overall site score."""
from app.api.routes.audits.analyses import _listed_cro_score


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
