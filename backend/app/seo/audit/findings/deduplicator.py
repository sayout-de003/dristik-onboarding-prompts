"""Deterministic de-duplication for legacy SEO finding dictionaries.

This adapter intentionally avoids semantic/LLM matching. It canonicalizes formatting
noise, merges evidence/URL coverage, and keeps the strongest observed severity.
Higher-level root-cause clustering belongs to the typed remediation deduplicator.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


_SEVERITY_RANK = {
    "CRITICAL": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "MODERATE": 3,
    "LOW": 2,
    "INFO": 1,
    "INFORMATIONAL": 1,
}


def _canonical_text(value: Any) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _severity(value: Any) -> str:
    return str(getattr(value, "value", value) or "INFO").upper()


class FindingDeduplicator:
    """Collapse exact root-cause duplicates without losing affected URLs/evidence."""

    def deduplicate(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str], dict[str, Any]] = {}
        ordered_keys: list[tuple[str, str]] = []

        for source in findings:
            if not isinstance(source, dict):
                raise TypeError("each finding must be a dictionary")
            finding = deepcopy(source)
            title_key = _canonical_text(finding.get("title"))
            category_key = _canonical_text(finding.get("category"))
            # Keep title-less items distinct; malformed findings should not all
            # collapse into one blank-key record.
            key = (category_key, title_key) if title_key else (
                category_key, f"__untitled__{len(ordered_keys)}"
            )

            if key not in groups:
                groups[key] = finding
                ordered_keys.append(key)
                groups[key]["duplicate_count"] = int(groups[key].get("duplicate_count") or 0)
                continue

            canonical = groups[key]
            current_rank = _SEVERITY_RANK.get(_severity(canonical.get("severity")), 0)
            incoming_rank = _SEVERITY_RANK.get(_severity(finding.get("severity")), 0)
            if incoming_rank > current_rank:
                canonical["severity"] = finding.get("severity")

            # Merge lists without losing order. Support common evidence fields.
            for field in ("affected_urls", "urls", "evidence", "evidence_refs", "evidence_ids", "observations"):
                left = canonical.get(field)
                right = finding.get(field)
                if isinstance(left, list) or isinstance(right, list):
                    merged: list[Any] = []
                    seen: set[str] = set()
                    for item in (left if isinstance(left, list) else []) + (right if isinstance(right, list) else []):
                        identity = repr(item)
                        if identity not in seen:
                            seen.add(identity)
                            merged.append(item)
                    canonical[field] = merged

            canonical["duplicate_count"] = int(canonical.get("duplicate_count") or 0) + 1
            # Preserve supplementary non-empty fields absent from the first item.
            for field, value in finding.items():
                if field not in canonical or canonical[field] in (None, "", [], {}):
                    if value not in (None, "", [], {}):
                        canonical[field] = value

        return [groups[key] for key in ordered_keys]
