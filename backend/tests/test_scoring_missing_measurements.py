"""Regression tests for fail-closed scoring when crawl inputs are absent."""
from app.domain.enums import BusinessIntent, Category
from app.domain.models import BusinessProfile
from app.domain.scoring.engine import ScoringEngine


def test_absent_transport_schema_and_readability_inputs_are_not_assumed_good():
    engine = ScoringEngine()
    profile = BusinessProfile(
        business_name="Example",
        domain="example.com",
        primary_intent=BusinessIntent.SAAS,
    )

    result = engine.calculate_scores(findings=[], business_profile=profile)
    technical = result.category_scores[Category.TECHNICAL_SEO.value]
    schema = result.category_scores[Category.SCHEMA.value]
    content = result.category_scores[Category.CONTENT.value]

    technical_checks = {check.check_id: check for check in technical.check_results}
    content_checks = {check.check_id: check for check in content.check_results}

    assert technical_checks["https_on_all_urls"].status == "NOT_MEASURED"
    assert technical_checks["tls_version_valid"].status == "NOT_MEASURED"
    assert schema.status == "NOT_MEASURED"
    assert schema.score is None
    assert content_checks["audience_flesch_reading_ease"].status == "NOT_MEASURED"


def test_explicit_transport_and_schema_measurements_are_honoured():
    engine = ScoringEngine()
    profile = BusinessProfile(
        business_name="Example",
        domain="example.com",
        primary_intent=BusinessIntent.SAAS,
    )

    result = engine.calculate_scores(
        findings=[],
        business_profile=profile,
        has_schema=False,
        is_https=False,
        readability=60.0,
    )

    technical_checks = {
        check.check_id: check
        for check in result.category_scores[Category.TECHNICAL_SEO.value].check_results
    }
    assert technical_checks["https_on_all_urls"].status == "DEFICIT"
    assert technical_checks["tls_version_valid"].status == "DEFICIT"
    assert result.category_scores[Category.SCHEMA.value].score is not None
