"""Deterministic report quality gates.

This module is intentionally independent from LLM output and PDF rendering. Call
validate_report_payload before persisting or exporting a final report.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    observed_at: str = Field(min_length=1)
    collection_method: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    observation: str = Field(min_length=1)


class FindingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_id: str = Field(min_length=1)
    title: str = Field(min_length=4, max_length=240)
    severity: str
    status: str
    evidence_refs: list[str] = Field(min_length=1)
    affected_urls: list[str] = Field(min_length=1)
    what_observed: str = Field(min_length=12)
    what_it_means: str = Field(min_length=12)
    why_it_matters: str = Field(min_length=12)
    how_to_fix: str = Field(min_length=12)
    how_to_verify: str = Field(min_length=12)
    limitations: str | None = None

    @model_validator(mode="after")
    def validate_classification(self) -> "FindingRecord":
        if self.severity.upper() not in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}:
            raise ValueError("severity must use the canonical severity model")
        if self.status.lower() not in {
            "verified", "inferred", "unavailable", "not_applicable",
            "fixed_not_verified", "verified_fixed",
        }:
            raise ValueError("unsupported finding evidence/lifecycle status")
        if self.status.lower() == "inferred" and not (self.limitations or "").strip():
            raise ValueError("inferred findings must disclose limitations")
        if self.status.lower() in {"unavailable", "not_applicable"}:
            raise ValueError("unavailable/not-applicable checks must be represented as checks, not findings")
        return self


class ReportScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    composite: float = Field(ge=0, le=100)
    components: dict[str, float]
    weights: dict[str, float]
    exclusions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def reconcile(self) -> "ReportScore":
        if not self.components:
            raise ValueError("at least one score component is required")
        if set(self.components) != set(self.weights):
            raise ValueError("score components and weights must have identical keys")
        if any(not 0 <= v <= 100 for v in self.components.values()):
            raise ValueError("component scores must be between 0 and 100")
        if any(not 0 <= v <= 1 for v in self.weights.values()):
            raise ValueError("weights must be between 0 and 1")
        total = sum(self.weights.values())
        if total <= 0 or abs(total - 1.0) > 1e-6:
            raise ValueError("available component weights must sum to 1")
        expected = sum(self.components[k] * self.weights[k] for k in self.components)
        if abs(expected - self.composite) > 0.11:
            raise ValueError(f"composite score {self.composite} does not reconcile with components ({expected:.2f})")
        return self


def validate_report_payload(
    findings: Iterable[dict[str, Any]],
    evidence: Iterable[dict[str, Any]],
    score: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed on dangling evidence, duplicate findings, or inconsistent scores."""
    evidence_models = [EvidenceRecord.model_validate(item) for item in evidence]
    evidence_by_id = {item.evidence_id: item for item in evidence_models}
    if len(evidence_by_id) != len(evidence_models):
        raise ValueError("duplicate evidence IDs in report")
    finding_models = [FindingRecord.model_validate(item) for item in findings]
    finding_ids: set[str] = set()
    dedupe_keys: set[str] = set()
    for finding in finding_models:
        if finding.finding_id in finding_ids:
            raise ValueError(f"duplicate finding ID: {finding.finding_id}")
        finding_ids.add(finding.finding_id)
        key = hashlib.sha256(
            (finding.title.casefold().strip() + "|" + "|".join(sorted(set(finding.affected_urls)))).encode()
        ).hexdigest()
        if key in dedupe_keys:
            raise ValueError(f"duplicate finding: {finding.title}")
        dedupe_keys.add(key)
        missing = sorted(set(finding.evidence_refs) - evidence_by_id.keys())
        if missing:
            raise ValueError(f"finding {finding.finding_id} references missing evidence: {', '.join(missing)}")
        evidence_urls = {evidence_by_id[eid].url for eid in finding.evidence_refs}
        if not set(finding.affected_urls).issubset(evidence_urls):
            raise ValueError(f"finding {finding.finding_id} has affected URLs without linked evidence")
        if finding.status.lower() == "verified":
            if any(evidence_by_id[eid].scope.upper() not in {"PAGE_VERIFIED", "SAMPLE_VERIFIED"} for eid in finding.evidence_refs):
                raise ValueError(f"verified finding {finding.finding_id} cites evidence outside verified scope")
    validated_score = ReportScore.model_validate(score).model_dump() if score is not None else None
    return {
        "valid": True,
        "finding_count": len(finding_models),
        "evidence_count": len(evidence_models),
        "score": validated_score,
    }
