"""Durable, idempotent history for completed AEO measurement scorecards.

This store is intentionally separate from the live GEO/AEO answer-engine pipeline
store: content/technical readiness and empirical AI visibility are different metrics.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _data_dir() -> str:
    cursor = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.basename(cursor) == "app":
            return os.path.join(os.path.dirname(cursor), "data")
        parent = os.path.dirname(cursor)
        if parent == cursor:
            break
        cursor = parent
    raise RuntimeError("could not locate backend/app from AEO analytics history store")


DB_PATH = os.path.join(_data_dir(), "aeo_analytics_history.db")


class AeoAnalyticsHistoryStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS aeo_analytics_snapshots (
                    analysis_id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    formula_version TEXT NOT NULL,
                    scorecard_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_aeo_history_domain_time
                ON aeo_analytics_snapshots(domain, captured_at ASC)
            """)
            conn.commit()

    @staticmethod
    def _clean_domain(domain: Optional[str]) -> str:
        value = (domain or "").strip().lower()
        value = value.removeprefix("https://").removeprefix("http://")
        return value.split("/")[0].removeprefix("www.")

    def record_snapshot(
        self,
        analysis_id: str,
        domain: Optional[str],
        scorecard: Dict[str, Any],
        captured_at: Optional[str] = None,
        formula_version: str = "aeo-four-pillars-v1",
    ) -> bool:
        """Insert one snapshot per completed analysis; repeated calls are safe."""
        clean_domain = self._clean_domain(domain)
        if not analysis_id or not clean_domain:
            return False
        timestamp = captured_at or datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO aeo_analytics_snapshots
                    (analysis_id, domain, captured_at, formula_version, scorecard_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                analysis_id,
                clean_domain,
                timestamp,
                formula_version,
                json.dumps(scorecard, separators=(",", ":"), sort_keys=True),
            ))
            conn.commit()
            return cursor.rowcount == 1

    def get_domain_history(self, domain: str, limit: int = 100) -> List[Dict[str, Any]]:
        clean_domain = self._clean_domain(domain)
        bounded_limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT analysis_id, domain, captured_at, formula_version, scorecard_json
                FROM aeo_analytics_snapshots
                WHERE domain = ?
                ORDER BY captured_at ASC, analysis_id ASC
                LIMIT ?
            """, (clean_domain, bounded_limit)).fetchall()
        return [
            {
                "analysis_id": row["analysis_id"],
                "domain": row["domain"],
                "captured_at": row["captured_at"],
                "formula_version": row["formula_version"],
                "scorecard": json.loads(row["scorecard_json"]),
            }
            for row in rows
        ]


aeo_analytics_history_store = AeoAnalyticsHistoryStore()
