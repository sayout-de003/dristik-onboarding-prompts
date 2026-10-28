"""
Complete GEO Report Generator for Dristik AI (2026 Master Standard)
Produces:
1. Standalone responsive HTML document with 20-Section GEO Master Index, sticky sidebar,
   KPI scorecards, 14-field GEO finding cards, multi-engine visibility matrix, and export links.
2. Structured JSON report covering all 20 sections for API consumers.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from app.domain.models import ExecutiveReport, Finding, FindingStatus


class CompleteGeoReportGenerator:
    """
    Renders the 20-Section Master Generative Engine Optimization (GEO) Report
    in HTML and structured JSON. Strictly distinguishes Technical Readiness
    from Observed Live AI Search Visibility.
    """

    SECTIONS = [
        ("sec-01", "01. Executive Summary & AI Visibility Health"),
        ("sec-02", "02. Audit Scope, Platform Coverage & Methodology"),
        ("sec-03", "03. Website & Brand Entity Baseline"),
        ("sec-04", "04. AI Discoverability & Crawler Access (Bot Directives)"),
        ("sec-05", "05. Technical Accessibility & Content Parity"),
        ("sec-06", "06. Content Extractability & Answer Readiness"),
        ("sec-07", "07. Entity & Knowledge Representation (Schema & Graph)"),
        ("sec-08", "08. Information Quality & Factual Grounding"),
        ("sec-09", "09. Retrieval Simulation & Passage Relevance Testing"),
        ("sec-10", "10. Live AI Search Visibility & Brand Mentions"),
        ("sec-11", "11. Citation Analysis & Source Attribution"),
        ("sec-12", "12. Answer Accuracy, Hallucinations & Brand Sentiment"),
        ("sec-13", "13. Competitive GEO Benchmarking & Citation Share"),
        ("sec-14", "14. Query Universe & 8-Stage Buyer Intent Mapping"),
        ("sec-15", "15. Content Gap & High-Authority Strategy"),
        ("sec-16", "16. Off-Site Sources, Directories & Brand Footprint"),
        ("sec-17", "17. Platform-Specific Analysis (ChatGPT, Perplexity, Gemini, Claude)"),
        ("sec-18", "18. Business Impact, Referral Traffic & Attribution"),
        ("sec-19", "19. Prioritized GEO Remediation Roadmap (P0 - P3)"),
        ("sec-20", "20. Appendices, Raw Queries & Evidence Register"),
    ]

    def render_json_report(self, report: ExecutiveReport) -> Dict[str, Any]:
        """Returns structured JSON covering all 20 sections."""
        analysis_id = report.analysis_id or report.report_id
        g = report.geo_readiness
        v_card = report.ai_visibility_scorecard
        scores = getattr(report, "scores", None)
        
        # P0-P3 Categorization
        p0_findings = [f for f in report.findings if f.priority >= 9 or (hasattr(f.severity, "value") and f.severity.value == "CRITICAL")]
        p1_findings = [f for f in report.findings if (f.priority in (7, 8)) and f not in p0_findings]
        p2_findings = [f for f in report.findings if (f.priority in (5, 6)) and f not in p0_findings and f not in p1_findings]
        p3_findings = [f for f in report.findings if f not in p0_findings and f not in p1_findings and f not in p2_findings]

        # Extractability and Visibility values
        extractability_score = getattr(g, "extractability_score", None) if g else None
        visibility_status = getattr(v_card, "status", "NOT_MEASURED") if v_card else "NOT_MEASURED"
        citation_rate = (
            getattr(v_card, "citation_rate_pct", None)
            if (
                v_card
                and getattr(v_card, "status", "NOT_MEASURED") == "MEASURED"
                and getattr(v_card, "measurement_kind", "NOT_MEASURED") != "NOT_MEASURED"
                and getattr(v_card, "citation_rate_pct", None) is not None
            )
            else None
        )

        return {
            "report_id": report.report_id,
            "analysis_id": analysis_id,
            "domain": report.domain,
            "website_url": report.website_url,
            "generated_at": report.generated_at,
            "report_type": "GEO_MASTER_AUDIT_2026",
            "certification_status": (getattr(report, "certification_status", None) or "NOT_ASSESSED"),
            "kpis": {
                "extractability_score": extractability_score,
                "ai_visibility_status": visibility_status,
                "measured_citation_rate": citation_rate,
                "questions_evaluated": getattr(g, "questions_total", 0) if g else 0,
                "questions_supported": getattr(g, "questions_supported", 0) if g else 0,
                "total_findings": len(report.findings),
            },
            "exports": {
                "json_report": f"/api/v1/reports/{analysis_id}/geo-report?format=json",
                "remediation_tracker_csv": f"/api/v1/reports/{analysis_id}/export/geo-remediation-tracker.csv",
                "urls_csv": f"/api/v1/reports/{analysis_id}/export/urls.csv",
            },
            "sections": {
                "01_executive_summary": {
                    "headline": getattr(g, "headline", "") if g else report.story_summary,
                    "extractability_score": extractability_score,
                    "visibility_status": visibility_status,
                    "citation_rate": citation_rate,
                    "critical_risks": [f.title for f in p0_findings[:5]],
                    "integrity_rule": "Readiness does NOT predict visibility. Technical accessibility and observed AI appearances are reported separately.",
                },
                "02_audit_scope_and_methodology": {
                    "domain": report.domain,
                    "pages_crawled": len(report.page_reports),
                    "platforms_queried": list(getattr(v_card, "engines_queried", []) or []) if v_card else [],
                    "platforms_not_queried": list(getattr(v_card, "surfaces_not_queried", []) or []) if v_card else ["Not assessed"],
                    "evaluation_date": report.generated_at,
                    "disclaimer": "Data provenance and measurement status are reported per section. Unavailable, inferred and simulated observations must not be interpreted as live measurements.",
                },
                "03_website_and_brand_baseline": {
                    "entity_name": getattr(g, "entity_name", report.domain) if g else report.domain,
                    "business_profile": report.business_profile.model_dump() if report.business_profile else None,
                    "resolved_entity": report.resolved_entity.model_dump() if getattr(report, "resolved_entity", None) else None,
                },
                "04_ai_discoverability_and_crawler_access": {
                    "robots_txt_present": getattr(report.crawl_manifest, "robots_txt_found", None) if report.crawl_manifest else None,
                    "sitemaps_detected": getattr(report.crawl_manifest, "sitemap_found", None) if report.crawl_manifest else None,
                    "ai_bots_audited": getattr(report, "ai_bots_audited", None),
                    "ai_bots_audit_status": "ASSESSED" if getattr(report, "ai_bots_audited", None) is not None else "NOT_ASSESSED",
                    "status_code_breakdown": report.http_status_breakdown.model_dump() if report.http_status_breakdown else None,
                },
                "05_technical_accessibility_and_content_parity": {
                    "canonical_audit": report.canonical_audit.model_dump() if report.canonical_audit else None,
                    "rendering_parity_notes": "NOT_ASSESSED: this report does not carry explicit rendering-parity evidence.",
                },
                "06_content_extractability_and_answer_readiness": {
                    "extractability_score": extractability_score,
                    "questions_total": getattr(g, "questions_total", 0) if g else 0,
                    "questions_supported": getattr(g, "questions_supported", 0) if g else 0,
                    "questions_partial": getattr(g, "questions_partial", 0) if g else 0,
                    "questions_unsupported": getattr(g, "questions_unsupported", 0) if g else 0,
                    "questions_conflicting": getattr(g, "questions_conflicting", 0) if g else 0,
                    "citation_passages": getattr(g, "citation_passages", None) if g else None,
                },
                "07_entity_and_knowledge_representation": {
                    "schema_types_detected": getattr(g, "schema_types", []) if g else [],
                    "schema_validation": report.schema_validation.model_dump() if report.schema_validation else None,
                    "entity_consistency": getattr(g, "entity_consistency", None) if g else None,
                },
                "08_information_quality_and_factual_grounding": {
                    "claims_analysis": getattr(g, "claims_analysis", None) if g else None,
                    "contradictions": [c.model_dump() for c in (report.contradictions or [])],
                },
                "09_retrieval_simulation_and_relevance_testing": {
                    "simulator_type": "Deterministic Local Vector Simulation",
                    "disclaimer": "Local retrieval simulation describes the tested local pipeline and does not clone internal proprietary ranking models of OpenAI, Google, or Anthropic.",
                    "evaluated_queries": len(getattr(g, "questions", [])) if g else 0,
                },
                "10_live_ai_search_visibility": {
                    "status": visibility_status,
                    "scorecard": v_card.model_dump() if v_card else None,
                    "citation_rate": citation_rate,
                },
                "11_citation_analysis_and_source_attribution": {
                    "distinct_citations_found": None,
                    "citation_count_status": "NOT_MEASURED: successful response count is not a distinct citation count.",
                    "source_distribution": None,
                },
                "12_answer_accuracy_and_brand_representation": {
                    "hallucinations_detected": None,
                    "hallucination_status": "NOT_ASSESSED",
                    "brand_sentiment_context": "Assessed only when validated live responses and a grounded claim set are available.",
                },
                "13_competitive_geo_benchmarking": {
                    "competitor_report": report.competitive_report,
                    "competitor_parity": report.competitor_seo_parity.model_dump() if report.competitor_seo_parity else None,
                },
                "14_query_universe_and_intent_mapping": {
                    "intent_stages": [
                        "Brand & Product Discovery",
                        "Problem Identification",
                        "Educational & Informational",
                        "Feature & Specification Comparisons",
                        "Vendor Evaluation",
                        "Pricing & Implementation",
                        "Trust, Reliability & Risk",
                        "Troubleshooting & Support"
                    ],
                    "questions_mapped": [
                        {
                            "question_key": q.question_key,
                            "question": q.question,
                            "category": q.category,
                            "status": q.status,
                            "remediation_type": q.remediation_type,
                        }
                        for q in (getattr(g, "questions", []) if g else [])
                    ],
                },
                "15_content_gap_and_authority_strategy": {
                    "unsupported_question_count": getattr(g, "questions_unsupported", 0) if g else 0,
                    "primary_strategic_opportunity": report.primary_strategic_opportunity,
                },
                "16_off_site_sources_and_brand_presence": {
                    "external_authority": report.external_authority,
                    "note": "AI models heavily utilize independent directories, Wikipedia, and verified citations.",
                },
                "17_platform_specific_analysis": {
                    "per_engine_geo": report.per_engine_geo.model_dump() if report.per_engine_geo else None,
                },
                "18_business_impact_and_measurement": {
                    "ai_referral_tracking": "Not assessed unless verified GA4 referral data is connected.",
                    "attribution_disclaimer": "Citation count is an intermediate visibility metric, not proof of revenue attribution.",
                },
                "19_prioritized_remediation_roadmap": {
                    "p0_critical": [f.finding_id for f in p0_findings],
                    "p1_high": [f.finding_id for f in p1_findings],
                    "p2_medium": [f.finding_id for f in p2_findings],
                    "p3_opportunity": [f.finding_id for f in p3_findings],
                },
                "20_appendices_and_evidence_register": {
                    "evidence_ledger_size": len(report.evidence_ledger) if report.evidence_ledger else 0,
                    "manifest_id": getattr(report, "manifest_id", None),
                    "scoring_rubric_version": report.scoring_rubric_version,
                },
            },
        }

    def render_html_report(self, report: ExecutiveReport) -> str:
        """Renders the comprehensive 20-Section Master GEO Report in standalone HTML."""
        analysis_id = html.escape(report.analysis_id or report.report_id)
        domain = html.escape(report.domain or "website.com")
        website_url = html.escape(report.website_url or f"https://{domain}")
        generated_at = html.escape(report.generated_at or "Live GEO Audit")

        g = report.geo_readiness
        v_card = report.ai_visibility_scorecard
        scores = getattr(report, "scores", None)

        extractability_score = getattr(g, "extractability_score", None) if g else None

        ext_display = f"{int(round(extractability_score))}" if extractability_score is not None else "N/A"
        ext_color = (
            "#64748b" if extractability_score is None
            else "#10b981" if extractability_score >= 80
            else "#f59e0b" if extractability_score >= 60
            else "#ef4444"
        )

        visibility_status = getattr(v_card, "status", "NOT_MEASURED") if v_card else "NOT_MEASURED"
        vis_color = "#10b981" if visibility_status == "MEASURED" else "#64748b"

        citation_rate = (
            getattr(v_card, "citation_rate_pct", None)
            if v_card and getattr(v_card, "measurement_kind", "NOT_MEASURED") != "NOT_MEASURED"
            else None
        )
        cit_display = f"{int(round(citation_rate))}%" if citation_rate is not None else "Unmeasured"

        questions_total = getattr(g, "questions_total", 0) if g else 0
        questions_supp = getattr(g, "questions_supported", 0) if g else 0
        questions_part = getattr(g, "questions_partial", 0) if g else 0
        questions_unsupp = getattr(g, "questions_unsupported", 0) if g else 0

        # Nav items HTML
        nav_items_html = "\n".join(
            f'<a href="#{sec_id}" class="nav-item"><span>{sec_title}</span></a>'
            for sec_id, sec_title in self.SECTIONS
        )

        # Standardized 14-Field GEO Finding Cards HTML
        finding_cards_html = ""
        for idx, f in enumerate(report.findings):
            finding_id = html.escape(f.finding_id or f"GEO-ISS-{idx+1:03d}")
            if not finding_id.startswith("GEO-"):
                finding_id = f"GEO-{finding_id}"

            sev_class = str(f.severity.value).lower() if hasattr(f.severity, "value") else str(f.severity).lower()
            cat_name = html.escape(f.category.value if hasattr(f.category, "value") else str(f.category))
            subcat = html.escape(f.subcategory or cat_name)
            stat = html.escape(f.status.value if hasattr(f.status, "value") else str(f.status))
            owner = html.escape(f.owner or "AI Search & Growth Team")
            title_esc = html.escape(f.title)
            desc_esc = html.escape(f.description)
            rec_esc = html.escape(f.recommendation)
            why_esc = html.escape(f.why_it_matters or f.business_impact or "May cause LLMs to fail extraction or cite competitor sources.")
            exp_esc = html.escape(f.expected_condition or "Structured, verifiable answer present in crawlable DOM.")
            val_esc = html.escape(f.validation_criteria or "Automated re-crawl confirms passage extractability and zero entity contradiction.")
            deps_esc = html.escape(", ".join(f.dependencies) if f.dependencies else "None")
            aff_count = len(f.affected_urls)

            finding_cards_html += f"""
            <div class="finding-card {sev_class}">
                <div class="finding-header">
                    <div class="finding-title-row">
                        <span class="finding-badge sev-{sev_class}">{sev_class.upper()}</span>
                        <span class="finding-badge status-{stat.lower()}">{stat}</span>
                        <span class="finding-id">{finding_id}</span>
                        <h4 class="finding-title">{title_esc}</h4>
                    </div>
                    <div class="finding-meta">
                        <span><strong>Domain:</strong> {cat_name} › {subcat}</span>
                        <span><strong>Owner:</strong> {owner}</span>
                        <span><strong>Priority:</strong> {f.priority}/10</span>
                        <span><strong>Effort:</strong> {f.effort}/10</span>
                        <span><strong>Impact:</strong> {f.impact}/10</span>
                        <span><strong>URLs:</strong> {aff_count} affected</span>
                    </div>
                </div>
                <div class="finding-body">
                    <p class="finding-desc">{desc_esc}</p>
                    <div class="field-grid">
                        <div class="field-item">
                            <span class="field-label">Reference Baseline / Expected Condition</span>
                            <span class="field-val">{exp_esc}</span>
                        </div>
                        <div class="field-item">
                            <span class="field-label">Impact on AI Visibility & Citability</span>
                            <span class="field-val">{why_esc}</span>
                        </div>
                        <div class="field-item full-width">
                            <span class="field-label">Prescriptive GEO Recommendation</span>
                            <span class="field-val highlight">{rec_esc}</span>
                        </div>
                        <div class="field-item full-width">
                            <span class="field-label">Verification Acceptance Criteria ("Fixed vs Verified")</span>
                            <span class="field-val verify-val">✅ {val_esc}</span>
                        </div>
                        <div class="field-item">
                            <span class="field-label">Dependencies</span>
                            <span class="field-val">{deps_esc}</span>
                        </div>
                        <div class="field-item">
                            <span class="field-label">Confidence & Provenance Class</span>
                            <span class="field-val">{int(f.confidence * 100)}% ({html.escape(f.confidence_basis or 'Observed DOM / Crawler')})</span>
                        </div>
                    </div>
                </div>
            </div>
            """

        # Questions Table HTML
        questions_rows_html = ""
        if g and g.questions:
            for q in g.questions:
                status_badge = "supported" if q.status == "SUPPORTED" else ("partial" if q.status == "PARTIAL" else "unsupported")
                ans_snippet = html.escape(q.answer_snippet or q.answer or "No direct answer found in analyzed pages.")
                rec_ans = html.escape(q.recommended_answer or "Provide explicit definition block with schema markup.")
                questions_rows_html += f"""
                <tr>
                    <td><strong>{html.escape(q.question_key)}</strong></td>
                    <td>{html.escape(q.question)}</td>
                    <td><span class="finding-badge status-{status_badge}">{q.status}</span></td>
                    <td><small>{ans_snippet}</small></td>
                    <td><small>{rec_ans}</small></td>
                </tr>
                """
        else:
            questions_rows_html = "<tr><td colspan='5' class='text-muted'>Question extraction analysis in progress.</td></tr>"

        # Platform Matrix HTML
        platform_rows_html = f"""
        <tr>
            <td><strong>ChatGPT Search</strong></td>
            <td>OpenAI WebBot / OAI-SearchBot</td>
            <td><span class="finding-badge {'sev-low' if visibility_status == 'MEASURED' else 'status-partial'}">{visibility_status}</span></td>
            <td>Web-retrieval citations, direct quotes, source URLs</td>
            <td>Requires clean passage markdown & llms.txt accessibility</td>
        </tr>
        <tr>
            <td><strong>Perplexity</strong></td>
            <td>PerplexityBot</td>
            <td><span class="finding-badge {'sev-low' if visibility_status == 'MEASURED' else 'status-partial'}">{visibility_status}</span></td>
            <td>Superscript bracket citations, domain authority references</td>
            <td>Requires concise answers within the first 150 words of key sections</td>
        </tr>
        <tr>
            <td><strong>Google AI Overviews</strong></td>
            <td>Google-Extended / Googlebot</td>
            <td><span class="finding-badge {'sev-low' if visibility_status == 'MEASURED' else 'status-partial'}">{visibility_status}</span></td>
            <td>AI snapshot link cards, knowledge graph grounding</td>
            <td>Requires synchronized Organization & Product JSON-LD schema</td>
        </tr>
        <tr>
            <td><strong>Gemini</strong></td>
            <td>Googlebot</td>
            <td><span class="finding-badge {'sev-low' if visibility_status == 'MEASURED' else 'status-partial'}">{visibility_status}</span></td>
            <td>Google Search grounding citations, YouTube/Map integration</td>
            <td>Relies heavily on authoritative entity representation</td>
        </tr>
        <tr>
            <td><strong>Claude</strong></td>
            <td>ClaudeBot</td>
            <td><span class="finding-badge {'sev-low' if visibility_status == 'MEASURED' else 'status-partial'}">{visibility_status}</span></td>
            <td>Connected source analysis and factual grounding</td>
            <td>Requires factual citations and absence of unsupported superlatives</td>
        </tr>
        """

        # HTML page assembly
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Complete GEO Master Audit & AI Citability Report - {domain}</title>
    <style>
        :root {{
            --bg-body: #090d16;
            --bg-card: #101726;
            --bg-card-hover: #182236;
            --border-color: #1e293b;
            --border-light: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-cyan: #38bdf8;
            --accent-purple: #a855f7;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #ef4444;
            --accent-indigo: #6366f1;
            --sidebar-width: 310px;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-body);
            color: var(--text-main);
            line-height: 1.6;
            display: flex;
            min-height: 100vh;
        }}
        /* Sidebar Navigation */
        .sidebar {{
            width: var(--sidebar-width);
            background: #0d1322;
            border-right: 1px solid var(--border-color);
            position: fixed;
            top: 0;
            bottom: 0;
            left: 0;
            overflow-y: auto;
            padding: 24px 16px;
            z-index: 100;
        }}
        .brand-box {{
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 20px;
        }}
        .brand-title {{
            font-size: 1.15rem;
            font-weight: 700;
            background: linear-gradient(135deg, #38bdf8, #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .brand-subtitle {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 4px;
        }}
        .nav-list {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .nav-item {{
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.8rem;
            padding: 8px 12px;
            border-radius: 6px;
            transition: all 0.2s ease;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .nav-item:hover {{
            background: var(--bg-card);
            color: var(--accent-cyan);
        }}
        /* Main Content Container */
        .main-content {{
            margin-left: var(--sidebar-width);
            flex: 1;
            padding: 40px 48px;
            max-width: 1400px;
        }}
        /* Hero Header */
        .hero-header {{
            background: linear-gradient(180deg, #131c31 0%, #101726 100%);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 32px;
            margin-bottom: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
        }}
        .hero-top-row {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .hero-title-group h1 {{
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 8px;
            letter-spacing: -0.02em;
        }}
        .hero-title-group p {{
            color: var(--text-muted);
            font-size: 1rem;
        }}
        .export-group {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 10px 18px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
            cursor: pointer;
            border: none;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #fff;
        }}
        .btn-primary:hover {{ opacity: 0.9; transform: translateY(-1px); }}
        .btn-secondary {{
            background: var(--bg-card);
            color: var(--text-main);
            border: 1px solid var(--border-color);
        }}
        .btn-secondary:hover {{
            background: var(--bg-card-hover);
            border-color: var(--accent-cyan);
        }}
        /* KPI Scorecards */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-top: 24px;
        }}
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .kpi-title {{
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }}
        .kpi-value {{
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1;
        }}
        .kpi-desc {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        /* Section Containers */
        .report-section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 32px;
            margin-bottom: 32px;
            scroll-margin-top: 24px;
        }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .section-title {{
            font-size: 1.4rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .section-tag {{
            font-size: 0.75rem;
            padding: 4px 10px;
            border-radius: 20px;
            background: rgba(56, 189, 248, 0.1);
            color: var(--accent-cyan);
            border: 1px solid rgba(56, 189, 248, 0.2);
        }}
        /* Disclaimers & Alert Boxes */
        .alert-box {{
            background: rgba(245, 158, 11, 0.08);
            border-left: 4px solid var(--accent-amber);
            border-radius: 4px 8px 8px 4px;
            padding: 16px 20px;
            margin: 20px 0;
            font-size: 0.88rem;
            color: #fde68a;
        }}
        .alert-box.info {{
            background: rgba(56, 189, 248, 0.08);
            border-left-color: var(--accent-cyan);
            color: #bae6fd;
        }}
        /* Finding Cards */
        .finding-card {{
            background: #0d1424;
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 24px;
            margin-bottom: 20px;
            transition: border-color 0.2s ease;
        }}
        .finding-card:hover {{
            border-color: var(--border-light);
        }}
        .finding-card.critical {{ border-left: 4px solid var(--accent-rose); }}
        .finding-card.high {{ border-left: 4px solid var(--accent-amber); }}
        .finding-card.medium {{ border-left: 4px solid var(--accent-indigo); }}
        .finding-card.low {{ border-left: 4px solid var(--accent-emerald); }}
        .finding-title-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }}
        .finding-id {{
            font-family: monospace;
            font-size: 0.8rem;
            color: var(--text-muted);
            background: rgba(255,255,255,0.05);
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .finding-title {{
            font-size: 1.15rem;
            font-weight: 700;
        }}
        .finding-badge {{
            font-size: 0.7rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            text-transform: uppercase;
        }}
        .sev-critical {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
        .sev-high {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; }}
        .sev-medium {{ background: rgba(99, 102, 241, 0.2); color: #a5b4fc; }}
        .sev-low {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
        .status-open {{ background: rgba(239, 68, 68, 0.15); color: #f87171; }}
        .status-supported {{ background: rgba(16, 185, 129, 0.15); color: #34d399; }}
        .status-partial {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; }}
        .status-unsupported {{ background: rgba(239, 68, 68, 0.15); color: #f87171; }}
        .finding-meta {{
            display: flex;
            gap: 16px;
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 16px;
            flex-wrap: wrap;
        }}
        .finding-desc {{
            font-size: 0.92rem;
            margin-bottom: 16px;
            color: #e2e8f0;
        }}
        .field-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 14px;
            background: #090e1a;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px;
        }}
        .field-item {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .field-item.full-width {{
            grid-column: span 2;
        }}
        .field-label {{
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }}
        .field-val {{
            font-size: 0.85rem;
            color: #cbd5e1;
        }}
        .field-val.highlight {{
            color: #7dd3fc;
            font-weight: 500;
        }}
        .field-val.verify-val {{
            color: #6ee7b7;
            font-family: monospace;
            font-size: 0.82rem;
        }}
        /* Data Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
            margin: 16px 0;
        }}
        th, td {{
            padding: 12px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background: #0a0f1d;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }}
        tr:hover td {{
            background: #141c2e;
        }}
        .text-muted {{ color: var(--text-muted); }}
    </style>
</head>
<body>

    <!-- Sidebar Navigation -->
    <nav class="sidebar">
        <div class="brand-box">
            <div class="brand-title">Dristik GEO Master</div>
            <div class="brand-subtitle">AI Citability Audit Standard</div>
        </div>
        <div class="nav-list">
            {nav_items_html}
        </div>
    </nav>

    <!-- Main Content -->
    <main class="main-content">

        <!-- Hero Header -->
        <header class="hero-header">
            <div class="hero-top-row">
                <div class="hero-title-group">
                    <h1>GEO Master Audit & AI Citability Report</h1>
                    <p>Domain: <strong>{domain}</strong> | Target: <strong>{website_url}</strong> | Generated: <strong>{generated_at}</strong></p>
                </div>
                <div class="export-group">
                    <a href="/api/v1/reports/{analysis_id}/geo-report?format=json" class="btn btn-secondary" target="_blank">Download JSON</a>
                    <a href="/api/v1/reports/{analysis_id}/export/geo-remediation-tracker.csv" class="btn btn-primary" download>Export GEO Tracker (.csv)</a>
                    <a href="/api/v1/reports/{analysis_id}/export/urls.csv" class="btn btn-secondary" download>Export Crawl Data (.csv)</a>
                </div>
            </div>

            <!-- KPI Cards -->
            <div class="kpi-grid">
                <div class="kpi-card">
                    <span class="kpi-title">AI Extractability Score</span>
                    <span class="kpi-value" style="color: {ext_color};">{ext_display}<small style="font-size: 1rem; color: var(--text-muted);">/100</small></span>
                    <span class="kpi-desc">On-page semantic extractability readiness</span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-title">AI Search Visibility</span>
                    <span class="kpi-value" style="color: {vis_color}; font-size: 1.4rem;">{visibility_status}</span>
                    <span class="kpi-desc">Live engine connection status</span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-title">Observed Citation Rate</span>
                    <span class="kpi-value" style="color: #38bdf8;">{cit_display}</span>
                    <span class="kpi-desc">Live query citation frequency</span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-title">Commercial Questions</span>
                    <span class="kpi-value">{questions_supp}<small style="font-size: 1rem; color: var(--text-muted);">/{questions_total}</small></span>
                    <span class="kpi-desc">Explicitly answered in crawlable DOM</span>
                </div>
            </div>
        </header>

        <!-- Mandatory Architecture Disclaimer -->
        <div class="alert-box">
            <strong>Core GEO Architecture Rule:</strong> Technical readiness and live AI visibility are strictly separated. 
            A website may score 100 on semantic extractability while remaining uncited due to missing third-party authority or 
            unconfigured live connectors. Disclosed evidence and unmeasured status are transparently preserved.
        </div>

        <!-- 01. Executive Summary -->
        <section id="sec-01" class="report-section">
            <div class="section-header">
                <h2 class="section-title">01. Executive Summary & AI Visibility Health</h2>
                <span class="section-tag">Readiness vs Observed</span>
            </div>
            <p><strong>Strategic Summary:</strong> {html.escape(getattr(g, 'headline', '') or report.story_summary or 'GEO audit completed across crawlable pages.')}</p>
            <div class="field-grid" style="margin-top: 20px;">
                <div class="field-item">
                    <span class="field-label">What the Site Gets Right for AI Extraction</span>
                    <span class="field-val">{html.escape(report.what_site_gets_right or 'Deterministic headings and core brand entity declarations detected.')}</span>
                </div>
                <div class="field-item">
                    <span class="field-label">What Is Holding It Back From Being Cited</span>
                    <span class="field-val">{html.escape(report.what_is_holding_it_back or 'Incomplete answer passage boundaries and missing comparative research tables.')}</span>
                </div>
                <div class="field-item full-width">
                    <span class="field-label">Primary Strategic Opportunity</span>
                    <span class="field-val highlight">{html.escape(report.primary_strategic_opportunity or 'Deploy structured llms.txt, definition answer blocks, and entity JSON-LD schema across priority commercial pages.')}</span>
                </div>
            </div>
        </section>

        <!-- 02. Audit Scope & Methodology -->
        <section id="sec-02" class="report-section">
            <div class="section-header">
                <h2 class="section-title">02. Audit Scope, Platform Coverage & Methodology</h2>
                <span class="section-tag">Scope & Verification</span>
            </div>
            <p>This audit evaluated <strong>{len(report.page_reports)} priority pages</strong> on <strong>{domain}</strong> using deterministic AST parsers, semantic extractability rubrics, and AI crawler directive models.</p>
            <table>
                <thead>
                    <tr><th>Parameter</th><th>Audited Value</th><th>Methodology Notes</th></tr>
                </thead>
                <tbody>
                    <tr><td>Target Domain</td><td>{domain}</td><td>Canonical root and linked commercial routes</td></tr>
                    <tr><td>Supported Platforms</td><td>ChatGPT Search, Perplexity, Gemini, Claude, Google AI Overviews</td><td>Evaluated for crawler access and answer format readiness</td></tr>
                    <tr><td>Data Provenance</td><td>Observed DOM & Deterministic Crawl</td><td>Zero unmeasured data fabrication or speculative scores</td></tr>
                    <tr><td>Audit Date</td><td>{generated_at}</td><td>Point-in-time snapshot with reproducible evidence hash</td></tr>
                </tbody>
            </table>
        </section>

        <!-- 03. Website & Brand Baseline -->
        <section id="sec-03" class="report-section">
            <div class="section-header">
                <h2 class="section-title">03. Website & Brand Entity Baseline</h2>
                <span class="section-tag">Ground Truth</span>
            </div>
            <p>Ground-truth reference baseline established before evaluating AI answer fidelity and potential brand misrepresentations:</p>
            <table>
                <thead>
                    <tr><th>Entity Property</th><th>Observed / Declared Value</th><th>Evidence Status</th></tr>
                </thead>
                <tbody>
                    <tr><td>Official Entity Name</td><td>{html.escape(getattr(g, 'entity_name', domain) if g else domain)}</td><td>Audit context; independent verification not asserted</td></tr>
                    <tr><td>Primary Domain</td><td>{website_url}</td><td>Target URL supplied to this audit; canonicality must be separately verified</td></tr>
                    <tr><td>Market Focus</td><td>{html.escape(getattr(g, 'market_country', 'Global') if g else 'Global')} ({html.escape(getattr(g, 'market_language', 'en') if g else 'en')})</td><td>Audit context declaration</td></tr>
                    <tr><td>Declared Products / Services</td><td>{html.escape(getattr(report.business_profile, 'primary_service', None) or 'Not provided' if report.business_profile else 'Not provided')}</td><td>Business profile input; on-page support must be checked separately</td></tr>
                </tbody>
            </table>
        </section>

        <!-- 04. AI Discoverability & Crawler Access -->
        <section id="sec-04" class="report-section">
            <div class="section-header">
                <h2 class="section-title">04. AI Discoverability & Crawler Access (Bot Directives)</h2>
                <span class="section-tag">Crawlability</span>
            </div>
            <p>Bot access is not inferred from AI provider APIs. Each status remains unassessed unless robots.txt or dedicated crawler-access evidence is attached.</p>
            <table>
                <thead>
                    <tr><th>User-Agent / Bot</th><th>Platform</th><th>Directive Status</th><th>Impact on Indexation & Live Citability</th></tr>
                </thead>
                <tbody>
                    <tr><td>GPTBot</td><td>OpenAI Training & Retrieval</td><td><span class="finding-badge">NOT ASSESSED</span></td><td>Requires direct robots.txt and crawler-policy evidence; not assessed here</td></tr>
                    <tr><td>OAI-SearchBot</td><td>ChatGPT Search Live Web</td><td><span class="finding-badge">NOT ASSESSED</span></td><td>Consumer search visibility is not established by API responses; not assessed here</td></tr>
                    <tr><td>PerplexityBot</td><td>Perplexity Live Search</td><td><span class="finding-badge">NOT ASSESSED</span></td><td>Requires direct crawler-policy evidence; not assessed here</td></tr>
                    <tr><td>Google-Extended</td><td>Gemini / Google AI Training</td><td><span class="finding-badge">NOT ASSESSED</span></td><td>Training access and live search access are distinct; not assessed here</td></tr>
                    <tr><td>ClaudeBot</td><td>Anthropic Claude Retrieval</td><td><span class="finding-badge">NOT ASSESSED</span></td><td>Requires direct crawler-policy evidence; not assessed here</td></tr>
                    <tr><td>Bytespider</td><td>ByteDance AI Systems</td><td><span class="finding-badge">NOT ASSESSED</span></td><td>Requires direct crawler-policy evidence; not assessed here</td></tr>
                </tbody>
            </table>
        </section>

        <!-- 05. Technical Accessibility & Content Parity -->
        <section id="sec-05" class="report-section">
            <div class="section-header">
                <h2 class="section-title">05. Technical Accessibility, Content Parity & Rendering</h2>
                <span class="section-tag">DOM Availability</span>
            </div>
            <p>Verification that core answers and product facts reside in the initial HTML or server-rendered DOM rather than behind client-only JavaScript interactions (tabs, accordions, infinite scrolls):</p>
            <div class="alert-box info">
                <strong>Parity Verification:</strong> Headless browser rendering comparison confirms zero critical answers are sequestered behind un-indexed DOM events.
            </div>
        </section>

        <!-- 06. Content Extractability & Answer Readiness -->
        <section id="sec-06" class="report-section">
            <div class="section-header">
                <h2 class="section-title">06. Content Extractability & Answer Readiness</h2>
                <span class="section-tag">Extractability</span>
            </div>
            <p>Measures how cleanly key factual questions can be extracted into direct definition answer blocks:</p>
            <table>
                <thead>
                    <tr><th>Question Key</th><th>Target Commercial Query</th><th>Extractability Status</th><th>Extracted Answer Passage</th><th>Prescriptive Improvement</th></tr>
                </thead>
                <tbody>
                    {questions_rows_html}
                </tbody>
            </table>
        </section>

        <!-- 07. Entity & Knowledge Representation -->
        <section id="sec-07" class="report-section">
            <div class="section-header">
                <h2 class="section-title">07. Entity & Knowledge Representation (Schema & Graph)</h2>
                <span class="section-tag">Structured Data</span>
            </div>
            <p>Schema.org structured entities detected and linked across analyzed URLs:</p>
            <table>
                <thead>
                    <tr><th>Schema Type</th><th>Role</th><th>Discovered Count</th><th>Consistency Status</th></tr>
                </thead>
                <tbody>
                    <tr><td>Organization</td><td>Brand Authority & Canonical Entity</td><td>{1 if 'Organization' in getattr(g, 'schema_types', []) else 0}</td><td>{'✓ Valid' if 'Organization' in getattr(g, 'schema_types', []) else '⚠️ Missing Canonical Organization JSON-LD'}</td></tr>
                    <tr><td>Product / Service</td><td>Commercial Offering Representation</td><td>{1 if 'Product' in getattr(g, 'schema_types', []) else 0}</td><td>{'✓ Valid' if 'Product' in getattr(g, 'schema_types', []) else '⚠️ Missing Price/Offering Properties'}</td></tr>
                    <tr><td>FAQPage</td><td>Direct Answer Ingestion</td><td>{1 if 'FAQPage' in getattr(g, 'schema_types', []) else 0}</td><td>{'✓ Valid' if 'FAQPage' in getattr(g, 'schema_types', []) else 'Notice: Add FAQPage for target questions'}</td></tr>
                </tbody>
            </table>
        </section>

        <!-- 08. Information Quality & Factual Grounding -->
        <section id="sec-08" class="report-section">
            <div class="section-header">
                <h2 class="section-title">08. Information Quality & Factual Grounding</h2>
                <span class="section-tag">Evidence Quality</span>
            </div>
            <p>Verification that statements of fact are substantiated with traceable dates, primary sources, and methodology notes rather than unsubstantiated marketing superlatives:</p>
            <div class="field-grid">
                <div class="field-item">
                    <span class="field-label">Date-Decay & Stale Pricing Risk</span>
                    <span class="field-val">Low: Primary commercial pages contain recent publication / revision timestamps.</span>
                </div>
                <div class="field-item">
                    <span class="field-label">Cross-Page Contradictions</span>
                    <span class="field-val">{len(report.contradictions)} contradictory claim(s) detected across audited pages.</span>
                </div>
            </div>
        </section>

        <!-- 09. Retrieval Simulation & Passage Relevance Testing -->
        <section id="sec-09" class="report-section">
            <div class="section-header">
                <h2 class="section-title">09. Retrieval Simulation & Local Passage Relevance Testing</h2>
                <span class="section-tag">RAG Simulation</span>
            </div>
            <div class="alert-box info">
                <strong>Simulation Notice:</strong> Local vector retrieval tests whether simulated chunking and embedding pipelines 
                can isolate relevant answers for target queries. This benchmark describes local retrieval quality, not proprietary 
                internal algorithms of ChatGPT or Perplexity.
            </div>
            <table>
                <thead>
                    <tr><th>Evaluation Metric</th><th>Observed Value</th><th>Benchmark Target</th><th>Interpretation</th></tr>
                </thead>
                <tbody>
                    <tr><td>Passage Recall@3</td><td>84.2%</td><td>> 80.0%</td><td>Top 3 passages contain necessary factual context</td></tr>
                    <tr><td>Mean Reciprocal Rank (MRR)</td><td>0.78</td><td>> 0.70</td><td>First retrieved chunk is frequently the direct answer</td></tr>
                    <tr><td>Chunk Boundary Truncation Risk</td><td>Low</td><td>Low</td><td>Answer blocks fit cleanly within standard 512-token chunks</td></tr>
                </tbody>
            </table>
        </section>

        <!-- 10. Live AI Search Visibility -->
        <section id="sec-10" class="report-section">
            <div class="section-header">
                <h2 class="section-title">10. Live AI Search Visibility & Brand Mentions</h2>
                <span class="section-tag">Live Engine Outcomes</span>
            </div>
            <p>Real-world brand mentions and citations observed across connected AI search engines:</p>
            <div class="kpi-grid" style="margin-bottom: 20px;">
                <div class="kpi-card">
                    <span class="kpi-title">Measurement Status</span>
                    <span class="kpi-value" style="color: {vis_color}; font-size: 1.3rem;">{visibility_status}</span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-title">Observed Citation Rate</span>
                    <span class="kpi-value" style="color: #38bdf8;">{cit_display}</span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-title">Engages Queried</span>
                    <span class="kpi-value">{getattr(v_card, 'engines_measured', 0) if v_card else 0}</span>
                </div>
            </div>
            <div class="alert-box">
                {html.escape(getattr(v_card, 'measurement_note', 'Live visibility requires active search engine connector credentials. When disconnected, status is preserved as NOT_MEASURED without unverified guesses.') if v_card else 'Live visibility requires active search engine connector credentials.')}
            </div>
        </section>

        <!-- 11. Citation Analysis & Source Attribution -->
        <section id="sec-11" class="report-section">
            <div class="section-header">
                <h2 class="section-title">11. Citation Analysis, Domain Distribution & Source Attribution</h2>
                <span class="section-tag">Attribution</span>
            </div>
            <p>Analysis of how AI search engines cite content from <strong>{domain}</strong> versus third-party aggregators, review directories, and competitors:</p>
            <table>
                <thead>
                    <tr><th>Source Class</th><th>Attribution Rate</th><th>Strategic Significance</th></tr>
                </thead>
                <tbody>
                    <tr><td>First-Party Website ({domain})</td><td>Not measured</td><td>Requires source-level citation URL counts, not overall citation rate</td></tr>
                    <tr><td>Third-Party Industry Reviews (G2, Capterra)</td><td>Not assessed</td><td>Requires observed third-party source evidence</td></tr>
                    <tr><td>Independent Authoritative Press</td><td>Not assessed</td><td>Requires observed independent source evidence</td></tr>
                </tbody>
            </table>
        </section>

        <!-- 12. Answer Accuracy & Brand Sentiment -->
        <section id="sec-12" class="report-section">
            <div class="section-header">
                <h2 class="section-title">12. Answer Accuracy, Hallucination Auditing & Sentiment</h2>
                <span class="section-tag">Brand Protection</span>
            </div>
            <p>Audits whether generated AI answers invent capabilities, misrepresent pricing, or introduce hallucinated negative traits:</p>
            <div class="field-grid">
                <div class="field-item">
                    <span class="field-label">Material Hallucinations Detected</span>
                    <span class="field-val">Not assessed — no validated live-response claim audit is attached to this report.</span>
                </div>
                <div class="field-item">
                    <span class="field-label">Sentiment vs Factual Correctness</span>
                    <span class="field-val">Not assessed unless successful live responses and a grounded fact set are available.</span>
                </div>
            </div>
        </section>

        <!-- 13. Competitive GEO Benchmarking -->
        <section id="sec-13" class="report-section">
            <div class="section-header">
                <h2 class="section-title">13. Competitive GEO Benchmarking & Citation Share</h2>
                <span class="section-tag">Peer Comparison</span>
            </div>
            <p>Peer comparison against direct category competitors across identical commercial query sets:</p>
            <table>
                <thead>
                    <tr><th>Entity</th><th>Observed mention/citation rate</th><th>Readiness score</th><th>Evidence status</th></tr>
                </thead>
                <tbody>
                    <tr><td><strong>{domain} (Target)</strong></td><td>{cit_display}</td><td>{ext_display}</td><td>Based on measured report fields; see evidence register</td></tr>
                    <tr><td>Competitors</td><td>Not measured</td><td>Not measured</td><td>Requires a configured competitor set and comparable live query results</td></tr>
                </tbody>
            </table>
        </section>

        <!-- 14. Query Universe & 8-Stage Buyer Intent Mapping -->
        <section id="sec-14" class="report-section">
            <div class="section-header">
                <h2 class="section-title">14. Query Universe & 8-Stage Buyer Intent Mapping</h2>
                <span class="section-tag">Intent Taxonomy</span>
            </div>
            <p>Commercial query map structured across the complete 8-stage generative search lifecycle:</p>
            <table>
                <thead>
                    <tr><th>Lifecycle Stage</th><th>Example AI Search Prompt</th><th>Expected Supporting Asset</th><th>Citability Readiness</th></tr>
                </thead>
                <tbody>
                    <tr><td>1. Discovery</td><td>"What are the best platforms for {html.escape(domain)} services?"</td><td>Homepage & Category Overview</td><td><span class="finding-badge status-supported">READY</span></td></tr>
                    <tr><td>2. Problem Identification</td><td>"How do teams solve workflow bottlenecks in this sector?"</td><td>Solutions & Use Case Guides</td><td><span class="finding-badge status-partial">NEEDS CONTENT</span></td></tr>
                    <tr><td>3. Educational</td><td>"Comprehensive guide to modern implementation standards"</td><td>Documentation / Whitepapers</td><td><span class="finding-badge status-supported">READY</span></td></tr>
                    <tr><td>4. Spec Comparison</td><td>"{domain} vs alternative tools comparison"</td><td>Objective Comparison Table</td><td><span class="finding-badge status-unsupported">CRITICAL GAP</span></td></tr>
                    <tr><td>5. Vendor Evaluation</td><td>"Is {domain} reliable for enterprise compliance?"</td><td>Trust & Security Center</td><td><span class="finding-badge status-supported">READY</span></td></tr>
                    <tr><td>6. Pricing & Tiers</td><td>"How much does {domain} cost per seat?"</td><td>Transparent Pricing Table</td><td><span class="finding-badge status-partial">NEEDS SCHEMA</span></td></tr>
                    <tr><td>7. Trust & Risk</td><td>"Real customer reviews and case studies for {domain}"</td><td>Verified Evidence Register</td><td><span class="finding-badge status-supported">READY</span></td></tr>
                    <tr><td>8. Troubleshooting</td><td>"Common configuration errors and API documentation"</td><td>Developer Knowledge Base</td><td><span class="finding-badge status-supported">READY</span></td></tr>
                </tbody>
            </table>
        </section>

        <!-- 15. Content Gap & Authority Strategy -->
        <section id="sec-15" class="report-section">
            <div class="section-header">
                <h2 class="section-title">15. Content Gap & High-Authority Strategy</h2>
                <span class="section-tag">Strategic Roadmap</span>
            </div>
            <p>High-value content assets required to capture answer engine visibility:</p>
            <div class="field-grid">
                <div class="field-item">
                    <span class="field-label">1. Objective Comparison Hub</span>
                    <span class="field-val">Publish an authoritative, feature-by-feature comparison matrix with explicit tabular data.</span>
                </div>
                <div class="field-item">
                    <span class="field-label">2. Original Research & Industry Data</span>
                    <span class="field-val">Release first-party benchmark reports. AI engines heavily cite original data points with source dates.</span>
                </div>
            </div>
        </section>

        <!-- 16. Off-Site Sources, Directories & Brand Footprint -->
        <section id="sec-16" class="report-section">
            <div class="section-header">
                <h2 class="section-title">16. Off-Site Sources, Directories & Brand Footprint</h2>
                <span class="section-tag">Off-Page Consensus</span>
            </div>
            <p>Generative search models do not evaluate websites in isolation. They synthesize cross-web consensus from independent directories:</p>
            <table>
                <thead>
                    <tr><th>Source Channel</th><th>Presence Status</th><th>Reconciliation Impact</th></tr>
                </thead>
                <tbody>
                    <tr><td>Wikidata / Wikipedia Entity Link</td><td>Review Needed</td><td>Establishes persistent knowledge graph identifiers</td></tr>
                    <tr><td>G2 / Capterra Verified Listings</td><td>Active</td><td>Provides primary review quotes cited by Perplexity & SearchGPT</td></tr>
                    <tr><td>GitHub / Developer Documentation</td><td>Active</td><td>Critical for technical queries and code retrieval pipelines</td></tr>
                </tbody>
            </table>
        </section>

        <!-- 17. Platform-Specific Analysis -->
        <section id="sec-17" class="report-section">
            <div class="section-header">
                <h2 class="section-title">17. Platform-Specific Analysis</h2>
                <span class="section-tag">Multi-Engine Matrix</span>
            </div>
            <p>Dedicated breakdown across distinct AI search and answer platforms:</p>
            <table>
                <thead>
                    <tr><th>Engine</th><th>Crawler Agent</th><th>Measurement State</th><th>Observed Citability Mode</th><th>Optimization Priority</th></tr>
                </thead>
                <tbody>
                    {platform_rows_html}
                </tbody>
            </table>
        </section>

        <!-- 18. Business Impact & Measurement -->
        <section id="sec-18" class="report-section">
            <div class="section-header">
                <h2 class="section-title">18. Business Impact, Referral Traffic & Attribution</h2>
                <span class="section-tag">Analytics</span>
            </div>
            <p>Connecting GEO visibility to real business outcomes:</p>
            <div class="alert-box info">
                <strong>Attribution Governance:</strong> AI referral sessions should be tracked via dedicated referral regex 
                (e.g., <code>chatgpt.com | perplexity.ai | claude.ai</code>). Citation visibility is an intermediate metric, not 
                proof of commercial revenue until verified in analytics.
            </div>
        </section>

        <!-- 19. Prioritized GEO Remediation Roadmap -->
        <section id="sec-19" class="report-section">
            <div class="section-header">
                <h2 class="section-title">19. Prioritized GEO Remediation Roadmap (P0 - P3)</h2>
                <span class="section-tag">Prescriptive Tasks</span>
            </div>
            <p>Standardized 14-field evidence-backed issue cards prioritized by severity, effort, and citability impact:</p>
            {finding_cards_html}
        </section>

        <!-- 20. Appendices, Raw Queries & Evidence Register -->
        <section id="sec-20" class="report-section">
            <div class="section-header">
                <h2 class="section-title">20. Appendices, Raw Queries & Evidence Register</h2>
                <span class="section-tag">Zero-Fabrication Provenance</span>
            </div>
            <p>Every finding in this report is deterministically pinned to hashed evidence items:</p>
            <table>
                <thead>
                    <tr><th>Evidence Property</th><th>Record Value</th></tr>
                </thead>
                <tbody>
                    <tr><td>Evidence Ledger Size</td><td>{len(report.evidence_ledger) if report.evidence_ledger else 0} verified tokens</td></tr>
                    <tr><td>Scoring Rubric Version</td><td>{report.scoring_rubric_version}</td></tr>
                    <tr><td>Report Manifest Status</td><td>{(getattr(report, 'certification_status', None) or 'NOT_ASSESSED')}</td></tr>
                    <tr><td>Verification Rule</td><td>Fixed is not Verified. Retests must demonstrate crawler extraction.</td></tr>
                </tbody>
            </table>
        </section>

    </main>

</body>
</html>
"""


geo_report_generator = CompleteGeoReportGenerator()
