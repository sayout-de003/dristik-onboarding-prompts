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
