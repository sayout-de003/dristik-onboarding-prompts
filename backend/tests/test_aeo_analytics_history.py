import os
import tempfile

from app.aeo.analytics_history import AeoAnalyticsHistoryStore


def test_aeo_history_records_one_snapshot_per_completed_analysis():
    with tempfile.TemporaryDirectory() as tmp:
        store = AeoAnalyticsHistoryStore(os.path.join(tmp, "aeo-history.db"))
        scorecard = {
            "pillar_a_content_readiness": {
                "composite_readiness_score": 72.5,
                "state": "SAMPLE_VERIFIED",
            },
            "pillar_b_technical_eligibility": {
                "composite_eligibility_score": None,
                "state": "DATA_UNAVAILABLE",
            },
            "pillar_c_observed_visibility": {"state": "NOT_TESTED"},
            "pillar_d_business_outcomes": {"state": "DATA_UNAVAILABLE"},
        }

        assert store.record_snapshot(
            "run_001", "https://www.example.com/path", scorecard,
            captured_at="2026-10-01T10:00:00+00:00",
        ) is True
        # A retry or duplicate completion event must not create another data point.
        assert store.record_snapshot(
            "run_001", "example.com", scorecard,
            captured_at="2026-10-01T10:01:00+00:00",
        ) is False

        history = store.get_domain_history("https://example.com/")
        assert len(history) == 1
        assert history[0]["analysis_id"] == "run_001"
        assert history[0]["domain"] == "example.com"
        assert history[0]["scorecard"]["pillar_a_content_readiness"]["composite_readiness_score"] == 72.5
        # Missing technical data remains null and is never coerced to zero.
        assert history[0]["scorecard"]["pillar_b_technical_eligibility"]["composite_eligibility_score"] is None
