"""GEO before/after attribution must use comparable successful live runs."""
from types import SimpleNamespace

from app.geo.attribution_engine import GeoAttributionEngine


def row(
    query_id="q1",
    query_text="best tools",
    engine_id="engine",
    locale="en-US",
    model_version="model-v1",
    status="SUCCESS",
    is_live=True,
    was_mentioned=False,
    was_first_party_cited=False,
    mention_position=None,
    error_message=None,
):
    return SimpleNamespace(
        query_id=query_id,
        query_text=query_text,
        engine_id=engine_id,
        locale=locale,
        model_version=model_version,
        status=status,
        is_live=is_live,
        was_mentioned=was_mentioned,
        was_first_party_cited=was_first_party_cited,
        mention_position=mention_position,
        error_message=error_message,
    )


def test_attribution_does_not_invent_deltas_without_comparable_live_runs():
    report = GeoAttributionEngine().calculate_attribution(
        pre_patch_evaluations=[row(is_live=False, was_mentioned=False)],
        post_patch_evaluations=[row(is_live=True, was_mentioned=True)],
        target_domain="example.com",
        brand_name="Example",
    )
    assert report.status == "INSUFFICIENT_COMPARABLE_DATA"
    assert report.total_queries_evaluated == 0
    assert report.pre_mention_rate_pct is None
    assert report.mention_rate_delta_pct is None
    assert report.som_delta_pct is None


def test_attribution_rejects_changed_prompt_or_model_as_non_comparable():
    report = GeoAttributionEngine().calculate_attribution(
        pre_patch_evaluations=[row(query_text="best tools", model_version="model-v1")],
        post_patch_evaluations=[row(query_text="top tools", model_version="model-v2")],
        target_domain="example.com",
        brand_name="Example",
    )
    assert report.status == "INSUFFICIENT_COMPARABLE_DATA"
    assert report.total_queries_evaluated == 0


def test_attribution_reports_observed_change_without_causal_claim_or_som():
    report = GeoAttributionEngine().calculate_attribution(
        pre_patch_evaluations=[row(was_mentioned=False, was_first_party_cited=False)],
        post_patch_evaluations=[row(was_mentioned=True, was_first_party_cited=True)],
        target_domain="example.com",
        brand_name="Example",
    )
    assert report.status == "MEASURED"
    assert report.mention_rate_delta_pct == 100.0
    assert report.citation_rate_delta_pct == 100.0
    assert report.som_delta_pct is None
    assert "not proof" in report.measurement_note.lower()
