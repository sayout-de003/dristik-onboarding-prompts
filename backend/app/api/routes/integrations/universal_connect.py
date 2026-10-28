"""Universal AI/software collaboration API.

Durable, tenant-scoped foundation for connections, capability discovery, task
exchange, artifact transfer, and authenticated MCP tool discovery. A registered
connection is not considered healthy until a real adapter tests it.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import hmac
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.identity.authorizer import Authorizer, UserIdentity
from app.domain.enums import UserRole
from app.identity.deps import get_current_user, get_current_user_optional, require_permission

router = APIRouter(tags=["Universal AI Connect"])
MCP_VERSION = "2025-03-26"
MAX_ARTIFACT_BYTES = int(os.getenv("DRISTIK_CONNECT_MAX_ARTIFACT_BYTES", str(25 * 1024 * 1024)))
DB_PATH = Path(os.getenv("DRISTIK_CONNECT_DB_PATH", str(Path(__file__).resolve().parents[4] / "data" / "universal_connect.sqlite3")))


@contextmanager
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS uc_ai_connections (
          id TEXT PRIMARY KEY, org_id TEXT NOT NULL, created_by TEXT NOT NULL,
          connection_email TEXT NOT NULL UNIQUE, key_hash TEXT NOT NULL UNIQUE,
          grant_profile TEXT NOT NULL, scopes_json TEXT NOT NULL, status TEXT NOT NULL,
          expires_at REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
          last_used_at REAL
        );
        CREATE INDEX IF NOT EXISTS idx_uc_ai_connections_org ON uc_ai_connections(org_id, created_at);
        CREATE TABLE IF NOT EXISTS uc_connections (
          id TEXT PRIMARY KEY, org_id TEXT NOT NULL, created_by TEXT NOT NULL,
          name TEXT NOT NULL, kind TEXT NOT NULL, endpoint TEXT, status TEXT NOT NULL,
          capabilities_json TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_uc_connections_org ON uc_connections(org_id);
        CREATE TABLE IF NOT EXISTS uc_tasks (
          id TEXT PRIMARY KEY, org_id TEXT NOT NULL, created_by TEXT NOT NULL,
          goal TEXT NOT NULL, status TEXT NOT NULL, input_json TEXT NOT NULL,
          result_json TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_uc_tasks_org ON uc_tasks(org_id, created_at);
        CREATE TABLE IF NOT EXISTS uc_messages (
          id TEXT PRIMARY KEY, org_id TEXT NOT NULL, task_id TEXT NOT NULL,
          sender TEXT NOT NULL, recipient TEXT, message_type TEXT NOT NULL,
          payload_json TEXT NOT NULL, created_at REAL NOT NULL,
          FOREIGN KEY(task_id) REFERENCES uc_tasks(id)
        );
        CREATE INDEX IF NOT EXISTS idx_uc_messages_task ON uc_messages(org_id, task_id, created_at);
        CREATE TABLE IF NOT EXISTS uc_artifacts (
          id TEXT PRIMARY KEY, org_id TEXT NOT NULL, task_id TEXT, filename TEXT NOT NULL,
          content_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
          storage_path TEXT NOT NULL, created_by TEXT NOT NULL, created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_uc_artifacts_org ON uc_artifacts(org_id);
        """)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _require_org(row: sqlite3.Row | None, user: UserIdentity) -> sqlite3.Row:
    if row is None or row["org_id"] != user.org_id:
        # Do not reveal whether another tenant owns the identifier.
        raise HTTPException(status_code=404, detail="Resource not found.")
    return row


class ConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["ai_provider", "mcp_server", "rest_api", "webhook", "custom"]
    endpoint: str | None = Field(default=None, max_length=2048)
    capabilities: list[str] = Field(default_factory=list, max_length=100)


class TaskCreate(BaseModel):
    goal: str = Field(min_length=1, max_length=8000)
    inputs: dict[str, Any] = Field(default_factory=dict)


class MessageCreate(BaseModel):
    sender: str = Field(min_length=1, max_length=160)
    recipient: str | None = Field(default=None, max_length=160)
    message_type: str = Field(default="text", min_length=1, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


def _task_public(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["inputs"] = json.loads(item.pop("input_json"))
    result = item.pop("result_json")
    item["result"] = json.loads(result) if result else None
    return item


@router.get("/connect/connections")
async def list_connections(user: UserIdentity = Depends(get_current_user)):
    with _db() as conn:
        rows = conn.execute("SELECT * FROM uc_connections WHERE org_id=? ORDER BY created_at DESC", (user.org_id,)).fetchall()
    return {"connections": [{**dict(r), "capabilities": json.loads(r["capabilities_json"])} for r in rows]}


@router.post("/connect/connections", status_code=201)
async def create_connection(body: ConnectionCreate, user: UserIdentity = Depends(require_permission("org:manage"))):
    now = time.time()
    connection_id = "ucn_" + uuid.uuid4().hex
    with _db() as conn:
        conn.execute(
            "INSERT INTO uc_connections VALUES (?,?,?,?,?,?,?,?,?,?)",
            (connection_id, user.org_id, user.user_id, body.name, body.kind, body.endpoint,
             "not_tested", _json(body.capabilities), now, now),
        )
    return {"id": connection_id, "name": body.name, "kind": body.kind, "endpoint": body.endpoint,
            "status": "not_tested", "capabilities": body.capabilities, "created_at": now,
            "note": "Registered only; connectivity and credentials have not been verified."}


@router.get("/connect/capabilities")
async def list_capabilities(user: UserIdentity = Depends(get_current_user)):
    return {"tenant_id": user.org_id, "capabilities": [
        {"name": "connections.list", "status": "available", "description": "List tenant-owned registered connections"},
        {"name": "tasks.create", "status": "available", "description": "Create a durable collaboration task record"},
        {"name": "tasks.get", "status": "available", "description": "Read a tenant-owned collaboration task"},
        {"name": "tasks.messages", "status": "available", "description": "Persist messages against a tenant-owned task"},
        {"name": "artifacts.upload", "status": "available", "description": "Store opaque bytes with a SHA-256 digest"},
        {"name": "audit.website", "status": "available", "description": "Start the canonical Dristik website-audit workflow with normal entitlement and evidence gates"}
    ]}


@router.post("/connect/tasks", status_code=201)
async def create_task(body: TaskCreate, user: UserIdentity = Depends(require_permission("mission:create"))):
    now = time.time()
    task_id = "uct_" + uuid.uuid4().hex
    with _db() as conn:
        conn.execute("INSERT INTO uc_tasks VALUES (?,?,?,?,?,?,?,?,?)",
                     (task_id, user.org_id, user.user_id, body.goal, "accepted", _json(body.inputs), None, now, now))
    return {"id": task_id, "goal": body.goal, "status": "accepted", "created_at": now,
            "execution_started": False,
            "note": "Durably accepted; no agent execution is claimed until a worker adapter is connected."}



@router.post("/connect/tasks/{task_id}/execute-audit")
async def execute_task_audit(task_id: str, background_tasks: BackgroundTasks, user: UserIdentity = Depends(require_permission("mission:create"))):
    """Submit a collaboration task to Dristik's existing audit pipeline."""
    with _db() as conn:
        task = _require_org(conn.execute("SELECT * FROM uc_tasks WHERE id=?", (task_id,)).fetchone(), user)
        inputs = json.loads(task["input_json"])
    url = inputs.get("url") or inputs.get("website_url")
    if not isinstance(url, str) or not url.strip():
        raise HTTPException(status_code=422, detail="Task inputs must include a website url.")
    try:
        from app.domain.models import AnalysisRequest
        from app.api.routes.audits.analyses import start_analysis
        request = AnalysisRequest(website_url=url, max_crawl_pages=1)
        run = await start_analysis(request, background_tasks, user)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not submit task to canonical audit pipeline.") from exc
    now = time.time()
    audit = {"analysis_id": run.analysis_id, "website_url": run.website_url, "status": str(getattr(run.status, "value", run.status))}
    with _db() as conn:
        conn.execute("UPDATE uc_tasks SET status='running',result_json=?,updated_at=? WHERE id=?", (_json(audit), now, task_id))
    return {"task_id": task_id, "status": "running", "execution_started": True, "audit": audit}


@router.get("/connect/tasks")
async def list_tasks(user: UserIdentity = Depends(get_current_user), limit: int = 50):
    limit = max(1, min(limit, 100))
    with _db() as conn:
        rows = conn.execute("SELECT * FROM uc_tasks WHERE org_id=? ORDER BY created_at DESC LIMIT ?", (user.org_id, limit)).fetchall()
    return {"tasks": [_task_public(r) for r in rows]}


@router.get("/connect/tasks/{task_id}")
async def get_task(task_id: str, user: UserIdentity = Depends(get_current_user)):
    with _db() as conn:
        row = _require_org(conn.execute("SELECT * FROM uc_tasks WHERE id=?", (task_id,)).fetchone(), user)
        messages = conn.execute("SELECT id,sender,recipient,message_type,payload_json,created_at FROM uc_messages WHERE org_id=? AND task_id=? ORDER BY created_at", (user.org_id, task_id)).fetchall()
        artifacts = conn.execute("SELECT id,filename,content_type,size_bytes,sha256,created_at FROM uc_artifacts WHERE org_id=? AND task_id=? ORDER BY created_at", (user.org_id, task_id)).fetchall()
    return {**_task_public(row),
            "messages": [{**dict(m), "payload": json.loads(m["payload_json"])} for m in messages],
            "artifacts": [dict(a) for a in artifacts]}


@router.post("/connect/tasks/{task_id}/messages", status_code=201)
async def send_message(task_id: str, body: MessageCreate, user: UserIdentity = Depends(require_permission("mission:create"))):
    now, message_id = time.time(), "ucm_" + uuid.uuid4().hex
    with _db() as conn:
        _require_org(conn.execute("SELECT * FROM uc_tasks WHERE id=?", (task_id,)).fetchone(), user)
        conn.execute("INSERT INTO uc_messages VALUES (?,?,?,?,?,?,?,?)",
                     (message_id, user.org_id, task_id, body.sender, body.recipient, body.message_type, _json(body.payload), now))
        conn.execute("UPDATE uc_tasks SET updated_at=? WHERE id=?", (now, task_id))
    return {"id": message_id, "task_id": task_id, "created_at": now, "delivery_status": "stored_not_delivered",
            "note": "Message is persisted; remote delivery requires a configured transport adapter."}


@router.post("/connect/tasks/{task_id}/artifacts", status_code=201)
async def upload_artifact(task_id: str, request: Request, user: UserIdentity = Depends(require_permission("mission:create"))):
    filename = request.headers.get("x-filename", "artifact.bin")
    if len(filename) > 255 or "/" in filename or "\\" in filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid x-filename header.")
    content_type = request.headers.get("content-type", "application/octet-stream").split(";", 1)[0][:160]
    body = await request.body()
    if len(body) > MAX_ARTIFACT_BYTES:
        raise HTTPException(status_code=413, detail=f"Artifact exceeds {MAX_ARTIFACT_BYTES} bytes.")
    with _db() as conn:
        _require_org(conn.execute("SELECT * FROM uc_tasks WHERE id=?", (task_id,)).fetchone(), user)
    digest, artifact_id = hashlib.sha256(body).hexdigest(), "uca_" + uuid.uuid4().hex
    artifact_root = Path(os.getenv("DRISTIK_CONNECT_ARTIFACT_DIR", str(DB_PATH.parent / "artifacts"))).resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    storage_path = (artifact_root / f"{artifact_id}.blob").resolve()
    if storage_path.parent != artifact_root:
        raise HTTPException(status_code=400, detail="Invalid artifact storage path.")
    storage_path.write_bytes(body)
    now = time.time()
    with _db() as conn:
        conn.execute("INSERT INTO uc_artifacts VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (artifact_id, user.org_id, task_id, filename, content_type, len(body), digest,
                      str(storage_path), user.user_id, now))
    return {"id": artifact_id, "task_id": task_id, "filename": filename, "content_type": content_type,
            "size_bytes": len(body), "sha256": digest, "created_at": now, "status": "stored"}


@router.get("/connect/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, user: UserIdentity = Depends(get_current_user)):
    with _db() as conn:
        row = _require_org(conn.execute("SELECT * FROM uc_artifacts WHERE id=?", (artifact_id,)).fetchone(), user)
    path = Path(row["storage_path"])
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Artifact metadata exists but its bytes are unavailable.")
    safe_name = row["filename"].replace('"', "").replace("\\r", "").replace("\\n", "")
    return StreamingResponse(path.open("rb"), media_type=row["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"', "X-Content-SHA256": row["sha256"]})




# Permission sets are deliberately explicit. "Full" means all Dristik capabilities
# inside this tenant; it never grants cross-tenant or platform-infrastructure access.
AI_GRANT_SCOPES: dict[str, list[str]] = {
    "read_only": ["capabilities.list", "templates.list", "agents.list", "audit.read", "report.read", "findings.read", "evidence.read", "tasks.read"],
    "audit_operator": ["capabilities.list", "templates.list", "agents.list", "audit.create", "audit.read", "report.read", "findings.read", "evidence.read", "tasks.create", "tasks.read"],
    "workflow_admin": ["capabilities.list", "templates.list", "agents.list", "agent.execute", "workflow.execute", "audit.create", "audit.read", "audit.cancel", "report.read", "findings.read", "evidence.read", "tasks.create", "tasks.read", "connector.read"],
    "full_access": ["*"],
}


class AIConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    grant_profile: Literal["read_only", "audit_operator", "workflow_admin", "full_access"] = "full_access"
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


class AIConnectionValidate(BaseModel):
    connection_email: str = Field(min_length=3, max_length=254)
    api_key: str = Field(min_length=20, max_length=256)


def _connection_domain() -> str:
    # Configure this to a domain controlled by the Dristik deployment. The value
    # is a connection identity, not an inbox used for email delivery.
    return os.getenv("DRISTIK_CONNECT_IDENTITY_DOMAIN", "connect.dristik.local").strip().lower()


def _public_ai_connection(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "connection_email": row["connection_email"],
        "grant_profile": row["grant_profile"], "scopes": json.loads(row["scopes_json"]),
        "status": row["status"], "expires_at": row["expires_at"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "last_used_at": row["last_used_at"],
    }


def _connection_scopes(user: UserIdentity) -> list[str] | None:
    if user.auth_provider != "dristik_connect":
        return None
    with _db() as conn:
        row = conn.execute(
            "SELECT scopes_json,status,expires_at FROM uc_ai_connections WHERE id=? AND org_id=?",
            (user.user_id, user.org_id),
        ).fetchone()
    if row is None or row["status"] != "active" or (row["expires_at"] is not None and row["expires_at"] <= time.time()):
        raise HTTPException(status_code=401, detail="Dristik AI connection is revoked or expired.")
    return json.loads(row["scopes_json"])


def _mcp_authorized(user: UserIdentity, scope: str, permission: str | None = None) -> bool:
    scopes = _connection_scopes(user)
    if scopes is not None:
        return "*" in scopes or scope in scopes
    return Authorizer.can_perform(user, permission or "mission:read")


async def get_mcp_user(
    authorization: str | None = Header(default=None),
    connection_email: str | None = Header(default=None, alias="X-Dristik-Connection-Email"),
    session_user: UserIdentity | None = Depends(get_current_user_optional),
) -> UserIdentity:
    """Authenticate a Dristik-issued connection key or preserve signed-in MCP access."""
    token = authorization.split(" ", 1)[1].strip() if authorization and authorization.lower().startswith("bearer ") else ""
    if not token.startswith("drk_live_"):
        if session_user is None:
            raise HTTPException(status_code=401, detail="Provide a Dristik connection API key or sign in.")
        return session_user
    if not connection_email:
        raise HTTPException(status_code=401, detail="X-Dristik-Connection-Email is required with a connection API key.")
    key_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM uc_ai_connections WHERE connection_email=? AND key_hash=?",
            (connection_email.strip().lower(), key_hash),
        ).fetchone()
        if row is None or row["status"] != "active" or (row["expires_at"] is not None and row["expires_at"] <= time.time()):
            raise HTTPException(status_code=401, detail="Invalid, expired, or revoked Dristik connection credentials.")
        conn.execute("UPDATE uc_ai_connections SET last_used_at=?,updated_at=? WHERE id=?",
                     (time.time(), time.time(), row["id"]))
    role_by_profile = {
        "read_only": UserRole.VIEWER,
        "audit_operator": UserRole.ANALYST,
        "workflow_admin": UserRole.ADMIN,
        "full_access": UserRole.OWNER,
    }
    return UserIdentity(
        user_id=row["id"], org_id=row["org_id"], email=row["connection_email"],
        full_name=row["name"] if "name" in row.keys() else "Dristik AI connection",
        role=role_by_profile.get(row["grant_profile"], UserRole.VIEWER),
        auth_provider="dristik_connect", is_active=True,
    )


@router.post("/connect/ai-connections", status_code=201)
async def create_ai_connection(
    body: AIConnectionCreate,
    user: UserIdentity = Depends(require_permission("org:manage")),
):
    """Issue a one-time API key for an external AI client to authenticate to Dristik."""
    now = time.time()
    connection_id = "dai_" + uuid.uuid4().hex
    domain = _connection_domain()
    if not domain or any(ch in domain for ch in "/:@ "):
        raise HTTPException(status_code=503, detail="DRISTIK_CONNECT_IDENTITY_DOMAIN is misconfigured.")
    email = f"ai-{connection_id[-12:]}@{domain}"
    api_key = "drk_live_" + secrets.token_urlsafe(36)
    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    expires_at = now + body.expires_in_days * 86400 if body.expires_in_days else None
    scopes = AI_GRANT_SCOPES[body.grant_profile]
    with _db() as conn:
        conn.execute(
            "INSERT INTO uc_ai_connections (id,org_id,created_by,connection_email,key_hash,grant_profile,scopes_json,status,expires_at,created_at,updated_at,last_used_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL)",
            (connection_id, user.org_id, user.user_id, email, key_hash, body.grant_profile,
             _json(scopes), "active", expires_at, now, now),
        )
    return {
        "id": connection_id, "name": body.name, "connection_email": email,
        "api_key": api_key, "grant_profile": body.grant_profile, "scopes": scopes,
        "status": "active", "expires_at": expires_at,
        "mcp_endpoint": os.getenv("DRISTIK_MCP_PUBLIC_URL", "/api/v1/mcp"),
        "key_display_policy": "shown_once",
        "instructions": "Copy the API key now. It cannot be retrieved later. Configure the AI client to send Authorization: Bearer <api_key> and X-Dristik-Connection-Email: <connection_email>.",
    }


@router.get("/connect/ai-connections")
async def list_ai_connections(user: UserIdentity = Depends(require_permission("org:manage"))):
    with _db() as conn:
        rows = conn.execute(
            "SELECT id,org_id,created_by,connection_email,grant_profile,scopes_json,status,expires_at,created_at,updated_at,last_used_at FROM uc_ai_connections WHERE org_id=? ORDER BY created_at DESC",
            (user.org_id,),
        ).fetchall()
    return {"connections": [_public_ai_connection(row) for row in rows]}


@router.post("/connect/ai-connections/validate")
async def validate_ai_connection(body: AIConnectionValidate):
    """Validate credentials without returning secrets or granting additional permissions."""
    key_hash = hashlib.sha256(body.api_key.encode("utf-8")).hexdigest()
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM uc_ai_connections WHERE connection_email=? AND key_hash=?",
            (body.connection_email.strip().lower(), key_hash),
        ).fetchone()
        if row is None or row["status"] != "active" or (row["expires_at"] is not None and row["expires_at"] <= time.time()):
            raise HTTPException(status_code=401, detail="Invalid, expired, or revoked Dristik connection credentials.")
        conn.execute("UPDATE uc_ai_connections SET last_used_at=?,updated_at=? WHERE id=?",
                     (time.time(), time.time(), row["id"]))
    return {"valid": True, "connection": _public_ai_connection(row), "tenant_data_exposed": False}


@router.post("/connect/ai-connections/{connection_id}/rotate")
async def rotate_ai_connection(connection_id: str, user: UserIdentity = Depends(require_permission("org:manage"))):
    now = time.time()
    new_key = "drk_live_" + secrets.token_urlsafe(36)
    new_hash = hashlib.sha256(new_key.encode("utf-8")).hexdigest()
    with _db() as conn:
        row = conn.execute("SELECT * FROM uc_ai_connections WHERE id=? AND org_id=?", (connection_id, user.org_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Connection not found.")
        if row["status"] != "active":
            raise HTTPException(status_code=409, detail="Only active connections can be rotated.")
        conn.execute("UPDATE uc_ai_connections SET key_hash=?,updated_at=? WHERE id=?", (new_hash, now, connection_id))
    return {"id": connection_id, "connection_email": row["connection_email"], "api_key": new_key,
            "status": "active", "key_display_policy": "shown_once"}


@router.post("/connect/ai-connections/{connection_id}/revoke")
async def revoke_ai_connection(connection_id: str, user: UserIdentity = Depends(require_permission("org:manage"))):
    with _db() as conn:
        row = conn.execute("SELECT id,status FROM uc_ai_connections WHERE id=? AND org_id=?", (connection_id, user.org_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Connection not found.")
        conn.execute("UPDATE uc_ai_connections SET status='revoked',updated_at=? WHERE id=?", (time.time(), connection_id))
    return {"id": connection_id, "status": "revoked"}


@router.post("/mcp")
async def mcp_json_rpc(request: Request, background_tasks: BackgroundTasks, user: UserIdentity = Depends(get_mcp_user)):
    """Authenticated stateless MCP-compatible JSON-RPC endpoint (initialize/tools/list/tools/call)."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be JSON.")
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0" or "method" not in body:
        raise HTTPException(status_code=400, detail="Invalid JSON-RPC 2.0 request.")
    method, request_id = body["method"], body.get("id")
    if method == "initialize":
        result = {"protocolVersion": MCP_VERSION, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "dristik-connect", "version": "1.0.0"}}
    elif method == "notifications/initialized":
        return Response(status_code=202)
    elif method == "tools/list":
        result = {"tools": [
            {"name": "dristik_list_capabilities", "description": "Discover Dristik Connect capabilities available to this identity.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "dristik_create_task", "description": "Create a durable collaboration task record.",
             "inputSchema": {"type": "object", "required": ["goal"], "properties": {"goal": {"type": "string"}, "inputs": {"type": "object"}}}},
            {"name": "dristik_get_task", "description": "Read a tenant-owned task and its messages/artifacts.",
             "inputSchema": {"type": "object", "required": ["task_id"], "properties": {"task_id": {"type": "string"}}}},
            {"name": "dristik_templates_list", "description": "List audit entry points currently exposed by Dristik.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "dristik_agents_list", "description": "List the actual registered specialist agents.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "dristik_audit_start", "description": "Start a canonical Dristik website audit with the normal entitlement and validation gates.",
             "inputSchema": {"type": "object", "required": ["website_url"], "properties": {"website_url": {"type": "string"}, "max_crawl_pages": {"type": "integer", "minimum": 1, "maximum": 100}, "target_pillars": {"type": "array", "items": {"type": "string"}}}}},
            {"name": "dristik_audit_status", "description": "Read the status of a tenant-owned canonical audit.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}}}},
            {"name": "dristik_report_get", "description": "Retrieve the persisted report for a completed tenant-owned audit.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}}}}
        ]}
    elif method == "tools/call":
        params = body.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        if name == "dristik_list_capabilities":
            result = await list_capabilities(user)
        elif name == "dristik_create_task":
            if not Authorizer.can_perform(user, "mission:create"):
                raise HTTPException(status_code=403, detail="You do not have permission to create collaboration tasks.")
            if not args.get("goal"):
                raise HTTPException(status_code=400, detail="goal is required.")
            task = await create_task(TaskCreate(goal=args["goal"], inputs=args.get("inputs") or {}), user)
            result = {"content": [{"type": "text", "text": _json(task)}], "structuredContent": task}
        elif name == "dristik_get_task":
            if not args.get("task_id"):
                raise HTTPException(status_code=400, detail="task_id is required.")
            if not _mcp_authorized(user, "tasks.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit reading tasks.")
            task = await get_task(args["task_id"], user)
            result = {"content": [{"type": "text", "text": _json(task)}], "structuredContent": task}
        elif name == "dristik_templates_list":
            if not _mcp_authorized(user, "templates.list", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit template discovery.")
            templates = [{"id": "website-audit", "name": "Canonical Dristik website audit", "status": "available",
                          "execution": "canonical_analysis_pipeline", "supports_target_pillars": True,
                          "note": "Uses the existing audit route, plan entitlements and evidence gates; this is not a claim that every future report template is registered."}]
            result = {"content": [{"type": "text", "text": _json(templates)}], "structuredContent": {"templates": templates}}
        elif name == "dristik_agents_list":
            if not _mcp_authorized(user, "agents.list", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit agent discovery.")
            try:
                from app.orchestration.runtime.registry import SPECIALIST_AGENTS_V3
                agents = [{"agent_id": agent_id, "name": defn.agent_name, "domain": defn.domain,
                           "description": defn.description, "status": "registered"}
                          for agent_id, defn in SPECIALIST_AGENTS_V3.items()]
            except Exception:
                agents = []
            result = {"content": [{"type": "text", "text": _json({"agents": agents, "count": len(agents)})}],
                      "structuredContent": {"agents": agents, "count": len(agents)}}
        elif name == "dristik_audit_start":
            if not _mcp_authorized(user, "audit.create", "mission:create"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit starting audits.")
            website_url = args.get("website_url")
            if not isinstance(website_url, str) or not website_url.strip():
                raise HTTPException(status_code=400, detail="website_url is required.")
            from app.domain.models import AnalysisRequest
            from app.api.routes.audits.analyses import start_analysis
            request_model = AnalysisRequest(
                website_url=website_url,
                max_crawl_pages=args.get("max_crawl_pages", 1),
                target_pillars=args.get("target_pillars"),
            )
            run = await start_analysis(request_model, background_tasks, user)
            audit = {"analysis_id": run.analysis_id, "website_url": run.website_url,
                     "status": str(getattr(run.status, "value", run.status))}
            result = {"content": [{"type": "text", "text": _json(audit)}], "structuredContent": audit}
        elif name == "dristik_audit_status":
            if not _mcp_authorized(user, "audit.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit reading audits.")
            analysis_id = args.get("analysis_id")
            if not isinstance(analysis_id, str) or not analysis_id:
                raise HTTPException(status_code=400, detail="analysis_id is required.")
            from app.identity.access import require_analysis
            run = require_analysis(analysis_id, user)
            audit = {"analysis_id": run.analysis_id, "website_url": run.website_url,
                     "status": str(getattr(run.status, "value", run.status)),
                     "progress_percentage": getattr(run, "progress_percentage", None),
                     "created_at": str(getattr(run, "created_at", "")),
                     "completed_at": str(getattr(run, "completed_at", "")) if getattr(run, "completed_at", None) else None,
                     "report_available": bool(getattr(run, "report", None))}
            result = {"content": [{"type": "text", "text": _json(audit)}], "structuredContent": audit}
        elif name == "dristik_report_get":
            if not _mcp_authorized(user, "report.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit report access.")
            analysis_id = args.get("analysis_id")
            if not isinstance(analysis_id, str) or not analysis_id:
                raise HTTPException(status_code=400, detail="analysis_id is required.")
            from app.identity.access import require_analysis
            run = require_analysis(analysis_id, user)
            if not getattr(run, "report", None):
                raise HTTPException(status_code=409, detail="Report is not ready yet.")
            report = run.report.model_dump(mode="json") if hasattr(run.report, "model_dump") else run.report
            result = {"content": [{"type": "text", "text": _json(report)}], "structuredContent": report}
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Unknown tool."}}
        if not (isinstance(result, dict) and "content" in result):
            result = {"content": [{"type": "text", "text": _json(result)}], "structuredContent": result}
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not supported."}}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}
