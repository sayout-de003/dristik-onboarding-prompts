"""Canonical finding registry helpers for report assembly.

Kept dependency-light so deduplication behavior can be regression-tested without
importing the full agent orchestration/report package.
"""
from __future__ import annotations

import re
from typing import Any


def finding_value(finding: Any, key: str, default: Any = None) -> Any:
    """Read a field from a Pydantic/object finding or a dictionary."""
    if isinstance(finding, dict):
        return finding.get(key, default)
    return getattr(finding, key, default)


def canonicalize_report_findings(report: Any) -> list[Any]:
    """Return one canonical record per repeated finding identity.

    Stable finding IDs take precedence. Without an ID, only matching normalized
    titles on the same affected URL are collapsed; similar issues on different
    pages remain independent findings.
    """
    raw = list(getattr(report, "findings", []) or [])
    canonical: list[Any] = []
    seen: set[tuple[str, tuple[str, ...], str, str, tuple[str, ...]]] = set()
    seen_ids: set[str] = set()
    for finding in raw:
        finding_id = str(finding_value(finding, "finding_id", finding_value(finding, "id", "")) or "").strip()
        if finding_id and finding_id in seen_ids:
            continue
        title = re.sub(
            r"\s+",
            " ",
            str(finding_value(finding, "title", finding_value(finding, "name", "")) or ""),
        ).strip().casefold()
        urls = finding_value(finding, "affected_urls", None) or finding_value(finding, "urls", None) or []
        if isinstance(urls, str):
            urls = [urls]
        if not urls:
            url = finding_value(finding, "url", None) or finding_value(finding, "affected_url", None)
            urls = [url] if url else []
        normalized_urls = tuple(sorted({str(url).rstrip("/").casefold() for url in urls if url}))
        root_cause = re.sub(
            r"\s+",
            " ",
            str(finding_value(finding, "root_cause_category", finding_value(finding, "root_cause", "")) or ""),
        ).strip().casefold()
        remediation = re.sub(
            r"\s+",
            " ",
            str(finding_value(finding, "how_to_fix", finding_value(finding, "remediation", "")) or ""),
        ).strip().casefold()
        evidence_refs = finding_value(finding, "evidence_refs", None) or finding_value(finding, "evidence_ids", None) or []
        if isinstance(evidence_refs, str):
            evidence_refs = [evidence_refs]
        evidence_key = tuple(sorted(str(ref) for ref in evidence_refs if ref))
        # Without a stable ID, matching wording and URL alone is not enough:
        # require a shared root cause, remediation, or evidence reference.
        has_corroborating_identity = bool(root_cause or remediation or evidence_key)
        identity = (
            title,
            normalized_urls,
            root_cause,
            remediation,
            evidence_key,
        ) if title and normalized_urls and has_corroborating_identity else (
            finding_id or str(id(finding)),
            normalized_urls,
            "",
            "",
            (),
        )
        if identity in seen:
            continue
        seen.add(identity)
        if finding_id:
            seen_ids.add(finding_id)
        canonical.append(finding)
    return canonical
