"""Dristik-issued credentials for external AI/MCP clients.

Keys are shown once, stored only as SHA-256 digests, and always scoped to one
organization and an explicit permission profile. This module intentionally does
not expose provider credentials or bypass the canonical audit authorization.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.identity.authorizer import UserIdentity
from app.identity.deps import get_current_user, get_current_user_optional, require_permission
from app.domain.enums import UserRole

router = APIRouter(prefix="/connect/ai-connections", tags=["Dristik AI Connections"])
DB_PATH = Path(os.getenv("DRISTIK_CONNECT_DB_PATH", str(Path(__file__).resolve().parents[4] / "data" / "universal_connect.sqlite3")))
PROFILE_ROLES = {
    "read_only": UserRole.VIEWER,
    "audit_operator": UserRole.ANALYST,
    "workflow_admin": UserRole.ADMIN,
    "full_access": UserRole.OWNER,
}
PROFILE_PERMISSIONS = {
    "read_only": ["capabilities.read", "audit.read", "findings.read", "evidence.read", "report.read"],
    "audit_operator": ["capabilities.read", "template.read", "audit.create", "audit.read", "audit.cancel", "agent.read", "evidence.read", "findings.read", "report.read", "report.export"],
    "workflow_admin": ["capabilities.read", "template.read", "audit.create", "audit.read", "audit.cancel", "agent.read", "agent.execute", "subagent.read", "subagent.execute", "workflow.read", "workflow.execute", "connector.read", "connector.test", "evidence.read", "findings.read", "report.read", "report.export", "schedule.read"],
    "full_access": ["*"],
}


@contextmanager
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS uc_ai_connections (
            id TEXT PRIMARY KEY, org_id TEXT NOT NULL, created_by TEXT NOT NULL,
            name TEXT NOT NULL, connection_email TEXT NOT NULL, profile TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE, key_prefix TEXT NOT NULL,
            status TEXT NOT NULL, expires_at REAL, created_at REAL NOT NULL,
            updated_at REAL NOT NULL, last_used_at REAL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_uc_ai_connections_org ON uc_ai_connections(org_id, created_at)")
        conn.execute("""CREATE TABLE IF NOT EXISTS uc_ai_connection_events (
            id TEXT PRIMARY KEY, connection_id TEXT NOT NULL, org_id TEXT NOT NULL,
            event TEXT NOT NULL, created_at REAL NOT NULL, metadata_json TEXT NOT NULL
        )""")
        yield conn
        conn.commit()
    finally:
        conn.close()


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _public(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "name": row["name"], "connection_email": row["connection_email"],
        "profile": row["profile"], "permissions": PROFILE_PERMISSIONS[row["profile"]],
        "key_prefix": row["key_prefix"], "status": row["status"], "expires_at": row["expires_at"],
        "created_at": row["created_at"], "updated_at": row["updated_at"], "last_used_at": row["last_used_at"],
        "mcp_endpoint": os.getenv("DRISTIK_PUBLIC_MCP_URL", "/api/v1/mcp"),
    }


class AIConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    profile: Literal["read_only", "audit_operator", "workflow_admin", "full_access"] = "audit_operator"
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


def get_mcp_user(
    request: Request,
    authorization: str | None = Header(default=None),
    session_user: UserIdentity | None = Depends(get_current_user_optional),
) -> UserIdentity:
    """Accept a Dristik-issued key for MCP, while preserving signed-in web access."""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token.startswith("drk_live_"):
        if session_user is None:
            raise HTTPException(status_code=401, detail="Provide a valid Dristik AI connection key.")
        return session_user

    now = time.time()
    with _db() as conn:
        row = conn.execute("SELECT * FROM uc_ai_connections WHERE key_hash=?", (_digest(token),)).fetchone()
        if row is None or row["status"] != "active" or (row["expires_at"] is not None and row["expires_at"] <= now):
            raise HTTPException(status_code=401, detail="Dristik AI connection key is invalid, expired, or revoked.")
        conn.execute("UPDATE uc_ai_connections SET last_used_at=?,updated_at=? WHERE id=?", (now, now, row["id"]))
        conn.execute("INSERT INTO uc_ai_connection_events VALUES (?,?,?,?,?,?)",
                     ("uce_" + uuid.uuid4().hex, row["id"], row["org_id"], "authenticated", now, "{}"))
    request.state.ai_connection = {"id": row["id"], "profile": row["profile"], "org_id": row["org_id"]}
    return UserIdentity(
        user_id="ai_" + row["id"], org_id=row["org_id"], email=row["connection_email"],
        role=PROFILE_ROLES[row["profile"]], auth_provider="dristik_ai_connection",
    )


def require_ai_permission(user: UserIdentity, permission: str, request: Request) -> None:
    connection = getattr(request.state, "ai_connection", None)
    if not connection:
        return
    profile = connection["profile"]
    allowed = PROFILE_PERMISSIONS.get(profile, [])
    if "*" not in allowed and permission not in allowed:
        raise HTTPException(status_code=403, detail=f"This AI connection is not granted '{permission}'.")


@router.post("", status_code=201)
async def create_ai_connection(body: AIConnectionCreate, user: UserIdentity = Depends(require_permission("org:manage"))):
    now = time.time()
    connection_id = "uai_" + uuid.uuid4().hex
    raw_key = "drk_live_" + secrets.token_urlsafe(32)
    email_domain = os.getenv("DRISTIK_CONNECT_EMAIL_DOMAIN", "connect.dristik.local").strip().lower()
    if not email_domain or "/" in email_domain or "@" in email_domain:
        raise HTTPException(status_code=503, detail="DRISTIK_CONNECT_EMAIL_DOMAIN is invalid.")
    connection_email = f"{connection_id.lower()}@{email_domain}"
    expires_at = now + body.expires_in_days * 86400 if body.expires_in_days else None
    with _db() as conn:
        conn.execute("INSERT INTO uc_ai_connections VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (connection_id, user.org_id, user.user_id, body.name, connection_email, body.profile,
                      _digest(raw_key), raw_key[:16], "active", expires_at, now, now, None))
        conn.execute("INSERT INTO uc_ai_connection_events VALUES (?,?,?,?,?,?)",
                     ("uce_" + uuid.uuid4().hex, connection_id, user.org_id, "created", now, "{}"))
        row = conn.execute("SELECT * FROM uc_ai_connections WHERE id=?", (connection_id,)).fetchone()
    return {**_public(row), "api_key": raw_key, "key_warning": "Copy this key now. It cannot be retrieved again."}


@router.get("")
async def list_ai_connections(user: UserIdentity = Depends(get_current_user)):
    with _db() as conn:
        rows = conn.execute("SELECT * FROM uc_ai_connections WHERE org_id=? ORDER BY created_at DESC", (user.org_id,)).fetchall()
    return {"connections": [_public(row) for row in rows]}


@router.get("/validate")
async def validate_ai_connection(request: Request, user: UserIdentity = Depends(get_mcp_user)):
    connection = getattr(request.state, "ai_connection", None)
    if not connection:
        return {"valid": True, "auth_type": "dristik_session", "tenant_id": user.org_id}
    return {"valid": True, "auth_type": "dristik_ai_connection", "connection_id": connection["id"],
            "tenant_id": user.org_id, "profile": connection["profile"],
            "permissions": PROFILE_PERMISSIONS[connection["profile"]],
            "mcp_endpoint": os.getenv("DRISTIK_PUBLIC_MCP_URL", "/api/v1/mcp")}


@router.post("/{connection_id}/rotate")
async def rotate_ai_connection(connection_id: str, user: UserIdentity = Depends(require_permission("org:manage"))):
    now = time.time()
    raw_key = "drk_live_" + secrets.token_urlsafe(32)
    with _db() as conn:
        row = conn.execute("SELECT * FROM uc_ai_connections WHERE id=? AND org_id=?", (connection_id, user.org_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="AI connection not found.")
        conn.execute("UPDATE uc_ai_connections SET key_hash=?,key_prefix=?,status='active',updated_at=? WHERE id=?",
                     (_digest(raw_key), raw_key[:16], now, connection_id))
        conn.execute("INSERT INTO uc_ai_connection_events VALUES (?,?,?,?,?,?)",
                     ("uce_" + uuid.uuid4().hex, connection_id, user.org_id, "rotated", now, "{}"))
        updated = conn.execute("SELECT * FROM uc_ai_connections WHERE id=?", (connection_id,)).fetchone()
    return {**_public(updated), "api_key": raw_key, "key_warning": "Previous key is invalid. Copy this key now."}


@router.post("/{connection_id}/revoke")
async def revoke_ai_connection(connection_id: str, user: UserIdentity = Depends(require_permission("org:manage"))):
    now = time.time()
    with _db() as conn:
        row = conn.execute("SELECT id FROM uc_ai_connections WHERE id=? AND org_id=?", (connection_id, user.org_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="AI connection not found.")
        conn.execute("UPDATE uc_ai_connections SET status='revoked',updated_at=? WHERE id=?", (now, connection_id))
        conn.execute("INSERT INTO uc_ai_connection_events VALUES (?,?,?,?,?,?)",
                     ("uce_" + uuid.uuid4().hex, connection_id, user.org_id, "revoked", now, "{}"))
    return {"id": connection_id, "status": "revoked", "revoked_at": now}
