import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.api.routes.integrations import provider_adapters as providers


def test_provider_credentials_are_not_returned(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, "DB_PATH", tmp_path / "connect.sqlite3")
    monkeypatch.setenv("DRISTIK_CONNECT_FERNET_KEY", Fernet.generate_key().decode())
    user = providers.UserIdentity(org_id="org-a", email="owner@example.test")
    body = providers.ProviderCreate(provider="openai", label="CI test", model="gpt-4.1-mini", api_key="sk-test-secret-123456")
    response = __import__("asyncio").run(providers.create_provider(body, user))
    assert response["status"] == "configured_not_tested"
    assert "api_key" not in response
    with providers._db() as conn:
        row = conn.execute("SELECT encrypted_secret FROM uc_provider_credentials WHERE id=?", (response["id"],)).fetchone()
    assert row["encrypted_secret"] != body.api_key
    assert providers._cipher().decrypt(row["encrypted_secret"].encode()).decode() == body.api_key


def test_provider_requires_encryption_key(monkeypatch):
    monkeypatch.delenv("DRISTIK_CONNECT_FERNET_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        providers._cipher()
    assert exc.value.status_code == 503


def test_provider_hosts_are_fixed_https_hosts():
    assert providers.PROVIDERS["openai"][0] == "https://api.openai.com/v1"
    assert providers.PROVIDERS["anthropic"][0] == "https://api.anthropic.com/v1"
    assert all(url.startswith("https://") for url, _ in providers.PROVIDERS.values())


@pytest.mark.asyncio
async def test_model_router_uses_explicit_tenant_provider(tmp_path, monkeypatch):
    from app.core.inference import model_router as router_module

    monkeypatch.setattr(providers, "DB_PATH", tmp_path / "routing.sqlite3")
    monkeypatch.setenv("DRISTIK_CONNECT_FERNET_KEY", Fernet.generate_key().decode())
    user = providers.UserIdentity(org_id="org-a", email="owner@example.test")
    body = providers.ProviderCreate(
        provider="openai", label="Selected routing provider",
        model="gpt-4.1-mini", api_key="sk-test-routing-key-123456",
    )
    created = await providers.create_provider(body, user)
    with providers._db() as conn:
        conn.execute("UPDATE uc_provider_credentials SET status='healthy' WHERE id=?", (created["id"],))

    calls = []
    async def fake_invoke(provider, model, key, prompt, system, max_tokens, temperature=0.1):
        calls.append((provider, model, prompt, system, max_tokens, temperature))
        return {"text": '{"claims":[]}', "provider": provider, "model": model,
                "usage": {"prompt_tokens": 11, "completion_tokens": 7}}

    monkeypatch.setattr(providers, "_invoke", fake_invoke)
    router = router_module.ModelRouter()
    with router_module.use_provider_override(created["id"], "org-a"):
        response = await router._generate_chat_completion(
            model="platform-default-model", system_prompt="system",
            user_prompt="structured task", max_tokens=333, temperature=0.0,
        )

    assert calls == [("openai", "gpt-4.1-mini", "structured task", "system", 333, 0.0)]
    assert response["provider"] == "openai"
    assert response["model"] == "gpt-4.1-mini"
    assert response["input_tokens"] == 11
    assert response["output_tokens"] == 7


@pytest.mark.asyncio
async def test_model_router_provider_override_cannot_cross_tenants(tmp_path, monkeypatch):
    from app.core.inference import model_router as router_module

    monkeypatch.setattr(providers, "DB_PATH", tmp_path / "routing.sqlite3")
    monkeypatch.setenv("DRISTIK_CONNECT_FERNET_KEY", Fernet.generate_key().decode())
    user = providers.UserIdentity(org_id="org-a", email="owner@example.test")
    body = providers.ProviderCreate(
        provider="openai", label="Tenant A", model="gpt-4.1-mini",
        api_key="sk-test-tenant-isolation-123456",
    )
    created = await providers.create_provider(body, user)
    with providers._db() as conn:
        conn.execute("UPDATE uc_provider_credentials SET status='healthy' WHERE id=?", (created["id"],))

    router = router_module.ModelRouter()
    with router_module.use_provider_override(created["id"], "org-b"):
        with pytest.raises(RuntimeError, match="not healthy or is unavailable"):
            await router._generate_chat_completion(
                model="ignored", system_prompt="system", user_prompt="task",
                max_tokens=100, temperature=0.1,
            )
