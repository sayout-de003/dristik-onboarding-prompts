"""Regression tests ensuring AEO specialists do not overstate completed work."""
from types import SimpleNamespace

from app.aeo.scoring import EvidenceState
from app.aeo.specialists import (
    EntityConsistencySpecialist,
    PassageAnalysisSpecialist,
    QuestionDiscoverySpecialist,
    SourceAttributionSpecialist,
    VerificationEngineSpecialist,
)


def test_passage_specialist_does_not_substitute_a_default_score():
    result = PassageAnalysisSpecialist().evaluate(SimpleNamespace(geo_readiness=None))
    assert result.status == EvidenceState.NOT_TESTED
    assert result.metadata["extractability_score"] is None


def test_entity_consistency_requires_more_than_a_domain_name():
    report = SimpleNamespace(domain="example.com", geo_readiness=None)
    result = EntityConsistencySpecialist().evaluate(report)
    assert result.status == EvidenceState.NOT_TESTED


def test_source_attribution_does_not_claim_verification_without_a_claim_source_map():
    result = SourceAttributionSpecialist().evaluate(SimpleNamespace())
    assert result.status == EvidenceState.NOT_TESTED
    assert "not tested" in result.summary.lower()


def test_verification_engine_does_not_claim_a_retest_was_executed():
    result = VerificationEngineSpecialist().evaluate(SimpleNamespace())
    assert result.status == EvidenceState.NOT_TESTED
    assert "no remediation recrawl" in result.summary.lower()
    assert "was executed" in result.summary.lower()


def test_question_discovery_does_not_claim_site_wide_absence_without_crawl_pages():
    report = SimpleNamespace(geo_readiness=None, page_reports=[], website_url="https://example.com")
    result = QuestionDiscoverySpecialist().evaluate(report)
    assert result.status == EvidenceState.NOT_TESTED
    assert result.findings == []
