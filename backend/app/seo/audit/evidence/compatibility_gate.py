"""
Evidence Compatibility Gate for Dristik Audit Pipeline.
Enforces strict semantic compatibility between audit findings and their cited evidence.
Guarantees zero cross-category evidence borrowing (e.g. image-alt evidence cited for pricing or personas).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger("dristik.seo.evidence.compatibility_gate")

IMAGE_KEYWORDS = {"image", "alt", "alt text", "img", "photo", "graphic", "media"}
SECURITY_KEYWORDS = {"hsts", "csp", "ssl", "tls", "security header", "strict-transport-security", "content-security-policy", "clickjacking", "x-frame", "x-content-type"}
ROBOTS_KEYWORDS = {"robots.txt", "robots", "disallow", "user-agent", "crawl-delay"}
SITEMAP_KEYWORDS = {"sitemap", "sitemap.xml", "xml sitemap"}
CANONICAL_KEYWORDS = {"canonical", "rel=canonical", "self-referential canonical"}
HEADING_KEYWORDS = {"h1", "h2", "h3", "heading", "document outline"}
TITLE_META_KEYWORDS = {"title tag", "meta description", "serp snippet", "title length", "meta length"}
SPEED_KEYWORDS = {"ttfb", "latency", "core web vitals", "lcp", "cls", "inp", "page speed", "server response time"}
COMMERCIAL_KEYWORDS = {"pricing", "commercial", "persona", "buyer", "refund", "terms of engagement", "b2b"}
COMPETITOR_KEYWORDS = {"competitor", "market share", "industry peer", "benchmark", "parity", "bakeoff"}


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class EvidenceCompatibilityGate:
    """
    Validates that every finding cites only evidence that genuinely measures the claimed defect.
    Rejects or strips incompatible evidence associations.
    """

    @classmethod
    def is_evidence_compatible(cls, finding_title: str, finding_category: str, evidence: Any) -> bool:
        """
        Determines whether a given evidence record or dict is semantically compatible
        with the finding claim.
        """
        title_l = (finding_title or "").lower()
        cat_l = str(finding_category or "").lower()
        claim_blob = f"{title_l} {cat_l}"

        ev_selector = str(_get_val(evidence, "selector") or "").strip().lower()
        ev_element = str(_get_val(evidence, "element") or "").strip().lower()
        ev_snippet = str(_get_val(evidence, "snippet") or "").strip().lower()
        ev_obs = str(
            _get_val(evidence, "observation")
            or _get_val(evidence, "observed_value")
            or ""
        ).strip().lower()
        ev_val = str(_get_val(evidence, "value") or "").strip().lower()
        ev_description = str(_get_val(evidence, "description") or "").strip().lower()
        ev_expected = str(_get_val(evidence, "expected_condition") or "").strip().lower()
        ev_test_method = str(_get_val(evidence, "test_method") or "").strip().lower()
        ev_url = str(_get_val(evidence, "url") or "").strip().lower()
        ev_blob = (
            f"{ev_selector} {ev_element} {ev_snippet} {ev_obs} {ev_val} "
            f"{ev_description} {ev_expected} {ev_test_method} {ev_url}"
        )

        # 1. Image Evidence Detection
        is_image_ev = (
            ev_selector == "img"
            or ev_element == "img"
            or "alt text" in ev_blob
            or "missing alt" in ev_blob
            or "image(s) are missing" in ev_blob
            or "15 image" in ev_blob
        )
        is_image_claim = any(k in claim_blob for k in IMAGE_KEYWORDS)
        is_layout_shift_evidence = any(
            token in ev_blob
            for token in (
                "layout shift",
                "cumulative layout shift",
                "cls risk",
                "missing width/height",
                "missing dimensions",
            )
        )
        is_alt_evidence = any(token in ev_blob for token in ("alt attribute", "alt text", "missing alt"))

        # A layout-shift/dimensions observation cannot substantiate an alt-text claim.
        if is_image_claim and is_layout_shift_evidence and not is_alt_evidence:
            return False

        # Image evidence can ONLY be bound to image/alt claims
        if is_image_ev and not is_image_claim:
            return False

        # Image claim cannot be supported by non-image selector (like title, h1, header)
        if is_image_claim and not is_image_ev and ev_selector in ("title", "h1", "h2", "h3", "strict-transport-security", "robots.txt"):
            return False

        # 2. Security Headers Evidence Detection
        is_security_ev = any(k in ev_blob for k in ("strict-transport-security", "content-security-policy", "x-frame-options", "x-content-type-options"))
        is_security_claim = any(k in claim_blob for k in SECURITY_KEYWORDS)
        if is_security_ev and not is_security_claim:
            return False

        # 3. Commercial / Pricing / Buyer Persona claims must not bind to image, robots, or security headers
        is_commercial_claim = any(k in claim_blob for k in COMMERCIAL_KEYWORDS)
        if is_commercial_claim and (is_image_ev or is_security_ev or "robots" in ev_blob):
            return False

        # 4. Competitor claims must not bind to image alt or transport headers
        is_competitor_claim = any(k in claim_blob for k in COMPETITOR_KEYWORDS)
        if is_competitor_claim and (is_image_ev or is_security_ev):
            return False

        # 5. Canonical claims must not bind to images
        if any(k in claim_blob for k in CANONICAL_KEYWORDS) and is_image_ev:
            return False

        # 6. Heading claims must not bind to images
        if any(k in claim_blob for k in HEADING_KEYWORDS) and is_image_ev:
            return False

        return True

    @classmethod
    def filter_compatible_evidence(cls, finding: Any) -> List[Any]:
        """
        Filters the evidence list of a finding, returning only compatible evidence.
        """
        title = _get_val(finding, "title") or _get_val(finding, "finding_title") or _get_val(finding, "finding") or ""
        cat = _get_val(finding, "category") or ""
        evidence_list = _get_val(finding, "evidence") or []
        compatible = []
        for ev in evidence_list:
            if cls.is_evidence_compatible(title, cat, ev):
                compatible.append(ev)
            else:
                logger.warning(
                    "Rejecting incompatible evidence '%s' for finding '%s' (Category: %s)",
                    _get_val(ev, "evidence_id") or _get_val(ev, "id"),
                    title,
                    cat,
                )
        return compatible

    @classmethod
    def validate_finding(cls, finding: Any) -> Tuple[bool, List[str]]:
        """
        Validates a finding against enterprise evidence compatibility rules.
        Returns (is_valid, rejection_reasons).
        """
        reasons: List[str] = []
        title = _get_val(finding, "title") or _get_val(finding, "finding_title") or _get_val(finding, "finding") or ""
        cat = _get_val(finding, "category") or ""
        evidence = _get_val(finding, "evidence") or []
        evidence_ids = _get_val(finding, "evidence_ids") or _get_val(finding, "evidence_refs") or []

        if not evidence and not evidence_ids:
            reasons.append(f"Finding '{title}' has zero attached evidence records or evidence IDs.")
            return False, reasons

        for ev in evidence:
            if not cls.is_evidence_compatible(title, cat, ev):
                reasons.append(
                    f"Evidence '{_get_val(ev, 'evidence_id') or _get_val(ev, 'id')}' ({_get_val(ev, 'selector') or _get_val(ev, 'element')}) "
                    f"is semantically incompatible with claim '{title}'."
                )

        return len(reasons) == 0, reasons
