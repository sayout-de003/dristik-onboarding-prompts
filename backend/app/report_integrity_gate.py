"""Final deterministic integrity gate for customer-facing audit reports.

This gate runs after report assembly and the existing validation gate, but before
the run manifest is sealed or the report is persisted. It distinguishes blocking
integrity failures from evidence gaps that must be disclosed to the customer.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


def _value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _normalized_title(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split())


def validate_final_report(report: Any, manifest: Any | None = None) -> dict[str, Any]:
    """Validate report identity, scores, finding uniqueness, evidence links and manifest parity.

    Raises ValueError for structural failures that make the report unsafe to persist.
    Missing evidence is not converted into a positive claim: it prevents certification
    and is surfaced as a warning, while dangling references and invalid scores block.
    """
    blockers: list[str] = []
    warnings: list[str] = []
    findings = list(getattr(report, "findings", None) or [])
    evidence_ledger = getattr(report, "evidence_ledger", None) or {}
    evidence_ids = set(evidence_ledger.keys()) if isinstance(evidence_ledger, dict) else set()

    for item in findings:
        embedded = getattr(item, "evidence", None) or []
        for evidence in embedded:
            evidence_id = getattr(evidence, "evidence_id", None)
            if evidence_id:
                evidence_ids.add(str(evidence_id))

    finding_ids: set[str] = set()
    semantic_keys: Counter[tuple[str, str]] = Counter()
    unsupported_findings: list[str] = []
    dangling_refs: list[str] = []

    for index, finding in enumerate(findings):
        finding_id = str(getattr(finding, "finding_id", "") or "").strip()
        if not finding_id:
            blockers.append(f"finding at index {index} has no finding_id")
        elif finding_id in finding_ids:
            blockers.append(f"duplicate finding_id: {finding_id}")
        finding_ids.add(finding_id)

        title = _normalized_title(getattr(finding, "title", None) or getattr(finding, "finding", None))
        category = str(_value(getattr(finding, "category", "")) or "").casefold()
        if title:
            semantic_keys[(category, title)] += 1

        refs: set[str] = set()
        for field in ("evidence_refs", "evidence_ids", "evidence_references"):
            raw = getattr(finding, field, None) or []
            if isinstance(raw, (list, tuple, set)):
                refs.update(str(ref) for ref in raw if ref)
        for evidence in (getattr(finding, "evidence", None) or []):
            ref = getattr(evidence, "evidence_id", None)
            if ref:
                refs.add(str(ref))

        if not refs:
            unsupported_findings.append(finding_id or f"index:{index}")
        else:
            missing = sorted(refs - evidence_ids)
            if missing:
                dangling_refs.append(f"{finding_id or index}: {', '.join(missing)}")

    duplicate_titles = [
        f"{category}:{title}" for (category, title), count in semantic_keys.items() if count > 1
    ]
    if duplicate_titles:
        blockers.append("duplicate finding root-cause keys: " + "; ".join(duplicate_titles[:20]))
        if len(duplicate_titles) > 20:
            warnings.append(f"{len(duplicate_titles) - 20} additional duplicate finding keys omitted")

    if dangling_refs:
        blockers.append("dangling evidence references: " + "; ".join(dangling_refs[:20]))
        if len(dangling_refs) > 20:
            warnings.append(f"{len(dangling_refs) - 20} additional dangling references omitted")

    scores = getattr(report, "scores", None)
    overall = getattr(scores, "overall_score", None)
    if isinstance(overall, bool) or not isinstance(overall, (int, float)) or not math.isfinite(float(overall)) or not 0 <= float(overall) <= 100:
        blockers.append("overall score is missing, non-finite, or outside 0..100")

    category_scores = getattr(scores, "category_scores", None) or {}
    active_category_weights: list[float] = []
    if isinstance(category_scores, dict):
        for key, item in category_scores.items():
            raw_score = getattr(item, "score", item if isinstance(item, (int, float)) else None)
            status = str(_value(getattr(item, "status", "MEASURED")) or "MEASURED").upper()
            raw_weight = getattr(item, "weight", None)
            raw_weighted = getattr(item, "weighted_score", None)
            weight = None
            if raw_weight is not None:
                if (
                    isinstance(raw_weight, bool)
                    or not isinstance(raw_weight, (int, float))
                    or not math.isfinite(float(raw_weight))
                    or not 0 <= float(raw_weight) <= 1
                ):
                    blockers.append(f"category weight {key} is invalid")
                else:
                    weight = float(raw_weight)
                    if status in {"MEASURED", "PARTIAL"} and weight > 0:
                        active_category_weights.append(weight)

            if raw_score is not None and (
                isinstance(raw_score, bool)
                or not isinstance(raw_score, (int, float))
                or not math.isfinite(float(raw_score))
                or not 0 <= float(raw_score) <= 100
            ):
                blockers.append(f"category score {key} is invalid")
                continue

            if status == "NOT_MEASURED" and raw_score is not None:
                blockers.append(f"category {key} is marked NOT_MEASURED but has a numeric score")
            if raw_score is None and weight is not None and weight > 0:
                blockers.append(f"category {key} has positive weight but no measured score")

            if raw_score is not None and weight is not None and raw_weighted is not None:
                if (
                    isinstance(raw_weighted, bool)
                    or not isinstance(raw_weighted, (int, float))
                    or not math.isfinite(float(raw_weighted))
                    or not 0 <= float(raw_weighted) <= 100
                ):
                    blockers.append(f"category weighted score {key} is invalid")
                elif weight > 0 and abs(float(raw_weighted) - float(raw_score) * weight) > 0.05:
                    blockers.append(f"category weighted score {key} does not reconcile with score × weight")

        if active_category_weights and abs(sum(active_category_weights) - 1.0) > 0.01:
            blockers.append("measured category weights do not sum to 1.0")

    if manifest is not None:
        if getattr(manifest, "analysis_id", None) != getattr(report, "analysis_id", None):
            blockers.append("report and manifest analysis_id do not match")
        if getattr(manifest, "report_id", None) != getattr(report, "report_id", None):
            blockers.append("report and manifest report_id do not match")
        pinned_ids = {str(getattr(pin, "finding_id", "")) for pin in (getattr(manifest, "findings", None) or [])}
        if hasattr(manifest, "findings") and pinned_ids != finding_ids:
            blockers.append("manifest finding pins do not match final report findings")

    if unsupported_findings:
        warnings.append(
            f"{len(unsupported_findings)} finding(s) have no linked evidence and must not be represented as verified."
        )
    if warnings:
        pass

    if blockers:
        raise ValueError("Final report integrity gate failed: " + " | ".join(blockers))

    fully_supported = not unsupported_findings
    return {
        "status": "PASS" if fully_supported else "PASS_WITH_EVIDENCE_GAPS",
        "certified": fully_supported,
        "finding_count": len(findings),
        "evidence_id_count": len(evidence_ids),
        "unsupported_finding_ids": unsupported_findings,
        "warnings": warnings,
        "blockers": [],
        "checked_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "gate_version": "final-report-integrity-v1",
    }
