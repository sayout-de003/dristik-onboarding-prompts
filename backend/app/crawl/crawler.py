"""
Dristik AI Async Multi-Page Web Ingestion & Crawler Engine
Performs recursive multi-page crawling, sitemap discovery, robots.txt parsing,
Firecrawl dynamic fallback for SPAs/WAFs, and deterministic multi-page SEO & AI-search evidence extraction.
"""
import time
import re
import asyncio
import logging
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Any, Set, Tuple, Optional, Callable
import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger("dristik.crawler")

from app.core.config import settings
from app.domain.models import PageEvidence, CrawlManifest
from app.core.security.ssrf import is_safe_url
from app.domain.evidence.store import EvidenceStore

# Deterministic Analyzers
from app.crawl.analyzers.html import analyze_html_content, distill_semantic_content
from app.crawl.analyzers.metadata import analyze_meta_tags
from app.crawl.robots import declared_sitemaps
from app.crawl.url_frontier import (
    classify_page_type,
    normalize_url,
    order_for_roles,
    page_priority,
    url_role,
)
from app.crawl.analyzers.dom import analyze_dom_structure
from app.crawl.analyzers.schema import analyze_schema_markup
from app.crawl.analyzers.links import analyze_link_graph
from app.crawl.analyzers.performance import analyze_performance_metrics
from app.crawl.analyzers.security import analyze_security_headers
from app.crawl.analyzers.dynamic_content import extract_embedded_cms_content, needs_js_render
from app.crawl.analyzers.visible import extract_visible_page
from app.crawl.browser import BrowserRenderService
from app.crawl.response_limits import ResponseTooLargeError, read_response_limited

class CrawlerService:
    def __init__(self):
        self.headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }

    def _classify_page_type(self, path: str) -> str:
        return classify_page_type(path)

    def _url_role(self, url: str) -> str:
        """Role slot used to keep a short crawl representative."""
        return url_role(url)

    def _order_for_roles(self, urls: List[str], crawled_pages: List[Any]) -> List[str]:
        """
        Fill unfilled roles before spending the remaining budget on the priority queue.
        Homepage, primary commercial, high-intent, a second commercial URL, then proof.
        """
        return order_for_roles(urls, crawled_pages)

    def _get_page_priority(self, url: str) -> int:
        return page_priority(url)

    def _normalize_url(self, raw_url: str, base_domain: str, base_origin: str) -> Optional[str]:
        return normalize_url(raw_url, base_domain, base_origin)

    async def _fetch_robots_txt(self, base_origin: str, client: httpx.AsyncClient) -> Tuple[bool, Optional[str], List[str]]:
        robots_url = f"{base_origin}/robots.txt"
        sitemap_urls: List[str] = []
        try:
            async with client.stream("GET", robots_url, headers=self.headers, timeout=5.0) as resp:
                if resp.status_code == 200:
                    max_bytes = int(getattr(settings, "CRAWL_MAX_SITEMAP_BYTES", 2 * 1024 * 1024) or 2 * 1024 * 1024)
                    body = await read_response_limited(resp, max_bytes)
                    content = body.decode("utf-8", errors="replace")
                    sitemap_urls.extend(declared_sitemaps(content))
                    return True, content[:2000], sitemap_urls
        except Exception as exc:
            logger.info("robots.txt fetch failed for %s: %s", robots_url, type(exc).__name__)
        return False, None, sitemap_urls

    async def _fetch_sitemap_urls(
        self,
        base_origin: str,
        base_domain: str,
        declared_sitemaps: List[str],
        client: httpx.AsyncClient,
        max_sitemap_urls: int = 500
    ) -> Tuple[bool, Optional[str], List[str], bool]:
        """Discover same-site URLs from bounded sitemap responses.

        Sitemap bodies are streamed under a byte budget, nested sitemap fetches
        are bounded, and every sitemap URL is checked before it is requested.
        """
        candidate_sitemaps = list(dict.fromkeys(declared_sitemaps + [
            f"{base_origin}/sitemap.xml",
            f"{base_origin}/sitemap_index.xml",
            f"{base_origin}/wp-sitemap.xml",
        ]))
        discovered_urls: List[str] = []
        found_sitemap_url: Optional[str] = None
        visited_xml_sitemaps: Set[str] = set()
        truncated = False
        max_sitemap_bytes = int(
            getattr(settings, "CRAWL_MAX_SITEMAP_BYTES", 2 * 1024 * 1024)
            or 2 * 1024 * 1024
        )

        def at_cap() -> bool:
            nonlocal truncated
            if len(discovered_urls) >= max_sitemap_urls:
                truncated = True
                return True
            return False

        def add_page(raw: str) -> None:
            if at_cap():
                return
            norm = self._normalize_url(raw, base_domain, base_origin)
            if norm and norm not in discovered_urls:
                discovered_urls.append(norm)

        async def read_sitemap(sitemap_url: str, timeout: float) -> Optional[str]:
            if settings.SSRF_PROTECTION_ENABLED:
                safe, reason = is_safe_url(sitemap_url)
                if not safe:
                    logger.warning("Blocked unsafe sitemap URL %s: %s", sitemap_url, reason)
                    return None
            try:
                async with client.stream(
                    "GET", sitemap_url, headers=self.headers, timeout=timeout
                ) as response:
                    if response.status_code != 200:
                        logger.info("Sitemap fetch returned HTTP %s for %s", response.status_code, sitemap_url)
                        return None
                    body = await read_response_limited(response, max_sitemap_bytes)
                    text = body.decode("utf-8", errors="replace")
                    content_type = response.headers.get("content-type", "").lower()
                    looks_like_xml = (
                        "xml" in content_type
                        or text.lstrip().startswith("<?xml")
                        or "<urlset" in text.lower()
                        or "<sitemapindex" in text.lower()
                    )
                    return text if looks_like_xml else None
            except Exception as exc:
                logger.info("Sitemap fetch failed for %s: %s", sitemap_url, type(exc).__name__)
                return None

        for sitemap_url in candidate_sitemaps:
            if sitemap_url in visited_xml_sitemaps or len(visited_xml_sitemaps) >= 25:
                continue
            visited_xml_sitemaps.add(sitemap_url)
            sitemap_text = await read_sitemap(sitemap_url, 6.0)
            if not sitemap_text:
                continue

            try:
                root = ET.fromstring(sitemap_text)
            except ET.ParseError:
                logger.info("Ignoring malformed XML sitemap: %s", sitemap_url)
                continue

            found_sitemap_url = found_sitemap_url or sitemap_url
            locs = [
                (element.text or "").strip()
                for element in root.iter()
                if element.tag.rsplit("}", 1)[-1].lower() == "loc"
            ]
            is_index = root.tag.rsplit("}", 1)[-1].lower() == "sitemapindex"
            for loc in locs:
                if at_cap():
                    break
                if not loc:
                    continue
                is_nested = loc.lower().split("?", 1)[0].endswith(".xml") or "sitemap" in loc.lower()
                if is_index and is_nested:
                    nested_url = urljoin(sitemap_url, loc)
                    if nested_url in visited_xml_sitemaps or len(visited_xml_sitemaps) >= 25:
                        continue
                    visited_xml_sitemaps.add(nested_url)
                    nested_text = await read_sitemap(nested_url, 5.0)
                    if not nested_text:
                        continue
                    try:
                        nested_root = ET.fromstring(nested_text)
                    except ET.ParseError:
                        logger.info("Ignoring malformed nested sitemap: %s", nested_url)
                        continue
                    for nested_element in nested_root.iter():
                        if nested_element.tag.rsplit("}", 1)[-1].lower() == "loc":
                            nested_loc = (nested_element.text or "").strip()
                            if nested_loc and not (
                                nested_loc.lower().split("?", 1)[0].endswith(".xml")
                                or "sitemap" in nested_loc.lower()
                            ):
                                add_page(nested_loc)
                            if at_cap():
                                break
                else:
                    add_page(loc)
            if discovered_urls:
                return True, found_sitemap_url, discovered_urls[:max_sitemap_urls], truncated

        return found_sitemap_url is not None, found_sitemap_url, discovered_urls[:max_sitemap_urls], truncated

    async def _js_render_page(
        self,
        url: str,
        client: httpx.AsyncClient,
        start_time: float,
    ) -> Tuple[Optional[str], Optional[str], int, float, Dict[str, str], int, Optional[str]]:
        """
        Enterprise 2-Tier Dynamic Rendering:
        Tier 1 (Free / Local): Headless Chromium via Playwright with asset-blocking for fast zero-cost hydration.
        Tier 2 (Cloud Fallback): Firecrawl API with waitFor if local browser is unavailable or cloud WAF blocks it.
        Returns (html, markdown, status, ttfb_ms, headers, bytes, error)
        markdown is Playwright innerText when the local browser rendered the page —
        that is the closest analogue to what a human actually sees.
        """
        # Browser and remote-render paths must validate the initial target too.
        # The browser additionally validates each redirect/subresource in its route hook.
        if settings.SSRF_PROTECTION_ENABLED:
            try:
                safe, reason = await asyncio.wait_for(
                    asyncio.to_thread(is_safe_url, url),
                    timeout=3.0,
                )
            except asyncio.TimeoutError:
                return None, None, 0, (time.time() - start_time) * 1000, {}, 0, "SSRF validation timed out; render target blocked", None
            if not safe:
                return None, None, 0, (time.time() - start_time) * 1000, {}, 0, f"SSRF blocked render target: {reason}", None

        # Tier 1: Local High-Speed Playwright ($0 API cost, fast asset-blocked execution)
        if BrowserRenderService.is_available():
            try:
                pw_html, pw_status, pw_ttfb, pw_headers, pw_err, pw_text, pw_perf = await BrowserRenderService.render_page(url)
                if pw_err == "ssrf_blocked_browser_request":
                    return None, None, 0, (time.time() - start_time) * 1000, {}, 0, "SSRF blocked unsafe browser redirect or subresource", None
                if pw_html:
                    max_response_bytes = int(getattr(settings, "CRAWL_MAX_RESPONSE_BYTES", 5 * 1024 * 1024) or 5 * 1024 * 1024)
                    if len(pw_html.encode("utf-8")) > max_response_bytes:
                        return None, None, 0, (time.time() - start_time) * 1000, {}, 0, "rendered_response_too_large", None
                    headers = pw_headers or {"x-crawler": "playwright-local-js"}
                    return (
                        pw_html,
                        pw_text,
                        pw_status if pw_status else 0,
                        pw_ttfb if pw_ttfb > 0 else ((time.time() - start_time) * 1000),
                        headers,
                        len(pw_html.encode("utf-8")),
                        None,
                        pw_perf,
                    )
            except Exception:
                pass

        # Tier 2: Cloud Firecrawl Dynamic Rendering Fallback
        if not settings.FIRECRAWL_API_KEY or not settings.FIRECRAWL_API_KEY.strip():
            return None, None, 0, (time.time() - start_time) * 1000, {}, 0, "js_render_unavailable", None

        try:
            async with client.stream(
                "POST",
                "https://api.firecrawl.dev/v1/scrape",
                json={
                    "url": url,
                    "formats": ["html", "markdown"],
                    "waitFor": max(800, int(settings.FIRECRAWL_WAIT_MS)),
                    "timeout": 25000,
                    "onlyMainContent": False,
                },
                headers={
                    "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY.strip()}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            ) as fc_resp:
                max_response_bytes = int(getattr(settings, "CRAWL_MAX_RESPONSE_BYTES", 5 * 1024 * 1024) or 5 * 1024 * 1024)
                if fc_resp.status_code == 200:
                    fc_body = await read_response_limited(fc_resp, max_response_bytes)
                    import json
                    data = (json.loads(fc_body.decode("utf-8", errors="replace")).get("data") or {})
                    html_content = data.get("html") or ""
                    markdown = data.get("markdown") or ""
                    if html_content or markdown:
                        payload = html_content or f"<html><body><article>{markdown}</article></body></html>"
                        payload_bytes = len(payload.encode("utf-8"))
                        if payload_bytes > max_response_bytes:
                            return None, None, 0, (time.time() - start_time) * 1000, {}, 0, "rendered_response_too_large", None
                        ttfb_ms = (time.time() - start_time) * 1000
                        return (
                            payload,
                            markdown,
                            200,
                            ttfb_ms,
                            {"x-crawler": "firecrawl-js"},
                            payload_bytes,
                            None,
                            None,
                        )
                return None, None, fc_resp.status_code, (time.time() - start_time) * 1000, {}, 0, f"firecrawl HTTP {fc_resp.status_code}", None
        except Exception as exc:
            return None, None, 0, (time.time() - start_time) * 1000, {}, 0, str(exc), None

    async def _fetch_page_with_fallbacks(
        self,
        url: str,
        client: httpx.AsyncClient,
        force_js: bool = False,
    ) -> Tuple[Optional[str], int, float, Dict[str, str], int, Optional[str], Optional[str], List[Dict[str, Any]], str, Optional[Dict[str, Any]]]:
        """
        Direct HTTP first following redirects step-by-step with SSRF validation on each hop.
        If blocked or force_js for CMS/SPA shells, render in a browser via Playwright/Firecrawl.
        Returns:
        (html_content, status_code, ttfb_ms, headers, content_bytes, error_msg, markdown, redirect_chain, final_url, timing_data)
        """
        start_time = time.time()
        direct_err = None
        ttfb_ms = 0.0
        redirect_chain: List[Dict[str, Any]] = []
        final_url = url
        timing_data: Optional[Dict[str, Any]] = None

        if not force_js:
            current_url = url
            visited_in_chain: Set[str] = set()

            for _ in range(10):
                if current_url in visited_in_chain:
                    direct_err = f"Redirect loop detected at '{current_url}'"
                    break
                visited_in_chain.add(current_url)

                if settings.SSRF_PROTECTION_ENABLED:
                    try:
                        is_safe, reason = await asyncio.wait_for(
                            asyncio.to_thread(is_safe_url, current_url),
                            timeout=3.0,
                        )
                    except asyncio.TimeoutError:
                        direct_err = f"SSRF blocked redirect validation timeout: {current_url}"
                        break
                    if not is_safe:
                        direct_err = f"SSRF blocked redirect: {current_url} ({reason})"
                        break

                hop_start = time.time()
                try:
                    async with client.stream("GET", current_url) as stream_resp:
                        ttfb_hop = (time.time() - hop_start) * 1000
                        max_response_bytes = int(getattr(settings, "CRAWL_MAX_RESPONSE_BYTES", 5 * 1024 * 1024) or 5 * 1024 * 1024)
                        content = await read_response_limited(stream_resp, max_response_bytes)
                        hop_latency = (time.time() - hop_start) * 1000
                        status_code = stream_resp.status_code
                        loc = stream_resp.headers.get("location") or stream_resp.headers.get("Location")
                        resp_headers = dict(stream_resp.headers)
                        resp_text = content.decode(stream_resp.encoding or "utf-8", errors="replace")
                except ResponseTooLargeError as e:
                    # Oversized responses are a hard per-URL limit, not a reason to
                    # fetch the same document through a second renderer/provider.
                    direct_err = str(e)
                    break
                except Exception as e:
                    direct_err = f"{type(e).__name__}: {e}"
                    break

                if 300 <= status_code < 400 and loc:
                    next_url = urljoin(current_url, loc)
                    redirect_chain.append({
                        "status": status_code,
                        "url": current_url,
                        "location": next_url,
                        "latency_ms": round(hop_latency, 2)
                    })
                    current_url = next_url
                else:
                    final_url = current_url
                    ttfb_ms = round(ttfb_hop, 1)
                    timing_data = {
                        "ttfb_ms": ttfb_ms,
                        "download_ms": round(max(0.0, hop_latency - ttfb_hop), 1),
                        "total_transferred_bytes": len(content),
                    }
                    if status_code < 400 and resp_text:
                        return (
                            resp_text,
                            status_code,
                            ttfb_ms,
                            resp_headers,
                            len(content),
                            None,
                            None,
                            redirect_chain,
                            final_url,
                            timing_data,
                        )
                    direct_err = f"HTTP {status_code}"
                    break

            if direct_err and (
                "Redirect loop" in direct_err
                or "SSRF blocked" in direct_err
                or "response exceeds configured" in direct_err
            ):
                return None, 0, ttfb_ms, {}, 0, direct_err, None, redirect_chain, final_url, None

        html, markdown, status, js_ttfb, headers, nbytes, js_err, js_perf = await self._js_render_page(url, client, start_time)
        if html:
            return (
                html,
                status,
                js_ttfb or ttfb_ms,
                headers,
                nbytes,
                None,
                markdown,
                redirect_chain,
                final_url,
                js_perf,
            )
        return None, 0, ttfb_ms, {}, 0, direct_err or js_err, None, redirect_chain, final_url, None

    async def crawl_and_analyze(self, target_url: str, evidence_store: EvidenceStore) -> PageEvidence:
        """
        Backwards-compatible single-page crawl entry point.
        """
        manifest = await self.crawl_site_and_analyze(target_url, evidence_store, max_pages=1)
        if not manifest.pages:
            raise RuntimeError(f"Failed to crawl website '{target_url}'. The target URL is unreachable or offline.")
        return manifest.pages[0]

    async def crawl_site_and_analyze(
        self,
        target_url: str,
        evidence_store: EvidenceStore,
        max_pages: Any = 10,
        progress_callback: Optional[Callable[[str, int], Any]] = None
    ) -> CrawlManifest:
        """
        Executes recursive multi-page crawl across the website.
        Supports page limit options: 10, 25, 50, 200, 500, or named tiers ('quick', 'standard', 'deep', 'enterprise').
        Discovers robots.txt, sitemaps, internal links, ranks URLs, and extracts multi-page SEO evidence.
        """
        target_max_pages = settings.get_max_crawl_pages(max_pages)
        raw_url = target_url.strip()
        if not raw_url.startswith(("http://", "https://")):
            raw_url = f"https://{raw_url}"
            
        parsed_target = urlparse(raw_url)
        base_domain = parsed_target.netloc
        base_origin = f"{parsed_target.scheme}://{parsed_target.netloc}"
        normalized_root = self._normalize_url(raw_url, base_domain, base_origin) or raw_url

        # 1. SSRF Verification. Bound DNS validation so a slow resolver cannot
        # stall the entire audit worker indefinitely; timeout fails closed.
        if settings.SSRF_PROTECTION_ENABLED:
            try:
                is_safe, reason = await asyncio.wait_for(
                    asyncio.to_thread(is_safe_url, normalized_root),
                    timeout=3.0,
                )
            except asyncio.TimeoutError as exc:
                raise ValueError("Security Alert: SSRF validation timed out; crawl blocked.") from exc
            if not is_safe:
                raise ValueError(f"Security Alert: {reason}")

        crawled_pages: List[PageEvidence] = []
        crawled_page_urls: Set[str] = set()
        discovered_urls_pool: Set[str] = {normalized_root}
        visited_urls: Set[str] = set()
        broken_links: List[Dict[str, str]] = []
        last_fetch_error: Optional[str] = None

        timeout = httpx.Timeout(settings.CRAWL_TIMEOUT_SECONDS, connect=8.0)
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

        async with httpx.AsyncClient(headers=self.headers, timeout=timeout, limits=limits, follow_redirects=False, verify=True) as client:
            
            # Step A: Discover robots.txt & Sitemap
            if progress_callback:
                progress_callback(f"Connecting to {base_origin}...", 15)
                
            robots_found, robots_content, declared_sitemaps = await self._fetch_robots_txt(base_origin, client)
            discovery_cap = max(int(getattr(settings, "CRAWL_PAGE_CAP", 5000) or 5000), target_max_pages)
            sitemap_found, sitemap_url, sitemap_urls, discovery_truncated = await self._fetch_sitemap_urls(
                base_origin, base_domain, declared_sitemaps, client, max_sitemap_urls=discovery_cap
            )
            
            for u in sitemap_urls:
                norm_s = self._normalize_url(u, base_domain, base_origin)
                if norm_s:
                    discovered_urls_pool.add(norm_s)

            if progress_callback:
                progress_callback(
                    f"Discovered {len(discovered_urls_pool)} pages ({'Sitemap detected' if sitemap_found else 'Link graph discovery'}). Ingesting key pages...",
                    22
                )

            # Step B: Priority Queue Crawl Loop
            semaphore = asyncio.Semaphore(settings.CRAWL_CONCURRENCY)

            async def fetch_and_analyze_single_page(page_url: str) -> Optional[PageEvidence]:
                nonlocal last_fetch_error
                async with semaphore:
                    html_content, status_code, ttfb_ms, resp_headers, content_bytes, err, markdown, redirect_chain, final_url, timing_data = await self._fetch_page_with_fallbacks(page_url, client)
                    
                    if not html_content:
                        last_fetch_error = err or "Connection failed"
                        broken_links.append({"url": page_url, "error": last_fetch_error})
                        return None

                    soup = BeautifulSoup(html_content, "lxml")
                    page_path = urlparse(page_url).path
                    page_type = self._classify_page_type(page_path)
                    crawler_hdr = (resp_headers or {}).get("x-crawler", "")
                    if crawler_hdr.startswith("playwright"):
                        render_mode = "playwright_js"
                    elif crawler_hdr.startswith("firecrawl"):
                        render_mode = "firecrawl_js"
                    else:
                        render_mode = "static"

                    snapshot = extract_visible_page(soup)
                    visible_text = snapshot["main_text"] or distill_semantic_content(soup)
                    visible_words = snapshot["word_count"] or len(re.findall(r"\b\w+\b", visible_text))
                    embedded = extract_embedded_cms_content(soup)
                    is_thin_shell = needs_js_render(soup, visible_words) or (
                        visible_words < 80 and (soup.find_all("script") and len(soup.find_all("script")) >= 3)
                    )

                    raw_http_content = html_content
                    rendered_dom_content = None
                    rendering_disparity_data = None

                    if (
                        settings.JS_RENDER_THIN_PAGES
                        and render_mode == "static"
                        and is_thin_shell
                        and embedded.get("word_count", 0) < 80
                    ):
                        js_html, js_status, js_ttfb, js_headers, js_bytes, js_err, js_md, js_chain, js_final, js_timing = await self._fetch_page_with_fallbacks(
                            page_url, client, force_js=True
                        )
                        if js_html:
                            rendered_dom_content = js_html
                            html_content = js_html
                            status_code = js_status or status_code
                            ttfb_ms = js_ttfb or ttfb_ms
                            timing_data = js_timing or timing_data
                            resp_headers = js_headers or resp_headers
                            content_bytes = js_bytes or content_bytes
                            markdown = js_md or markdown
                            soup = BeautifulSoup(html_content, "lxml")
                            render_mode = "playwright_js" if (resp_headers or {}).get("x-crawler") == "playwright-local-js" else "firecrawl_js"
                            if js_chain:
                                redirect_chain = js_chain
                            if js_final:
                                final_url = js_final

                            # Perform deep Raw HTML vs Rendered DOM Disparity Evaluation
                            try:
                                from app.seo.analyzers.rendering_disparity import analyze_rendering_disparity
                                rendering_disparity_data, _ = analyze_rendering_disparity(
                                    raw_html=raw_http_content,
                                    rendered_html=rendered_dom_content,
                                    page_url=page_url,
                                    evidence_store=evidence_store,
                                )
                            except Exception as disp_err:
                                logger.warning("Rendering disparity analysis note: %s", disp_err)
                        elif embedded.get("word_count"):
                            render_mode = "embedded_cms"
                    elif embedded.get("sources"):
                        render_mode = "embedded_cms"

                    fetch_rec = evidence_store.record_fetch(
                        page_url,
                        html_content,
                        source="crawler",
                        source_type="http",
                        media_type="text/html",
                    )
                    snap_id = getattr(fetch_rec, "snapshot_id", None)
                    snap_path = None
                    if snap_id:
                        try:
                            snap_path = str(evidence_store._ensure_snapshots()._path(snap_id))
                        except Exception:
                            pass

                    # Record dynamic content architectural discovery in evidence store
                    if is_thin_shell:
                        evidence_store.add_evidence(
                            source_type="architecture",
                            analyzer="dynamic_content_analyzer",
                            url=page_url,
                            text="Dynamic client-side hydration detected: content relies on JavaScript/API to populate database copy.",
                            value={
                                "render_mode": render_mode,
                                "is_thin_shell": True,
                                "cms_sources": embedded.get("sources", []),
                                "recovered_words": embedded.get("word_count", 0),
                            }
                        )

                    # Run Deterministic Analyzers
                    html_res = analyze_html_content(
                        soup,
                        page_url,
                        evidence_store,
                        extra_text=markdown or snapshot.get("visible_text") or "",
                        extra_h1=embedded.get("h1"),
                        extra_h2=embedded.get("h2"),
                    )
                    meta_res = analyze_meta_tags(soup, page_url, evidence_store, resp_headers=resp_headers)
                    dom_res = analyze_dom_structure(soup, page_url, evidence_store)
                    schema_res = analyze_schema_markup(soup, page_url, evidence_store)
                    links_res = analyze_link_graph(soup, page_url, normalized_root, evidence_store)
                    perf_res = analyze_performance_metrics(
                        page_url,
                        ttfb_ms,
                        content_bytes,
                        resp_headers,
                        evidence_store,
                        soup=soup,
                        timing_data=timing_data,
                        dom_data=dom_res,
                        raw_html=raw_http_content,
                        rendered_html=rendered_dom_content or html_content,
                    )
                    sec_res = analyze_security_headers(page_url, resp_headers, evidence_store)

                    # Extract newly found internal links
                    internal_links = links_res.get("internal_links", [])
                    for link in internal_links:
                        norm = self._normalize_url(link, base_domain, base_origin)
                        if norm:
                            discovered_urls_pool.add(norm)

                    # Compute Industry-Standard SEO Metrics
                    sc_class = "2xx" if 200 <= status_code < 300 else ("3xx" if 300 <= status_code < 400 else ("4xx" if 400 <= status_code < 500 else "5xx"))
                    robots_str = f"{meta_res.get('robots_meta') or ''} {meta_res.get('x_robots_tag') or ''}".lower()
                    is_idx = "noindex" not in robots_str

                    raw_can = meta_res.get("canonical_url")
                    if not raw_can:
                        can_stat = "missing"
                    elif not raw_can.startswith(("http://", "https://")):
                        can_stat = "relative"
                    elif raw_can.rstrip("/") == page_url.rstrip("/"):
                        can_stat = "self"
                    else:
                        can_stat = "canonicalized"

                    from app.crawl.analyzers.pixel_calculator import evaluate_title_pixel_status, evaluate_meta_pixel_status
                    t_px, t_status = evaluate_title_pixel_status(meta_res.get("title") or "")
                    m_px, m_status = evaluate_meta_pixel_status(meta_res.get("meta_description") or "")
                    w_cnt = html_res.get("word_count", 0)
                    is_thin = bool(w_cnt < 250 and page_type not in ("contact", "legal"))

                    return PageEvidence(
                        url=page_url,
                        status_code=status_code,
                        title=meta_res.get("title"),
                        meta_description=meta_res.get("meta_description"),
                        h1=html_res.get("h1", []),
                        h2=html_res.get("h2", []),
                        h3=html_res.get("h3", []),
                        word_count=w_cnt,
                        readability_score=html_res.get("readability_score", 0.0),
                        canonical_url=raw_can,
                        robots_meta=meta_res.get("robots_meta"),
                        viewport=meta_res.get("viewport"),
                        og_tags=meta_res.get("og_tags", {}),
                        twitter_tags=meta_res.get("twitter_tags", {}),
                        schema_types=schema_res.get("schema_types", []),
                        raw_schema=schema_res.get("raw_schema", []),
                        internal_links=internal_links,
                        external_links=links_res.get("external_links", []),
                        images_without_alt=dom_res.get("images_without_alt", 0),
                        total_images=dom_res.get("total_images", 0),
                        ttfb_ms=perf_res.get("ttfb_ms", 0.0),
                        lab_performance=perf_res.get("lab_performance"),
                        dom_elements_count=dom_res.get("dom_elements_count", 0),
                        scripts_count=dom_res.get("scripts_count", 0),
                        stylesheets_count=dom_res.get("stylesheets_count", 0),
                        page_type=page_type,
                        body_text=(html_res.get("distilled_text") or html_res.get("visible_text") or "")[:100000] or None,
                        ctas=dom_res.get("cta_candidates", [])[:8],
                        render_mode=render_mode,
                        response_headers=dict(resp_headers or {}),
                        redirect_chain=redirect_chain,
                        is_redirected=bool(redirect_chain),
                        final_url=final_url if final_url != page_url else None,
                        snapshot_id=snap_id,
                        snapshot_path=snap_path,
                        raw_html=raw_http_content,
                        rendered_html=rendered_dom_content,
                        rendering_discrepancy=rendering_disparity_data,
                        observed_at=datetime.now(timezone.utc).isoformat(),
                        image_assets=dom_res.get("image_assets", []),
                        x_robots_tag=meta_res.get("x_robots_tag"),
                        status_code_class=sc_class,
                        is_indexable=is_idx,
                        canonical_status=can_stat,
                        title_pixel_width=t_px,
                        meta_pixel_width=m_px,
                        title_pixel_status=t_status,
                        meta_pixel_status=m_status,
                        thin_content=is_thin,
                        hreflang_tags=meta_res.get("hreflang_tags", {}),
                        html_lang=meta_res.get("html_lang"),
                        nap_data=html_res.get("nap_data"),
                        content_authority=html_res.get("content_authority"),
                    )

            # Iteratively fetch top priority pages until target_max_pages reached or queue empty
            while len(crawled_pages) < target_max_pages:
                remaining_candidates = [
                    u for u in discovered_urls_pool 
                    if (self._normalize_url(u, base_domain, base_origin) or u) not in visited_urls
                ]
                if not remaining_candidates:
                    break
                
                sorted_candidates = self._order_for_roles(remaining_candidates, crawled_pages)
                batch = sorted_candidates[: (target_max_pages - len(crawled_pages))]
                
                for u in batch:
                    norm_b = self._normalize_url(u, base_domain, base_origin) or u
                    visited_urls.add(norm_b)
                    
                tasks = [fetch_and_analyze_single_page(u) for u in batch]
                results = await asyncio.gather(*tasks)
                
                for res in results:
                    if res:
                        norm_res = self._normalize_url(res.url, base_domain, base_origin) or res.url
                        if norm_res not in crawled_page_urls:
                            crawled_page_urls.add(norm_res)
                            crawled_pages.append(res)
                            if progress_callback:
                                progress_callback(
                                    f"Audited ({len(crawled_pages)}/{target_max_pages}) pages: {res.page_type.upper()} [{res.url}]",
                                    22 + int((len(crawled_pages) / max(target_max_pages, 1)) * 12)
                                )

        # Check if any pages could be reached
        if not crawled_pages:
            diag_msg = f"Failed to connect to or crawl website '{target_url}'."
            if last_fetch_error:
                if "nodename nor servname" in last_fetch_error or "NameResolutionError" in last_fetch_error:
                    diag_msg = f"DNS Resolution Error: Could not find domain '{base_domain}'. Please verify the spelling or domain registration."
                elif "403" in last_fetch_error:
                    diag_msg = f"Access Blocked (HTTP 403): The website '{base_domain}' is blocking automated requests. Configure FIRECRAWL_API_KEY in .env to bypass bot protection."
                elif "Timeout" in last_fetch_error:
                    diag_msg = f"Connection Timed Out: '{base_domain}' took too long to respond. The server may be offline or slow."
                else:
                    diag_msg += f" (Detail: {last_fetch_error})"
            raise RuntimeError(diag_msg)

        # Step C: Compute Site-Wide SEO Crawl Metrics
        manifest = self._build_crawl_manifest(
            base_domain=base_domain,
            base_url=normalized_root,
            crawled_pages=crawled_pages,
            total_discovered=len(discovered_urls_pool),
            sitemap_found=sitemap_found,
            sitemap_url=sitemap_url,
            robots_txt_found=robots_found,
            robots_txt_content=robots_content,
            broken_links=broken_links,
            sitemap_urls=sitemap_urls,
            target_max_pages=target_max_pages,
            discovery_truncated=discovery_truncated,
            discovered_urls=list(discovered_urls_pool),
        )

        # Step D: Index page chunks into VectorStore using E5-Large
        try:
            from app.crawl.vector_store import vector_store
            from app.crawl.embeddings import embedding_service
            for page in crawled_pages:
                chunks = self._chunk_page_content(page)
                if chunks:
                    vectors = embedding_service.embed_documents(chunks)
                    vector_store.save_chunks(
                        domain=base_domain,
                        url=page.url,
                        page_type=page.page_type,
                        chunks=chunks,
                        vectors=vectors,
                        analysis_id=getattr(evidence_store, "run_id", None),
                    )
        except Exception as exc:
            logger.warning("[Crawler] VectorStore indexing error (non-fatal): %s", exc)

        return manifest

    def _chunk_page_content(self, page: PageEvidence, chunk_size_words: int = 350, overlap_words: int = 50) -> List[str]:
        text_parts = []
        if page.title:
            text_parts.append(f"Title: {page.title}")
        if page.meta_description:
            text_parts.append(f"Description: {page.meta_description}")
        if page.h1:
            text_parts.append(f"H1: {', '.join(page.h1)}")
        if page.h2:
            text_parts.append(f"H2: {', '.join(page.h2)}")
        if page.h3:
            text_parts.append(f"H3: {', '.join(page.h3)}")
        if page.body_text:
            text_parts.append(page.body_text)

        full_text = "\n\n".join(text_parts).strip()
        words = full_text.split()
        if not words:
            return []

        chunks = []
        i = 0
        step = max(chunk_size_words - overlap_words, 1)
        while i < len(words):
            chunk = " ".join(words[i:i + chunk_size_words])
            if chunk.strip():
                chunks.append(chunk.strip())
            i += step
        return chunks

    def _build_crawl_manifest(
        self,
        base_domain: str,
        base_url: str,
        crawled_pages: List[PageEvidence],
        total_discovered: int,
        sitemap_found: bool,
        sitemap_url: Optional[str],
        robots_txt_found: bool,
        robots_txt_content: Optional[str],
        broken_links: List[Dict[str, str]],
        sitemap_urls: Optional[List[str]] = None,
        target_max_pages: int = 10,
        discovery_truncated: bool = False,
        discovered_urls: Optional[List[str]] = None,
    ) -> CrawlManifest:
        title_map: Dict[str, List[str]] = {}
        desc_map: Dict[str, List[str]] = {}
        missing_h1: List[str] = []
        missing_meta: List[str] = []
        missing_schema: List[str] = []
        total_words = 0
        total_ttfb = 0.0

        for p in crawled_pages:
            total_words += p.word_count
            total_ttfb += p.ttfb_ms
            if p.title:
                title_map.setdefault(p.title.strip(), []).append(p.url)
            if p.meta_description:
                desc_map.setdefault(p.meta_description.strip(), []).append(p.url)
            else:
                missing_meta.append(p.url)
            if not p.h1:
                missing_h1.append(p.url)
            if not p.schema_types:
                missing_schema.append(p.url)

        duplicate_titles = {t: urls for t, urls in title_map.items() if len(urls) > 1}
        duplicate_descriptions = {d: urls for d, urls in desc_map.items() if len(urls) > 1}

        avg_ttfb = round(total_ttfb / max(len(crawled_pages), 1), 1)

        # Orphan detection: Sitemap URLs that receive 0 internal links from crawled pages
        s_urls = list(sitemap_urls or [])
        internal_destinations = {link for p in crawled_pages for link in p.internal_links}
        orphan_urls = [u for u in s_urls if u not in internal_destinations and u != base_url]

        # Redirect chains collection
        all_redirect_chains = [
            {"initial_url": p.url, "final_url": p.final_url or p.url, "hops": p.redirect_chain, "hop_count": len(p.redirect_chain)}
            for p in crawled_pages if p.redirect_chain
        ]

        # Crawl budget and inventory accounting
        urls_discovered_cnt = max(total_discovered, len(crawled_pages))
        urls_crawled_cnt = len(crawled_pages)
        urls_skipped_cnt = max(0, urls_discovered_cnt - urls_crawled_cnt)
        crawled_urls_set = {p.url for p in crawled_pages}
        all_discovered = list(discovered_urls or []) if discovered_urls else list(crawled_urls_set)
        untested_urls = [u for u in all_discovered if u not in crawled_urls_set]
        url_cov_pct = round((urls_crawled_cnt / max(urls_discovered_cnt, 1)) * 100.0, 1)
        # A capped/truncated discovery inventory is never a full-site crawl,
        # even when every URL discovered before the cap was analyzed.
        samp_status = (
            "FULL_CRAWL"
            if urls_crawled_cnt >= urls_discovered_cnt and not discovery_truncated
            else "SAMPLED_AUDIT"
        )

        crawl_inventory = {
            "seed_urls": [base_url],
            "discovered_via_sitemap": list(s_urls),
            "discovered_via_sitemap_count": len(s_urls),
            "discovered_via_links": max(0, urls_discovered_cnt - len(s_urls)),
            "discovered_total": urls_discovered_cnt,
            "eligible_total": urls_discovered_cnt,
            "total_unique_discovered": urls_discovered_cnt,
            "total_queued": urls_discovered_cnt,
            "total_attempted": urls_crawled_cnt + len(broken_links),
            "total_crawled_tested": urls_crawled_cnt,
            "tested_pages": urls_crawled_cnt,
            "total_rendered": sum(1 for p in crawled_pages if p.render_mode in ("playwright_js", "firecrawl_js")),
            "rendered_pages": sum(1 for p in crawled_pages if p.render_mode in ("playwright_js", "firecrawl_js")),
            "total_untested": len(untested_urls),
            "untested_pages": len(untested_urls),
            "total_redirects": len(all_redirect_chains),
            "total_errors": len(broken_links),
            "failed_pages": len(broken_links),
            "url_coverage_pct": url_cov_pct,
            "coverage_denominator": "eligible_total",
            "sampling_status": samp_status,
            "seed_urls_count": 1,
            "tested_urls": [p.url for p in crawled_pages],
            "untested_urls": untested_urls[:100],
        }

        crawl_budget = {
            "urls_discovered": urls_discovered_cnt,
            "urls_allowed": target_max_pages,
            "urls_crawled": urls_crawled_cnt,
            "urls_skipped": urls_skipped_cnt,
            "url_coverage_pct": url_cov_pct,
            "sampling_status": samp_status,
            "skip_reasons": {
                "budget_cap_reached": max(0, urls_skipped_cnt - len(broken_links)),
                "failed_or_broken": len(broken_links)
            },
            "discovery_truncated": discovery_truncated,
        }

        role_labels = {
            "homepage": "homepage",
            "commercial": "primary commercial",
            "high_intent": "high-intent",
            "proof": "proof or about",
            "other": "additional",
        }
        seen_roles: List[str] = []
        commercial_seen = 0
        for page in crawled_pages:
            role = self._url_role(page.url)
            if role == "commercial":
                commercial_seen += 1
                label = "primary commercial" if commercial_seen == 1 else "secondary commercial"
            else:
                label = role_labels.get(role, "additional")
            if label not in seen_roles:
                seen_roles.append(label)
        required_roles = ["homepage", "primary commercial", "high-intent", "secondary commercial", "proof or about"]
        missing_roles = [role for role in required_roles if role not in seen_roles]
        sitemap_count = len(s_urls)
        floor_note = (
            " The sitemap listing stopped at the discovery cap, so the discovered count is a floor, not the size of the site."
            if discovery_truncated else ""
        )
        sampling_note = (
            f"This run analyzed {len(crawled_pages)} URL"
            f"{'' if len(crawled_pages) == 1 else 's'}"
            f" of {urls_discovered_cnt} discovered ({url_cov_pct}% URL coverage).{floor_note} "
            f"Sampling status: {samp_status}. "
            f"Pages were selected for these roles: {', '.join(seen_roles) or 'general pages'}. "
            f"Sitemap listed {sitemap_count} URL{'' if sitemap_count == 1 else 's'}. "
            f"Findings are page-verified, sample-verified, origin-verified, or site-inferred. "
            f"This run does not claim untested URLs were rendered."
        )
        if missing_roles:
            sampling_note += f" Roles not fetched in this budget: {', '.join(missing_roles)}."

        crawl_health = {
            "total_pages_crawled": len(crawled_pages),
            "sampling_note": sampling_note,
            "sampling_status": samp_status,
            "url_coverage_pct": url_cov_pct,
            "crawl_inventory": crawl_inventory,
            "roles_filled": seen_roles,
            "roles_missing": missing_roles,
            "sitemap_url_count": sitemap_count,
            "total_pages_discovered": urls_discovered_cnt,
            "discovery_truncated": discovery_truncated,
            "sitemap_status": "Verified" if sitemap_found else "Missing / Inaccessible",
            "robots_txt_status": "Configured" if robots_txt_found else "Missing / Inaccessible",
            "duplicate_titles_count": len(duplicate_titles),
            "duplicate_titles": duplicate_titles,
            "duplicate_descriptions_count": len(duplicate_descriptions),
            "duplicate_descriptions": duplicate_descriptions,
            "missing_h1_count": len(missing_h1),
            "missing_h1_urls": missing_h1,
            "missing_meta_count": len(missing_meta),
            "missing_meta_urls": missing_meta,
            "missing_schema_count": len(missing_schema),
            "missing_schema_urls": missing_schema,
            "broken_links_count": len(broken_links),
            "broken_links": broken_links,
            "avg_ttfb_ms": avg_ttfb,
            "total_words_across_site": total_words,
            "orphan_pages_count": len(orphan_urls),
            "redirect_chains_count": len(all_redirect_chains),
            "crawl_budget": crawl_budget,
            "page_breakdown": [
                {
                    "url": p.url,
                    "type": p.page_type,
                    "status": p.status_code,
                    "words": p.word_count,
                    "ttfb_ms": p.ttfb_ms,
                    "render_blocking_count": p.lab_performance.render_blocking_count if p.lab_performance else 0,
                    "fcp_ms": p.lab_performance.fcp_ms if p.lab_performance else None,
                    "transferred_kb": p.lab_performance.total_transferred_kb if p.lab_performance else 0.0,
                    "schema_count": len(p.schema_types),
                    "has_redirects": p.is_redirected,
                    "redirect_hops": len(p.redirect_chain)
                }
                for p in crawled_pages
            ]
        }

        return CrawlManifest(
            domain=base_domain,
            base_url=base_url,
            total_pages_discovered=urls_discovered_cnt,
            pages=crawled_pages,
            sitemap_found=sitemap_found,
            sitemap_url=sitemap_url,
            robots_txt_found=robots_txt_found,
            robots_txt_content=robots_txt_content,
            crawl_health=crawl_health,
            redirect_chains=all_redirect_chains,
            crawl_budget=crawl_budget,
            sitemap_urls=s_urls,
            orphan_urls=orphan_urls,
            crawl_inventory=crawl_inventory,
            url_coverage_pct=url_cov_pct,
            sampling_status=samp_status,
            discovered_urls=all_discovered,
            discovered_via_sitemap=s_urls,
            untested_discovered_urls=untested_urls[:100],
        )
