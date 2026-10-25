"""
Dristik Autonomous Background Scheduler
Executes recurring intelligence jobs:
- Daily (00:00 UTC): SERP tracking, rank delta calculation, movement alerts
- Weekly (Sundays 02:00 UTC): Autonomous audit crawls & regression detection
- Weekly (Mondays 04:00 UTC): GSC and GA4 first-party analytics refresh
- Monthly (1st of month): Backlinks & referring domain profile refresh
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.connectors.authority.service import ExternalAuthorityService
from app.connectors.authority.store import ExternalStore
from app.intelligence.serp_tracker import serp_tracking_engine

logger = logging.getLogger("dristik.scheduler")


class DristikScheduler:
    def __init__(self, check_interval_seconds: int = 60):
        self.interval = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_serp_day: Optional[str] = None
        self._last_weekly_week: Optional[str] = None
        self._last_monthly_month: Optional[str] = None
        self.total_jobs_executed = 0
        self.last_run_at: Optional[str] = None
        self.store = ExternalStore()
        self.service = ExternalAuthorityService(store=self.store)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Dristik Autonomous Scheduler started (check interval: %ds).", self.interval)

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Dristik Autonomous Scheduler stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "interval_seconds": self.interval,
            "total_jobs_executed": self.total_jobs_executed,
            "last_run_at": self.last_run_at,
            "last_serp_day": self._last_serp_day,
            "last_weekly_week": self._last_weekly_week,
            "last_monthly_month": self._last_monthly_month,
        }

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.tick()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in scheduler tick: %s", exc, exc_info=True)

            try:
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break

    async def tick(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        today_str = now.date().isoformat()
        week_str = f"{now.year}-W{now.isocalendar()[1]}"
        month_str = f"{now.year}-{now.month:02d}"
        self.last_run_at = now.isoformat()

        executed: List[str] = []

        # 1. Run due external jobs from external_jobs queue (rate-limit retries, scheduled syncs)
        try:
            due_outcomes = self.service.run_due_jobs(limit=10)
            if due_outcomes:
                self.total_jobs_executed += len(due_outcomes)
                executed.append(f"due_external_jobs_{len(due_outcomes)}")
        except Exception as exc:
            logger.warning("Failed processing due external jobs: %s", exc)

        # 2. Daily SERP Sync (runs once per UTC day)
        if self._last_serp_day != today_str:
            try:
                synced = await self._run_daily_serp_sync()
                self._last_serp_day = today_str
                self.total_jobs_executed += synced
                executed.append(f"daily_serp_sync_{synced}_keywords")
                logger.info("Completed daily SERP sync: %d keywords processed.", synced)
            except Exception as exc:
                logger.error("Daily SERP sync failed: %s", exc, exc_info=True)

        # 3. Weekly Sync (on Sundays or first check of week)
        if now.weekday() == 6 and self._last_weekly_week != week_str:
            try:
                await self._run_weekly_sync()
                self._last_weekly_week = week_str
                executed.append("weekly_sync")
            except Exception as exc:
                logger.error("Weekly sync failed: %s", exc, exc_info=True)

        # 5. Subscription-plan eligible monthly website intelligence. The ledger makes
        # this safe to check on every tick and supports catch-up after a restart.
        try:
            from app.continuous_intelligence import process_due_monthly_runs
            monthly_result = await process_due_monthly_runs()
            if monthly_result.get("runs_started"):
                executed.append(f"continuous_intelligence_monthly_{monthly_result['runs_started']}")
                self.total_jobs_executed += monthly_result["runs_started"]
        except Exception as exc:
            logger.error("Continuous intelligence monthly processing failed: %s", exc, exc_info=True)

        # 4. Monthly Backlink Sync (1st day of month)
        if now.day == 1 and self._last_monthly_month != month_str:
            try:
                await self._run_monthly_sync()
                self._last_monthly_month = month_str
                executed.append("monthly_sync")
            except Exception as exc:
                logger.error("Monthly sync failed: %s", exc, exc_info=True)

        return {
            "timestamp": self.last_run_at,
            "tasks_executed": executed,
        }

    async def _run_daily_serp_sync(self) -> int:
        """Runs SERP tracking for all projects with active tracked keywords."""
        with self.store._connect() as conn:
            projects = conn.execute(
                "SELECT DISTINCT project_id, domain FROM project_keywords WHERE is_active=1"
            ).fetchall()

        total_synced = 0
        for p in projects:
            p_id = p["project_id"]
            p_domain = p["domain"]
            res = serp_tracking_engine.sync_keyword_serp(
                project_id=p_id,
                domain=p_domain,
            )
            total_synced += res.get("synced_count", 0)
        return total_synced

    async def _run_weekly_sync(self) -> None:
        """Enqueues GSC and GA4 first-party analytics sync for all connected projects."""
        with self.store._connect() as conn:
            connections = conn.execute(
                "SELECT project_id, domain, provider FROM external_connections WHERE status='CONNECTED'"
            ).fetchall()

        for c in connections:
            prov = c["provider"]
            if prov == "google_search_console":
                self.service.enqueue_sync(c["project_id"], c["domain"], ["sync_gsc_data"])
            elif prov == "google_analytics_4":
                self.service.enqueue_sync(c["project_id"], c["domain"], ["sync_ga4_data"])

    async def _run_monthly_sync(self) -> None:
        """Enqueues backlink sync for active domains."""
        with self.store._connect() as conn:
            domains = conn.execute(
                "SELECT DISTINCT project_id, domain FROM external_connections"
            ).fetchall()

        for d in domains:
            self.service.enqueue_sync(d["project_id"], d["domain"], ["sync_backlinks"])


scheduler = DristikScheduler()
