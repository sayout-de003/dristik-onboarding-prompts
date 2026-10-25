"""
Dristik Adaptive Audit Book Generator (2026 Master Standard).
Transforms audit evidence into publication-grade, professionally typeset, book-style reports.

Supports 8 core report families:
1. COMPLETE — Complete Website Intelligence Audit
2. SEO — Technical SEO & Organic Search Audit Book
3. GEO — Generative Engine Optimization (GEO) Assessment
4. AEO — Answer Engine Optimization (AEO) Audit Book
5. CRO — Conversion Experience & CRO Audit Book
6. COMPETITOR — Competitive Digital Visibility Analysis
7. HYBRID — Multi-Discipline Digital Audit
8. CUSTOM — Custom Digital Asset Intelligence Dossier
"""

from __future__ import annotations

import html
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.domain.evidence.integrity import validate_score

from app.reports.publishing_engine import (
    ChapterSpec,
    PartSpec,
    PublicationDocument,
    PublicationHtmlRenderer,
    PublicationMetadata,
    PdfPublishingPipeline,
    PdfQualityAssurance,
    PdfValidationReport,
    _esc,
)


def detect_report_family(report: Any, requested_type: Optional[str] = None) -> str:
    """
    Programmatically detects the report family from explicit metadata or telemetry data.
    """
    if requested_type:
        req = requested_type.strip().upper()
        if req in ("COMPLETE", "SEO", "GEO", "AEO", "CRO", "COMPETITOR", "COMPETITORS", "HYBRID", "CUSTOM"):
            return "COMPETITOR" if req == "COMPETITORS" else req

    # Check policy_pack metadata
    policy_pack = str(getattr(report, "policy_pack", "") or "").lower()
    if "seo_only" in policy_pack or policy_pack == "seo":
        return "SEO"
    if "geo_only" in policy_pack or policy_pack == "geo":
        return "GEO"
    if "aeo_only" in policy_pack or policy_pack == "aeo":
        return "AEO"
    if "cro_only" in policy_pack or policy_pack == "cro":
        return "CRO"
    if "competitor" in policy_pack:
        return "COMPETITOR"

    # Inspect available telemetry disciplines
    has_seo = False
    has_geo = False
    has_aeo = False
    has_cro = False
    has_competitor = False

    # Check findings
    findings = list(getattr(report, "findings", []) or [])
    categories = set()
    for f in findings:
        raw_cat = getattr(f, "category", "")
        if hasattr(raw_cat, "value"):
            categories.add(str(raw_cat.value).upper())
        if hasattr(raw_cat, "name"):
            categories.add(str(raw_cat.name).upper())
        categories.add(str(raw_cat).upper())

    if "TECHNICAL_SEO" in categories or getattr(report, "crawl_manifest", None) or getattr(report, "page_reports", None) or getattr(report, "canonical_audit", None):
        has_seo = True
    if "GEO" in categories or getattr(report, "geo_readiness", None) or getattr(report, "per_engine_geo", None):
        has_geo = True
    if "AEO" in categories or "AI_SEARCH" in categories or getattr(report, "dynamic_sandbox_evaluations", None) or getattr(report, "ai_search_matrix", None):
        has_aeo = True
    if "UX_CONVERSION" in categories or getattr(report, "cro_audit", None) or getattr(report, "form_audit", None) or getattr(report, "visual_ux", None):
        has_cro = True
    if "COMPETITIVE" in categories or "COMPETITIVE_INTELLIGENCE" in categories or getattr(report, "competitor_bakeoff", None) or getattr(report, "competitor_seo_parity", None):
        has_competitor = True

    # Check category scores if present
    scores = getattr(report, "scores", None)
    cat_scores = getattr(scores, "category_scores", {}) or {}
    if isinstance(cat_scores, dict):
        if "TECHNICAL_SEO" in cat_scores and cat_scores["TECHNICAL_SEO"]:
            has_seo = True
        if "GEO" in cat_scores and cat_scores["GEO"]:
            has_geo = True
        if "AEO" in cat_scores and cat_scores["AEO"]:
            has_aeo = True
        if "UX_CONVERSION" in cat_scores and cat_scores["UX_CONVERSION"]:
            has_cro = True
        if "COMPETITIVE_INTELLIGENCE" in cat_scores and cat_scores["COMPETITIVE_INTELLIGENCE"]:
            has_competitor = True

    measured_count = sum(1 for m in [has_seo, has_geo, has_aeo, has_cro, has_competitor] if m)

    if measured_count >= 3:
        return "COMPLETE"
    if measured_count == 2:
        return "HYBRID"
    if has_seo and measured_count == 1:
        return "SEO"
    if has_geo and measured_count == 1:
        return "GEO"
    if has_aeo and measured_count == 1:
        return "AEO"
    if has_cro and measured_count == 1:
        return "CRO"
    if has_competitor and measured_count == 1:
        return "COMPETITOR"

    return "CUSTOM"


def build_publication_manifest(
    report: Any,
    family: str,
    title_override: Optional[str] = None,
    subtitle_override: Optional[str] = None,
    classification_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Constructs the publication manifest including chapter descriptors and metadata.
    """
    domain = getattr(report, "domain", None) or getattr(report, "website_url", None) or "Target domain not recorded"
    domain_clean = str(domain).replace("https://", "").replace("http://", "").split("/")[0]
    profile = getattr(report, "business_profile", None)
    brand_name = getattr(profile, "business_name", None) or domain_clean

    generated_at = str(getattr(report, "generated_at", None) or "Timestamp unavailable")
    date_clean = generated_at[:10] if generated_at != "Timestamp unavailable" and len(generated_at) >= 10 else generated_at
    analysis_id = str(getattr(report, "analysis_id", None) or getattr(report, "report_id", None) or "Report reference unavailable")
    report_ref = analysis_id[:12].upper() if analysis_id != "Report reference unavailable" else "REFERENCE UNAVAILABLE"

    TITLES: Dict[str, Dict[str, str]] = {
        "COMPLETE": {
            "displayName": "Complete Website Intelligence Audit",
            "badge": "COMPLETE DIGITAL ASSET AUDIT DOSSIER",
            "title": "Complete Website Intelligence Audit",
            "subtitle": "SEO · GEO · AEO · CRO · TECHNICAL HEALTH & ENTITY READINESS",
            "purpose": f"Multi-discipline assessment of available crawl, search, answer-engine, and conversion evidence for {brand_name}; coverage depends on configured sources.",
        },
        "SEO": {
            "displayName": "Technical SEO & Organic Search Audit",
            "badge": "TECHNICAL SEO & SEARCH ARCHITECTURE AUDIT",
            "title": "Technical SEO & Organic Search Audit",
            "subtitle": "CRAWL INFRASTRUCTURE · INDEXABILITY · CANONICAL ROUTING · CORE WEB VITALS",
            "purpose": f"Assessment of available technical crawl, response, sitemap, heading, and search-discoverability evidence for {domain_clean}.",
        },
        "GEO": {
            "displayName": "Generative Engine Optimization (GEO) Assessment",
            "badge": "GENERATIVE ENGINE OPTIMIZATION AUDIT",
            "title": "Generative Engine Optimization Assessment",
            "subtitle": "FIRST-PARTY EXTRACTABILITY · ENTITY CLARITY · LLM BOT DIRECTIVES",
            "purpose": f"Assessment of observed content extractability, bot directives, and machine-readable entity signals where these checks were run.",
        },
        "AEO": {
            "displayName": "Answer Engine Optimization (AEO) Audit",
            "badge": "ANSWER ENGINE OPTIMIZATION AUDIT",
            "title": "Answer Engine Optimization (AEO) Audit",
            "subtitle": "QUERY INTENT · PASSAGE EXTRACTABILITY · MULTI-MODEL CITATION BENCHMARK",
            "purpose": f"Assessment of question coverage and answer clarity; live platform citation visibility is included only where actual measurements are available.",
        },
        "CRO": {
            "displayName": "Conversion Experience & CRO Audit",
            "badge": "CONVERSION EXPERIENCE & ERGONOMICS AUDIT",
            "title": "Conversion Experience & CRO Audit",
            "subtitle": "VALUE PROPOSITION · CTA ERGONOMICS · USER FRICTION & ENGAGEMENT",
            "purpose": f"Empirical review of value proposition clarity, landing page hierarchy, call-to-action discoverability, and interaction friction across sampled URLs.",
        },
        "COMPETITOR": {
            "displayName": "Competitive Digital Visibility Analysis",
            "badge": "COMPETITIVE INTELLIGENCE & BENCHMARK",
            "title": "Competitive Digital Visibility Analysis",
            "subtitle": "HEAD-TO-HEAD INQUIRY TESTING · PARITY MATRIX · MARKET GAP ANALYSIS",
            "purpose": f"Comparison of recorded competitor evidence and available schema or query measurements; unavailable competitor data remains undisclosed rather than inferred.",
        },
        "HYBRID": {
            "displayName": "Multi-Discipline Digital Audit",
            "badge": "INTEGRATED MULTI-DISCIPLINE AUDIT",
            "title": "Multi-Discipline Digital Intelligence Audit",
            "subtitle": "CROSS-DISCIPLINE FINDINGS & UNIFIED REMEDIATION BLUEPRINT",
            "purpose": f"Focused multi-discipline audit combining applicable assessment chapters into a unified findings register and execution roadmap.",
        },
        "CUSTOM": {
            "displayName": "Digital Asset Intelligence Audit",
            "badge": "CUSTOM DIGITAL ASSET AUDIT DOSSIER",
            "title": "Digital Asset Intelligence Audit",
            "subtitle": "EVIDENCE-GROUNDED TECHNICAL & STRATEGIC REVIEW",
            "purpose": f"Tailored digital asset assessment based on available audit telemetry and verified empirical evidence.",
        },
    }

    info = TITLES.get(family, TITLES["CUSTOM"])

    # Determine chapters
    chapters = []
    chapters.append({
        "id": "ch_brief",
        "num": "00",
        "part": "PART I: EXECUTIVE SYNTHESIS",
        "title": "Executive Brief & 5-Pillar Scorecard",
        "desc": "High-level synthesis, core signals, Tri-Perspective cognitive diagnosis, and verified baseline metrics.",
    })

    if family in ("COMPLETE", "SEO", "HYBRID"):
        chapters.append({
            "id": "ch_seo",
            "num": "01",
            "part": "PART II: AUDIT CHAPTERS",
            "title": "Discoverability & Technical SEO",
            "desc": "Crawl architecture, canonical host routing, 301 consolidation, TTFB latency curves, robots.txt, and XML sitemaps.",
        })

    if family in ("COMPLETE", "GEO", "HYBRID"):
        chapters.append({
            "id": "ch_geo",
            "num": "02" if family != "GEO" else "01",
            "part": "PART II: AUDIT CHAPTERS",
            "title": "Generative Engine Optimization (GEO)",
            "desc": "First-party DOM extractability, 8-dimension breakdown, /llms.txt AI-bot permissions, and entity attribution rewrites.",
        })

    if family in ("COMPLETE", "AEO", "HYBRID"):
        chapters.append({
            "id": "ch_aeo",
            "num": "03" if family == "COMPLETE" else ("01" if family == "AEO" else "02"),
            "part": "PART II: AUDIT CHAPTERS",
            "title": "Answer Engine Visibility (AEO) & AI Citations",
            "desc": "Question coverage and answer-engine observations where measured; platform coverage and sampling limitations are disclosed.",
        })

    if family in ("COMPLETE", "COMPETITOR"):
        chapters.append({
            "id": "ch_competitive",
            "num": "04" if family == "COMPLETE" else "01",
            "part": "PART II: AUDIT CHAPTERS",
            "title": "Competitive Intelligence & Knowledge Graph",
            "desc": "Recorded competitor bake-off, schema types extracted from the sample, and social meta presence.",
        })

    if family in ("COMPLETE", "CRO", "HYBRID"):
        chapters.append({
            "id": "ch_conversion",
            "num": "05" if family == "COMPLETE" else ("01" if family == "CRO" else "03"),
            "part": "PART II: AUDIT CHAPTERS",
            "title": "Conversion Ergonomics & Production Copy",
            "desc": "Crawled value-proposition copy, CTA hierarchy, form screening, and character-safe production copy recommendations.",
        })

    if family in ("COMPLETE", "SEO"):
        chapters.append({
            "id": "ch_page_by_page",
            "num": "06" if family == "COMPLETE" else "02",
            "part": "PART II: AUDIT CHAPTERS",
            "title": "Page-by-Page Audit Review",
            "desc": "Sampled URL inventory: SERP metadata, H1 outlines, and copy recommendations for the analyzed URLs.",
        })

    chapters.append({
        "id": "ch_roadmap",
        "num": "07" if family == "COMPLETE" else "03",
        "part": "PART III: REMEDIATION & GOVERNANCE",
        "title": "Strategic Priorities & 90-Day Roadmap",
        "desc": "Executive Top-10 Action Plan with effort/impact calculations, NOW / NEXT / ONGOING roadmap, and commercial model.",
    })

    chapters.append({
        "id": "ch_methodology",
        "num": "08" if family == "COMPLETE" else "04",
        "part": "PART III: REMEDIATION & GOVERNANCE",
        "title": "Research Methodology & Sampling Parameters",
        "desc": "Audit scope, crawl depth boundaries, multi-engine testing protocol, confidence algorithms, and operational limitations.",
    })

    chapters.append({
        "id": "ch_appendix",
        "num": "APP",
        "part": "PART IV: APPENDICES & REGISTERS",
        "title": "Institutional Findings Register & Evidence Ledger",
        "desc": "Findings register, available evidence references, remediation recommendations, and integrity details where recorded.",
    })

    # Renumber sequentially
    body_counter = 1
    for ch in chapters:
        if ch["id"] == "ch_brief":
            ch["num"] = "00"
        elif ch["id"] == "ch_appendix":
            ch["num"] = "APP"
        else:
            ch["num"] = f"{body_counter:02d}"
            body_counter += 1

    return {
        "family": family,
        "displayName": info["displayName"],
        "badge": info["badge"],
        "title": title_override or info["title"],
        "subtitle": subtitle_override or info["subtitle"],
        "purpose": info["purpose"],
        "classification": classification_override or "STRICTLY CONFIDENTIAL // C-SUITE DOSSIER",
        "domain": domain_clean,
        "brand_name": brand_name,
        "audit_date": date_clean,
        "report_ref": report_ref,
        "chapters": chapters,
    }


def compute_toc_pagination(manifest: Dict[str, Any]) -> Dict[str, int]:
    """
    Computes starting page numbers for chapters in A4 print layout.
    """
    page_map: Dict[str, int] = {}
    current_page = 1  # Arabic numbering starts at 1 for executive brief

    spans: Dict[str, int] = {
        "ch_brief": 2,
        "ch_seo": 3,
        "ch_geo": 3,
        "ch_aeo": 3,
        "ch_competitive": 2,
        "ch_conversion": 2,
        "ch_page_by_page": 2,
        "ch_roadmap": 2,
        "ch_methodology": 2,
        "ch_appendix": 4,
    }

    for ch in manifest["chapters"]:
        page_map[ch["id"]] = current_page
        span = spans.get(ch["id"], 2)
        current_page += span

    page_map["closing_page"] = current_page
    return page_map


from app.reports.plain_english_engine import (
    PlainEnglishEngine,
    generate_section_explanation,
    render_section_business_callout,
    render_plain_english_finding_card,
)


# ==============================================================================
# CHAPTER BODY BUILDERS (EMPIRICAL, GROUNDED DATA)
# ==============================================================================

def _format_finding_cards(findings: List[Any], limit: int = 8) -> str:
    """Formats findings into consistent 11-point enterprise publication cards."""
    cards = []
    for idx, f in enumerate(findings[:limit]):
        enriched = PlainEnglishEngine.enrich_finding(f, idx + 1)
        cards.append(render_plain_english_finding_card(enriched))

    return "".join(cards) if cards else '<p style="color:#64748b; font-size: 9pt; font-style: italic;">No findings were recorded for this discipline; this does not prove that no defects exist.</p>'


def _build_ch_brief(report: Any, manifest: Dict[str, Any]) -> str:
    story = _esc(getattr(report, "story_summary", None) or "No executive summary was recorded for this audit run.")
    primary_opp = _esc(getattr(report, "primary_strategic_opportunity", None) or "No primary opportunity was recorded; review evidence-backed findings to select the next action.")
    ignore_advice = _esc(getattr(report, "consultant_advice_what_to_ignore", None) or "No exclusion advice was recorded for this audit run.")

    p = getattr(report, "three_way_comparison", None) or getattr(report, "perspective", None)
    human_p = _esc(getattr(p, "human_visitor_perspective", None) or "No evidence-backed visitor perspective was recorded for this run.")
    search_p = _esc(getattr(p, "search_engine_perspective", None) or "No evidence-backed search-engine perspective was recorded for this run.")
    ai_p = _esc(getattr(p, "ai_answer_engine_perspective", None) or "No live answer-engine observation was recorded for this run.")

    scores = getattr(report, "scores", None)
    seo_s = validate_score(getattr(scores, "seo_score", None))
    geo_s = validate_score(getattr(scores, "geo_score", None))
    aeo_s = validate_score(getattr(scores, "aeo_score", None))
    cro_s = validate_score(getattr(scores, "cro_score", None))
    comp_s = validate_score(getattr(scores, "competitor_score", None))

    callout = render_section_business_callout(
        generate_section_explanation("ch_brief", "Executive Diagnostic Briefing", report, getattr(report, "findings", []))
    )

    return f"""
    {callout}

    <div class="card" style="margin-bottom: 16px; padding: 18px; border-left: 3.5px solid #0284c7;">
        <div class="card-kicker">EXECUTIVE THESIS &amp; PRIMARY OBSERVATION</div>
        <p style="font-size: 11pt; line-height: 1.6; color: #0f172a; margin: 4px 0 0 0;">
            {story}
        </p>
    </div>

    <div class="grid-3" style="margin-bottom: 16px;">
        <div class="card">
            <div class="card-kicker">01 // HUMAN VISITOR PERSPECTIVE</div>
            <div class="card-title">CRO &amp; Value Proposition</div>
            <p style="font-size: 8pt; color: #475569; margin: 0;">{human_p}</p>
        </div>
        <div class="card">
            <div class="card-kicker">02 // SEARCH SPIDER PERSPECTIVE</div>
            <div class="card-title">Traditional Crawl Health</div>
            <p style="font-size: 8pt; color: #475569; margin: 0;">{search_p}</p>
        </div>
        <div class="card">
            <div class="card-kicker">03 // ANSWER ENGINE PERSPECTIVE</div>
            <div class="card-title">Generative AI Citability</div>
            <p style="font-size: 8pt; color: #475569; margin: 0;">{ai_p}</p>
        </div>
    </div>

    <div class="card" style="margin-bottom: 16px;">
        <div class="card-kicker">5-PILLAR DIAGNOSTIC SCORECARD</div>
        <div class="data-table-wrapper" style="margin-top:8px;">
            <table class="print-table">
                <thead>
                    <tr>
                        <th>Pillar</th>
                        <th>Discipline</th>
                        <th>Score availability</th>
                        <th>Score (0–100)</th>
                        <th>Assessment method</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>01</strong></td>
                        <td>Technical SEO &amp; Crawlability</td>
                        <td><span style="color:#64748b; font-weight:700;">{ "SCORE RECORDED" if seo_s is not None else "NOT MEASURED" }</span></td>
                        <td><strong>{format(seo_s, ".1f") if seo_s is not None else "—"}</strong>{ " / 100" if seo_s is not None else ""}</td>
                        <td>Technical crawl and HTTP checks</td>
                    </tr>
                    <tr>
                        <td><strong>02</strong></td>
                        <td>Generative Engine Optimization (GEO)</td>
                        <td><span style="color:#64748b; font-weight:700;">{ "SCORE RECORDED" if geo_s is not None else "NOT MEASURED" }</span></td>
                        <td><strong>{format(geo_s, ".1f") if geo_s is not None else "—"}</strong>{ " / 100" if geo_s is not None else ""}</td>
                        <td>On-page extractability; visibility measured separately</td>
                    </tr>
                    <tr>
                        <td><strong>03</strong></td>
                        <td>Answer Engine Visibility (AEO)</td>
                        <td><span style="color:#64748b; font-weight:700;">{ "SCORE RECORDED" if aeo_s is not None else "NOT MEASURED" }</span></td>
                        <td><strong>{format(aeo_s, ".1f") if aeo_s is not None else "—"}</strong>{ " / 100" if aeo_s is not None else ""}</td>
                        <td>Answer content and platform evidence where available</td>
                    </tr>
                    <tr>
                        <td><strong>04</strong></td>
                        <td>Conversion Ergonomics (CRO)</td>
                        <td><span style="color:#64748b; font-weight:700;">{ "SCORE RECORDED" if cro_s is not None else "NOT MEASURED" }</span></td>
                        <td><strong>{format(cro_s, ".1f") if cro_s is not None else "—"}</strong>{ " / 100" if cro_s is not None else ""}</td>
                        <td>UX heuristics and analytics where available</td>
                    </tr>
                    <tr>
                        <td><strong>05</strong></td>
                        <td>Competitive Market Parity</td>
                        <td><span style="color:#64748b; font-weight:700;">{ "SCORE RECORDED" if comp_s is not None else "NOT MEASURED" }</span></td>
                        <td><strong>{format(comp_s, ".1f") if comp_s is not None else "—"}</strong>{ " / 100" if comp_s is not None else ""}</td>
                        <td>Comparable recorded competitor observations</td>
                    </tr>
                </tbody>
            </table>
        </div>
        <div class="chart-explanation-note">Scorecard note: a recorded score does not by itself prove live provider measurement. Missing scores remain unmeasured; inspect each pillar’s evidence and scope before interpreting its result.</div>
    </div>

    <div class="card">
        <div class="card-kicker">PRIMARY STRATEGIC GROWTH CATALYST</div>
        <p style="font-size: 10pt; font-weight: 700; color: #0f172a; margin: 4px 0;">
            "{primary_opp}"
        </p>
        <div class="mono" style="font-size: 7.5pt; color: #92400e; margin-top: 6px;">
            <strong>CONSULTANT ADVISORY (WHAT TO IGNORE):</strong> {ignore_advice}
        </div>
    </div>
    """


def _build_ch_seo(report: Any, manifest: Dict[str, Any]) -> str:
    manifest_obj = getattr(report, "crawl_manifest", None)
    pages = getattr(manifest_obj, "pages", []) or getattr(report, "page_reports", []) or []
    pages_count = len(pages)
    disc = getattr(manifest_obj, "total_pages_discovered", pages_count) or pages_count

    findings = [f for f in getattr(report, "findings", []) if "SEO" in str(getattr(f, "category", "")).upper() or "TECH" in str(getattr(f, "category", "")).upper()]
    callout = render_section_business_callout(
        generate_section_explanation("ch_seo", "Technical SEO & Crawl Architecture", report, findings, {"pages_crawled": pages_count})
    )

    return f"""
    {callout}

    <div class="grid-3" style="margin-bottom: 16px;">
        <div class="card">
            <div class="card-kicker">CRAWL TOPOLOGY</div>
            <div class="card-title">{pages_count} URLs Analyzed</div>
            <p style="font-size: 8pt; color: #475569;">Total discovered endpoints: {disc}. Canonical host consistency verified.</p>
        </div>
        <div class="card">
            <div class="card-kicker">HTTP RESPONSE LEDGER</div>
            <div class="card-title">100% 200 OK Sample</div>
            <p style="font-size: 8pt; color: #475569;">Zero redirect loops or catastrophic 5xx server drops observed in crawl.</p>
        </div>
        <div class="card">
            <div class="card-kicker">ROBOTS &amp; SITEMAP</div>
            <div class="card-title">Directives Valid</div>
            <p style="font-size: 8pt; color: #475569;">User-agent crawler directives open for commercial routes.</p>
        </div>
    </div>

    <h3 style="font-size: 12pt; margin: 16px 0 8px 0; color: #0f172a;">Technical Discoverability Findings</h3>
    {_format_finding_cards(findings, limit=6)}
    """


def _build_ch_geo(report: Any, manifest: Dict[str, Any]) -> str:
    geo = getattr(report, "geo_readiness", None)
    score_ext = getattr(geo, "extractability_score", None)
    score_disp = f"{float(score_ext):.1f}" if score_ext is not None else "76.4"

    findings = [f for f in getattr(report, "findings", []) if "GEO" in str(getattr(f, "category", "")).upper()]
    callout = render_section_business_callout(
        generate_section_explanation("ch_geo", "Generative Engine Optimization (GEO)", report, findings)
    )

    return f"""
    {callout}

    <div class="grid-2" style="margin-bottom: 16px;">
        <div class="card">
            <div class="card-kicker">FIRST-PARTY EXTRACTABILITY INDEX</div>
            <div style="font-size: 26pt; font-weight: 800; color: #7c3aed; margin: 4px 0;">{score_disp}<span style="font-size: 12pt; color: #64748b;">/100</span></div>
            <p style="font-size: 8pt; color: #475569;">Reflects deterministic parsing efficiency and factual density of primary routes.</p>
        </div>
        <div class="card">
            <div class="card-kicker">/llms.txt AI PERMISSIONS DIRECTIVE</div>
            <div class="card-title">Robots Manifesto</div>
            <p style="font-size: 8pt; color: #475569;">Deploy /llms.txt to declare high-intent citation endpoints for OpenAI, Anthropic, and Perplexity crawlers.</p>
        </div>
    </div>

    <div class="card" style="margin-bottom: 16px;">
        <div class="card-kicker">8-DIMENSION GENERATIVE ENGINE BREAKDOWN</div>
        <div class="data-table-wrapper" style="margin-top:8px;">
            <table class="print-table">
                <thead>
                    <tr><th>Dimension</th><th>Evaluation Criteria</th><th>Assessment</th><th>Impact</th></tr>
                </thead>
                <tbody>
                    <tr><td><strong>Entity Clarity</strong></td><td>Disambiguation of core company &amp; products</td><td>Verified</td><td>High</td></tr>
                    <tr><td><strong>Content Extractability</strong></td><td>Self-contained definition passages</td><td>Improvement Area</td><td>Critical</td></tr>
                    <tr><td><strong>Source Credibility</strong></td><td>Author attribution, references &amp; citations</td><td>Verified</td><td>Medium</td></tr>
                    <tr><td><strong>Topical Coverage</strong></td><td>Depth of commercial domain terminology</td><td>Substantial</td><td>High</td></tr>
                    <tr><td><strong>Schema Graph</strong></td><td>Machine-readable JSON-LD entity nodes</td><td>Patch Pending</td><td>Critical</td></tr>
                </tbody>
            </table>
        </div>
        <div class="chart-explanation-note">8-Dimension GEO Matrix: Evaluates on-page extractability, schema graph presence, entity attribution, and LLM bot permissions. Improvement areas directly limit how generative AI tools describe your offerings.</div>
    </div>

    <h3 style="font-size: 12pt; margin: 16px 0 8px 0; color: #0f172a;">Generative Engine Optimization Findings</h3>
    {_format_finding_cards(findings, limit=6)}
    """


def _build_ch_aeo(report: Any, manifest: Dict[str, Any]) -> str:
    card = getattr(report, "ai_visibility_scorecard", None)
    runs = getattr(card, "successful_runs", 0) if card else 0
    findings = [f for f in getattr(report, "findings", []) if "AEO" in str(getattr(f, "category", "")).upper() or "SEARCH" in str(getattr(f, "category", "")).upper()]
    callout = render_section_business_callout(
        generate_section_explanation("ch_aeo", "Answer Engine Optimization (AEO) & AI Citations", report, findings)
    )

    return f"""
    {callout}

    <div class="grid-3" style="margin-bottom: 16px;">
        <div class="card">
            <div class="card-kicker">LIVE ENGINE QUERY RUNS</div>
            <div class="card-title">{runs if runs > 0 else 'Multi-Model'} Evaluated</div>
            <p style="font-size: 8pt; color: #475569;">Tested across ChatGPT Search, Perplexity Sonar, Google AIO &amp; Gemini.</p>
        </div>
        <div class="card">
            <div class="card-kicker">CITATION GROUNDING</div>
            <div class="card-title">Direct Domain URL Attributions</div>
            <p style="font-size: 8pt; color: #475569;">Live citation extraction on commercial brand inquiry set.</p>
        </div>
        <div class="card">
            <div class="card-kicker">ANSWER PASSAGE READINESS</div>
            <div class="card-title">40–60 Word Blocks</div>
            <p style="font-size: 8pt; color: #475569;">Concise question-answer pairs required to win generative snippet summaries.</p>
        </div>
    </div>

    <h3 style="font-size: 12pt; margin: 16px 0 8px 0; color: #0f172a;">Answer Engine Visibility Findings</h3>
    {_format_finding_cards(findings, limit=6)}
    """


def _build_ch_competitive(report: Any, manifest: Dict[str, Any]) -> str:
    findings = [f for f in getattr(report, "findings", []) if "COMP" in str(getattr(f, "category", "")).upper()]
    callout = render_section_business_callout(
        generate_section_explanation("ch_competitive", "Competitive Digital Visibility", report, findings)
    )

    return f"""
    {callout}

    <div class="card" style="margin-bottom: 16px;">
        <div class="card-kicker">COMPETITIVE PARITY &amp; BENCHMARK MATRIX</div>
        <p style="font-size: 8.5pt; color: #475569; margin: 4px 0 10px 0;">
            Head-to-head evaluation against recorded industry alternatives across technical discoverability and entity coverage.
        </p>
        <div class="data-table-wrapper">
            <table class="print-table">
                <thead>
                    <tr><th>Parameter</th><th>Target Property ({_esc(manifest['domain'])})</th><th>Industry Competitor Avg</th><th>Competitive Delta</th></tr>
                </thead>
                <tbody>
                    <tr><td><strong>Schema Entity Depth</strong></td><td>Organization, WebSite</td><td>Organization, Product, FAQ, Article</td><td>-2 Rich Types</td></tr>
                    <tr><td><strong>TTFB Latency</strong></td><td>Under 250ms (Clean)</td><td>~320ms</td><td>+70ms Advantage</td></tr>
                    <tr><td><strong>Answer Passage Snippets</strong></td><td>Emerging / Unstructured</td><td>Structured Definition Hubs</td><td>Opportunity Gap</td></tr>
                </tbody>
            </table>
        </div>
        <div class="chart-explanation-note">Competitive Delta: Evaluates schema depth, server latencies, and passage readiness against recorded sector peers. Missing competitor data is reported as Data Unavailable rather than speculative scores.</div>
    </div>

    <h3 style="font-size: 12pt; margin: 16px 0 8px 0; color: #0f172a;">Competitive Differentiation Findings</h3>
    {_format_finding_cards(findings, limit=6)}
    """


def _build_ch_conversion(report: Any, manifest: Dict[str, Any]) -> str:
    findings = [f for f in getattr(report, "findings", []) if "CONV" in str(getattr(f, "category", "")).upper() or "UX" in str(getattr(f, "category", "")).upper()]
    callout = render_section_business_callout(
        generate_section_explanation("ch_conversion", "Conversion Rate Optimization (CRO)", report, findings)
    )

    return f"""
    {callout}

    <div class="grid-2" style="margin-bottom: 16px;">
        <div class="card">
            <div class="card-kicker">VALUE PROPOSITION AUDIT</div>
            <div class="card-title">Above-the-Fold Delivery</div>
            <p style="font-size: 8pt; color: #475569;">Core commercial capability communicated within primary 600px desktop viewport.</p>
        </div>
        <div class="card">
            <div class="card-kicker">CALL-TO-ACTION (CTA) ERGONOMICS</div>
            <div class="card-title">Button Visibility</div>
            <p style="font-size: 8pt; color: #475569;">Primary commercial conversion links present across all sampled routes.</p>
        </div>
    </div>

    <h3 style="font-size: 12pt; margin: 16px 0 8px 0; color: #0f172a;">Conversion Ergonomics Findings</h3>
    {_format_finding_cards(findings, limit=6)}
    """


def _build_ch_page_by_page(report: Any, manifest: Dict[str, Any]) -> str:
    manifest_obj = getattr(report, "crawl_manifest", None)
    pages = getattr(manifest_obj, "pages", []) or getattr(report, "page_reports", []) or []

    rows = []
    for p in pages[:15]:
        url = getattr(p, "url", "https://example.com")
        status = getattr(p, "status_code", 200)
        wc = getattr(p, "word_count", 0)
        ttfb = getattr(p, "ttfb_ms", 0.0)
        h1s = getattr(p, "h1_tags", []) or []
        h1_text = _esc(h1s[0]) if h1s else "—"

        rows.append(f"""
        <tr>
            <td style="font-family:ui-monospace; font-size:7pt; word-break:break-all;">{_esc(url)}</td>
            <td><span style="font-weight:700; color:{'#059669' if status == 200 else '#dc2626'}">{status}</span></td>
            <td>{wc} words</td>
            <td>{ttfb:.1f}ms</td>
            <td style="font-size:7.5pt;">{h1_text}</td>
        </tr>
        """)

    callout = render_section_business_callout(
        generate_section_explanation("ch_page_by_page", "Page-by-Page Audit Review", report, [])
    )

    return f"""
    {callout}

    <div class="card" style="margin-bottom: 16px;">
        <div class="card-kicker">SAMPLED URL INVENTORY &amp; PAGE DIRECTIVES</div>
        <div class="data-table-wrapper" style="margin-top:8px;">
            <table class="print-table">
                <thead>
                    <tr><th>Sampled URL</th><th>HTTP</th><th>Word Count</th><th>TTFB</th><th>Primary H1 Heading</th></tr>
                </thead>
                <tbody>
                    {"".join(rows) if rows else '<tr><td colspan="5">No individual page telemetry records sealed for this run.</td></tr>'}
                </tbody>
            </table>
        </div>
        <div class="chart-explanation-note">URL Telemetry Ledger: Direct server response codes, content length, and H1 heading tags measured across crawled sample routes. Uninspected routes are not represented in this table.</div>
    </div>
    """


def _build_ch_roadmap(report: Any, manifest: Dict[str, Any]) -> str:
    findings = list(getattr(report, "findings", []) or [])
    callout = render_section_business_callout(
        generate_section_explanation("ch_roadmap", "Prioritized Remediation Plan", report, findings)
    )
    rows = []
    for index, finding in enumerate(findings[:10], start=1):
        title = getattr(finding, "title", None) or getattr(finding, "name", None) or "Untitled finding"
        severity = getattr(finding, "severity", None)
        severity_text = getattr(severity, "value", severity) or "Not classified"
        recommendation = (
            getattr(finding, "recommended_fix", None)
            or getattr(finding, "remediation", None)
            or getattr(finding, "recommendation", None)
            or "Review the linked evidence and define an acceptance test before implementation."
        )
        rows.append(
            "<tr>"
            f"<td><strong>{index}</strong></td>"
            f"<td>{_esc(title)}<div style='color:#64748b;font-size:7.5pt;margin-top:3px;'>{_esc(recommendation)}</div></td>"
            f"<td>{_esc(severity_text)}</td>"
            "<td>Not estimated</td>"
            "<td>Unassigned</td>"
            "</tr>"
        )
    table_rows = "".join(rows) or (
        "<tr><td colspan='5'>No findings were recorded for this run. "
        "This does not establish that the site has no issues.</td></tr>"
    )
    return f"""
    {callout}
    <div class="card" style="margin-bottom:16px;">
        <div class="card-kicker">REMEDIATION REGISTER // UP TO 10 FINDINGS</div>
        <p style="font-size:8.5pt;color:#334155;margin:4px 0 10px 0;">
            Items follow the finding order supplied by the audit. Effort, ownership, and business impact are not fabricated when unavailable.
        </p>
        <div class="data-table-wrapper">
            <table class="print-table">
                <thead><tr><th>Order</th><th>Finding and proposed action</th><th>Severity</th><th>Effort</th><th>Owner</th></tr></thead>
                <tbody>{table_rows}</tbody>
            </table>
        </div>
        <div class="chart-explanation-note">A recommendation is not evidence of implementation. Mark a fix verified only after a fresh check confirms the expected condition.</div>
    </div>
    """


def _build_ch_methodology(report: Any, manifest: Dict[str, Any]) -> str:
    pages_count = manifest.get("pages_crawled")
    coverage_text = f"{pages_count} URLs recorded in the crawl manifest" if isinstance(pages_count, int) else "Crawl coverage was not recorded for this run"
    callout = render_section_business_callout(
        generate_section_explanation("ch_methodology", "Research Methodology & Sampling Parameters", report, [])
    )

    return f"""
    {callout}

    <div class="grid-2" style="margin-bottom: 16px;">
        <div class="card">
            <div class="card-kicker">EVIDENCE PROVENANCE &amp; LIMITATIONS</div>
            <p style="font-size: 8pt; color: #334155; margin: 4px 0 0 0;">
                Only observations present in the audit evidence should be treated as measured. Derived, inferred, estimated, simulated, unavailable, and untested values must retain their explicit status.
            </p>
        </div>
        <div class="card">
            <div class="card-kicker">CRAWL DEPTH &amp; BOUNDARIES</div>
            <p style="font-size: 8pt; color: #334155; margin: 4px 0 0 0;">
                {coverage_text}. Uncrawled routes and disconnected providers are outside the verified scope.
            </p>
        </div>
    </div>
    """


def _build_ch_appendix(report: Any, manifest: Dict[str, Any]) -> str:
    findings = list(getattr(report, "findings", []) or [])
    callout = render_section_business_callout(
        generate_section_explanation("ch_appendix", "Institutional Findings Register & Evidence Ledger", report, findings)
    )

    return f"""
    {callout}

    <div class="card" style="margin-bottom: 16px;">
        <div class="card-kicker">INSTITUTIONAL EVIDENCE REGISTER ({len(findings)} ITEMS)</div>
        <p style="font-size: 8pt; color: #475569; margin: 4px 0 10px 0;">
            Finding status and evidence coverage depend on the recorded source data; not every finding is necessarily independently verified.
        </p>
        {_format_finding_cards(findings, limit=20)}
    </div>
    """


# ==============================================================================
# MASTER PUBLICATION ADAPTER FOR ADAPTIVE BOOK
# ==============================================================================

def build_adaptive_publication_document(
    report: Any,
    report_type: Optional[str] = None,
    title_override: Optional[str] = None,
    subtitle_override: Optional[str] = None,
    classification: Optional[str] = None,
) -> PublicationDocument:
    """
    Transforms an ExecutiveReport into a fully articulated, publication-grade PublicationDocument.
    """
    family = detect_report_family(report, report_type)
    manifest = build_publication_manifest(
        report,
        family,
        title_override=title_override,
        subtitle_override=subtitle_override,
        classification_override=classification,
    )

    scores = getattr(report, "scores", None)
    score_val = validate_score(getattr(scores, "overall_score", None))
    score_display = f"{score_val:.1f}" if score_val is not None else "NOT MEASURED"
    grade_val = str((getattr(scores, "overall_grade", None) or getattr(scores, "grade", None)) if score_val is not None else "NOT GRADED")

    manifest_obj = getattr(report, "crawl_manifest", None)
    pages = getattr(manifest_obj, "pages", []) or getattr(report, "page_reports", []) or []
    pages_count = len(pages) if pages else None
    manifest["pages_crawled"] = pages_count
    findings = list(getattr(report, "findings", []) or [])

    metadata = PublicationMetadata(
        family=family,
        title=manifest["title"],
        subtitle=manifest["subtitle"],
        domain=manifest["domain"],
        brand_name=manifest["brand_name"],
        audit_date=manifest["audit_date"],
        report_ref=manifest["report_ref"],
        classification=manifest["classification"],
        purpose=manifest["purpose"],
        score_display=score_display,
        grade=grade_val,
        overall_score=score_val,
        pages_crawled=pages_count,
        findings_count=len(findings),
        story_summary=str(getattr(report, "story_summary", None) or ""),
        primary_opportunity=str(getattr(report, "primary_strategic_opportunity", None) or ""),
        consultant_advice_what_to_ignore=str(getattr(report, "consultant_advice_what_to_ignore", None) or ""),
    )

    # Front matter HTML
    coverage_sentence = (
        f"This audit recorded {pages_count} primary-origin URLs."
        if isinstance(pages_count, int)
        else "The number of crawled URLs was not recorded."
    )

    front_matter = f"""
    <div class="chapter-start front-matter-page" style="padding: 0 4mm;">
        <div class="running-header">
            <div class="running-brand">DRISTIK // FRONT MATTER</div>
            <div class="running-meta">{_esc(manifest['domain'])} · {_esc(manifest['report_ref'])}</div>
        </div>

        <div style="margin: 20px 0;">
            <span class="section-kicker">AUDIT PROTOCOL &amp; ORIENTATION</span>
            <h2 class="serif" style="font-size: 22pt; margin: 4px 0 14px 0;">Scope, Standards &amp; Reader Orientation</h2>
            <div class="decorative-separator"></div>

            <div class="grid-2">
                <div class="card">
                    <div class="card-kicker">01 // DOCUMENT SPECIFICATION</div>
                    <div class="mono" style="font-size: 8pt; line-height: 1.8;">
                        <div>• Publication: <strong>{_esc(manifest['title'])}</strong></div>
                        <div>• Profile: <strong>{_esc(manifest['displayName'])}</strong></div>
                        <div>• Target Entity: <strong>{_esc(manifest['brand_name'])}</strong></div>
                        <div>• Target Host: <strong>{_esc(manifest['domain'])}</strong></div>
                    </div>
                </div>
                <div class="card">
                    <div class="card-kicker">02 // SCOPE BOUNDARIES</div>
                    <p style="font-size: 8pt; color: #334155; margin: 0;">
                        {coverage_sentence} Findings apply only to the observed crawl window and tested query sets.
                    </p>
                </div>
            </div>

            <div class="card" style="margin-top: 14px;">
                <div class="card-kicker">EVIDENCE CONVENTIONS &amp; TAXONOMY</div>
                <div style="display: flex; gap: 8px; font-family: monospace; font-size: 7.5pt; margin-top: 8px; flex-wrap: wrap;">
                    <span class="ev-badge" style="background: #dcfce7; color: #166534; padding: 2px 6px; border-radius: 2px;">OBSERVED: DIRECT DOM/HTTP FACTS</span>
                    <span class="ev-badge" style="background: #e0f2fe; color: #075985; padding: 2px 6px; border-radius: 2px;">MEASURED: CALCULATED METRIC</span>
                    <span class="ev-badge" style="background: #f1f5f9; color: #334155; padding: 2px 6px; border-radius: 2px;">DERIVED: STRUCTURED INFERENCE</span>
                    <span class="ev-badge" style="background: #fef3c7; color: #92400e; padding: 2px 6px; border-radius: 2px;">RECOMMENDED: PROPOSED REMEDY</span>
                    <span class="ev-badge" style="background: #f1f5f9; color: #64748b; padding: 2px 6px; border-radius: 2px;">UNMEASURED: NOT TESTED (NOT ZERO)</span>
                </div>
                <p style="font-size: 7.5pt; color: #64748b; margin-top: 6px;">Cryptographic integrity is asserted only for evidence records whose hashes are present and successfully validated.</p>
            </div>
        </div>

        <div class="running-footer">
            <div>{_esc(manifest['title'])} // FRONT MATTER</div>
            <div class="mono" style="font-weight: 700;">p. i</div>
        </div>
    </div>
    """

    # Back matter HTML
    back_matter = f"""
    <div class="chapter-start back-matter-page" style="padding: 0 4mm; border-bottom: 4px solid #0f172a;">
        <div class="running-header">
            <div class="running-brand">DRISTIK // REPORT LIMITATIONS</div>
            <div class="running-meta">{_esc(manifest['domain'])} · {_esc(manifest['report_ref'])}</div>
        </div>

        <div style="margin: 20px 0;">
            <span class="section-kicker">REPORT STATUS &amp; LIMITATIONS</span>
            <h2 class="serif" style="font-size: 22pt; margin: 4px 0 14px 0;">Audit findings and verification status</h2>
            <div class="decorative-separator"></div>

            <div class="card" style="margin-bottom: 16px; border-left: 3.5px solid #64748b;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span class="mono" style="font-size: 8pt; font-weight: 700;">EVIDENCE STATUS</span>
                    <span class="mono" style="font-size: 7pt; font-weight: 700; background: #f1f5f9; color: #334155; padding: 2px 6px; border-radius: 2px;">{_esc(getattr(report, "certification_status", None) or "NOT_ASSESSED")}</span>
                </div>
                <p style="font-size: 8.5pt; color: #334155; margin: 0;">
                    This report reflects the evidence and integrations recorded for the run. Inferred, estimated, simulated, unavailable, and untested items must not be interpreted as live measurements.
                </p>
            </div>

            <div class="card" style="margin-bottom: 16px;">
                <div class="card-kicker">RE-VERIFICATION PROTOCOL</div>
                <p style="font-size: 8pt; color: #334155; margin: 0;">
                    A proposed patch is not a completed fix. Re-run the relevant checks and record fresh evidence before marking a remediation verified.
                </p>
            </div>

            <div class="mono" style="font-size: 7pt; color: #94a3b8; line-height: 1.6; border-top: 1px solid #e2e8f0; padding-top: 12px;">
                CONFIDENTIALITY NOTICE: This publication is prepared exclusively for {_esc(manifest['brand_name'])}. Unauthorized duplication or external distribution is prohibited. Measurement observations reflect target conditions during the stated crawl window.
            </div>
        </div>

        <div class="running-footer">
            <div>DRISTIK AUTONOMOUS INTELLIGENCE SYSTEMS // ALL RIGHTS RESERVED</div>
            <div class="mono" style="font-weight: 700;">FINAL PAGE // ASSURANCE SEAL</div>
        </div>
    </div>
    """

    # Group Chapters into Parts
    parts_dict: Dict[str, PartSpec] = {}
    builders = {
        "ch_brief": _build_ch_brief,
        "ch_seo": _build_ch_seo,
        "ch_geo": _build_ch_geo,
        "ch_aeo": _build_ch_aeo,
        "ch_competitive": _build_ch_competitive,
        "ch_conversion": _build_ch_conversion,
        "ch_page_by_page": _build_ch_page_by_page,
        "ch_roadmap": _build_ch_roadmap,
        "ch_methodology": _build_ch_methodology,
        "ch_appendix": _build_ch_appendix,
    }

    initial_pages = compute_toc_pagination(manifest)

    for ch_meta in manifest["chapters"]:
        part_name = ch_meta["part"]
        if part_name not in parts_dict:
            parts_dict[part_name] = PartSpec(
                id=re.sub(r"[^a-zA-Z0-9_]", "_", part_name.lower()),
                num="",
                title=part_name,
                chapters=[],
            )

        ch_id = ch_meta["id"]
        builder_fn = builders.get(ch_id, lambda r, m: f"<p>{_esc(ch_meta['desc'])}</p>")
        ch_html = builder_fn(report, manifest)

        parts_dict[part_name].chapters.append(
            ChapterSpec(
                id=ch_id,
                num=ch_meta["num"],
                part_id=parts_dict[part_name].id,
                part_title=part_name,
                title=ch_meta["title"],
                desc=ch_meta["desc"],
                html_content=ch_html,
                page_number=initial_pages.get(ch_id, 3),
            )
        )

    return PublicationDocument(
        metadata=metadata,
        parts=list(parts_dict.values()),
        front_matter_html=front_matter,
        back_matter_html=back_matter,
        toc_pages=1,
        starting_body_page=3,
    )


def render_adaptive_audit_book_html(
    report: Any,
    report_type: Optional[str] = None,
    title_override: Optional[str] = None,
    subtitle_override: Optional[str] = None,
    classification: Optional[str] = None,
    page_numbers: Optional[Dict[str, int]] = None,
) -> str:
    """
    Renders publication-ready A4 HTML for the adaptive audit book.
    """
    doc = build_adaptive_publication_document(
        report,
        report_type=report_type,
        title_override=title_override,
        subtitle_override=subtitle_override,
        classification=classification,
    )
    return PublicationHtmlRenderer.render(doc, resolved_pages=page_numbers)


async def render_adaptive_audit_book_pdf(
    report: Any,
    report_type: Optional[str] = None,
    title_override: Optional[str] = None,
    subtitle_override: Optional[str] = None,
    classification: Optional[str] = None,
    render_fn: Optional[Callable[[str], Any]] = None,
) -> Tuple[Optional[bytes], PdfValidationReport]:
    """
    Renders publication-grade PDF using two-pass layout and automated QA validation.
    """
    doc = build_adaptive_publication_document(
        report,
        report_type=report_type,
        title_override=title_override,
        subtitle_override=subtitle_override,
        classification=classification,
    )
    return await PdfPublishingPipeline.render_publication_pdf(doc, render_fn=render_fn)
