"""On-page GEO readiness does not count as a live citation measurement."""
from app.intelligence.geo.readiness import evaluate_geo_readiness


def test_readiness_without_a_live_run_is_not_measured():
    report = evaluate_geo_readiness(website_url="https://example.com", pages=[])
    assert report.visibility_status == "NOT_CONFIGURED"
    # Empty crawl: no dimensions were measured, so do not synthesize a per-dimension score.
    assert report.dimension_scores == {}
