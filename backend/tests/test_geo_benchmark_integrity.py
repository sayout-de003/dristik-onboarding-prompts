"""Regression tests for GEO benchmark evidence classification."""

from app.geo.benchmark_runner import GeoBenchmarkRunner


def runner():
    # These pure classification helpers do not need the persistence store.
    return GeoBenchmarkRunner.__new__(GeoBenchmarkRunner)


def test_first_party_requires_exact_host_or_dns_subdomain():
    geo = runner()
    assert geo._is_first_party_host("example.com", "example.com")
    assert geo._is_first_party_host("www.example.com", "example.com")
    assert geo._is_first_party_host("docs.eu.example.com", "example.com")
    assert not geo._is_first_party_host("notexample.com", "example.com")
    assert not geo._is_first_party_host("example.com.attacker.test", "example.com")


def test_source_classification_does_not_accept_substring_lookalikes():
    geo = runner()
    domains, quality, first_party = geo._classify_sources(
        ["https://notexample.com/page", "https://example.com.attacker.test/path"],
        "Sources: https://notexample.com/about",
        "example.com",
    )
    assert first_party is False
    assert quality == "third_party"
    assert "notexample.com" in domains


def test_source_classification_accepts_first_party_subdomain():
    geo = runner()
    domains, quality, first_party = geo._classify_sources(
        ["https://docs.example.com/article"],
        "",
        "https://www.example.com/",
    )
    assert first_party is True
    assert quality == "first_party"
    assert domains == ["docs.example.com"]


def test_brand_mention_requires_word_boundaries():
    geo = runner()
    assert geo._detect_mention_and_position("Dristik is recommended.", "Dristik", "dristik.example")[0]
    assert not geo._detect_mention_and_position("NotDristik is a different product.", "Dristik", "dristik.example")[0]
    assert not geo._detect_mention_and_position("example.com.attacker.test", "Acme", "example.com")[0]


def test_provider_error_text_is_not_counted_as_a_brand_mention():
    geo = runner()
    assert geo._detect_mention_and_position("API Error: Dristik unavailable", "Dristik", "dristik.example") == (False, None)
    assert geo._detect_mention_and_position("Missing API key for Dristik", "Dristik", "dristik.example") == (False, None)


def test_share_of_model_is_unmeasured_without_successful_evaluations():
    geo = runner()
    metric = geo.calculate_share_of_model(
        evaluations=[],
        target_domain="example.com",
        brand_name="Example",
        competitors=["Competitor"],
    )
    assert metric.total_evaluated_queries == 0
    assert metric.share_of_model_pct is None
    assert metric.funnel_weighted_som_pct is None
    assert metric.first_party_citation_share_pct is None
    assert metric.recommendation_rank_score is None


def test_provider_response_defaults_are_not_live_evidence():
    from app.geo.adapters.base import EngineRawResponse

    response = EngineRawResponse(
        engine_id="example",
        engine_name="Example",
        model_version="unknown",
        raw_content="",
    )
    assert response.is_live is False
    assert response.status_code == 0


def test_share_of_model_uses_observed_competitor_mention_denominator():
    from app.geo.benchmark_runner import EvaluatedQueryRun

    geo = runner()
    evaluations = [
        EvaluatedQueryRun(
            query_id="q1", category="entity", query_text="Who is the target?",
            engine_id="engine", engine_name="Engine", model_version="v1",
            timestamp="2026-10-25T00:00:00Z", raw_response="Example is a provider.",
            was_mentioned=True, was_first_party_cited=False, status="SUCCESS", is_live=True,
        ),
        EvaluatedQueryRun(
            query_id="q2", category="comparative", query_text="Compare providers",
            engine_id="engine", engine_name="Engine", model_version="v1",
            timestamp="2026-10-25T00:00:00Z", raw_response="CompetitorCo is another provider.",
            was_mentioned=False, was_first_party_cited=False, status="SUCCESS", is_live=True,
        ),
    ]
    metric = geo.calculate_share_of_model(
        evaluations=evaluations,
        target_domain="example.com",
        brand_name="Example",
        competitors=["CompetitorCo"],
    )
    assert metric.total_evaluated_queries == 2
    assert metric.share_of_model_pct == 50.0
    assert metric.competitor_shares["competitorco"] == 50.0


def test_share_of_model_is_not_relabelled_mention_rate_without_competitors():
    from app.geo.benchmark_runner import EvaluatedQueryRun

    geo = runner()
    evaluation = EvaluatedQueryRun(
        query_id="q1", category="entity", query_text="Who is the target?",
        engine_id="engine", engine_name="Engine", model_version="v1",
        timestamp="2026-10-25T00:00:00Z", raw_response="Example is a provider.",
        was_mentioned=True, was_first_party_cited=False, status="SUCCESS", is_live=True,
    )
    metric = geo.calculate_share_of_model(
        evaluations=[evaluation],
        target_domain="example.com",
        brand_name="Example",
        competitors=[],
    )
    assert metric.share_of_model_pct is None
    assert metric.funnel_weighted_som_pct is None
