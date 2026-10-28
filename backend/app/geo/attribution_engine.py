"""
Evidence-bounded before/after GEO comparison.

This module reports observed changes across comparable successful query runs.
It does not infer Share of Model from mention/citation deltas and does not claim
causality from a before/after comparison alone.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QueryAttributionDelta(BaseModel):
    query_id: str
    query_text: str
    engine_id: str
    pre_rank: Optional[int] = None
    post_rank: Optional[int] = None
    rank_delta: Optional[int] = None
    pre_cited: Optional[bool] = None
    post_cited: Optional[bool] = None
    citation_gained: Optional[bool] = None
    status: str = "NOT_COMPARABLE"  # IMPROVED | UNCHANGED | REGRESSED | NOT_COMPARABLE


class GeoAttributionReport(BaseModel):
    target_domain: str
    brand_name: str
    pre_patch_run_id: str
    post_patch_run_id: str
    pre_mention_rate_pct: Optional[float] = None
    post_mention_rate_pct: Optional[float] = None
    mention_rate_delta_pct: Optional[float] = None
    pre_citation_rate_pct: Optional[float] = None
    post_citation_rate_pct: Optional[float] = None
    citation_rate_delta_pct: Optional[float] = None
    # Share of Model is intentionally unmeasured here: this engine has no
    # competitor-universe denominator and must not substitute mention rate.
    pre_share_of_model_pct: Optional[float] = None
    post_share_of_model_pct: Optional[float] = None
    som_delta_pct: Optional[float] = None
    total_queries_evaluated: int = 0
    improved_queries_count: int = 0
    regressed_queries_count: int = 0
    net_improvement_pct: Optional[float] = None
    status: str = "INSUFFICIENT_COMPARABLE_DATA"
    measurement_note: str = (
        "Before/after differences are observed changes, not proof that a remediation caused them. "
        "Share of Model requires a defined competitor universe and is not inferred from mention rate."
    )
    query_deltas: List[QueryAttributionDelta] = Field(default_factory=list)
    executive_roi_summary: str = "Insufficient comparable successful query runs to calculate changes."


class GeoAttributionEngine:
    """Compare valid, like-for-like observations without manufacturing missing metrics."""

    @staticmethod
    def _is_successful(row: Any) -> bool:
        status = str(getattr(row, "status", "") or "").upper()
        return (
            status in {"SUCCESS", "SUCCEEDED", "COMPLETED"}
            and not getattr(row, "error_message", None)
            and bool(getattr(row, "is_live", False))
        )

    @staticmethod
    def _key(row: Any) -> Tuple[str, str, str, str, str]:
        # Do not compare different prompts, locales or model versions as if they
        # were the same experiment.
        return (
            str(getattr(row, "query_id", "") or ""),
            str(getattr(row, "engine_id", "") or ""),
            str(getattr(row, "locale", "") or ""),
            str(getattr(row, "model_version", "") or ""),
            str(getattr(row, "query_text", "") or "").strip(),
        )

    def calculate_attribution(
        self,
        pre_patch_evaluations: List[Any],
        post_patch_evaluations: List[Any],
        target_domain: str,
        brand_name: str,
        pre_run_id: str = "pre_patch",
        post_run_id: str = "post_patch",
    ) -> GeoAttributionReport:
        pre_rows = {self._key(row): row for row in pre_patch_evaluations if self._is_successful(row)}
        post_rows = {self._key(row): row for row in post_patch_evaluations if self._is_successful(row)}
        common_keys = sorted(set(pre_rows).intersection(post_rows))
        total = len(common_keys)

        base = dict(
            target_domain=target_domain,
            brand_name=brand_name,
            pre_patch_run_id=pre_run_id,
            post_patch_run_id=post_run_id,
        )
        if total == 0:
            return GeoAttributionReport(
                **base,
                status="INSUFFICIENT_COMPARABLE_DATA",
                executive_roi_summary=(
                    "No comparable successful query/engine/model/locale runs overlap between "
                    "the before and after measurements. No performance delta is reported."
                ),
            )

        pre_mentions = post_mentions = pre_citations = post_citations = 0
        deltas: List[QueryAttributionDelta] = []
        improved = regressed = 0

        for key in common_keys:
            pre_row, post_row = pre_rows[key], post_rows[key]
            pre_mention = bool(getattr(pre_row, "was_mentioned", False))
            post_mention = bool(getattr(post_row, "was_mentioned", False))
            pre_cited = bool(getattr(pre_row, "was_first_party_cited", False))
            post_cited = bool(getattr(post_row, "was_first_party_cited", False))
            pre_mentions += int(pre_mention)
            post_mentions += int(post_mention)
            pre_citations += int(pre_cited)
            post_citations += int(post_cited)

            pre_rank = getattr(pre_row, "mention_position", None)
            post_rank = getattr(post_row, "mention_position", None)
            rank_delta: Optional[int] = None
            if pre_rank is not None and post_rank is not None:
                rank_delta = int(pre_rank) - int(post_rank)  # positive means improved
            elif pre_rank is None and post_rank is not None:
                rank_delta = 1
            elif pre_rank is not None and post_rank is None:
                rank_delta = -1

            citation_gained = (not pre_cited and post_cited)
            improved_signal = rank_delta is not None and rank_delta > 0
            regressed_signal = rank_delta is not None and rank_delta < 0
            if improved_signal or citation_gained or (not pre_mention and post_mention):
                status = "IMPROVED"
                improved += 1
            elif regressed_signal or (pre_cited and not post_cited) or (pre_mention and not post_mention):
                status = "REGRESSED"
                regressed += 1
            else:
                status = "UNCHANGED"

            deltas.append(QueryAttributionDelta(
                query_id=str(getattr(post_row, "query_id", "") or ""),
                query_text=str(getattr(post_row, "query_text", "") or ""),
                engine_id=str(getattr(post_row, "engine_id", "") or ""),
                pre_rank=pre_rank,
                post_rank=post_rank,
                rank_delta=rank_delta,
                pre_cited=pre_cited,
                post_cited=post_cited,
                citation_gained=citation_gained,
                status=status,
            ))

        pre_mention_rate = round(pre_mentions / total * 100, 1)
        post_mention_rate = round(post_mentions / total * 100, 1)
        pre_citation_rate = round(pre_citations / total * 100, 1)
        post_citation_rate = round(post_citations / total * 100, 1)
        mention_delta = round(post_mention_rate - pre_mention_rate, 1)
        citation_delta = round(post_citation_rate - pre_citation_rate, 1)
        net_improvement = round((improved - regressed) / total * 100, 1)

        summary = (
            f"Across {total} comparable successful query runs, brand mention rate changed "
            f"from {pre_mention_rate:.1f}% to {post_mention_rate:.1f}% "
            f"({mention_delta:+.1f} percentage points), and first-party citation rate changed "
            f"from {pre_citation_rate:.1f}% to {post_citation_rate:.1f}% "
            f"({citation_delta:+.1f} percentage points). These are observed before/after "
            "differences, not proof of causal impact. Share of Model was not calculated."
        )

        return GeoAttributionReport(
            **base,
            pre_mention_rate_pct=pre_mention_rate,
            post_mention_rate_pct=post_mention_rate,
            mention_rate_delta_pct=mention_delta,
            pre_citation_rate_pct=pre_citation_rate,
            post_citation_rate_pct=post_citation_rate,
            citation_rate_delta_pct=citation_delta,
            pre_share_of_model_pct=None,
            post_share_of_model_pct=None,
            som_delta_pct=None,
            total_queries_evaluated=total,
            improved_queries_count=improved,
            regressed_queries_count=regressed,
            net_improvement_pct=net_improvement,
            status="MEASURED",
            query_deltas=deltas,
            executive_roi_summary=summary,
        )


geo_attribution_engine = GeoAttributionEngine()
