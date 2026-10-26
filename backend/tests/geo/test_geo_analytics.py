from app.geo.api.analytics import _measure
from app.geo.pipeline_store import GeoPipelineStore, GeoQueryRecord


def _record(text, mentioned=False, cited=False, engine="Test Engine"):
    return GeoQueryRecord(
        query_id="Q-01",
        buyer_query="Example question",
        commercial_intent="Awareness",
        engine_id=engine.lower().replace(" ", "-"),
        engine_name=engine,
        raw_response_text=text,
        was_mentioned=mentioned,
        was_cited=cited,
        cited_urls=[],
    )


def test_measure_excludes_failed_requests_from_score_and_rates():
    records = [
        _record("The brand is mentioned.", mentioned=True),
        _record("Source: https://example.com", mentioned=True, cited=True),
        _record("API Error (Test Engine): timeout"),
        _record(""),
    ]
    result = _measure(records)
    assert result["status"] == "MEASURED"
    assert result["observations"] == 2
    assert result["attempted"] == 4
    assert result["failed_or_empty"] == 2
    assert result["mentions"] == 2
    assert result["citations"] == 1
    assert result["mention_rate_pct"] == 100.0
    assert result["citation_rate_pct"] == 50.0
    assert result["score"] == 77.5


def test_measure_reports_unavailable_when_no_successful_responses():
    result = _measure([
        _record("Request failed: timeout"),
        _record("API Error: missing key"),
    ])
    assert result["status"] == "UNAVAILABLE"
    assert result["score"] is None
    assert result["mention_rate_pct"] is None
    assert result["citation_rate_pct"] is None
    assert result["failed_or_empty"] == 2


def test_domain_history_returns_latest_limit_in_chronological_order(tmp_path):
    store = GeoPipelineStore(str(tmp_path / "geo-test.db"))
    with store._get_conn() as conn:
        for index, timestamp in enumerate(
            ["2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00", "2026-01-03T00:00:00+00:00"],
            start=1,
        ):
            conn.execute(
                """INSERT INTO geo_snapshots (
                    id, domain, brand_name, industry, timestamp, overall_score, delta_score,
                    total_queries, engines_measured_count, engine_scores_json, critical_blindspots_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"snap-{index}", "example.com", "Example", "SaaS", timestamp, 50 + index,
                 None, 1, 1, '{"Test Engine": 50}', "[]"),
            )
    history = store.get_domain_history("example.com", limit=2)
    assert [item.snapshot_id for item in history] == ["snap-2", "snap-3"]
