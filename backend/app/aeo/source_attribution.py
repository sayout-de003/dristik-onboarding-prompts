"""Deterministic AEO claim-to-source traceability checks.

This module validates provenance completeness only. A URL and excerpt establish
traceability, not that the cited source semantically proves the claim.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class ClaimSourceAttribution(BaseModel):
    claim_id: str
    claim_text: str
    status: str
    source_url: Optional[str] = None
    evidence_snippet: Optional[str] = None
    reason: Optional[str] = None


class SourceAttributionResult(BaseModel):
    status: str
    total_claims: int = 0
    attributable_claims: int = 0
    missing_source_claims: int = 0
    invalid_source_url_claims: int = 0
    missing_snippet_claims: int = 0
    attribution_coverage_pct: Optional[float] = None
    claims: List[ClaimSourceAttribution] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


def _value(item: Any, *names: str) -> Any:
    for name in names:
        if isinstance(item, dict) and name in item:
            return item[name]
        value = getattr(item, name, None)
        if value is not None:
            return value
    return None


def _valid_http_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)
    except (TypeError, ValueError):
        return False


class SourceAttributionEvaluator:
    """Checks whether each supplied claim has a usable source URL and excerpt."""

    @staticmethod
    def evaluate(claims: Optional[Iterable[Any]]) -> SourceAttributionResult:
        records = list(claims or [])
        if not records:
            return SourceAttributionResult(
                status="NOT_TESTED",
                limitations=["No explicit claim inventory was supplied."],
            )

        results: List[ClaimSourceAttribution] = []
        for index, claim in enumerate(records, start=1):
            claim_text = str(_value(claim, "claim_text", "claim", "text") or "").strip()
            claim_id = str(_value(claim, "claim_id", "id") or f"CLAIM-{index:04d}")
            source_url = _value(claim, "evidence_url", "source_url", "url")
            snippet = _value(claim, "evidence_snippet", "evidence_excerpt", "snippet")
            source_url = source_url.strip() if isinstance(source_url, str) else None
            snippet = snippet.strip() if isinstance(snippet, str) else None

            if not claim_text:
                status, reason = "UNASSESSABLE", "Claim text is missing."
            elif not source_url:
                status, reason = "MISSING_SOURCE", "No source URL is linked to this claim."
            elif not _valid_http_url(source_url):
                status, reason = "INVALID_SOURCE_URL", "Source URL must be an absolute HTTP(S) URL."
            elif not snippet:
                status, reason = "MISSING_SNIPPET", "Source URL exists but no supporting source excerpt is recorded."
            else:
                status, reason = "ATTRIBUTED", None

            results.append(ClaimSourceAttribution(
                claim_id=claim_id,
                claim_text=claim_text,
                status=status,
                source_url=source_url,
                evidence_snippet=snippet,
                reason=reason,
            ))

        assessable = [item for item in results if item.status != "UNASSESSABLE"]
        attributable = sum(item.status == "ATTRIBUTED" for item in assessable)
        missing = sum(item.status == "MISSING_SOURCE" for item in assessable)
        invalid = sum(item.status == "INVALID_SOURCE_URL" for item in assessable)
        no_snippet = sum(item.status == "MISSING_SNIPPET" for item in assessable)
        coverage = round(attributable / len(assessable) * 100.0, 1) if assessable else None
        status = "MEASURED" if assessable else "NOT_TESTED"
        return SourceAttributionResult(
            status=status,
            total_claims=len(results),
            attributable_claims=attributable,
            missing_source_claims=missing,
            invalid_source_url_claims=invalid,
            missing_snippet_claims=no_snippet,
            attribution_coverage_pct=coverage,
            claims=results,
            limitations=[
                "Attribution coverage measures traceability completeness, not semantic entailment or factual correctness.",
                "Source credibility, freshness, claim-to-passage entailment, and contradiction resolution require separate checks.",
            ],
        )


__all__ = ["ClaimSourceAttribution", "SourceAttributionResult", "SourceAttributionEvaluator"]
