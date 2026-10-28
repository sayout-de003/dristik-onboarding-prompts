"""Compatibility entry point for the canonical evidence-backed GEO readiness score.

Citation rate and sentiment are visibility/answer-quality observations; neither
alone nor blended together defines on-page readiness. Legacy calls that pass
only those two values return None instead of manufacturing a readiness score.
"""
from typing import Mapping, Optional

from app.domain.models import GeoDimensionScore
from app.geo.readiness import _compute_composite


def calculate_geo_readiness(
    citation_rate: Optional[float] = None,
    sentiment_score: Optional[float] = None,
    *,
    dimension_scores: Optional[Mapping[str, GeoDimensionScore]] = None,
) -> Optional[float]:
    """Return the canonical weighted score, or None when readiness is unmeasured.

    The two positional arguments remain accepted for source compatibility but
    are intentionally not used to calculate GEO readiness.
    """
    if not dimension_scores:
        return None
    return _compute_composite(dict(dimension_scores))


__all__ = ["calculate_geo_readiness"]
