"""Regression tests for GEO measurement integrity and fail-closed behavior."""
from types import SimpleNamespace

from app.geo.attribution_engine import GeoAttributionEngine
from app.geo.benchmark_runner import GeoBenchmarkRunner
from app.geo.readiness import (
    _compute_composite,
    _score_citation_readiness,
    _score_external_authority,
)


def _row(*, query_id="q1", engine_id="engine-a", locale="en-US", model_version="model-v1",
         query_text="best vendor", status="SUCCESS", mentioned=False, cited=False, rank=None,
         error_message=None):
    return SimpleNamespace(
        query_id=query_id,
        engine_id=engine_id,
        locale=locale,
        model_version=model_version,
        query_text=query_text,
        status=status,
        was_mentioned=mentioned,
        was_first_party_cited=cited,
        mention_position=rank,
        error_message=error_message,
        is_live=True,
    )


def test_first_party_domain_requires_dns_label_boundary():
    runner = GeoBenchmarkRunner()
    domains, _, first_party = runner._classify_sources(
        ["https://notexample.com/about"], "", "example.com"
    )
    assert "notexample.com" in domains
    assert first_party is False

    _, _, subdomain_first_party = runner._classify_sources(
        ["https://docs.example.com/page"], "", "example.com"
    )
    assert subdomain_first_party is True


def test_first_party_domain_normalizes_scheme_www_port_and_trailing_dot():
    runner = GeoBenchmarkRunner()
    _, _, first_party = runner._classify_sources(
        ["https://www.example.com.:8443/path"], "", "https://example.com/"
    )
    assert first_party is True


def test_unavailable_passage_analysis_is_not_scored_as_neutral():
    dimension = _score_citation_readiness(None)
    assert dimension.is_measured is False
    assert dimension.measurement_note
    assert "NOT_MEASURED" in " ".join(dimension.evidence_notes)


def test_unmeasured_external_authority_has_no_neutral_credit():
    dimension = _score_external_authority(None)
    assert dimension.is_measured is False
    assert dimension.score is None
    assert "cannot be measured" in dimension.summary.lower()


def test_composite_with_no_measured_dimensions_is_none_not_fifty():
    assert _compute_composite({}) is None


def test_attribution_does_not_synthesize_share_of_model():
    engine = GeoAttributionEngine()
    report = engine.calculate_attribution(
        [_row(mentioned=False, cited=False)],
        [_row(mentioned=True, cited=True)],
        target_domain="example.com",
        brand_name="Example",
    )
    assert report.status == "MEASURED"
    assert report.mention_rate_delta_pct == 100.0
    assert report.citation_rate_delta_pct == 100.0
    assert report.pre_share_of_model_pct is None
    assert report.post_share_of_model_pct is None
    assert report.som_delta_pct is None
    assert "not proof of causal impact" in report.executive_roi_summary.lower()


def test_attribution_excludes_failed_runs_and_reports_insufficient_data():
    engine = GeoAttributionEngine()
    report = engine.calculate_attribution(
        [_row(status="TIMEOUT", mentioned=False)],
        [_row(status="SUCCESS", mentioned=True)],
        target_domain="example.com",
        brand_name="Example",
    )
    assert report.status == "INSUFFICIENT_COMPARABLE_DATA"
    assert report.total_queries_evaluated == 0
    assert report.pre_mention_rate_pct is None
    assert report.post_mention_rate_pct is None
    assert report.som_delta_pct is None


def test_attribution_requires_same_model_locale_and_prompt():
    engine = GeoAttributionEngine()
    report = engine.calculate_attribution(
        [_row(model_version="model-v1", locale="en-US", query_text="best vendor")],
        [_row(model_version="model-v2", locale="en-GB", query_text="best vendors")],
        target_domain="example.com",
        brand_name="Example",
    )
    assert report.status == "INSUFFICIENT_COMPARABLE_DATA"
    assert report.total_queries_evaluated == 0


def test_empty_crawl_does_not_create_readiness_findings_or_score():
    from app.geo.readiness import evaluate_geo_readiness

    report = evaluate_geo_readiness(website_url="https://example.com", pages=[])
    assert report.extractability_score is None
    assert report.questions_total == 0
    assert report.questions == []
    assert report.dimension_scores == {}
    assert "no analyzed pages" in report.headline.lower()


def test_brand_and_domain_mentions_use_boundaries():
    runner = GeoBenchmarkRunner()
    assert runner._detect_mention_and_position(
        "AcmeCorp is a vendor", "Acme", "example.com"
    ) == (False, None)
    assert runner._detect_mention_and_position(
        "A review of notexample.com", "Acme", "example.com"
    ) == (False, None)
    assert runner._detect_mention_and_position(
        "Acme is recommended", "Acme", "example.com"
    )[0] is True
