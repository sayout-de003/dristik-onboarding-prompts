"""Encrypted API-key storage and fixed-host adapters for major model providers."""
from __future__ import annotations

import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.identity.authorizer import UserIdentity
from app.identity.deps import get_current_user, require_permission

router = APIRouter(prefix="/connect/providers", tags=["Universal AI Connect Providers"])
DB_PATH = Path(os.getenv("DRISTIK_CONNECT_DB_PATH", str(Path(__file__).resolve().parents[4] / "data" / "universal_connect.sqlite3")))
PROVIDERS = {
    "openai": ("https://api.openai.com/v1", "openai"),
    "grok": ("https://api.x.ai/v1", "openai"),
    "deepseek": ("https://api.deepseek.com/v1", "openai"),
    "openrouter": ("https://openrouter.ai/api/v1", "openai"),
    "anthropic": ("https://api.anthropic.com/v1", "anthropic"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta", "gemini"),
    "kimi": ("https://api.moonshot.cn/v1", "openai"),
}


@contextmanager
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS uc_provider_credentials (
            id TEXT PRIMARY KEY, org_id TEXT NOT NULL, created_by TEXT NOT NULL,
            provider TEXT NOT NULL, label TEXT NOT NULL, model TEXT NOT NULL,
            encrypted_secret TEXT NOT NULL, status TEXT NOT NULL,
            created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_uc_provider_org ON uc_provider_credentials(org_id)")
        yield conn
        conn.commit()
    finally:
        conn.close()


def _cipher():
    key = os.getenv("DRISTIK_CONNECT_FERNET_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="Provider credential encryption is not configured.")
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode("ascii"))
    except Exception:
        raise HTTPException(status_code=503, detail="Provider credential encryption key is invalid.")


class ProviderCreate(BaseModel):
    provider: Literal["openai", "anthropic", "gemini", "grok", "deepseek", "openrouter", "kimi"]
    label: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=160)
    api_key: str = Field(min_length=8, max_length=4096)


class ProviderInvoke(BaseModel):
    prompt: str = Field(min_length=1, max_length=30000)
    system: str | None = Field(default=None, max_length=8000)
    max_tokens: int = Field(default=1200, ge=1, le=8192)


@router.get("")
async def list_providers(user: UserIdentity = Depends(get_current_user)):
    with _db() as conn:
        rows = conn.execute("SELECT id,provider,label,model,status,created_at,updated_at FROM uc_provider_credentials WHERE org_id=? ORDER BY created_at DESC", (user.org_id,)).fetchall()
    return {"providers": [dict(r) for r in rows], "supported": list(PROVIDERS)}


@router.post("", status_code=201)
async def create_provider(body: ProviderCreate, user: UserIdentity = Depends(require_permission("org:manage"))):
    cipher = _cipher()
    now, provider_id = time.time(), "ucp_" + uuid.uuid4().hex
    encrypted = cipher.encrypt(body.api_key.encode()).decode("ascii")
    with _db() as conn:
        conn.execute("INSERT INTO uc_provider_credentials VALUES (?,?,?,?,?,?,?,?,?,?)",
            (provider_id, user.org_id, user.user_id, body.provider, body.label, body.model, encrypted, "configured_not_tested", now, now))
    return {"id": provider_id, "provider": body.provider, "label": body.label, "model": body.model, "status": "configured_not_tested", "created_at": now}


async def _invoke(provider: str, model: str, key: str, prompt: str, system: str | None, max_tokens: int, temperature: float = 0.1) -> dict[str, Any]:
    base, style = PROVIDERS[provider]
    async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=8), follow_redirects=False) as client:
        if style == "openai":
            messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
            response = await client.post(base + "/chat/completions", headers={"Authorization": "Bearer " + key},
                json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature})
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                raise HTTPException(status_code=502, detail="Provider returned no completion choices.")
            output = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage") or {}
        elif style == "anthropic":
            response = await client.post(base + "/messages", headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                json={"model": model, "system": system or "", "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.1})
            response.raise_for_status()
            data = response.json()
            output = "\n".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text")
            usage = data.get("usage") or {}
        else:
            response = await client.post(base + "/models/" + model + ":generateContent", headers={"x-goog-api-key": key},
                json={"systemInstruction": {"parts": [{"text": system}]} if system else None,
                     "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                     "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.1}})
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates") or []
            output = "\n".join(part.get("text", "") for part in (candidates[0].get("content", {}).get("parts", []) if candidates else []))
            usage = data.get("usageMetadata") or {}
    return {"text": output, "usage": usage, "provider": provider, "model": model}


@router.post("/{provider_id}/invoke")
async def invoke_provider(provider_id: str, body: ProviderInvoke, user: UserIdentity = Depends(require_permission("mission:create"))):
    with _db() as conn:
        row = conn.execute("SELECT * FROM uc_provider_credentials WHERE id=? AND org_id=?", (provider_id, user.org_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Provider connection not found.")
    try:
        key = _cipher().decrypt(row["encrypted_secret"].encode()).decode()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Credential decryption failed; reconfigure the provider.")
    try:
        result = await _invoke(row["provider"], row["model"], key, body.prompt, body.system, body.max_tokens)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Model provider timed out.")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Model provider rejected the request (HTTP {exc.response.status_code}).")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not reach model provider.")
    with _db() as conn:
        conn.execute("UPDATE uc_provider_credentials SET status='healthy',updated_at=? WHERE id=?", (time.time(), provider_id))
    return {"provider_id": provider_id, **result, "execution_status": "completed"}
