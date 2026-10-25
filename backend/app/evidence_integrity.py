"""Evidence integrity contracts for customer-facing Dristik measurements.

This module provides fail-closed validation primitives for report assembly and
future API boundaries. It deliberately does not infer evidence from model text.
"""
from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ValueStatus(str, Enum):
    MEASURED = "MEASURED"
    DERIVED = "DERIVED"
    ESTIMATED = "ESTIMATED"
    INFERRED = "INFERRED"
    SIMULATION_ONLY = "SIMULATION_ONLY"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNAVAILABLE = "UNAVAILABLE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


_UNAVAILABLE = {
    ValueStatus.NOT_CONFIGURED,
    ValueStatus.UNAVAILABLE,
    ValueStatus.DATA_UNAVAILABLE,
}


class MetricValue(BaseModel):
    """A metric with an explicit epistemic status and reproducible provenance."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    value: Optional[float] = None
    unit: Optional[str] = None
    status: ValueStatus
    source_refs: list[str] = Field(default_factory=list)
    observed_at: Optional[datetime] = None
    formula: Optional[str] = None
    limitations: Optional[str] = None
    is_live: bool = False

    @model_validator(mode="after")
    def validate_provenance(self) -> "MetricValue":
        if self.value is not None and not math.isfinite(self.value):
            raise ValueError("metric value must be finite")
        if self.status in _UNAVAILABLE and self.value is not None:
            raise ValueError("unavailable metrics must not contain a numeric value")
        if self.status not in _UNAVAILABLE and self.value is None:
            raise ValueError("available metrics require a value")
        if self.status == ValueStatus.MEASURED:
            if not self.source_refs:
                raise ValueError("measured metrics require at least one source reference")
            if self.observed_at is None:
                raise ValueError("measured metrics require an observation timestamp")
        if self.status == ValueStatus.DERIVED:
            if not self.source_refs or not (self.formula or "").strip():
                raise ValueError("derived metrics require source references and a formula")
        if self.status in {ValueStatus.ESTIMATED, ValueStatus.INFERRED, ValueStatus.SIMULATION_ONLY}:
            if not (self.limitations or "").strip():
                raise ValueError(f"{self.status.value} metrics require a limitations statement")
        if self.status == ValueStatus.SIMULATION_ONLY and self.is_live:
            raise ValueError("simulation-only metrics cannot be marked live")
        return self


class EvidenceBackedClaim(BaseModel):
    """A reportable claim that must resolve to evidence in the same audit."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=4000)
    evidence_refs: list[str] = Field(default_factory=list)
    status: ValueStatus
    scope: str = Field(min_length=1, max_length=80)
    limitations: Optional[str] = None


def validate_claim_evidence(
    claim: EvidenceBackedClaim,
    available_evidence_ids: set[str],
) -> None:
    """Raise ValueError when a claim's provenance is missing or dangling."""
    if claim.status not in _UNAVAILABLE and not claim.evidence_refs:
        raise ValueError(f"claim {claim.claim_id!r} has no evidence references")
    missing = sorted(set(claim.evidence_refs) - available_evidence_ids)
    if missing:
        raise ValueError(
            f"claim {claim.claim_id!r} references missing evidence: {', '.join(missing)}"
        )
    if claim.status in {ValueStatus.ESTIMATED, ValueStatus.INFERRED, ValueStatus.SIMULATION_ONLY}:
        if not (claim.limitations or "").strip():
            raise ValueError(f"claim {claim.claim_id!r} must disclose limitations")


def validate_score(value: Any) -> Optional[float]:
    """Return a valid 0–100 score or None; never coerce missing data to zero."""
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    if not 0 <= float(value) <= 100:
        return None
    return float(value)
