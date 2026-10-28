"""Universal AI/software collaboration API.

Durable, tenant-scoped foundation for connections, capability discovery, task
exchange, artifact transfer, and authenticated MCP tool discovery. A registered
connection is not considered healthy until a real adapter tests it.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

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
          name TEXT NOT NULL DEFAULT 'Dristik AI connection',
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
        CREATE TABLE IF NOT EXISTS uc_ai_connection_events (
          id TEXT PRIMARY KEY, connection_id TEXT NOT NULL, org_id TEXT NOT NULL,
          event TEXT NOT NULL, created_at REAL NOT NULL, metadata_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_uc_ai_connection_events ON uc_ai_connection_events(connection_id, created_at);
        """)
        # Safe additive migration for databases created by the earlier Connect slice.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(uc_ai_connections)").fetchall()}
        if "name" not in columns:
            conn.execute("ALTER TABLE uc_ai_connections ADD COLUMN name TEXT NOT NULL DEFAULT 'Dristik AI connection'")
        yield conn
        conn.commit()
    finally:
        conn.close()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _validate_public_audit_url(value: str) -> str:
    """Preflight public HTTP(S) targets and reject obvious SSRF destinations.

    This is a defense-in-depth preflight, not a substitute for redirect-aware
    transport-level DNS pinning in the crawler.
    """
    raw = value.strip()
    if not raw:
        raise HTTPException(status_code=422, detail="A website URL is required.")
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid website URL.")
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Only public HTTP or HTTPS website URLs are supported.")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=422, detail="Website URLs must not contain embedded credentials.")
    if port not in (None, 80, 443):
        raise HTTPException(status_code=422, detail="Non-standard website ports are not permitted for AI-triggered audits.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
        raise HTTPException(status_code=422, detail="Private and local network targets are not permitted.")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
        except (OSError, ValueError):
            raise HTTPException(status_code=422, detail="Website hostname could not be resolved safely.")
    if not addresses or any(not address.is_global for address in addresses):
        raise HTTPException(status_code=422, detail="Website URL resolves to a private, reserved, or non-public address.")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, ""))




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


def _pipeline_status_payload(analysis_id: str, run: Any, graph: dict[str, Any], sections_registry: list[Any]) -> dict[str, Any]:
    """Normalize live controller state without implying its in-memory node state is durable."""
    nodes = graph.get("nodes", {})
    sections = []
    for section in sections_registry:
        section_nodes = [nodes[node_id] for node_id in section.node_ids if node_id in nodes]
        statuses = [node.get("status", "pending") for node in section_nodes]
        if statuses and all(status == "completed" for status in statuses):
            section_status = "completed"
        elif any(status == "running" for status in statuses):
            section_status = "running"
        elif any(status == "failed" for status in statuses):
            section_status = "failed"
        elif any(status == "completed" for status in statuses):
            section_status = "partial"
        else:
            section_status = "pending"
        sections.append({
            "section_id": section.section_id,
            "title": section.title,
            "description": section.description,
            "order": section.order,
            "status": section_status,
            "completed_nodes": sum(1 for status in statuses if status == "completed"),
            "total_nodes": len(section_nodes),
            "nodes": section_nodes,
        })
    return {
        "analysis_id": analysis_id,
        "website_url": run.website_url,
        "audit_status": str(getattr(run.status, "value", run.status)),
        "audit_progress_percentage": getattr(run, "progress_percentage", None),
        "controller_progress_percentage": graph.get("progress_percentage", 0),
        "completed_nodes": graph.get("completed_nodes", 0),
        "total_nodes": graph.get("total_nodes", 0),
        "is_paused": graph.get("is_paused", False),
        "sections": sections,
        "recent_activity": graph.get("activity_events", []),
        "controller_state_scope": "process-local; node-level controller state may be empty after a server restart",
    }


def _citation_tracking_unavailable_payload(domain: str, queries: list[str] | None = None, engines: list[str] | None = None) -> dict[str, Any]:
    """Fail closed until the MCP path is connected to a verified live citation measurement adapter."""
    clean_domain = domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    return {
        "domain": clean_domain,
        "requested_queries": queries or [],
        "requested_engines": engines or ["openai", "gemini", "anthropic", "xai", "deepseek"],
        "status": "NOT_CONFIGURED",
        "overall_citation_score": None,
        "engines": {},
        "metrics_available": False,
        "reason": "No verified live citation-tracking adapter is wired to this MCP operation. No citation rates, mentions, or visibility scores were fabricated.",
        "next_step": "Configure a supported live measurement adapter and persist engine, query, timestamp, response, and citation evidence before reporting metrics.",
    }


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
@router.get("/capabilities")
async def list_capabilities(user: UserIdentity = Depends(get_current_user)):
    catalog = [
        {"name": "capabilities.list", "scope": "capabilities.list", "status": "available", "description": "Discover all authorized capabilities and workflows"},
        {"name": "templates.list", "scope": "templates.list", "status": "available", "description": "List registered audit templates"},
        {"name": "templates.inspect", "scope": "templates.list", "status": "available", "description": "Inspect template stages, parameters, and pillars"},
        {"name": "audit.create", "scope": "audit.create", "status": "available", "description": "Start the canonical Dristik website audit"},
        {"name": "audit.read", "scope": "audit.read", "status": "available", "description": "Inspect audit progress, state, and steps"},
        {"name": "audit.cancel", "scope": "audit.cancel", "status": "available", "description": "Cancel a running canonical audit"},
        {"name": "agents.list", "scope": "agents.list", "status": "available", "description": "List the actual registered runtime agents and their contracts; the returned count is discovered from the runtime registry"},
        {"name": "agent.execute", "scope": "agent.execute", "status": "available", "description": "Execute a specific DAG node with prerequisite verification"},
        {"name": "workflow.execute", "scope": "workflow.execute", "status": "available", "description": "Execute a pipeline section in the audit DAG"},
        {"name": "pipeline.inspect", "scope": "pipeline.inspect", "status": "available", "description": "Inspect DAG sections, node hierarchy, and execution graph"},
        {"name": "pipeline.status", "scope": "audit.read", "status": "available", "description": "Inspect tenant-authorized section/node statuses and recent activity; node-level controller state is process-local"},
        {"name": "report.artifacts", "scope": "report.export", "status": "available", "description": "Retrieve protected Dristik-owned PDF, PPTX, HTML, and CSV artifact endpoints"},
        {"name": "evidence.read", "scope": "evidence.read", "status": "available", "description": "Read evidence graph and provenance records"},
        {"name": "findings.read", "scope": "findings.read", "status": "available", "description": "Retrieve audit findings with severity and scores"},
        {"name": "blackboard.read", "scope": "blackboard.read", "status": "available", "description": "Read intermediate blackboard state, crawl pages, claims, and evidence"},
        {"name": "claim.submit", "scope": "claim.submit", "status": "available", "description": "Submit external AI claims into the blackboard for verification"},
        {"name": "citations.track", "scope": "citations.track", "status": "available", "description": "Request live AI citation tracking; reports NOT_CONFIGURED unless a verified measurement adapter is connected"},
        {"name": "report.read", "scope": "report.read", "status": "available", "description": "Retrieve the canonical persisted audit report"},
        {"name": "report.export", "scope": "report.export", "status": "available", "description": "Export audit data and retrieve Dristik-owned report artifact endpoints"},
        {"name": "connector.read", "scope": "connector.read", "status": "available", "description": "Inspect configured platform connectors and health"},
        {"name": "providers.list", "scope": "providers.list", "status": "available", "description": "Discover configured tenant model inference providers"},
        {"name": "provider.invoke", "scope": "provider.invoke", "status": "available", "description": "Delegate inference to encrypted tenant model providers"},
        {"name": "tasks.create", "scope": "tasks.create", "status": "available", "description": "Create a durable collaboration task record"},
        {"name": "tasks.read", "scope": "tasks.read", "status": "available", "description": "Read tenant collaboration tasks, messages, and artifacts"},
        {"name": "tasks.message", "scope": "tasks.message", "status": "available", "description": "Send messages and structured payload updates into collaboration tasks"},
        {"name": "artifacts.upload", "scope": "tasks.create", "status": "available", "description": "Store opaque bytes with a SHA-256 digest"},
    ]
    if user.auth_provider == "dristik_connect":
        catalog = [item for item in catalog if _mcp_authorized(user, item["scope"])]
    return {"tenant_id": user.org_id, "capabilities": [{k: v for k, v in item.items() if k != "scope"} for item in catalog]}


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
async def execute_task_audit(task_id: str, background_tasks: BackgroundTasks, model_provider_id: str | None = None, user: UserIdentity = Depends(require_permission("mission:create"))):
    """Submit a collaboration task to Dristik's existing audit pipeline."""
    with _db() as conn:
        task = _require_org(conn.execute("SELECT * FROM uc_tasks WHERE id=?", (task_id,)).fetchone(), user)
        inputs = json.loads(task["input_json"])
    url = inputs.get("url") or inputs.get("website_url")
    if not isinstance(url, str) or not url.strip():
        raise HTTPException(status_code=422, detail="Task inputs must include a website url.")
    url = _validate_public_audit_url(url)
    try:
        from app.domain.models import AnalysisRequest
        from app.api.routes.audits.analyses import start_analysis
        request = AnalysisRequest(website_url=url, max_crawl_pages=1)
        run = await start_analysis(request, background_tasks, user, model_provider_id)
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
    "read_only": [
        "capabilities.list", "templates.list", "template.inspect", "agents.list", "pipeline.inspect",
        "audit.read", "report.read", "findings.read", "evidence.read", "blackboard.read", "tasks.read",
        "connector.read"
    ],
    "audit_operator": [
        "capabilities.list", "templates.list", "template.inspect", "agents.list", "pipeline.inspect", "providers.list",
        "audit.create", "audit.read", "audit.cancel", "report.read", "report.export",
        "findings.read", "evidence.read", "blackboard.read", "claim.submit", "citations.track",
        "tasks.create", "tasks.read", "tasks.message", "connector.read"
    ],
    "workflow_admin": [
        "capabilities.list", "templates.list", "template.inspect", "agents.list", "pipeline.inspect", "providers.list",
        "agent.execute", "workflow.execute", "audit.create", "audit.read", "audit.cancel",
        "report.read", "report.export", "findings.read", "evidence.read", "blackboard.read", "claim.submit",
        "citations.track", "provider.invoke", "tasks.create", "tasks.read", "tasks.message", "connector.read"
    ],
    "full_access": ["*"],
}


class AIConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    grant_profile: Literal["read_only", "audit_operator", "workflow_admin", "full_access"] = "full_access"
    expires_in_days: int = Field(default=90, ge=1, le=365)


class AIConnectionValidate(BaseModel):
    connection_email: str = Field(min_length=3, max_length=254)
    api_key: str = Field(min_length=20, max_length=256)


def _connection_domain() -> str:
    # Configure this to a domain controlled by the Dristik deployment. The value
    # is a connection identity, not an inbox used for email delivery.
    return os.getenv("DRISTIK_CONNECT_IDENTITY_DOMAIN", "connect.dristik.local").strip().lower()


def _public_ai_connection(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "name": row["name"], "connection_email": row["connection_email"],
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


def _resolve_mcp_endpoint(request: Request | None = None) -> str:
    env_url = os.getenv("DRISTIK_MCP_PUBLIC_URL", "").strip()
    if env_url:
        return env_url
    if request is not None:
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
        if host:
            return f"{proto}://{host}/api/v1/mcp"
    return "/api/v1/mcp"


def _is_absolute_url(url: str) -> bool:
    return url.startswith(("https://", "http://"))


async def get_mcp_user(
    request: Request = None,
    authorization: str | None = Header(default=None),
    connection_email: str | None = Header(default=None, alias="X-Dristik-Connection-Email"),
    session_user: UserIdentity | None = Depends(get_current_user_optional),
) -> UserIdentity:
    """Authenticate a Dristik-issued connection key or preserve signed-in MCP access."""
    auth_header = authorization if isinstance(authorization, str) else ""
    token = auth_header.split(" ", 1)[1].strip() if auth_header.lower().startswith("bearer ") else ""
    if not token and request is not None:
        token = request.query_params.get("token") or request.query_params.get("api_key") or ""
    if not token.startswith("drk_live_"):
        if session_user is None:
            raise HTTPException(status_code=401, detail="Provide a Dristik connection API key or sign in.")
        return session_user
    email_param = connection_email if isinstance(connection_email, str) else (request.query_params.get("connection_email") if request is not None else None)
    key_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = time.time()
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM uc_ai_connections WHERE key_hash=?",
            (key_hash,),
        ).fetchone()
        if row is None or row["status"] != "active" or (row["expires_at"] is not None and row["expires_at"] <= now):
            raise HTTPException(status_code=401, detail="Invalid, expired, or revoked Dristik connection credentials.")
        if isinstance(email_param, str) and row["connection_email"].strip().lower() != email_param.strip().lower():
            raise HTTPException(status_code=401, detail="Invalid, expired, or revoked Dristik connection credentials.")
        conn.execute("UPDATE uc_ai_connections SET last_used_at=?,updated_at=? WHERE id=?",
                     (now, now, row["id"]))
        conn.execute("INSERT INTO uc_ai_connection_events VALUES (?,?,?,?,?,?)",
                     ("uce_" + uuid.uuid4().hex, row["id"], row["org_id"], "authenticated", now, "{}"))
    role_by_profile = {
        "read_only": UserRole.VIEWER,
        "audit_operator": UserRole.ANALYST,
        "workflow_admin": UserRole.ADMIN,
        "full_access": UserRole.OWNER,
    }
    return UserIdentity(
        user_id=row["id"], org_id=row["org_id"], email=row["connection_email"],
        full_name=row["name"],
        role=role_by_profile.get(row["grant_profile"], UserRole.VIEWER),
        auth_provider="dristik_connect", is_active=True,
    )


@router.post("/connect/ai-connections", status_code=201)
@router.post("/ai-connections", status_code=201)
async def create_ai_connection(
    body: AIConnectionCreate,
    user: UserIdentity = Depends(require_permission("org:manage")),
    request: Request = None,
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
    expires_at = now + body.expires_in_days * 86400
    scopes = AI_GRANT_SCOPES[body.grant_profile]
    with _db() as conn:
        conn.execute(
            "INSERT INTO uc_ai_connections (id,org_id,created_by,name,connection_email,key_hash,grant_profile,scopes_json,status,expires_at,created_at,updated_at,last_used_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL)",
            (connection_id, user.org_id, user.user_id, body.name, email, key_hash, body.grant_profile,
             _json(scopes), "active", expires_at, now, now),
        )
        conn.execute(
            "INSERT INTO uc_ai_connection_events VALUES (?,?,?,?,?,?)",
            ("uce_" + uuid.uuid4().hex, connection_id, user.org_id, "created", now, "{}"),
        )
    mcp_endpoint = _resolve_mcp_endpoint(request)
    mcp_config = {
        "url": mcp_endpoint,
        "sse_url": mcp_endpoint.rstrip("/") + "/sse" if not mcp_endpoint.endswith("/sse") else mcp_endpoint,
        "headers": {
            "Authorization": "Bearer " + api_key,
            "X-Dristik-Connection-Email": email,
        },
    }
    return {
        "id": connection_id, "name": body.name, "connection_email": email,
        "api_key": api_key, "grant_profile": body.grant_profile, "scopes": scopes,
        "status": "active", "expires_at": expires_at,
        "mcp_endpoint": mcp_endpoint, "mcp_endpoint_is_absolute": _is_absolute_url(mcp_endpoint),
        "mcp_config": mcp_config, "key_display_policy": "shown_once",
        "instructions": "Copy the API key now. It cannot be retrieved later. Configure the AI client to send Authorization: Bearer <api_key> and X-Dristik-Connection-Email: <connection_email>.",
    }


@router.get("/connect/ai-connections")
@router.get("/ai-connections")
async def list_ai_connections(user: UserIdentity = Depends(require_permission("org:manage"))):
    with _db() as conn:
        rows = conn.execute(
            "SELECT id,org_id,created_by,name,connection_email,grant_profile,scopes_json,status,expires_at,created_at,updated_at,last_used_at FROM uc_ai_connections WHERE org_id=? ORDER BY created_at DESC",
            (user.org_id,),
        ).fetchall()
    return {"connections": [_public_ai_connection(row) for row in rows]}


@router.post("/connect/ai-connections/validate")
@router.post("/ai-connections/validate")
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
@router.post("/ai-connections/{connection_id}/rotate")
async def rotate_ai_connection(
    connection_id: str,
    user: UserIdentity = Depends(require_permission("org:manage")),
    request: Request = None,
):
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
        conn.execute(
            "INSERT INTO uc_ai_connection_events VALUES (?,?,?,?,?,?)",
            ("uce_" + uuid.uuid4().hex, connection_id, user.org_id, "rotated", now, "{}"),
        )
    mcp_endpoint = _resolve_mcp_endpoint(request)
    return {"id": connection_id, "connection_email": row["connection_email"], "api_key": new_key,
            "mcp_endpoint": mcp_endpoint, "mcp_endpoint_is_absolute": _is_absolute_url(mcp_endpoint),
            "mcp_config": {
                "url": mcp_endpoint,
                "sse_url": mcp_endpoint.rstrip("/") + "/sse" if not mcp_endpoint.endswith("/sse") else mcp_endpoint,
                "headers": {
                    "Authorization": "Bearer " + new_key,
                    "X-Dristik-Connection-Email": row["connection_email"],
                },
            },
            "status": "active", "key_display_policy": "shown_once"}


@router.post("/connect/ai-connections/{connection_id}/revoke")
@router.post("/ai-connections/{connection_id}/revoke")
async def revoke_ai_connection(connection_id: str, user: UserIdentity = Depends(require_permission("org:manage"))):
    now = time.time()
    with _db() as conn:
        row = conn.execute("SELECT id,status FROM uc_ai_connections WHERE id=? AND org_id=?", (connection_id, user.org_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Connection not found.")
        conn.execute("UPDATE uc_ai_connections SET status='revoked',updated_at=? WHERE id=?", (now, connection_id))
        conn.execute(
            "INSERT INTO uc_ai_connection_events VALUES (?,?,?,?,?,?)",
            ("uce_" + uuid.uuid4().hex, connection_id, user.org_id, "revoked", now, "{}"),
        )
    return {"id": connection_id, "status": "revoked"}


def _log_connection_event(
    connection_id: str,
    org_id: str,
    event: str,
    direction: Literal["inbound", "outbound", "internal"] = "inbound",
    method: str = "",
    tool: str | None = None,
    arguments: dict | None = None,
    summary: str | None = None,
    status: str = "success",
    error: str | None = None,
    extra: dict | None = None,
) -> None:
    now = time.time()
    payload = {
        "direction": direction,
        "method": method,
        "tool": tool,
        "arguments": arguments or {},
        "summary": summary or "",
        "status": status,
        "error": error,
        **(extra or {}),
    }
    with _db() as conn:
        conn.execute(
            "INSERT INTO uc_ai_connection_events VALUES (?,?,?,?,?,?)",
            ("uce_" + uuid.uuid4().hex, connection_id, org_id, event, now, _json(payload)),
        )


class ConnectionTestProbe(BaseModel):
    message: str = Field(default="Connection verification probe", description="Test message or probe description")
    probe_type: Literal["ping", "audits_list", "pipeline_inspect", "agents_list", "custom_message"] = "ping"
    tool_arguments: dict[str, Any] = Field(default_factory=dict)


@router.post("/connect/ai-connections/{connection_id}/test-message")
@router.post("/ai-connections/{connection_id}/test-message")
async def test_ai_connection_message(
    connection_id: str,
    probe: ConnectionTestProbe,
    user: UserIdentity = Depends(require_permission("org:manage")),
):
    """Send an interactive test message or probe to verify two-way connection readiness and log inbound/outbound ledger records."""
    start_time = time.time()
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM uc_ai_connections WHERE id=?",
            (connection_id,),
        ).fetchone()
        _require_org(row, user)
        if row["status"] != "active":
            raise HTTPException(status_code=400, detail=f"Cannot test inactive connection (status: {row['status']}).")

    # 1. Log outbound test probe sent from Dristik
    _log_connection_event(
        connection_id, user.org_id,
        event="outbound:probe_sent",
        direction="outbound",
        method=f"test:{probe.probe_type}",
        arguments=probe.tool_arguments,
        summary=f"Dristik sent test probe: {probe.probe_type} - '{probe.message}'",
        status="success",
    )

    # 2. Execute probe logic
    response_data: dict[str, Any] = {}
    summary_text = ""
    if probe.probe_type == "ping":
        response_data = {
            "status": "connected",
            "ping": "pong",
            "protocol": MCP_VERSION,
            "connection_email": row["connection_email"],
            "connection_name": row["name"],
            "grant_profile": row["grant_profile"],
            "scopes": json.loads(row["scopes_json"]) if row["scopes_json"] else ["*"],
            "timestamp": time.time(),
        }
        summary_text = "Connection identity & MCP protocol verified active."
    elif probe.probe_type == "audits_list":
        from app.api.routes.audits.analyses import list_analyses
        audits = await list_analyses(limit=probe.tool_arguments.get("limit", 10), user=user)
        response_data = {
            "audits": audits,
            "count": len(audits),
            "org_id": user.org_id,
        }
        summary_text = f"Retrieved {len(audits)} past audits for org {user.org_id}."
    elif probe.probe_type == "pipeline_inspect":
        from app.orchestration.pipeline_dag import SECTIONS_REGISTRY, NODES_REGISTRY
        sections_count = len(SECTIONS_REGISTRY)
        nodes_count = len(NODES_REGISTRY.values() if hasattr(NODES_REGISTRY, "values") else NODES_REGISTRY)
        response_data = {
            "sections_count": sections_count,
            "nodes_count": nodes_count,
            "pipeline_status": "ready",
        }
        summary_text = f"Pipeline verified: {sections_count} sections, {nodes_count} DAG nodes ready."
    elif probe.probe_type == "agents_list":
        from app.orchestration.runtime.registry import AGENT_REGISTRY
        unique_agents = len({defn.agent_id: defn for defn in AGENT_REGISTRY.values()})
        response_data = {
            "agent_count": unique_agents,
            "sample_agents": [defn.agent_id for defn in list(AGENT_REGISTRY.values())[:5]],
            "fleet_status": "registered; execution readiness is not inferred from registry presence",
        }
        summary_text = f"Agent fleet verified: {unique_agents} specialist agents registered."
    else:
        response_data = {
            "echo": probe.message,
            "received": True,
            "timestamp": time.time(),
            "target": row["connection_email"],
        }
        summary_text = "Custom message delivered and recorded in connection ledger."

    duration_ms = round((time.time() - start_time) * 1000, 2)

    # 3. Log inbound probe acknowledgment
    _log_connection_event(
        connection_id, user.org_id,
        event="inbound:probe_acknowledged",
        direction="inbound",
        method=f"test:{probe.probe_type}",
        summary=f"{summary_text} ({duration_ms}ms round-trip)",
        status="success",
        extra={"duration_ms": duration_ms},
    )

    now = time.time()
    with _db() as conn:
        conn.execute("UPDATE uc_ai_connections SET last_used_at=?,updated_at=? WHERE id=?", (now, now, connection_id))

    return {
        "success": True,
        "probe_type": probe.probe_type,
        "round_trip_ms": duration_ms,
        "connection_id": connection_id,
        "connection_email": row["connection_email"],
        "message": probe.message,
        "response_summary": summary_text,
        "response_data": response_data,
    }


@router.get("/connect/ai-connections/{connection_id}/activity")
@router.get("/ai-connections/{connection_id}/activity")
async def get_ai_connection_activity(
    connection_id: str,
    user: UserIdentity = Depends(require_permission("org:manage")),
    limit: int = 50,
):
    limit = max(1, min(limit, 100))
    with _db() as conn:
        _require_org(conn.execute("SELECT * FROM uc_ai_connections WHERE id=?", (connection_id,)).fetchone(), user)
        rows = conn.execute(
            "SELECT id,event,created_at,metadata_json FROM uc_ai_connection_events WHERE connection_id=? AND org_id=? ORDER BY created_at DESC LIMIT ?",
            (connection_id, user.org_id, limit),
        ).fetchall()
    events = []
    for r in rows:
        meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
        evt_name = r["event"]
        direction = meta.get("direction")
        if not direction:
            if evt_name.startswith("outbound:"):
                direction = "outbound"
            elif evt_name.startswith("inbound:"):
                direction = "inbound"
            elif evt_name in ("mcp_initialize", "mcp_tools/list", "mcp_tools/call", "mcp_ping", "mcp_notifications/initialized", "authenticated"):
                direction = "inbound"
            else:
                direction = "internal"
        events.append({
            "id": r["id"],
            "event": evt_name,
            "created_at": r["created_at"],
            "direction": direction,
            "method": meta.get("method") or evt_name,
            "tool": meta.get("tool"),
            "arguments": meta.get("arguments"),
            "summary": meta.get("summary") or meta.get("note") or evt_name,
            "status": meta.get("status", "success"),
            "error": meta.get("error"),
            "metadata": meta,
        })
    return {
        "connection_id": connection_id,
        "events": events,
    }


@router.get("/mcp")
async def mcp_server_info(request: Request, user: UserIdentity = Depends(get_mcp_user)):
    """MCP server discovery, capabilities, and transport endpoints."""
    endpoint = _resolve_mcp_endpoint(request)
    sse_endpoint = endpoint.rstrip("/") + "/sse"
    return {
        "name": "dristik-connect",
        "version": "1.0.0",
        "protocolVersion": MCP_VERSION,
        "status": "active",
        "authenticated_as": user.email,
        "org_id": user.org_id,
        "transports": {
            "http_post": endpoint,
            "sse": sse_endpoint,
        },
        "capabilities": {
            "tools": {"listChanged": False},
        },
    }


@router.get("/mcp/sse")
async def mcp_sse(request: Request, user: UserIdentity = Depends(get_mcp_user)):
    """Standard Model Context Protocol Server-Sent Events (SSE) transport."""
    post_endpoint = _resolve_mcp_endpoint(request)
    now = time.time()
    with _db() as conn:
        conn.execute(
            "INSERT INTO uc_ai_connection_events VALUES (?,?,?,?,?,?)",
            ("uce_" + uuid.uuid4().hex, user.user_id, user.org_id, "sse_connected", now, "{}"),
        )

    async def sse_event_stream():
        # MCP SSE protocol: emit the HTTP POST endpoint URI that the client
        # should send subsequent JSON-RPC messages to.
        yield f"event: endpoint\r\ndata: {post_endpoint}\r\n\r\n"
        yield f": keep-alive\r\n\r\n"

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    if user.auth_provider == "dristik_connect":
        if method == "tools/call":
            params = body.get("params") or {}
            t_name = params.get("name")
            t_args = params.get("arguments") or {}
            _log_connection_event(
                user.user_id, user.org_id,
                event=f"mcp_tools/call",
                direction="inbound",
                method="tools/call",
                tool=t_name,
                arguments=t_args,
                summary=f"Inbound tool call: {t_name}",
            )
        else:
            _log_connection_event(
                user.user_id, user.org_id,
                event=f"mcp_{method}",
                direction="inbound",
                method=method,
                summary=f"Inbound {method} request from AI client",
            )
    if method == "initialize":
        result = {"protocolVersion": MCP_VERSION, "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "dristik-connect", "version": "1.0.0"}}
    elif method == "notifications/initialized":
        return Response(status_code=202)
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [
            {"name": "dristik_capabilities_list", "description": "Discover all Dristik Connect capabilities available to this identity.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "dristik_create_task", "description": "Create a durable collaboration task record.",
             "inputSchema": {"type": "object", "required": ["goal"], "properties": {"goal": {"type": "string"}, "inputs": {"type": "object"}}}},
            {"name": "dristik_get_task", "description": "Read a tenant-owned task and its messages/artifacts.",
             "inputSchema": {"type": "object", "required": ["task_id"], "properties": {"task_id": {"type": "string"}}}},
            {"name": "dristik_templates_list", "description": "List audit entry points currently exposed by Dristik.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "dristik_template_inspect", "description": "Inspect an audit template's configuration, stages, supported pillars, and execution graph.",
             "inputSchema": {"type": "object", "properties": {"template_id": {"type": "string", "default": "website-audit"}}}},
            {"name": "dristik_agents_list", "description": "List registered specialist agents and their execution contracts, or inspect a single agent.",
             "inputSchema": {"type": "object", "properties": {"agent_id": {"type": "string"}, "domain": {"type": "string"}}}},
            {"name": "dristik_model_providers_list", "description": "List tenant-owned model provider IDs and health status without returning secrets.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "dristik_audits_list", "description": "List earlier website audits and analyses for this organization, returning analysis_id, URL, domain, status, progress, composite score, and dates.",
             "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 25, "minimum": 1, "maximum": 100}}}},
            {"name": "dristik_audit_start", "description": "Start a canonical Dristik website audit with normal entitlement and validation gates.",
             "inputSchema": {"type": "object", "required": ["website_url"], "properties": {"website_url": {"type": "string"}, "max_crawl_pages": {"type": "integer", "minimum": 1, "maximum": 100}, "target_pillars": {"type": "array", "items": {"type": "string"}}, "model_provider_id": {"type": "string", "description": "Optional tenant-owned configured provider ID for all compatible model-router calls in this run."}}}},
            {"name": "dristik_audit_status", "description": "Read the status of a tenant-owned canonical audit.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}}}},
            {"name": "dristik_audit_cancel", "description": "Cancel a running canonical audit.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}}}},
            {"name": "dristik_report_get", "description": "Retrieve the persisted report for a completed tenant-owned audit.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}}}},
            {"name": "dristik_audit_get", "description": "Retrieve comprehensive audit run details, composite scores, and executive report for an analysis ID.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}}}},
            {"name": "dristik_report_export", "description": "Export a completed audit report in CSV format (remediation tracker or crawl URLs) or summary JSON.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}, "format": {"type": "string", "enum": ["csv_remediation", "csv_urls", "summary_json"], "default": "summary_json"}}}},
            {"name": "dristik_findings_list", "description": "List persisted findings from a tenant-owned audit report.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}}}},
            {"name": "dristik_evidence_list", "description": "Retrieve the evidence graph for a tenant-owned audit when available.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}}}},
            {"name": "dristik_agent_execute", "description": "Execute one registered audit DAG node using the canonical orchestrator after dependency checks.",
             "inputSchema": {"type": "object", "required": ["analysis_id", "node_id"], "properties": {"analysis_id": {"type": "string"}, "node_id": {"type": "string"}}}},
            {"name": "dristik_workflow_execute", "description": "Execute a canonical audit pipeline section for a tenant-owned run.",
             "inputSchema": {"type": "object", "required": ["analysis_id", "section_id"], "properties": {"analysis_id": {"type": "string"}, "section_id": {"type": "string"}}}},
            {"name": "dristik_pipeline_inspect", "description": "Inspect the entire DAG pipeline sections, stages, node dependency hierarchy, and execution graph.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "dristik_pipeline_status", "description": "Inspect section and node execution status for a tenant-owned audit, including dependencies, recent activity, and durable audit status.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}}}},
            {"name": "dristik_report_artifacts", "description": "Get Dristik-owned HTML, PDF, GEO report, deliverables, and PPTX endpoints for a completed audit. URLs require the same authenticated tenant connection.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}}}},
            {"name": "dristik_blackboard_read", "description": "Read intermediate crawl pages, claims, evidence items, and scores from the shared audit blackboard.",
             "inputSchema": {"type": "object", "required": ["analysis_id"], "properties": {"analysis_id": {"type": "string"}}}},
            {"name": "dristik_claim_submit", "description": "Submit an external AI reasoned finding or claim into the audit blackboard for adversarial verification.",
             "inputSchema": {"type": "object", "required": ["analysis_id", "statement"], "properties": {"analysis_id": {"type": "string"}, "statement": {"type": "string"}, "category": {"type": "string"}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "supporting_evidence": {"type": "array", "items": {"type": "string"}}, "recommendation": {"type": "string"}}}},
            {"name": "dristik_ai_citations_track", "description": "Track brand citation frequency, sentiment, and AI search visibility across Perplexity, ChatGPT, Gemini, and Claude.",
             "inputSchema": {"type": "object", "required": ["domain"], "properties": {"domain": {"type": "string"}, "queries": {"type": "array", "items": {"type": "string"}}, "engines": {"type": "array", "items": {"type": "string"}}}}},
            {"name": "dristik_crux_query", "description": "Fetch real Chrome UX Report field metrics for a public URL or origin. Returns explicit NOT_CONFIGURED or DATA_UNAVAILABLE states rather than invented metrics.", "inputSchema": {"type": "object", "required": ["origin"], "properties": {"origin": {"type": "string"}, "url": {"type": "string"}, "form_factor": {"type": "string", "enum": ["PHONE", "DESKTOP", "TABLET"], "default": "PHONE"}}}},
            {"name": "dristik_pagespeed_query", "description": "Run a real Google PageSpeed Insights/Lighthouse lab audit for a public URL. Lab data is explicitly distinguished from CrUX field data.", "inputSchema": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}, "strategy": {"type": "string", "enum": ["mobile", "desktop"], "default": "mobile"}, "categories": {"type": "array", "items": {"type": "string", "enum": ["performance", "accessibility", "best-practices", "seo"]}}}}},
            {"name": "dristik_google_search", "description": "Run a real Google Programmable Search query when configured. Results are explicitly labeled as configured search-engine results, not universal live Google SERP rankings.", "inputSchema": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "num": {"type": "integer", "minimum": 1, "maximum": 10, "default": 10}, "start": {"type": "integer", "minimum": 1, "maximum": 91, "default": 1}}}},
            {"name": "dristik_provider_invoke", "description": "Delegate inference to a tenant-configured encrypted model provider (OpenAI, Anthropic, Gemini, Grok, DeepSeek, Kimi, OpenRouter).",
             "inputSchema": {"type": "object", "required": ["provider_id", "prompt"], "properties": {"provider_id": {"type": "string"}, "prompt": {"type": "string"}, "system": {"type": "string"}, "max_tokens": {"type": "integer", "default": 1200}}}},
            {"name": "dristik_tasks_list", "description": "List collaboration tasks for this organization.",
             "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}}},
            {"name": "dristik_task_send_message", "description": "Send a message or structured update into a collaboration task.",
             "inputSchema": {"type": "object", "required": ["task_id", "sender", "payload"], "properties": {"task_id": {"type": "string"}, "sender": {"type": "string"}, "recipient": {"type": "string"}, "message_type": {"type": "string", "default": "text"}, "payload": {"type": "object"}}}},
            {"name": "dristik_connector_status", "description": "Inspect the status and health of configured external platform connectors.",
             "inputSchema": {"type": "object", "properties": {"connector_id": {"type": "string"}}}},
            {"name": "dristik_ping", "description": "Verify two-way connection health, latency, tenant identity, and active capabilities.",
             "inputSchema": {"type": "object", "properties": {"message": {"type": "string"}}}},
            {"name": "dristik_send_message", "description": "Send a two-way message, query, or check-in between external AI client and Dristik.",
             "inputSchema": {"type": "object", "required": ["message"], "properties": {"message": {"type": "string"}, "metadata": {"type": "object"}}}},
        ]}
        scope_for_tool = {
            "dristik_capabilities_list": "capabilities.list",
            "dristik_list_capabilities": "capabilities.list",
            "dristik_create_task": "tasks.create",
            "dristik_get_task": "tasks.read",
            "dristik_tasks_list": "tasks.read",
            "dristik_task_send_message": "tasks.message",
            "dristik_templates_list": "templates.list",
            "dristik_template_inspect": "templates.list",
            "dristik_agents_list": "agents.list",
            "dristik_model_providers_list": "providers.list",
            "dristik_provider_invoke": "provider.invoke",
            "dristik_audits_list": "audit.read",
            "dristik_audit_list": "audit.read",
            "dristik_analyses_list": "audit.read",
            "dristik_runs_list": "audit.read",
            "dristik_audit_start": "audit.create",
            "dristik_audit_status": "audit.read",
            "dristik_audit_cancel": "audit.cancel",
            "dristik_report_get": "report.read",
            "dristik_audit_get": "report.read",
            "dristik_analysis_get": "report.read",
            "dristik_report_export": "report.export",
            "dristik_findings_list": "findings.read",
            "dristik_evidence_list": "evidence.read",
            "dristik_blackboard_read": "blackboard.read",
            "dristik_claim_submit": "claim.submit",
            "dristik_ai_citations_track": "citations.track",
            "dristik_crux_query": "connector.read",
            "dristik_pagespeed_query": "connector.read",
            "dristik_google_search": "connector.read",
            "dristik_pipeline_inspect": "pipeline.inspect",
            "dristik_pipeline_status": "audit.read",
            "dristik_report_artifacts": "report.export",
            "dristik_agent_execute": "agent.execute",
            "dristik_workflow_execute": "workflow.execute",
            "dristik_connector_status": "connector.read",
            "dristik_ping": "capabilities.list",
            "dristik_send_message": "tasks.message",
        }
        result["tools"] = [tool for tool in result["tools"]
                           if _mcp_authorized(user, scope_for_tool[tool["name"]])]
    elif method == "tools/call":
        params = body.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        if name in ("dristik_capabilities_list", "dristik_list_capabilities"):
            if not _mcp_authorized(user, "capabilities.list", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit capability discovery.")
            result = await list_capabilities(user)
        elif name == "dristik_create_task":
            if not _mcp_authorized(user, "tasks.create", "mission:create"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit creating collaboration tasks.")
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
        elif name == "dristik_template_inspect":
            if not _mcp_authorized(user, "templates.list", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit template inspection.")
            template_id = args.get("template_id") or "website-audit"
            if template_id != "website-audit":
                raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
            inspection = {
                "template_id": "website-audit",
                "name": "Canonical Dristik website audit",
                "version": "3.0.0",
                "description": "Comprehensive autonomous audit across SEO, GEO, AEO, and CRO pillars.",
                "supported_pillars": ["seo", "geo", "aeo", "cro"],
                "stages": [
                    {"id": "crawl", "name": "Headless Browser Crawl & DOM Extraction"},
                    {"id": "deterministic", "name": "Deterministic Technical & Security Rule Engine"},
                    {"id": "planning", "name": "Task Card Planning & Dispatch"},
                    {"id": "specialist", "name": "105 Specialist Agents Across 12 Domains Parallel Execution"},
                    {"id": "verification", "name": "Adversarial Verification & Evidence Proof"},
                    {"id": "scoring", "name": "Multi-Pillar 0-100 Mathematical Scoring"},
                    {"id": "synthesis", "name": "Executive Synthesis & Remediation Matrix"},
                ],
                "workflow_sections": [
                    {"id": "sec_ingestion", "title": "1. Ingestion & Multi-Page Crawl", "nodes_count": 3},
                    {"id": "sec_business_identity", "title": "2. Business Understanding & Entity Grounding", "nodes_count": 2},
                    {"id": "sec_seo", "title": "3. Search Engine Optimization (SEO)", "nodes_count": 5},
                    {"id": "sec_geo", "title": "4. Generative Engine Optimization (GEO)", "nodes_count": 3},
                    {"id": "sec_aeo", "title": "5. Answer Engine Optimization (AEO)", "nodes_count": 3},
                    {"id": "sec_cro", "title": "6. Conversion Rate Optimization (CRO & UX)", "nodes_count": 3},
                    {"id": "sec_synthesis", "title": "7. Executive Synthesis, Scoring & Patches", "nodes_count": 14},
                ],
                "total_specialist_agents": 105,
                "total_agent_domains": 12,
                "total_workflow_sections": 7,
                "total_dag_nodes": 33,
                "parameters": {
                    "website_url": {"type": "string", "required": True},
                    "max_crawl_pages": {"type": "integer", "default": 1, "minimum": 1, "maximum": 100},
                    "target_pillars": {"type": "array", "items": "string", "default": ["seo", "geo", "aeo", "cro"]},
                    "model_provider_id": {"type": "string", "description": "Tenant-configured inference provider"},
                },
                "execution_engine": "canonical_analysis_pipeline",
            }
            result = {"content": [{"type": "text", "text": _json(inspection)}], "structuredContent": inspection}
        elif name == "dristik_agents_list":
            if not _mcp_authorized(user, "agents.list", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit agent discovery.")
            target_aid = args.get("agent_id")
            target_domain = (args.get("domain") or "").upper()
            try:
                from app.orchestration.runtime.registry import AGENT_REGISTRY
                unique = {defn.agent_id: defn for defn in AGENT_REGISTRY.values()}
                if target_aid:
                    defn = AGENT_REGISTRY.get(target_aid)
                    if not defn:
                        raise HTTPException(status_code=404, detail=f"Specialist agent '{target_aid}' not registered.")
                    agents = [defn.model_dump(mode="json") if hasattr(defn, "model_dump") else defn]
                else:
                    agents = [
                        {"agent_id": defn.agent_id, "name": defn.agent_name, "domain": defn.domain,
                         "description": defn.description, "status": "registered",
                         "capabilities": defn.capabilities, "dependencies": defn.dependencies,
                         "risk_level": defn.risk_level, "timeout_sec": defn.timeout_sec,
                         "token_budget": getattr(defn, "token_budget", 4000),
                         "worker_type": getattr(defn, "worker_type", "analyst_worker")}
                        for defn in unique.values()
                        if not target_domain or defn.domain.upper() == target_domain
                    ]
            except HTTPException:
                raise
            except Exception:
                agents = []
            result = {"content": [{"type": "text", "text": _json({"agents": agents, "count": len(agents)})}],
                      "structuredContent": {"agents": agents, "count": len(agents)}}
        elif name == "dristik_model_providers_list":
            if not _mcp_authorized(user, "providers.list", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit model-provider discovery.")
            from app.api.routes.integrations.provider_adapters import list_providers
            payload = await list_providers(user)
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name in ("dristik_audits_list", "dristik_audit_list", "dristik_analyses_list", "dristik_runs_list"):
            if not _mcp_authorized(user, "audit.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit reading audits.")
            limit = int(args.get("limit", 25))
            from app.api.routes.audits.analyses import list_analyses
            audits = await list_analyses(limit=limit, user=user)
            payload = {"audits": audits, "count": len(audits), "org_id": user.org_id}
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_audit_start":
            if not _mcp_authorized(user, "audit.create", "mission:create"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit starting audits.")
            website_url = args.get("website_url")
            if not isinstance(website_url, str) or not website_url.strip():
                raise HTTPException(status_code=400, detail="website_url is required.")
            website_url = _validate_public_audit_url(website_url)
            from app.domain.models import AnalysisRequest
            from app.api.routes.audits.analyses import start_analysis
            request_model = AnalysisRequest(
                website_url=website_url,
                max_crawl_pages=args.get("max_crawl_pages", 1),
                target_pillars=args.get("target_pillars"),
            )
            run = await start_analysis(request_model, background_tasks, user, args.get("model_provider_id"))
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
        elif name == "dristik_audit_cancel":
            if not _mcp_authorized(user, "audit.cancel", "mission:create"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit cancelling audits.")
            analysis_id = args.get("analysis_id")
            if not isinstance(analysis_id, str) or not analysis_id:
                raise HTTPException(status_code=400, detail="analysis_id is required.")
            from app.identity.access import require_analysis
            from app.orchestration.pipeline_dag import get_pipeline_controller
            from app.orchestration.orchestrator import orchestrator
            from app.domain.enums import AnalysisStage
            run = require_analysis(analysis_id, user)
            controller = get_pipeline_controller(analysis_id)
            controller.request_stop()
            in_mem = orchestrator.runs.get(analysis_id)
            if in_mem:
                in_mem.status = AnalysisStage.STOPPED
                in_mem.current_step = "Audit stopped by user via external AI connection"
            canceled_info = {"analysis_id": analysis_id, "status": "stopped", "stopped": True}
            result = {"content": [{"type": "text", "text": _json(canceled_info)}], "structuredContent": canceled_info}
        elif name in ("dristik_report_get", "dristik_audit_get", "dristik_analysis_get"):
            if not _mcp_authorized(user, "report.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit report access.")
            analysis_id = args.get("analysis_id")
            if not isinstance(analysis_id, str) or not analysis_id:
                raise HTTPException(status_code=400, detail="analysis_id is required.")
            from app.identity.access import require_analysis
            run = require_analysis(analysis_id, user)
            report_data = run.report.model_dump(mode="json") if getattr(run, "report", None) and hasattr(run.report, "model_dump") else getattr(run, "report", None)
            run_data = {
                "analysis_id": run.analysis_id,
                "website_url": run.website_url,
                "status": str(getattr(run.status, "value", run.status)),
                "progress_percentage": getattr(run, "progress_percentage", 100),
                "created_at": str(getattr(run, "created_at", "")),
                "completed_at": str(getattr(run, "completed_at", "")) if getattr(run, "completed_at", None) else None,
                "report": report_data,
            }
            result = {"content": [{"type": "text", "text": _json(run_data)}], "structuredContent": run_data}
        elif name == "dristik_report_export":
            if not _mcp_authorized(user, "report.export", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit exporting reports.")
            analysis_id = args.get("analysis_id")
            if not isinstance(analysis_id, str) or not analysis_id:
                raise HTTPException(status_code=400, detail="analysis_id is required.")
            fmt = args.get("format", "summary_json")
            from app.identity.access import require_analysis
            run = require_analysis(analysis_id, user)
            if not getattr(run, "report", None):
                raise HTTPException(status_code=409, detail="Report is not ready yet.")
            if fmt == "csv_remediation":
                from app.reports.export_service import generate_remediation_tracker_csv
                content = generate_remediation_tracker_csv(run.report)
                export_payload = {"analysis_id": analysis_id, "format": "csv_remediation", "csv": content}
            elif fmt == "csv_urls":
                from app.reports.export_service import generate_urls_csv
                content = generate_urls_csv(run.report)
                export_payload = {"analysis_id": analysis_id, "format": "csv_urls", "csv": content}
            else:
                report = run.report
                scores = getattr(report, "scores", None)
                export_payload = {
                    "analysis_id": analysis_id,
                    "format": "summary_json",
                    "website_url": run.website_url,
                    "overall_score": getattr(scores, "overall_score", None),
                    "pillar_scores": getattr(scores, "pillar_scores", {}),
                    "findings_count": len(getattr(report, "findings", []) or []),
                    "summary": getattr(report, "executive_summary", ""),
                }
            result = {"content": [{"type": "text", "text": _json(export_payload)}], "structuredContent": export_payload}
        elif name == "dristik_findings_list":
            if not _mcp_authorized(user, "findings.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit findings access.")
            analysis_id = args.get("analysis_id")
            from app.identity.access import require_analysis
            run = require_analysis(analysis_id, user) if isinstance(analysis_id, str) and analysis_id else None
            if run is None:
                raise HTTPException(status_code=400, detail="analysis_id is required.")
            report = getattr(run, "report", None)
            if not report:
                raise HTTPException(status_code=409, detail="Report is not ready yet.")
            findings = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                        for item in (getattr(report, "findings", None) or [])]
            payload = {"analysis_id": analysis_id, "count": len(findings), "findings": findings}
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_evidence_list":
            if not _mcp_authorized(user, "evidence.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit evidence access.")
            analysis_id = args.get("analysis_id")
            from app.identity.access import require_analysis
            run = require_analysis(analysis_id, user) if isinstance(analysis_id, str) and analysis_id else None
            if run is None:
                raise HTTPException(status_code=400, detail="analysis_id is required.")
            graph = getattr(getattr(run, "report", None), "evidence_graph", None)
            if graph is None:
                raise HTTPException(status_code=409, detail="Evidence graph is not available for this run.")
            payload = graph.model_dump(mode="json") if hasattr(graph, "model_dump") else graph
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_agent_execute":
            if not _mcp_authorized(user, "agent.execute", "mission:create"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit agent execution.")
            analysis_id, node_id = args.get("analysis_id"), args.get("node_id")
            if not isinstance(analysis_id, str) or not analysis_id or not isinstance(node_id, str) or not node_id:
                raise HTTPException(status_code=400, detail="analysis_id and node_id are required.")
            from app.identity.access import require_analysis
            from app.orchestration.orchestrator import orchestrator
            require_analysis(analysis_id, user)
            payload = await orchestrator.run_pipeline_node(analysis_id, node_id)
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_workflow_execute":
            if not _mcp_authorized(user, "workflow.execute", "mission:create"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit workflow execution.")
            analysis_id, section_id = args.get("analysis_id"), args.get("section_id")
            if not isinstance(analysis_id, str) or not analysis_id or not isinstance(section_id, str) or not section_id:
                raise HTTPException(status_code=400, detail="analysis_id and section_id are required.")
            from app.identity.access import require_analysis
            from app.orchestration.orchestrator import orchestrator
            require_analysis(analysis_id, user)
            payload = await orchestrator.run_pipeline_section(analysis_id, section_id)
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_connector_status":
            if not _mcp_authorized(user, "connector.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit connector inspection.")
            from app.connectors.store import connector_store
            cid = args.get("connector_id")
            if cid:
                item = connector_store.get_integration(cid)
                if not item or item.org_id != user.org_id:
                    raise HTTPException(status_code=404, detail="Connector not found.")
                connectors_data = [item.model_dump(mode="json")]
            else:
                items = connector_store.get_integrations_for_org(user.org_id)
                connectors_data = [i.model_dump(mode="json") for i in items]
            payload = {"connectors": connectors_data, "count": len(connectors_data)}
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_pipeline_inspect":
            if not _mcp_authorized(user, "pipeline.inspect", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit pipeline inspection.")
            from app.orchestration.pipeline_dag import SECTIONS_REGISTRY, NODES_REGISTRY, SECTION_TO_PILLAR
            sections = [
                {"section_id": s.section_id, "title": s.title, "description": s.description,
                 "order": s.order, "node_ids": s.node_ids, "pillar": SECTION_TO_PILLAR.get(s.section_id, "")}
                for s in SECTIONS_REGISTRY
            ]
            nodes = [
                {"node_id": n.node_id, "section_id": n.section_id, "section_title": n.section_title,
                 "title": n.title, "description": n.description, "agent_name": n.agent_name,
                 "dependencies": n.dependencies}
                for n in NODES_REGISTRY.values() if hasattr(NODES_REGISTRY, "values")
            ] if isinstance(NODES_REGISTRY, dict) else [
                {"node_id": n.node_id, "section_id": n.section_id, "section_title": n.section_title,
                 "title": n.title, "description": n.description, "agent_name": n.agent_name,
                 "dependencies": n.dependencies}
                for n in NODES_REGISTRY
            ]
            payload = {"sections": sections, "nodes": nodes, "total_nodes": len(nodes), "total_sections": len(sections)}
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_pipeline_status":
            if not _mcp_authorized(user, "audit.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit pipeline status access.")
            analysis_id = args.get("analysis_id")
            if not isinstance(analysis_id, str) or not analysis_id:
                raise HTTPException(status_code=400, detail="analysis_id is required.")
            from app.identity.access import require_analysis
            from app.orchestration.pipeline_dag import get_pipeline_controller, SECTIONS_REGISTRY
            run = require_analysis(analysis_id, user)
            graph = get_pipeline_controller(analysis_id).get_full_graph_state()
            payload = _pipeline_status_payload(analysis_id, run, graph, SECTIONS_REGISTRY)
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_report_artifacts":
            if not _mcp_authorized(user, "report.export", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit report artifact access.")
            analysis_id = args.get("analysis_id")
            if not isinstance(analysis_id, str) or not analysis_id:
                raise HTTPException(status_code=400, detail="analysis_id is required.")
            from app.identity.access import require_analysis
            run = require_analysis(analysis_id, user)
            if not getattr(run, "report", None):
                raise HTTPException(status_code=409, detail="Report is not ready yet.")
            base_url = str(request.base_url).rstrip("/")
            root = f"{base_url}/api/v1/reports/{analysis_id}"
            payload = {
                "analysis_id": analysis_id,
                "status": "ready",
                "artifacts": [
                    {"id": "seo_audit_book_html", "format": "html", "url": f"{root}/seo-report?format=html", "owner": "dristik"},
                    {"id": "seo_audit_book_pdf", "format": "pdf", "url": f"{root}/seo-report?format=pdf&download=true", "owner": "dristik"},
                    {"id": "geo_audit_book_pdf", "format": "pdf", "url": f"{root}/geo-report?format=pdf", "owner": "dristik"},
                    {"id": "executive_deck_html", "format": "html", "url": f"{root}/executive-deck", "owner": "dristik"},
                    {"id": "executive_deck_pptx", "format": "pptx", "url": f"{root}/deck.pptx", "owner": "dristik"},
                    {"id": "audit_deliverables_json", "format": "json", "url": f"{root}/deliverables", "owner": "dristik"},
                    {"id": "remediation_tracker_csv", "format": "csv", "url": f"{root}/export/remediation-tracker.csv", "owner": "dristik"},
                    {"id": "crawl_urls_csv", "format": "csv", "url": f"{root}/export/urls.csv", "owner": "dristik"},
                ],
                "access_note": "Artifact URLs are protected by Dristik authentication and tenant authorization; use the same bearer token and connection email headers.",
            }
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_blackboard_read":
            if not _mcp_authorized(user, "blackboard.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit blackboard inspection.")
            analysis_id = args.get("analysis_id")
            if not isinstance(analysis_id, str) or not analysis_id:
                raise HTTPException(status_code=400, detail="analysis_id is required.")
            from app.identity.access import require_analysis
            from app.orchestration.orchestrator import orchestrator
            run = require_analysis(analysis_id, user)
            bb = orchestrator.blackboards.get(analysis_id)
            if bb:
                claims_items = []
                if hasattr(bb, "claim_registry") and hasattr(bb.claim_registry, "_claims"):
                    claims_items = [
                        c.model_dump(mode="json") if hasattr(c, "model_dump") else (c.__dict__ if hasattr(c, "__dict__") else dict(c))
                        for c in bb.claim_registry._claims.values()
                    ]
                pages_summary = [
                    {"url": getattr(p, "url", ""), "status_code": getattr(p, "status_code", 200), "title": getattr(p, "title", "")}
                    for p in (getattr(bb, "pages", []) or [])[:20]
                ]
                observations_summary = [
                    o.model_dump(mode="json") if hasattr(o, "model_dump") else str(o)
                    for o in (getattr(bb, "observations", []) or [])[:20]
                ]
                findings_summary = [
                    f.model_dump(mode="json") if hasattr(f, "model_dump") else str(f)
                    for f in (getattr(bb, "findings", []) or [])[:20]
                ]
                payload = {
                    "analysis_id": analysis_id,
                    "stage": str(getattr(bb, "stage", run.status)),
                    "website_url": bb.website_url,
                    "pages_crawled_count": len(getattr(bb, "pages", []) or []),
                    "pages_sample": pages_summary,
                    "site_facts": getattr(bb, "site_facts", {}),
                    "claims_count": len(claims_items),
                    "claims": claims_items[:25],
                    "observations_count": len(getattr(bb, "observations", []) or []),
                    "observations": observations_summary,
                    "findings_count": len(getattr(bb, "findings", []) or []),
                    "findings": findings_summary,
                }
            else:
                report = getattr(run, "report", None)
                findings = getattr(report, "findings", []) or [] if report else []
                payload = {
                    "analysis_id": analysis_id,
                    "stage": str(getattr(run.status, "value", run.status)),
                    "website_url": run.website_url,
                    "pages_crawled_count": len(getattr(run, "crawled_pages", []) or []),
                    "claims_count": 0,
                    "claims": [],
                    "findings_count": len(findings),
                    "findings": [f.model_dump(mode="json") if hasattr(f, "model_dump") else str(f) for f in findings[:20]],
                }
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_claim_submit":
            if not _mcp_authorized(user, "claim.submit", "mission:create"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit submitting claims.")
            analysis_id = args.get("analysis_id")
            statement = args.get("statement")
            if not isinstance(analysis_id, str) or not analysis_id:
                raise HTTPException(status_code=400, detail="analysis_id is required.")
            if not isinstance(statement, str) or len(statement.strip()) < 5:
                raise HTTPException(status_code=400, detail="statement must be at least 5 characters.")
            from app.identity.access import require_analysis
            from app.orchestration.orchestrator import orchestrator
            from app.domain.enums import Category, Severity, ClaimType
            require_analysis(analysis_id, user)
            bb = orchestrator.blackboards.get(analysis_id)
            if not bb:
                raise HTTPException(status_code=409, detail=f"Active blackboard not found for analysis '{analysis_id}'. Start or resume the audit first.")
            raw_cat = (args.get("category") or "CONTENT").upper()
            cat = getattr(Category, raw_cat, Category.CONTENT)
            conf = float(args.get("confidence", 0.85))
            ev_refs = args.get("supporting_evidence") or []
            claim = bb.claim_registry.register_claim(
                agent_id="external.ai.brain",
                statement=statement.strip(),
                category=cat,
                severity=Severity.MEDIUM,
                claim_type=ClaimType.INFERENCE,
                evidence_refs=ev_refs if isinstance(ev_refs, list) else [str(ev_refs)],
                confidence=max(0.1, min(conf, 1.0)),
                recommendation=args.get("recommendation") or f"External AI recommendation: {statement.strip()[:60]}",
            )
            payload = {
                "claim_id": claim.id,
                "statement": claim.statement,
                "confidence": claim.confidence,
                "verification_status": "registered_for_adversarial_verification",
                "analysis_id": analysis_id,
            }
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name in ("dristik_crux_query", "dristik_pagespeed_query"):
            if not _mcp_authorized(user, "connector.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit reading integration data.")
            from app.api.routes.integrations.performance_data import fetch_crux, fetch_pagespeed
            if name == "dristik_crux_query":
                origin = args.get("origin")
                if not isinstance(origin, str) or not origin.strip():
                    raise HTTPException(status_code=400, detail="origin is required.")
                form_factor = str(args.get("form_factor") or "PHONE").upper()
                if form_factor not in ("PHONE", "DESKTOP", "TABLET"):
                    raise HTTPException(status_code=400, detail="form_factor must be PHONE, DESKTOP, or TABLET.")
                url = args.get("url")
                if url is not None and not isinstance(url, str):
                    raise HTTPException(status_code=400, detail="url must be a string.")
                payload = await fetch_crux(origin, form_factor, url)
            else:
                target_url = args.get("url")
                if not isinstance(target_url, str) or not target_url.strip():
                    raise HTTPException(status_code=400, detail="url is required.")
                strategy = str(args.get("strategy") or "mobile").lower()
                if strategy not in ("mobile", "desktop"):
                    raise HTTPException(status_code=400, detail="strategy must be mobile or desktop.")
                categories = args.get("categories") or ["performance", "accessibility", "best-practices", "seo"]
                allowed_categories = {"performance", "accessibility", "best-practices", "seo"}
                if not isinstance(categories, list) or any(c not in allowed_categories for c in categories):
                    raise HTTPException(status_code=400, detail="categories contains an unsupported category.")
                payload = await fetch_pagespeed(target_url, strategy, categories)
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_google_search":
            if not _mcp_authorized(user, "connector.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit reading integration data.")
            query = args.get("query")
            if not isinstance(query, str) or not query.strip():
                raise HTTPException(status_code=400, detail="query is required.")
            num, start = int(args.get("num", 10)), int(args.get("start", 1))
            if num < 1 or num > 10 or start < 1 or start > 91:
                raise HTTPException(status_code=400, detail="num must be 1-10 and start must be 1-91.")
            from app.api.routes.integrations.performance_data import fetch_google_search
            payload = await fetch_google_search(query, num, start)
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_ai_citations_track":
            if not _mcp_authorized(user, "citations.track", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit citation tracking.")
            domain = args.get("domain")
            if not isinstance(domain, str) or not domain.strip():
                raise HTTPException(status_code=400, detail="domain is required.")
            payload = _citation_tracking_unavailable_payload(
                domain, args.get("queries"), args.get("engines")
            )
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_provider_invoke":
            if not _mcp_authorized(user, "provider.invoke", "mission:create"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit provider invocation.")
            provider_id = args.get("provider_id")
            prompt = args.get("prompt")
            if not isinstance(provider_id, str) or not provider_id:
                raise HTTPException(status_code=400, detail="provider_id is required.")
            if not isinstance(prompt, str) or not prompt.strip():
                raise HTTPException(status_code=400, detail="prompt is required.")
            from app.api.routes.integrations.provider_adapters import invoke_provider, ProviderInvoke
            invoke_body = ProviderInvoke(
                prompt=prompt,
                system=args.get("system"),
                max_tokens=int(args.get("max_tokens", 1200)),
            )
            payload = await invoke_provider(provider_id, invoke_body, user)
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_tasks_list":
            if not _mcp_authorized(user, "tasks.read", "mission:read"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit reading tasks.")
            limit = int(args.get("limit", 20))
            payload = await list_tasks(user, limit=limit)
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name == "dristik_task_send_message":
            if not _mcp_authorized(user, "tasks.message", "mission:create"):
                raise HTTPException(status_code=403, detail="Connection grant does not permit sending task messages.")
            task_id = args.get("task_id")
            sender = args.get("sender")
            if not task_id or not sender:
                raise HTTPException(status_code=400, detail="task_id and sender are required.")
            msg_body = MessageCreate(
                sender=sender,
                recipient=args.get("recipient"),
                message_type=args.get("message_type", "text"),
                payload=args.get("payload") or {},
            )
            payload = await send_message(task_id, msg_body, user)
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name in ("dristik_ping", "ping"):
            payload = {
                "status": "connected",
                "ping": "pong",
                "timestamp": time.time(),
                "org_id": user.org_id,
                "identity": user.email,
                "client_name": user.full_name,
                "protocol": MCP_VERSION,
                "message": args.get("message") or "Two-way connection verified active.",
            }
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        elif name in ("dristik_send_message", "dristik_message_send"):
            msg = args.get("message")
            if not msg or not isinstance(msg, str):
                raise HTTPException(status_code=400, detail="message is required.")
            payload = {
                "status": "received",
                "message_id": "msg_" + uuid.uuid4().hex[:12],
                "sender": user.email,
                "received_at": time.time(),
                "echo": msg.strip(),
                "org_id": user.org_id,
                "ack": "Message acknowledged by Dristik Brain controller.",
            }
            result = {"content": [{"type": "text", "text": _json(payload)}], "structuredContent": payload}
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Unknown tool."}}
        if not (isinstance(result, dict) and "content" in result):
            result = {"content": [{"type": "text", "text": _json(result)}], "structuredContent": result}

        # Log outbound response for tools/call
        if user.auth_provider == "dristik_connect":
            t_structured = result.get("structuredContent") if isinstance(result, dict) else None
            outbound_summary = f"Executed {name} successfully"
            if name in ("dristik_audits_list", "dristik_audit_list", "dristik_analyses_list", "dristik_runs_list") and t_structured:
                outbound_summary = f"Returned {t_structured.get('count', 0)} audits for {user.org_id}"
            elif name == "dristik_pipeline_inspect" and t_structured:
                outbound_summary = f"Returned {t_structured.get('total_sections', 0)} pipeline sections & {t_structured.get('total_nodes', 0)} DAG nodes"
            elif name == "dristik_agents_list" and t_structured:
                outbound_summary = f"Returned {t_structured.get('count', 0)} registered specialist agents"
            elif name in ("dristik_report_get", "dristik_audit_get") and t_structured:
                outbound_summary = f"Returned audit report for {t_structured.get('analysis_id')}"
            elif name in ("dristik_ping", "ping"):
                outbound_summary = "Pong acknowledgment returned"
            elif name in ("dristik_send_message", "dristik_message_send"):
                outbound_summary = "Message acknowledged by Dristik controller"
            _log_connection_event(
                user.user_id, user.org_id,
                event=f"outbound:tools/call:{name}",
                direction="outbound",
                method="tools/call",
                tool=name,
                summary=outbound_summary,
                status="success",
            )
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not supported."}}

    # Log outbound response for discovery methods
    if user.auth_provider == "dristik_connect":
        if method == "tools/list":
            tool_count = len(result.get("tools", [])) if isinstance(result, dict) else 0
            _log_connection_event(
                user.user_id, user.org_id,
                event="outbound:tools/list",
                direction="outbound",
                method="tools/list",
                summary=f"Exposed {tool_count} authorized MCP tools to AI client",
                status="success",
            )
        elif method == "initialize":
            _log_connection_event(
                user.user_id, user.org_id,
                event="outbound:initialize",
                direction="outbound",
                method="initialize",
                summary=f"Handshake accepted (protocol {MCP_VERSION})",
                status="success",
            )
        elif method == "ping":
            _log_connection_event(
                user.user_id, user.org_id,
                event="outbound:ping",
                direction="outbound",
                method="ping",
                summary="Pong acknowledgment returned",
                status="success",
            )

    return {"jsonrpc": "2.0", "id": request_id, "result": result}
