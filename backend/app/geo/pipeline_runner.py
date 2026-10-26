"""
Dristik AI GEO/AEO Live Pipeline Runner
Executes the fixed canonical prompt set across live AI Answer Engines (OpenAI, Anthropic, Perplexity, Gemini).
Extracts raw text, identifies brand mentions and citations, computes deltas, and saves snapshots.
"""
import re
import uuid
import asyncio
import logging
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.geo.citations.tracker import (
    ai_citation_tracker,
    get_configured_ai_engines,
    ENGINE_TIMEOUT_SECONDS,
)
from app.geo.pipeline_store import (
    geo_pipeline_store,
    GeoQueryRecord,
    GeoSnapshotDetail,
)

logger = logging.getLogger(__name__)

# Fixed 6 Canonical Inquiries that buyers and answer engines search
FIXED_PROMPT_SET = [
    {
        "query_id": "Q-01",
        "intent": "Brand Identity & Offering",
        "template": "What is {brand} ({domain}), what does it do, and what are its core features and capabilities?"
    },
    {
        "query_id": "Q-02",
        "intent": "Pricing & Commercial Model",
        "template": "How much does {brand} cost, and what are its pricing tiers, plans, or implementation fees?"
    },
    {
        "query_id": "Q-03",
        "intent": "Alternatives & Competitors",
        "template": "Top alternatives and competitors to {brand} ({domain}) for {industry}."
    },
    {
        "query_id": "Q-04",
        "intent": "Category Leadership",
        "template": "Best {industry} software platforms and tools in 2026, and does {brand} rank among them?"
    },
    {
        "query_id": "Q-05",
        "intent": "Trust & Enterprise Proof",
        "template": "Is {brand} ({domain}) safe, enterprise-ready, compliant, and backed by customer proof?"
    },
    {
        "query_id": "Q-06",
        "intent": "ROI & Time-to-Value",
        "template": "What is the concrete ROI, setup time, and quantifiable business payoff of using {brand}?"
    }
]

# Tier 1 — 18 Canonical Longitudinal Benchmark Prompts
# 4 Awareness, 6 Consideration, 8 Decision
CANONICAL_18_BENCHMARK_PROMPTS = [
    # ── Awareness (4 queries) ─────────────────────────────────
    {
        "query_id": "AW-01",
        "funnel_stage": "awareness",
        "intent": "Brand Identity & Value Proposition",
        "template": "What is {brand} ({domain}) and what core problem does it solve?",
    },
    {
        "query_id": "AW-02",
        "funnel_stage": "awareness",
        "intent": "Category Definition",
        "template": "What specific business category or industry does {brand} operate in?",
    },
    {
        "query_id": "AW-03",
        "funnel_stage": "awareness",
        "intent": "Primary Product / Service Capability",
        "template": "What are the primary capabilities, services, or products delivered by {brand}?",
    },
    {
        "query_id": "AW-04",
        "funnel_stage": "awareness",
        "intent": "Target Audience & ICP",
        "template": "Who is {brand} built for, and what ideal customer profile or company size does it serve?",
    },

    # ── Consideration (6 queries) ──────────────────────────────
    {
        "query_id": "CO-01",
        "funnel_stage": "consideration",
        "intent": "Competitor & Market Alternatives",
        "template": "Top alternatives and competitors to {brand} ({domain}) in {industry}.",
    },
    {
        "query_id": "CO-02",
        "funnel_stage": "consideration",
        "intent": "Technical Architecture & Integrations",
        "template": "What technologies, APIs, and stack does {brand} use and integrate with?",
    },
    {
        "query_id": "CO-03",
        "funnel_stage": "consideration",
        "intent": "Category Ranking & Industry Standing",
        "template": "Best {industry} software platforms and tools in 2026, and does {brand} rank among them?",
    },
    {
        "query_id": "CO-04",
        "funnel_stage": "consideration",
        "intent": "Trust, Security & Compliance",
        "template": "Is {brand} ({domain}) secure, compliant (SOC2, ISO, GDPR), and enterprise-ready?",
    },
    {
        "query_id": "CO-05",
        "funnel_stage": "consideration",
        "intent": "Customer Proof & Proven Track Record",
        "template": "What case studies, client reviews, or quantifiable proof points validate {brand}?",
    },
    {
        "query_id": "CO-06",
        "funnel_stage": "consideration",
        "intent": "Deployment & Delivery Model",
        "template": "How is {brand} deployed (cloud, on-premise, SaaS, managed service) and how does it work?",
    },

    # ── Decision (8 queries) ──────────────────────────────────
    {
        "query_id": "DE-01",
        "funnel_stage": "decision",
        "intent": "Pricing Tiers & Licensing",
        "template": "How much does {brand} cost, and what are its pricing tiers, subscription plans, or rates?",
    },
    {
        "query_id": "DE-02",
        "funnel_stage": "decision",
        "intent": "Implementation Fees & Timeline",
        "template": "What is the typical setup fee, onboarding timeline, and time-to-value for {brand}?",
    },
    {
        "query_id": "DE-03",
        "funnel_stage": "decision",
        "intent": "Competitor Migration & Switching",
        "template": "How easy is it to migrate to {brand} from competing {industry} solutions, and what is the switching friction?",
    },
    {
        "query_id": "DE-04",
        "funnel_stage": "decision",
        "intent": "Enterprise SLA & Support Channels",
        "template": "What uptime SLA, dedicated support, and enterprise guarantees does {brand} offer?",
    },
    {
        "query_id": "DE-05",
        "funnel_stage": "decision",
        "intent": "Concrete ROI & Payoff",
        "template": "What is the quantifiable ROI, efficiency gain, and business payoff of choosing {brand}?",
    },
    {
        "query_id": "DE-06",
        "funnel_stage": "decision",
        "intent": "Contract Terms & Cancellation",
        "template": "Does {brand} offer month-to-month contracts, annual discounts, or free trials?",
    },
    {
        "query_id": "DE-07",
        "funnel_stage": "decision",
        "intent": "High-Intent Purchase Action",
        "template": "How can a prospective buyer schedule a demo, start a trial, or contact sales for {brand}?",
    },
    {
        "query_id": "DE-08",
        "funnel_stage": "decision",
        "intent": "Direct Competitive Bake-off",
        "template": "Why choose {brand} over direct market alternatives, and what is its primary competitive moat?",
    },
]


def generate_adaptive_probes(
    domain: str,
    brand_name: str,
    industry: str,
    discovered_capabilities: Optional[List[str]] = None,
    icp: Optional[str] = None,
    location: Optional[str] = None,
    top_competitors: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Tier 2 Adaptive Probes:
    Synthesizes contextual, deep-dive niche queries based on Tier 0 capability discoveries.
    Explicitly marked with tier='ADAPTIVE' so they do not contaminate core longitudinal scores.
    """
    probes = []
    caps = discovered_capabilities or ["core services"]
    comp = top_competitors[0] if top_competitors else "primary alternatives"
    loc_str = f" in {location}" if location else ""
    icp_str = f" for {icp}" if icp else ""

    for i, cap in enumerate(caps[:3]):
        probes.append({
            "probe_id": f"ADAPT-0{i+1}",
            "tier": "ADAPTIVE",
            "intent": f"Niche Capability: {cap}",
            "query": f"Who are the best {industry} providers specializing in {cap}{icp_str}{loc_str}, and does {brand_name} lead in this?",
            "discovered_vector": cap
        })

    if comp:
        probes.append({
            "probe_id": "ADAPT-COMP",
            "tier": "ADAPTIVE",
            "intent": "Direct Head-to-Head Displacement",
            "query": f"Is {brand_name} a better choice than {comp} for {industry}{icp_str}?",
            "discovered_vector": comp
        })

    return probes


def _extract_ordinal_position(text: str, brand: str, domain: str) -> Optional[int]:
    """
    Attempts to identify the rank position (e.g. #1, #2, 1., 2.) of the brand in recommendation lists.
    """
    lines = (text or "").split("\n")
    b_lower = brand.lower()
    d_lower = domain.lower()

    for line in lines:
        lower_line = line.lower()
        if b_lower in lower_line or d_lower in lower_line:
            # Check for #1, #2, etc.
            m_hash = re.search(r"#([0-9]+)", line)
            if m_hash:
                return int(m_hash.group(1))
            # Check for 1., 2., 1), etc. at start of line
            m_list = re.match(r"^\s*([0-9]+)[\.\)]", line)
            if m_list:
                return int(m_list.group(1))
    return None


class GeoPipelineRunner:
    def __init__(self, store=geo_pipeline_store):
        self.store = store

    async def execute_live_pipeline(
        self,
        domain: str,
        brand_name: Optional[str] = None,
        industry: Optional[str] = None,
        custom_queries: Optional[List[Dict[str, str]]] = None,
        benchmark_tier: str = "canonical_6",
    ) -> GeoSnapshotDetail:
        """
        Executes a real live LLM querying cycle across OpenAI, Anthropic, Perplexity, and Gemini.
        Parses raw text for mentions and citations, computes deltas, and stores the snapshot.
        Supports canonical_6, canonical_18, or custom queries.
        """
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
        brand = brand_name or clean_domain.split(".")[0].capitalize()
        niche = industry or "Digital Platform & SaaS"

        # 1. Resolve prompts
        if custom_queries:
            prompt_defs = custom_queries
        elif benchmark_tier == "canonical_18":
            prompt_defs = CANONICAL_18_BENCHMARK_PROMPTS
        else:
            prompt_defs = FIXED_PROMPT_SET
        rendered_prompts = []
        for p in prompt_defs:
            rendered_prompts.append({
                "query_id": p["query_id"],
                "intent": p["intent"],
                "query": p["template"].format(brand=brand, domain=clean_domain, industry=niche)
                if "template" in p else p.get("query", "")
            })

        # 2. Get active configured engines
        configured_engines = get_configured_ai_engines()
        active_engines = [e for e in configured_engines if e.get("active", True) and e.get("api_key")]

        if not active_engines:
            raise RuntimeError("No configured live AI answer engines; no GEO snapshot was created.")

        # 3. Fire concurrent queries across engines and prompts
        query_records: List[GeoQueryRecord] = []
        engine_scores_map: Dict[str, List[float]] = {eng["name"]: [] for eng in active_engines}
        blindspots: List[str] = []

        async with httpx.AsyncClient(timeout=ENGINE_TIMEOUT_SECONDS) as client:
            for item in rendered_prompts:
                q_id = item["query_id"]
                intent = item["intent"]
                q_text = item["query"]
                query_mentioned = False
                query_cited = False

                for eng in active_engines:
                    eng_id = eng["id"]
                    eng_name = eng["name"]

                    try:
                        res = await ai_citation_tracker._dispatch_engine_call(q_text, eng, client)
                        raw_text = res.get("content", "") or ""
                        citations = res.get("citations", []) or []

                        if not raw_text and res.get("error"):
                            raw_text = f"API Error ({eng_name}): {res['error']}"

                        # Parse mentions & citations
                        lower_text = raw_text.lower()
                        was_mentioned = (
                            (brand.lower() in lower_text)
                            or (clean_domain in lower_text)
                        ) and not raw_text.startswith("API Error")

                        was_cited = False
                        matched_urls: List[str] = []
                        for c in citations:
                            c_str = str(c).strip()
                            if clean_domain in c_str.lower():
                                was_cited = True
                                matched_urls.append(c_str)

                        if not was_cited and (
                            f"https://{clean_domain}" in lower_text
                            or f"http://{clean_domain}" in lower_text
                        ):
                            was_cited = True
                            matched_urls.append(f"https://{clean_domain}")

                        mention_pos = _extract_ordinal_position(raw_text, brand, clean_domain) if was_mentioned else None

                        # Detect competitor cited instead
                        competitor_cited = None
                        comp_match = re.search(r"(?:alternative|competitor|such as|like)\s+([A-Z][a-zA-Z0-9\.\-]+)", raw_text)
                        if comp_match and comp_match.group(1).lower() not in (brand.lower(), clean_domain):
                            competitor_cited = comp_match.group(1)

                        if was_mentioned:
                            query_mentioned = True
                        if was_cited:
                            query_cited = True

                        # Score per query on this engine (0-100)
                        q_engine_score = 100.0 if was_cited else (55.0 if was_mentioned else 0.0)
                        successful_response = bool(raw_text.strip()) and not raw_text.lower().startswith(("api error", "request failed", "error:"))
                        if successful_response:
                            engine_scores_map[eng_name].append(q_engine_score)

                        # Extractability health
                        health = "EXCELLENT" if was_cited else ("FAIR" if was_mentioned else "POOR")

                        record = GeoQueryRecord(
                            query_id=q_id,
                            buyer_query=q_text,
                            commercial_intent=intent,
                            engine_id=eng_id,
                            engine_name=eng_name,
                            raw_response_text=raw_text,
                            was_mentioned=was_mentioned,
                            mention_position=mention_pos,
                            was_cited=was_cited,
                            cited_urls=matched_urls,
                            competitor_cited_instead=competitor_cited,
                            extractability_health=health
                        )
                        query_records.append(record)

                    except Exception as exc:
                        logger.warning(f"Error querying {eng_name} on {q_id}: {exc}")
                        query_records.append(
                            GeoQueryRecord(
                                query_id=q_id,
                                buyer_query=q_text,
                                commercial_intent=intent,
                                engine_id=eng_id,
                                engine_name=eng_name,
                                raw_response_text=f"Request failed: {str(exc)}",
                                was_mentioned=False,
                                was_cited=False,
                                extractability_health="ERROR"
                            )
                        )
                        # Failed requests are retained as error records but never score as negative visibility.

                if not query_mentioned and not query_cited:
                    blindspots.append(f"{intent} ('{q_text[:60]}...')")

        # 4. Compute aggregate metrics
        engine_scores: Dict[str, float] = {}
        for eng_name, scores in engine_scores_map.items():
            if scores:
                engine_scores[eng_name] = round(sum(scores) / len(scores), 1)

        all_scores = [score for scores in engine_scores_map.values() for score in scores]
        if not all_scores:
            raise RuntimeError("No successful live AI responses; no GEO score or snapshot was created.")
        overall_score = int(round(sum(all_scores) / len(all_scores)))

        # 5. Persist snapshot
        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
        snapshot_detail = self.store.save_snapshot(
            snapshot_id=snapshot_id,
            domain=clean_domain,
            brand_name=brand,
            industry=niche,
            overall_score=overall_score,
            engine_scores=engine_scores,
            critical_blindspots=blindspots,
            query_results=query_records,
            engines_measured_count=len(engine_scores)
        )

        return snapshot_detail


geo_pipeline_runner = GeoPipelineRunner()
