"""
GEO Benchmark Execution Engine & Immutable Evidence Store (Layer 2).
Executes standardized benchmark suites across live AI answer engines (ChatGPT, Perplexity, Gemini, Claude, Groq).
Stores verbatim raw responses, citations, ordinal positions, source classification, and computes reproducible scores.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.parse import urlparse, urlsplit
import httpx
from pydantic import BaseModel, Field

from app.geo.adapters.base import BaseGeoEngineAdapter, EngineRawResponse
from app.geo.adapters.registry import get_available_adapters, get_adapter
from app.geo.benchmark_generator import BenchmarkQuery, BenchmarkSuite, benchmark_generator
from app.geo.pipeline_store import geo_pipeline_store
from app.geo.metrics import (
    calculate_response_impressions,
    wilson_score_interval,
    continuous_confidence_interval,
    calculate_sample_variance,
)

logger = logging.getLogger(__name__)

SourceQuality = Literal["first_party", "third_party", "social_directory", "unsourced"]


class EvaluatedQueryRun(BaseModel):
    query_id: str
    category: str
    query_text: str
    engine_id: str
    engine_name: str
    model_version: str
    timestamp: str
    locale: str = "en-US"
    latency_ms: float = 0.0
    raw_response: str
    citations: List[str] = Field(default_factory=list)
    was_mentioned: bool = False
    mention_position: Optional[int] = None
    was_first_party_cited: bool = False
    word_count_impression_pct: float = 0.0          # Paper Imp_wc
    position_adjusted_impression_pct: float = 0.0   # Paper Imp_pwc (negative exponential decay)
    dristik_adjusted_impression_pct: float = 0.0    # Dristik-adjusted (credit split |s| / |C_s|)
    unlinked_brand_mentions: int = 0
    sentence_count: int = 0
    total_words: int = 0
    cost_usd: float = 0.0
    source_domains: List[str] = Field(default_factory=list)
    source_quality: SourceQuality = "unsourced"
    status: str = "SUCCESS"  # SUCCESS | KEY_MISSING | TIMEOUT | RATE_LIMITED | ERROR
    is_live: bool = False
    error_message: Optional[str] = None
    run_index: int = 1


class EngineBenchmarkAggregate(BaseModel):
    engine_id: str
    engine_name: str
    model_version: str
    queries_tested: int = 0
    queries_succeeded: int = 0
    mention_count: int = 0
    mention_rate_pct: Optional[float] = None
    mention_rate_ci: Optional[Tuple[float, float]] = None
    first_party_citation_count: int = 0
    first_party_citation_rate_pct: Optional[float] = None
    first_party_citation_rate_ci: Optional[Tuple[float, float]] = None
    mean_word_count_impression_pct: float = 0.0
    word_count_impression_ci: Optional[Tuple[float, float]] = None
    mean_position_adjusted_impression_pct: float = 0.0
    position_adjusted_impression_ci: Optional[Tuple[float, float]] = None
    mean_dristik_adjusted_impression_pct: float = 0.0
    dristik_adjusted_impression_ci: Optional[Tuple[float, float]] = None
    average_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    is_live: bool = False
    status: str = "AVAILABLE"  # AVAILABLE | UNAVAILABLE | RATE_LIMITED | KEY_MISSING


class ShareOfModelMetric(BaseModel):
    """
    Enterprise Share of Model (SoM) and Competitor Displacement metrics,
    benchmarking brand presence vs rivals across AI answer engines with buyer funnel weighting.
    """
    target_domain: str
    brand_name: str
    total_evaluated_queries: int
    share_of_model_pct: Optional[float] = None
    funnel_weighted_som_pct: Optional[float] = None
    first_party_citation_share_pct: Optional[float] = None
    recommendation_rank_score: Optional[float] = None  # unmeasured when no successful evaluations
    ordinal_distribution: Dict[str, int] = Field(default_factory=dict)  # rank_1, rank_2_3, rank_4_plus, unranked
    stage_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)  # awareness, consideration, decision
    competitor_shares: Dict[str, float] = Field(default_factory=dict)
    competitor_displacements: List[Dict[str, Any]] = Field(default_factory=list)


class GeoBenchmarkReport(BaseModel):
    benchmark_id: str
    target_domain: str
    brand_name: str
    locale: str = "en-US"
    run_date: str
    total_queries: int
    engines_tested: List[str] = Field(default_factory=list)  # engines with successful live responses
    engines_requested: List[str] = Field(default_factory=list)
    engines_attempted: List[str] = Field(default_factory=list)
    engines_configured: List[str] = Field(default_factory=list)
    engine_aggregates: Dict[str, EngineBenchmarkAggregate] = Field(default_factory=dict)
    overall_mention_rate_pct: Optional[float] = None
    overall_mention_rate_ci: Optional[Tuple[float, float]] = None
    overall_first_party_citation_rate_pct: Optional[float] = None
    overall_first_party_citation_rate_ci: Optional[Tuple[float, float]] = None
    overall_word_count_impression_pct: Optional[float] = None
    overall_word_count_impression_ci: Optional[Tuple[float, float]] = None
    overall_position_adjusted_impression_pct: Optional[float] = None
    overall_position_adjusted_impression_ci: Optional[Tuple[float, float]] = None
    overall_dristik_adjusted_impression_pct: Optional[float] = None
    overall_dristik_adjusted_impression_ci: Optional[Tuple[float, float]] = None
    share_of_model: Optional[ShareOfModelMetric] = None
    repeats: int = 1
    failed_runs: int = 0
    total_cost_usd: float = 0.0
    cost_cap_exceeded: bool = False
    run_metadata: Dict[str, Any] = Field(default_factory=dict)
    matrix_grounding: Optional[str] = None
    evaluations: List[EvaluatedQueryRun] = Field(default_factory=list)
    critical_blindspots: List[str] = Field(default_factory=list)
    reproducibility_hash: str
    is_live_measurement: bool = False
    summary: str = ""
    sentiment_audit: Optional[Dict[str, Any]] = None
    offpage_citation_summary: Optional[Dict[str, Any]] = None


class GeoBenchmarkRunner:
    """
    Orchestrates live benchmark execution across configured AI engines.
    """

    def __init__(self):
        self.store = geo_pipeline_store

    @staticmethod
    def _normalize_hostname(value: str) -> str:
        """Normalize a URL or hostname without accepting substring lookalikes."""
        raw = (value or "").strip().lower()
        if not raw:
            return ""
        try:
            parsed = urlsplit(raw if "://" in raw else f"//{raw}")
            host = (parsed.hostname or "").rstrip(".").lower()
        except ValueError:
            return ""
        return host[4:] if host.startswith("www.") else host

    @classmethod
    def _is_first_party_host(cls, candidate: str, target_domain: str) -> bool:
        host = cls._normalize_hostname(candidate)
        target = cls._normalize_hostname(target_domain)
        return bool(host and target and (host == target or host.endswith("." + target)))

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        """Match a whole brand/domain token, not a substring of another word."""
        if not text or not term:
            return False
        return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, flags=re.IGNORECASE) is not None

    @staticmethod
    def _contains_domain(text: str, domain: str) -> bool:
        """Match a hostname or its subdomain, but not a deceptive suffix host."""
        if not text or not domain:
            return False
        host = GeoBenchmarkRunner._normalize_hostname(domain)
        if not host:
            return False
        pattern = r"(?<![\w-])(?:[\w-]+\.)*" + re.escape(host) + r"(?![\w.-])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None

    def _classify_sources(self, citations: List[str], raw_text: str, target_domain: str) -> Tuple[List[str], SourceQuality, bool]:
        extracted_domains = set()
        for citation in citations or []:
            host = self._normalize_hostname(str(citation))
            if host:
                extracted_domains.add(host)

        for match in re.finditer(r"""https?://([^\s/<>\"'?#]+)""", raw_text or "", flags=re.IGNORECASE):
            host = self._normalize_hostname(match.group(1).rstrip(".,);]"))
            if host:
                extracted_domains.add(host)

        domain_list = sorted(extracted_domains)
        was_first_party = any(self._is_first_party_host(host, target_domain) for host in domain_list)
        social_domains = ("linkedin.com", "twitter.com", "x.com", "crunchbase.com", "github.com", "clutch.co", "g2.com")
        is_social = any(
            any(host == social or host.endswith("." + social) for social in social_domains)
            for host in domain_list
        )
        if was_first_party:
            quality: SourceQuality = "first_party"
        elif is_social:
            quality: SourceQuality = "social_directory"
        elif domain_list:
            quality: SourceQuality = "third_party"
        else:
            quality: SourceQuality = "unsourced"
        return domain_list, quality, was_first_party

    def _detect_mention_and_position(self, raw_text: str, brand: str, domain: str) -> Tuple[bool, Optional[int]]:
        text = raw_text or ""
        if not text or text.startswith("API Error") or "Missing API key" in text:
            return False, None

        low_text = text.lower()
        low_brand = (brand or "").strip().lower()
        low_domain = self._normalize_hostname(domain)
        has_mention = self._contains_term(text, low_brand) or self._contains_domain(text, low_domain)
        if not has_mention:
            return False, None

        position = None
        for line in text.splitlines():
            if not (self._contains_term(line, low_brand) or self._contains_domain(line, low_domain)):
                continue
            match = re.search(r"#([0-9]+)", line)
            if match:
                position = int(match.group(1))
                break
            match = re.match(r"^\s*([0-9]+)[\.\)]", line)
            if match:
                position = int(match.group(1))
                break

        if position is None and low_brand:
            for pattern, rank in (
                (rf"(?:1\.|#1|first|top choice|primary).*?{re.escape(low_brand)}", 1),
                (rf"(?:2\.|#2|second).*?{re.escape(low_brand)}", 2),
                (rf"(?:3\.|#3|third).*?{re.escape(low_brand)}", 3),
            ):
                if re.search(pattern, low_text):
                    position = rank
                    break
        return has_mention, position

    async def execute_benchmark(
        self,
        domain: str,
        brand_name: Optional[str] = None,
        industry: Optional[str] = None,
        services: Optional[List[str]] = None,
        competitors: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        locale: str = "en-US",
        mode: Literal["comprehensive", "concise"] = "concise",
        engines: Optional[List[str]] = None,
        suite_override: Optional[BenchmarkSuite] = None,
        repeats: int = 1,
        max_queries: Optional[int] = None,
        budget_cap_usd: float = 5.0,
        adaptive_sampling: bool = True,
    ) -> GeoBenchmarkReport:
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
        brand = brand_name or clean_domain.split(".")[0].capitalize()

        # 1. Resolve Suite
        suite = suite_override or benchmark_generator.generate_suite(
            domain=clean_domain,
            brand_name=brand,
            industry=industry,
            services=services,
            competitors=competitors,
            locations=locations,
            mode=mode,
        )
        repeat_count = max(1, min(int(repeats or 1), 10))
        if max_queries and max_queries > 0:
            suite.queries = suite.queries[:max_queries]
            suite.total_queries = len(suite.queries)

        # 2. Resolve Engine Adapters
        active_adapters: List[BaseGeoEngineAdapter] = []
        if engines:
            for eid in engines:
                ad = get_adapter(eid)
                if ad:
                    active_adapters.append(ad)
        else:
            active_adapters = get_available_adapters()

        if not active_adapters:
            # Fallback to default adapters even if keys unconfigured to produce fail-closed report
            from app.geo.adapters.registry import get_all_adapters
            active_adapters = get_all_adapters()[:3]

        benchmark_id = f"GEO-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{suite.suite_id[-4:]}"
        evaluations: List[EvaluatedQueryRun] = []
        engine_stats_map: Dict[str, Dict[str, Any]] = {
            ad.engine_id: {
                "name": ad.display_name,
                "model": ad.model,
                "tested": 0,
                "succeeded": 0,
                "mentions": 0,
                "first_party_citations": 0,
                "latencies": [],
                "is_live": ad.is_configured(),
                "status": "AVAILABLE" if ad.is_configured() else "KEY_MISSING"
            }
            for ad in active_adapters
        }

        # 3. Concurrently Dispatch Queries
        sem = asyncio.Semaphore(5)  # Max 5 concurrent external engine calls
        disabled_engines: Dict[str, EngineRawResponse] = {}

        async def _run_single(
            ad: BaseGeoEngineAdapter,
            q: BenchmarkQuery,
            client: httpx.AsyncClient,
            run_index: int,
        ) -> EvaluatedQueryRun:
            if ad.engine_id in disabled_engines:
                resp = disabled_engines[ad.engine_id]
            else:
                async with sem:
                    if ad.engine_id in disabled_engines:
                        resp = disabled_engines[ad.engine_id]
                    else:
                        resp = await ad.execute_query(q.query_text, locale=locale, client=client)
                        if resp.status_code in (400, 401, 403, 404):
                            logger.warning(
                                f"[GEO Benchmark] Engine '{ad.engine_id}' failed with HTTP {resp.status_code} ({resp.error}). "
                                f"Short-circuiting remaining queries for this engine to avoid repeated errors."
                            )
                            disabled_engines[ad.engine_id] = resp

            # Classify provider outcome before extracting evidence. Error payloads must
            # never become successful negative mentions or citation observations.
            error_text = (resp.error or "").lower()
            raw_text = resp.raw_content or ""
            if resp.status_code == 401 or "missing api key" in error_text or "missing api key" in raw_text.lower():
                status = "KEY_MISSING"
            elif resp.status_code == 429:
                status = "RATE_LIMITED"
            elif resp.status_code in (408, 504):
                status = "TIMEOUT"
            elif resp.status_code < 200 or resp.status_code >= 300 or resp.error:
                status = "ERROR"
            else:
                status = "SUCCESS"

            if status == "SUCCESS":
                has_mention, pos = self._detect_mention_and_position(raw_text, brand, clean_domain)
                sources, quality, is_1p = self._classify_sources(resp.citations, raw_text, clean_domain)
                imp_res = calculate_response_impressions(
                    raw_response=raw_text,
                    citations=resp.citations or [],
                    target_domain=clean_domain,
                    brand_name=brand,
                )
                word_count_impression_pct = imp_res.word_count_impression_pct
                position_adjusted_impression_pct = imp_res.position_adjusted_impression_pct
                dristik_adjusted_impression_pct = imp_res.dristik_adjusted_impression_pct
                unlinked_brand_mentions = imp_res.unlinked_brand_sentences
                sentence_count = imp_res.total_sentences
                total_words = imp_res.total_words
            else:
                has_mention, pos = False, None
                sources, quality, is_1p = [], "unsourced", False
                word_count_impression_pct = 0.0
                position_adjusted_impression_pct = 0.0
                dristik_adjusted_impression_pct = 0.0
                unlinked_brand_mentions = 0
                sentence_count = 0
                total_words = 0

            # Cost estimate is retained for budget accounting, including failed attempts.
            in_words = len((q.query_text or "").split())
            out_words = len(raw_text.split())
            run_cost = round((in_words * 0.000003) + (out_words * 0.000015), 6)

            return EvaluatedQueryRun(
                query_id=q.query_id,
                category=q.category,
                query_text=q.query_text,
                engine_id=ad.engine_id,
                engine_name=ad.display_name,
                model_version=ad.model,
                timestamp=resp.queried_at,
                locale=locale,
                latency_ms=resp.latency_ms,
                raw_response=raw_text,
                citations=resp.citations,
                was_mentioned=has_mention,
                mention_position=pos,
                was_first_party_cited=is_1p,
                word_count_impression_pct=word_count_impression_pct,
                position_adjusted_impression_pct=position_adjusted_impression_pct,
                dristik_adjusted_impression_pct=dristik_adjusted_impression_pct,
                unlinked_brand_mentions=unlinked_brand_mentions,
                sentence_count=sentence_count,
                total_words=total_words,
                cost_usd=run_cost,
                source_domains=sources,
                source_quality=quality,
                status=status,
                is_live=bool(getattr(resp, "is_live", False)) and status == "SUCCESS",
                error_message=resp.error or (
                    None if status == "SUCCESS"
                    else "Provider response was not a successful live measurement."
                ),
                run_index=run_index,
            )

        tasks = []
        async with httpx.AsyncClient(timeout=18.0) as client:
            for run_index in range(1, repeat_count + 1):
                for q in suite.queries:
                    for ad in active_adapters:
                        tasks.append(_run_single(ad, q, client, run_index))

            evaluations = list(await asyncio.gather(*tasks))

        # 4. Aggregate Metrics
        for ev in evaluations:
            st = engine_stats_map.get(ev.engine_id)
            if not st:
                continue
            st["tested"] += 1
            if ev.status == "SUCCESS" and ev.is_live:
                st["succeeded"] += 1
                if ev.latency_ms > 0:
                    st["latencies"].append(ev.latency_ms)
                if ev.was_mentioned:
                    st["mentions"] += 1
                if ev.was_first_party_cited:
                    st["first_party_citations"] += 1

        engine_aggregates: Dict[str, EngineBenchmarkAggregate] = {}
        total_mentions = 0
        total_1p_citations = 0
        total_succeeded = 0

        for eid, st in engine_stats_map.items():
            t_cnt = st["tested"]
            m_cnt = st["mentions"]
            c_cnt = st["first_party_citations"]
            s_cnt = st["succeeded"]
            total_mentions += m_cnt
            total_1p_citations += c_cnt
            total_succeeded += s_cnt

            avg_lat = round(sum(st["latencies"]) / len(st["latencies"]), 1) if st["latencies"] else 0.0
            m_rate = round((m_cnt / s_cnt) * 100.0, 1) if s_cnt > 0 else None
            c_rate = round((c_cnt / s_cnt) * 100.0, 1) if s_cnt > 0 else None

            # Wilson score 95% confidence intervals
            m_ci = wilson_score_interval(m_cnt, s_cnt) if s_cnt > 0 else None
            c_ci = wilson_score_interval(c_cnt, s_cnt) if s_cnt > 0 else None

            # Continuous impression metrics across successful evaluations for this engine
            eng_successes = [ev for ev in evaluations if ev.engine_id == eid and ev.status == "SUCCESS" and ev.is_live]
            wc_list = [ev.word_count_impression_pct for ev in eng_successes]
            pwc_list = [ev.position_adjusted_impression_pct for ev in eng_successes]
            dristik_list = [ev.dristik_adjusted_impression_pct for ev in eng_successes]

            mean_wc = round(sum(wc_list) / len(wc_list), 1) if wc_list else 0.0
            ci_wc = continuous_confidence_interval(wc_list) if wc_list else None

            mean_pwc = round(sum(pwc_list) / len(pwc_list), 1) if pwc_list else 0.0
            ci_pwc = continuous_confidence_interval(pwc_list) if pwc_list else None

            mean_dristik = round(sum(dristik_list) / len(dristik_list), 1) if dristik_list else 0.0
            ci_dristik = continuous_confidence_interval(dristik_list) if dristik_list else None

            eng_cost = round(sum(ev.cost_usd for ev in evaluations if ev.engine_id == eid), 6)

            engine_aggregates[eid] = EngineBenchmarkAggregate(
                engine_id=eid,
                engine_name=st["name"],
                model_version=st["model"],
                queries_tested=t_cnt,
                queries_succeeded=s_cnt,
                mention_count=m_cnt,
                mention_rate_pct=m_rate,
                mention_rate_ci=m_ci,
                first_party_citation_count=c_cnt,
                first_party_citation_rate_pct=c_rate,
                first_party_citation_rate_ci=c_ci,
                mean_word_count_impression_pct=mean_wc,
                word_count_impression_ci=ci_wc,
                mean_position_adjusted_impression_pct=mean_pwc,
                position_adjusted_impression_ci=ci_pwc,
                mean_dristik_adjusted_impression_pct=mean_dristik,
                dristik_adjusted_impression_ci=ci_dristik,
                average_latency_ms=avg_lat,
                total_cost_usd=eng_cost,
                is_live=st["is_live"],
                status=st["status"],
            )

        overall_mention_rate = round((total_mentions / total_succeeded) * 100.0, 1) if total_succeeded > 0 else None
        overall_mention_ci = wilson_score_interval(total_mentions, total_succeeded) if total_succeeded > 0 else None

        overall_1p_citation_rate = round((total_1p_citations / total_succeeded) * 100.0, 1) if total_succeeded > 0 else None
        overall_1p_citation_ci = wilson_score_interval(total_1p_citations, total_succeeded) if total_succeeded > 0 else None

        # Overall continuous impression metrics across all successes
        all_successes = [ev for ev in evaluations if ev.status == "SUCCESS" and ev.is_live]
        all_wc = [ev.word_count_impression_pct for ev in all_successes]
        all_pwc = [ev.position_adjusted_impression_pct for ev in all_successes]
        all_dristik = [ev.dristik_adjusted_impression_pct for ev in all_successes]

        overall_wc_pct = round(sum(all_wc) / len(all_wc), 1) if all_wc else None
        overall_wc_ci = continuous_confidence_interval(all_wc) if all_wc else None

        overall_pwc_pct = round(sum(all_pwc) / len(all_pwc), 1) if all_pwc else None
        overall_pwc_ci = continuous_confidence_interval(all_pwc) if all_pwc else None

        overall_dristik_pct = round(sum(all_dristik) / len(all_dristik), 1) if all_dristik else None
        overall_dristik_ci = continuous_confidence_interval(all_dristik) if all_dristik else None

        total_cost_usd = round(sum(ev.cost_usd for ev in evaluations), 4)
        cost_cap_exceeded = total_cost_usd > budget_cap_usd
        failed_runs = sum(1 for ev in evaluations if ev.status != "SUCCESS")

        # Blindspots only when a successful response omitted the brand. Errors are not omissions.
        blindspots: List[str] = []
        for q in suite.queries:
            success_runs = [e for e in evaluations if e.query_id == q.query_id and e.status == "SUCCESS" and e.is_live]
            if success_runs and not any(r.was_mentioned for r in success_runs):
                blindspots.append(f"{q.category_label}: '{q.query_text}'")

        # Reproducibility hash
        hash_input = f"{benchmark_id}|{clean_domain}|{len(evaluations)}|{overall_mention_rate}|{overall_1p_citation_rate}|{overall_wc_pct}"
        reproducibility_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

        mention_text = f"{overall_mention_rate:.1f}%" if overall_mention_rate is not None else "not measured"
        citation_text = f"{overall_1p_citation_rate:.1f}%" if overall_1p_citation_rate is not None else "not measured"
        imp_text = f"{overall_wc_pct:.1f}%" if overall_wc_pct is not None else "not measured"

        ci_str = f" [95% CI: {overall_mention_ci[0]}%-{overall_mention_ci[1]}%]" if overall_mention_ci else ""
        summary = (
            f"Live AI Retrieval Benchmark ({benchmark_id}): {len(suite.queries)} queries, "
            f"{repeat_count} run(s) each, across {len(active_adapters)} engines. "
            f"Brand mention rate {mention_text}{ci_str}, first-party citation rate {citation_text}, "
            f"Imp_wc continuous visibility {imp_text}, "
            f"over {total_succeeded} successful responses ({failed_runs} errors excluded). "
            f"Estimated cost: ${total_cost_usd:.4f}. {len(blindspots)} category blindspots identified."
        )

        from app.commercial.measurement import assess_proportion

        mention_reliability = None
        if total_succeeded > 0:
            mention_reliability = assess_proportion(total_mentions, total_succeeded).model_dump()
        run_metadata = {
            "sampling_runs": repeat_count,
            "confidence_level": 0.95,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "engines_configured": [ad.engine_id for ad in active_adapters if ad.is_configured()],
            "engine_response_counts": {
                ad.engine_id: {
                    "attempted": sum(1 for ev in evaluations if ev.engine_id == ad.engine_id),
                    "successful_live": sum(1 for ev in evaluations if ev.engine_id == ad.engine_id and ev.status == "SUCCESS" and ev.is_live),
                    "failed_or_non_live": sum(1 for ev in evaluations if ev.engine_id == ad.engine_id and not (ev.status == "SUCCESS" and ev.is_live)),
                }
                for ad in active_adapters
            },
            "cost_tracking_enabled": True,
            "budget_cap_usd": budget_cap_usd,
            "cost_cap_exceeded": cost_cap_exceeded,
            "fixed_run_count_is_statistically_sufficient": False,
            "sampling_note": (
                "The repeat count is a measurement budget. It is not a claim that the "
                "sample meets a precision target. Repeated runs of the same prompt are correlated."
            ),
            "mention_reliability": mention_reliability,
        }

        # Compute Share of Model (SoM) and Competitor Displacement
        som_metric = self.calculate_share_of_model(
            evaluations=evaluations,
            target_domain=clean_domain,
            brand_name=brand,
            competitors=competitors,
        )

        # Compute sentiment & hallucination audit
        sentiment_audit_dict = None
        try:
            from app.geo.sentiment_engine import geo_sentiment_engine
            sentiment_audit_dict = geo_sentiment_engine.generate_audit_report(
                evaluations=evaluations,
                brand_name=brand,
            ).model_dump()
        except Exception as exc:
            logger.debug("[BenchmarkRunner] Sentiment audit skipped: %s", exc)

        # Compute off-page citation authority network
        offpage_dict = None
        try:
            from app.geo.offpage_network import offpage_network_analyzer
            offpage_dict = offpage_network_analyzer.analyze_citation_network(
                evaluations=evaluations,
                target_domain=clean_domain,
                brand_name=brand,
                competitors=competitors,
            ).model_dump()
        except Exception as exc:
            logger.debug("[BenchmarkRunner] Offpage network skipped: %s", exc)

        return GeoBenchmarkReport(
            benchmark_id=benchmark_id,
            target_domain=clean_domain,
            brand_name=brand,
            locale=locale,
            run_date=datetime.now(timezone.utc).isoformat(),
            total_queries=len(suite.queries),
            engines_tested=[
                ad.display_name for ad in active_adapters
                if any(ev.engine_id == ad.engine_id and ev.status == "SUCCESS" and ev.is_live for ev in evaluations)
            ],
            engines_requested=[str(engine) for engine in engines] if engines else [ad.engine_id for ad in active_adapters],
            engines_attempted=[
                ad.display_name for ad in active_adapters
                if any(ev.engine_id == ad.engine_id for ev in evaluations)
            ],
            engines_configured=[ad.engine_id for ad in active_adapters if ad.is_configured()],
            engine_aggregates=engine_aggregates,
            overall_mention_rate_pct=overall_mention_rate,
            overall_mention_rate_ci=overall_mention_ci,
            overall_first_party_citation_rate_pct=overall_1p_citation_rate,
            overall_first_party_citation_rate_ci=overall_1p_citation_ci,
            overall_word_count_impression_pct=overall_wc_pct,
            overall_word_count_impression_ci=overall_wc_ci,
            overall_position_adjusted_impression_pct=overall_pwc_pct,
            overall_position_adjusted_impression_ci=overall_pwc_ci,
            overall_dristik_adjusted_impression_pct=overall_dristik_pct,
            overall_dristik_adjusted_impression_ci=overall_dristik_ci,
            share_of_model=som_metric,
            evaluations=evaluations,
            critical_blindspots=blindspots[:8],
            reproducibility_hash=reproducibility_hash,
            is_live_measurement=total_succeeded > 0,
            summary=summary,
            repeats=repeat_count,
            failed_runs=failed_runs,
            total_cost_usd=total_cost_usd,
            cost_cap_exceeded=cost_cap_exceeded,
            run_metadata=run_metadata,
            sentiment_audit=sentiment_audit_dict,
            offpage_citation_summary=offpage_dict,
        )

    def calculate_share_of_model(
        self,
        evaluations: List[EvaluatedQueryRun],
        target_domain: str,
        brand_name: str,
        competitors: Optional[List[str]] = None,
    ) -> ShareOfModelMetric:
        """Calculate an explicitly defined share among observed tracked entities.

        This is not market share. It is the target's fraction of observed target
        plus supplied-competitor mentions in successful live responses. Without a
        competitor universe, mention rate must not be relabeled as Share of Model.
        """
        clean_domain = self._normalize_hostname(target_domain)
        brand = (brand_name or clean_domain.split(".")[0]).strip()
        comp_list = list(dict.fromkeys(
            str(c).strip().lower() for c in (competitors or [])
            if c and str(c).strip()
        ))
        successes = [
            row for row in evaluations
            if row.status == "SUCCESS" and getattr(row, "is_live", False)
        ]
        total = len(successes)

        if total == 0:
            return ShareOfModelMetric(
                target_domain=clean_domain,
                brand_name=brand_name,
                total_evaluated_queries=0,
                share_of_model_pct=None,
                funnel_weighted_som_pct=None,
                first_party_citation_share_pct=None,
                recommendation_rank_score=None,
                ordinal_distribution={"rank_1": 0, "rank_2_3": 0, "rank_4_plus": 0, "unranked": 0},
                competitor_shares={},
                competitor_displacements=[],
            )

        competitor_hits = {comp: 0 for comp in comp_list}
        target_mentions = 0
        target_first_party_citations = 0
        competitor_citations = 0
        competitor_domain_universe = {
            comp: self._normalize_hostname(comp)
            for comp in comp_list
            if "." in self._normalize_hostname(comp)
        }
        citation_universe_measurable = bool(competitor_domain_universe)
        rank_1 = rank_2_3 = rank_4_plus = unranked = 0
        position_weight_sum = 0.0
        displacements: List[Dict[str, Any]] = []
        stages = {
            "awareness": {"total": 0, "mentions": 0, "weight": 1.0},
            "consideration": {"total": 0, "mentions": 0, "weight": 2.5},
            "decision": {"total": 0, "mentions": 0, "weight": 4.0},
        }
        target_weighted_mentions = 0.0
        all_entity_weighted_mentions = 0.0

        for ev in successes:
            raw = ev.raw_response or ""
            target_hit = bool(ev.was_mentioned)
            target_mentions += int(target_hit)
            target_first_party_citations += int(bool(ev.was_first_party_cited))

            this_competitors = []
            for comp in comp_list:
                comp_host = self._normalize_hostname(comp)
                if "." in comp_host:
                    comp_hit = self._contains_domain(raw, comp_host)
                else:
                    comp_hit = self._contains_term(raw, comp.lower())
                if comp_hit:
                    competitor_hits[comp] += 1
                    this_competitors.append(comp)

            if citation_universe_measurable:
                cited_domains = [self._normalize_hostname(d) for d in (ev.source_domains or [])]
                competitor_citations += sum(
                    1 for host in cited_domains
                    if any(self._is_first_party_host(host, comp_domain)
                           for comp_domain in competitor_domain_universe.values())
                )

            if ev.was_mentioned:
                if ev.mention_position == 1:
                    rank_1 += 1
                    position_weight_sum += 1.0
                elif ev.mention_position in (2, 3):
                    rank_2_3 += 1
                    position_weight_sum += 0.75
                elif ev.mention_position is not None and ev.mention_position >= 4:
                    rank_4_plus += 1
                    position_weight_sum += 0.40
                else:
                    unranked += 1
                    position_weight_sum += 0.50
            else:
                unranked += 1

            if this_competitors and (not target_hit or (ev.mention_position is not None and ev.mention_position > 1)):
                for comp in this_competitors:
                    displacements.append({
                        "query_id": ev.query_id,
                        "query_text": ev.query_text,
                        "engine": ev.engine_name,
                        "displacing_competitor": comp,
                        "target_mentioned": target_hit,
                        "target_position": ev.mention_position,
                        "reason": (
                            f"Competitor '{comp}' appeared in the answer while "
                            f"'{brand_name}' was {'omitted' if not target_hit else f'ranked #{ev.mention_position}'}."
                        ),
                    })

            category = (getattr(ev, "category", "") or "").lower()
            if category in ("commercial", "comparative", "high_intent"):
                stage_key = "decision"
            elif category in ("services", "problem"):
                stage_key = "consideration"
            else:
                stage_key = "awareness"
            stage = stages[stage_key]
            stage["total"] += 1
            weight = stage["weight"]
            if target_hit:
                stage["mentions"] += 1
                target_weighted_mentions += weight
                all_entity_weighted_mentions += weight
            all_entity_weighted_mentions += weight * len(this_competitors)

        total_competitor_hits = sum(competitor_hits.values())
        entity_mention_denominator = target_mentions + total_competitor_hits
        som_pct = (
            round(target_mentions / entity_mention_denominator * 100.0, 1)
            if comp_list and entity_mention_denominator > 0 else None
        )
        competitor_shares = {
            comp: round(count / entity_mention_denominator * 100.0, 1)
            for comp, count in competitor_hits.items()
            if entity_mention_denominator > 0
        }
        funnel_som = (
            round(target_weighted_mentions / all_entity_weighted_mentions * 100.0, 1)
            if comp_list and all_entity_weighted_mentions > 0 else None
        )
        citation_denominator = target_first_party_citations + competitor_citations
        citation_share = (
            round(target_first_party_citations / citation_denominator * 100.0, 1)
            if citation_universe_measurable and citation_denominator > 0 else None
        )

        stage_breakdown: Dict[str, Dict[str, Any]] = {}
        for name, data in stages.items():
            count = data["total"]
            mentions = data["mentions"]
            stage_breakdown[name] = {
                "total_queries": count,
                "mentions": mentions,
                "mention_rate_pct": round(mentions / count * 100.0, 1) if count else None,
                "commercial_weight": data["weight"],
            }

        return ShareOfModelMetric(
            target_domain=clean_domain,
            brand_name=brand_name,
            total_evaluated_queries=total,
            share_of_model_pct=som_pct,
            funnel_weighted_som_pct=funnel_som,
            first_party_citation_share_pct=citation_share,
            recommendation_rank_score=round(position_weight_sum / total * 100.0, 1),
            ordinal_distribution={
                "rank_1": rank_1,
                "rank_2_3": rank_2_3,
                "rank_4_plus": rank_4_plus,
                "unranked": unranked,
            },
            stage_breakdown=stage_breakdown,
            competitor_shares=competitor_shares,
            competitor_displacements=displacements[:30],
        )


def _pct(hits: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    return round((hits / total) * 100.0, 1)


def _queried_engine_names(report: GeoBenchmarkReport, successes: List[EvaluatedQueryRun]) -> List[str]:
    names: List[str] = []
    seen = set()
    for ev in successes:
        label = (ev.engine_name or ev.engine_id or "").strip()
        key = label.lower()
        if label and key not in seen:
            seen.add(key)
            names.append(label)
    if names:
        return names
    for agg in report.engine_aggregates.values():
        if agg.queries_succeeded <= 0:
            continue
        label = (agg.engine_name or agg.engine_id or "").strip()
        key = label.lower()
        if label and key not in seen:
            seen.add(key)
            names.append(label)
    return names


def build_visibility_scorecard(
    report: GeoBenchmarkReport,
    services: Optional[List[str]] = None,
    competitors: Optional[List[str]] = None,
    locations: Optional[List[str]] = None,
    industry: Optional[str] = None,
    audience: Optional[str] = None,
    matrix_grounding: Optional[str] = None,
):
    """Rates over successful responses only. Unchecked rates stay null."""
    from app.domain.models import AiVisibilityScorecard
    from app.geo.buyer_surfaces import surfaces_not_queried

    successes = [ev for ev in report.evaluations if ev.status == "SUCCESS" and ev.is_live]
    failures = [ev for ev in report.evaluations if ev.status != "SUCCESS"]
    engine_names = _queried_engine_names(report, successes)
    missing_surfaces = surfaces_not_queried(engine_names)
    surface_note = (
        " These responses are model APIs. They are not "
        + ", ".join(missing_surfaces)
        + ", which were not queried."
        if missing_surfaces
        else ""
    )
    if not successes:
        return AiVisibilityScorecard(
            status="NOT_MEASURED",
            measurement_kind="NOT_MEASURED",
            engines_requested=len(report.engines_requested or report.engines_attempted),
            engines_queried=engine_names,
            surfaces_not_queried=missing_surfaces,
            queries=report.total_queries,
            repeats=report.repeats,
            failed_runs=len(failures),
            not_measured_reason="No successful engine responses. Errors are excluded rather than scored as omissions."
            + surface_note,
            matrix_grounding=matrix_grounding,
        )

    brand = (report.brand_name or "").lower()
    service_terms = [s.lower() for s in (services or []) if s]
    competitor_terms = [c.lower() for c in (competitors or []) if c and "leading competitors" not in c.lower()]
    location_terms = [loc.lower() for loc in (locations or []) if loc]
    industry_term = (industry or "").lower().strip()
    audience_term = (audience or "").lower().strip()

    entity_hits = 0
    entity_slots = 0
    service_hits = 0
    service_total = 0
    pricing_hits = 0
    pricing_total = 0
    icp_hits = 0
    icp_total = 0
    competitor_hits = 0

    for ev in successes:
        text = (ev.raw_response or "").lower()
        slots = []
        if brand:
            slots.append(brand in text)
        if service_terms:
            slots.append(any(term in text for term in service_terms))
        if location_terms:
            slots.append(any(term in text for term in location_terms))
        if industry_term and industry_term not in ("this category",):
            slots.append(industry_term in text)
        if audience_term:
            slots.append(audience_term in text)
        if slots:
            entity_slots += len(slots)
            entity_hits += sum(1 for ok in slots if ok)

        if ev.category == "services" and service_terms:
            service_total += 1
            if any(term in text for term in service_terms):
                service_hits += 1
        if ev.category in ("high_intent", "commercial") and "pric" in (ev.query_text or "").lower():
            pricing_total += 1
            if brand and brand in text:
                pricing_hits += 1
        if ev.category == "audience" and (audience_term or brand):
            icp_total += 1
            if (audience_term and audience_term in text) or (brand and brand in text):
                icp_hits += 1
        if competitor_terms and any(term in text for term in competitor_terms):
            competitor_hits += 1

    source_consistency = None
    if report.repeats >= 2:
        by_query: Dict[str, List[EvaluatedQueryRun]] = {}
        for ev in successes:
            by_query.setdefault(ev.query_id, []).append(ev)
        stable = 0
        seen = 0
        for runs in by_query.values():
            domain_counts: Dict[str, int] = {}
            for ev in runs:
                for domain in ev.source_domains:
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
            for count in domain_counts.values():
                seen += 1
                if count >= 2:
                    stable += 1
        source_consistency = _pct(stable, seen)

    engines_live = sum(1 for agg in report.engine_aggregates.values() if agg.queries_succeeded > 0)
    
    # Compile deep AI Retrieval Observatory metrics
    from app.geo.observatory import AiRetrievalObservatory
    obs_summary = AiRetrievalObservatory.compile_observatory(
        evaluations=report.evaluations,
        brand_name=report.brand_name or "",
        target_domain=report.target_domain,
        competitors=competitors,
    )

    return AiVisibilityScorecard(
        status="MEASURED",
        measurement_kind="LIVE_MODEL_API",
        measurement_note=(
            "Rates use successful API or SERP responses only. "
            "An API answer can differ from the consumer chat UI. "
            "A timeout is an error, not a failure to mention the brand."
            + surface_note
        ),
        engines_measured=engines_live,
        engines_requested=len(report.engines_tested),
        engines_queried=engine_names,
        surfaces_not_queried=missing_surfaces,
        queries=report.total_queries,
        repeats=report.repeats,
        successful_runs=len(successes),
        failed_runs=len(failures),
        mention_rate_pct=report.overall_mention_rate_pct,
        citation_rate_pct=report.overall_first_party_citation_rate_pct,
        citation_accuracy_pct=None,
        entity_accuracy_pct=_pct(entity_hits, entity_slots),
        service_recognition_pct=_pct(service_hits, service_total),
        icp_recognition_pct=_pct(icp_hits, icp_total),
        pricing_recognition_pct=_pct(pricing_hits, pricing_total),
        competitor_visibility_pct=_pct(competitor_hits, len(successes)) if competitor_terms else None,
        hallucination_rate_pct=obs_summary.hallucination_rate_pct if obs_summary.total_evaluations > 0 else None,
        source_consistency_pct=source_consistency,
        matrix_grounding=matrix_grounding,
        observatory_records=[r.model_dump() for r in obs_summary.records],
        observatory_summary=obs_summary.model_dump(),
    )


benchmark_runner = GeoBenchmarkRunner()
