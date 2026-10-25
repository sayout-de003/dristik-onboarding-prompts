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
