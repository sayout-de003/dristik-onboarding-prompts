"""Evidence-aware legacy SEO score engine.

Missing pillars are excluded and the remaining configured weights are normalized.
A missing measurement is never silently converted into a passing score.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


class ScoreEngine:
    """Calculate a transparent weighted score from measured pillars only."""

    WEIGHTS: dict[str, float] = {
        "technical": 0.25,
        "content": 0.20,
        "geo": 0.15,
        "authority": 0.15,
        "ux": 0.15,
        "conversion": 0.10,
    }

    def calculate_overall_score(self, pillar_scores: Mapping[str, Any]) -> float:
        """Return a 0–100 score using only supplied, valid measurements.

        Values that are absent or explicitly None are treated as unmeasured,
        not as zero and not as an invented default. Invalid supplied values fail
        closed so malformed upstream data cannot silently affect the score.
        """
        if not isinstance(pillar_scores, Mapping):
            raise TypeError("pillar_scores must be a mapping")

        measured: dict[str, float] = {}
        for pillar, raw_value in pillar_scores.items():
            if pillar not in self.WEIGHTS or raw_value is None:
                continue
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise ValueError(f"score for {pillar!r} must be a finite number from 0 to 100")
            value = float(raw_value)
            if not math.isfinite(value) or not 0.0 <= value <= 100.0:
                raise ValueError(f"score for {pillar!r} must be a finite number from 0 to 100")
            measured[pillar] = value

        if not measured:
            raise ValueError("cannot calculate an overall score: no measured pillars are available")

        available_weight = sum(self.WEIGHTS[key] for key in measured)
        weighted_score = sum(
            measured[key] * self.WEIGHTS[key] for key in measured
        ) / available_weight
        return round(weighted_score, 1)

    def score_breakdown(self, pillar_scores: Mapping[str, Any]) -> dict[str, Any]:
        """Return the score plus its denominator, coverage, and normalized weights."""
        score = self.calculate_overall_score(pillar_scores)
        measured = {
            key: float(value)
            for key, value in pillar_scores.items()
            if key in self.WEIGHTS and value is not None
        }
        available_weight = sum(self.WEIGHTS[key] for key in measured)
        return {
            "overall_score": score,
            "measured_pillars": sorted(measured),
            "unmeasured_pillars": sorted(set(self.WEIGHTS) - set(measured)),
            "coverage_pct": round(len(measured) / len(self.WEIGHTS) * 100, 1),
            "normalized_weights": {
                key: round(self.WEIGHTS[key] / available_weight, 6)
                for key in sorted(measured)
            },
            "score_status": "MEASURED" if len(measured) == len(self.WEIGHTS) else "PARTIAL",
        }
