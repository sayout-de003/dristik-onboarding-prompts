"""
GEO Readiness vs GEO Visibility (High-Density Layer 1 Extractability).

Layer 1 Readiness: Can an answer engine (Perplexity, ChatGPT Search, Gemini, Claude)
understand, extract, verify, and quote this website from crawled first-party evidence?
Computed 100% deterministically from the DOM and content graph.

Layer 2 Visibility: Was the entity actually cited in a live AI engine?
Never inferred from HTML. If no live connector ran, status is NOT_CONFIGURED.

v2 Changes:
  - GEO score is decomposed into 8 independently scored dimensions
    (GeoDimensionKey enum), each with provenance, band, and measurement metadata.
  - Dimensions that cannot be measured from crawl evidence explicitly declare
    is_measured=False and provide a measurement_note explaining the gap.
  - The composite readiness score is the weighted mean of all scored dimensions.
  - AI Engine Visibility dimension is only scored if a live connector ran.
  - Every report now carries an interpretation_disclaimer to prevent
    GEO Readiness from being misread as live citation rank.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from app.domain.models import (
    BusinessProfile,
    CrawlManifest,
    GeoDimension,
    GeoDimensionScore,
    GeoQuestionEvidence,
    GeoReadinessReport,
    PageEvidence,
)
from app.domain.enums import GeoDimensionKey
from app.geo.entity_consistency import entity_consistency_analyzer
from app.geo.claim_extractor import claim_extractor
from app.geo.question_graph import question_graph_engine
from app.geo.citation_passages import passage_analyzer
from app.geo.entity_graph import EntityGraphReport, evaluate_entity_graph


_FLUFF = (
    "revolutionize", "empower", "unprecedented", "cutting-edge", "seamless",
    "next-generation", "unlock growth", "future of business",
)

_PRICING_RE = re.compile(
    r"(?:₹|rs\.?\s?|inr\s?|\$|€|£)\s*[\d,]+(?:\.\d+)?|\b\d{2,6}\s*/\s*(?:mo|month|yr|year)\b",
    re.I,
)


def _corpus(pages: List[PageEvidence]) -> str:
    parts = []
    for p in pages:
        parts.append(p.title or "")
        parts.extend(p.h1 or [])
        parts.extend(p.h2 or [])
        parts.extend(p.h3 or [])
        parts.append(p.body_text or "")
        parts.append(p.meta_description or "")
    return "\n".join(parts)


def _page_hits(pages: List[PageEvidence], pattern: re.Pattern) -> List[Tuple[str, str]]:
    hits = []
    for p in pages:
        blob = " ".join([
            p.title or "",
            " ".join(p.h1 or []),
            " ".join(p.h2 or []),
            p.body_text or "",
        ])
        m = pattern.search(blob)
        if m:
            start = max(0, m.start() - 80)
            snippet = blob[start:m.end() + 120].strip()
            hits.append((p.url, snippet[:240]))
    return hits


def _questions(name: str) -> List[Tuple[str, str, List[str]]]:
    n = name
    return [
        ("identity", f"What is {n}?", [n.lower(), "we are", "we provide", "we build", "platform", "software", "agency"]),
        ("icp", f"Who is {n} for?", ["for ", "built for", "smb", "sme", "enterprise", "startup", "b2b", "buyer", "teams of", "employees"]),
        ("pricing", f"How much does {n} cost?", ["pricing", "price", "₹", "$", "/mo", "/month", "plan", "starting at", "contact sales"]),
        ("offering", f"What does {n} offer?", ["api", "feature", "service", "product", "integration", "module"]),
        ("trust", f"Can I trust {n}?", ["testimonial", "case study", "iso", "soc 2", "soc2", "gdpr", "client", "customer"]),
        ("compare", f"How does {n} compare to alternatives?", ["vs ", "versus", "alternative", "compared", "competitor", "unlike"]),
    ]


def _status_for(blob: str, needles: List[str], hits: List[Tuple[str, str]], key: str) -> str:
    low = blob.lower()
    found = [n for n in needles if n in low]
    if key == "pricing":
        amounts = {m.group(0).lower().replace(" ", "") for m in _PRICING_RE.finditer(blob)}
        if len(amounts) >= 2:
            return "CONFLICTING"
        if amounts:
            return "SUPPORTED"
        if "contact sales" in low or "request a quote" in low:
            return "PARTIAL"
        return "UNSUPPORTED"
    if hits and len(found) >= 2:
        return "SUPPORTED"
    if hits or found:
        return "PARTIAL"
    return "UNSUPPORTED"


def _band(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Multi-dimensional GEO scoring
# Each dimension returns a GeoDimensionScore.
# ---------------------------------------------------------------------------

def _score_entity_clarity(
    pages: List[PageEvidence],
    blob: str,
    name: str,
    profile: BusinessProfile,
    entity_res,
) -> GeoDimensionScore:
    low = blob.lower()
    fluff_hits = [w for w in _FLUFF if w in low]
    named = name.lower() in low if name else False
    specific = bool(profile.industry or profile.niche or profile.products or profile.services)

    base_score = 30.0
    if named:
        base_score += 20.0
    if specific:
        base_score += 20.0
    if not fluff_hits:
        base_score += 10.0
    else:
        base_score -= 10.0
    if entity_res and not entity_res.is_fragmented:
        base_score += 10.0
    elif entity_res and entity_res.is_fragmented:
        base_score -= 15.0

    score = max(0.0, min(100.0, base_score))
    summary = (
        f"{name} is named on-page with a specific category/offer."
        if (named and specific and not fluff_hits)
        else f"Identity is vague or fluff-heavy ({', '.join(fluff_hits[:3]) or 'no concrete category'})."
    )
    if entity_res and entity_res.is_fragmented:
        summary += f" Notice: {len(entity_res.discrepancies)} surface discrepancies ({entity_res.fragmentation_risk.lower()} risk)."

    return GeoDimensionScore(
        key=GeoDimensionKey.ENTITY_CLARITY.value,
        label="Entity clarity & consistency",
        score=round(score, 1),
        band=_band(score),
        confidence=0.85,
        summary=summary,
        evidence_notes=[
            f"business_name={name}",
            f"consistency_score={entity_res.overall_consistency_score if entity_res else 'N/A'}",
            f"fluff_words_detected={len(fluff_hits)}",
        ],
        is_measured=True,
        measurement_note=None,
    )


def _score_answerability(
    canonical_questions: List[GeoQuestionEvidence],
    q_graph_res,
) -> GeoDimensionScore:
    total = len(canonical_questions)
    supported = sum(1 for q in canonical_questions if q.status == "SUPPORTED")
    partial = sum(1 for q in canonical_questions if q.status == "PARTIAL")

    base_score = (supported / max(1, total)) * 60.0 + (partial / max(1, total)) * 20.0
    if q_graph_res:
        base_score = (base_score * 0.5) + (q_graph_res.answerability_score * 0.5)

    score = max(0.0, min(100.0, base_score))
    return GeoDimensionScore(
        key=GeoDimensionKey.ANSWERABILITY.value,
        label="Direct buyer question answerability",
        score=round(score, 1),
        band=_band(score),
        confidence=0.80,
        summary=f"{supported}/{total} buyer questions have explicit on-page answers. {partial} partial.",
        evidence_notes=[
            f"supported={supported}",
            f"partial={partial}",
            f"q_graph_score={q_graph_res.answerability_score if q_graph_res else 'N/A'}",
        ],
        is_measured=True,
        measurement_note=None,
    )


def _score_content_extractability(
    pages: List[PageEvidence],
    passage_res,
    supported: int,
) -> GeoDimensionScore:
    headings = sum(len(p.h2 or []) + len(p.h3 or []) for p in pages)
    heading_score = min(40.0, headings * 4.0)
    passage_score = (passage_res.citation_readiness_score * 0.40) if passage_res else 0.0
    question_score = min(20.0, supported * 5.0)
    score = max(0.0, min(100.0, heading_score + passage_score + question_score))

    summary = f"{headings} H2/H3 blocks; {supported} questions have quotable answers."
    if not pages:
        return GeoDimensionScore(
            key=GeoDimensionKey.CONTENT_EXTRACTABILITY.value,
            label="Content extractability & citation readiness",
            score=0.0,
            band="low",
            confidence=0.0,
            summary="Content extractability was not measured because no pages were available.",
            evidence_notes=["pages_analyzed=0"],
            is_measured=False,
            measurement_note="A successful crawl with at least one analyzed page is required.",
        )
    if passage_res:
        summary += f" {passage_res.highly_citable_count} highly citation-ready passages."

    return GeoDimensionScore(
        key=GeoDimensionKey.CONTENT_EXTRACTABILITY.value,
        label="Content extractability & citation readiness",
        score=round(score, 1),
        band=_band(score),
        confidence=0.80,
        summary=summary,
        evidence_notes=[
            f"h2_h3_count={headings}",
            f"citation_score={passage_res.citation_readiness_score if passage_res else 'NOT_MEASURED'}",
        ],
        is_measured=True,
        measurement_note=("Passage analyzer unavailable; score uses observed heading/question signals only."
                          if passage_res is None else None),
    )


def _score_citation_readiness(passage_res) -> GeoDimensionScore:
    if passage_res:
        raw = passage_res.citation_readiness_score
        count = passage_res.highly_citable_count
    else:
        return GeoDimensionScore(
            key=GeoDimensionKey.CITATION_READINESS.value,
            label="Citation-ready passage density",
            score=0.0,
            band="low",
            confidence=0.0,
            summary="Passage analysis unavailable; citation readiness was not measured.",
            evidence_notes=["highly_citable_count=NOT_MEASURED", "raw_score=NOT_MEASURED"],
            is_measured=False,
            measurement_note="A successful passage analysis is required to score citation readiness.",
        )

    score = max(0.0, min(100.0, raw))
    return GeoDimensionScore(
        key=GeoDimensionKey.CITATION_READINESS.value,
        label="Citation-ready passage density",
        score=round(score, 1),
        band=_band(score),
        confidence=0.75,
        summary=f"{count} highly citation-ready passages detected." if passage_res else "Passage analysis unavailable.",
        evidence_notes=[f"highly_citable_count={count}", f"raw_score={raw}"],
        is_measured=True,
        measurement_note=None,
    )


def _score_retrieval_accessibility(
    website_url: str,
    manifest: Optional[CrawlManifest],
) -> GeoDimensionScore:
    robots = bool(manifest and manifest.robots_txt_found)
    sitemap = bool(manifest and manifest.sitemap_found)
    https = (website_url or "").startswith("https://")

    score = 30.0
    if https:
        score += 30.0
    if robots:
        score += 20.0
    if sitemap:
        score += 20.0
    score = max(0.0, min(100.0, score))

    return GeoDimensionScore(
        key=GeoDimensionKey.RETRIEVAL_ACCESSIBILITY.value,
        label="Retrieval accessibility (HTTPS, robots, sitemap)",
        score=round(score, 1),
        band=_band(score),
        confidence=0.95,
        summary=f"https={https}, robots.txt={robots}, sitemap.xml={sitemap}.",
        evidence_notes=[f"https={https}", f"robots={robots}", f"sitemap={sitemap}"],
        is_measured=True,
        measurement_note=None,
    )


def _score_factual_grounding(
    claims_res,
    conflicting: int,
) -> GeoDimensionScore:
    if conflicting > 0:
        score = 20.0
        summary = f"{conflicting} conflicting commercial fact(s) detected. Contradictory signals reduce AI trust."
    elif claims_res:
        raw = min(100.0, claims_res.claim_clarity_score)
        score = raw
        summary = f"{claims_res.citable_claims_count} verified citable claims with no detected contradictions."
    else:
        return GeoDimensionScore(
            key=GeoDimensionKey.FACTUAL_GROUNDING.value,
            label="Factual grounding & claim verifiability",
            score=0.0,
            band="low",
            confidence=0.0,
            summary="Claim analysis unavailable; factual grounding was not measured.",
            evidence_notes=["conflicting_facts=0", "claim_clarity=NOT_MEASURED"],
            is_measured=False,
            measurement_note="Run claim extraction and evidence validation before scoring factual grounding.",
        )

    return GeoDimensionScore(
        key=GeoDimensionKey.FACTUAL_GROUNDING.value,
        label="Factual grounding & claim verifiability",
        score=max(0.0, min(100.0, score)),
        band=_band(score),
        confidence=0.70 if not claims_res else 0.80,
        summary=summary,
        evidence_notes=[
            f"conflicting_facts={conflicting}",
            f"claim_clarity={claims_res.claim_clarity_score if claims_res else 'N/A'}",
        ],
        is_measured=True,
        measurement_note=None,
    )


def _score_external_authority(entity_res) -> GeoDimensionScore:
    """
    External authority cannot be measured from HTML crawl alone.
    Requires external API (backlinks, directory presence, GSC).
    This dimension is explicitly NOT_MEASURED when no connector ran.
    """
    return GeoDimensionScore(
        key=GeoDimensionKey.EXTERNAL_AUTHORITY.value,
        label="External authority & backlink signals",
        score=0.0,   # Placeholder value is ignored because is_measured=False
        band="low",
        confidence=0.0,
        summary=(
            "External authority cannot be measured from on-page HTML crawl. "
            "This requires GSC, backlink API, or business directory connector data. "
            "No score is reported until external connector data are available."
        ),
        evidence_notes=["requires_connector=GSC or backlink API"],
        is_measured=False,
        measurement_note=(
            "Connect Google Search Console or a backlink data provider "
            "to measure external authority with evidence."
        ),
    )


def _score_ai_engine_visibility(
    visibility_measured: bool,
    visibility_detail: Optional[str],
    visibility_score: Optional[float] = None,
) -> GeoDimensionScore:
    """
    AI engine visibility can ONLY be scored if a live connector ran
    and returned a rate. NEVER infer from HTML, and never use a placeholder.
    """
    if visibility_measured and visibility_score is not None:
        score = max(0.0, min(100.0, float(visibility_score)))
        return GeoDimensionScore(
            key=GeoDimensionKey.AI_ENGINE_VISIBILITY.value,
            label="Live AI citation visibility",
            score=score,
            band=_band(score),
            confidence=0.90,
            summary=visibility_detail or (
                f"Live AI citation visibility is {score:.0f}/100 from successful engine responses. "
                "This is not the on-page GEO Readiness score."
            ),
            evidence_notes=["source=live_engine_connector"],
            is_measured=True,
            measurement_note=None,
        )
    else:
        return GeoDimensionScore(
            key=GeoDimensionKey.AI_ENGINE_VISIBILITY.value,
            label="Live AI engine citation visibility",
            score=0.0,
            band="low",
            confidence=0.0,
            summary=(
                "Live AI engine visibility was NOT measured in this audit run. "
                "Connect the Live AI Search connector to query Perplexity, ChatGPT, "
                "Gemini, and Claude with real queries against the target domain."
            ),
            evidence_notes=["requires_connector=live_ai_search"],
            is_measured=False,
            measurement_note=(
                "Activate the 'Live AI Search' connector under Settings → Connectors "
                "to enable direct citation measurement."
            ),
        )


# Dimension weights for composite score
# NOTE: AI_ENGINE_VISIBILITY is excluded from composite when not measured
_WEIGHTS: Dict[str, float] = {
    GeoDimensionKey.ENTITY_CLARITY.value:          0.20,
    GeoDimensionKey.ANSWERABILITY.value:           0.25,
    GeoDimensionKey.CONTENT_EXTRACTABILITY.value:  0.15,
    GeoDimensionKey.CITATION_READINESS.value:      0.15,
    GeoDimensionKey.RETRIEVAL_ACCESSIBILITY.value: 0.10,
    GeoDimensionKey.FACTUAL_GROUNDING.value:       0.15,
    GeoDimensionKey.EXTERNAL_AUTHORITY.value:      0.00,  # 0 weight when not measured
    GeoDimensionKey.AI_ENGINE_VISIBILITY.value:    0.00,  # 0 weight when not measured
}


def _compute_composite(dimension_scores: Dict[str, GeoDimensionScore]) -> Optional[float]:
    """Weighted composite of measured dimensions only."""
    total_weight = 0.0
    total_score = 0.0
    for key, ds in dimension_scores.items():
        weight = _WEIGHTS.get(key, 0.0)
        if ds.is_measured and weight > 0.0:
            total_score += ds.score * weight
            total_weight += weight
    if total_weight == 0.0:
        return None  # Cannot compute is not a neutral score.
    return round(total_score / total_weight, 1)


def evaluate_geo_readiness(
    *,
    website_url: str,
    pages: List[PageEvidence],
    manifest: Optional[CrawlManifest] = None,
    profile: Optional[BusinessProfile] = None,
    visibility_measured: bool = False,
    visibility_detail: Optional[str] = None,
    visibility_score: Optional[float] = None,
    country: Optional[str] = None,
    language: Optional[str] = None,
    extended_questions: bool = False,
    entity_graph: Optional[EntityGraphReport] = None,
) -> GeoReadinessReport:
    profile = profile or BusinessProfile()
    name = profile.business_name if profile.business_name not in ("Unknown", "Unknown Business", "") else ""
    if not name:
        host = urlparse(website_url or "").netloc.replace("www.", "")
        name = host.split(".")[0].capitalize() if host else "the company"

    # An empty crawl is not evidence that the site's content is poor. Fail closed
    # before generating unsupported-question findings or heuristic scores.
    if not pages:
        return GeoReadinessReport(
            entity_name=name,
            visibility_status="MEASURED" if visibility_measured and visibility_score is not None else "NOT_CONFIGURED",
            visibility_message=(
                visibility_detail or "Live visibility is measured separately from on-page readiness."
                if visibility_measured and visibility_score is not None
                else "No live AI-engine measurement was supplied for this run."
            ),
            questions_total=0,
            questions_supported=0,
            questions_partial=0,
            questions_unsupported=0,
            questions_conflicting=0,
            headline="GEO readiness unavailable: the crawl produced no analyzed pages. Retry the crawl before interpreting readiness.",
            questions=[],
            dimensions=[],
            dimension_scores={},
            schema_types=[],
            extractability_score=None,
            market_country=(country or "Global").strip() or "Global",
            market_language=(language or "en").strip() or "en",
        )

    blob = _corpus(pages)

    # ------------------------------------------------------------------
    # 1. Canonical 6-Question Evaluation
    # ------------------------------------------------------------------
    category_map = {
        "identity": "Entity Identity",
        "icp": "Target Audience & ICP",
        "pricing": "Pricing & Commercial Terms",
        "offering": "Core Capabilities & Services",
        "trust": "Security, Trust & Compliance",
        "compare": "Comparative & Differentiators",
    }
    canonical_questions: List[GeoQuestionEvidence] = []
    for key, q, needles in _questions(name):
        pattern = re.compile("|".join(re.escape(n) for n in needles if n.strip()), re.I)
        hits = _page_hits(pages, pattern) if needles else []
        status = _status_for(blob, needles, hits, key)
        url, snippet = hits[0] if hits else (None, None)
        why = {
            "SUPPORTED": "A crawled page contains an explicit, extractable statement for this question.",
            "PARTIAL": "Related words appear, but there is no self-contained answer a model can quote.",
            "UNSUPPORTED": "The crawled sample does not contain an answer to this buyer question.",
            "CONFLICTING": "Multiple distinct price/value strings appear across the crawled sample.",
        }[status]
        cat = category_map.get(key, "General")
        ans = (
            f"According to {name}'s crawled pages: \"{snippet.strip()}\""
            if status == "SUPPORTED" and snippet
            else (f"Partially mentioned on {name}'s website." if status == "PARTIAL" else f"No direct answer found on crawled pages for {name}.")
        )
        rec = None if status == "SUPPORTED" else f"Publish explicit on-page answers for {q} to secure generative search citations."
        canonical_questions.append(GeoQuestionEvidence(
            question_key=key,
            question=q,
            category=cat,
            status=status,
            answer=ans,
            answer_snippet=snippet,
            evidence_url=url,
            evidence_snippet=snippet,
            why=why,
            recommended_answer=rec,
        ))

    supported = sum(1 for q in canonical_questions if q.status == "SUPPORTED")
    partial = sum(1 for q in canonical_questions if q.status == "PARTIAL")
    unsupported = sum(1 for q in canonical_questions if q.status == "UNSUPPORTED")
    conflicting = sum(1 for q in canonical_questions if q.status == "CONFLICTING")

    # ------------------------------------------------------------------
    # 2. Deep Extractability Engines
    # ------------------------------------------------------------------
    try:
        entity_res = entity_consistency_analyzer.analyze(pages, website_url=website_url, profile=profile)
    except Exception:
        entity_res = None

    try:
        claims_res = claim_extractor.extract_claims(pages, brand_name=name)
    except Exception:
        claims_res = None

    try:
        q_graph_res = question_graph_engine.evaluate_graph(pages, brand_name=name, website_url=website_url, profile=profile)
    except Exception:
        q_graph_res = None

    try:
        passage_res = passage_analyzer.analyze(pages, brand_name=name)
    except Exception:
        passage_res = None

    schema_res = entity_graph
    if schema_res is None:
        try:
            schema_res, _, _ = evaluate_entity_graph(pages, brand_name=name)
        except Exception:
            schema_res = None

    # ------------------------------------------------------------------
    # 3. Multi-Dimensional Scoring (v2)
    # ------------------------------------------------------------------
    dim_scores: Dict[str, GeoDimensionScore] = {}

    dim_scores[GeoDimensionKey.ENTITY_CLARITY.value] = _score_entity_clarity(
        pages, blob, name, profile, entity_res
    )
    dim_scores[GeoDimensionKey.ANSWERABILITY.value] = _score_answerability(
        canonical_questions, q_graph_res
    )
    dim_scores[GeoDimensionKey.CONTENT_EXTRACTABILITY.value] = _score_content_extractability(
        pages, passage_res, supported
    )
    dim_scores[GeoDimensionKey.CITATION_READINESS.value] = _score_citation_readiness(passage_res)
    dim_scores[GeoDimensionKey.RETRIEVAL_ACCESSIBILITY.value] = _score_retrieval_accessibility(
        website_url, manifest
    )
    dim_scores[GeoDimensionKey.FACTUAL_GROUNDING.value] = _score_factual_grounding(
        claims_res, conflicting
    )
    dim_scores[GeoDimensionKey.EXTERNAL_AUTHORITY.value] = _score_external_authority(entity_res)
    dim_scores[GeoDimensionKey.AI_ENGINE_VISIBILITY.value] = _score_ai_engine_visibility(
        visibility_measured, visibility_detail, visibility_score
    )

    # Composite extractability score from measured dimensions
    extractability_score = _compute_composite(dim_scores)

    # ------------------------------------------------------------------
    # 4. Schema types
    # ------------------------------------------------------------------
    schema_types = sorted({t for p in pages for t in (p.schema_types or [])})
    if schema_res and schema_res.summary:
        schema_summary = schema_res.summary
    else:
        schema_summary = (
            f"Schema.org types observed: {', '.join(schema_types) or 'none'}. "
            "Schema is a machine-readable evidence layer, not a GEO score."
        )

    # ------------------------------------------------------------------
    # 5. Legacy dimensions list (backwards-compat with existing report views)
    # ------------------------------------------------------------------
    legacy_dimensions = [
        GeoDimension(
            key=ds.key,
            label=ds.label,
            band=ds.band,
            summary=ds.summary,
            evidence_notes=ds.evidence_notes,
        )
        for ds in dim_scores.values()
    ]
    legacy_dimensions.append(
        GeoDimension(
            key="structured_data",
            label="Structured Data Grounding",
            band="medium" if schema_types else "low",
            summary=f"{schema_summary} Structured data is a machine-readable evidence layer, not proof of GEO readiness.",
            evidence_notes=[f"schema_types={len(schema_types)}"],
        )
    )

    # ------------------------------------------------------------------
    # 6. Headline
    # ------------------------------------------------------------------
    headline = (
        f"{supported} of {len(canonical_questions)} high-value buyer questions have explicit on-page answers"
        f"{f'; {partial} partial' if partial else ''}"
        f"{f'; {conflicting} conflicting' if conflicting else ''}"
        f"{f'; {unsupported} cannot be answered from the crawled site' if unsupported else ''}."
    )

    visibility_status = "MEASURED" if visibility_measured else "NOT_CONFIGURED"
    if visibility_measured:
        visibility_message = visibility_detail or (
            "Live engine visibility was measured by the citation tracker or GEO pipeline. "
            "This number is not inferred from HTML."
        )
    else:
        visibility_message = (
            "Visibility data unavailable — connector/API access required. "
            "This report measures GEO Readiness (can an engine extract answers from the site), "
            "not GEO Visibility (does ChatGPT/Perplexity/AI Overviews actually cite you)."
        )

    active_questions = (
        q_graph_res.questions if (extended_questions and q_graph_res and q_graph_res.questions)
        else canonical_questions
    )

    return GeoReadinessReport(
        visibility_status=visibility_status,
        visibility_message=visibility_message,
        entity_name=name,
        questions_total=len(active_questions),
        questions_supported=sum(1 for q in active_questions if q.status == "SUPPORTED"),
        questions_partial=sum(1 for q in active_questions if q.status == "PARTIAL"),
        questions_unsupported=sum(1 for q in active_questions if q.status == "UNSUPPORTED"),
        questions_conflicting=sum(1 for q in active_questions if q.status == "CONFLICTING"),
        headline=headline,
        questions=active_questions,
        dimensions=legacy_dimensions,
        dimension_scores=dim_scores,
        schema_types=schema_types,
        market_country=(country or "Global").strip() or "Global",
        market_language=(language or "en").strip() or "en",
        extractability_score=extractability_score,
        entity_consistency=entity_res.model_dump() if entity_res else None,
        claims_analysis=claims_res.model_dump() if claims_res else None,
        question_graph_50=q_graph_res.model_dump() if q_graph_res else None,
        citation_passages=passage_res.model_dump() if passage_res else None,
        schema_crosscheck=schema_res.model_dump() if schema_res else None,
    )


async def enrich_geo_readiness_citations(
    report: GeoReadinessReport,
    model_router: Any,
    brand_name: str,
    domain: str,
    profile: Optional[Any] = None,
) -> GeoReadinessReport:
    """Enriches citation passage rewrites with LLM when available."""
    if not model_router or not getattr(report, "citation_passages", None):
        return report
    try:
        from app.geo.citation_passages import (
            passage_analyzer,
            CitationPassageAnalysisResult,
        )
        curr_passages = report.citation_passages
        if isinstance(curr_passages, dict):
            parsed = CitationPassageAnalysisResult(**curr_passages)
            enriched = await passage_analyzer.enrich_rewrites_with_llm(
                parsed,
                model_router=model_router,
                brand_name=brand_name,
                domain=domain,
                profile=profile,
            )
            report.citation_passages = enriched.model_dump()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to enrich citation rewrites with LLM: %s", exc)
    return report
