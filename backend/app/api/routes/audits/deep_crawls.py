"""Tenant-scoped API for resumable deep-crawl jobs.

Quick Scan remains unchanged. This first HTTP-only worker uses persisted URL
state and reports rendered coverage separately (not implemented by this worker).
"""
from __future__ import annotations

import asyncio
import os
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.crawl_orchestration import DeepCrawlStore, is_public_http_target, is_same_origin, normalize_url
from app.identity.deps import get_current_user, require_permission
from app.identity.authorizer import UserIdentity

router = APIRouter(prefix="/deep-crawls", tags=["Deep Crawls"])


def _store() -> DeepCrawlStore:
    path = settings.AUTH_DATABASE_PATH or "data/dristik.db"
    return DeepCrawlStore(path)


class DeepCrawlRequest(BaseModel):
    website_url: str = Field(min_length=8, max_length=2048)
    max_pages: int = Field(default=1000, ge=1, le=100000)
    max_depth: int = Field(default=8, ge=0, le=100)


async def _worker(job_id: str, org_id: str) -> None:
    store = _store()
    snapshot = store.get_job(job_id, org_id)
    origin = snapshot["origin_url"]
    robots = RobotFileParser()
    if not is_public_http_target(origin):
        store.finish_url(job_id, org_id, origin, "FAILED", error_code="SSRF_TARGET_BLOCKED")
        with store._connect() as db:
            db.execute("UPDATE deep_crawl_jobs SET status='PARTIAL',updated_at=? WHERE job_id=? AND org_id=?", (datetime.now(timezone.utc).isoformat(), job_id, org_id))
        return
    robots_url = urljoin(origin, "/robots.txt")
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), follow_redirects=False, headers={"User-Agent": "DristikBot/1.0 (+https://dristik.ai/bot)"}) as client:
        try:
            response = await client.get(robots_url)
            if response.status_code < 400:
                robots.parse(response.text.splitlines())
            else:
                # A missing robots file means no published robots rules.
                robots.parse(["User-agent: *", "Allow: /"])
        except httpx.HTTPError:
            # Fail closed when robots policy cannot be fetched.
            robots.parse(["User-agent: *", "Disallow: /"])
        # Discover sitemap URLs declared by robots.txt. Sitemap fetching is
        # bounded and each URL is still checked against same-origin scope.
        sitemap_urls = []
        try:
            for line in response.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_urls.append(line.split(":", 1)[1].strip())
        except (NameError, AttributeError):
            pass
        sitemap_urls.append(urljoin(origin, "/sitemap.xml"))
        root_url = origin
        for sitemap_url in sitemap_urls[:10]:
            normalized_sitemap = normalize_url(sitemap_url)
            if not normalized_sitemap or not is_same_origin(normalized_sitemap, origin) or not is_public_http_target(normalized_sitemap):
                continue
            try:
                sitemap_response = await client.get(normalized_sitemap)
                if sitemap_response.status_code != 200:
                    continue
                root = ET.fromstring(sitemap_response.content)
                discovered = []
                for node in root.iter():
                    if node.tag.rsplit("}", 1)[-1] == "loc" and node.text:
                        normalized = normalize_url(node.text)
                        if normalized and is_same_origin(normalized, origin):
                            discovered.append(normalized)
                store.enqueue_discovered(job_id, org_id, discovered, root_url, 0)
            except (httpx.HTTPError, ET.ParseError, ValueError):
                continue

        while True:
            state = store.get_job(job_id, org_id)
            if state["cancel_requested"]:
                break
            item = store.claim_next(job_id, org_id)
            if item is None:
                break
            url = item["normalized_url"]
            if not is_public_http_target(url):
                store.finish_url(job_id, org_id, url, "EXCLUDED", error_code="SSRF_TARGET_BLOCKED")
                continue
            if not robots.can_fetch("DristikBot", url):
                store.finish_url(job_id, org_id, url, "EXCLUDED", error_code="ROBOTS_DISALLOW")
                continue
            result = None
            error_code = "HTTP_ERROR"
            for attempt in range(2):
                try:
                    result = await client.get(url)
                    break
                except httpx.TimeoutException:
                    error_code = "TIMEOUT"
                except httpx.HTTPError:
                    error_code = "NETWORK_ERROR"
                if attempt == 0:
                    await asyncio.sleep(0.25)
            if result is None:
                store.finish_url(job_id, org_id, url, "FAILED", error_code=error_code)
                continue
            if result.status_code in {301, 302, 303, 307, 308}:
                target = normalize_url(urljoin(url, result.headers.get("location", "")))
                if not target or not is_same_origin(target, origin):
                    store.finish_url(job_id, org_id, url, "EXCLUDED", http_status=result.status_code, final_url=target, error_code="REDIRECT_OUT_OF_SCOPE")
                else:
                    store.enqueue_discovered(job_id, org_id, [target], url, int(item["depth"]))
                    store.finish_url(job_id, org_id, url, "CRAWLED", http_status=result.status_code, final_url=target)
                continue
            if result.status_code >= 400:
                store.finish_url(job_id, org_id, url, "FAILED", http_status=result.status_code, error_code=f"HTTP_{result.status_code}")
                continue
            store.finish_url(job_id, org_id, url, "CRAWLED", http_status=result.status_code, final_url=str(result.url))
            content_type = result.headers.get("content-type", "").lower()
            if "text/html" not in content_type or item["depth"] >= int(state.get("max_depth", 8)):
                continue
            soup = BeautifulSoup(result.text, "html.parser")
            links = []
            for anchor in soup.find_all("a", href=True):
                normalized = normalize_url(anchor.get("href", ""), url)
                if normalized:
                    links.append(normalized)
            store.enqueue_discovered(job_id, org_id, links, url, int(item["depth"]))
        with store._connect() as db:
            job = db.execute("SELECT cancel_requested FROM deep_crawl_jobs WHERE job_id=? AND org_id=?", (job_id, org_id)).fetchone()
            if job and job["cancel_requested"]:
                db.execute("UPDATE deep_crawl_jobs SET status='CANCELLED',updated_at=? WHERE job_id=? AND org_id=?", (datetime.now(timezone.utc).isoformat(), job_id, org_id))
            else:
                remaining = db.execute("SELECT COUNT(*) FROM deep_crawl_urls WHERE job_id=? AND status IN ('DISCOVERED','IN_PROGRESS')", (job_id,)).fetchone()[0]
                failed = db.execute("SELECT COUNT(*) FROM deep_crawl_urls WHERE job_id=? AND status='FAILED'", (job_id,)).fetchone()[0]
                status = "PARTIAL" if remaining or failed else "COMPLETED"
                db.execute("UPDATE deep_crawl_jobs SET status=?,updated_at=? WHERE job_id=? AND org_id=?", (status, __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), job_id, org_id))


@router.post("", status_code=202)
async def create_deep_crawl(
    payload: DeepCrawlRequest,
    background_tasks: BackgroundTasks,
    user: UserIdentity = Depends(require_permission("mission:create")),
):
    origin = normalize_url(payload.website_url)
    if not origin:
        raise HTTPException(status_code=422, detail="website_url must be a valid HTTP(S) URL")
    if not is_public_http_target(origin):
        raise HTTPException(status_code=422, detail="Deep crawl targets must resolve exclusively to public IP addresses.")
    job_id = "crawl_" + uuid.uuid4().hex
    try:
        _store().create_job(job_id, user.org_id, origin, payload.max_pages, payload.max_depth)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(_worker, job_id, user.org_id)
    return _store().get_job(job_id, user.org_id)


@router.get("/{job_id}")
async def get_deep_crawl(job_id: str, user: UserIdentity = Depends(get_current_user)):
    try:
        return _store().get_job(job_id, user.org_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Deep crawl not found") from exc


@router.post("/{job_id}/cancel")
async def cancel_deep_crawl(job_id: str, user: UserIdentity = Depends(require_permission("mission:create"))):
    try:
        _store().request_cancel(job_id, user.org_id)
        return _store().get_job(job_id, user.org_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Active deep crawl not found") from exc
