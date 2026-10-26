"""Evidence-backed historical GEO KPI analytics API.

Only successful, non-empty live engine responses contribute to measured metrics.
Failed requests are tracked separately and never interpreted as a negative brand result.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query

from app.geo.pipeline_store import geo_pipeline_store

router = APIRouter(prefix="/geo-analytics", tags=["GEO KPI Analytics"])
METHODOLOGY_VERSION = "live-visibility-v1"


def _successful(record: Any) -> bool:
    text = (record.raw_response_text or "").strip()
    lowered = text.lower()
    return bool(text) and not lowered.startswith(("api error", "request failed", "error:"))


def _measure(records: List[Any]) -> Dict[str, Any]:
    successful = [r for r in records if _successful(r)]
    total = len(records)
    mentioned = sum(bool(r.was_mentioned) for r in successful)
    cited = sum(bool(r.was_cited) for r in successful)
    score_points = [100.0 if r.was_cited else 55.0 if r.was_mentioned else 0.0 for r in successful]
    return {
        "status": "MEASURED" if successful else "UNAVAILABLE",
        "observations": len(successful),
        "attempted": total,
        "failed_or_empty": total - len(successful),
        "mentions": mentioned,
        "citations": cited,
        "mention_rate_pct": round(100 * mentioned / len(successful), 1) if successful else None,
        "citation_rate_pct": round(100 * cited / len(successful), 1) if successful else None,
        "score": round(sum(score_points) / len(score_points), 1) if score_points else None,
    }


@router.get("")
def get_geo_analytics(
    domain: str = Query(..., min_length=1, description="Domain to inspect"),
    limit: int = Query(30, ge=1, le=100, description="Number of latest snapshots"),
) -> Dict[str, Any]:
    clean_domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0].strip()
    if not clean_domain:
        raise HTTPException(status_code=422, detail="A valid domain is required.")

    snapshots = geo_pipeline_store.get_domain_history(clean_domain, limit=limit)
    history: List[Dict[str, Any]] = []
    latest_records: List[Any] = []
    for snapshot in snapshots:
        detail = geo_pipeline_store.get_snapshot_detail(snapshot.snapshot_id)
        records = detail.query_results if detail else []
        measured = _measure(records)
        history.append({
            "snapshot_id": snapshot.snapshot_id,
            "timestamp": snapshot.timestamp,
            "score": measured["score"],
            "observations": measured["observations"],
            "attempted": measured["attempted"],
            "mentions": measured["mentions"],
            "citations": measured["citations"],
            "mention_rate_pct": measured["mention_rate_pct"],
            "citation_rate_pct": measured["citation_rate_pct"],
            "status": measured["status"],
        })
        latest_records = records

    current = _measure(latest_records) if history else _measure([])
    engines: Dict[str, List[Any]] = defaultdict(list)
    intents: Dict[str, List[Any]] = defaultdict(list)
    for record in latest_records:
        engines[record.engine_name].append(record)
        intents[record.commercial_intent or "Unclassified"].append(record)

    engine_breakdown = []
    for name, rows in sorted(engines.items()):
        values = _measure(rows)
        engine_breakdown.append({"engine": name, **values})

    intent_breakdown = []
    for name, rows in sorted(intents.items()):
        values = _measure(rows)
        intent_breakdown.append({"intent": name, **values})

    return {
        "domain": clean_domain,
        "methodology_version": METHODOLOGY_VERSION,
        "status": current["status"] if history else "NO_HISTORY",
        "snapshot_count": len(history),
        "current": current if history else {
            "status": "UNAVAILABLE", "observations": 0, "attempted": 0,
            "failed_or_empty": 0, "mentions": 0, "citations": 0,
            "mention_rate_pct": None, "citation_rate_pct": None, "score": None,
        },
        "history": history,
        "engines": engine_breakdown,
        "intents": intent_breakdown,
        "formula": {
            "name": "Observed live visibility score",
            "description": "Arithmetic mean across successful live responses only.",
            "citation_response_points": 100,
            "mention_without_citation_points": 55,
            "no_mention_or_citation_points": 0,
            "failed_response_treatment": "Excluded from numerator and denominator; reported separately.",
            "denominator": "Successful non-empty live engine responses in this snapshot.",
        },
        "data_quality": {
            "successful_observations": current["observations"],
            "failed_or_empty_attempts": current["failed_or_empty"],
            "scope": "Only configured AI engines actually queried in the stored snapshot.",
            "limitations": [
                "This live visibility score is not the on-page GEO readiness score.",
                "Mention and citation detection depends on the stored response text and extracted citation URLs.",
                "Historical snapshots are not backfilled; analytics begin with existing stored observations.",
            ],
        },
    }
