"""Durable tenant-scoped recurring SEO audit schedules."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class RecurringAuditStore:
    """SQLite-backed schedule registry with tenant scoping and dispatch leases."""

    def __init__(self, database_path: Optional[str] = None):
        if database_path is None:
            from app.core.config import settings
            database_path = settings.AUTH_DATABASE_PATH
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS recurring_audit_schedules (
                    schedule_id TEXT PRIMARY KEY, org_id TEXT NOT NULL, created_by TEXT NOT NULL,
                    website_url TEXT NOT NULL, cadence_days INTEGER NOT NULL, max_pages INTEGER NOT NULL,
                    target_pillars_json TEXT NOT NULL DEFAULT '[]', site_type TEXT, country TEXT, language TEXT,
                    status TEXT NOT NULL DEFAULT 'ACTIVE', next_run_at TEXT NOT NULL, lease_until TEXT,
                    last_run_at TEXT, last_analysis_id TEXT, last_error TEXT, run_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_recurring_audits_due ON recurring_audit_schedules(status, next_run_at)")

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        return db

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["target_pillars"] = json.loads(item.pop("target_pillars_json") or "[]")
        item.pop("lease_until", None)
        return item

    def create(self, *, org_id: str, created_by: str, website_url: str, cadence_days: int, max_pages: int, target_pillars: Optional[list[str]] = None, site_type: Optional[str] = None, country: Optional[str] = None, language: Optional[str] = None) -> dict[str, Any]:
        if cadence_days not in {7, 30}:
            raise ValueError("cadence_days must be 7 or 30")
        if not org_id or not created_by:
            raise ValueError("org_id and created_by are required")
        now = _now()
        schedule_id = "ras_" + uuid.uuid4().hex
        with self._connect() as db:
            db.execute(
                """INSERT INTO recurring_audit_schedules
                (schedule_id, org_id, created_by, website_url, cadence_days, max_pages, target_pillars_json, site_type, country, language, status, next_run_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)""",
                (schedule_id, org_id, created_by, website_url, cadence_days, max_pages, json.dumps(target_pillars or []), site_type, country, language, _iso(now + timedelta(days=cadence_days)), _iso(now), _iso(now)),
            )
            row = db.execute("SELECT * FROM recurring_audit_schedules WHERE schedule_id=?", (schedule_id,)).fetchone()
            return self._public(row)

    def list_for_org(self, org_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM recurring_audit_schedules WHERE org_id=? ORDER BY created_at DESC LIMIT ?", (org_id, max(1, min(limit, 250)))).fetchall()
        return [self._public(row) for row in rows]

    def cancel(self, schedule_id: str, org_id: str) -> bool:
        now = _iso(_now())
        with self._connect() as db:
            cur = db.execute("UPDATE recurring_audit_schedules SET status='CANCELLED', lease_until=NULL, updated_at=? WHERE schedule_id=? AND org_id=? AND status!='CANCELLED'", (now, schedule_id, org_id))
            return cur.rowcount == 1

    def pause(self, schedule_id: str, reason: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE recurring_audit_schedules SET status='PAUSED', lease_until=NULL, last_error=?, updated_at=? WHERE schedule_id=?", (reason[:500], _iso(_now()), schedule_id))

    def claim_due(self, limit: int = 10, lease_minutes: int = 10) -> list[dict[str, Any]]:
        now = _now()
        now_s = _iso(now)
        lease_s = _iso(now + timedelta(minutes=lease_minutes))
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT * FROM recurring_audit_schedules WHERE (status='ACTIVE' AND next_run_at<=?) OR (status='DISPATCHING' AND lease_until<=?) ORDER BY next_run_at LIMIT ?",
                (now_s, now_s, max(1, min(limit, 100))),
            ).fetchall()
            claimed = []
            for row in rows:
                cur = db.execute("UPDATE recurring_audit_schedules SET status='DISPATCHING', lease_until=?, updated_at=? WHERE schedule_id=? AND status IN ('ACTIVE','DISPATCHING')", (lease_s, now_s, row["schedule_id"]))
                if cur.rowcount:
                    fresh = db.execute("SELECT * FROM recurring_audit_schedules WHERE schedule_id=?", (row["schedule_id"],)).fetchone()
                    claimed.append(self._public(fresh))
            db.commit()
        return claimed

    def mark_dispatched(self, schedule_id: str, analysis_id: str) -> None:
        now = _now()
        with self._connect() as db:
            row = db.execute("SELECT cadence_days FROM recurring_audit_schedules WHERE schedule_id=?", (schedule_id,)).fetchone()
            if not row:
                return
            db.execute(
                "UPDATE recurring_audit_schedules SET status='ACTIVE', lease_until=NULL, next_run_at=?, last_run_at=?, last_analysis_id=?, last_error=NULL, run_count=run_count+1, updated_at=? WHERE schedule_id=?",
                (_iso(now + timedelta(days=int(row["cadence_days"]))), _iso(now), analysis_id, _iso(now), schedule_id),
            )

    def mark_dispatch_failed(self, schedule_id: str, error: str, retry_minutes: int = 15) -> None:
        now = _now()
        with self._connect() as db:
            db.execute(
                "UPDATE recurring_audit_schedules SET status='ACTIVE', lease_until=NULL, next_run_at=?, last_error=?, updated_at=? WHERE schedule_id=?",
                (_iso(now + timedelta(minutes=retry_minutes)), str(error)[:500], _iso(now), schedule_id),
            )


_store: Optional[RecurringAuditStore] = None


def get_recurring_audit_store() -> RecurringAuditStore:
    global _store
    if _store is None:
        _store = RecurringAuditStore()
    return _store
