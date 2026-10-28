"""Security regression tests for Dristik-issued external AI credentials."""
import asyncio
import hashlib
import json
import time

import pytest
from fastapi import HTTPException

from app.api.routes.integrations import universal_connect as uc
from app.identity.authorizer import UserIdentity


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(uc, "DB_PATH", tmp_path / "connect.sqlite3")
    monkeypatch.setenv("DRISTIK_CONNECT_IDENTITY_DOMAIN", "connect.example.test")
    yield tmp_path


def owner():
    return UserIdentity(org_id="org-a", email="owner@example.test", role="owner")


def test_create_connection_shows_key_once_and_stores_only_hash(isolated_db):
    response = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Claude workspace", grant_profile="full_access"),
        owner(),
    ))
    assert response["connection_email"].endswith("@connect.example.test")
    assert response["api_key"].startswith("drk_live_")
    assert response["key_display_policy"] == "shown_once"
    assert response["grant_profile"] == "full_access"
    assert "*" in response["scopes"]
    with uc._db() as conn:
        row = conn.execute("SELECT * FROM uc_ai_connections WHERE id=?", (response["id"],)).fetchone()
    assert row["key_hash"] == hashlib.sha256(response["api_key"].encode()).hexdigest()
    assert response["api_key"] not in row["key_hash"]
    assert row["name"] == "Claude workspace"


def test_connection_key_authentication_is_tenant_scoped_and_returns_grant(isolated_db):
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Audit operator", grant_profile="audit_operator"),
        owner(),
    ))
    user = asyncio.run(uc.get_mcp_user(
        authorization="Bearer " + created["api_key"],
        connection_email=created["connection_email"],
        session_user=None,
    ))
    assert user.org_id == "org-a"
    assert user.auth_provider == "dristik_connect"
    assert user.user_id == created["id"]
    assert uc._mcp_authorized(user, "audit.create")
    assert not uc._mcp_authorized(user, "workflow.execute")


def test_invalid_or_wrong_identity_credentials_are_rejected(isolated_db):
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Read only", grant_profile="read_only"), owner()
    ))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(uc.get_mcp_user(
            authorization="Bearer " + created["api_key"],
            connection_email="other@connect.example.test",
            session_user=None,
        ))
    assert exc.value.status_code == 401


def test_revoked_connection_cannot_authenticate(isolated_db):
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Temporary", grant_profile="full_access"), owner()
    ))
    asyncio.run(uc.revoke_ai_connection(created["id"], owner()))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(uc.get_mcp_user(
            authorization="Bearer " + created["api_key"],
            connection_email=created["connection_email"],
            session_user=None,
        ))
    assert exc.value.status_code == 401


def test_key_rotation_invalidates_old_key_and_returns_new_key(isolated_db):
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Rotating", grant_profile="full_access"), owner()
    ))
    rotated = asyncio.run(uc.rotate_ai_connection(created["id"], owner()))
    assert rotated["api_key"] != created["api_key"]
    with pytest.raises(HTTPException):
        asyncio.run(uc.get_mcp_user(
            authorization="Bearer " + created["api_key"],
            connection_email=created["connection_email"],
            session_user=None,
        ))
    new_user = asyncio.run(uc.get_mcp_user(
        authorization="Bearer " + rotated["api_key"],
        connection_email=rotated["connection_email"],
        session_user=None,
    ))
    assert new_user.user_id == created["id"]


def test_expired_connection_is_rejected(isolated_db):
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Expired", grant_profile="full_access", expires_in_days=1), owner()
    ))
    with uc._db() as conn:
        conn.execute("UPDATE uc_ai_connections SET expires_at=? WHERE id=?", (time.time() - 1, created["id"]))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(uc.get_mcp_user(
            authorization="Bearer " + created["api_key"],
            connection_email=created["connection_email"],
            session_user=None,
        ))
    assert exc.value.status_code == 401
