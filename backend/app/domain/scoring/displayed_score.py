"""The one composite the dashboard and the PDF cover both show.

Matches frontend ``buildDisplayedScore``. GEO is the measured extractability
score. A live citation of zero stays in the total only when this run recorded
successful engine responses. An unmeasured pillar is left out.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Optional


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _score(value: Any) -> Optional[float]:
    """Accept only finite measured scores in the documented 0..100 range."""
    number = _num(value)
    return number if number is not None and 0.0 <= number <= 100.0 else None


def _round_to(value: float, digits: int) -> float:
    factor = 10 ** digits
    return math.floor(value * factor + 0.5) / factor


def _as_report(report: Any) -> Optional[dict]:
    if report is None:
        return None
    if isinstance(report, str):
        if not report.strip():
            return None
        try:
            report = json.loads(report)
        except (TypeError, ValueError):
            return None
    if not isinstance(report, dict) and hasattr(report, "model_dump"):
        try:
            report = report.model_dump(mode="json")
        except Exception:
            return None
    return report if isinstance(report, dict) else None


def _positive_int(value: Any) -> int:
    number = _num(value)
    if number is None or number <= 0:
        return 0
    return int(number)


def _record_identifies_engine(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    return bool(str(record.get("engine_id") or "").strip() or str(record.get("engine_name") or "").strip())


def live_execution_proven(report: Any) -> bool:
    """True when this run has a successful engine response, not merely an attempted budget."""
    payload = _as_report(report) or {}
    card = payload.get("ai_visibility_scorecard") or {}
    records = []
    if isinstance(card, dict):
        if _positive_int(card.get("successful_runs")) > 0:
            return True
        card_records = card.get("observatory_records") or []
        if isinstance(card_records, list):
            records.extend(card_records)
    top_records = payload.get("observatory_records") or []
    if isinstance(top_records, list):
        records.extend(top_records)
    return any(_record_identifies_engine(record) for record in records)


def grade_for_displayed(score: float) -> str:
    """Grade bands shared with the editorial ledger."""
    if score >= 93:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 65:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def _score_claim_pattern(token: Optional[str] = None) -> "re.Pattern[str]":
    number = rf"{re.escape(token)}(?:\.0)?" if token else r"\d+(?:\.\d+)?"
    return re.compile(
        rf"{number}/100(?:\s*\([^)]*\))?(?:,?\s*grade\s+[A-F]\+?)?",
        re.IGNORECASE,
    )


def first_story_score(story: str) -> Optional[float]:
    """The first composite-shaped score in a sentence, if the prose states one."""
    if not story:
        return None
    match = _score_claim_pattern().search(story)
    if not match:
        return None
    raw = match.group(0).split("/100", 1)[0].strip()
    try:
        number = float(raw)
    except ValueError:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def story_matches_composite(story: str, composite: Optional[float], tolerance: float = 0.15) -> bool:
    """A story with no score claim agrees. A stated score must be the dossier composite."""
    claimed = first_story_score(story)
    if claimed is None or composite is None:
        return True
    return abs(claimed - composite) <= tolerance


def align_story_score(story: str, sealed_score: Any, composite: float) -> str:
    """Replace the headline score with the dossier composite and its grade.

    The sealed overall and a synthesizer number are both rewritten. A later
    pillar score in the same paragraph is left alone.
    """
    if not story or composite is None:
        return story
    replacement = f"{composite:.1f}/100 (grade {grade_for_displayed(composite)})"
    sealed = _num(sealed_score)
    if sealed is not None:
        sealed_token = str(int(round(sealed)))
        updated, count = _score_claim_pattern(sealed_token).subn(replacement, story, count=1)
        if count:
            return updated
    updated, count = _score_claim_pattern().subn(replacement, story, count=1)
    return updated if count else story


def _live_citation(payload: dict, honest: dict) -> Optional[float]:
    if not live_execution_proven(payload):
        return None
    live = _score(honest.get("live_ai_citation_score"))
    if live is None and honest.get("ai_visibility_status") == "MEASURED":
        live = _score(honest.get("ai_visibility_score"))
    if live is None:
        card = payload.get("ai_visibility_scorecard") or {}
        if isinstance(card, dict):
            live = _score(card.get("citation_rate_pct"))
    return live


def displayed_composite(report: Any) -> Optional[float]:
    """Return the dossier composite, or None when the report has no measured pillars."""
    payload = _as_report(report)
    if not payload:
        return None
    scores = payload.get("scores") or {}
    honest = payload.get("honest_scores") or {}
    categories = scores.get("category_scores") or {}
    geo = payload.get("geo_readiness") or {}

    def category_score(key: str) -> Optional[float]:
        category = categories.get(key) or {}
        if not isinstance(category, dict) or category.get("status") == "NOT_MEASURED":
            return None
        status = str(category.get("status") or "MEASURED").upper()
        if status in {"NOT_MEASURED", "UNAVAILABLE", "NOT_CONNECTED", "NOT_CONFIGURED", "SIMULATION_ONLY"}:
            return None
        return _score(category.get("score"))

    live = _live_citation(payload, honest if isinstance(honest, dict) else {})
    pillars = [
        (0.30, _score(honest.get("google_score")) if _score(honest.get("google_score")) is not None else category_score("TECHNICAL_SEO")),
        (0.25, _score(geo.get("extractability_score")) if _score(geo.get("extractability_score")) is not None else (
            _score(honest.get("ai_readiness_score")) if _score(honest.get("ai_readiness_score")) is not None else category_score("GEO")
        )),
        (0.25, live),
        (0.20, _score(honest.get("human_score")) if _score(honest.get("human_score")) is not None else category_score("UX_CONVERSION")),
    ]
    measured = [(weight, score) for weight, score in pillars if score is not None]
    if not measured:
        return None
    weight_sum = sum(weight for weight, _ in measured)
    if weight_sum <= 0:
        return None
    composite = sum(score * (weight / weight_sum) for weight, score in measured)
    return _round_to(composite, 1)
