"""
Dristik AI Scoring Engine v5.0
Check-based, continuous metric curves, statistical Wilson sampling, and declarative JSON gates.
"""
from typing import List, Dict, Optional, Any, Tuple
import math
from app.domain.models import (
    Finding,
    CategoryScore,
    OverallScoreResult,
    BusinessProfile,
    CheckResult,
    LLMJudgeRecord,
    AuditScopeInfo,
    HonestScores
)
from app.domain.enums import Category, Severity, BusinessIntent, EvidenceClass
from app.domain.scoring.weights import compute_intent_adjusted_weights
from app.domain.scoring.config_v5 import load_scoring_rubric_v5, ScoringRubricV5
from app.domain.scoring.curves import log_normal_curve, wilson_interval, audience_readability_score
from app.orchestration.cognition.finding_registry import _canonical_id


_SEVERITY_RANK = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1}


def severity_rank(finding: Finding) -> int:
    """Rank severity by impact. Enum names are not alphabetical: MEDIUM would otherwise beat CRITICAL."""
    raw = finding.severity.value if hasattr(finding.severity, "value") else finding.severity
    return _SEVERITY_RANK.get(str(raw).upper(), 0)


def measured_category_score(cat_scores: Dict[str, CategoryScore], category: Category) -> Optional[float]:
    """Return a measured category score. Zero stays zero. Missing and NOT_MEASURED stay None."""
    cat = cat_scores.get(category.value)
    if cat is None or cat.score is None or getattr(cat, "status", "MEASURED") == "NOT_MEASURED":
        return None
    return float(cat.score)


def positive_query_count(value: Any) -> Optional[int]:
    """Live AI sample size. A missing or zero count is not a default of 18."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    count = int(value)
    return count if count > 0 else None


def weighted_mean(parts: List[Tuple[float, Optional[float]]]) -> Optional[float]:
    present = [(weight, score) for weight, score in parts if score is not None]
    if not present:
        return None
    total_weight = sum(weight for weight, _ in present)
    if total_weight <= 0:
        return None
    return round(sum(weight * score for weight, score in present) / total_weight, 1)


CHECK_KEYWORDS: Dict[str, List[str]] = {
    "robots_txt_rfc9309": ["robots.txt", "robots", "disallow"],
    "sitemap_urls_valid_200": ["sitemap", "xml sitemap"],
    "indexable_url_share": ["noindex", "index", "indexable", "5xx", "500", "503", "unindexable"],
    "internal_click_depth_ok": ["click depth", "crawl depth", "orphan"],
    "hreflang_tags_valid": ["hreflang", "x-default", "international"],
    "https_on_all_urls": ["https", "insecure http", "ssl"],
    "tls_version_valid": ["tls", "certificate", "ssl"],
    "http_to_https_single_301": ["redirect", "301", "http to https"],
    "no_mixed_content": ["mixed content"],
    "security_headers_hardening": ["hsts", "csp", "security headers"],
    "canonical_valid_rate": ["canonical", "self-referencing"],
    "redirect_chains_clean": ["redirect chain", "redirects", "hop"],
    "broken_internal_links_rate": ["broken", "404", "broken link", "dead link"],
    "duplicate_content_clusters": ["duplicate", "near-duplicate", "cosine"],
    "title_present": ["missing title", "title tag", "no title"],
    "title_length_bounds": ["title length", "title too long", "title too short", "exceeds", "title tag exceeds"],
    "title_uniqueness": ["duplicate title", "title duplicate", "unique title"],
    "title_h1_topic_semantic_match": ["title h1", "title mismatch"],
    "meta_desc_present": ["meta description", "missing description", "meta desc", "missing meta"],
    "meta_desc_length": ["description length"],
    "meta_desc_uniqueness": ["duplicate description"],
    "single_h1_present": ["h1", "missing h1", "multiple h1", "heading tag", "h1 tag"],
    "no_skipped_heading_levels": ["skipped", "heading level", "h2", "h3"],
    "h1_matches_title_intent": ["h1 intent", "h1 align"],
    "og_tags_present": ["og:", "opengraph", "open graph"],
    "twitter_card_present": ["twitter:card", "twitter card"],
    "og_image_dimensions_reachable": ["og:image", "og image"],
    "image_alt_text_rate": ["alt text", "alt attribute", "image alt"],
    "topical_entity_coverage": ["topical", "thin", "coverage", "commodity", "specifications", "entity schema"],
    "information_gain_score": ["information gain", "originality", "gain"],
    "supported_claim_rate": ["claim", "unbacked", "evidence", "proof", "unbacked claims", "superlative"],
    "author_byline_and_date": ["author", "byline", "date", "credentials"],
    "outline_depth_and_intent": ["outline", "intent set"],
    "cannibalization_freedom_rate": ["cannibalization", "keyword conflict", "duplicate metadata", "metadata", "duplicate", "duplicate content", "conflict"],
    "sentence_length_under_25": ["sentence length"],
    "paragraph_length_under_120": ["paragraph length"],
    "kg_wikidata_resolution": ["wikidata", "knowledge graph", "unresolved entity", "entity resolution", "entity clarity", "missing entity"],
    "sameas_link_reciprocity": ["sameas", "social link"],
    "brand_name_consistency": ["brand name", "name consistency", "naming"],
    "canonical_definition_top_100_words": ["canonical definition", "definition in top 100", "opening definition", "first 100 words", "service area definition", "definition"],
    "bayesian_review_rating": ["review", "rating", "backlink", "toxic backlink", "link graph", "referring domain", "authority"],
    "buyer_intent_answer_score": ["buyer question", "answerability", "icp question", "answer", "answer basic icp", "direct answer", "answer format", "structured answer"],
    "schema_dom_facts_match": ["schema dom", "schema mismatch", "text match"],
    "commercial_topics_concrete_rate": ["commercial", "pricing", "concrete", "commercial pricing", "engagement model"],
    "citation_ready_chunk_density": ["citation-ready", "passage density", "chunk", "entity schema"],
    "ai_search_bots_unblocked": ["searchbot", "bot blocked", "perplexitybot", "claudebot"],
    "raw_html_content_share": ["raw html", "javascript rendering", "client-side"],
    "org_schema_completeness": ["organization schema", "org schema", "organizationschema"],
    "org_schema_validity": ["schema syntax", "json-ld error"],
    "org_schema_id_linking": ["@id", "sameas link"],
    "website_schema_valid": ["website schema"],
    "breadcrumb_list_valid": ["breadcrumb"],
    "page_template_type_schema": ["product schema", "article schema", "software schema", "template schema", "product and offer", "product", "offer", "professionalservice"],
    "schema_truthfulness_rate": ["schema truthfulness", "contradicting schema"],
    "hero_clarity_rubric": ["value proposition", "hero clarity", "5-second"],
    "cta_above_the_fold": ["call to action", "primary cta", "cta above", "above the fold", "above fold", "add to cart", "cta", "phone number or call"],
    "cta_contrast_wcag": ["cta contrast", "button contrast"],
    "cta_verb_specific_label": ["cta label", "vague button", "verb", "action label"],
    "clicks_to_conversion_under_3": ["funnel", "clicks to conversion"],
    "form_labels_accessible": ["form label", "autocomplete"],
    "form_inline_validation": ["form validation", "error message"],
    "viewport_meta_declared": ["viewport meta"],
    "no_horizontal_scroll_360px": ["horizontal scroll", "overflow 360px"],
    "tap_target_dimensions_wcag": ["tap target"],
    "base_font_size_16px": ["font size", "base font"],
}


def _matches_check(check_id: str, finding: Finding) -> bool:
    cid_low = check_id.lower()
    fid_low = finding.finding_id.lower()
    if cid_low in fid_low:
        return True
    rule_id = getattr(finding, "rule_id", None)
    if rule_id and (cid_low in rule_id.lower() or rule_id.lower() in cid_low):
        return True
    title_low = finding.title.lower()
    desc_low = (finding.finding or finding.description or "").lower()
    keywords = CHECK_KEYWORDS.get(check_id, check_id.split("_"))
    return any(kw in title_low or kw in desc_low for kw in keywords)


class ScoringEngine:
    def __init__(self, rubric: Optional[ScoringRubricV5] = None):
        self.rubric = rubric or load_scoring_rubric_v5()

    def calculate_scores(
        self,
        findings: Optional[List[Finding]] = None,
        business_profile: Optional[BusinessProfile] = None,
        has_schema: Optional[bool] = None,
        is_https: Optional[bool] = None,
        readability: Optional[float] = None,
        external_authority_connected: bool = False,
        live_citation_score: Optional[float] = None,
        performance_metrics: Optional[Dict[str, float]] = None,
        plan_tier: str = "starter",
        audit_scope: Optional[AuditScopeInfo] = None,
        cwv_data: Optional[Dict[str, float]] = None,
        live_benchmark_data: Optional[Dict[str, Any]] = None,
        manifest: Optional[Any] = None,
        **kwargs: Any,
    ) -> OverallScoreResult:
        """
        Calculates category scores, subsection breakdowns, check results with evidence,
        and intent-adjusted overall score according to Scoring Rubric v5.0.
        """
        if findings is None:
            findings = kwargs.get("claims", [])
        intent = business_profile.primary_intent if business_profile else BusinessIntent.LEAD_GENERATION
        base_weights = compute_intent_adjusted_weights(intent)
        scope = audit_scope or AuditScopeInfo(plan_tier=plan_tier)

        # Map findings by canonical root cause to ensure single-charge deduplication
        seen_root_causes: Dict[str, str] = {}
        primary_findings: List[Finding] = []
        downstream_findings: List[Finding] = []

        for f in findings:
            rubric_conf = getattr(f, "confidence_rubric", None)
            if rubric_conf is not None and not rubric_conf.affects_score:
                continue
            if getattr(f, "held_from_executive", False) and not getattr(f, "adversarial_reviewed", False):
                continue

            cid = getattr(f, "root_cause_id", None) or getattr(f, "rule_id", None) or _canonical_id(f)
            cat_name = f.category.value if hasattr(f.category, "value") else str(f.category)
            if cid not in seen_root_causes:
                seen_root_causes[cid] = cat_name
                primary_findings.append(f)
            else:
                downstream_findings.append(f)

        # Performance / CWV defaults (CrUX field or lab fallback)
        cwv = cwv_data or performance_metrics or {}
        lcp_val = float(cwv["lcp"]) if "lcp" in cwv else None
        inp_val = float(cwv["inp"]) if "inp" in cwv else None
        cls_val = float(cwv["cls"]) if "cls" in cwv else None
        ttfb_val = float(cwv["ttfb"]) if "ttfb" in cwv else None

        # Check for catastrophic gate conditions
        has_sitewide_noindex = any(
            "noindex" in f.title.lower() or "noindex" in (f.finding or "").lower()
            for f in findings if f.category == Category.TECHNICAL_SEO and f.severity in (Severity.CRITICAL, Severity.HIGH)
        )
        has_disallow_all = any(
            "disallow: /" in f.title.lower() or "disallow all" in f.title.lower() or "blocks all" in f.title.lower()
            for f in findings if f.category == Category.TECHNICAL_SEO and f.severity in (Severity.CRITICAL, Severity.HIGH)
        )
        has_homepage_5xx = any(
            "500" in f.title or "503" in f.title or "5xx" in f.title.lower() or "server error" in f.title.lower()
            for f in findings if f.category == Category.TECHNICAL_SEO and f.severity == Severity.CRITICAL
        )
        has_contradicting_schema = any(
            "contradict" in f.title.lower() or "mismatch" in f.title.lower() or "false schema" in f.title.lower()
            for f in findings if f.category == Category.SCHEMA and f.severity in (Severity.CRITICAL, Severity.HIGH)
        )

        category_scores: Dict[str, CategoryScore] = {}
        category_status: Dict[str, str] = {}
        category_check_results: Dict[str, List[CheckResult]] = {}
        category_deductions_ui: Dict[str, List[Dict[str, Any]]] = {}

        # -------------------------------------------------------------
        # Evaluate checks per Category & Subsection
        # -------------------------------------------------------------
        for cat_enum in Category:
            cat_key = cat_enum.value
            cat_def = self.rubric.categories.get(cat_key)
            if not cat_def:
                continue

            subsections_breakdown: List[Dict[str, Any]] = []
            category_checks: List[CheckResult] = []
            cat_deductions: List[Dict[str, Any]] = []
            cat_strengths: List[str] = []
            cat_weaknesses: List[str] = []

            # Check if category has an unmeasured prerequisite gate
            is_unmeasured_by_gate = False
            unmeasured_reason = ""
            for gate in cat_def.gates:
                if gate.action == "MARK_NOT_MEASURED":
                    if gate.gate_id == "gate_ai_search_requires_live_run" and live_citation_score is None:
                        is_unmeasured_by_gate = True
                        unmeasured_reason = gate.reason
                        break
                    elif gate.gate_id == "gate_trust_requires_evidence" and not external_authority_connected:
                        # Check if any verified trust findings exist
                        has_trust_ev = any(
                            f.category == Category.TRUST_AUTHORITY
                            and getattr(f, "evidence_class", None) in (EvidenceClass.OBSERVED, EvidenceClass.EXTERNALLY_VERIFIED)
                            for f in findings
                        )
                        if not has_trust_ev:
                            is_unmeasured_by_gate = True
                            unmeasured_reason = "connector unavailable"
                            break

            if is_unmeasured_by_gate:
                unmeasured_breakdown = [
                    {
                        "component": sub_def.name,
                        "points_earned": 0.0,
                        "points_possible": sub_def.budget_share,
                        "status": "NOT_MEASURED",
                        "coverage": 0.0,
                        "provenance": "CONNECTOR_UNAVAILABLE"
                    }
                    for sub_def in cat_def.subsections.values()
                ]
                category_scores[cat_key] = CategoryScore(
                    category=cat_enum,
                    score=None,
                    confidence=0.0,
                    coverage=0.0,
                    weight=0.0,
                    weighted_score=0.0,
                    strengths=[],
                    weaknesses=[unmeasured_reason] if unmeasured_reason else ["Prerequisite connector not measured."],
                    summary=f"Not measured — {unmeasured_reason or 'prerequisite unavailable'}",
                    deductions=[],
                    formula_breakdown=unmeasured_breakdown,
                    check_results=[],
                    status="NOT_MEASURED",
                    provenance="CONNECTOR_UNAVAILABLE"
                )
                category_status[cat_key] = "NOT_MEASURED"
                category_check_results[cat_key] = []
                category_deductions_ui[cat_key] = []
                continue

            total_cat_budget = 0.0
            measured_cat_budget = 0.0
            weighted_subsection_sum = 0.0
            total_cat_weight_possible = 0.0
            total_cat_weight_measured = 0.0

            cat_primary_findings = [f for f in primary_findings if f.category == cat_enum]
            matched_findings_by_check: Dict[str, List[Finding]] = {}
            unmatched_findings = list(cat_primary_findings)
            for sub_k, s_def in cat_def.subsections.items():
                for c_def in s_def.checks:
                    matched = [f for f in cat_primary_findings if _matches_check(c_def.check_id, f)]
                    if matched:
                        matched_findings_by_check[c_def.check_id] = matched
                        for mf in matched:
                            if mf in unmatched_findings:
                                unmatched_findings.remove(mf)

            # If any primary findings for this category didn't match any check keywords,
            # attach them to the first graded or primary check in this category
            if unmatched_findings:
                fallback_cid = None
                for s_def in cat_def.subsections.values():
                    for c_def in s_def.checks:
                        if c_def.check_type == "graded":
                            fallback_cid = c_def.check_id
                            break
                        if fallback_cid is None:
                            fallback_cid = c_def.check_id
                    if fallback_cid:
                        break
                if fallback_cid:
                    matched_findings_by_check.setdefault(fallback_cid, []).extend(unmatched_findings)

            for sub_key, sub_def in cat_def.subsections.items():
                sub_budget = sub_def.budget_share
                total_cat_budget += sub_budget
                sub_weight_measured = 0.0
                sub_weight_total = 0.0
                sub_score_accum = 0.0

                for check_def in sub_def.checks:
                    cid = check_def.check_id
                    w = check_def.weight
                    sub_weight_total += w
                    total_cat_weight_possible += w

                    # Default check state
                    s = 1.0
                    passed = 1
                    failed = 0
                    sample_size = max(1, scope.measured_pages)
                    evidence_list: List[Dict[str, Any]] = []
                    status = "PASS"
                    is_measured = True
                    llm_judge = None

                    # Find findings targeting this check / category
                    check_findings = matched_findings_by_check.get(cid, [])


                    # Specific Check Value Evaluations
                    if cat_enum == Category.SCHEMA and has_schema is None:
                        is_measured = False
                        status = "NOT_MEASURED"
                        s = 0.0
                        passed = 0
                        failed = 0
                    elif cid == "robots_txt_rfc9309":
                        if manifest is not None and not getattr(manifest, "robots_txt_found", True):
                            s = 0.0
                            passed = 0
                            failed = sample_size
                            evidence_list.append({"url": "robots.txt", "status": "FAIL", "detail": "robots.txt file was not detected at domain root."})
                        elif check_findings:
                            s = 0.0
                            passed = 0
                            failed = sample_size
                            evidence_list.append({"url": "robots.txt", "status": "FAIL", "detail": check_findings[0].title})
                        else:
                            s = 1.0
                    elif cid == "sitemap_urls_valid_200":
                        if manifest is not None and not getattr(manifest, "sitemap_found", True):
                            site_size = len(manifest.pages) if getattr(manifest, "pages", None) else sample_size
                            if site_size <= 25:
                                s = 0.5
                                passed = int(round(s * sample_size))
                                failed = sample_size - passed
                                evidence_list.append({"url": "sitemap.xml", "status": "ADVISORY", "detail": "XML Sitemap not discovered; on small sites (<= 25 pages) with complete internal linking, impact is advisory."})
                            else:
                                s = 0.0
                                passed = 0
                                failed = sample_size
                                evidence_list.append({"url": "sitemap.xml", "status": "FAIL", "detail": "XML Sitemap is missing or unreferenced in robots.txt."})
                        elif check_findings:
                            top_f = max(check_findings, key=severity_rank)
                            s = 0.0 if top_f.severity in (Severity.CRITICAL, Severity.HIGH) else 0.5
                            passed = int(round(s * sample_size))
                            failed = sample_size - passed
                            evidence_list.append({"url": "sitemap.xml", "status": "FAIL", "detail": top_f.title})
                        else:
                            s = 1.0
                    elif cid == "https_on_all_urls":
                        if is_https is None:
                            is_measured = False
                            status = "NOT_MEASURED"
                        else:
                            s = 1.0 if is_https else 0.0
                            domain_lbl = getattr(business_profile, "domain", None) or getattr(business_profile, "business_name", "") or "homepage"
                            if is_https:
                                evidence_list.append({"url": domain_lbl, "status": "PASS", "detail": "All inspected pages served securely over HTTPS."})
                            else:
                                evidence_list.append({"url": domain_lbl, "status": "FAIL", "detail": "Homepage requested over insecure HTTP."})
                    elif cid == "tls_version_valid":
                        if is_https is None:
                            is_measured = False
                            status = "NOT_MEASURED"
                        else:
                            s = 1.0 if is_https else 0.0
                    elif cid == "security_headers_hardening":
                        hsts_finding = next((f for f in primary_findings if "hsts" in f.title.lower() or "hsts" in f.finding_id.lower()), None)
                        s = 0.5 if hsts_finding else 1.0
                        if hsts_finding:
                            evidence_list.append({"url": "response_headers", "status": "PARTIAL", "detail": "Strict-Transport-Security header absent."})
                    elif cid == "cwv_lcp":
                        if lcp_val is not None:
                            s = log_normal_curve(lcp_val, p10=check_def.p10 or 2.5, median=check_def.median or 4.0, higher_is_better=False)
                            evidence_list.append({"metric": "LCP", "value": f"{lcp_val:.2f}s", "status": "PASS" if s >= 0.75 else "FAIL"})
                        else:
                            is_measured = False
                    elif cid == "cwv_inp":
                        if inp_val is not None:
                            s = log_normal_curve(inp_val, p10=check_def.p10 or 200.0, median=check_def.median or 500.0, higher_is_better=False)
                        else:
                            is_measured = False
                    elif cid == "cwv_cls":
                        if cls_val is not None:
                            s = log_normal_curve(cls_val, p10=check_def.p10 or 0.10, median=check_def.median or 0.25, higher_is_better=False)
                        else:
                            is_measured = False
                    elif cid == "cwv_ttfb":
                        if ttfb_val is not None:
                            s = log_normal_curve(ttfb_val, p10=check_def.p10 or 0.8, median=check_def.median or 1.8, higher_is_better=False)
                        else:
                            is_measured = False
                    elif cid == "audience_flesch_reading_ease":
                        if readability is None or isinstance(readability, bool) or not isinstance(readability, (int, float)) or not math.isfinite(float(readability)):
                            is_measured = False
                            status = "NOT_MEASURED"
                        else:
                            s = audience_readability_score(readability, audience=getattr(business_profile, "target_audience", None) or "b2b")
                            evidence_list.append({"readability": readability, "status": "PASS" if s >= 0.7 else "PARTIAL"})
                    elif cid == "form_field_count_curve":
                        form_field_count = 3.0
                        for f in check_findings:
                            if "field" in f.title.lower():
                                form_field_count = 7.0
                        if form_field_count <= 3.0:
                            s = 1.0
                        else:
                            s = log_normal_curve(form_field_count, p10=3.0, median=8.0, higher_is_better=False)
                    elif cat_enum == Category.SCHEMA and not has_schema:
                        s = 0.0
                        passed = 0
                        failed = 1
                        evidence_list.append({"schema": "missing", "status": "FAIL", "detail": "No Schema.org types recorded in crawl sample."})
                    elif cid == "ai_brand_mention_rate":
                        if live_benchmark_data and "overall_mention_rate_pct" in live_benchmark_data:
                            sample_size = positive_query_count(live_benchmark_data.get("total_queries"))
                            if sample_size is None:
                                is_measured = False
                                status = "NOT_MEASURED"
                                s = 0.0
                                passed = 0
                                sample_size = 0
                            else:
                                s = min(1.0, max(0.0, float(live_benchmark_data["overall_mention_rate_pct"]) / 100.0))
                                passed = int(round(s * sample_size))
                                failed = sample_size - passed
                                _, low, high = wilson_interval(passed, sample_size)
                                evidence_list.append({
                                    "metric": "brand_mention_rate",
                                    "observed_rate": f"{s*100:.1f}%",
                                    "wilson_ci": [round(low, 3), round(high, 3)],
                                    "sample_size": sample_size,
                                    "status": "PASS" if s >= 0.6 else "PARTIAL",
                                    "detail": f"Observed brand mention rate: {s*100:.1f}% across {sample_size} engine queries."
                                })
                        elif live_citation_score is not None:
                            s = min(1.0, max(0.0, live_citation_score / 100.0))
                            sample_size = self.rubric.plans.get(plan_tier, self.rubric.plans["starter"]).ai_search_min_sample
                            passed = int(s * sample_size)
                            failed = sample_size - passed
                        else:
                            is_measured = False
                            status = "NOT_MEASURED"

                    elif cid == "ai_domain_citation_rate":
                        if live_benchmark_data and "overall_first_party_citation_rate_pct" in live_benchmark_data:
                            sample_size = positive_query_count(live_benchmark_data.get("total_queries"))
                            if sample_size is None:
                                is_measured = False
                                status = "NOT_MEASURED"
                                s = 0.0
                                passed = 0
                                sample_size = 0
                            else:
                                s = min(1.0, max(0.0, float(live_benchmark_data["overall_first_party_citation_rate_pct"]) / 100.0))
                                passed = int(round(s * sample_size))
                                failed = sample_size - passed
                                _, low, high = wilson_interval(passed, sample_size)
                                evidence_list.append({
                                    "metric": "domain_citation_rate",
                                    "observed_rate": f"{s*100:.1f}%",
                                    "wilson_ci": [round(low, 3), round(high, 3)],
                                    "sample_size": sample_size,
                                    "status": "PASS" if s >= 0.4 else "PARTIAL",
                                    "detail": f"Own-domain citation link rate: {s*100:.1f}% across {sample_size} queries."
                                })
                        elif live_citation_score is not None:
                            sample_size = self.rubric.plans.get(plan_tier, self.rubric.plans["starter"]).ai_search_min_sample
                            domain_finding = next((f for f in check_findings if "citation" in f.title.lower()), None)
                            if domain_finding:
                                s = 0.20 if domain_finding.severity in (Severity.CRITICAL, Severity.HIGH) else 0.50
                            else:
                                s = min(1.0, max(0.0, (live_citation_score * 0.7) / 100.0))
                            passed = int(round(s * sample_size))
                            failed = sample_size - passed
                            evidence_list.append({
                                "metric": "domain_citation_rate",
                                "status": "PASS" if s >= 0.5 else "PARTIAL",
                                "detail": f"Estimated domain citation rate: {s*100:.1f}%."
                            })
                        else:
                            is_measured = False
                            status = "NOT_MEASURED"

                    elif cid == "ai_displacement_resistance":
                        if live_benchmark_data and "share_of_model" in live_benchmark_data:
                            som = live_benchmark_data["share_of_model"]
                            total_q = positive_query_count(live_benchmark_data.get("total_queries"))
                            if total_q is None:
                                is_measured = False
                                status = "NOT_MEASURED"
                                sample_size = 0
                            else:
                                sample_size = total_q
                                displacements = som.get("competitor_displacements", [])
                                comp_only_rate = som.get("competitor_only_rate")
                                if comp_only_rate is not None:
                                    s = max(0.0, min(1.0, 1.0 - float(comp_only_rate)))
                                else:
                                    s = max(0.0, min(1.0, 1.0 - (len(displacements) / max(1, total_q))))
                                passed = int(round(s * sample_size))
                                failed = sample_size - passed
                                evidence_list.append({
                                    "metric": "displacement_resistance",
                                    "brand_presence": som.get("share_of_model_pct", 0.0),
                                    "displacements_count": len(displacements),
                                    "status": "PASS" if s >= 0.75 else "PARTIAL",
                                    "detail": f"Displacement resistance {s*100:.1f}% ({len(displacements)} competitor displacement events)."
                                })
                        elif check_findings:
                            top_f = max(check_findings, key=severity_rank)
                            s = 0.20 if top_f.severity in (Severity.CRITICAL, Severity.HIGH) else 0.50
                            passed = int(round(s * sample_size))
                            failed = sample_size - passed
                        elif live_citation_score is not None:
                            s = 0.70
                            sample_size = self.rubric.plans.get(plan_tier, self.rubric.plans["starter"]).ai_search_min_sample
                            passed = int(round(s * sample_size))
                            failed = sample_size - passed
                        else:
                            is_measured = False
                            status = "NOT_MEASURED"

                    elif cid == "ai_decision_stage_mention":
                        if live_benchmark_data and "share_of_model" in live_benchmark_data:
                            som = live_benchmark_data["share_of_model"]
                            dec_data = som.get("stage_breakdown", {}).get("decision", {})
                            dec_total = dec_data.get("total", 8)
                            dec_mentioned = dec_data.get("mentioned", 0)
                            sample_size = max(1, dec_total)
                            s = max(0.0, min(1.0, dec_mentioned / sample_size))
                            passed = dec_mentioned
                            failed = sample_size - passed
                            evidence_list.append({
                                "stage": "decision",
                                "total_decision_queries": sample_size,
                                "decision_mentions": dec_mentioned,
                                "status": "PASS" if s >= 0.6 else "PARTIAL",
                                "detail": f"Mentioned in {dec_mentioned}/{sample_size} high-intent decision prompts."
                            })
                        elif check_findings:
                            top_f = max(check_findings, key=severity_rank)
                            s = 0.20 if top_f.severity in (Severity.CRITICAL, Severity.HIGH) else 0.50
                            passed = int(round(s * sample_size))
                            failed = sample_size - passed
                        elif live_citation_score is not None:
                            s = min(1.0, max(0.0, (live_citation_score * 0.8) / 100.0))
                            sample_size = self.rubric.plans.get(plan_tier, self.rubric.plans["starter"]).ai_search_min_sample
                            passed = int(round(s * sample_size))
                            failed = sample_size - passed
                        else:
                            is_measured = False
                            status = "NOT_MEASURED"

                    elif cid == "ai_fact_precision_recall":
                        if live_benchmark_data and "ai_answer_diff" in live_benchmark_data:
                            diff_data = live_benchmark_data["ai_answer_diff"]
                            precision = diff_data.get("fact_precision")
                            if precision is not None:
                                s = max(0.0, min(1.0, float(precision)))
                                sample_size = diff_data.get("total_claims", 10)
                                passed = int(round(s * sample_size))
                                failed = sample_size - passed
                                evidence_list.append({
                                    "metric": "fact_precision",
                                    "verified_claims": diff_data.get("verified_claims", 0),
                                    "unverified_claims": diff_data.get("unverified_claims", 0),
                                    "contradictions": diff_data.get("contradictions", 0),
                                    "status": "PASS" if s >= 0.8 else "PARTIAL",
                                    "detail": f"Fact precision: {s*100:.1f}% across extracted claims."
                                })
                            else:
                                s = 0.70
                                sample_size = 10
                                passed = 7
                                failed = 3
                        elif check_findings:
                            top_f = max(check_findings, key=severity_rank)
                            s = 0.20 if top_f.severity in (Severity.CRITICAL, Severity.HIGH) else 0.60
                            passed = int(round(s * sample_size))
                            failed = sample_size - passed
                        elif live_citation_score is not None:
                            s = 0.65
                            sample_size = self.rubric.plans.get(plan_tier, self.rubric.plans["starter"]).ai_search_min_sample
                            passed = int(round(s * sample_size))
                            failed = sample_size - passed
                            evidence_list.append({
                                "detail": "Provisional fact recall based on live citation run."
                            })
                        else:
                            is_measured = False
                            status = "NOT_MEASURED"
                    else:
                        # Graded or Binary check evaluated against findings
                        if check_findings:
                            if check_def.check_type == "binary":
                                s = 0.0
                                passed = 0
                                failed = 1
                            elif check_def.check_type == "graded":
                                top_f = max(check_findings, key=severity_rank)
                                if top_f.severity == Severity.CRITICAL:
                                    s = 0.0
                                elif top_f.severity == Severity.HIGH:
                                    s = 0.20
                                elif top_f.severity == Severity.MEDIUM:
                                    s = 0.50
                                else:
                                    s = 0.80
                                passed = int(round(s * sample_size))
                                failed = sample_size - passed
                            else:
                                s = 0.30
                                passed = 0
                                failed = 1

                            for f in check_findings:
                                evidence_list.append({
                                    "url": f.evidence_refs[0] if f.evidence_refs else "crawl_sample",
                                    "status": "FAIL" if s < 0.5 else "PARTIAL",
                                    "detail": f.title
                                })
                        elif cat_enum == Category.AI_SEARCH and live_citation_score is None and not live_benchmark_data:
                            # CRITICAL INTEGRITY RULE: AI_SEARCH checks without live data or findings MUST NOT silently PASS!
                            is_measured = False
                            s = 0.0
                            passed = 0
                            failed = sample_size
                            status = "NOT_MEASURED"
                        else:
                            s = 1.0
                            passed = sample_size
                            failed = 0

                    if is_measured:
                        sub_weight_measured += w
                        total_cat_weight_measured += w
                        sub_score_accum += w * s

                    # Status & intervals. An unmeasured check stays unmeasured.
                    if not is_measured:
                        status = "NOT_MEASURED"
                        s = 0.0
                    elif s >= 0.75:
                        status = "PASS"
                    elif s >= 0.40:
                        status = "PARTIAL"
                    else:
                        status = "DEFICIT"

                    # Reconcile sample counts
                    if check_def.check_type == "binary":
                        passed = sample_size if s >= 0.5 else 0
                        failed = sample_size - passed
                    else:
                        passed = int(round(s * sample_size))
                        failed = sample_size - passed

                    ci = None
                    if sample_size > 1 or check_def.check_type == "graded":
                        _, low, high = wilson_interval(passed, sample_size)
                        ci = (low, high)

                    check_res = CheckResult(
                        check_id=cid,
                        name=check_def.name,
                        score=round(s, 3),
                        weight=w,
                        sample_size=sample_size,
                        passed=passed,
                        failed=failed,
                        coverage=1.0 if is_measured else 0.0,
                        status=status,
                        confidence_interval=ci,
                        evidence=evidence_list,
                        llm_judge=llm_judge,
                        methodology_version=self.rubric.methodology_version
                    )
                    category_checks.append(check_res)

                    if is_measured and s < 0.75:
                        if check_findings:
                            for idx, f in enumerate(check_findings):
                                pts = round(w * (1.0 - s), 1) if idx == 0 else 0.0
                                if pts <= 0.0:
                                    pts = round(max(0.5, w * (1.0 - s) / len(check_findings)), 1)
                                cat_deductions.append({
                                    "check_id": cid,
                                    "finding_id": f.finding_id,
                                    "title": f.title,
                                    "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                                    "points_lost": pts,
                                    "blocking": getattr(getattr(f, "calibrated_impact", None), "is_blocking", False),
                                    "why_it_matters": getattr(f, "why_it_matters", None) or f.description or check_def.description
                                })
                        else:
                            cat_deductions.append({
                                "check_id": cid,
                                "finding_id": f"chk_{cid}",
                                "title": check_def.name,
                                "severity": "CRITICAL" if s < 0.3 else ("HIGH" if s < 0.6 else "MEDIUM"),
                                "points_lost": round(w * (1.0 - s), 1),
                                "blocking": False,
                                "why_it_matters": check_def.description
                            })
                        cat_weaknesses.append(check_def.name)
                    elif is_measured:
                        cat_strengths.append(check_def.name)

                # Subsection Score. A subsection with no measured checks is omitted
                # from the category total. Missing Core Web Vitals are not a zero.
                if sub_weight_measured <= 0:
                    subsections_breakdown.append({
                        "component": sub_def.name,
                        "points_earned": 0.0,
                        "points_possible": sub_budget,
                        "status": "NOT_MEASURED",
                        "coverage": 0.0,
                        "provenance": "NOT_MEASURED",
                    })
                    continue
                sub_score = 100.0 * (sub_score_accum / sub_weight_measured)
                measured_cat_budget += sub_budget
                weighted_subsection_sum += (sub_budget / 100.0) * sub_score
                subsections_breakdown.append({
                    "component": sub_def.name,
                    "points_earned": round((sub_score / 100.0) * sub_budget, 1),
                    "points_possible": sub_budget,
                    "status": "PASS" if sub_score >= 75.0 else ("DEFICIT" if sub_score < 40.0 else "PARTIAL"),
                    "coverage": round(sub_weight_measured / sub_weight_total, 2) if sub_weight_total > 0 else 1.0,
                    "provenance": "MEASURED_DOM"
                })

            # Append downstream consequences without charging duplicate points
            for df in downstream_findings:
                if df.category == cat_enum:
                    cat_deductions.append({
                        "check_id": f"downstream_{_canonical_id(df)}",
                        "finding_id": df.finding_id,
                        "title": f"{df.title} (Downstream Consequence)",
                        "severity": df.severity.value,
                        "points_lost": 0.0,
                        "blocking": False,
                        "is_downstream_consequence": True,
                        "why_it_matters": getattr(df, "why_it_matters", None) or df.title
                    })

            raw_cat_score = (weighted_subsection_sum / (measured_cat_budget / 100.0)) if measured_cat_budget > 0 else 0.0
            cat_coverage = (total_cat_weight_measured / total_cat_weight_possible) if total_cat_weight_possible > 0 else 1.0

            # Dynamic Gates from JSON Rubric
            for gate in cat_def.gates:
                if gate.cap_score is not None:
                    trigger = False
                    if gate.gate_id == "gate_critical_indexation" and (has_sitewide_noindex or has_disallow_all or has_homepage_5xx):
                        trigger = True
                    elif gate.gate_id == "gate_schema_contradicts_visible" and has_contradicting_schema:
                        trigger = True

                    if trigger and raw_cat_score > gate.cap_score:
                        raw_cat_score = gate.cap_score
                        cat_weaknesses.insert(0, f"Score capped at {gate.cap_score:.0f} by gate: {gate.reason}")

            # Coverage threshold semantics: >= 60% MEASURED, 30-59.99% PARTIAL, <30% NOT_MEASURED
            if cat_coverage >= 0.60:
                cat_status = "MEASURED"
            elif cat_coverage >= 0.30:
                cat_status = "PARTIAL"
            else:
                cat_status = "NOT_MEASURED"

            summary = (
                f"{raw_cat_score:.0f}/100 based on {len(category_checks)} check evaluations. "
                f"Coverage: {cat_coverage*100:.0f}% ({cat_status})."
            )

            final_cat_score = round(raw_cat_score, 1) if cat_status != "NOT_MEASURED" else None

            if final_cat_score is not None and subsections_breakdown:
                scored_components = [comp for comp in subsections_breakdown if comp.get("status") != "NOT_MEASURED"]
                for comp in subsections_breakdown:
                    if comp.get("status") == "NOT_MEASURED":
                        comp["points_earned"] = 0.0
                total_earned = sum(comp["points_earned"] for comp in scored_components)
                total_possible = sum(comp["points_possible"] for comp in scored_components)
                # Measured rows are renormalized onto the 0-100 category scale.
                # An omitted subsection stays at 0 earned and is not given leftover points.
                if scored_components and total_possible > 0 and abs(final_cat_score - total_earned) > 0.05:
                    possible_scale = 100.0 / total_possible
                    running_possible = 0.0
                    running_earned = 0.0
                    for comp in scored_components[:-1]:
                        ratio = (comp["points_earned"] / comp["points_possible"]) if comp["points_possible"] else 0.0
                        comp["points_possible"] = round(comp["points_possible"] * possible_scale, 1)
                        comp["points_earned"] = min(comp["points_possible"], round(comp["points_possible"] * ratio, 1))
                        running_possible += comp["points_possible"]
                        running_earned += comp["points_earned"]
                    last = scored_components[-1]
                    last_ratio = (last["points_earned"] / last["points_possible"]) if last["points_possible"] else 0.0
                    last["points_possible"] = max(0.0, round(100.0 - running_possible, 1))
                    last["points_earned"] = min(last["points_possible"], round(last["points_possible"] * last_ratio, 1))
                    running_earned += last["points_earned"]
                    drift = round(final_cat_score - running_earned, 1)
                    if drift:
                        room = round(last["points_possible"] - last["points_earned"], 1)
                        applied = min(drift, room) if drift > 0 else drift
                        last["points_earned"] = max(0.0, round(last["points_earned"] + applied, 1))

            category_scores[cat_key] = CategoryScore(
                category=cat_enum,
                score=final_cat_score,
                confidence=round(min(0.95, 0.50 + 0.45 * cat_coverage), 2),
                coverage=round(cat_coverage, 2),
                score_interval=(round(max(0.0, raw_cat_score - 5.0), 1), round(min(100.0, raw_cat_score + 5.0), 1)),
                weight=0.0,  # Will be assigned during intent re-normalization
                weighted_score=0.0,
                strengths=cat_strengths[:3],
                weaknesses=cat_weaknesses[:4],
                summary=summary,
                deductions=cat_deductions,
                formula_breakdown=subsections_breakdown,
                check_results=category_checks,
                status=cat_status,
                provenance="EVIDENCE_CHECK_V5"
            )
            category_status[cat_key] = cat_status
            category_check_results[cat_key] = category_checks
            category_deductions_ui[cat_key] = cat_deductions

        # -------------------------------------------------------------
        # Category Weight Normalization (exclude NOT_MEASURED categories)
        # -------------------------------------------------------------
        active_cats = [
            cat for cat in Category
            if category_status.get(cat.value) in ("MEASURED", "PARTIAL")
        ]
        active_weights = compute_intent_adjusted_weights(intent, active_categories=active_cats)

        math_derivation = []
        overall_weighted_sum = 0.0

        for cat_enum in Category:
            cat_key = cat_enum.value
            c_score = category_scores.get(cat_key)
            if not c_score:
                continue

            if cat_enum in active_weights:
                norm_w = active_weights[cat_enum]
                c_score.weight = round(norm_w, 4)
                c_score.weighted_score = round((c_score.score or 0.0) * norm_w, 2)
                overall_weighted_sum += c_score.weighted_score
                math_derivation.append({
                    "category": cat_key,
                    "category_label": cat_key.replace("_", " ").title(),
                    "raw_score": c_score.score,
                    "weight_pct": round(norm_w * 100.0, 1),
                    "weight": round(norm_w, 4),
                    "weighted_points": c_score.weighted_score,
                    "coverage": c_score.coverage,
                    "status": c_score.status
                })
            else:
                c_score.weight = 0.0
                c_score.weighted_score = 0.0
                math_derivation.append({
                    "category": cat_key,
                    "category_label": cat_key.replace("_", " ").title(),
                    "raw_score": "Not measured",
                    "weight_pct": 0.0,
                    "weight": 0.0,
                    "weighted_points": 0.0,
                    "coverage": c_score.coverage,
                    "status": "NOT_MEASURED"
                })

        overall_score = round(max(0.0, min(100.0, overall_weighted_sum)), 1)

        if overall_score >= 93:
            grade, health = "A+", "Exceptional"
        elif overall_score >= 85:
            grade, health = "A", "Excellent"
        elif overall_score >= 75:
            grade, health = "B", "Good"
        elif overall_score >= 65:
            grade, health = "C", "Moderate"
        elif overall_score >= 50:
            grade, health = "D", "Needs Attention"
        else:
            grade, health = "F", "Low readiness"

        # Evidence coverage across findings
        total_f = len(findings)
        ev_cov = round(sum(1 for f in findings if f.evidence_refs) / total_f, 2) if total_f > 0 else 0.0
        measured_confidence = (
            sum(
                active_weights[cat] * float(category_scores[cat.value].confidence or 0.0)
                for cat in active_cats
                if cat in active_weights and cat.value in category_scores
            )
            if active_weights else 0.0
        )

        return OverallScoreResult(
            overall_score=overall_score,
            overall_confidence=round(measured_confidence, 2),
            evidence_coverage=ev_cov,
            grade=grade,
            health_label=health,
            category_scores=category_scores,
            intent_adjusted_weights={k.value: round(v, 4) for k, v in active_weights.items()},
            mathematical_derivation=math_derivation
        )

    def apply_measured_geo_score(self, scores: Optional[OverallScoreResult], extractability: Optional[float]) -> Optional[OverallScoreResult]:
        """Replace a rubric GEO score with the measured extractability composite.

        GEO checks with no matching findings take a perfect pass. That pass is not
        a measurement. Extractability is the measured GEO number, so the category
        score and its points in the overall follow that composite.
        """
        if scores is None or extractability is None:
            return scores
        try:
            value = float(extractability)
        except (TypeError, ValueError):
            return scores
        if value != value:
            return scores
        value = max(0.0, min(100.0, value))
        geo = scores.category_scores.get(Category.GEO.value)
        if geo is None or geo.score is None:
            return scores

        weight = float(geo.weight or 0.0)
        fraction = weight / 100.0 if weight > 1.5 else weight
        old_points = float(geo.weighted_score) if geo.weighted_score is not None else round(float(geo.score) * fraction, 2)
        new_points = round(value * fraction, 2)
        geo.score = round(value, 1)
        geo.weighted_score = new_points
        geo.status = "MEASURED"
        geo.provenance = "GEO_EXTRACTABILITY"
        geo.summary = (
            f"{geo.score:.0f}/100 from the measured extractability composite. "
            "Rubric checks with no matching findings are not a perfect score."
        )
        scores.overall_score = round(max(0.0, min(100.0, float(scores.overall_score or 0.0) - old_points + new_points)), 1)
        overall_score = scores.overall_score
        if overall_score >= 93:
            grade, health = "A+", "Exceptional"
        elif overall_score >= 85:
            grade, health = "A", "Excellent"
        elif overall_score >= 75:
            grade, health = "B", "Good"
        elif overall_score >= 65:
            grade, health = "C", "Moderate"
        elif overall_score >= 50:
            grade, health = "D", "Needs Attention"
        else:
            grade, health = "F", "Low readiness"
        scores.grade = grade
        scores.health_label = health
        for row in scores.mathematical_derivation or []:
            if row.get("category") == Category.GEO.value:
                row["raw_score"] = geo.score
                row["weighted_points"] = new_points
                row["status"] = "MEASURED"
                row["provenance"] = "GEO_EXTRACTABILITY"
        return scores

    def calculate_honest_scores(
        self,
        findings: List[Finding],
        business_profile: BusinessProfile,
        commercial_evals: Optional[List[Any]] = None,
        has_schema: Optional[bool] = None,
        is_https: Optional[bool] = None,
        readability: Optional[float] = None,
        geo_readiness: Optional[Any] = None,
        live_citation_score: Optional[float] = None,
        performance_metrics: Optional[Dict[str, float]] = None,
        plan_tier: str = "starter",
        live_benchmark_data: Optional[Dict[str, Any]] = None,
        external_authority_connected: bool = False,
    ) -> HonestScores:
        """
        Specialized Views:
        Grounded directly in the check results and category scores from v5.0 check engine.
        No separate conflicting deduction tables!
        """
        scores_res = self.calculate_scores(
            findings=findings,
            business_profile=business_profile,
            has_schema=has_schema,
            is_https=is_https,
            readability=readability,
            external_authority_connected=external_authority_connected,
            live_citation_score=live_citation_score,
            live_benchmark_data=live_benchmark_data,
            performance_metrics=performance_metrics,
            plan_tier=plan_tier
        )
        extractability = getattr(geo_readiness, "extractability_score", None) if geo_readiness is not None else None
        if extractability is not None:
            self.apply_measured_geo_score(scores_res, extractability)

        cat_scores = scores_res.category_scores
        ux_score = measured_category_score(cat_scores, Category.UX_CONVERSION)
        content_score = measured_category_score(cat_scores, Category.CONTENT)
        tech_score = measured_category_score(cat_scores, Category.TECHNICAL_SEO)
        onpage_score = measured_category_score(cat_scores, Category.ON_PAGE_SEO)
        schema_score = measured_category_score(cat_scores, Category.SCHEMA)
        geo_score = measured_category_score(cat_scores, Category.GEO)

        # Human View: UX & Conversion (50%) + Content (50%). Unmeasured inputs are left out.
        human_score = weighted_mean([(0.50, ux_score), (0.50, content_score)])

        # Google View: Technical (40%) + On-Page (30%) + Schema (30%).
        google_score = weighted_mean([(0.40, tech_score), (0.30, onpage_score), (0.30, schema_score)])

        # AI Readiness View: GEO category score blended with question support when both exist.
        support_points = None
        if geo_readiness is not None and getattr(geo_readiness, "questions_total", 0) > 0:
            support_ratio = getattr(geo_readiness, "questions_supported", 0) / geo_readiness.questions_total
            support_points = support_ratio * 100.0
            ai_readiness_score = weighted_mean([(0.6, geo_score), (0.4, support_points)])
        elif commercial_evals:
            valid_comm = [getattr(c, "before_score", None) for c in commercial_evals if getattr(c, "before_score", None) is not None]
            if valid_comm:
                avg_comm = sum(valid_comm) / len(valid_comm)
                ai_readiness_score = weighted_mean([(0.5, geo_score), (0.5, avg_comm * 10.0)])
            else:
                ai_readiness_score = None if geo_score is None else round(geo_score, 1)
        else:
            ai_readiness_score = None if geo_score is None else round(geo_score, 1)

        # AI Visibility: Live empirical outcome only. Zero is measured. None is not.
        if live_citation_score is not None:
            ai_visibility_score = round(float(live_citation_score), 1)
            ai_visibility_status = "MEASURED"
            live_ai_citation_score = ai_visibility_score
            ai_citation_status = "measured"
        else:
            ai_visibility_score = None
            ai_visibility_status = "NOT_MEASURED"
            live_ai_citation_score = None
            ai_citation_status = "not_measured"

        overall = weighted_mean([
            (0.35, human_score),
            (0.35, google_score),
            (0.30, ai_readiness_score),
        ])

        if overall is None:
            band = "Not scored"
        elif overall >= 90:
            band = "Category Benchmark"
        elif overall >= 75:
            if ai_visibility_status == "MEASURED" and ai_visibility_score is not None and ai_visibility_score < 15:
                band = "Structure Ready (Uncited)"
            else:
                band = "Citation Ready"
        elif overall >= 50:
            band = "Fragile Presence"
        else:
            band = "Low readiness"

        def _view(score: Optional[float]) -> str:
            return "not measured" if score is None else f"{score:.0f}/100"

        human_summary = f"Human Experience View: {_view(human_score)} aggregated from measured UX and Content checks."
        google_summary = f"Google Organic View: {_view(google_score)} aggregated from measured Technical, On-Page, and Schema checks."
        if ai_visibility_score is not None:
            if ai_visibility_score == 0:
                ai_summary = f"AI Readiness: {_view(ai_readiness_score)} (on-page). Live Engine Citations: 0% (measured; domain not cited)."
            else:
                ai_summary = f"AI Readiness: {_view(ai_readiness_score)} (on-page). AI Visibility: {ai_visibility_score:.0f}/100 (live measurement)."
        else:
            ai_summary = f"AI Readiness: {_view(ai_readiness_score)} (on-page). AI Visibility: NOT MEASURED (live connector not run)."

        all_evidence: List[str] = []
        for f in findings:
            all_evidence.extend(f.evidence_refs)

        return HonestScores(
            human_score=human_score,
            google_score=google_score,
            ai_readiness_score=ai_readiness_score,
            ai_visibility_score=ai_visibility_score,
            ai_visibility_status=ai_visibility_status,
            ai_citation_score=ai_visibility_score,
            on_page_proxy_score=ai_readiness_score,
            live_ai_citation_score=live_ai_citation_score,
            overall_score=overall,
            score_band=band,
            human_summary=human_summary,
            google_summary=google_summary,
            ai_citation_summary=ai_summary,
            evidence_refs=sorted(list(set(all_evidence)))[:12],
            status="AVAILABLE",
            ai_citation_status=ai_citation_status,
        )
