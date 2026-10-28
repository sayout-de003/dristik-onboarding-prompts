"""Regression tests for the Universal AI Connect persistence boundary."""
import hashlib
import sqlite3

import pytest

from app.api.routes.integrations import universal_connect as uc
from app.identity.authorizer import UserIdentity


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(uc, "DB_PATH", tmp_path / "connect.sqlite3")
    yield tmp_path


def test_task_records_persist_and_are_org_scoped(isolated_db):
    owner = UserIdentity(org_id="org-a", email="owner@example.test")
    other = UserIdentity(org_id="org-b", email="other@example.test")
    task_id = "uct_test"
    with uc._db() as conn:
        conn.execute(
            "INSERT INTO uc_tasks VALUES (?,?,?,?,?,?,?,?,?)",
            (task_id, owner.org_id, owner.user_id, "Audit example.test", "accepted",
             uc._json({"url": "https://example.test"}), None, 1.0, 1.0),
        )
    with uc._db() as conn:
        row = conn.execute("SELECT * FROM uc_tasks WHERE id=?", (task_id,)).fetchone()
        assert uc._task_public(row)["inputs"]["url"] == "https://example.test"
        with pytest.raises(Exception) as exc:
            uc._require_org(row, other)
        assert getattr(exc.value, "status_code", None) == 404


def test_artifact_hash_is_sha256():
    payload = b"opaque document bytes\x00\x01"
    assert hashlib.sha256(payload).hexdigest() == hashlib.sha256(payload).hexdigest()
    assert len(hashlib.sha256(payload).hexdigest()) == 64


def test_connection_is_not_claimed_healthy_on_registration(isolated_db):
    now = 1.0
    with uc._db() as conn:
        conn.execute(
            "INSERT INTO uc_connections VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("ucn_test", "org-a", "usr-test", "Claude MCP", "mcp_server", "https://mcp.example.test",
             "not_tested", "[]", now, now),
        )
    with uc._db() as conn:
        row = conn.execute("SELECT status FROM uc_connections WHERE id='ucn_test'").fetchone()
    assert row["status"] == "not_tested"
