"""
Dristik AI Connector Integration Store
Stores configured integrations, manages encrypted credentials, and provides active connector instances.
Credentials are persisted in SQLite and encrypted with AES-GCM.
The key is a hash of AUTH_SECRET. Older HMAC-keystream rows still decrypt.
"""
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.domain.models import Integration
from app.domain.enums import ConnectorType, ConnectorHealthStatus
from app.connectors.base.models import ConnectorCredentials
from app.connectors.base.interface import BaseConnector
from app.connectors.wordpress import WordPressConnector
from app.connectors.github import GitHubConnector
from app.connectors.shopify import ShopifyConnector
from app.connectors.webflow import WebflowConnector
from app.connectors.generic import GenericWebsiteConnector
from app.connectors.google.connector import GoogleSearchConsoleConnector


def _keystream(key: bytes, nonce: bytes, size: int) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < size:
        output.extend(hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    return bytes(output[:size])


def _secret_key() -> bytes:
    secret = (settings.AUTH_SECRET or "").encode("utf-8")
    return hashlib.sha256(secret).digest()


def _encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_secret_key()).encrypt(nonce, plaintext.encode("utf-8"), b"dristik-connector-v1")
    return "aesgcm:" + base64.b64encode(nonce + ciphertext).decode("ascii")


def _decrypt(payload: str) -> str:
    key = _secret_key()
    if payload.startswith("aesgcm:"):
        blob = base64.b64decode(payload[len("aesgcm:"):].encode("ascii"))
        nonce, ciphertext = blob[:12], blob[12:]
        return AESGCM(key).decrypt(nonce, ciphertext, b"dristik-connector-v1").decode("utf-8")
    blob = base64.b64decode(payload.encode("ascii"))
    nonce, cipher = blob[:16], blob[16:]
    raw = bytes(a ^ b for a, b in zip(cipher, _keystream(key, nonce, len(cipher))))
    return raw.decode("utf-8")

class ConnectorStore:
    def __init__(self):
        self._integrations: Dict[str, Integration] = {}
        self._credentials: Dict[str, ConnectorCredentials] = {}
        self._load()

    def _db_path(self) -> str:
        return settings.AUTH_DATABASE_PATH or "data/dristik.db"

    def _connect(self) -> sqlite3.Connection:
        path = self._db_path()
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS connector_integrations (
                integration_id TEXT PRIMARY KEY,
                integration_json TEXT NOT NULL,
                credentials_json TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS connector_audit_events (
                event_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                integration_id TEXT,
                actor_id TEXT,
                action TEXT NOT NULL,
                result TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_connector_audit_org_time ON connector_audit_events(org_id, created_at)")
        return conn

    def _load(self) -> None:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT integration_id, integration_json, credentials_json FROM connector_integrations"
                ).fetchall()
        except Exception:
            return
        for integration_id, integration_json, credentials_json in rows:
            try:
                integration = Integration.model_validate(json.loads(integration_json))
                credentials = ConnectorCredentials.model_validate(json.loads(_decrypt(credentials_json)))
            except Exception:
                continue
            self._integrations[integration_id] = integration
            self._credentials[integration_id] = credentials

    def _write(self, integration: Integration) -> None:
        credentials = self._credentials.get(integration.integration_id)
        if credentials is None:
            return
        payload = _encrypt(credentials.model_dump_json())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO connector_integrations (integration_id, integration_json, credentials_json)
                VALUES (?, ?, ?)
                ON CONFLICT(integration_id) DO UPDATE SET
                    integration_json = excluded.integration_json,
                    credentials_json = excluded.credentials_json
                """,
                (integration.integration_id, integration.model_dump_json(), payload),
            )
            conn.commit()

    def persist(self, integration: Integration) -> None:
        """Write the current integration row, including a status updated after a health check."""
        if integration.integration_id in self._integrations:
            self._integrations[integration.integration_id] = integration
            self._write(integration)

    def list_integrations(self, org_id: str = "org_default") -> List[Integration]:
        return [i for i in self._integrations.values() if i.org_id == org_id]

    def get_integration_for_org(self, integration_id: str, org_id: str) -> Optional[Integration]:
        """Resolve an integration only inside its tenant boundary."""
        integration = self._integrations.get(integration_id)
        if integration is None or integration.org_id != org_id:
            return None
        return integration

    def record_event(
        self, org_id: str, action: str, result: str,
        integration_id: Optional[str] = None, actor_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist lifecycle events. Callers must never pass credential values."""
        event_id = f"cevt_{uuid.uuid4().hex}"
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO connector_audit_events
                (event_id, org_id, integration_id, actor_id, action, result, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, org_id, integration_id, actor_id, action, result,
                 json.dumps(details or {}, sort_keys=True, default=str), created_at),
            )
            conn.commit()

    def list_events(self, org_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Return only audit events scoped to the requesting organization."""
        bounded_limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT event_id, integration_id, actor_id, action, result, details_json, created_at
                FROM connector_audit_events WHERE org_id = ? ORDER BY created_at DESC LIMIT ?""",
                (org_id, bounded_limit),
            ).fetchall()
        events = []
        for event_id, integration_id, actor_id, action, result, details_json, created_at in rows:
            try:
                details = json.loads(details_json)
            except (TypeError, ValueError):
                details = {}
            events.append({
                "event_id": event_id, "integration_id": integration_id, "actor_id": actor_id,
                "action": action, "result": result, "details": details, "created_at": created_at,
            })
        return events

    def get_integration(self, integration_id: str) -> Optional[Integration]:
        return self._integrations.get(integration_id)

    def add_integration(
        self,
        provider: ConnectorType,
        name: str,
        target_url: str,
        credentials: ConnectorCredentials,
        repository: Optional[str] = None,
        branch: Optional[str] = "main",
        org_id: str = "org_default",
        workspace_id: str = "ws_default",
        settings: Optional[Dict[str, Any]] = None
    ) -> Integration:
        integration_id = f"int_{provider.value}_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        # Zero-Fake Rule: Never initialize as CONNECTED before health verification passes
        integration = Integration(
            integration_id=integration_id,
            org_id=org_id,
            workspace_id=workspace_id,
            provider=provider,
            name=name,
            target_url=target_url,
            status=ConnectorHealthStatus.DISCONNECTED,
            scopes=credentials.scopes or ["read", "write_patches"],
            repository=repository,
            branch=branch,
            created_at=now,
            last_synced_at=now,
            settings=settings or {}
        )
        self._integrations[integration_id] = integration
        self._credentials[integration_id] = credentials
        try:
            self._write(integration)
        except Exception:
            pass
        return integration


    def update_credentials(self, integration_id: str, credentials: ConnectorCredentials) -> Optional[Integration]:
        """Replace encrypted credentials for an existing integration and persist atomically."""
        integration = self._integrations.get(integration_id)
        if integration is None:
            return None
        self._credentials[integration_id] = credentials
        integration.status = ConnectorHealthStatus.DISCONNECTED
        self._integrations[integration_id] = integration
        self._write(integration)
        return integration

    def delete_integration(self, integration_id: str) -> bool:
        if integration_id in self._integrations:
            del self._integrations[integration_id]
            self._credentials.pop(integration_id, None)
            try:
                with self._connect() as conn:
                    conn.execute("DELETE FROM connector_integrations WHERE integration_id = ?", (integration_id,))
                    conn.commit()
            except Exception:
                pass
            return True
        return False

    def get_connector(self, integration_id: str) -> Optional[BaseConnector]:
        integ = self.get_integration(integration_id)
        if not integ:
            return None
        creds = self._credentials.get(integration_id, ConnectorCredentials(provider=integ.provider, api_url=integ.target_url))
        
        if integ.provider == ConnectorType.WORDPRESS:
            return WordPressConnector(creds)
        elif integ.provider == ConnectorType.GITHUB:
            return GitHubConnector(creds)
        elif integ.provider == ConnectorType.SHOPIFY:
            return ShopifyConnector(creds)
        elif integ.provider == ConnectorType.WEBFLOW:
            return WebflowConnector(creds)
        elif integ.provider == ConnectorType.GOOGLE_SEARCH_CONSOLE:
            return GoogleSearchConsoleConnector(creds)
        elif integ.provider in (ConnectorType.GOOGLE_ANALYTICS_4, ConnectorType.GOOGLE_ANALYTICS):
            from app.connectors.google.ga4_connector import GoogleAnalytics4Connector
            return GoogleAnalytics4Connector(creds)
        elif integ.provider == ConnectorType.CRM:
            from app.connectors.crm.connector import CrmRevenueConnector
            return CrmRevenueConnector(creds)
        elif integ.provider == ConnectorType.DATAFORSEO:
            from app.connectors.dataforseo.connector import DataForSeoConnector
            return DataForSeoConnector(creds)
        elif integ.provider == ConnectorType.LIVE_AI_SEARCH:
            from app.connectors.ai_search.connector import LiveAiSearchConnector
            return LiveAiSearchConnector(creds)
        elif integ.provider == ConnectorType.CRUX:
            from app.connectors.crux.connector import CruxConnector
            return CruxConnector(creds)
        elif integ.provider in (
            ConnectorType.FRAMER, ConnectorType.WIX, ConnectorType.SANITY,
            ConnectorType.OPENAI_SEARCH, ConnectorType.PERPLEXITY, ConnectorType.CLAUDE,
            ConnectorType.GEMINI, ConnectorType.LINKEDIN, ConnectorType.X,
            ConnectorType.TIKTOK, ConnectorType.INSTAGRAM, ConnectorType.WHATSAPP_BUSINESS,
            ConnectorType.TELEGRAM, ConnectorType.SLACK, ConnectorType.HUBSPOT,
            ConnectorType.SALESFORCE, ConnectorType.STRIPE,
        ):
            from app.connectors.provider_api import ProviderApiConnector
            return ProviderApiConnector(creds)
        else:
            return GenericWebsiteConnector(creds)

    def get_telemetry_service(self) -> Any:
        from app.connectors.telemetry_service import ExternalTelemetryService
        from app.connectors.google.connector import GoogleSearchConsoleConnector
        from app.connectors.google.ga4_connector import GoogleAnalytics4Connector
        from app.connectors.crux.connector import CruxConnector
        from app.connectors.external_seo.connector import ExternalSeoConnector

        gsc = None
        ga4 = None
        crux = None
        seo = None

        for integ_id, integ in self._integrations.items():
            creds = self._credentials.get(integ_id, ConnectorCredentials(provider=integ.provider))
            if integ.provider == ConnectorType.GOOGLE_SEARCH_CONSOLE and not gsc:
                gsc = GoogleSearchConsoleConnector(creds)
            elif integ.provider in (ConnectorType.GOOGLE_ANALYTICS_4, ConnectorType.GOOGLE_ANALYTICS) and not ga4:
                ga4 = GoogleAnalytics4Connector(creds)
            elif integ.provider == ConnectorType.CRUX and not crux:
                crux = CruxConnector(creds)
            elif integ.provider == ConnectorType.DATAFORSEO and not seo:
                seo = ExternalSeoConnector(creds)

        return ExternalTelemetryService(gsc=gsc, ga4=ga4, crux=crux, external_seo=seo)

connector_store = ConnectorStore()
