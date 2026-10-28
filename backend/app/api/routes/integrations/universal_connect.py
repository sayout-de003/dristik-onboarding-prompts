"""Universal AI/software collaboration API.

Durable, tenant-scoped foundation for connections, capability discovery, task
exchange, artifact transfer, and authenticated MCP tool discovery. A registered
connection is not considered healthy until a real adapter tests it.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.identity.authorizer import UserIdentity
from app.identity.deps import get_current_user, require_permission

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
        {"name": "audit.website", "status": "not_wired", "description": "Start the canonical Dristik website-audit workflow",
         "reason": "This capability stays disabled until wired to the canonical audit orchestrator."}
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
    return StreamingResponse(path.open("rb"), media_type=row["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{row["filename"]}"', "X-Content-SHA256": row["sha256"]})


@router.post("/mcp")
async def mcp_json_rpc(request: Request, user: UserIdentity = Depends(get_current_user)):
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
            {"name": "dristik_list_capabilities", "description": "List available Dristik Connect capabilities.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "dristik_create_task", "description": "Create a durable task record; does not claim to execute an audit.",
             "inputSchema": {"type": "object", "required": ["goal"], "properties": {"goal": {"type": "string"}, "inputs": {"type": "object"}}}},
            {"name": "dristik_get_task", "description": "Read a task and its messages/artifacts.",
             "inputSchema": {"type": "object", "required": ["task_id"], "properties": {"task_id": {"type": "string"}}}}
        ]}
    elif method == "tools/call":
        params = body.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        if name == "dristik_list_capabilities":
            result = await list_capabilities(user)
        elif name == "dristik_create_task":
            if not args.get("goal"):
                raise HTTPException(status_code=400, detail="goal is required.")
            task = await create_task(TaskCreate(goal=args["goal"], inputs=args.get("inputs") or {}), user)
            result = {"content": [{"type": "text", "text": _json(task)}], "structuredContent": task}
        elif name == "dristik_get_task":
            if not args.get("task_id"):
                raise HTTPException(status_code=400, detail="task_id is required.")
            task = await get_task(args["task_id"], user)
            result = {"content": [{"type": "text", "text": _json(task)}], "structuredContent": task}
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Unknown tool."}}
        if not (isinstance(result, dict) and "content" in result):
            result = {"content": [{"type": "text", "text": _json(result)}], "structuredContent": result}
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not supported."}}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}
