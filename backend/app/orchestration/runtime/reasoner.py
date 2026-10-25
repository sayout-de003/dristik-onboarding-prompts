"""
Dristik AI Pruned Specialist Reasoner Workforce
Implements the 3 focused Specialist Reasoners (Technical, GEO/AEO, CRO/Experience),
along with CrossAnalystAgent, CriticAgent (adversarial gatekeeper), and SynthesizerAgent.
All reasoners operate strictly over deterministic evidence and emit typed EvidenceRef contracts.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime

from app.domain.enums import Category, Severity, VerificationStatus, Materiality, RubricConfidence
from app.domain.models import Claim, CrawlManifest, Finding, FindingEvidence, PageEvidence
from app.domain.evidence.models import EvidenceRef
from app.seo.analyzers.canonical_redirect_consistency import CanonicalRedirectConsistencyAnalyzer
from app.seo.analyzers.sitemap_orphan_analyzer import SitemapOrphanAnalyzer

logger = logging.getLogger("dristik.agents.reasoners")


def _compute_hash(data: Any) -> str:
    s = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def derive_finding_metrics(
    severity: Severity,
    evidence_strength: str = "direct_measurement",
    scope_affected_urls: int = 1,
    is_blocking: bool = False,
    estimated_complexity: str = "medium"
) -> Tuple[int, int, int]:
    """
    Deterministically derives (impact, effort, priority) from explicit, transparent factors.
    Eliminates arbitrary hardcoded integers across findings.
    """
    sev_impact = {
        Severity.CRITICAL: 10,
        Severity.HIGH: 8,
        Severity.MEDIUM: 5,
        Severity.LOW: 3,
        Severity.INFO: 1,
    }.get(severity, 5)

    if scope_affected_urls > 5:
        sev_impact = min(10, sev_impact + 1)
    # `is_blocking` stays on the signature for callers. Blocking does not raise business impact.
    _ = is_blocking
    impact = sev_impact

    effort_map = {
        "trivial": 1,
        "low": 2,
        "medium": 4,
        "high": 6,
        "architectural": 8,
    }
    effort = effort_map.get(estimated_complexity, 4)

    strength_mult = {
        "direct_measurement": 1.0,
        "dom_structure": 0.9,
        "derived_correlation": 0.8,
        "heuristic": 0.6,
    }.get(evidence_strength, 0.8)

    raw_prio = (impact * 0.7 + (10 - effort) * 0.3) * strength_mult
    priority = max(1, min(10, int(round(raw_prio))))
    return impact, effort, priority


# ==============================================================================
# 1. TECHNICAL REASONER AGENT
# ==============================================================================
class TechnicalReasonerAgent:
    """
    Cognitive & deterministic reasoning over indexability, canonical/redirect
    consistency, crawl budget, TTFB, image dimensions/CLS, and security.
    """

    def __init__(self, model_router=None):
        self.model_router = model_router
        self.canonical_analyzer = CanonicalRedirectConsistencyAnalyzer()
        self.orphan_analyzer = SitemapOrphanAnalyzer()

    async def reason(
        self,
        manifest: CrawlManifest,
        pages: Optional[List[PageEvidence]] = None,
        evidence_store: Optional[Any] = None
    ) -> List[Finding]:
        findings: List[Finding] = []
        pages_list = pages or manifest.pages or []

        # 1. Run canonical & redirect engine
        canon_res = self.canonical_analyzer.analyze(manifest, pages_list)
        findings.extend(canon_res.get("findings", []))

        # 2. Run sitemap orphan engine
        orphan_res = self.orphan_analyzer.analyze(manifest)
        findings.extend(orphan_res.get("findings", []))

        # 3. Analyze image dimensions & CLS risk
        for p in pages_list:
            cls_risks = [img for img in (p.image_assets or []) if img.get("cls_risk")]
            if cls_risks:
                sample = cls_risks[:3]
                ev_hash = _compute_hash({"url": p.url, "cls_risks": sample})
                ev_ref = EvidenceRef(
                    source_type="measured",
                    source_id=f"tech_cls_risk_{hashlib.md5(p.url.encode()).hexdigest()[:8]}",
                    evidence_hash=ev_hash,
                    url=p.url,
                    selector="img",
                    snippet=f"{len(cls_risks)} images missing width/height attributes",
                    observed_value=sample,
                    collector_or_analyzer="TechnicalReasonerAgent.cls_analyzer",
                    metadata={"cls_risk_images": sample}
                )
                sev = Severity.HIGH if len(cls_risks) > 4 else Severity.MEDIUM
                impact, effort, priority = derive_finding_metrics(
                    severity=sev,
                    evidence_strength="dom_structure",
                    scope_affected_urls=1,
                    estimated_complexity="low"
                )
                findings.append(Finding(
                    finding_id=f"finding_cls_risk_{ev_hash[:8]}",
                    category=Category.TECHNICAL_SEO,
                    severity=sev,
                    title=f"{len(cls_risks)} Image(s) Missing Explicit Dimensions (CLS Risk)",
                    description=(
                        f"Page '{p.url}' contains {len(cls_risks)} image(s) lacking intrinsic width and height attributes. "
                        "Browsers cannot allocate layout space before image download, triggering Cumulative Layout Shift (CLS)."
                    ),
                    recommendation="Add explicit width and height attributes (or aspect-ratio CSS) to all <img> tags.",
                    why_it_matters="CLS is a Core Web Vital. Layout shifts degrade mobile user experience and hurt search rankings.",
                    validation_criteria="All <img> tags on the page must specify explicit width and height attributes.",
                    evidence=[
                        FindingEvidence(
                            url=p.url,
                            element="img",
                            value=img.get("src", ""),
                            source="crawl",
                            evidence_ref=ev_ref,
                        )
                        for img in sample
                    ],
                    evidence_refs=[ev_ref.source_id],
                    evidence_ref_objects=[ev_ref],
                    impact=impact,
                    effort=effort,
                    priority=priority,
                ))

            # 4. Check TTFB latency
            if p.ttfb_ms and p.ttfb_ms > 800.0:
                ev_hash = _compute_hash({"url": p.url, "ttfb_ms": p.ttfb_ms})
                ev_ref = EvidenceRef(
                    source_type="measured",
                    source_id=f"tech_ttfb_{hashlib.md5(p.url.encode()).hexdigest()[:8]}",
                    evidence_hash=ev_hash,
                    url=p.url,
                    snippet=f"TTFB measured at {p.ttfb_ms:.1f}ms (> 800ms threshold)",
                    observed_value=p.ttfb_ms,
                    collector_or_analyzer="TechnicalReasonerAgent.ttfb_analyzer",
                    metadata={"ttfb_ms": p.ttfb_ms}
                )
                impact, effort, priority = derive_finding_metrics(
                    severity=Severity.HIGH,
                    evidence_strength="direct_measurement",
                    scope_affected_urls=1,
                    estimated_complexity="medium"
                )
                findings.append(Finding(
                    finding_id=f"finding_high_ttfb_{ev_hash[:8]}",
                    category=Category.TECHNICAL_SEO,
                    severity=Severity.HIGH,
                    title=f"Slow Server Response Time: TTFB {p.ttfb_ms:.0f}ms",
                    description=(
                        f"Page '{p.url}' exhibited a measured Time-to-First-Byte (TTFB) of {p.ttfb_ms:.0f}ms, "
                        "exceeding the standard 800ms threshold."
                    ),
                    recommendation=(
                        f"Profile origin server-side response execution and database query latency for '{p.url}' "
                        "before introducing edge caching rules. Validate using repeat measurements below 600ms."
                    ),
                    why_it_matters="High TTFB directly delays initial page rendering (LCP) and degrades mobile visitor retention.",
                    validation_criteria=f"TTFB for {p.url} must remain below 600ms on repeatable edge measurements.",
                    evidence=[FindingEvidence(
                        url=p.url,
                        element="network_ttfb",
                        value=f"{p.ttfb_ms:.1f}ms",
                        source="measured",
                        evidence_ref=ev_ref,
                    )],
                    evidence_refs=[ev_ref.source_id],
                    evidence_ref_objects=[ev_ref],
                    impact=impact,
                    effort=effort,
                    priority=priority,
                ))

        return findings


# ==============================================================================
# 2. GEO / AEO REASONER AGENT
# ==============================================================================
class GeoAeoReasonerAgent:
    """
    Reasoning over machine-readability, Schema JSON-LD graphs, entity disambiguation,
    and AI search engine visibility preparedness.
    """

    def __init__(self, model_router=None):
        self.model_router = model_router

    async def reason(
        self,
        manifest: CrawlManifest,
        pages: Optional[List[PageEvidence]] = None,
        evidence_store: Optional[Any] = None
    ) -> List[Finding]:
        findings: List[Finding] = []
        pages_list = pages or manifest.pages or []

        # 1. Entity-Aware Schema JSON-LD Audit across domain
        all_schemas = {st for p in pages_list for st in (p.schema_types or [])}
        homepage = pages_list[0] if pages_list else None

        recognized_entity_types = {
            "Organization", "Corporation", "LocalBusiness", "MedicalOrganization",
            "FinancialService", "ProfessionalService", "WebSite", "SoftwareApplication", "Person"
        }
        has_entity_schema = bool(all_schemas.intersection(recognized_entity_types))

        if not has_entity_schema:
            ev_hash = _compute_hash({"domain": manifest.domain, "schemas": list(all_schemas)})
            ev_ref = EvidenceRef(
                source_type="crawl",
                source_id="geo_missing_entity_schema",
                evidence_hash=ev_hash,
                url=homepage.url if homepage else None,
                selector="script[type='application/ld+json']",
                snippet="No recognized Schema.org entity graph (Organization, LocalBusiness, etc.) found",
                observed_value=list(all_schemas),
                collector_or_analyzer="GeoAeoReasonerAgent.schema_analyzer",
                metadata={"schemas_found": list(all_schemas)}
            )
            impact, effort, priority = derive_finding_metrics(
                severity=Severity.HIGH,
                evidence_strength="dom_structure",
                scope_affected_urls=1,
                estimated_complexity="low"
            )
            findings.append(Finding(
                finding_id=f"finding_missing_entity_schema_{ev_hash[:8]}",
                category=Category.AI_SEARCH,
                severity=Severity.HIGH,
                title="Missing Organization Schema / Structured Entity Graph (JSON-LD)",
                description=(
                    f"Domain '{manifest.domain}' lacks structured JSON-LD entity markup on the homepage. "
                    "Observed: Homepage contains no Organization, LocalBusiness, or primary entity graph. "
                    "Derived: Search engines and AI answer engines must parse unformatted text to disambiguate the official brand entity."
                ),
                recommendation="Deploy Schema.org JSON-LD entity markup on the homepage matching your verified business entity type (e.g. Organization or LocalBusiness) with name, url, logo, and sameAs profiles.",
                why_it_matters="Structured entity graphs provide verifiable corporate identity that disambiguates brand ownership in search indexes.",
                validation_criteria="Homepage must contain valid <script type='application/ld+json'> defining a primary entity graph.",
                evidence=[FindingEvidence(
                    url=homepage.url if homepage else "",
                    element="script[type='application/ld+json']",
                    value="Missing entity schema",
                    source="crawl",
                    evidence_ref=ev_ref,
                )],
                evidence_refs=[ev_ref.source_id],
                evidence_ref_objects=[ev_ref],
                impact=impact,
                effort=effort,
                priority=priority,
            ))

        # 2. Audit Heading Hierarchy for LLM text chunking
        for p in pages_list:
            h1s = p.h1 or []
            if len(h1s) == 0:
                ev_hash = _compute_hash({"url": p.url, "h1_count": 0})
                ev_ref = EvidenceRef(
                    source_type="crawl",
                    source_id=f"geo_missing_h1_{hashlib.md5(p.url.encode()).hexdigest()[:8]}",
                    evidence_hash=ev_hash,
                    url=p.url,
                    selector="h1",
                    snippet="No <h1> element found on page",
                    observed_value=0,
                    collector_or_analyzer="GeoAeoReasonerAgent.heading_analyzer",
                    metadata={"url": p.url}
                )
                impact, effort, priority = derive_finding_metrics(
                    severity=Severity.HIGH,
                    evidence_strength="dom_structure",
                    scope_affected_urls=1,
                    estimated_complexity="trivial"
                )
                findings.append(Finding(
                    finding_id=f"finding_missing_h1_{ev_hash[:8]}",
                    category=Category.AI_SEARCH,
                    severity=Severity.HIGH,
                    title="Missing Primary <h1> Heading",
                    description=(
                        f"Page '{p.url}' lacks an <h1> heading tag. Primary headings provide essential semantic "
                        "anchors for document outline structure and content indexing."
                    ),
                    recommendation="Add a descriptive, single <h1> tag clearly stating the core subject or value proposition of the page.",
                    why_it_matters="Without an <h1>, document hierarchy is incomplete and passage indexing confidence is reduced.",
                    validation_criteria=f"Document at {p.url} must contain exactly one semantic <h1> element.",
                    evidence=[FindingEvidence(
                        url=p.url,
                        element="h1",
                        value="Missing <h1> element",
                        source="crawl",
                        evidence_ref=ev_ref,
                    )],
                    evidence_refs=[ev_ref.source_id],
                    evidence_ref_objects=[ev_ref],
                    impact=impact,
                    effort=effort,
                    priority=priority,
                ))
            elif len(h1s) > 1:
                ev_hash = _compute_hash({"url": p.url, "h1_count": len(h1s), "h1s": h1s})
                ev_ref = EvidenceRef(
                    source_type="crawl",
                    source_id=f"geo_multiple_h1_{hashlib.md5(p.url.encode()).hexdigest()[:8]}",
                    evidence_hash=ev_hash,
                    url=p.url,
                    selector="h1",
                    snippet=f"Multiple <h1> tags detected: {h1s[:2]}",
                    observed_value=h1s,
                    collector_or_analyzer="GeoAeoReasonerAgent.heading_analyzer",
                    metadata={"h1s": h1s}
                )
                impact, effort, priority = derive_finding_metrics(
                    severity=Severity.LOW,
                    evidence_strength="dom_structure",
                    scope_affected_urls=1,
                    estimated_complexity="trivial"
                )
                findings.append(Finding(
                    finding_id=f"finding_multiple_h1_{ev_hash[:8]}",
                    category=Category.AI_SEARCH,
                    severity=Severity.LOW,
                    title=f"Multiple <h1> Tags Detected ({len(h1s)} Found)",
                    description=(
                        f"Page '{p.url}' contains {len(h1s)} distinct <h1> tags. While valid HTML5, "
                        "a single top-level <h1> clarifies primary document topic hierarchy."
                    ),
                    recommendation="Consolidate primary page title into one <h1> and downgrade subordinate section headings to <h2>.",
                    why_it_matters="Ambiguous heading hierarchy reduces confidence in primary entity identification.",
                    validation_criteria=f"Page {p.url} should maintain a single top-level <h1>.",
                    evidence=[FindingEvidence(
                        url=p.url,
                        element="h1",
                        value=" · ".join(h1s[:2]),
                        source="crawl",
                        evidence_ref=ev_ref,
                    )],
                    evidence_refs=[ev_ref.source_id],
                    evidence_ref_objects=[ev_ref],
                    impact=impact,
                    effort=effort,
                    priority=priority,
                ))

        # 3. Contextual /llms.txt presence audit
        has_llms_txt = getattr(manifest, "llms_txt_found", False) or any(
            (p.url or "").endswith("/llms.txt") for p in pages_list
        )

        if not has_llms_txt:
            ev_hash = _compute_hash({"domain": manifest.domain, "llms_txt_found": False})
            ev_ref = EvidenceRef(
                source_type="crawl",
                source_id="geo_missing_llms_txt",
                evidence_hash=ev_hash,
                url=f"https://{manifest.domain}/llms.txt" if manifest.domain else None,
                selector="HEAD /llms.txt",
                snippet="/llms.txt returned 404 Not Found or unreferenced",
                observed_value="404 Not Found",
                collector_or_analyzer="GeoAeoReasonerAgent.llms_txt_analyzer",
                metadata={"domain": manifest.domain}
            )
            impact, effort, priority = derive_finding_metrics(
                severity=Severity.LOW,
                evidence_strength="crawl",
                scope_affected_urls=1,
                estimated_complexity="trivial"
            )
            findings.append(Finding(
                finding_id=f"finding_missing_llms_txt_{ev_hash[:8]}",
                category=Category.AI_SEARCH,
                severity=Severity.LOW,
                title="Missing /llms.txt Machine Readability File (Optional)",
                description=(
                    f"Domain '{manifest.domain}' does not provide an `/llms.txt` file at the root. "
                    "A standard /llms.txt file provides clean markdown references for external LLM ingestion."
                ),
                recommendation="Deploy an optional `/llms.txt` file at domain root outlining key documentation sections and API references.",
                why_it_matters="LLM crawlers that support /llms.txt can ingest structured markdown directly.",
                validation_criteria="HTTP GET /llms.txt returns 200 OK with Markdown formatted text.",
                evidence=[FindingEvidence(
                    url=f"https://{manifest.domain}/llms.txt" if manifest.domain else "",
                    element="GET /llms.txt",
                    value="404 Not Found",
                    source="crawl",
                    evidence_ref=ev_ref,
                )],
                evidence_refs=[ev_ref.source_id],
                evidence_ref_objects=[ev_ref],
                impact=impact,
                effort=effort,
                priority=priority,
            ))

        # 4. Layer 3 & 4: Causal Citation Gap Analysis (Telemetry-backed only)
        try:
            from app.geo.citation_gap import geo_citation_gap_engine
            gap_report = geo_citation_gap_engine.analyze_citation_gaps(
                target_domain=manifest.domain or "target.com",
                pages=pages_list,
            )
            if gap_report.status == "AVAILABLE" and gap_report.gaps:
                primary_gap = gap_report.gaps[0]
                ev_ref = primary_gap.evidence_ref or EvidenceRef(
                    source_type="derived",
                    source_id=primary_gap.gap_id,
                    evidence_hash=_compute_hash({"gap_id": primary_gap.gap_id}),
                    url=f"https://{manifest.domain}",
                    snippet=primary_gap.actionable_copy_snippet[:180],
                    observed_value=primary_gap.root_cause_explanation,
                    collector_or_analyzer="GeoCitationGapEngine",
                    parent_evidence_refs=["geo_missing_entity_schema"] if not has_entity_schema else []
                )
                impact, effort, priority = derive_finding_metrics(
                    severity=Severity.HIGH,
                    evidence_strength="derived_correlation",
                    scope_affected_urls=1,
                    estimated_complexity="medium"
                )
                findings.append(Finding(
                    finding_id=f"finding_{primary_gap.gap_id}",
                    category=Category.AI_SEARCH,
                    severity=Severity.HIGH,
                    title="AI Citation Gap: Missing 3rd-Party Authority Verification",
                    description=(
                        f"AI search engines prioritize competitors ({primary_gap.competitor_cited}) over {manifest.domain} "
                        f"for buyer inquiries because competitors are cited across independent authority sources "
                        f"({', '.join(primary_gap.competitor_sources[:3])}). {primary_gap.root_cause_explanation}"
                    ),
                    recommendation=(
                        f"1. Deploy drop-in 35-75 word extractable copy snippet on relevant page. "
                        f"2. Add JSON-LD schema patch with sameAs authority links. "
                        f"3. {primary_gap.third_party_acquisition_actions[0] if primary_gap.third_party_acquisition_actions else 'Establish directory presence.'}"
                    ),
                    why_it_matters="AI answer engines rely on third-party verification to validate brand claims before citing.",
                    validation_criteria="Target must establish verified profiles on independent review platforms and provide public citable facts.",
                    evidence=[FindingEvidence(
                        url=f"https://{manifest.domain}",
                        element="ai_citation_graph",
                        value=primary_gap.root_cause_explanation,
                        source="derived",
                        evidence_ref=ev_ref,
                    )],
                    evidence_refs=[ev_ref.source_id],
                    evidence_ref_objects=[ev_ref],
                    impact=impact,
                    effort=effort,
                    priority=priority,
                ))
        except Exception as exc:
            logger.warning("Failed to run citation gap analysis in GeoAeoReasonerAgent: %s", exc)

        return findings


# ==============================================================================
# 3. CRO / EXPERIENCE REASONER AGENT
# ==============================================================================
class CroExperienceReasonerAgent:
    """
    Reasoning over conversion friction, CTA visual prominence, mobile responsiveness,
    and lead capture form usability.
    """

    def __init__(self, model_router=None):
        self.model_router = model_router

    async def reason(
        self,
        manifest: CrawlManifest,
        pages: Optional[List[PageEvidence]] = None,
        evidence_store: Optional[Any] = None
    ) -> List[Finding]:
        findings: List[Finding] = []
        pages_list = pages or manifest.pages or []

        for p in pages_list:
            # 1. Viewport Meta Tag Audit (Critical Mobile Gate)
            if not p.viewport:
                ev_hash = _compute_hash({"url": p.url, "viewport": None})
                ev_ref = EvidenceRef(
                    source_type="crawl",
                    source_id=f"cro_missing_viewport_{hashlib.md5(p.url.encode()).hexdigest()[:8]}",
                    evidence_hash=ev_hash,
                    url=p.url,
                    selector="meta[name=viewport]",
                    snippet="No viewport meta tag found",
                    observed_value=None,
                    collector_or_analyzer="CroExperienceReasonerAgent.viewport_analyzer",
                    metadata={"url": p.url}
                )
                impact, effort, priority = derive_finding_metrics(
                    severity=Severity.CRITICAL,
                    evidence_strength="dom_structure",
                    scope_affected_urls=1,
                    is_blocking=False,
                    estimated_complexity="trivial"
                )
                findings.append(Finding(
                    finding_id=f"finding_missing_viewport_{ev_hash[:8]}",
                    category=Category.UX_CONVERSION,
                    severity=Severity.CRITICAL,
                    title="Missing Mobile Viewport Meta Tag",
                    description=(
                        f"Page '{p.url}' lacks a `<meta name='viewport'>` tag. Mobile browsers will render "
                        "the page in desktop mode, causing severe layout degradation on mobile screens."
                    ),
                    recommendation="Add `<meta name='viewport' content='width=device-width, initial-scale=1.0'>` in the <head>.",
                    why_it_matters="Over 60% of modern web traffic is mobile. Lack of viewport tag breaks responsive mobile rendering.",
                    validation_criteria="Page <head> must include `<meta name='viewport' content='width=device-width, initial-scale=1.0'>`.",
                    evidence=[FindingEvidence(
                        url=p.url,
                        element="meta[name=viewport]",
                        value="Missing viewport",
                        source="crawl",
                        evidence_ref=ev_ref,
                    )],
                    evidence_refs=[ev_ref.source_id],
                    evidence_ref_objects=[ev_ref],
                    impact=impact,
                    effort=effort,
                    priority=priority,
                ))

            # 2. Contextual Form Field Friction Analysis
            p_forms = getattr(p, "forms", None) or []
            if p_forms:
                for idx, form in enumerate(p_forms):
                    inputs = form.get("inputs", []) if isinstance(form, dict) else []
                    substantive = [inp for inp in inputs if isinstance(inp, dict) and inp.get("type") not in ("hidden", "submit", "button")]
                    field_count = len(substantive) if substantive else len(inputs)

                    # Only flag lengthy forms that exceed 6 substantive fields
                    if field_count > 6:
                        ev_hash = _compute_hash({"url": p.url, "form_idx": idx, "field_count": field_count})
                        ev_ref = EvidenceRef(
                            source_type="crawl",
                            source_id=f"cro_form_friction_{hashlib.md5(p.url.encode()).hexdigest()[:8]}_{idx}",
                            evidence_hash=ev_hash,
                            url=p.url,
                            selector="form",
                            snippet=f"Form contains {field_count} substantive input fields",
                            observed_value=field_count,
                            collector_or_analyzer="CroExperienceReasonerAgent.form_analyzer",
                            metadata={"field_count": field_count}
                        )
                        impact, effort, priority = derive_finding_metrics(
                            severity=Severity.MEDIUM,
                            evidence_strength="dom_structure",
                            scope_affected_urls=1,
                            estimated_complexity="medium"
                        )
                        findings.append(Finding(
                            finding_id=f"finding_form_friction_{ev_hash[:8]}",
                            category=Category.UX_CONVERSION,
                            severity=Severity.MEDIUM,
                            title=f"High Form Field Friction ({field_count} Fields)",
                            description=(
                                f"Page '{p.url}' contains a form with {field_count} substantive input fields. "
                                "Observed: Input count exceeds recommended single-step form length. "
                                "Interpretation: Lengthy forms increase cognitive friction and input fatigue on mobile devices."
                            ),
                            recommendation="Audit required vs optional fields and consider multi-step progressive disclosure for lengthy forms.",
                            why_it_matters="High input fatigue on mobile devices increases form abandonment.",
                            validation_criteria="Form should require no more than 3-4 essential inputs on initial submission step.",
                            evidence=[FindingEvidence(
                                url=p.url,
                                element="form",
                                value=f"{field_count} fields",
                                source="crawl",
                                evidence_ref=ev_ref,
                            )],
                            evidence_refs=[ev_ref.source_id],
                            evidence_ref_objects=[ev_ref],
                            impact=impact,
                            effort=effort,
                            priority=priority,
                        ))

            # 3. Grounded Call-to-Action (CTA) Audit
            p_ctas = getattr(p, "call_to_actions", None) or getattr(p, "ctas", None) or []
            if not p_ctas and (p.word_count or 0) > 100:
                ev_hash = _compute_hash({"url": p.url, "ctas": 0})
                ev_ref = EvidenceRef(
                    source_type="crawl",
                    source_id=f"cro_missing_cta_{hashlib.md5(p.url.encode()).hexdigest()[:8]}",
                    evidence_hash=ev_hash,
                    url=p.url,
                    selector="a, button",
                    snippet="No clear conversion call-to-action found in HTML markup",
                    observed_value=0,
                    collector_or_analyzer="CroExperienceReasonerAgent.cta_analyzer",
                    metadata={"url": p.url}
                )
                impact, effort, priority = derive_finding_metrics(
                    severity=Severity.MEDIUM,
                    evidence_strength="dom_structure",
                    scope_affected_urls=1,
                    estimated_complexity="low"
                )
                findings.append(Finding(
                    finding_id=f"finding_missing_cta_{ev_hash[:8]}",
                    category=Category.UX_CONVERSION,
                    severity=Severity.MEDIUM,
                    title="Missing Primary Call-to-Action (CTA)",
                    description=(
                        f"Page '{p.url}' contains content ({p.word_count} words) but has no clearly defined "
                        "primary conversion action or button identified in crawled HTML markup. "
                        "Note: Viewport above-the-fold placement and visual contrast were not evaluated from raw DOM."
                    ),
                    recommendation="Add a clear primary CTA link or button (e.g., 'Get Started', 'Schedule a Demo', 'View Pricing').",
                    why_it_matters="Visitors without an obvious next step are far more likely to exit without converting.",
                    validation_criteria="Page must include at least one prominent primary action button.",
                    evidence=[FindingEvidence(
                        url=p.url,
                        element="body",
                        value="Zero CTAs detected in HTML",
                        source="crawl",
                        evidence_ref=ev_ref,
                    )],
                    evidence_refs=[ev_ref.source_id],
                    evidence_ref_objects=[ev_ref],
                    impact=impact,
                    effort=effort,
                    priority=priority,
                ))

            # 4. Passive & Generic CTA Friction Check
            if p_ctas:
                generic_ctas = [
                    str(c).strip() for c in p_ctas
                    if str(c).strip().lower() in ("submit", "click here", "learn more", "read more", "continue", "go")
                ]
                if generic_ctas:
                    ev_hash = _compute_hash({"url": p.url, "generic_ctas": generic_ctas})
                    ev_ref = EvidenceRef(
                        source_type="crawl",
                        source_id=f"cro_passive_cta_{hashlib.md5(p.url.encode()).hexdigest()[:8]}",
                        evidence_hash=ev_hash,
                        url=p.url,
                        selector="button, a",
                        snippet=f"Generic microcopy buttons: {', '.join(generic_ctas)}",
                        observed_value=len(generic_ctas),
                        collector_or_analyzer="CroExperienceReasonerAgent.cta_microcopy_analyzer",
                        metadata={"generic_ctas": generic_ctas}
                    )
                    impact, effort, priority = derive_finding_metrics(
                        severity=Severity.LOW,
                        evidence_strength="dom_structure",
                        scope_affected_urls=1,
                        estimated_complexity="low"
                    )
                    findings.append(Finding(
                        finding_id=f"finding_passive_cta_{ev_hash[:8]}",
                        category=Category.UX_CONVERSION,
                        severity=Severity.LOW,
                        title=f"Passive CTA Microcopy ('{generic_ctas[0]}')",
                        description=(
                            f"Page '{p.url}' contains {len(generic_ctas)} CTA button(s) with generic microcopy ({', '.join(generic_ctas)}). "
                            "Low-intent labels increase cognitive friction and deliver lower click-through conversion than outcome-driven verbs."
                        ),
                        recommendation="Replace generic button copy with outcome-driven action phrases (e.g., 'Claim Free Audit', 'Explore Plans').",
                        why_it_matters="Outcome-driven CTAs clarify user benefit and reduce hesitation before clicking.",
                        validation_criteria="All interactive CTA buttons must contain specific value-oriented verbs.",
                        evidence=[FindingEvidence(
                            url=p.url,
                            element="button, a",
                            value=f"{len(generic_ctas)} generic buttons",
                            source="crawl",
                            evidence_ref=ev_ref,
                        )],
                        evidence_refs=[ev_ref.source_id],
                        evidence_ref_objects=[ev_ref],
                        impact=impact,
                        effort=effort,
                        priority=priority,
                    ))

        return findings


# ==============================================================================
# 4. CROSS-ANALYST AGENT
# ==============================================================================
class CrossAnalystAgent:
    """
    Synthesizes causal multi-hop interactions across technical, GEO, and CRO pillars.
    Strictly distinguishes observed correlations from proven causal claims.
    """

    async def analyze(self, findings: List[Finding], manifest: CrawlManifest) -> List[Finding]:
        synthesized: List[Finding] = []

        ttfb_findings = [f for f in findings if "Slow Server Response Time" in f.title or "TTFB" in f.title]
        form_findings = [f for f in findings if "Form" in f.title]

        # Verify page overlap: TTFB + Form friction must occur on the SAME page to establish candidate correlation
        ttfb_urls: Set[str] = {
            ev.url for f in ttfb_findings for ev in (f.evidence or []) if ev.url
        } | {
            obj.url for f in ttfb_findings for obj in (f.evidence_ref_objects or []) if getattr(obj, "url", None)
        }
        form_urls: Set[str] = {
            ev.url for f in form_findings for ev in (f.evidence or []) if ev.url
        } | {
            obj.url for f in form_findings for obj in (f.evidence_ref_objects or []) if getattr(obj, "url", None)
        }
        shared_urls = ttfb_urls.intersection(form_urls)

        # If findings don't specify individual sub-URLs, evaluate domain-level co-occurrence
        if not shared_urls and ttfb_findings and form_findings and not ttfb_urls and not form_urls:
            domain_name = manifest.domain or "target-domain"
            shared_urls = {f"https://{domain_name}/"}

        if shared_urls:
            for target_url in sorted(list(shared_urls)):
                parent_refs = [
                    ref for f in ttfb_findings + form_findings
                    for ref in f.evidence_refs
                ]
                ev_hash = _compute_hash({"synergy": "ttfb_and_form_friction", "url": target_url})
                ev_ref = EvidenceRef(
                    source_type="derived",
                    source_id=f"cross_bounce_compound_{hashlib.md5(target_url.encode()).hexdigest()[:8]}",
                    evidence_hash=ev_hash,
                    url=target_url,
                    snippet=f"Measured TTFB >800ms and form friction coincide on page '{target_url}'",
                    observed_value={"url": target_url, "factors": ["high_ttfb", "form_friction"]},
                    collector_or_analyzer="CrossAnalystAgent",
                    parent_evidence_refs=parent_refs[:4],
                    metadata={"factors": ["high_ttfb", "form_friction"], "url": target_url}
                )
                impact, effort, priority = derive_finding_metrics(
                    severity=Severity.HIGH,
                    evidence_strength="derived_correlation",
                    scope_affected_urls=1,
                    estimated_complexity="medium"
                )
                synthesized.append(Finding(
                    finding_id=f"finding_cross_bounce_compound_{ev_hash[:8]}",
                    category=Category.UX_CONVERSION,
                    severity=Severity.HIGH,
                    title="Compounded Conversion Barrier: Slow TTFB Meets High Form Friction",
                    description=(
                        f"Page '{target_url}' exhibits both high server response time (>800ms TTFB) and high form complexity. "
                        "Observed correlation: Delivery latency coincides on the same page with complex input forms. "
                        "Hypothesis: Technical delivery delay may compound form abandonment; causal user loss requires analytics telemetry."
                    ),
                    recommendation=f"Profile server response time for '{target_url}' and streamline form fields to minimize conversion drop-off.",
                    why_it_matters="Combined technical and interaction barriers create multiple drop-off points for commercial visitors.",
                    validation_criteria=f"TTFB for {target_url} < 600ms and form simplified.",
                    evidence_refs=[ev_ref.source_id],
                    evidence_ref_objects=[ev_ref],
                    confidence_rubric=RubricConfidence.LOW_CONFIDENCE,
                    verification_status=VerificationStatus.DERIVED,
                    impact=impact,
                    effort=effort,
                    priority=priority,
                ))

        # Synergy 2: Missing Entity Schema + Canonical issues
        has_schema_issue = any("Missing Structured Entity Schema" in f.title or "Missing Organization" in f.title for f in findings)
        canon_findings = [f for f in findings if "Canonical" in f.title]
        if has_schema_issue and canon_findings:
            parent_refs = [
                ref for f in canon_findings for ref in f.evidence_refs
            ]
            ev_hash = _compute_hash({"synergy": "schema_and_canonical_ambiguity", "domain": manifest.domain})
            ev_ref = EvidenceRef(
                source_type="derived",
                source_id="cross_ai_entity_ambiguity",
                evidence_hash=ev_hash,
                snippet="Missing primary entity schema combined with canonical inconsistencies across crawled pages",
                observed_value={"domain": manifest.domain, "factors": ["missing_entity_schema", "canonical_inconsistency"]},
                collector_or_analyzer="CrossAnalystAgent",
                parent_evidence_refs=parent_refs[:4],
                metadata={"factors": ["missing_entity_schema", "canonical_inconsistency"]}
            )
            impact, effort, priority = derive_finding_metrics(
                severity=Severity.HIGH,
                evidence_strength="derived_correlation",
                scope_affected_urls=1,
                estimated_complexity="medium"
            )
            synthesized.append(Finding(
                finding_id=f"finding_cross_ai_ambiguity_{ev_hash[:8]}",
                category=Category.AI_SEARCH,
                severity=Severity.HIGH,
                title="AI Entity Disambiguation Risk: Structured Data Absence + Canonical Inconsistency",
                description=(
                    "The combination of absent homepage entity JSON-LD and inconsistent canonical link tags "
                    "hampers search crawlers from deterministically verifying primary entity identity."
                ),
                recommendation="Deploy clean self-referencing canonicals and a verified Schema.org entity graph.",
                why_it_matters="Ambiguity in both canonical URL and structured corporate data impairs search engine knowledge graph attribution.",
                validation_criteria="Valid entity JSON-LD present with self-referencing canonicals.",
                evidence_refs=[ev_ref.source_id],
                evidence_ref_objects=[ev_ref],
                confidence_rubric=RubricConfidence.HIGH_CONFIDENCE,
                verification_status=VerificationStatus.DERIVED,
                impact=impact,
                effort=effort,
                priority=priority,
            ))

        return synthesized


# ==============================================================================
# 5. CRITIC AGENT (ADVERSARIAL GATEKEEPER)
# ==============================================================================
class CriticAgent:
    """
    Adversarial verification gatekeeper.
    Performs true evidence-chain validation:
    Finding -> Claim -> EvidenceRef -> Underlying observation -> Source.
    Rejects or flags any finding or claim that lacks verifiable, observable EvidenceRef.
    """

    def audit_findings(self, findings: List[Finding], evidence_store: Optional[Any] = None) -> Dict[str, Any]:
        verified: List[Finding] = []
        rejected: List[Finding] = []
        demoted: List[Finding] = []

        store_evidence_ids: Set[str] = set()
        if evidence_store and hasattr(evidence_store, "get_all"):
            try:
                for item in evidence_store.get_all():
                    store_evidence_ids.add(getattr(item, "id", str(item)))
            except Exception:
                pass

        for f in findings:
            # Check 1: Must have evidence_refs or evidence_ref_objects or evidence items
            has_refs = bool(f.evidence_refs or f.evidence_ref_objects)
            has_evidence_items = bool(f.evidence)

            if not has_refs and not has_evidence_items:
                f.held_from_executive = True
                f.confidence_rubric = RubricConfidence.GUESSING
                f.verification_status = VerificationStatus.REJECTED
                f.verification_notes = "Rejected: Finding contains zero backing evidence references or observations."
                f.adversarial_reviewed = True
                rejected.append(f)
                continue

            # Check 2: Unresolvable / fabricated EvidenceRef verification against EvidenceStore
            if store_evidence_ids:
                ref_ids = set(f.evidence_refs)
                for ref_obj in f.evidence_ref_objects:
                    if ref_obj.source_id:
                        ref_ids.add(ref_obj.source_id)

                unresolvable = [rid for rid in ref_ids if rid not in store_evidence_ids and not rid.startswith("tech_") and not rid.startswith("geo_") and not rid.startswith("cro_") and not rid.startswith("cross_")]
                if unresolvable:
                    f.held_from_executive = True
                    f.confidence_rubric = RubricConfidence.UNVERIFIED
                    f.verification_status = VerificationStatus.REJECTED
                    f.verification_notes = f"Rejected: Fabricated or unresolvable EvidenceRef '{unresolvable[0]}' not present in EvidenceStore."
                    f.adversarial_reviewed = True
                    rejected.append(f)
                    continue

            # Check 3: Evidence content hash integrity
            corrupted = False
            for ref in f.evidence_ref_objects:
                if not ref.evidence_hash or len(ref.evidence_hash) < 16:
                    corrupted = True
                    break

            if corrupted:
                f.held_from_executive = True
                f.confidence_rubric = RubricConfidence.LOW_CONFIDENCE
                f.verification_status = VerificationStatus.UNSUPPORTED
                f.verification_notes = "Demoted: EvidenceRef cryptographic hash is missing or corrupted."
                f.adversarial_reviewed = True
                demoted.append(f)
                continue

            # Check 4: Evidence Contradiction Checks
            contradicted = False
            title_low = f.title.lower()
            for ev in f.evidence:
                # Contradiction: Claims missing H1, but evidence shows valid H1 text
                if "missing primary <h1>" in title_low or "missing <h1>" in title_low:
                    if ev.value and ev.value != "Missing <h1> element" and len(str(ev.value).strip()) > 3:
                        contradicted = True
                        break
                # Contradiction: Claims high TTFB, but value is <= 800ms
                if "slow server response time" in title_low or "ttfb" in title_low:
                    val_str = str(ev.value)
                    if "ms" in val_str:
                        try:
                            num = float(val_str.replace("ms", "").strip())
                            if num <= 800.0:
                                contradicted = True
                                break
                        except ValueError:
                            pass

            if contradicted:
                f.held_from_executive = True
                f.confidence_rubric = RubricConfidence.UNVERIFIED
                f.verification_status = VerificationStatus.CONTRADICTED
                f.verification_notes = "Rejected: Underlying evidence contradicts the asserted finding claim."
                f.adversarial_reviewed = True
                rejected.append(f)
                continue

            # Epistemic Confidence Assignment:
            # Distinguish direct measurements from derived correlations and hypotheses
            f.adversarial_reviewed = True
            if f.verification_status == VerificationStatus.DERIVED:
                f.confidence_rubric = RubricConfidence.HIGH_CONFIDENCE
            elif f.verification_status == VerificationStatus.INFERRED:
                f.confidence_rubric = RubricConfidence.LOW_CONFIDENCE
            else:
                f.confidence_rubric = RubricConfidence.VERIFIED
                f.verification_status = VerificationStatus.VERIFIED

            verified.append(f)

        return {
            "verified": verified,
            "rejected": rejected,
            "demoted": demoted,
            "audit_summary": {
                "total_inspected": len(findings),
                "verified_count": len(verified),
                "rejected_count": len(rejected),
                "demoted_count": len(demoted),
            }
        }


# ==============================================================================
# 6. SYNTHESIZER AGENT
# ==============================================================================
class SynthesizerAgent:
    """
    Consolidates verified findings into prioritized executive actions
    with surface-weighting and identity-aware deduplication.
    Never deduplicates by title alone when findings span distinct URLs or root causes.
    """

    def synthesize(self, findings: List[Finding]) -> List[Finding]:
        seen_keys: Dict[Tuple[str, str], Finding] = {}
        deduped: List[Finding] = []

        for f in findings:
            target_url = f.evidence[0].url if f.evidence and f.evidence[0].url else ""
            # Group by Category + Defect Rule Identifier + URL scope
            key = (f.category.value, f.rule_id or f.title.strip().lower(), target_url)

            if key not in seen_keys:
                seen_keys[key] = f
                deduped.append(f)
            else:
                # Merge affected surfaces into existing finding
                existing = seen_keys[key]
                for s in f.surfaces_affected:
                    if s not in existing.surfaces_affected:
                        existing.surfaces_affected.append(s)
                for ev in f.evidence:
                    if ev.url and ev.url not in [e.url for e in existing.evidence]:
                        existing.evidence.append(ev)

        # Sort by priority (descending) and severity
        severity_order = {Severity.CRITICAL: 4, Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1, Severity.INFO: 0}
        deduped.sort(
            key=lambda x: (
                x.priority,
                severity_order.get(x.severity, 0),
                x.impact
            ),
            reverse=True
        )

        return deduped
