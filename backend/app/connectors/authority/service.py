"""Connection management, collection, cache, and reporting.

Collection is explicit. Reading a report never calls a provider.
A provider error is recorded on that provider and does not raise into the audit.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.connectors.authority.analyze import build_report
from app.connectors.authority.http import HttpxTransport, ProviderAuthError, ProviderRateLimitError, ProviderTransientError
from app.connectors.authority.models import CollectionResult, isoformat, period_window, utcnow
from app.connectors.authority.redact import install_log_redaction
from app.connectors.authority.registry import JOB_PROVIDERS, all_providers, get_provider
from app.connectors.authority.store import ExternalStore, datetime_from_iso

logger = logging.getLogger("app.external_authority")

_TIER_RANK = {"FREE": 0, "STANDARD": 1, "ADVANCED": 2}
_SERVICE: Optional["ExternalAuthorityService"] = None


def _connector_freshness(*, connection_status: str, last_success_at: Optional[str], next_sync_at: Optional[str], now) -> tuple[str, Optional[int]]:
    """Classify freshness from recorded sync scheduling without inventing an SLA."""
    if connection_status != "CONNECTED":
        return "NOT_CONNECTED", None
    if not last_success_at:
        return "UNKNOWN", None
    try:
        last_success = datetime_from_iso(last_success_at)
        if last_success.tzinfo is None:
            last_success = last_success.replace(tzinfo=now.tzinfo)
        age_seconds = max(0, int((now - last_success).total_seconds()))
    except (TypeError, ValueError, AttributeError):
        return "UNKNOWN", None
    if not next_sync_at:
        return "UNKNOWN", age_seconds
    try:
        next_sync = datetime_from_iso(next_sync_at)
        if next_sync.tzinfo is None:
            next_sync = next_sync.replace(tzinfo=now.tzinfo)
    except (TypeError, ValueError, AttributeError):
        return "UNKNOWN", age_seconds
    return ("STALE" if next_sync <= now else "FRESH"), age_seconds

class ExternalAuthorityService:
    def __init__(self, store: Optional[ExternalStore] = None, transport: Any = None, clock=None):
        install_log_redaction()
        self.store = store or ExternalStore()
        self.transport = transport or HttpxTransport()
        self.clock = clock or utcnow

    def now(self):
        return self.clock()

    def providers(self) -> List[Dict[str, Any]]:
        catalog = []
        for provider in all_providers():
            catalog.append({
                "provider": provider.provider_id,
                "display_name": provider.display_name,
                "enabled": provider.enabled(),
                "auth_mode": provider.current_auth_mode(),
                "oauth_ready": provider.oauth_application_ready(),
                "api_key_fallback": provider.current_auth_mode() == "api_key" or provider.provider_id in {"ahrefs", "semrush", "majestic", "dataforseo", "serpapi", "citations", "brand_mentions"},
                "tier": provider.collection_tier,
                "scopes": list(provider.scopes),
                "capabilities": provider.capabilities.model_dump(),
            })
        return catalog

    def coverage(self, project_id: str, domain: str, period_days: int = 28) -> Dict[str, Any]:
        report = self.report(project_id, domain, period_days)
        return {"domain": domain, "period_days": period_days, "matrix": report["coverage"], "sources": report["data_sources"]}

    def health(self, project_id: str) -> List[Dict[str, Any]]:
        connections = {row["provider"]: row for row in self.store.public_connections(project_id)}
        rows = []
        for provider in all_providers():
            connection = connections.get(provider.provider_id)
            credential_source = (connection or {}).get("credential_source")
            if connection is None and provider.application_credentials():
                connection = {
                    "status": "CONNECTED",
                    "credential_source": "application",
                    "token_status": "application",
                    "account_label": "Application credential",
                }
                credential_source = "application"
            status = connection.get("status") if connection else "NOT_CONNECTED"
            token_status = (connection or {}).get("token_status") or "missing"
            if status == "CONNECTED" and token_status == "valid":
                health = "Healthy"
            elif status == "CONNECTED" and token_status in {"expired", "unreadable"}:
                health = "Reconnect required"
            elif status == "NOT_CONNECTED":
                health = "Not connected"
            else:
                health = status
            last_success = (connection or {}).get("last_success_at")
            next_sync = (connection or {}).get("next_sync_at")
            freshness_status, freshness_age_seconds = _connector_freshness(
                connection_status=status,
                last_success_at=last_success,
                next_sync_at=next_sync,
                now=self.now(),
            )
            rows.append({
                "provider": provider.display_name,
                "provider_id": provider.provider_id,
                "connection_status": status,
                "account": (connection or {}).get("account_label"),
                "property": (connection or {}).get("property_label") or (connection or {}).get("property_id"),
                "last_successful_sync": last_success,
                "last_attempted_sync": (connection or {}).get("last_attempt_at"),
                "next_sync": next_sync,
                "freshness_status": freshness_status,
                "freshness_age_seconds": freshness_age_seconds,
                "token_status": token_status,
                "quota_status": (connection or {}).get("quota_status"),
                "error_message": (connection or {}).get("last_error"),
                "capabilities": [name for name, enabled in provider.capabilities.model_dump().items() if enabled],
                "status": health,
                "credential_source": credential_source,
                "enabled": provider.enabled(),
            })
        return rows

    def start_oauth(self, project_id: str, provider_id: str, domain: Optional[str] = None) -> Dict[str, str]:
        provider = get_provider(provider_id)
        if provider.current_auth_mode() != "oauth":
            raise ValueError(f"{provider.display_name} does not use OAuth. Connect with an API key.")
        if not provider.oauth_application_ready():
            raise ValueError(f"{provider.display_name} OAuth is not configured on this Dristik instance.")
        state = secrets.token_urlsafe(24)
        authorize_url, verifier = provider.build_authorize(state)
        from app.core.config import settings
        expires = isoformat(self.now() + timedelta(seconds=int(settings.OAUTH_STATE_TTL_SECONDS)))
        self.store.save_oauth_state(state, project_id, provider_id, _domain(domain) if domain else None, {"code_verifier": verifier}, expires)
        return {"authorize_url": authorize_url, "provider": provider_id}

    def finish_oauth(self, code: str, state: str) -> Dict[str, Any]:
        payload = self.store.consume_oauth_state(state, isoformat(self.now()))
        if not payload:
            raise ValueError("OAuth state is invalid or expired.")
        provider = get_provider(payload["provider"])
        secret = provider.authenticate({"code": code, "code_verifier": payload.get("code_verifier")}, self.transport)
        self.store.upsert_connection({
            "project_id": payload["project_id"],
            "provider": provider.provider_id,
            "status": "CONNECTED",
            "auth_mode": "oauth",
            "domain": payload.get("domain"),
            "scopes": provider.scopes,
            "token_status": "valid",
            "token_expires_at": secret.get("expires_at"),
            "capabilities": provider.capabilities.model_dump(),
            "collection_tier": provider.collection_tier,
            "credential_source": "account",
            "last_error": None,
        }, secret=secret)
        logger.info("oauth connected provider=%s", provider.provider_id)
        return {"provider": provider.provider_id, "status": "CONNECTED", "project_id": payload["project_id"]}

    def connect_api_key(self, project_id: str, provider_id: str, secret: Dict[str, Any], domain: Optional[str] = None) -> Dict[str, Any]:
        provider = get_provider(provider_id)
        if not provider.enabled():
            raise ValueError(f"{provider.display_name} is disabled.")
        if provider.current_auth_mode() == "oauth" and provider.provider_id not in {"ahrefs", "semrush"}:
            raise ValueError(f"{provider.display_name} uses OAuth. Use the Connect button.")
        stored = provider.authenticate(secret, self.transport)
        self.store.upsert_connection({
            "project_id": project_id,
            "provider": provider.provider_id,
            "status": "CONNECTED",
            "auth_mode": provider.current_auth_mode() if provider.provider_id not in {"ahrefs", "semrush"} else "api_key",
            "domain": _domain(domain) if domain else None,
            "scopes": [],
            "token_status": "valid",
            "capabilities": provider.capabilities.model_dump(),
            "collection_tier": provider.collection_tier,
            "credential_source": "account",
            "last_error": None,
        }, secret=stored)
        logger.info("api credential stored provider=%s", provider.provider_id)
        return {"provider": provider.provider_id, "status": "CONNECTED"}

    def disconnect(self, project_id: str, provider_id: str) -> Dict[str, str]:
        provider = get_provider(provider_id)
        secret = self.store.load_secret(project_id, provider_id)
        if secret:
            try:
                provider.disconnect(secret, self.transport)
            except Exception:
                logger.info("provider revocation failed provider=%s", provider_id)
        self.store.clear_secret(project_id, provider_id)
        return {"provider": provider_id, "status": "DISCONNECTED"}

    def select_property(self, project_id: str, provider_id: str, property_id: str, label: Optional[str] = None) -> Dict[str, str]:
        self.store.mark_connection(
            project_id,
            provider_id,
            property_id=property_id,
            property_label=label or property_id,
        )
        return {"provider": provider_id, "property_id": property_id}

    def save_brand(self, project_id: str, name: str, aliases: List[str]) -> Dict[str, Any]:
        payload = {"name": name, "aliases": [alias for alias in aliases if alias]}
        self.store.save_profile(project_id, "brand", payload)
        return payload

    def save_competitors(self, project_id: str, competitors: List[Dict[str, str]]) -> Dict[str, Any]:
        cleaned = []
        for item in competitors:
            domain = _domain(item.get("domain") or "")
            if domain:
                cleaned.append({"name": item.get("name") or domain, "domain": domain})
        payload = {"competitors": cleaned}
        self.store.save_profile(project_id, "competitors", payload)
        return payload

    def save_local_business(self, project_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        applicability = profile.get("applicability") or "UNKNOWN"
        if applicability not in {"LOCAL_BUSINESS", "NON_LOCAL_BUSINESS", "UNKNOWN"}:
            raise ValueError("applicability must be LOCAL_BUSINESS, NON_LOCAL_BUSINESS, or UNKNOWN.")
        payload = {
            "applicability": applicability,
            "name": profile.get("name") or "",
            "address": profile.get("address") or "",
            "phone": profile.get("phone") or "",
            "website": profile.get("website") or "",
            "category": profile.get("category") or "",
            "expected_directories": profile.get("expected_directories") or [],
        }
        self.store.save_profile(project_id, "local_business", payload)
        return payload

    def collect_provider(
        self,
        project_id: str,
        provider_id: str,
        domain: str,
        period_days: int = 28,
        *,
        force: bool = False,
        mode: str = "default",
    ) -> Dict[str, Any]:
        provider = get_provider(provider_id)
        domain = _domain(domain)
        if not provider.enabled():
            return {"provider": provider_id, "data_state": "NOT_CONNECTED", "note": "Provider disabled."}
        ctx = self._context(project_id, provider, domain, period_days, mode)
        if not _has_credentials(ctx) and provider.provider_id != "google_business_profile":
            return {"provider": provider_id, "data_state": "NOT_CONNECTED", "note": f"{provider.display_name} is not connected."}
        if provider.provider_id == "google_business_profile" and ctx.applicability == "NON_LOCAL_BUSINESS":
            result = provider.collect(ctx)
            return self._persist(project_id, provider, domain, period_days, mode, result)
        key = f"{project_id}|{provider_id}|{domain}|{period_days}|{ctx.period_end}|{mode}"
        if not force:
            fresh = self.store.fresh_snapshot(key, _refresh_hours(provider.collection_tier), isoformat(self.now()))
            if fresh:
                logger.info("cache hit provider=%s domain=%s period=%s", provider_id, domain, period_days)
                return {"provider": provider_id, "data_state": fresh["data_state"], "cached": True, "snapshot_id": fresh["snapshot_id"]}
        self.store.mark_connection(project_id, provider_id, last_attempt_at=isoformat(self.now()))
        result = provider.collect(ctx)
        return self._persist(project_id, provider, domain, period_days, mode, result)

    def enqueue(self, project_id: str, domain: str, job_types: Optional[List[str]] = None, periods: Optional[List[int]] = None, *, force: bool = False, automatic: bool = False) -> List[Dict[str, Any]]:
        domain = _domain(domain)
        kinds = job_types or list(JOB_PROVIDERS)
        windows = periods or [28]
        created = []
        for kind in kinds:
            if kind not in JOB_PROVIDERS:
                continue
            if automatic and not _job_allowed(kind):
                continue
            for period in windows:
                if period not in {7, 28, 90, 365}:
                    continue
                created.append(self.store.enqueue_job({
                    "project_id": project_id,
                    "domain": domain,
                    "job_type": kind,
                    "period_days": period,
                    "idempotency_key": f"{project_id}|{kind}|{domain}|{period}|{self.now().date().isoformat()}",
                    "force": force,
                    "next_run_at": isoformat(self.now()),
                }))
        return created

    def run_due_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        outcomes = []
        for job in self.store.claim_due_jobs(isoformat(self.now()), limit=limit):
            outcomes.append(self.execute_job(job))
        return outcomes

    def execute_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        providers = JOB_PROVIDERS.get(job["job_type"], [])
        if job.get("provider"):
            providers = [job["provider"]]
        results = []
        retryable = False
        retry_after = None
        for provider_id in providers:
            mode = "serp" if job["job_type"] == "sync_serp" else "backlinks" if provider_id == "dataforseo" and job["job_type"] == "sync_backlinks" else "default"
            try:
                outcome = self.collect_provider(
                    job["project_id"], provider_id, job.get("domain") or "", int(job.get("period_days") or 28), mode=mode,
                )
                results.append({"provider": provider_id, "ok": True, **outcome})
            except ProviderRateLimitError as exc:
                retryable = True
                retry_after = exc.retry_after
                results.append({"provider": provider_id, "ok": False, "error": "rate_limited"})
                logger.info("rate limited provider=%s", provider_id)
            except ProviderAuthError:
                self.store.mark_connection(job["project_id"], provider_id, token_status="expired", last_error="credential expired or rejected")
                results.append({"provider": provider_id, "ok": False, "error": "credentials_expired"})
                logger.info("credentials rejected provider=%s", provider_id)
            except ProviderTransientError:
                retryable = True
                results.append({"provider": provider_id, "ok": False, "error": "transient"})
            except Exception:
                results.append({"provider": provider_id, "ok": False, "error": "provider_failed"})
                logger.info("provider sync failed provider=%s", provider_id)
        failures = [item for item in results if not item["ok"]]
        if retryable and int(job.get("attempt") or 1) < int(job.get("max_attempts") or 4):
            delay = retry_after or min(3600, 2 ** int(job.get("attempt") or 1))
            next_run = isoformat(self.now() + timedelta(seconds=delay))
            self.store.finish_job(job["job_id"], "queued", {"providers": results}, error="retry scheduled", next_run_at=next_run)
            return {"job_id": job["job_id"], "status": "queued", "providers": results}
        if not failures:
            status = "succeeded"
        elif len(failures) < len(results):
            status = "partial"
        else:
            status = "failed"
        self.store.finish_job(job["job_id"], status, {"providers": results}, error=None if status == "succeeded" else "one or more providers did not complete")
        return {"job_id": job["job_id"], "status": status, "providers": results}

    def report(self, project_id: str, domain: str, period_days: int = 28, crawl_observations: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        domain = _domain(domain) if domain else domain
        connections = self.store.public_connections(project_id)
        snapshots: Dict[str, Dict[str, Any]] = {}
        records: Dict[str, list] = {}
        for provider in all_providers():
            if not domain:
                continue
            snapshot = self.store.latest_snapshot(project_id, provider.provider_id, domain, period_days)
            if snapshot:
                snapshots[provider.provider_id] = snapshot
                records[provider.provider_id] = self.store.records_for_snapshot(snapshot["snapshot_id"])
        brand = self.store.get_profile(project_id, "brand")
        local_profile = self.store.get_profile(project_id, "local_business")
        competitors = (self.store.get_profile(project_id, "competitors").get("competitors") or [])
        competitor_records: Dict[str, list] = {}
        for competitor in competitors:
            rows = []
            for provider in all_providers():
                snapshot = self.store.latest_snapshot(project_id, provider.provider_id, competitor["domain"], period_days)
                if snapshot:
                    rows.extend(self.store.records_for_snapshot(snapshot["snapshot_id"]))
            competitor_records[competitor["domain"]] = rows
        history = self.store.snapshot_history(project_id, domain, period_days) if domain else []
        return build_report(
            project_id=project_id,
            domain=domain,
            period_days=period_days,
            connections=connections,
            snapshots=snapshots,
            records_by_provider=records,
            history=history,
            brand=brand,
            competitors=competitors,
            local_profile=local_profile,
            crawl_observations=crawl_observations,
            competitor_records=competitor_records,
        )

    def _persist(self, project_id, provider, domain, period_days, mode, result: CollectionResult) -> Dict[str, Any]:
        ctx_end = period_window(period_days, self.now())[1]
        key = f"{project_id}|{provider.provider_id}|{domain}|{period_days}|{ctx_end}|{mode}"
        totals = {}
        for row in result.records:
            if row.value is not None and (row.metadata or {}).get("comparison", "current") == "current":
                if row.metric not in totals:
                    totals[row.metric] = row.value
        snapshot_id = self.store.save_snapshot(
            project_id=project_id,
            provider=provider.provider_id,
            domain=domain,
            period_days=period_days,
            period_start=period_window(period_days, self.now())[0],
            period_end=ctx_end,
            data_state=result.data_state,
            summary={"note": result.note, "partial_errors": result.partial_errors, "totals": totals, "mode": mode},
            idempotency_key=key,
            records=result.records,
            raw_payloads=result.raw_payloads,
            collected_at=isoformat(self.now()),
        )
        self.store.save_catalog(project_id, provider.provider_id, result.accounts, result.properties)
        if result.data_state in {"MEASURED", "PARTIALLY_MEASURED"}:
            self.store.mark_connection(
                project_id,
                provider.provider_id,
                status="CONNECTED",
                last_success_at=isoformat(self.now()),
                last_error=None,
                quota_status=result.quota_status,
                next_sync_at=isoformat(self.now() + timedelta(hours=_refresh_hours(provider.collection_tier))),
            )
        elif result.error:
            self.store.mark_connection(project_id, provider.provider_id, last_error=result.error[:300])
        logger.info("collected provider=%s domain=%s state=%s", provider.provider_id, domain, result.data_state)
        return {
            "provider": provider.provider_id,
            "data_state": result.data_state,
            "cached": False,
            "snapshot_id": snapshot_id,
            "note": result.note,
            "partial_errors": result.partial_errors,
            "records": len(result.records),
        }

    def _context(self, project_id: str, provider, domain: str, period_days: int, mode: str):
        from app.connectors.authority.providers.base import CollectContext
        from app.core.config import settings
        secret = self.store.load_secret(project_id, provider.provider_id) or {}
        if secret and secret.get("expires_at") and settings.OAUTH_TOKEN_REFRESH_ENABLED and secret.get("refresh_token"):
            expires = datetime_from_iso(secret["expires_at"])
            if expires <= self.now() + timedelta(seconds=120):
                secret = provider.refresh_credentials(secret, self.transport)
                self.store.replace_secret(project_id, provider.provider_id, secret, token_expires_at=secret.get("expires_at"), token_status="valid")
        if not secret:
            secret = provider.application_credentials() or {}
        if provider.provider_id in {"citations", "brand_mentions"} and not secret.get("login"):
            borrowed = self.store.load_secret(project_id, "dataforseo") or get_provider("dataforseo").application_credentials() or {}
            secret = {**borrowed, **secret}
        connection = self.store.get_public_connection(project_id, provider.provider_id) or {}
        local_profile = self.store.get_profile(project_id, "local_business")
        brand = self.store.get_profile(project_id, "brand")
        start, end, previous_start, previous_end = period_window(period_days, self.now())
        terms = [item for item in [brand.get("name"), *(brand.get("aliases") or [])] if item]
        return CollectContext(
            project_id=project_id,
            provider_id=provider.provider_id,
            domain=domain,
            period_days=period_days,
            property_id=connection.get("property_id"),
            access_token=secret.get("access_token"),
            api_key=secret.get("api_key"),
            login=secret.get("login"),
            password=secret.get("password"),
            brand_terms=terms,
            transport=self.transport,
            now=self.now(),
            mode=mode,
            period_start=start,
            period_end=end,
            previous_start=previous_start,
            previous_end=previous_end,
            external_account_id=connection.get("external_account_id"),
            applicability=local_profile.get("applicability") or "UNKNOWN",
        )


def _has_credentials(ctx) -> bool:
    return bool(ctx.access_token or ctx.api_key or (ctx.login and ctx.password))


def _domain(value: str) -> str:
    raw = (value or "").strip().lower()
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    return raw.split("/")[0].split("?")[0].removeprefix("www.")


def _refresh_hours(tier: str) -> int:
    from app.core.config import settings
    if tier == "ADVANCED":
        return int(settings.EXTERNAL_SYNC_REFRESH_HOURS_ADVANCED)
    if tier == "STANDARD":
        return int(settings.EXTERNAL_SYNC_REFRESH_HOURS_STANDARD)
    return int(settings.EXTERNAL_SYNC_REFRESH_HOURS_FREE)


def _job_allowed(job_type: str) -> bool:
    from app.core.config import settings
    plan = _TIER_RANK.get(str(settings.EXTERNAL_COLLECTION_PLAN).upper(), 1)
    for provider_id in JOB_PROVIDERS.get(job_type, []):
        provider = get_provider(provider_id)
        if _TIER_RANK.get(provider.collection_tier, 2) <= plan and provider.enabled():
            return True
    return False


def get_service() -> ExternalAuthorityService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ExternalAuthorityService()
    return _SERVICE


def reset_service() -> None:
    global _SERVICE
    _SERVICE = None
