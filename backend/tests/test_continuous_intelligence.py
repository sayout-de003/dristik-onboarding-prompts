"""Tests for persistent tenant-scoped continuous intelligence state."""
import sqlite3
from app.continuous_intelligence import ContinuousIntelligenceStore


def test_profile_roundtrip_and_tenant_isolation(tmp_path):
    store = ContinuousIntelligenceStore(str(tmp_path / "ci.db"))
    profile = store.upsert_profile("org_a", {
        "website_url": "example.com",
        "niche": "B2B SaaS",
        "business_model": "subscription software",
        "target_audience": "Operations leaders",
        "audience_pain_points": ["manual work"],
        "target_markets": ["India"],
        "languages": ["en"],
        "competitors": ["rival.example"],
        "goals": ["qualified leads"],
        "schedule_enabled": True,
    }, 10)
    assert profile["domain"] == "example.com"
    assert profile["niche"] == "B2B SaaS"
    assert profile["target_markets"] == ["India"]
    assert profile["schedule_enabled"] is True
    assert store.get_profile("org_b", profile["profile_id"]) is None
    assert store.list_profiles("org_b") == []


def test_monthly_run_claim_is_idempotent(tmp_path):
    store = ContinuousIntelligenceStore(str(tmp_path / "ci.db"))
    profile = store.upsert_profile("org_a", {"website_url": "https://example.com"}, 3)
    first = store.create_run(profile, "monthly", "2026-10")
    assert first
    # The same profile/month cannot be claimed twice while a monthly run is queued/running/completed.
    assert store.create_run(profile, "monthly", "2026-10") is None
    assert store.list_runs("org_a")[0]["run_id"] == first
    assert store.list_runs("org_b") == []


def test_due_profiles_only_include_active_paid_organizations(tmp_path):
    db = str(tmp_path / "ci.db")
    store = ContinuousIntelligenceStore(db)
    with sqlite3.connect(db) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS organizations(
            org_id TEXT PRIMARY KEY, plan TEXT NOT NULL, is_active INTEGER NOT NULL)""")
        conn.execute("INSERT INTO organizations(org_id,plan,is_active) VALUES('paid','professional',1)")
        conn.execute("INSERT INTO organizations(org_id,plan,is_active) VALUES('free','free_scan',1)")
        conn.execute("INSERT INTO organizations(org_id,plan,is_active) VALUES('inactive','enterprise',0)")
    store.upsert_profile("paid", {"website_url": "paid.example"}, 10)
    store.upsert_profile("free", {"website_url": "free.example"}, 1)
    store.upsert_profile("inactive", {"website_url": "inactive.example"}, 10)
    due = store.due_profiles("2026-10")
    assert [item["org_id"] for item in due] == ["paid"]


def test_invalid_or_credential_bearing_website_url_rejected(tmp_path):
    store = ContinuousIntelligenceStore(str(tmp_path / "ci.db"))
    try:
        store.upsert_profile("org_a", {"website_url": "https://user:secret@example.com"}, 3)
        assert False, "expected invalid URL to be rejected"
    except ValueError as exc:
        assert "credentials" in str(exc)
