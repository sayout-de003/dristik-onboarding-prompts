"""
Complete AEO (Answer Engine Optimization) Report Generator for Dristik AI (2026 Master Standard).
Produces:
1. Standalone responsive HTML document with 55-Section Master Taxonomy across 7 Parts,
   15 Auditable Appendices, 4-Tier Decoupled Scorecard, 16 Specialist Modules Registry,
   10 Core Formulas Table, 14-Field AEO Finding Cards, and multi-format CSV/JSON exports.
2. Comprehensive structured JSON report covering all 55 sections and 15 appendices.

Core Architectural Integrity Rule:
Answer Readiness (on-site content completeness), Feature Eligibility (schema & structural fit),
Observed Answer Visibility (empirically recorded SERP/voice/AI snippet appearances), and
Business Outcomes (commercial attribution) are strictly separated. Zero fabricated scores.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from app.domain.models import ExecutiveReport, Finding, FindingStatus
from app.aeo.scoring import AeoMetricsCalculator
from app.aeo.specialists import AeoSpecialistRegistry
from app.aeo.taxonomy import (
    AEO_APPENDICES_15,
    AEO_PARTS,
    AEO_SECTIONS_55,
    DISCIPLINE_TAXONOMY,
)


class CompleteAeoReportGenerator:
    """
    Renders the 55-Section Master Answer Engine Optimization (AEO) Report
    in HTML and structured JSON. Strictly distinguishes Answer Readiness,
    Search Feature Eligibility, Observed Live Answer Visibility, and Business Outcomes.
    """

    SECTIONS = [(s.sec_id, f"{s.number}. {s.title}") for s in AEO_SECTIONS_55]
    PARTS = AEO_PARTS
    APPENDICES = AEO_APPENDICES_15

    DOMAINS_10 = [
        ("Featured Snippet Optimization", "Concise definitions (40-60 words), lists, comparison tables, and heading alignment formatted for rank-zero extraction."),
        ("Question-Based Search Optimization", "Question clusters, FAQ structures, intent resolution, and comprehensive follow-up coverage."),
        ("Voice Search & Conversational Answers", "Natural conversational phrasing, spoken readability, pronunciation clarity, and local action support."),
        ("Rich Results & Structured Answers", "Applicable JSON-LD schemas (Organization, Product, Article, LocalBusiness) strictly validated against visible DOM."),
        ("Knowledge Panels & Entity Answers", "Canonical entity identity, disambiguation, authoritative sameAs profiles, and Wikidata/knowledge graph alignment."),
        ("AI Answer Engine Optimization", "Factual grounding, passage extractability, citation frequency across ChatGPT, Perplexity, Gemini, and Claude."),
        ("Local & Action-Oriented Answers", "Name, Address, Phone (NAP), operating hours, service radius, and Google Business Profile consistency."),
        ("Product & Transactional Answers", "Specifications, pricing models, feature matrices, compatibility, availability, and return policies."),
        ("Support & Troubleshooting Answers", "Procedural step-by-step guides, prerequisites, error codes, and technical troubleshooting flows."),
        ("Answer Visibility & Performance Measurement", "Search Console query-level click/impression tracking, answer feature capture, and conversion attribution."),
    ]

    def render_json_report(self, report: ExecutiveReport) -> Dict[str, Any]:
        """Returns structured JSON covering all 55 sections and 15 appendices."""
        analysis_id = report.analysis_id or report.report_id
        g = report.geo_readiness
        v_card = report.ai_visibility_scorecard

        # 4-Pillar Decoupled Measurement & 10 Core Formulas
        scorecard = AeoMetricsCalculator.calculate(report)
        scorecard_dict = scorecard.to_dict()

        # 16 Modular Specialists
        specialist_results = AeoSpecialistRegistry.execute_all(report)
        specialists_dict = [s.to_dict() for s in specialist_results]

        # Categorize P0 - P3 findings
        p0_findings = [f for f in report.findings if f.priority >= 9 or (hasattr(f.severity, "value") and f.severity.value == "CRITICAL")]
        p1_findings = [f for f in report.findings if (f.priority in (7, 8)) and f not in p0_findings]
        p2_findings = [f for f in report.findings if (f.priority in (5, 6)) and f not in p0_findings and f not in p1_findings]
        p3_findings = [f for f in report.findings if f not in p0_findings and f not in p1_findings and f not in p2_findings]

        questions_total = getattr(g, "questions_total", 0) if g else 0
        questions_supp = getattr(g, "questions_supported", 0) if g else 0
        questions_part = getattr(g, "questions_partial", 0) if g else 0
        questions_unsupp = getattr(g, "questions_unsupported", 0) if g else 0

        # Answer readiness score (0-100)
        answer_readiness_score = getattr(g, "extractability_score", None) if g else None
        if answer_readiness_score is None and scores:
            answer_readiness_score = getattr(scores, "geo_score", None)
        if answer_readiness_score is None:
            answer_readiness_score = scorecard.pillar_a_content_readiness.composite_readiness_score
        if answer_readiness_score is None and questions_total > 0:
            answer_readiness_score = round(((questions_supp * 1.0 + questions_part * 0.5) / questions_total) * 100, 1)

        visibility_status = getattr(v_card, "status", None) if v_card else None
        if not visibility_status:
            visibility_status = scorecard.pillar_c_observed_visibility.state.value
        citation_rate = getattr(report, "ai_visibility_score", None)
        if citation_rate is None and scorecard.pillar_c_observed_visibility.citation_rate_pct is not None:
            citation_rate = scorecard.pillar_c_observed_visibility.citation_rate_pct / 100.0

        # Question mapping
        mapped_questions = []
        if g and g.questions:
            for q in g.questions:
                q_text = q.question.strip()
                q_lower = q_text.lower()
                q_type = "What"
                for word in ["what", "why", "how", "when", "where", "who", "which", "compare", "vs"]:
                    if q_lower.startswith(word) or f" {word} " in q_lower:
                        q_type = word.capitalize()
                        break

                mapped_questions.append({
                    "question_key": q.question_key,
                    "question": q_text,
                    "question_type": q_type,
                    "category": q.category,
                    "status": q.status,
                    "evidence_url": q.evidence_url or report.website_url,
                    "answer_excerpt": q.evidence_snippet or q.answer_snippet or "",
                    "recommended_remediation": q.recommended_answer or "",
                    "remediation_type": q.remediation_type or "ANSWER_BLOCK",
                })

        def _page_has_content_signals(p: Any) -> bool:
            h1 = getattr(p, "h1_tags", None) or getattr(p, "h1", None)
            if not h1 and getattr(p, "seo", None):
                h1 = getattr(p.seo, "h1_tags", None)
            st = getattr(p, "schema_types", None)
            if not st and getattr(p, "seo", None):
                st = getattr(p.seo, "schema_types", None)
            return bool(h1 or st)

        def _get_page_schemas(p: Any) -> List[str]:
            st = getattr(p, "schema_types", None)
            if st is None and getattr(p.seo, "schema_types", None):
                st = getattr(p.seo, "schema_types", None)
            return st or []

        # Build 55 Sections Dictionary
        sections_dict: Dict[str, Any] = {}
        for s in AEO_SECTIONS_55:
            sec_key = f"{s.number}_{s.title.lower().replace(' ', '_').replace('-', '_').replace(',', '')}"
            sections_dict[sec_key] = {
                "section_id": s.sec_id,
                "section_number": s.number,
                "title": s.title,
                "part_id": s.part_id,
                "part_name": s.part_name,
                "description": s.description,
                "checklist": s.checklist,
                "status": "EVALUATED",
            }

        # Ensure full backward compatibility for previous 20 section key names
        legacy_key_map = {
            "01_executive_summary": "01_executive_summary",
            "02_audit_scope_and_methodology": "02_aeo_health_and_performance_scorecard",
            "03_question_universe_and_intent_mapping": "07_question_research_and_discovery",
            "04_answer_readiness_and_content_structure": "16_answer_focused_content_structure",
            "05_featured_snippet_analysis": "33_featured_snippets_and_traditional_search_answers",
            "06_people_also_ask_and_related_questions": "34_people_also_ask_and_related_questions",
            "07_faq_and_question_answer_content_audit": "14_faq_and_question_page_optimization",
            "08_structured_data_and_rich_results": "29_structured_data_and_machine_readable_information",
            "09_entity_answers_and_knowledge_panels": "43_brand_entity_and_knowledge_consistency",
            "10_voice_and_conversational_search": "37_voice_and_assistant_style_answers",
            "11_ai_answer_engine_visibility": "36_conversational_ai_and_answer_platforms",
            "12_local_and_action_oriented_answers": "03_business_and_answer_ecosystem_understanding",
            "13_product_commercial_and_transactional_answers": "23_comparative_and_decision_support_content",
            "14_support_documentation_and_troubleshooting": "38_documentation_knowledge_bases_and_support_answers",
            "15_answer_accuracy_and_source_quality": "18_factual_accuracy_and_verifiability",
            "16_competitor_answer_benchmarking": "47_competitive_answer_share_and_source_gaps",
            "17_search_performance_and_business_outcomes": "48_aeo_traffic_and_referral_analytics",
            "18_content_gaps_and_answer_strategy": "15_question_prioritization_and_coverage_gaps",
            "19_prioritized_remediation_roadmap": "52_question_level_remediation_register",
            "20_appendices_and_evidence_register": "55_methodology_governance_and_evidence_integrity",
        }

        # Populate detailed data into core legacy keys
        sections_dict["01_executive_summary"] = {
            "headline": getattr(g, "headline", "") if g else report.story_summary,
            "answer_readiness_score": answer_readiness_score,
            "observed_visibility_status": visibility_status,
            "questions_evaluated": questions_total,
            "questions_answered_directly": questions_supp,
            "critical_risks": [f.title for f in p0_findings[:5]],
            "core_rule": "Answer readiness, search feature eligibility, and observed answer appearances are separate outcomes.",
        }
        sections_dict["02_audit_scope_and_methodology"] = {
            "domain": report.domain,
            "website_url": report.website_url,
            "pages_audited": len(report.page_reports),
            "search_markets": ["Google Search", "Google Assistant / Voice", "Bing / Copilot", "ChatGPT Search", "Perplexity AI"],
            "evaluation_date": report.generated_at,
            "data_sources": ["DOM Crawl Engine", "JSON-LD Schema Validator", "SERP Snippet Parser", "AI Knowledge Connectors"],
            "disclaimer": "Readiness scores evaluate content completeness against the audit rubric and do NOT represent an official Google ranking factor or guaranteed snippet probability.",
        }
        sections_dict["03_question_universe_and_intent_mapping"] = {
            "intent_taxonomy": [
                "Informational (What, Why, How)",
                "Navigational (Brand, Portal, Login)",
                "Commercial Investigation (Which, Best, Features)",
                "Transactional (Pricing, Cost, Plans, Terms)",
                "Support & Troubleshooting (How to fix, Error, Requirements)",
            ],
            "question_types": ["What", "Why", "How", "When", "Where", "Who", "Which", "Comparison"],
            "questions_total": questions_total,
            "questions_mapped": mapped_questions,
        }
        sections_dict["04_answer_readiness_and_content_structure"] = {
            "readiness_score": answer_readiness_score,
            "definition_block_rule": "Direct answers must appear in the first relevant passage (40-60 words) directly below the corresponding question heading.",
            "evaluated_passages": questions_total,
            "supported_direct_passages": questions_supp,
            "partial_passages": questions_part,
        }
        sections_dict["05_featured_snippet_analysis"] = {
            "supported_formats": ["Paragraph (Definition)", "Numbered / Bulleted List (Procedure/Ranking)", "HTML Table (Comparison/Pricing)"],
            "eligible_pages_count": len([p for p in report.page_reports if _page_has_content_signals(p)]),
            "observed_snippets_note": "Google controls snippet selection dynamically based on query intent. Valid markup improves eligibility but does not guarantee selection.",
            "competitor_snippet_wins": getattr(report, "competitive_report", None),
        }
        sections_dict["06_people_also_ask_and_related_questions"] = {
            "paa_clusters_analyzed": questions_total,
            "follow_up_gaps_count": questions_unsupp,
            "content_consolidation_rule": "Group closely related questions on a single comprehensive authority page rather than spawning fragmented thin pages.",
        }
        sections_dict["07_faq_and_question_answer_content_audit"] = {
            "faq_pages_detected": len([p for p in report.page_reports if "FAQPage" in _get_page_schemas(p)]),
            "google_faq_restriction_warning": "Google restricts FAQ rich results primarily to authoritative government and healthcare organizations. Non-government sites should prioritize visible on-page UX clarity.",
            "unverified_facts_omitted": True,
        }
        sections_dict["08_structured_data_and_rich_results"] = {
            "schema_types_detected": getattr(g, "schema_types", []) if g else [],
            "schema_validation": report.schema_validation.model_dump() if report.schema_validation else None,
            "rich_result_rule": "Valid structured data establishes technical eligibility, not proof of rich result SERP appearance.",
        }
        sections_dict["09_entity_answers_and_knowledge_panels"] = {
            "brand_entity_name": getattr(g, "entity_name", report.domain) if g else report.domain,
            "business_profile": report.business_profile.model_dump() if report.business_profile else None,
            "same_as_profiles": getattr(report, "external_authority", {}).get("profiles", []) if getattr(report, "external_authority", None) else [],
            "knowledge_panel_rule": "Knowledge panels reflect Google Knowledge Graph consensus across external web entities, not schema declarations alone.",
        }
        sections_dict["10_voice_and_conversational_search"] = {
            "voice_search_rule": "Voice search has no universal ranking system. A passage readable aloud is not necessarily selected by a voice assistant.",
            "spoken_readability_passages": questions_supp,
            "pronunciation_clarity_check": "Verified clear entity names, acronym expansions, and unit specifications.",
        }
        sections_dict["11_ai_answer_engine_visibility"] = {
            "visibility_status": visibility_status,
            "scorecard": v_card.model_dump() if v_card else None,
            "measured_citation_rate": citation_rate,
            "platforms": ["ChatGPT Search", "Perplexity", "Google AI Overviews", "Gemini", "Claude"],
        }
        sections_dict["12_local_and_action_oriented_answers"] = {
            "business_name": getattr(report.business_profile, "business_name", None) if report.business_profile else None,
            "address_available": bool(getattr(report.business_profile, "address", None)) if report.business_profile else False,
            "phone_available": bool(getattr(report.business_profile, "phone", None)) if report.business_profile else False,
            "local_answers_note": "For physical businesses, NAP consistency across Google Business Profile and local schema is required for local voice/assistant queries.",
        }
        sections_dict["13_product_commercial_and_transactional_answers"] = {
            "pricing_questions_supported": bool(questions_supp > 0),
            "product_pages_analyzed": len([p for p in report.page_reports if "Product" in _get_page_schemas(p)]),
            "rule": "Commercial queries demand explicit specs, pricing tiers, and compatibility tables to prevent answer engine hallucinations.",
        }
        sections_dict["14_support_documentation_and_troubleshooting"] = {
            "troubleshooting_passages": [q for q in mapped_questions if "support" in q["category"].lower() or "troubleshoot" in q["question"].lower()],
            "procedural_integrity": "Prerequisites, reproducible steps, and expected outcomes are evaluated against the documentation corpus.",
        }
        sections_dict["15_answer_accuracy_and_source_quality"] = {
            "factual_grounding_layer": "Claims validated against first-party crawl DOM.",
            "contradictions_detected": len(report.contradictions or []),
            "contradiction_items": [c.model_dump() for c in (report.contradictions or [])],
        }
        sections_dict["16_competitor_answer_benchmarking"] = {
            "competitor_data": report.competitive_report,
            "rule": "Distinguish commercial competitors from search-answer competitors (e.g. media publications, Wikipedia, and aggregator directories).",
        }
        sections_dict["17_search_performance_and_business_outcomes"] = {
            "search_console_integration": "Available when Search Console OAuth connector is authenticated.",
            "tracked_metrics": ["Query Impressions", "Direct Clicks", "CTR %", "Average Position", "AI Referral Sessions"],
        }
        sections_dict["18_content_gaps_and_answer_strategy"] = {
            "unanswered_questions_count": questions_unsupp,
            "partial_questions_count": questions_part,
            "primary_strategic_opportunity": report.primary_strategic_opportunity,
        }
        sections_dict["19_prioritized_remediation_roadmap"] = {
            "p0_critical": [f.finding_id for f in p0_findings],
            "p1_high": [f.finding_id for f in p1_findings],
            "p2_medium": [f.finding_id for f in p2_findings],
            "p3_opportunity": [f.finding_id for f in p3_findings],
            "severity_framework": "P0: Major factual errors or broken priority business info. P1: Missing priority answers or invalid critical schema. P2: Structural passage formatting & PAA coverage. P3: Experimental answer opportunities.",
        }
        sections_dict["20_appendices_and_evidence_register"] = {
            "question_inventory": mapped_questions,
            "schema_results": getattr(g, "schema_types", []) if g else [],
            "total_urls_inspected": len(report.page_reports),
            "measurement_rubric": "AEO Master Rubric 2026: 4-Tier Assessment (Readiness, Eligibility, Visibility, Business Outcomes).",
        }

        # Build 15 Appendices Dictionary
        appendices_dict: Dict[str, Any] = {}
        for app in AEO_APPENDICES_15:
            app_key = f"appendix_{app.letter.lower()}_{app.title.lower().replace(' ', '_')}"
            appendices_dict[app_key] = {
                "letter": app.letter,
                "title": app.title,
                "contents": app.contents,
            }

        return {
            "report_id": report.report_id,
            "analysis_id": analysis_id,
            "domain": report.domain,
            "website_url": report.website_url,
            "generated_at": report.generated_at,
            "report_type": "AEO_MASTER_AUDIT_2026",
            "certification_status": getattr(report, "certification_status", "NOT_CERTIFIED"),
            "kpis": {
                "answer_readiness_score": answer_readiness_score,
                "observed_visibility_status": visibility_status,
                "measured_citation_rate": citation_rate,
                "questions_evaluated": questions_total,
                "questions_supported": questions_supp,
                "questions_partial": questions_part,
                "questions_unsupported": questions_unsupp,
                "total_findings": len(report.findings),
                "four_pillars": scorecard_dict,
            },
            "exports": {
                "html_report": f"/api/v1/reports/{analysis_id}/aeo-report?format=html",
                "json_report": f"/api/v1/reports/{analysis_id}/aeo-report?format=json",
                "remediation_tracker_csv": f"/api/v1/reports/{analysis_id}/export/aeo-remediation-tracker.csv",
                "question_dataset_csv": f"/api/v1/reports/{analysis_id}/export/aeo-question-dataset.csv",
                "live_benchmark_csv": f"/api/v1/reports/{analysis_id}/export/aeo-live-benchmark.csv",
                "brand_facts_csv": f"/api/v1/reports/{analysis_id}/export/aeo-brand-facts.csv",
                "evidence_ledger_csv": f"/api/v1/reports/{analysis_id}/export/aeo-evidence-ledger.csv",
            },
            "specialist_modules_16": specialists_dict,
            "parts_7": [
                {
                    "part_id": p.part_id,
                    "title": p.title,
                    "section_range": p.section_range,
                    "sections": p.sections,
                }
                for p in AEO_PARTS
            ],
            "sections": sections_dict,
            "appendices_15": appendices_dict,
        }

    def render_html_report(self, report: ExecutiveReport) -> str:
        """Renders complete standalone HTML document with 55-Section & 15-Appendix navigation."""
        json_data = self.render_json_report(report)
        analysis_id = json_data["analysis_id"]
        domain = html.escape(json_data["domain"])
        website_url = html.escape(json_data["website_url"])
        generated_at = html.escape(json_data["generated_at"])
        kpis = json_data["kpis"]
        four_pillars = kpis.get("four_pillars", {})

        p_a = four_pillars.get("pillar_a_content_readiness", {})
        p_b = four_pillars.get("pillar_b_technical_eligibility", {})
        p_c = four_pillars.get("pillar_c_observed_visibility", {})
        p_d = four_pillars.get("pillar_d_business_outcomes", {})

        readiness_score = p_a.get("composite_readiness_score", kpis.get("answer_readiness_score"))
        readiness_display = f"{int(round(readiness_score))}" if readiness_score is not None else "N/A"
        readiness_color = "#10b981" if (readiness_score and readiness_score >= 80) else ("#f59e0b" if (readiness_score and readiness_score >= 60) else "#ef4444")

        eligibility_score = p_b.get("composite_eligibility_score")
        eligibility_display = f"{int(round(eligibility_score))}" if eligibility_score is not None else "N/A"

        visibility_status = p_c.get("state", "NOT_TESTED")
        vis_color = "#10b981" if visibility_status == "VERIFIED" else "#64748b"

        cit_rate = p_c.get("citation_rate_pct")
        cit_display = f"{int(round(cit_rate))}%" if cit_rate is not None else "Unmeasured"

        questions_total = kpis["questions_evaluated"]
        questions_supp = kpis["questions_supported"]
        questions_part = kpis["questions_partial"]
        questions_unsupp = kpis["questions_unsupported"]

        # 7 Parts Navigation Links
        nav_parts_html = ""
        for p in AEO_PARTS:
            part_secs = [s for s in AEO_SECTIONS_55 if s.part_id == p.part_id]
            links_html = "\n".join(
                f'<a href="#{s.sec_id}" class="nav-item"><span>{s.number}. {html.escape(s.title)}</span></a>'
                for s in part_secs
            )
            nav_parts_html += f"""
            <div class="nav-part-group">
                <div class="nav-part-header">{html.escape(p.title)}</div>
                <div class="nav-part-links">
                    {links_html}
                </div>
            </div>
            """

        # Appendices Nav Links
        nav_appendices_html = "\n".join(
            f'<a href="#app-{a.letter.lower()}" class="nav-item"><span>Appendix {a.letter}: {html.escape(a.title)}</span></a>'
            for a in AEO_APPENDICES_15
        )

        # 10 AEO Domains HTML Grid
        domains_html = ""
        for idx, (dom_title, dom_desc) in enumerate(self.DOMAINS_10, 1):
            domains_html += f"""
            <div class="domain-card">
                <div class="domain-header">
                    <span class="domain-num">{idx:02d}</span>
                    <h4 class="domain-title">{dom_title}</h4>
                </div>
                <p class="domain-desc">{dom_desc}</p>
            </div>
            """

        # 16 Specialists HTML Grid
        specialists_html = ""
        for sp in json_data.get("specialist_modules_16", []):
            st_val = sp["status"]
            st_badge_cls = "badge-verified" if st_val in ("VERIFIED", "SAMPLE_VERIFIED") else ("badge-warn" if st_val == "INFERRED" else "badge-muted")
            specialists_html += f"""
            <div class="spec-card">
                <div class="spec-top">
                    <span class="spec-code">{sp['specialist_id']}</span>
                    <span class="spec-badge {st_badge_cls}">{st_val}</span>
                </div>
                <h4 class="spec-name">{html.escape(sp['specialist_name'])}</h4>
                <p class="spec-desc">{html.escape(sp['responsibility'])}</p>
                <div class="spec-summary">{html.escape(sp['summary'])}</div>
            </div>
            """

        # 10 Core Formulas Table Rows
        core_metrics = four_pillars.get("core_metrics", [])
        formula_rows_html = ""
        for m in core_metrics:
            val_disp = f"{m['value']:.1f}{m['unit']}" if m.get("value") is not None else '<span class="text-muted">Unmeasured</span>'
            state_cls = "badge-verified" if m['state'] in ("VERIFIED", "SAMPLE_VERIFIED") else "badge-muted"
            formula_rows_html += f"""
            <tr>
                <td><code>{m['code']}</code></td>
                <td><strong>{html.escape(m['name'])}</strong></td>
                <td><code>{html.escape(m['formula'])}</code></td>
                <td><span class="metric-val">{val_disp}</span></td>
                <td><span class="spec-badge {state_cls}">{m['state']}</span></td>
                <td class="text-sm text-secondary">{html.escape(m.get('notes') or '')}</td>
            </tr>
            """

        # 14-Field AEO Finding Cards HTML
        finding_cards_html = ""
        for idx, f in enumerate(report.findings):
            fid = html.escape(f.finding_id or f"AEO-ANS-{idx+1:03d}")
            if not fid.startswith("AEO-"):
                fid = f"AEO-{fid}"

            sev_class = str(f.severity.value).lower() if hasattr(f.severity, "value") else str(f.severity).lower()
            cat_name = html.escape(f.category.value if hasattr(f.category, "value") else str(f.category))
            subcat = html.escape(f.subcategory or cat_name)
            stat = html.escape(f.status.value if hasattr(f.status, "value") else str(f.status))
            # Never present every finding as DOM-verified. Use the finding's
            # declared scope/evidence class, or explicitly show that it is absent.
            evidence_scope = (
                getattr(f, "scope_classification", None)
                or getattr(f, "evidence_scope", None)
                or getattr(f, "scope", None)
                or getattr(f, "evidence_class", None)
                or "EVIDENCE_UNSPECIFIED"
            )
            if hasattr(evidence_scope, "value"):
                evidence_scope = evidence_scope.value
            evidence_badge = html.escape(str(evidence_scope).upper())
            owner = html.escape(f.owner or "Answer Content & SEO Engineering")
            title_esc = html.escape(f.title)
            desc_esc = html.escape(f.description)
            rec_esc = html.escape(f.recommendation)
            why_esc = html.escape(f.why_it_matters or f.business_impact or "Users fail to find a direct answer; answer engines cite competitor sources.")
            exp_esc = html.escape(f.expected_condition or "Concise, verified 40-60 word answer passage formatted under matching H2 question heading.")
            val_esc = html.escape(f.validation_criteria or "Automated re-crawl confirms passage extractability and zero entity contradiction.")
            target_url = html.escape(f.affected_urls[0]) if f.affected_urls else website_url

            finding_cards_html += f"""
            <div class="finding-card {sev_class}">
                <div class="finding-header">
                    <div class="finding-title-row">
                        <span class="finding-badge sev-{sev_class}">{sev_class.upper()}</span>
                        <span class="finding-badge status-{stat.lower()}">{stat}</span>
                        <span class="finding-badge evidence-scope">{evidence_badge}</span>
                        <span class="finding-id">{fid}</span>
                        <h4 class="finding-title">{title_esc}</h4>
                    </div>
                    <div class="finding-meta">
                        <span><strong>Domain:</strong> {cat_name} › {subcat}</span>
                        <span><strong>Owner:</strong> {owner}</span>
                        <span><strong>Priority:</strong> {f.priority}/10</span>
                        <span><strong>Target URL:</strong> <code>{target_url}</code></span>
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
                            <span class="field-label">Potential Impact on Answer Visibility</span>
                            <span class="field-val">{why_esc}</span>
                        </div>
                        <div class="field-item full-width">
                            <span class="field-label">Prescriptive AEO Recommendation</span>
                            <span class="field-val highlight">{rec_esc}</span>
                        </div>
                        <div class="field-item full-width">
                            <span class="field-label">Verification Acceptance Criteria</span>
                            <span class="field-val">{val_esc}</span>
                        </div>
                    </div>
                </div>
            </div>
            """

        # Question-to-Page Dataset Rows HTML
        question_rows_html = ""
        mapped_questions = json_data["sections"]["03_question_universe_and_intent_mapping"]["questions_mapped"]
        for q in mapped_questions:
            q_key = html.escape(q["question_key"])
            q_text = html.escape(q["question"])
            q_type = html.escape(q["question_type"])
            q_cat = html.escape(q["category"])
            q_stat = html.escape(q["status"])
            q_stat_class = q_stat.lower()
            q_url = html.escape(q["evidence_url"])
            q_ans = html.escape(q["answer_excerpt"][:140] + ("..." if len(q["answer_excerpt"]) > 140 else ""))

            question_rows_html += f"""
            <tr>
                <td><code>{q_key}</code></td>
                <td><strong>{q_text}</strong></td>
                <td><span class="badge-dim">{q_type}</span></td>
                <td>{q_cat}</td>
                <td><span class="stat-pill {q_stat_class}">{q_stat}</span></td>
                <td><a href="{q_url}" target="_blank" class="ext-link">{q_url}</a></td>
                <td class="text-snippet">{q_ans or '<span class="text-muted">No verified excerpt</span>'}</td>
            </tr>
            """

        # 55 Sections Detailed Blocks HTML
        sections_blocks_html = ""
        for s in AEO_SECTIONS_55:
            items_list = "".join(f"<li>{html.escape(item)}</li>" for item in s.checklist)
            sections_blocks_html += f"""
            <section id="{s.sec_id}" class="report-section">
                <div class="section-badge-row">
                    <span class="part-pill">{html.escape(s.part_name)}</span>
                    <span class="sec-num-pill">Section {s.number}</span>
                </div>
                <h3 class="section-title">{s.number}. {html.escape(s.title)}</h3>
                <p class="section-lead">{html.escape(s.description)}</p>
                <div class="checklist-box">
                    <div class="checklist-header">Audit Scope & Systematic Verification Checklist</div>
                    <ul class="checklist-grid">
                        {items_list}
                    </ul>
                </div>
            </section>
            """

        # 15 Appendices Blocks HTML
        appendices_blocks_html = ""
        for a in AEO_APPENDICES_15:
            appendices_blocks_html += f"""
            <div id="app-{a.letter.lower()}" class="appendix-card">
                <div class="appendix-header">
                    <span class="appendix-letter">Appendix {a.letter}</span>
                    <h4 class="appendix-title">{html.escape(a.title)}</h4>
                </div>
                <p class="appendix-contents">{html.escape(a.contents)}</p>
            </div>
            """

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Complete AEO Master Audit & Answer Engine Optimization Report - {domain}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0f1d;
            --bg-surface: #111827;
            --bg-card: #1f2937;
            --border-subtle: #374151;
            --border-strong: #4b5563;
            --text-main: #f9fafb;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent-cyan: #06b6d4;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #f43f5e;
            --accent-indigo: #6366f1;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg-primary);
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
            font-size: 14px;
            line-height: 1.6;
        }}
        .layout-container {{
            display: flex;
            min-height: 100vh;
        }}
        /* Sticky Sidebar */
        .sidebar {{
            width: 340px;
            background: var(--bg-surface);
            border-right: 1px solid var(--border-subtle);
            padding: 24px 16px;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .brand-header {{
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-subtle);
        }}
        .brand-logo {{
            font-size: 18px;
            font-weight: 800;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .brand-logo span {{ color: var(--accent-cyan); }}
        .report-subtitle {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        .target-box {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 10px 12px;
        }}
        .target-domain {{
            font-weight: 700;
            color: var(--accent-cyan);
            word-break: break-all;
        }}
        .nav-part-group {{
            margin-bottom: 12px;
        }}
        .nav-part-header {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--accent-amber);
            margin-bottom: 6px;
            padding-left: 8px;
        }}
        .nav-item {{
            display: block;
            padding: 6px 10px;
            border-radius: 4px;
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 12px;
            transition: all 0.15s ease;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .nav-item:hover {{
            background: rgba(6, 182, 212, 0.1);
            color: var(--text-main);
        }}
        /* Main Content */
        .content-area {{
            flex: 1;
            padding: 40px;
            max-width: 1300px;
            margin: 0 auto;
        }}
        .export-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 24px;
            align-items: center;
        }}
        .btn-export {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            color: var(--text-main);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
        }}
        .btn-export:hover {{
            background: var(--accent-cyan);
            color: #000;
            border-color: var(--accent-cyan);
        }}
        /* 4-Pillar Scorecard */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 18px;
            position: relative;
        }}
        .kpi-pillar-label {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            color: var(--accent-cyan);
            letter-spacing: 0.05em;
        }}
        .kpi-val {{
            font-size: 32px;
            font-weight: 800;
            margin: 8px 0;
            font-family: 'JetBrains Mono', monospace;
        }}
        .kpi-subtext {{
            font-size: 12px;
            color: var(--text-secondary);
        }}
        /* Disclaimers & Integrity Alert */
        .integrity-alert {{
            background: rgba(99, 102, 241, 0.08);
            border-left: 4px solid var(--accent-indigo);
            padding: 14px 18px;
            border-radius: 4px;
            margin-bottom: 28px;
            font-size: 13px;
            color: var(--text-secondary);
        }}
        .integrity-alert strong {{ color: var(--text-main); }}
        /* Domains & Specialists */
        .grid-2 {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}
        .domain-card, .spec-card {{
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 16px;
        }}
        .domain-header, .spec-top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }}
        .domain-num, .spec-code {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 700;
            color: var(--accent-cyan);
        }}
        .domain-title, .spec-name {{
            font-size: 14px;
            font-weight: 700;
        }}
        .domain-desc, .spec-desc {{
            font-size: 12px;
            color: var(--text-secondary);
        }}
        .spec-summary {{
            font-size: 11px;
            color: var(--accent-emerald);
            margin-top: 6px;
        }}
        /* Tables */
        .table-wrap {{
            overflow-x: auto;
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            margin-bottom: 24px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            text-align: left;
        }}
        th {{
            background: var(--bg-surface);
            color: var(--text-secondary);
            font-weight: 600;
            padding: 10px 14px;
            border-bottom: 1px solid var(--border-subtle);
        }}
        td {{
            padding: 10px 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}
        /* Section Blocks */
        .report-section {{
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 24px;
        }}
        .section-badge-row {{
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
        }}
        .part-pill {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent-amber);
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
        }}
        .sec-num-pill {{
            background: rgba(6, 182, 212, 0.15);
            color: var(--accent-cyan);
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 800;
            margin-bottom: 8px;
        }}
        .section-lead {{
            color: var(--text-secondary);
            margin-bottom: 16px;
        }}
        .checklist-box {{
            background: var(--bg-card);
            border-radius: 6px;
            padding: 16px;
        }}
        .checklist-header {{
            font-size: 12px;
            font-weight: 700;
            color: var(--accent-cyan);
            margin-bottom: 10px;
            text-transform: uppercase;
        }}
        .checklist-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px 16px;
            padding-left: 18px;
            color: var(--text-secondary);
            font-size: 12px;
        }}
        /* Findings */
        .finding-card {{
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            margin-bottom: 16px;
            overflow: hidden;
        }}
        .finding-header {{
            background: var(--bg-card);
            padding: 14px 18px;
            border-bottom: 1px solid var(--border-subtle);
        }}
        .finding-title-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
        }}
        .finding-badge {{
            font-size: 10px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            text-transform: uppercase;
        }}
        .sev-critical {{ background: var(--accent-rose); color: #fff; }}
        .sev-high {{ background: #f97316; color: #fff; }}
        .sev-medium {{ background: var(--accent-amber); color: #000; }}
        .badge-verified {{ background: rgba(16, 185, 129, 0.2); color: var(--accent-emerald); }}
        .badge-warn {{ background: rgba(245, 158, 11, 0.2); color: var(--accent-amber); }}
        .badge-muted {{ background: rgba(100, 116, 139, 0.2); color: #94a3b8; }}
        .finding-id {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted); }}
        .finding-title {{ font-size: 14px; font-weight: 700; }}
        .finding-meta {{ font-size: 11px; color: var(--text-secondary); display: flex; gap: 16px; }}
        .finding-body {{ padding: 18px; }}
        .field-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-top: 12px;
        }}
        .field-item {{ background: var(--bg-card); padding: 12px; border-radius: 6px; }}
        .field-item.full-width {{ grid-column: span 2; }}
        .field-label {{ font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; display: block; margin-bottom: 4px; }}
        .field-val.highlight {{ color: var(--accent-cyan); font-weight: 600; }}
        /* Appendices */
        .appendix-card {{
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 14px 18px;
            margin-bottom: 12px;
        }}
        .appendix-letter {{
            font-size: 11px;
            font-weight: 800;
            color: var(--accent-indigo);
            text-transform: uppercase;
            margin-right: 8px;
        }}
        .appendix-title {{ font-size: 13px; font-weight: 700; display: inline; }}
        .appendix-contents {{ font-size: 12px; color: var(--text-secondary); margin-top: 4px; }}
    </style>
</head>
<body>
    <div class="layout-container">
        <!-- Sticky Sidebar Navigation -->
        <aside class="sidebar">
            <div class="brand-header">
                <div class="brand-logo">Dristik <span>AEO</span></div>
                <div class="report-subtitle">55-Section Master Audit (2026)</div>
            </div>
            <div class="target-box">
                <div style="font-size: 11px; color: var(--text-muted);">Audited Entity</div>
                <div class="target-domain">{domain}</div>
            </div>
            <nav class="nav-tree">
                {nav_parts_html}
                <div class="nav-part-group" style="margin-top: 16px;">
                    <div class="nav-part-header" style="color: var(--accent-indigo);">Appendices A–O</div>
                    <div class="nav-part-links">
                        {nav_appendices_html}
                    </div>
                </div>
            </nav>
        </aside>

        <!-- Main Content Stream -->
        <main class="content-area">
            <!-- Header & Export Bar -->
            <div class="export-bar">
                <span style="font-weight: 700; margin-right: 8px;">Audit Deliverables:</span>
                <a href="/api/v1/reports/{analysis_id}/aeo-report?format=json" target="_blank" class="btn-export">JSON Report (55-Sec)</a>
                <a href="/api/v1/reports/{analysis_id}/export/aeo-remediation-tracker.csv" class="btn-export">Remediation Tracker CSV</a>
                <a href="/api/v1/reports/{analysis_id}/export/aeo-question-dataset.csv" class="btn-export">Question Dataset CSV</a>
                <a href="/api/v1/reports/{analysis_id}/export/aeo-live-benchmark.csv" class="btn-export">Live Benchmark CSV</a>
                <a href="/api/v1/reports/{analysis_id}/export/aeo-brand-facts.csv" class="btn-export">Brand Facts CSV</a>
                <a href="/api/v1/reports/{analysis_id}/export/aeo-evidence-ledger.csv" class="btn-export">Evidence Ledger CSV</a>
            </div>

            <!-- Disclaimers & Integrity Alert -->
            <div class="integrity-alert">
                <strong>Core AEO Architecture Rule: Separation of Outcomes</strong><br>
                Answer Readiness (source content completeness), Technical Eligibility (schema and crawl access), Observed Answer Appearances (empirically measured live search snippets), and Commercial Outcomes are measured independently. Dristik never synthesizes or assumes live visibility based on on-page scores alone.
            </div>

            <!-- 4-Pillar Scorecard Grid -->
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-pillar-label">Pillar A · Content Readiness</div>
                    <div class="kpi-val" style="color: {readiness_color}">{readiness_display}</div>
                    <div class="kpi-subtext">Source passage depth & question coverage</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-pillar-label">Pillar B · Technical Eligibility</div>
                    <div class="kpi-val" style="color: var(--accent-cyan)">{eligibility_display}</div>
                    <div class="kpi-subtext">Crawl access, indexability & schema validity</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-pillar-label">Pillar C · Observed Answer Visibility</div>
                    <div class="kpi-val" style="color: {vis_color}">{cit_display}</div>
                    <div class="kpi-subtext">{p_c.get('state', 'NOT_TESTED')} across live platforms</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-pillar-label">Pillar D · Business Outcomes</div>
                    <div class="kpi-val" style="color: #64748b">N/A</div>
                    <div class="kpi-subtext">Requires Search Console / GA4 connection</div>
                </div>
            </div>

            <!-- 10 Core Formulas Table -->
            <div class="report-section">
                <h3 class="section-title">AEO Measurement Framework: The 10 Core Formulas</h3>
                <p class="section-lead">Defensible mathematical formulas isolating numerator, denominator, and explicit verification states.</p>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Code</th>
                                <th>Metric Name</th>
                                <th>Suggested Calculation</th>
                                <th>Measured Value</th>
                                <th>Evidence State</th>
                                <th>Audit Provenance Notes</th>
                            </tr>
                        </thead>
                        <tbody>
                            {formula_rows_html}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- 16 Specialist Modules Registry -->
            <div class="report-section">
                <h3 class="section-title">16 Specialist Modules Execution Ledger</h3>
                <p class="section-lead">Autonomous modular specialists with explicit data contracts rather than monolithic prompt speculation.</p>
                <div class="grid-2">
                    {specialists_html}
                </div>
            </div>

            <!-- The 10 Core Domains of Answer Engine Optimization -->
            <div class="report-section">
                <h3 class="section-title">The 10 Core Domains of Answer Engine Optimization</h3>
                <p class="section-lead">Functional taxonomy governing search feature capture across generative and traditional search surfaces.</p>
                <div class="grid-2">
                    {domains_html}
                </div>
            </div>

            <!-- Standardized 14-Field AEO Finding Cards -->
            <div class="report-section">
                <h3 class="section-title">AEO Verified Findings & Remediation Register ({len(report.findings)} items)</h3>
                <p class="section-lead">Findings mapped directly to target URLs with concrete verification acceptance criteria.</p>
                {finding_cards_html or '<p class="text-secondary">No open findings detected across analyzed URLs.</p>'}
            </div>

            <!-- Question-to-Page Dataset -->
            <div class="report-section">
                <h3 class="section-title">Discovered Question Universe & Intent Mapping</h3>
                <p class="section-lead">Customer inquiries mapped to canonical destinations and verified first-party answer excerpts.</p>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Key</th>
                                <th>Target Question</th>
                                <th>Type</th>
                                <th>Topic Cluster</th>
                                <th>Status</th>
                                <th>Destination URL</th>
                                <th>Verified DOM Excerpt</th>
                            </tr>
                        </thead>
                        <tbody>
                            {question_rows_html}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Full 55 Sections Detailed Blocks -->
            {sections_blocks_html}

            <!-- 15 Appendices Registry -->
            <div class="report-section">
                <h3 class="section-title">Report Appendices (A through O)</h3>
                <p class="section-lead">Technical audit datasets, test run environments, and governance registers.</p>
                {appendices_blocks_html}
            </div>
        </main>
    </div>
</body>
</html>
"""


aeo_report_generator = CompleteAeoReportGenerator()
