"""
Export Service for Dristik AI
Generates machine-readable CSV exports for:
1. urls.csv: Complete crawl dataset across every analyzed page
2. remediation-tracker.csv: Comprehensive issue tracker with 14-field findings and lifecycle states
"""
from __future__ import annotations

import csv
import io
from typing import Any, List, Optional
from urllib.parse import urlparse

from app.domain.models import ExecutiveReport, Finding, PageReport


def generate_urls_csv(report: ExecutiveReport) -> str:
    """
    Generates a full URL-level crawl dataset in CSV format.
    Includes status code, indexability, canonical state, title/desc pixel widths,
    word count, depth, and schema types.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    headers = [
        "URL",
        "Status Code",
        "Indexability Status",
        "Canonical URL",
        "Canonical Match",
        "Title",
        "Title Character Count",
        "Title Pixel Width (est)",
        "Title Truncated (Desktop)",
        "Meta Description",
        "Meta Description Character Count",
        "Meta Description Pixel Width (est)",
        "Meta Description Truncated",
        "H1 Count",
        "Primary H1",
        "Word Count",
        "Click Depth",
        "TTFB (ms)",
        "Schema Types",
    ]
    writer.writerow(headers)

    # Collect pages from crawl_manifest if present, else page_reports
    pages = []
    if report.crawl_manifest and report.crawl_manifest.pages:
        pages = report.crawl_manifest.pages
    elif report.page_reports:
        pages = report.page_reports
    
    # If serp_appearance snippet previews are available, index them by URL
    serp_map = {}
    if report.serp_appearance and report.serp_appearance.snippets:
        for snip in report.serp_appearance.snippets:
            serp_map[snip.url] = snip

    # If click depth is available, index depth by URL
    depth_map = {}
    if report.click_depth and report.click_depth.pages:
        for cd in report.click_depth.pages:
            depth_map[cd.url] = cd.depth

    for pr in pages:
        p_url = pr.url
        snip = serp_map.get(p_url)

        title = getattr(pr, "title", "") or ""
        title_len = len(title)
        title_px = snip.desktop_title_pixel_width if snip else (title_len * 9.8)
        title_trunc = "YES" if (snip and snip.desktop_title_truncated) or (title_len > 60) else "NO"

        desc = getattr(pr, "meta_description", None)
        if desc is None:
            desc = ""
        desc_len = len(desc)
        desc_px = snip.meta_description_pixel_width if snip else (desc_len * 6.8)
        desc_trunc = "YES" if (snip and snip.meta_description_truncated) or (desc_len > 160) else "NO"

        canon = getattr(pr, "canonical_url", "") or ""
        canon_match = "MATCH" if (canon and canon.strip() == p_url.strip()) else ("MISMATCH" if canon else "MISSING")

        depth = depth_map.get(p_url, getattr(pr, "click_depth", 1))
        status_code = getattr(pr, "status_code", None)
        indexability = getattr(pr, "is_indexable", None)

        h1_raw = getattr(pr, "h1", None)
        if h1_raw is None:
            h1_raw = getattr(pr, "h1_tags", None)
        h1_list = h1_raw if isinstance(h1_raw, list) else None
        primary_h1 = h1_list[0] if h1_list else ""
        word_count = getattr(pr, "word_count", None)
        if word_count is None:
            ux = getattr(pr, "ux", None)
            word_count = getattr(ux, "word_count", None) if ux is not None else None
        ttfb = getattr(pr, "ttfb_ms", None)
        if ttfb is None:
            ux = getattr(pr, "ux", None)
            ttfb = getattr(ux, "ttfb_ms", None) if ux is not None else None
        schema_types = getattr(pr, "schema_types", None)

        writer.writerow([
            p_url,
            status_code,
            ("INDEXABLE" if indexability is True else "NOINDEX" if indexability is False else "UNKNOWN"),
            canon,
            canon_match,
            title,
            title_len,
            int(title_px),
            title_trunc,
            desc,
            desc_len,
            int(desc_px),
            desc_trunc,
            len(h1_list) if h1_list is not None else "",
            primary_h1,
            word_count if word_count is not None else "",
            depth,
            ttfb if ttfb is not None else "",
            "; ".join(schema_types) if isinstance(schema_types, list) else "",
        ])

    return output.getvalue()


def generate_remediation_tracker_csv(report: ExecutiveReport) -> str:
    """
    Generates a remediation tracking spreadsheet with all findings,
    14 professional fields, ownership, priority, and 'Fixed vs Verified' lifecycle states.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    headers = [
        "Finding ID",
        "Category",
        "Subcategory",
        "Severity",
        "Status (Lifecycle)",
        "Priority Score (1-10)",
        "Impact Score (1-10)",
        "Effort Score (1-10)",
        "Title",
        "Description",
        "Expected Condition",
        "Why It Matters (Commercial Consequence)",
        "Recommendation",
        "Validation Criteria (Acceptance Test)",
        "Owner",
        "Affected URLs Count",
        "Affected URLs (Sample)",
        "Dependencies",
        "Evidence Class",
        "Confidence Basis",
    ]
    writer.writerow(headers)

    findings: List[Finding] = report.findings or []

    for f in findings:
        cat_str = f.category.value if hasattr(f.category, "value") else str(f.category)
        sev_str = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        stat_str = f.status.value if hasattr(f.status, "value") else str(f.status)

        aff_urls = f.affected_urls or []
        aff_sample = "; ".join(aff_urls[:5]) + (f" (+{len(aff_urls)-5} more)" if len(aff_urls) > 5 else "")

        writer.writerow([
            f.finding_id,
            cat_str,
            f.subcategory or cat_str,
            sev_str,
            stat_str,
            f.priority,
            f.impact,
            f.effort,
            f.title,
            f.description.replace("\n", " ").strip(),
            f.expected_condition or "",
            (f.why_it_matters or f.business_impact or "").replace("\n", " ").strip(),
            f.recommendation.replace("\n", " ").strip(),
            (f.validation_criteria or "").replace("\n", " ").strip(),
            f.owner or "Engineering",
            len(aff_urls),
            aff_sample,
            "; ".join(f.dependencies or []),
            f.evidence_class.value if hasattr(f.evidence_class, "value") else str(f.evidence_class),
            f.confidence_basis or "",
        ])

    return output.getvalue()


def generate_geo_remediation_csv(report: ExecutiveReport) -> str:
    """
    Generates a specialized GEO Remediation Tracker CSV adhering to the 14-field
    Generative Engine Optimization issue schema.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    headers = [
        "Finding ID",
        "Category / Domain",
        "Subcategory",
        "Severity",
        "Lifecycle Status",
        "Priority (1-10)",
        "Citability Impact (1-10)",
        "Remediation Effort (1-10)",
        "Title",
        "Observed Result",
        "Reference Baseline (Expected Condition)",
        "Commercial Risk / Citability Impact",
        "Prescriptive Recommendation",
        "Validation Criteria (Fixed vs Verified)",
        "Owner",
        "Affected URLs Count",
        "Affected URLs (Sample)",
        "Dependencies",
        "Evidence Class",
        "Confidence & Provenance",
    ]
    writer.writerow(headers)

    findings: List[Finding] = report.findings or []

    for idx, f in enumerate(findings):
        fid = f.finding_id or f"GEO-ISS-{idx+1:03d}"
        if not fid.startswith("GEO-"):
            fid = f"GEO-{fid}"

        cat_str = f.category.value if hasattr(f.category, "value") else str(f.category)
        sev_str = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        stat_str = f.status.value if hasattr(f.status, "value") else str(f.status)

        aff_urls = f.affected_urls or []
        aff_sample = "; ".join(aff_urls[:5]) + (f" (+{len(aff_urls)-5} more)" if len(aff_urls) > 5 else "")

        writer.writerow([
            fid,
            cat_str,
            f.subcategory or cat_str,
            sev_str,
            stat_str,
            f.priority,
            f.impact,
            f.effort,
            f.title,
            f.description.replace("\n", " ").strip(),
            f.expected_condition or "",
            (f.why_it_matters or f.business_impact or "").replace("\n", " ").strip(),
            f.recommendation.replace("\n", " ").strip(),
            (f.validation_criteria or "").replace("\n", " ").strip(),
            f.owner or "AI Search & Growth Team",
            len(aff_urls),
            aff_sample,
            "; ".join(f.dependencies or []),
            f.evidence_class.value if hasattr(f.evidence_class, "value") else str(f.evidence_class),
            f"{int(f.confidence * 100)}% ({f.confidence_basis})" if f.confidence_basis else "",
        ])

    return output.getvalue()


# --- Answer Engine Optimization (AEO) CSV Exports (Delegated to app.aeo.reporting) ---
from app.aeo.reporting.exports import (
    generate_aeo_remediation_csv,
    generate_aeo_question_dataset_csv,
    generate_aeo_live_benchmark_csv,
    generate_aeo_brand_facts_csv,
    generate_aeo_evidence_ledger_csv,
)


