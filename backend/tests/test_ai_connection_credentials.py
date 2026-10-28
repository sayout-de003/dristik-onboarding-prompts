"""Security regression tests for Dristik-issued external AI credentials."""
import asyncio
import hashlib
import time

import pytest
from fastapi import HTTPException

from app.api.routes.integrations import universal_connect as uc
from app.identity.authorizer import UserIdentity
from app.domain.enums import UserRole


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(uc, "DB_PATH", tmp_path / "connect.sqlite3")
    monkeypatch.setenv("DRISTIK_CONNECT_IDENTITY_DOMAIN", "connect.example.test")
    yield tmp_path


def owner():
    return UserIdentity(org_id="org-a", email="owner@example.test", role=UserRole.OWNER)


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


@pytest.mark.parametrize("url", [
    "http://127.0.0.1",
    "https://localhost",
    "http://10.1.2.3",
    "https://192.168.1.1",
    "http://169.254.169.254/latest/meta-data",
    "file:///etc/passwd",
    "https://user:password@example.com",
])
def test_ai_audit_target_rejects_private_or_unsafe_urls(url):
    with pytest.raises(HTTPException):
        uc._validate_public_audit_url(url)


def test_ai_audit_target_accepts_public_ip_literal():
    assert uc._validate_public_audit_url("https://8.8.8.8") == "https://8.8.8.8/"


def test_bearer_only_authentication_without_email_header_succeeds(isolated_db):
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Cursor MCP", grant_profile="full_access"), owner()
    ))
    user = asyncio.run(uc.get_mcp_user(
        authorization="Bearer " + created["api_key"],
        connection_email=None,
        session_user=None,
    ))
    assert user.org_id == "org-a"
    assert user.email == created["connection_email"]
    assert user.auth_provider == "dristik_connect"


def test_connection_activity_events_tracked_and_retrievable(isolated_db):
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Claude Desktop", grant_profile="full_access"), owner()
    ))
    # Authenticate once
    asyncio.run(uc.get_mcp_user(authorization="Bearer " + created["api_key"], session_user=None))
    # Rotate key
    rotated = asyncio.run(uc.rotate_ai_connection(created["id"], owner()))
    # Revoke
    asyncio.run(uc.revoke_ai_connection(created["id"], owner()))

    activity = asyncio.run(uc.get_ai_connection_activity(created["id"], owner()))
    events = [e["event"] for e in activity["events"]]
    assert "created" in events
    assert "authenticated" in events
    assert "rotated" in events
    assert "revoked" in events


@pytest.mark.asyncio
async def test_mcp_tools_list_and_call_extended_tools(isolated_db, monkeypatch):
    created = await uc.create_ai_connection(
        uc.AIConnectionCreate(name="AI Operator", grant_profile="full_access"), owner()
    )
    user = await uc.get_mcp_user(authorization="Bearer " + created["api_key"], session_user=None)

    class DummyRequest:
        def __init__(self, data):
            self._data = data
        async def json(self):
            return self._data

    from fastapi import BackgroundTasks
    bg = BackgroundTasks()

    # Test tools/list
    list_req = DummyRequest({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    list_res = await uc.mcp_json_rpc(list_req, bg, user)
    tool_names = [t["name"] for t in list_res["result"]["tools"]]
    assert "dristik_capabilities_list" in tool_names
    assert "dristik_template_inspect" in tool_names
    assert "dristik_audit_cancel" in tool_names
    assert "dristik_report_export" in tool_names
    assert "dristik_connector_status" in tool_names
    assert "dristik_agents_list" in tool_names

    # Test tools/call: dristik_template_inspect
    inspect_req = DummyRequest({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                "params": {"name": "dristik_template_inspect", "arguments": {"template_id": "website-audit"}}})
    inspect_res = await uc.mcp_json_rpc(inspect_req, bg, user)
    assert inspect_res["result"]["structuredContent"]["template_id"] == "website-audit"
    assert "seo" in inspect_res["result"]["structuredContent"]["supported_pillars"]

    # Test tools/call: dristik_agents_list for specific agent
    agent_req = DummyRequest({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                              "params": {"name": "dristik_agents_list", "arguments": {"agent_id": "business.discovery.v3"}}})
    agent_res = await uc.mcp_json_rpc(agent_req, bg, user)
    assert len(agent_res["result"]["structuredContent"]["agents"]) == 1
    assert agent_res["result"]["structuredContent"]["agents"][0]["agent_id"] == "business.discovery.v3"


def test_mcp_public_url_and_dynamic_resolution(isolated_db, monkeypatch):
    # 1. When DRISTIK_MCP_PUBLIC_URL is explicitly configured
    monkeypatch.setenv("DRISTIK_MCP_PUBLIC_URL", "https://connect.dristik.ai/api/v1/mcp")
    res1 = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Explicit URL client", grant_profile="full_access"), owner()
    ))
    assert res1["mcp_endpoint"] == "https://connect.dristik.ai/api/v1/mcp"
    assert res1["mcp_endpoint_is_absolute"] is True
    assert res1["mcp_config"]["url"] == "https://connect.dristik.ai/api/v1/mcp"
    assert res1["mcp_config"]["sse_url"] == "https://connect.dristik.ai/api/v1/mcp/sse"

    # 2. When DRISTIK_MCP_PUBLIC_URL is empty, dynamic resolution from request headers
    monkeypatch.delenv("DRISTIK_MCP_PUBLIC_URL", raising=False)
    class FakeURL:
        scheme = "http"
        netloc = "internal.host:8000"
    class FakeRequest:
        headers = {"x-forwarded-proto": "https", "x-forwarded-host": "ai.tenant.example.com"}
        url = FakeURL()

    res2 = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Dynamic URL client", grant_profile="full_access"), owner(), FakeRequest()
    ))
    assert res2["mcp_endpoint"] == "https://ai.tenant.example.com/api/v1/mcp"
    assert res2["mcp_endpoint_is_absolute"] is True


def test_live_mcp_handshake_end_to_end(isolated_db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setenv("DRISTIK_MCP_PUBLIC_URL", "https://api.dristik.ai/api/v1/mcp")
    client = TestClient(app)

    # 1. Issue an AI connection identity and API key
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Claude Desktop Live", grant_profile="full_access"), owner()
    ))
    api_key = created["api_key"]
    email = created["connection_email"]
    auth_headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Dristik-Connection-Email": email,
    }

    # 2. Unauthenticated request to MCP endpoints must be rejected with 401
    unauth_resp = client.get("/api/v1/mcp")
    assert unauth_resp.status_code == 401

    # 3. GET /api/v1/mcp server discovery with credentials
    info_resp = client.get("/api/v1/mcp", headers=auth_headers)
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert info_data["name"] == "dristik-connect"
    assert info_data["status"] == "active"
    assert info_data["protocolVersion"] == "2025-03-26"
    assert info_data["authenticated_as"] == email

    # 4. GET /api/v1/mcp/sse Server-Sent Events handshake
    sse_resp = client.get("/api/v1/mcp/sse", headers=auth_headers)
    assert sse_resp.status_code == 200
    assert "text/event-stream" in sse_resp.headers.get("content-type", "")
    assert "event: endpoint" in sse_resp.text
    assert "https://api.dristik.ai/api/v1/mcp" in sse_resp.text

    # 5. SSE with query parameter token (browser EventSource compatibility)
    sse_query_resp = client.get(f"/api/v1/mcp/sse?token={api_key}")
    assert sse_query_resp.status_code == 200
    assert "event: endpoint" in sse_query_resp.text

    # 6. POST /api/v1/mcp JSON-RPC initialize
    init_payload = {
        "jsonrpc": "2.0",
        "id": "req-1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "claude-client", "version": "1.0.0"},
        },
    }
    init_resp = client.post("/api/v1/mcp", json=init_payload, headers=auth_headers)
    assert init_resp.status_code == 200
    init_data = init_resp.json()
    assert init_data["result"]["protocolVersion"] == "2025-03-26"
    assert init_data["result"]["serverInfo"]["name"] == "dristik-connect"

    # 7. POST /api/v1/mcp notifications/initialized notification
    notif_resp = client.post(
        "/api/v1/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=auth_headers,
    )
    assert notif_resp.status_code == 202

    # 8. POST /api/v1/mcp ping
    ping_resp = client.post(
        "/api/v1/mcp",
        json={"jsonrpc": "2.0", "id": "req-2", "method": "ping"},
        headers=auth_headers,
    )
    assert ping_resp.status_code == 200
    assert ping_resp.json()["result"] == {}

    # 9. POST /api/v1/mcp tools/list
    tools_resp = client.post(
        "/api/v1/mcp",
        json={"jsonrpc": "2.0", "id": "req-3", "method": "tools/list"},
        headers=auth_headers,
    )
    assert tools_resp.status_code == 200
    tools = [t["name"] for t in tools_resp.json()["result"]["tools"]]
    assert "dristik_capabilities_list" in tools
    assert "dristik_template_inspect" in tools
    assert "dristik_agents_list" in tools

    # 10. POST /api/v1/mcp tools/call: dristik_capabilities_list
    call_resp = client.post(
        "/api/v1/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "req-4",
            "method": "tools/call",
            "params": {"name": "dristik_capabilities_list", "arguments": {}},
        },
        headers=auth_headers,
    )
    assert call_resp.status_code == 200
    call_data = call_resp.json()
    assert "structuredContent" in call_data["result"]
    assert call_data["result"]["structuredContent"]["tenant_id"] == "org-a"

    # 11. Root direct endpoints /mcp and /mcp/sse
    root_mcp = client.get("/mcp", headers=auth_headers)
    assert root_mcp.status_code == 200
    assert root_mcp.json()["name"] == "dristik-connect"


def test_provider_credentials_rely_on_configured_fernet_key(isolated_db, monkeypatch):
    import os
    from app.api.routes.integrations import provider_adapters as providers
    monkeypatch.setattr(providers, "DB_PATH", isolated_db / "providers.sqlite3")

    # With DRISTIK_CONNECT_FERNET_KEY configured from .env, encryption works
    assert os.getenv("DRISTIK_CONNECT_FERNET_KEY")
    body = providers.ProviderCreate(
        provider="openai",
        label="Production LLM",
        model="gpt-4.1-mini",
        api_key="sk-live-secret-fernet-encrypted-12345",
    )
    user = providers.UserIdentity(org_id="org-a", email="owner@example.test", role=UserRole.OWNER)
    res = asyncio.run(providers.create_provider(body, user))
    assert res["status"] == "configured_not_tested"
    assert "api_key" not in res

    # Stored secret is encrypted in database
    with providers._db() as conn:
        row = conn.execute("SELECT encrypted_secret FROM uc_provider_credentials WHERE id=?", (res["id"],)).fetchone()
    assert row["encrypted_secret"] != body.api_key
    assert providers._cipher().decrypt(row["encrypted_secret"].encode()).decode() == body.api_key


def test_agents_list_exposes_105_specialist_agents(isolated_db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Fleet Inspector", grant_profile="full_access"),
        owner(),
    ))
    auth_headers = {
        "Authorization": "Bearer " + created["api_key"],
        "X-Dristik-Connection-Email": created["connection_email"],
    }

    # Discover all registered agents
    resp = client.post(
        "/api/v1/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "agents-req-1",
            "method": "tools/call",
            "params": {"name": "dristik_agents_list", "arguments": {}},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["result"]["structuredContent"]
    assert data["count"] >= 105, f"Expected at least 105 registered agents, got {data['count']}"
    domains = {agent["domain"].upper() for agent in data["agents"]}
    for expected_domain in ["BUSINESS", "TECHNICAL_SEO", "CONTENT", "GEO", "AEO", "AI_SEARCH", "COPYWRITING", "PRESENTATION"]:
        assert expected_domain in domains

    # Query single agent by ID
    single_resp = client.post(
        "/api/v1/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "agents-req-2",
            "method": "tools/call",
            "params": {"name": "dristik_agents_list", "arguments": {"agent_id": "ai_search.discoverability.v3"}},
        },
        headers=auth_headers,
    )
    assert single_resp.status_code == 200
    single_data = single_resp.json()["result"]["structuredContent"]
    assert single_data["count"] == 1
    assert single_data["agents"][0]["agent_id"] == "ai_search.discoverability.v3"


def test_external_ai_brain_pipeline_inspect_and_citations(isolated_db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="External AI Brain", grant_profile="full_access"),
        owner(),
    ))
    auth_headers = {
        "Authorization": "Bearer " + created["api_key"],
        "X-Dristik-Connection-Email": created["connection_email"],
    }

    # 1. Pipeline inspect
    pipe_resp = client.post(
        "/api/v1/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "pipe-1",
            "method": "tools/call",
            "params": {"name": "dristik_pipeline_inspect", "arguments": {}},
        },
        headers=auth_headers,
    )
    assert pipe_resp.status_code == 200
    pipe_data = pipe_resp.json()["result"]["structuredContent"]
    assert pipe_data["total_sections"] > 0
    assert pipe_data["total_nodes"] > 0

    # 2. AI citations track
    cite_resp = client.post(
        "/api/v1/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "cite-1",
            "method": "tools/call",
            "params": {
                "name": "dristik_ai_citations_track",
                "arguments": {"domain": "dristik.org", "engines": ["perplexity", "chatgpt", "gemini", "claude"]},
            },
        },
        headers=auth_headers,
    )
    assert cite_resp.status_code == 200
    cite_data = cite_resp.json()["result"]["structuredContent"]
    assert cite_data["domain"] == "dristik.org"
    assert cite_data["status"] == "NOT_CONFIGURED"
    assert cite_data["metrics_available"] is False
    assert cite_data["overall_citation_score"] is None
    assert "perplexity" in cite_data["requested_engines"]


def test_external_ai_tasks_messaging_and_listing(isolated_db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Task Collaborator", grant_profile="full_access"),
        owner(),
    ))
    auth_headers = {
        "Authorization": "Bearer " + created["api_key"],
        "X-Dristik-Connection-Email": created["connection_email"],
    }

    # 1. Create task via MCP
    create_resp = client.post(
        "/api/v1/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "task-create-1",
            "method": "tools/call",
            "params": {
                "name": "dristik_create_task",
                "arguments": {"goal": "Optimize brand citations on Perplexity", "inputs": {"target": "dristik.org"}},
            },
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["result"]["structuredContent"]["id"]

    # 2. Send message into task via MCP
    msg_resp = client.post(
        "/api/v1/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "task-msg-1",
            "method": "tools/call",
            "params": {
                "name": "dristik_task_send_message",
                "arguments": {
                    "task_id": task_id,
                    "sender": "external_claude_brain",
                    "payload": {"analysis": "Identified schema gap in Organization sameAs links"},
                },
            },
        },
        headers=auth_headers,
    )
    assert msg_resp.status_code == 200
    assert msg_resp.json()["result"]["structuredContent"]["task_id"] == task_id

    # 3. List tasks via MCP
    list_resp = client.post(
        "/api/v1/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "task-list-1",
            "method": "tools/call",
            "params": {"name": "dristik_tasks_list", "arguments": {"limit": 10}},
        },
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    tasks = list_resp.json()["result"]["structuredContent"]["tasks"]
    assert any(t["id"] == task_id for t in tasks)


def test_kimi_provider_creation_and_encryption(isolated_db, monkeypatch):
    from app.api.routes.integrations import provider_adapters as providers
    monkeypatch.setattr(providers, "DB_PATH", isolated_db / "kimi_providers.sqlite3")

    body = providers.ProviderCreate(
        provider="kimi",
        label="Moonshot Kimi",
        model="moonshot-v1-8k",
        api_key="sk-kimi-test-secret-moonshot-12345",
    )
    user = providers.UserIdentity(org_id="org-a", email="owner@example.test", role=UserRole.OWNER)
    res = asyncio.run(providers.create_provider(body, user))
    assert res["status"] == "configured_not_tested"
    assert res["provider"] == "kimi"
    assert "api_key" not in res
    assert providers.PROVIDERS["kimi"][0] == "https://api.moonshot.cn/v1"


def test_blackboard_read_and_claim_submit(isolated_db):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.domain.models import AnalysisRun
    from app.domain.enums import AnalysisStage
    from app.orchestration.orchestrator import orchestrator
    from app.orchestration.cognition.blackboard import CognitiveBlackboard

    client = TestClient(app)
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Brain Controller", grant_profile="full_access"),
        owner(),
    ))
    auth_headers = {
        "Authorization": "Bearer " + created["api_key"],
        "X-Dristik-Connection-Email": created["connection_email"],
    }

    # Setup an active in-memory run and blackboard
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    analysis_id = "test-analysis-123"
    run = AnalysisRun(
        analysis_id=analysis_id,
        website_url="https://dristik.org",
        org_id="org-a",
        status=AnalysisStage.SPECIALIST_EXECUTION,
        created_at=now_iso,
        updated_at=now_iso,
    )
    orchestrator.runs[analysis_id] = run
    bb = CognitiveBlackboard(run_id=analysis_id, website_url="https://dristik.org")
    orchestrator.blackboards[analysis_id] = bb

    try:
        # 1. Read blackboard
        read_resp = client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "bb-1",
                "method": "tools/call",
                "params": {"name": "dristik_blackboard_read", "arguments": {"analysis_id": analysis_id}},
            },
            headers=auth_headers,
        )
        assert read_resp.status_code == 200
        assert read_resp.json()["result"]["structuredContent"]["analysis_id"] == analysis_id

        # 2. Submit claim into blackboard
        claim_resp = client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "claim-1",
                "method": "tools/call",
                "params": {
                    "name": "dristik_claim_submit",
                    "arguments": {
                        "analysis_id": analysis_id,
                        "statement": "Missing Product schema on pricing landing page",
                        "category": "STRUCTURED_DATA",
                        "confidence": 0.95,
                        "supporting_evidence": ["dom_element_pricing_table"],
                    },
                },
            },
            headers=auth_headers,
        )
        assert claim_resp.status_code == 200
        claim_data = claim_resp.json()["result"]["structuredContent"]
        assert claim_data["confidence"] == 0.95
        assert claim_data["verification_status"] == "registered_for_adversarial_verification"

        # Verify claim is now inside blackboard
        assert len(bb.claim_registry._claims) == 1
    finally:
        orchestrator.runs.pop(analysis_id, None)
        orchestrator.blackboards.pop(analysis_id, None)


def test_mcp_audits_list_ping_and_inbound_outbound_ledger(isolated_db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Grok Brain", grant_profile="full_access"), owner()
    ))
    auth_headers = {
        "Authorization": f"Bearer {created['api_key']}",
        "X-Dristik-Connection-Email": created["connection_email"],
    }

    # 1. Ping tool
    ping_resp = client.post(
        "/api/v1/mcp",
        json={"jsonrpc": "2.0", "id": "p-1", "method": "tools/call", "params": {"name": "dristik_ping", "arguments": {}}},
        headers=auth_headers,
    )
    assert ping_resp.status_code == 200
    assert ping_resp.json()["result"]["structuredContent"]["status"] == "connected"

    # 2. Audits list tool (what Grok specifically requested!)
    audits_resp = client.post(
        "/api/v1/mcp",
        json={"jsonrpc": "2.0", "id": "a-1", "method": "tools/call", "params": {"name": "dristik_audits_list", "arguments": {"limit": 10}}},
        headers=auth_headers,
    )
    assert audits_resp.status_code == 200
    audits_data = audits_resp.json()["result"]["structuredContent"]
    assert "audits" in audits_data
    assert audits_data["org_id"] == "org-a"

    # 3. Two-way message tool
    msg_resp = client.post(
        "/api/v1/mcp",
        json={"jsonrpc": "2.0", "id": "m-1", "method": "tools/call", "params": {"name": "dristik_send_message", "arguments": {"message": "Hello from Grok"}}},
        headers=auth_headers,
    )
    assert msg_resp.status_code == 200
    assert msg_resp.json()["result"]["structuredContent"]["status"] == "received"

    # 4. Inbound & Outbound Ledger inspection
    activity = asyncio.run(uc.get_ai_connection_activity(created["id"], owner()))
    events = activity["events"]
    assert len(events) >= 6

    inbound_events = [e for e in events if e.get("direction") == "inbound"]
    outbound_events = [e for e in events if e.get("direction") == "outbound"]

    assert len(inbound_events) >= 3
    assert len(outbound_events) >= 3

    tool_names = [e.get("tool") for e in events if e.get("tool")]
    assert "dristik_ping" in tool_names
    assert "dristik_audits_list" in tool_names


def test_ai_connection_interactive_test_probe_endpoint(isolated_db):
    created = asyncio.run(uc.create_ai_connection(
        uc.AIConnectionCreate(name="Claude Desktop", grant_profile="full_access"), owner()
    ))

    # Send audits_list probe from Dristik UI
    probe_res = asyncio.run(uc.test_ai_connection_message(
        created["id"],
        uc.ConnectionTestProbe(probe_type="audits_list", message="Check past audits"),
        owner(),
    ))
    assert probe_res["success"] is True
    assert probe_res["probe_type"] == "audits_list"
    assert "audits" in probe_res["response_data"]
    assert probe_res["round_trip_ms"] >= 0

    # Verify both outbound:probe_sent and inbound:probe_acknowledged are logged in ledger
    activity = asyncio.run(uc.get_ai_connection_activity(created["id"], owner()))
    event_names = [e["event"] for e in activity["events"]]
    assert "outbound:probe_sent" in event_names
    assert "inbound:probe_acknowledged" in event_names




