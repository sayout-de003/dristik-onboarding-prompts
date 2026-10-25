from datetime import datetime, timedelta, timezone

from app.connectors.authority.service import _connector_freshness


def test_connected_provider_is_fresh_only_when_next_sync_is_in_future():
    now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    status, age = _connector_freshness(
        connection_status="CONNECTED",
        last_success_at=(now - timedelta(hours=1)).isoformat(),
        next_sync_at=(now + timedelta(hours=2)).isoformat(),
        now=now,
    )
    assert status == "FRESH"
    assert age == 3600


def test_connected_provider_past_due_sync_is_stale():
    now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    status, age = _connector_freshness(
        connection_status="CONNECTED",
        last_success_at=(now - timedelta(days=3)).isoformat(),
        next_sync_at=(now - timedelta(hours=1)).isoformat(),
        now=now,
    )
    assert status == "STALE"
    assert age == 259200


def test_freshness_is_unknown_when_no_sync_contract_exists():
    now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    status, age = _connector_freshness(
        connection_status="CONNECTED",
        last_success_at=(now - timedelta(minutes=5)).isoformat(),
        next_sync_at=None,
        now=now,
    )
    assert status == "UNKNOWN"
    assert age == 300


def test_disconnected_provider_is_not_connected_not_stale():
    now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    assert _connector_freshness(
        connection_status="NOT_CONNECTED",
        last_success_at=None,
        next_sync_at=None,
        now=now,
    ) == ("NOT_CONNECTED", None)


def test_invalid_sync_timestamp_is_unknown_not_fresh():
    now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    status, age = _connector_freshness(
        connection_status="CONNECTED",
        last_success_at="not-a-date",
        next_sync_at=(now + timedelta(hours=1)).isoformat(),
        now=now,
    )
    assert status == "UNKNOWN"
    assert age is None
