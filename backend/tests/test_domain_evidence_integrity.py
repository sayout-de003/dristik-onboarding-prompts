"""Full-backend tests for domain evidence defaults and certification invariants.

These tests import the complete domain package and therefore run with the backend
runtime dependencies installed, unlike the lightweight core integrity CI job.
"""
from app.domain.models import ClaimLedger, ClaimLedgerEntry, FindingEvidence


def test_finding_evidence_does_not_assume_http_success_or_source():
    evidence = FindingEvidence()
    assert evidence.response_status is None
    assert evidence.source is None
    assert evidence.test_method is None
    assert evidence.evidence_subtype is None


def test_claim_ledger_cannot_certify_empty_or_unsupported_claims():
    empty = ClaimLedger(ledger_id="l1", run_id="r1", certified_zero_fake=True)
    assert empty.certified_zero_fake is False

    unsupported = ClaimLedgerEntry(
        claim_id="c1",
        claim="A metric was measured.",
        is_valid_fact=True,
        confidence=0.9,
        scope="PAGE_VERIFIED",
        timestamp="2026-10-25T00:00:00Z",
        evidence_ids=[],
    )
    ledger = ClaimLedger(
        ledger_id="l2",
        run_id="r2",
        entries=[unsupported],
        certified_zero_fake=True,
    )
    assert ledger.certified_zero_fake is False


def test_claim_ledger_certification_requires_explicit_supported_entries():
    entry = ClaimLedgerEntry(
        claim_id="c1",
        claim="The page returned HTTP 404.",
        is_valid_fact=True,
        confidence=0.9,
        scope="PAGE_VERIFIED",
        timestamp="2026-10-25T00:00:00Z",
        evidence_ids=["ev_001"],
    )
    ledger = ClaimLedger(ledger_id="l3", run_id="r3", entries=[entry])
    assert ledger.certified_zero_fake is True
