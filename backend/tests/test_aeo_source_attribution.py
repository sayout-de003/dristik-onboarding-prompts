"""Tests for explicit, non-fabricating AEO source attribution."""
from types import SimpleNamespace

from app.aeo.scoring import EvidenceState
from app.aeo.source_attribution import SourceAttributionEvaluator
from app.aeo.specialists import SourceAttributionSpecialist


def test_empty_claim_inventory_is_not_tested():
    result = SourceAttributionEvaluator.evaluate(None)
    assert result.status == "NOT_TESTED"
    assert result.attribution_coverage_pct is None
    assert result.total_claims == 0


def test_attribution_requires_absolute_http_url_and_source_excerpt():
    result = SourceAttributionEvaluator.evaluate([
        {"claim_id": "C1", "claim_text": "The product supports SSO.", "source_url": "https://docs.example.com/sso", "evidence_snippet": "SSO is supported."},
        {"claim_id": "C2", "claim_text": "99.99% uptime.", "source_url": "", "evidence_snippet": "We are reliable."},
        {"claim_id": "C3", "claim_text": "Certified.", "source_url": "javascript:alert(1)", "evidence_snippet": "Certified."},
        {"claim_id": "C4", "claim_text": "Fast.", "source_url": "https://example.com/performance", "evidence_snippet": ""},
    ])

    assert result.status == "MEASURED"
    assert result.total_claims == 4
    assert result.attributable_claims == 1
    assert result.missing_source_claims == 1
    assert result.invalid_source_url_claims == 1
    assert result.missing_snippet_claims == 1
    assert result.attribution_coverage_pct == 25.0
    assert result.claims[0].status == "ATTRIBUTED"
    assert "not semantic entailment" in result.limitations[0].lower()


def test_unassessable_claims_do_not_inflate_attribution_denominator():
    result = SourceAttributionEvaluator.evaluate([
        {"claim_id": "C1", "claim_text": "", "source_url": "https://example.com", "evidence_snippet": "Text"},
        {"claim_id": "C2", "claim_text": "Has a source.", "source_url": "https://example.com", "evidence_snippet": "Text"},
    ])
    assert result.attribution_coverage_pct == 100.0
    assert result.claims[0].status == "UNASSESSABLE"


def test_specialist_reports_missing_source_links_as_findings():
    report = SimpleNamespace(assessed_claims=[
        {"claim_id": "C-PRICE", "claim_text": "The service costs $99 monthly."},
        {"claim_id": "C-SSO", "claim_text": "Supports SSO.", "source_url": "https://docs.example.com/sso", "evidence_snippet": "SSO is supported."},
    ])
    result = SourceAttributionSpecialist().evaluate(report)

    assert result.status == EvidenceState.SAMPLE_VERIFIED
    assert result.metadata["attribution_coverage_pct"] == 50.0
    assert len(result.findings) == 1
    assert result.findings[0].finding_id == "AEO-SOURCE-C-PRICE"
    assert "provenance completeness only" in result.findings[0].limitations.lower()


def test_specialist_does_not_mark_traceability_as_factual_verification():
    report = SimpleNamespace(assessed_claims=[
        {"claim_id": "C1", "claim_text": "A claim.", "source_url": "https://example.com", "evidence_snippet": "A passage."}
    ])
    result = SourceAttributionSpecialist().evaluate(report)
    assert result.status == EvidenceState.SAMPLE_VERIFIED
    assert "does not establish semantic support" in result.summary.lower()
