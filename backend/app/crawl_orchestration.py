"""Persistent, bounded deep-crawl primitives.

The five-page Quick Scan remains a separate workflow. These primitives provide
URL normalization, same-origin scope enforcement, and durable URL/job accounting
for a resumable deep crawl. Fetching/rendering is performed by the worker layer.
"""
from __future__ import annotations

import ipaddress
import socket
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_url(raw_url: str, base_url: str | None = None) -> str | None:
    """Normalize a web URL; drop fragments and common tracking parameters."""
    candidate = urljoin(base_url, raw_url) if base_url else raw_url
    try:
        parts = urlsplit(candidate.strip())
        scheme = parts.scheme.lower()
        host = (parts.hostname or "").lower().rstrip(".")
        if scheme not in {"http", "https"} or not host or parts.username or parts.password:
            return None
        port = parts.port
        if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
            netloc = f"{host}:{port}"
        else:
            netloc = host
        path = parts.path or "/"
        if path != "/":
            path = path.rstrip("/") or "/"
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_KEYS]
        query.sort()
        return urlunsplit((scheme, netloc, path, urlencode(query, doseq=True), ""))
    except (ValueError, UnicodeError):
        return None


def is_public_http_target(url: str) -> bool:
    """Reject private, loopback, link-local, reserved and unresolved targets.

    Call immediately before every outbound request. This DNS preflight is a
    defense-in-depth check; production deployments should also enforce egress
    policy at the network layer to mitigate DNS rebinding between check and use.
    """
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return False
        addresses = {
            ipaddress.ip_address(item[4][0].split("%", 1)[0])
            for item in socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme.lower() == "https" else 80), type=socket.SOCK_STREAM)
        }
        return bool(addresses) and all(address.is_global for address in addresses)
    except (OSError, ValueError, TypeError):
        return False


def is_same_origin(url: str, origin_url: str) -> bool:
    target, origin = urlsplit(url), urlsplit(origin_url)
    return (
        target.scheme.lower() in {"http", "https"}
        and target.scheme.lower() == origin.scheme.lower()
        and (target.hostname or "").lower().rstrip(".") == (origin.hostname or "").lower().rstrip(".")
        and (target.port or (443 if target.scheme == "https" else 80))
            == (origin.port or (443 if origin.scheme == "https" else 80))
    )


class DeepCrawlStore:
    """SQLite-backed crawl jobs and deduplicated URL state."""

    def __init__(self, database_path: str):
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS deep_crawl_jobs (
                    job_id TEXT PRIMARY KEY, org_id TEXT NOT NULL, origin_url TEXT NOT NULL,
                    status TEXT NOT NULL, max_pages INTEGER NOT NULL, max_depth INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS deep_crawl_urls (
                    job_id TEXT NOT NULL, normalized_url TEXT NOT NULL, depth INTEGER NOT NULL,
                    status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, http_status INTEGER,
                    final_url TEXT, error_code TEXT, discovered_from TEXT, updated_at TEXT NOT NULL,
                    PRIMARY KEY(job_id, normalized_url),
                    FOREIGN KEY(job_id) REFERENCES deep_crawl_jobs(job_id)
                );
                CREATE INDEX IF NOT EXISTS idx_deep_crawl_urls_status ON deep_crawl_urls(job_id, status, depth);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def create_job(self, job_id: str, org_id: str, origin_url: str, max_pages: int = 1000, max_depth: int = 8) -> dict[str, Any]:
        origin = normalize_url(origin_url)
        if not origin or not org_id.strip() or not job_id.strip():
            raise ValueError("job ID, organization ID, and a valid HTTP(S) origin are required")
        if not 1 <= max_pages <= 100000 or not 0 <= max_depth <= 100:
            raise ValueError("crawl limits are outside the allowed range")
        now = utc_now()
        with self._connect() as db:
            db.execute(
                "INSERT INTO deep_crawl_jobs(job_id,org_id,origin_url,status,max_pages,max_depth,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (job_id, org_id, origin, "QUEUED", max_pages, max_depth, now, now),
            )
            self._enqueue(db, job_id, origin, 0, None)
        return self.get_job(job_id, org_id)

    def _enqueue(self, db: sqlite3.Connection, job_id: str, url: str, depth: int, discovered_from: str | None) -> bool:
        db.execute(
            "INSERT OR IGNORE INTO deep_crawl_urls(job_id,normalized_url,depth,status,discovered_from,updated_at) VALUES(?,?,?,?,?,?)",
            (job_id, url, depth, "DISCOVERED", discovered_from, utc_now()),
        )
        return db.execute("SELECT changes()").fetchone()[0] == 1

    def enqueue_discovered(self, job_id: str, org_id: str, urls: list[str], parent_url: str, parent_depth: int) -> dict[str, int]:
        parent = normalize_url(parent_url)
        if parent is None:
            raise ValueError("invalid parent URL")
        inserted = excluded = 0
        with self._connect() as db:
            job = db.execute("SELECT * FROM deep_crawl_jobs WHERE job_id=? AND org_id=?", (job_id, org_id)).fetchone()
            if not job:
                raise KeyError("crawl job not found for organization")
            if job["cancel_requested"] or job["status"] in {"CANCELLED", "COMPLETED"}:
                return {"discovered": 0, "excluded": 0}
            for raw in urls:
                normalized = normalize_url(raw, parent)
                if not normalized or not is_same_origin(normalized, job["origin_url"]) or parent_depth + 1 > job["max_depth"]:
                    excluded += 1
                    continue
                count = db.execute("SELECT COUNT(*) FROM deep_crawl_urls WHERE job_id=?", (job_id,)).fetchone()[0]
                if count >= job["max_pages"]:
                    excluded += 1
                    continue
                if self._enqueue(db, job_id, normalized, parent_depth + 1, parent):
                    inserted += 1
            db.execute("UPDATE deep_crawl_jobs SET status='RUNNING', updated_at=? WHERE job_id=? AND status='QUEUED'", (utc_now(), job_id))
        return {"discovered": inserted, "excluded": excluded}

    def claim_next(self, job_id: str, org_id: str) -> dict[str, Any] | None:
        """Atomically claim one URL. A process crash can recover IN_PROGRESS URLs."""
        with self._connect() as db:
            job = db.execute("SELECT * FROM deep_crawl_jobs WHERE job_id=? AND org_id=?", (job_id, org_id)).fetchone()
            if not job or job["cancel_requested"] or job["status"] in {"CANCELLED", "COMPLETED"}:
                return None
            row = db.execute("SELECT * FROM deep_crawl_urls WHERE job_id=? AND status='DISCOVERED' ORDER BY depth, normalized_url LIMIT 1", (job_id,)).fetchone()
            if not row:
                return None
            db.execute("UPDATE deep_crawl_urls SET status='IN_PROGRESS', attempts=attempts+1, updated_at=? WHERE job_id=? AND normalized_url=? AND status='DISCOVERED'", (utc_now(), job_id, row["normalized_url"]))
            return dict(db.execute("SELECT * FROM deep_crawl_urls WHERE job_id=? AND normalized_url=?", (job_id, row["normalized_url"])).fetchone())

    def recover_interrupted(self, job_id: str, org_id: str) -> int:
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM deep_crawl_jobs WHERE job_id=? AND org_id=?", (job_id, org_id)).fetchone():
                raise KeyError("crawl job not found for organization")
            cur = db.execute("UPDATE deep_crawl_urls SET status='DISCOVERED', updated_at=? WHERE job_id=? AND status='IN_PROGRESS'", (utc_now(), job_id))
            return cur.rowcount

    def finish_url(self, job_id: str, org_id: str, url: str, status: str, http_status: int | None = None, final_url: str | None = None, error_code: str | None = None) -> None:
        if status not in {"CRAWLED", "FAILED", "EXCLUDED"}:
            raise ValueError("URL result status must be CRAWLED, FAILED, or EXCLUDED")
        normalized = normalize_url(url)
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM deep_crawl_jobs WHERE job_id=? AND org_id=?", (job_id, org_id)).fetchone():
                raise KeyError("crawl job not found for organization")
            cur = db.execute(
                "UPDATE deep_crawl_urls SET status=?, http_status=?, final_url=?, error_code=?, updated_at=? WHERE job_id=? AND normalized_url=?",
                (status, http_status, final_url, error_code, utc_now(), job_id, normalized),
            )
            if cur.rowcount != 1:
                raise KeyError("URL does not belong to this crawl job")

    def request_cancel(self, job_id: str, org_id: str) -> None:
        with self._connect() as db:
            cur = db.execute("UPDATE deep_crawl_jobs SET cancel_requested=1,status='CANCEL_REQUESTED',updated_at=? WHERE job_id=? AND org_id=? AND status NOT IN ('COMPLETED','CANCELLED')", (utc_now(), job_id, org_id))
            if cur.rowcount != 1:
                raise KeyError("active crawl job not found for organization")

    def get_job(self, job_id: str, org_id: str) -> dict[str, Any]:
        with self._connect() as db:
            job = db.execute("SELECT * FROM deep_crawl_jobs WHERE job_id=? AND org_id=?", (job_id, org_id)).fetchone()
            if not job:
                raise KeyError("crawl job not found for organization")
            rows = db.execute("SELECT status, COUNT(*) AS count FROM deep_crawl_urls WHERE job_id=? GROUP BY status", (job_id,)).fetchall()
            counts = {row["status"]: row["count"] for row in rows}
            discovered = sum(counts.values())
            crawled = counts.get("CRAWLED", 0)
            remaining = counts.get("DISCOVERED", 0) + counts.get("IN_PROGRESS", 0)
            eligible = remaining + crawled + counts.get("FAILED", 0)
            terminal = crawled + counts.get("FAILED", 0)
            return {
                "job_id": job["job_id"], "status": job["status"], "origin_url": job["origin_url"],
                "max_pages": job["max_pages"], "max_depth": job["max_depth"],
                "discovered": discovered, "eligible": eligible, "crawled": crawled,
                "failed": counts.get("FAILED", 0), "excluded": counts.get("EXCLUDED", 0),
                "remaining": remaining, "in_progress": counts.get("IN_PROGRESS", 0),
                "completion_percent": round((terminal / eligible) * 100, 1) if eligible else 0.0,
                "partial": bool(remaining or counts.get("FAILED", 0) or job["status"] not in {"COMPLETED"}),
                "cancel_requested": bool(job["cancel_requested"]), "updated_at": job["updated_at"],
            }
