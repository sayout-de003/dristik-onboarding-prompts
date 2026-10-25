"""
Per-page SEO, copywriting, and UX intelligence.
Runs once for every crawled URL and returns a detailed page report
with suggested copy even when the LLM is unavailable.
"""
from __future__ import annotations

import asyncio
import json
import re
import logging
from typing import Any, Dict, List, Optional

from app.orchestration.runtime.base import BaseAgent
from app.orchestration.runtime.task_cards import task_card_for
from app.orchestration.cognition.blackboard import CognitiveBlackboard
from app.domain.enums import Category, Severity
from app.domain.evidence.models import Evidence
from app.core.inference.prompt_compiler import load_prompt
from app.domain.models import (
    BusinessProfile,
    CopyFaqItem,
    CopyIssue,
    CopySection,
    PageCopyAudit,
    PageEvidence,
    PageReport,
    PageSeoAudit,
    PageUxSignals,
    SuggestedCopy,
)

logger = logging.getLogger("dristik.page_intelligence")

WORD_TARGETS = {
    "homepage": 400,
    "pricing": 250,
    "product": 350,
    "about": 300,
    "contact": 120,
    "docs": 400,
    "blog": 600,
    "legal": 200,
    "general": 250,
}

# Observed CTAs only. Do not invent a trial/demo button that is not on the page.
WEAK_CTAS = {"submit", "click here", "learn more", "read more", "here", "click"}
PAIN_MARKERS = re.compile(
    r"\b(problem|challenge|struggle|pain|without|bottleneck|friction|slow|manual|fragmented|waste|risk|fail)\b",
    re.I,
)


def _clip(text: Optional[str], n: int) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    if len(value) <= n:
        return value
    cut = value[: n - 1].rsplit(" ", 1)[0]
    return (cut or value[: n - 1]).rstrip(".,;:") + "…"


def _sentences(text: str, limit: int = 3) -> List[str]:
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
    return parts[:limit]


def _status_len(value: Optional[str], low: int, high: int, missing: str = "missing") -> str:
    if not value or not value.strip():
        return missing
    length = len(value.strip())
    if length < low:
        return "too_short"
    if length > high:
        return "too_long"
    return "good"


def audit_page_seo(page: PageEvidence) -> PageSeoAudit:
    issues: List[str] = []
    strengths: List[str] = []
    recs: List[str] = []
    score = 100.0

    title = (page.title or "").strip()
    meta = (page.meta_description or "").strip()
    title_status = _status_len(title, 30, 60)
    meta_status = _status_len(meta, 110, 160)
    title_len = len(title)
    meta_len = len(meta)

    if title_status == "missing":
        issues.append("Title tag is missing.")
        recs.append("Write a unique 50–60 character title that names the page offer.")
        score -= 18
    elif title_status == "too_short":
        issues.append(f"Title is short ({title_len} characters).")
        recs.append("Expand the title with the primary keyword and a benefit.")
        score -= 8
    elif title_status == "too_long":
        issues.append(f"Title may truncate in SERPs ({title_len} characters).")
        recs.append("Shorten the title to about 50–60 characters.")
        score -= 5
    else:
        strengths.append("Title length is in a healthy range.")

    if meta_status == "missing":
        issues.append("Meta description is missing.")
        recs.append("Add a 140–160 character description with offer, proof, and CTA.")
        score -= 14
    elif meta_status == "too_short":
        issues.append(f"Meta description is short ({meta_len} characters).")
        recs.append("Write a fuller snippet so search listings are not auto-generated.")
        score -= 6
    elif meta_status == "too_long":
        issues.append(f"Meta description may truncate ({meta_len} characters).")
        recs.append("Keep the description under 160 characters.")
        score -= 4
    else:
        strengths.append("Meta description length is usable.")

    h1_count = len(page.h1)
    if h1_count == 0:
        h1_status = "missing"
        issues.append("No H1 heading on the page.")
        recs.append("Add one H1 that states the page promise in plain language.")
        score -= 16
    elif h1_count > 1:
        h1_status = "multiple"
        issues.append(f"{h1_count} H1 headings found; search engines prefer one.")
        recs.append("Keep a single H1 and demote the rest to H2.")
        score -= 8
    else:
        h1_status = "good"
        strengths.append("Single H1 is present.")

    heading_bits = []
    if page.h2:
        heading_bits.append(f"{len(page.h2)} H2")
    if page.h3:
        heading_bits.append(f"{len(page.h3)} H3")
    heading_structure = ", ".join(heading_bits) if heading_bits else "No subheadings"
    if not page.h2 and page.word_count > 200:
        issues.append("Long copy without H2 subheadings.")
        recs.append("Break the page into scannable H2 sections.")
        score -= 6
    elif page.h2:
        strengths.append("Subheadings give the page structure.")

    if page.canonical_url:
        canonical_status = "present"
        strengths.append("Canonical URL is set.")
    else:
        canonical_status = "missing"
        issues.append("Canonical tag is missing.")
        recs.append("Add a self-referential canonical for this URL.")
        score -= 7

    robots = (page.robots_meta or "").lower()
    if "noindex" in robots:
        robots_status = "noindex"
        indexability = "blocked"
        issues.append("robots meta is set to noindex.")
        recs.append("Remove noindex if this page should rank.")
        score -= 20
    else:
        robots_status = "indexable"
        indexability = "indexable"

    if page.og_tags.get("og:title") or page.og_tags.get("og:description"):
        og_status = "partial" if not (page.og_tags.get("og:title") and page.og_tags.get("og:description")) else "present"
        strengths.append("Open Graph tags are present.")
    else:
        og_status = "missing"
        issues.append("Open Graph tags are missing.")
        recs.append("Add og:title, og:description, and og:image.")
        score -= 5

    if page.schema_types:
        schema_status = "present"
        strengths.append(f"Schema types: {', '.join(page.schema_types[:4])}.")
    else:
        schema_status = "missing"
        issues.append("No structured data on this page.")
        recs.append("Add JSON-LD that matches the page type (Organization, Product, FAQ, Article).")
        score -= 8

    if not page.viewport:
        issues.append("Viewport meta is missing.")
        recs.append("Add a mobile viewport tag.")
        score -= 6

    target = WORD_TARGETS.get(page.page_type, 250)
    if page.word_count < max(80, int(target * 0.45)):
        issues.append(f"Thin copy ({page.word_count} words; target ~{target}).")
        recs.append("Add substance: proof, specifics, and answers to buyer questions.")
        score -= 10
    else:
        strengths.append(f"{page.word_count} words of on-page copy.")

    if page.images_without_alt and page.total_images:
        issues.append(f"{page.images_without_alt}/{page.total_images} images missing alt text.")
        recs.append("Write descriptive alt text for every meaningful image.")
        score -= min(8, page.images_without_alt * 2)

    if page.status_code and page.status_code >= 400:
        issues.append(f"HTTP status {page.status_code}.")
        score -= 25
        indexability = "error"

    return PageSeoAudit(
        score=max(0.0, min(100.0, round(score, 1))),
        title_status=title_status,
        title_length=title_len,
        meta_status=meta_status,
        meta_length=meta_len,
        h1_status=h1_status,
        heading_structure=heading_structure,
        canonical_status=canonical_status,
        robots_status=robots_status,
        og_status=og_status,
        schema_status=schema_status,
        indexability=indexability,
        issues=issues,
        strengths=strengths,
        recommendations=recs,
    )


def audit_page_ux(page: PageEvidence) -> PageUxSignals:
    return PageUxSignals(
        cta_count=len(page.ctas or []),
        ctas=list(page.ctas or [])[:8],
        images_missing_alt=page.images_without_alt,
        total_images=page.total_images,
        internal_links=len(page.internal_links or []),
        external_links=len(page.external_links or []),
        ttfb_ms=page.ttfb_ms or 0.0,
        readability=page.readability_score or 0.0,
        word_count=page.word_count or 0,
        viewport=page.viewport,
        scripts_count=page.scripts_count or 0,
    )


NAV_NOISE = re.compile(
    r"(about us.{0,24}careers|careers.{0,24}blog|sign in|log in|cookie settings|company\s*>\s*about)",
    re.I,
)
KICKER_NOISE = re.compile(
    r"(legal\s*//|system module|system status|protocol|initialize handshake|mission brief|click to start|system_intake)",
    re.I,
)


def _clean_lead(body: str, h1: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n+", body or "") if b.strip()]
    if not blocks:
        blocks = _sentences(re.sub(r"\s+", " ", body or ""), 8)
    picked = []
    for sentence in blocks:
        lowered = sentence.lower()
        if len(sentence) < 40:
            continue
        if h1 and sentence.lower().replace(" ", "").startswith(h1.lower().replace(" ", "")[:12]):
            if len(sentence) < 80:
                continue
        if KICKER_NOISE.search(sentence) and len(sentence) < 90:
            continue
        if NAV_NOISE.search(sentence) and len(sentence) < 120:
            continue
        if sentence.count(">") >= 2 or sentence.count("|") >= 2:
            continue
        if sentence.isupper() and len(sentence) < 80:
            continue
        picked.append(re.sub(r"\s+", " ", sentence))
        if len(picked) >= 2:
            break
    return " ".join(picked)


def _pain_sentences(body: str) -> List[str]:
    found = []
    for sentence in _sentences(re.sub(r"\s+", " ", body or ""), 20):
        if PAIN_MARKERS.search(sentence) and 40 <= len(sentence) <= 240:
            found.append(sentence)
        if len(found) >= 2:
            break
    return found


def _answer_for_heading(body: str, heading: str) -> Optional[str]:
    if not heading or not body:
        return None
    tokens = [t for t in re.findall(r"[A-Za-z]{4,}", heading.lower()) if t not in {"this", "that", "with", "from", "your"}]
    if not tokens:
        return None
    for sentence in _sentences(re.sub(r"\s+", " ", body), 40):
        low = sentence.lower()
        if any(t in low for t in tokens) and 40 <= len(sentence) <= 280:
            return sentence
    return None


def _build_default_sections(
    page: PageEvidence,
    profile: BusinessProfile,
    h1: str,
    hero: str,
    primary_cta: str,
    secondary_cta: Optional[str],
    points: List[str],
    brand: str,
) -> List[CopySection]:
    offer = profile.value_proposition if profile.value_proposition and "not clearly" not in profile.value_proposition.lower() else ""
    brand_label = brand or (page.title or "this page")
    current_h1 = page.h1[0] if page.h1 else (page.title or "No H1 on this URL")
    hero_status = "NEEDS_REWRITE" if (not page.h1 or len(page.h1[0]) > 80 or len(page.h1[0]) < 15) else "UPDATE_RECOMMENDED"
    body = page.body_text or ""
    pain = _pain_sentences(body)
    faq_on_page = "faq" in body.lower() or any("faq" in t.lower() for t in (page.schema_types or []))

    if pain:
        problem_status = "UPDATE_RECOMMENDED"
        problem_preview = pain[0][:160]
        problem_copy = " ".join(pain)
    else:
        problem_status = "NEEDS_REWRITE"
        problem_preview = "NOT_IN_EVIDENCE: no problem/pain paragraph on this URL."
        problem_copy = (
            "NOT_IN_EVIDENCE on this URL. Do not invent a bottleneck story. "
            "Add a short paragraph that names the buyer’s real problem using language already true for this offer: "
            f"{offer or h1}."
        )

    if points:
        solution_preview = ", ".join(points[:3])
        solution_copy = (f"{brand_label}: {offer}\n" if offer else f"{brand_label}\n") + "\n".join(f"• {p}" for p in points[:4])
        solution_status = "UPDATE_RECOMMENDED"
    else:
        solution_preview = "NOT_IN_EVIDENCE: no H2 capability list on this URL."
        solution_copy = "NOT_IN_EVIDENCE. Add H2s that name actual offerings from the business, then one sentence of proof under each. Do not invent capabilities."
        solution_status = "NEEDS_REWRITE"

    faq_lines = []
    for heading in points[:3]:
        ans = _answer_for_heading(body, heading)
        faq_lines.append(f"Q: What is {heading}?\nA: {ans}" if ans else f"Q: What is {heading}?\nA: NOT_IN_EVIDENCE on this URL — the heading exists but no defining sentence was crawled.")
    if not faq_lines:
        faq_lines.append(
            f"Q: What is {brand_label}?\nA: {offer or hero or h1 or 'NOT_IN_EVIDENCE: no definition sentence on this URL.'}"
        )
    faq_status = "UPDATE_RECOMMENDED" if faq_on_page or any("NOT_IN_EVIDENCE" not in line for line in faq_lines) else "NEEDS_REWRITE"

    cta_preview = primary_cta or "NOT_IN_EVIDENCE: no CTA detected."
    cta_copy = (
        f"Keep the observed action: {primary_cta}"
        + (f"\nSecondary observed: {secondary_cta}" if secondary_cta else "")
        if primary_cta
        else "NOT_IN_EVIDENCE: add one primary action that names the next step already true for this page (quote, call, trial, or purchase)."
    )

    return [
        CopySection(
            section_id="hero",
            section_name="Hero & Opening Hook",
            status=hero_status,
            current_preview=f"Headline: {current_h1[:90]}",
            suggested_copy=f"Headline: {h1}\nSubhead: {hero or 'NOT_IN_EVIDENCE: no lead paragraph crawled.'}\nPrimary Action: {primary_cta or 'NOT_IN_EVIDENCE'}",
            purpose="State buyer, offer, and outcome in the first screen using words already on the page.",
            seo_geo_notes="Rewrite only from observed H1/title/body. Do not add metrics or features that were not crawled.",
            keywords=[k for k in [brand_label, page.page_type] if k],
        ),
        CopySection(
            section_id="problem",
            section_name="Problem Agitation & Commercial Friction",
            status=problem_status,
            current_preview=problem_preview,
            suggested_copy=problem_copy,
            purpose="Quote the buyer problem if the page states it; otherwise mark the gap.",
            seo_geo_notes="Pain copy must be a quote or NOT_IN_EVIDENCE. Never invent industry-generic bottlenecks.",
            keywords=["problem"] + ([pain[0][:40]] if pain else []),
        ),
        CopySection(
            section_id="solution",
            section_name="Solution Architecture & Core Capabilities",
            status=solution_status,
            current_preview=solution_preview,
            suggested_copy=solution_copy,
            purpose="List only offerings that appear as H2s or stated value proposition.",
            seo_geo_notes="Each bullet is an observed heading. Empty list = missing information architecture.",
            keywords=points[:4],
        ),
        CopySection(
            section_id="geo_faq",
            section_name="AI Answer Engine FAQ Block",
            status=faq_status,
            current_preview="FAQ markup present." if faq_on_page else "No FAQPage schema or FAQ copy on this URL.",
            suggested_copy="\n\n".join(faq_lines),
            purpose="Give answer engines a Q/A pair only when the answer is on the page.",
            seo_geo_notes="Answers marked NOT_IN_EVIDENCE must be written from real facts before FAQ schema is shipped.",
            keywords=["FAQ"] + points[:3],
        ),
        CopySection(
            section_id="cta_banner",
            section_name="Closing Conversion Banner",
            status="UPDATE_RECOMMENDED" if primary_cta else "NEEDS_REWRITE",
            current_preview=cta_preview,
            suggested_copy=cta_copy,
            purpose="Repeat the observed primary action. Do not invent a trial if the page has none.",
            seo_geo_notes="CTA text must match a crawled button or be labeled missing.",
            keywords=[primary_cta] if primary_cta else [],
        ),
    ]


def _build_default_faqs(
    brand: str,
    offer: str,
    audience: str,
    page: Optional[PageEvidence] = None,
) -> List[CopyFaqItem]:
    b = brand or ((page.title or "").split("|")[0].strip() if page else "") or "this site"
    headline = (page.h1[0] if page and page.h1 else (page.title if page else "") or "").strip()
    subtopics = [h.strip() for h in (page.h2 or []) if h.strip() and len(h.strip()) < 80][:4] if page else []
    meta_desc = (page.meta_description or "").strip() if page else ""
    page_cta = (page.ctas[0].strip() if page and page.ctas else "")
    body = (page.body_text or "") if page else ""
    clean_offer = offer if (offer and "unknown" not in offer.lower() and "not clearly" not in offer.lower()) else (meta_desc or headline)

    items: List[CopyFaqItem] = []
    a1 = _answer_for_heading(body, headline) if headline else None
    items.append(CopyFaqItem(
        question=f"What is {b}?" if b else f"What is this page about?",
        answer=a1 or clean_offer or "NOT_IN_EVIDENCE: no definition sentence on this URL.",
        target_engine="ChatGPT / Perplexity / Gemini / Google AI Overviews",
    ))

    if audience and "unknown" not in audience.lower():
        a2 = f"The page addresses {audience}." + (f" Offer stated as: {clean_offer}" if clean_offer else "")
    else:
        a2 = "NOT_IN_EVIDENCE: this URL does not name a buyer role."
    items.append(CopyFaqItem(
        question=f"Who is {b} for?" if b else "Who is this page for?",
        answer=a2,
        target_engine="Perplexity Search & Google AI Overviews",
    ))

    if page_cta:
        a3 = f"The observed call to action on this URL is '{page_cta}'."
    elif subtopics:
        defined = [_answer_for_heading(body, h) for h in subtopics[:2]]
        a3 = " ".join(d for d in defined if d) or f"On-page sections: {', '.join(subtopics)}. No further definition crawled."
    else:
        a3 = "NOT_IN_EVIDENCE: no next step or capability definition on this URL."
    items.append(CopyFaqItem(
        question=f"How do I get started with {b}?" if page_cta else (f"What does {b} cover?" if subtopics else f"What should a buyer do on this page?"),
        answer=a3,
        target_engine="ChatGPT Search & Claude",
    ))
    return items


def _build_default_geo_snippet(
    brand: str,
    offer: str,
    audience: str,
    page: Optional[PageEvidence] = None,
) -> str:
    lead = _clean_lead((page.body_text or "") if page else "", (page.h1[0] if page and page.h1 else ""))
    bits = []
    if brand:
        bits.append(brand)
    if offer and "not clearly" not in offer.lower():
        bits.append(offer)
    elif page and (page.meta_description or page.h1):
        bits.append((page.meta_description or page.h1[0]).strip())
    if audience and "unknown" not in audience.lower():
        bits.append(f"For {audience}.")
    if page and page.h2:
        bits.append("On-page sections: " + ", ".join([h.strip() for h in page.h2 if h.strip()][:3]) + ".")
    snippet = lead or " ".join(bits)
    return _clip(snippet, 420) if snippet else "NOT_IN_EVIDENCE: no extractable definition on this URL."


def _fallback_suggested(page: PageEvidence, profile: BusinessProfile) -> SuggestedCopy:
    brand = (profile.business_name or "").strip()
    if brand.lower() in {"unknown", "unknown business", ""}:
        brand = ""
    offer = profile.value_proposition if profile.value_proposition and "not clearly" not in profile.value_proposition.lower() else ""
    h1 = (page.h1[0] if page.h1 else page.title or "What this page is for").strip()
    observed_ctas = [re.sub(r"\s+", " ", c).strip() for c in (page.ctas or []) if c and c.strip()]
    intent = (profile.primary_intent.value if hasattr(profile.primary_intent, "value") else str(profile.primary_intent or "")).lower()
    default_cta = "Get in touch" if "lead" in intent else ("Get started" if "saas" in intent else "Contact us")
    primary = observed_ctas[0] if observed_ctas else default_cta
    secondary = observed_ctas[1] if len(observed_ctas) > 1 else None

    legal = page.page_type == "legal"
    title_core = h1
    current_title = (page.title or "").strip()
    if legal and current_title:
        title = current_title
    else:
        title = f"{title_core} | {brand}" if brand and brand.lower() not in title_core.lower() else title_core
        title = _clip(title, 60)

    body = page.body_text or ""
    hero_src = _clean_lead(body, h1) or ("" if legal else offer) or h1
    hero = _clip(hero_src, 280)

    hook_3sec = f"{brand + ': ' if brand else ''}{offer or h1}"
    geo_snippet = _build_default_geo_snippet(brand, offer, profile.target_audience, page=page)
    faq_items = _build_default_faqs(brand, offer, profile.target_audience, page=page)

    if legal:
        meta = (page.meta_description or "").strip() or _clip(hero, 155)
        notes = "Legal page: keep current policy language; only tighten headings and opening summary."
        points = [h.strip() for h in (page.h2 or []) if h.strip()][:6]
        body_rewrite = "\n\n".join([h1, hero] + points[:6])
        legal_cta = primary if page.ctas and primary.lower() not in {"contact", "get a quote", "start free trial"} else ""
        sections_list = _build_default_sections(
            page=page,
            profile=profile,
            h1=h1,
            hero=hero,
            primary_cta=legal_cta,
            secondary_cta=None,
            points=points,
            brand=brand,
        )
        return SuggestedCopy(
            title=title,
            meta_description=_clip(meta, 160),
            h1=_clip(h1, 80),
            hero=hero,
            primary_cta=legal_cta,
            secondary_cta=None,
            supporting_points=points,
            body_rewrite=body_rewrite,
            geo_snippet=geo_snippet,
            hook_3sec=hook_3sec,
            sections=sections_list,
            faq_items=faq_items,
            notes=notes,
        )

    meta_src = (page.meta_description or "").strip() or offer or hero or h1
    meta = _clip(meta_src, 155)
    points = [h.strip() for h in (page.h2 or []) if h.strip()][:4]
    if len(points) < 2 and offer:
        points.append(offer)

    sections_text = [h1, hero]
    if points:
        sections_text.append("\n".join(f"- {p}" for p in points[:4]))
    if offer:
        sections_text.append(offer)
    sections_text.append(primary)
    body_rewrite = "\n\n".join(s for s in sections_text if s)

    sections_list = _build_default_sections(
        page=page,
        profile=profile,
        h1=h1,
        hero=hero,
        primary_cta=primary,
        secondary_cta=secondary,
        points=points,
        brand=brand,
    )

    return SuggestedCopy(
        title=title,
        meta_description=meta,
        h1=_clip(h1, 70),
        hero=hero,
        primary_cta=primary,
        secondary_cta=secondary,
        supporting_points=points[:5],
        body_rewrite=body_rewrite,
        geo_snippet=geo_snippet,
        hook_3sec=hook_3sec,
        sections=sections_list,
        faq_items=faq_items,
        notes="Deterministic draft from crawled title, headings, CTAs, and body. LLM rewrite runs when a model key is present. Nothing here is an invented feature, metric, or testimonial.",
    )


def _compute_geo_score(page: PageEvidence) -> float:
    """Deterministic extractability score from this URL only. Not a live citation rate."""
    score = 20.0
    body = (page.body_text or "")
    if any(t.lower() in {"faqpage", "question", "qapage"} for t in (page.schema_types or [])):
        score += 25
    if "faq" in body.lower() or re.search(r"\bQ\s*[:.]|\bA\s*[:.]", body):
        score += 15
    lead = _clean_lead(body, page.h1[0] if page.h1 else "")
    if 40 <= len(lead.split()) <= 80:
        score += 20
    elif lead:
        score += 10
    if page.h2:
        score += min(15, len(page.h2) * 4)
    if page.schema_types:
        score += 10
    return max(0.0, min(100.0, round(score, 1)))


def fallback_copy_audit(page: PageEvidence, profile: BusinessProfile, seo: PageSeoAudit) -> PageCopyAudit:
    issues: List[CopyIssue] = []
    works: List[str] = []
    score = 70.0

    if not (page.title or "").strip():
        issues.append(CopyIssue(area="title", severity="HIGH", issue="No title copy.", why_it_matters="Search listings and browser tabs have nothing unique to show."))
        score -= 12
    if not (page.meta_description or "").strip():
        issues.append(CopyIssue(area="meta", severity="HIGH", issue="No meta description.", why_it_matters="Search engines invent a snippet from random sentences."))
        score -= 10
    if not page.h1:
        issues.append(CopyIssue(area="h1", severity="HIGH", issue="No headline.", why_it_matters="Visitors and crawlers cannot tell the page promise."))
        score -= 12
    elif page.h1 and len(page.h1[0]) < 12:
        issues.append(CopyIssue(area="h1", severity="MEDIUM", issue="Headline is too vague or short.", why_it_matters="It does not name the offer or the audience."))
        score -= 6
    else:
        works.append(f"Headline: {page.h1[0]}")

    if page.page_type != "legal":
        if not page.ctas:
            issues.append(CopyIssue(area="cta", severity="HIGH", issue="No clear call to action.", why_it_matters="The page does not tell the visitor what to do next."))
            score -= 12
        else:
            works.append(f"CTA present: {', '.join(page.ctas[:3])}")

    target = WORD_TARGETS.get(page.page_type, 250)
    if page.word_count < max(80, int(target * 0.45)):
        issues.append(CopyIssue(area="body", severity="HIGH", issue=f"Thin body copy ({page.word_count} words).", why_it_matters="There is not enough substance for SEO or for a buyer to decide."))
        score -= 10
    else:
        works.append(f"{page.word_count} words of body copy.")

    if page.readability_score and page.readability_score < 40 and page.page_type != "legal":
        issues.append(CopyIssue(area="body", severity="MEDIUM", issue=f"Hard to read (score {page.readability_score:.0f}).", why_it_matters="Dense copy lowers conversion and extractability."))
        score -= 6
    elif page.readability_score:
        works.append(f"Readability {page.readability_score:.0f}/100.")

    if page.page_type == "legal":
        analysis = (
            f"This legal page has {page.word_count} words and {len(page.h2)} sections. "
            f"Keep the policy wording; improve heading spacing, a short summary, and a table of contents."
        )
    else:
        analysis = (
            f"This {page.page_type} page has {page.word_count} words, "
            f"{len(page.h1)} H1, {len(page.h2)} H2, and {len(page.ctas or [])} detected CTAs. "
            f"Lead with the offer in the first screen, then proof and a single primary action."
        )
    if seo.issues:
        analysis += " SEO gaps on this URL also weaken how the copy appears in search."

    suggested = _fallback_suggested(page, profile)
    geo_score = _compute_geo_score(page)
    specialist_insights = {
        "seo": f"Observed title {len((page.title or '').strip())} chars ({seo.title_status}); meta {len((page.meta_description or '').strip())} chars ({seo.meta_status}).",
        "geo": f"GEO {geo_score:.0f}/100 from on-page structure (FAQ/schema/definition). Not a live citation rate.",
        "cro": f"Observed CTAs: {', '.join(page.ctas[:3]) if page.ctas else 'none'}.",
        "clarity": f"Readability {page.readability_score:.0f}/100; word count {page.word_count}.",
        "sections": f"{len(suggested.sections)} sections mapped from this URL. Gaps labeled NOT_IN_EVIDENCE rather than filled with generic copy.",
    }

    return PageCopyAudit(
        score=max(0.0, min(100.0, round(score, 1))),
        voice="Inferred from on-page headings and body; tighten toward the brand's spoken voice.",
        clarity="Headlines and body need a sharper promise and fewer generic claims." if issues else "Core message is present.",
        persuasion="Add proof, specifics, and a single primary action." if not page.ctas else "Action language exists; test a stronger primary CTA.",
        audience_fit=profile.target_audience or "Audience is not explicit on the page.",
        cta_quality="Missing" if not page.ctas else "Present",
        geo_score=geo_score,
        seo_score=seo.score,
        issues=issues,
        what_works=works,
        analysis=analysis,
        suggested=suggested,
        specialist_insights=specialist_insights,
        llm_status="skipped",
        llm_failure_reason=None,
        llm_failure_code=None,
    )


def validate_and_clip_copy(sug: SuggestedCopy, brand_name: Optional[str] = None) -> SuggestedCopy:
    """
    Clip over-length fields. Never pad with invented slogans.
    If the title/meta is short, expand only with words already on this SuggestedCopy
    (brand, h1, hero, supporting_points). If still short, leave it short.
    """
    title = (sug.title or "").strip()
    brand = (brand_name or "").strip()
    brand_ok = brand and brand.lower() not in {"unknown", "unknown business"}

    if len(title) < 50:
        extras = [sug.h1, sug.hero, *list(sug.supporting_points or [])]
        for extra in extras:
            extra = re.sub(r"\s+", " ", (extra or "").strip())
            if not extra:
                continue
            candidate = f"{title} — {extra}" if title else extra
            title = candidate
            if len(title) >= 50:
                break

    if brand_ok and brand.lower() not in title.lower():
        suffix = f" | {brand}"
        if len(title) + len(suffix) <= 60:
            title = f"{title}{suffix}" if title else brand
        else:
            budget = max(8, 60 - len(suffix))
            core = title[:budget].rsplit(" ", 1)[0] or title[:budget]
            title = f"{core}{suffix}"
    elif len(title) > 60:
        title = title[:60].rsplit(" ", 1)[0]
    if len(title) > 60:
        title = title[:60].rsplit(" ", 1)[0]
    sug.title = title

    meta = (sug.meta_description or "").strip()
    if len(meta) > 160:
        meta = meta[:157].rsplit(" ", 1)[0] + "..."
    elif meta and len(meta) < 140:
        extras = [sug.hero, sug.h1, *list(sug.supporting_points or []), sug.primary_cta]
        for extra in extras:
            extra = re.sub(r"\s+", " ", (extra or "").strip())
            if not extra or extra.lower() in meta.lower():
                continue
            candidate = f"{meta} {extra}".strip()
            if len(candidate) > 160:
                candidate = candidate[:157].rsplit(" ", 1)[0] + "..."
            meta = candidate
            if len(meta) >= 140:
                break
    sug.meta_description = meta

    hero = (sug.hero or "").strip()
    words = hero.split()
    if len(words) > 60:
        sug.hero = " ".join(words[:60]) + "."
    else:
        sug.hero = hero

    return sug


def _parse_copy_result(raw: Dict[str, Any], fallback: PageCopyAudit, brand_name: Optional[str] = None) -> PageCopyAudit:
    suggested_raw = raw.get("suggested") or {}
    issues_raw = raw.get("issues") or []
    issues: List[CopyIssue] = []
    for item in issues_raw:
        if not isinstance(item, dict):
            continue
        issue_text = str(item.get("issue") or "").strip()
        if not issue_text:
            continue
        issues.append(
            CopyIssue(
                area=str(item.get("area") or "body"),
                severity=str(item.get("severity") or "MEDIUM").upper(),
                issue=issue_text,
                why_it_matters=str(item.get("why_it_matters") or ""),
            )
        )

    sections_raw = suggested_raw.get("sections") or []
    sections: List[CopySection] = []
    if isinstance(sections_raw, list) and sections_raw:
        for s in sections_raw:
            if not isinstance(s, dict):
                continue
            sections.append(
                CopySection(
                    section_id=str(s.get("section_id") or "section"),
                    section_name=str(s.get("section_name") or "Section"),
                    status=str(s.get("status") or "UPDATE_RECOMMENDED"),
                    current_preview=s.get("current_preview"),
                    suggested_copy=str(s.get("suggested_copy") or ""),
                    purpose=str(s.get("purpose") or ""),
                    seo_geo_notes=s.get("seo_geo_notes"),
                    keywords=list(s.get("keywords") or []),
                )
            )
    if not sections:
        sections = list(fallback.suggested.sections)

    faqs_raw = suggested_raw.get("faq_items") or []
    faq_items: List[CopyFaqItem] = []
    if isinstance(faqs_raw, list) and faqs_raw:
        for f in faqs_raw:
            if not isinstance(f, dict):
                continue
            faq_items.append(
                CopyFaqItem(
                    question=str(f.get("question") or "").strip(),
                    answer=str(f.get("answer") or "").strip(),
                    target_engine=str(f.get("target_engine") or "ChatGPT / Perplexity / Google AI Overviews"),
                )
            )
    if not faq_items:
        faq_items = list(fallback.suggested.faq_items)

    geo_snippet = str(suggested_raw.get("geo_snippet") or fallback.suggested.geo_snippet or "")
    hook_3sec = str(suggested_raw.get("hook_3sec") or fallback.suggested.hook_3sec or "")

    sug = SuggestedCopy(
        title=str(suggested_raw.get("title") or fallback.suggested.title),
        meta_description=str(suggested_raw.get("meta_description") or fallback.suggested.meta_description),
        h1=str(suggested_raw.get("h1") or fallback.suggested.h1),
        hero=str(suggested_raw.get("hero") or fallback.suggested.hero),
        primary_cta=str(suggested_raw.get("primary_cta") or fallback.suggested.primary_cta),
        secondary_cta=suggested_raw.get("secondary_cta") or fallback.suggested.secondary_cta,
        supporting_points=list(suggested_raw.get("supporting_points") or fallback.suggested.supporting_points),
        body_rewrite=str(suggested_raw.get("body_rewrite") or fallback.suggested.body_rewrite),
        geo_snippet=geo_snippet,
        hook_3sec=hook_3sec,
        sections=sections,
        faq_items=faq_items,
        notes=suggested_raw.get("notes") or fallback.suggested.notes,
    )
    sug = validate_and_clip_copy(sug, brand_name=brand_name)

    score = raw.get("score")
    try:
        score_n = float(score)
    except (TypeError, ValueError):
        score_n = fallback.score

    geo_sc = raw.get("geo_score")
    try:
        geo_score_n = float(geo_sc) if geo_sc is not None else fallback.geo_score
    except (TypeError, ValueError):
        geo_score_n = fallback.geo_score

    seo_sc = raw.get("seo_score")
    try:
        seo_score_n = float(seo_sc) if seo_sc is not None else fallback.seo_score
    except (TypeError, ValueError):
        seo_score_n = fallback.seo_score

    specialist_insights_raw = raw.get("specialist_insights") or {}
    insights = dict(fallback.specialist_insights)
    if isinstance(specialist_insights_raw, dict):
        for k, v in specialist_insights_raw.items():
            insights[str(k)] = str(v)

    return PageCopyAudit(
        score=max(0.0, min(100.0, round(score_n, 1))),
        voice=str(raw.get("voice") or fallback.voice),
        clarity=str(raw.get("clarity") or fallback.clarity),
        persuasion=str(raw.get("persuasion") or fallback.persuasion),
        audience_fit=str(raw.get("audience_fit") or fallback.audience_fit),
        cta_quality=str(raw.get("cta_quality") or fallback.cta_quality),
        geo_score=max(0.0, min(100.0, round(geo_score_n, 1))),
        seo_score=max(0.0, min(100.0, round(seo_score_n, 1))),
        issues=issues or fallback.issues,
        what_works=list(raw.get("what_works") or fallback.what_works),
        analysis=str(raw.get("analysis") or fallback.analysis),
        suggested=sug,
        specialist_insights=insights,
        llm_status="ok",
        llm_failure_reason=None,
        llm_failure_code=None,
    )


def _fail_copy_audit(copy: PageCopyAudit, seo: PageSeoAudit, reason: str, code: str) -> PageCopyAudit:
    """Strip production-copy pretence when the model did not run. Keep crawl-based issues only."""
    issues = list(copy.issues or [])
    analysis = (
        f"FAILED: copy rewrite did not run. {reason} "
        f"SEO score {seo.score:.0f}/100 is from the crawl. Copy score is null."
    )
    return PageCopyAudit(
        score=None,
        voice="",
        clarity="",
        persuasion="",
        audience_fit="",
        cta_quality=copy.cta_quality,
        geo_score=None,
        seo_score=seo.score,
        issues=issues,
        what_works=list(copy.what_works or []),
        analysis=analysis,
        suggested=None,
        specialist_insights={},
        llm_status="failed",
        llm_failure_reason=reason,
        llm_failure_code=code,
    )


class PageIntelligenceAgent(BaseAgent):
    def __init__(self, model_router):
        super().__init__(agent_id="agent_page_intelligence", capability="content_intelligence", model_router=model_router)

    async def run(self, blackboard: CognitiveBlackboard) -> Dict[str, Any]:
        pages = blackboard.pages or []
        profile = blackboard.business_profile or BusinessProfile()
        reports: List[PageReport] = []
        semaphore = asyncio.Semaphore(3)

        # Identify top strategic pages for deep LLM copywriting
        # Priority: Homepage first (0), then pricing (1), product/services (2), about/contact (3), other (4)
        def _page_priority(p: PageEvidence) -> int:
            u = (p.url or "").lower()
            if u.rstrip("/").count("/") <= 2 or p.page_type == "homepage":
                return 0
            if any(k in u for k in ("pricing", "plans", "tier", "price")):
                return 1
            if any(k in u for k in ("product", "features", "solutions", "services")):
                return 2
            if any(k in u for k in ("about", "contact", "company")):
                return 3
            return 4

        from app.core.config import settings
        max_llm_pages = int(getattr(settings, "MAX_LLM_COPY_PAGES", 4))
        sorted_pages = sorted(pages, key=_page_priority)
        llm_eligible_urls = {p.url for p in sorted_pages[:max_llm_pages]}

        async def one(page: PageEvidence) -> PageReport:
            async with semaphore:
                enable_llm = page.url in llm_eligible_urls
                return await self._analyze_page(page, profile, blackboard, enable_llm_copy=enable_llm)

        if pages:
            reports = await asyncio.gather(*[one(p) for p in pages])
            reports = list(reports)

        blackboard.page_reports = reports

        for report in reports:
            page_ev_ids = [ev.id for ev in blackboard.evidence_store.get_all() if getattr(ev, "url", None) == report.url][:3]
            if not page_ev_ids:
                page_ev_ids = [ev.id for ev in blackboard.evidence_store.get_all()[:2]]
            for issue in report.seo.issues[:3]:
                severity = Severity.HIGH if report.seo.score < 55 else Severity.MEDIUM
                self.register_claim(
                    blackboard=blackboard,
                    statement=f"{report.url}: {issue}",
                    category=Category.ON_PAGE_SEO,
                    severity=severity,
                    confidence=0.93,
                    evidence_refs=page_ev_ids,
                    recommendation=report.seo.recommendations[0] if report.seo.recommendations else "Fix on-page SEO for this URL.",
                    impact=7,
                    effort=3,
                )
            for copy_issue in report.copywriting.issues[:2]:
                sev = Severity.HIGH if copy_issue.severity == "HIGH" else Severity.MEDIUM
                self.register_claim(
                    blackboard=blackboard,
                    statement=f"{report.url} copy — {copy_issue.area}: {copy_issue.issue}",
                    category=Category.CONTENT,
                    severity=sev,
                    confidence=0.9,
                    evidence_refs=page_ev_ids,
                    recommendation=(
                        f"Replace {copy_issue.area} copy."
                        + (
                            f" Suggested H1: {report.copywriting.suggested.h1}"
                            if report.copywriting.suggested and report.copywriting.suggested.h1
                            else ""
                        )
                    ),
                    impact=8,
                    effort=3,
                )

        blackboard.log_step(
            "Per-page SEO and copy reports completed",
            self.agent_id,
            {"pages": len(reports), "avg_score": round(sum(r.overall_score for r in reports) / len(reports), 1) if reports else 0},
        )
        return {"page_reports": len(reports)}

    def _page_to_evidence(self, page: PageEvidence, blackboard: Optional[CognitiveBlackboard] = None) -> List[Evidence]:
        slices: List[Evidence] = []
        n = 0

        def add(kind: str, text: Optional[str], sel: Optional[str] = None) -> None:
            nonlocal n
            value = (text or "").strip()
            if not value:
                return
            n += 1
            slices.append(
                Evidence(
                    id=f"ev_pg_{n:03d}",
                    source_type=kind,
                    analyzer="page_intelligence",
                    hash=f"pg_{n}_{kind}",
                    url=page.url,
                    text=value[:800],
                    selector=sel,
                )
            )

        add("title", page.title)
        add("meta", page.meta_description)
        for h in page.h1[:3]:
            add("h1", h)
        for h in page.h2[:8]:
            add("h2", h)
        for c in (page.ctas or [])[:6]:
            add("cta", c)
        add("body", (page.body_text or "")[:4000])
        if page.schema_types:
            add("schema", ", ".join(page.schema_types))

        if blackboard and getattr(blackboard, "evidence_store", None):
            try:
                for ev in blackboard.evidence_store.get_all()[:40]:
                    if ev.url and page.url and ev.url.rstrip("/") == page.url.rstrip("/"):
                        slices.append(ev)
            except Exception:
                logger.debug("Could not merge blackboard evidence for %s", page.url)
        return slices

    async def _analyze_page(
        self,
        page: PageEvidence,
        profile: BusinessProfile,
        blackboard: Optional[CognitiveBlackboard] = None,
        enable_llm_copy: bool = True,
    ) -> PageReport:
        seo = audit_page_seo(page)
        ux = audit_page_ux(page)
        copy = fallback_copy_audit(page, profile, seo)
        if enable_llm_copy:
            try:
                copy = await self._llm_copy(page, profile, copy, blackboard)
            except Exception as exc:
                logger.warning("LLM page copy failed for %s: %s", page.url, exc)
                copy = _fail_copy_audit(copy, seo, str(exc), "llm_exception")
        if copy.llm_status == "ok" and copy.score is not None:
            overall = round((seo.score * 0.45) + (copy.score * 0.4) + (min(100.0, 100 - min(ux.ttfb_ms / 20, 25)) * 0.15), 1)
        else:
            overall = round(seo.score, 1)
        findings = []
        findings.extend(seo.issues[:4])
        findings.extend([i.issue for i in copy.issues[:3]])
        if ux.cta_count == 0:
            findings.append("No call to action detected.")
        if ux.ttfb_ms and ux.ttfb_ms > 800:
            findings.append(f"Slow TTFB ({int(ux.ttfb_ms)} ms).")
        return PageReport(
            url=page.url,
            page_type=page.page_type,
            title=page.title,
            overall_score=max(0.0, min(100.0, overall)),
            seo=seo,
            copywriting=copy,
            ux=ux,
            findings=findings[:8],
        )

    async def _llm_copy(
        self,
        page: PageEvidence,
        profile: BusinessProfile,
        fallback: PageCopyAudit,
        blackboard: Optional[CognitiveBlackboard] = None,
    ) -> PageCopyAudit:
        intent = profile.primary_intent.value if hasattr(profile.primary_intent, "value") else str(profile.primary_intent)
        context = {
            "url": page.url,
            "page_type": page.page_type,
            "title": page.title,
            "meta_description": page.meta_description,
            "h1": page.h1,
            "h2": page.h2[:8],
            "ctas": page.ctas,
            "word_count": page.word_count,
            "readability": page.readability_score,
            "body": (page.body_text or "")[:12000],
            "business_name": profile.business_name,
            "audience": profile.target_audience,
            "value_proposition": profile.value_proposition,
            "intent": intent,
        }
        evidence_list = self._page_to_evidence(page, blackboard)
        specialist_card = "\n".join([
            task_card_for("copywriting.seo.v3"),
            task_card_for("copywriting.geo.v3"),
            task_card_for("copywriting.cro.v3"),
            task_card_for("copywriting.clarity.v3"),
            task_card_for("copywriting.section.v3"),
        ])
        page_prompt = load_prompt("page_intel")
        result = await self.model_router.generate_structured(
            capability="content_intelligence",
            agent_role="Page copy auditor. Five specialists: SEO, GEO, CRO, clarity, section architect. Evidence only.",
            task_contract=(
                (page_prompt + "\n\n") if page_prompt else ""
            ) + (
                "Audit THIS URL as five specialists. Use only <evidence> and <site_facts>.\n"
                "1. SEO: rewrite title 50-60 chars and meta 140-160 chars from observed offer + brand. Do not pad with generic 'enterprise platform' slogans.\n"
                "2. GEO: 40-60 word definition from observed sentences. FAQ answers that are not on the page must be the string NOT_IN_EVIDENCE.\n"
                "3. CRO: keep observed CTA text unless it is Submit/Click Here. Do not invent a free trial.\n"
                "4. CLARITY: quote vague phrases and rewrite them without new facts.\n"
                "5. SECTIONS: hero, problem, solution, geo_faq, cta_banner. Missing sections = NEEDS_REWRITE + NOT_IN_EVIDENCE, never a fake pain story.\n"
                "AFTER copy may not introduce features, metrics, customers, timelines, or competitors absent from BEFORE/evidence."
            ),
            task_card=specialist_card[:1200],
            evidence_list=evidence_list,
            site_facts=context,
            allow_fallback=False,
            rubric=(
                "1. CLARITY OVER CLEVERNESS: The H1 and hero must communicate exactly what the product/service is within 3 seconds of scanning. Never rely on abstract metaphors or empty slogans.\n"
                "2. AUDIENCE CALLOUT: High-converting copy immediately signals the specific target buyer (e.g. 'For Engineering Leaders', 'For High-Growth B2B Teams').\n"
                "3. RIGOROUS SEO & GEO SPECIFICATIONS: Strict length compliance: Title (50-60 chars), Meta Description (140-160 chars), exactly one semantic H1, and direct citable GEO definition (40-60 words).\n"
                "4. FRICTIONLESS CTAs: Replace weak, generic CTAs like 'Submit' or 'Click Here' with value-forward verbs like 'Explore Platform', 'Audit Your Site', 'Request Demo'.\n"
                "5. ZERO FLUFF TOLERANCE: Ban empty consulting filler like 'seamless experience' or 'cutting-edge platform' in favor of concrete features and outcomes.\n"
                "6. MODULAR SECTION COMPLETENESS: Each section must provide actionable current vs suggested copy and an explicit status (NEEDS_REWRITE, UPDATE_RECOMMENDED, or OPTIMIZED)."
            ),
            output_schema_desc=(
                "{\n"
                '  "score": 0-100,\n'
                '  "seo_score": 0-100,\n'
                '  "geo_score": 0-100,\n'
                '  "voice": "string",\n'
                '  "clarity": "string",\n'
                '  "persuasion": "string",\n'
                '  "audience_fit": "string",\n'
                '  "cta_quality": "string",\n'
                '  "specialist_insights": {\n'
                '    "seo": "string",\n'
                '    "geo": "string",\n'
                '    "cro": "string",\n'
                '    "clarity": "string",\n'
                '    "sections": "string"\n'
                '  },\n'
                '  "what_works": ["string"],\n'
                '  "analysis": "2-4 sentence critique",\n'
                '  "issues": [{"area": "title|meta|h1|hero|cta|body|faq|sections", "severity": "HIGH|MEDIUM|LOW", "issue": "string", "why_it_matters": "string"}],\n'
                '  "suggested": {\n'
                '    "title": "string (50-60 chars)",\n'
                '    "meta_description": "string (140-160 chars)",\n'
                '    "h1": "string",\n'
                '    "hero": "string (40-60 words)",\n'
                '    "hook_3sec": "string",\n'
                '    "geo_snippet": "string (40-60 words)",\n'
                '    "primary_cta": "string",\n'
                '    "secondary_cta": "string",\n'
                '    "supporting_points": ["string"],\n'
                '    "body_rewrite": "string",\n'
                '    "sections": [\n'
                '      {\n'
                '        "section_id": "string",\n'
                '        "section_name": "string",\n'
                '        "status": "NEEDS_REWRITE|UPDATE_RECOMMENDED|OPTIMIZED",\n'
                '        "current_preview": "string",\n'
                '        "suggested_copy": "string",\n'
                '        "purpose": "string",\n'
                '        "seo_geo_notes": "string",\n'
                '        "keywords": ["string"]\n'
                '      }\n'
                '    ],\n'
                '    "faq_items": [\n'
                '      {\n'
                '        "question": "string",\n'
                '        "answer": "string",\n'
                '        "target_engine": "string"\n'
                '      }\n'
                '    ],\n'
                '    "notes": "string"\n'
                '  }\n'
                "}"
            ),
            additional_context=json.dumps(context, ensure_ascii=False),
        )
        if not isinstance(result, dict) or not result.get("suggested"):
            reason = "LLM returned no copy"
            code = "no_suggested"
            if isinstance(result, dict):
                reason = str(result.get("unavailable_reason") or result.get("status") or reason)
                code = str(result.get("unavailable_reason") or result.get("status") or code)
            return _fail_copy_audit(fallback, PageSeoAudit(score=fallback.seo_score), reason, code)
        parsed = _parse_copy_result(result, fallback, brand_name=profile.business_name)
        parsed.llm_status = "ok"
        if parsed.suggested:
            parsed.suggested.notes = (
                (parsed.suggested.notes or "") + " LLM rewrite grounded in crawled evidence for this URL."
            ).strip()
        return parsed
