from app.geo.scoring.geo_readiness import calculate_geo_readiness

def test_legacy_geo_readiness_does_not_blend_citation_rate_and_sentiment():
    score = calculate_geo_readiness(citation_rate=0.8, sentiment_score=0.9)
    assert score is None
