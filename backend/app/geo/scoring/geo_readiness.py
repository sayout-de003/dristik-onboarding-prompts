"""
Legacy GEO readiness scoring compatibility shim.

Citation rate and sentiment are separate observations; combining them does not
produce a validated readiness score. Callers must use the canonical evidence-backed
GEO readiness evaluator instead.
"""
from typing import Optional


def calculate_geo_readiness(citation_rate: float, sentiment_score: float) -> Optional[float]:
    """Return no score until a canonical, evidence-backed readiness model is supplied."""
    return None


__all__ = ["calculate_geo_readiness"]
