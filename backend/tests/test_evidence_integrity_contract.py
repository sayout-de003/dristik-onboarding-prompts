from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.evidence_integrity import (
    EvidenceBackedClaim,
    MetricValue,
    ValueStatus,
    validate_claim_evidence,
    validate_score,
)


def test_measured_metric_requires_provenance():
    with pytest.raises(ValidationError):
        MetricValue(name="TTFB", value=420, status=ValueStatus.MEASURED)


def test_measured_metric_accepts_timestamp_and_source():
    metric = MetricValue(
        name="TTFB",
        value=420,
        unit="ms",
        status=ValueStatus.MEASURED,
        source_refs=["ev_001"],
        observed_at=datetime.now(timezone.utc),
        is_live=True,
    )
    assert metric.value == 420


def test_unavailable_metric_cannot_be_zero_or_any_number():
    with pytest.raises(ValidationError):
        MetricValue(name="AI visibility", value=0, status=ValueStatus.UNAVAILABLE)


def test_unavailable_metric_is_explicit_and_null():
    metric = MetricValue(name="AI visibility", value=None, status=ValueStatus.NOT_CONFIGURED)
    assert metric.value is None


def test_derived_metric_requires_formula_and_inputs():
    with pytest.raises(ValidationError):
        MetricValue(name="CTR", value=3.4, status=ValueStatus.DERIVED, source_refs=["ev_1"])


def test_simulation_cannot_claim_live_measurement():
    with pytest.raises(ValidationError):
        MetricValue(
            name="AI visibility",
            value=0.7,
            status=ValueStatus.SIMULATION_ONLY,
            limitations="Synthetic prompt evaluation, not a live engine query.",
            is_live=True,
        )


def test_claim_must_reference_existing_evidence():
    claim = EvidenceBackedClaim(
        claim_id="f_1",
        text="The page has no title element.",
        evidence_refs=["ev_missing"],
        status=ValueStatus.MEASURED,
        scope="PAGE_VERIFIED",
    )
    with pytest.raises(ValueError, match="missing evidence"):
        validate_claim_evidence(claim, set())


def test_claim_with_no_evidence_is_not_publishable():
    claim = EvidenceBackedClaim(
        claim_id="f_2",
        text="The brand is invisible in AI search.",
        status=ValueStatus.MEASURED,
        scope="SITE_INFERRED",
    )
    with pytest.raises(ValueError, match="no evidence"):
        validate_claim_evidence(claim, set())


def test_estimated_claim_requires_limitations():
    claim = EvidenceBackedClaim(
        claim_id="f_3",
        text="This may improve conversions.",
        evidence_refs=["ev_1"],
        status=ValueStatus.ESTIMATED,
        scope="SITE_INFERRED",
    )
    with pytest.raises(ValueError, match="limitations"):
        validate_claim_evidence(claim, {"ev_1"})


@pytest.mark.parametrize("value,expected", [
    (None, None), (True, None), (-1, None), (101, None), (float("nan"), None),
    (0, 0.0), (72.5, 72.5), (100, 100.0),
])
def test_score_validation_never_fabricates_or_accepts_invalid_values(value, expected):
    assert validate_score(value) == expected
