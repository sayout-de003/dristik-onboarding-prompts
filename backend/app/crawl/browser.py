"""
Enterprise Headless Browser Rendering Service
Executes dynamic client-side JavaScript, waiting for database-driven content
to hydrate into the DOM. Uses high-performance asset blocking (images, media, fonts)
for fast execution and minimal CPU/memory overhead.
"""
import os
import signal
import time
import asyncio
import logging
from typing import Optional, Tuple, Dict, Any
from app.core.config import settings
from app.core.security.ssrf import is_safe_url

logger = logging.getLogger("dristik.browser")

# Graceful detection of playwright package
_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright, Browser, Playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False


class BrowserRenderService:
    _playwright: Optional[Any] = None
    _browser: Optional[Any] = None
    _lock = asyncio.Lock()
    # One print job at a time. A second download waits instead of piling
    # onto a Chromium process that is already inside page.pdf().
    _render_lock = asyncio.Lock()

    @classmethod
    def is_available(cls) -> bool:
        """Returns True if Playwright is installed and enabled in settings."""
        return _PLAYWRIGHT_AVAILABLE and settings.PLAYWRIGHT_ENABLED

    @classmethod
    async def get_browser(cls) -> Optional[Any]:
        if not cls.is_available():
            return None

        async with cls._lock:
            if cls._browser is None or not cls._browser.is_connected():
                try:
                    cls._playwright = await async_playwright().start()
                    cls._browser = await cls._playwright.chromium.launch(
                        headless=settings.PLAYWRIGHT_HEADLESS,
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                            "--disable-extensions",
                        ]
                    )
                except Exception as exc:
                    logger.warning("Failed to launch headless Chromium: %s", exc)
                    cls._browser = None
                    return None
            return cls._browser

    @classmethod
    async def render_page(
        cls,
        url: str,
        timeout_ms: Optional[int] = None
    ) -> Tuple[Optional[str], int, float, Dict[str, str], Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """
        Renders a page using headless Chromium, waiting for DOM hydration.
        Returns: (html_content, status_code, ttfb_ms, headers, error_msg, inner_text, perf_data)
        inner_text is document.body.innerText — what a person can actually read.
        perf_data contains W3C Navigation Timing Level 2 and resource footprint.
        """
        if not cls.is_available():
            return None, 0, 0.0, {}, "playwright_not_installed", None, None

        start_time = time.time()
        timeout = timeout_ms or settings.PLAYWRIGHT_TIMEOUT_MS

        browser = await cls.get_browser()
        if not browser:
            return None, 0, 0.0, {}, "browser_launch_failed", None, None

        context = None
        page = None
        blocked_unsafe_request = False
        try:
            context = await browser.new_context(
                user_agent=settings.USER_AGENT,
                viewport={"width": 1440, "height": 900},
                ignore_https_errors=True
            )
            page = await context.new_page()

            # Enterprise Optimization: Block heavy media and tracking assets
            async def filter_route(route):
                nonlocal blocked_unsafe_request
                req = route.request
                rtype = req.resource_type
                # Abort intentionally excluded resources before DNS validation; they
                # will not be fetched and therefore do not need an egress lookup.
                if rtype in ["image", "media", "font"]:
                    await route.abort()
                    return
                if any(t in req.url.lower() for t in ["google-analytics", "googletagmanager", "hotjar", "facebook.net", "clarity.ms"]):
                    await route.abort()
                    return
                if settings.SSRF_PROTECTION_ENABLED:
                    # Validate every request that will actually be sent, including
                    # top-level navigations, redirects, scripts, and XHR/fetch calls.
                    try:
                        safe, reason = await asyncio.wait_for(
                            asyncio.to_thread(is_safe_url, req.url),
                            timeout=3.0,
                        )
                    except asyncio.TimeoutError:
                        blocked_unsafe_request = True
                        logger.warning("Blocked browser request after SSRF validation timeout: %s", req.url)
                        await route.abort("blockedbyclient")
                        return
                    if not safe:
                        blocked_unsafe_request = True
                        logger.warning("Blocked unsafe browser request %s: %s", req.url, reason)
                        await route.abort("blockedbyclient")
                        return
                await route.continue_()

            await page.route("**/*", filter_route)

            # networkidle hangs on long-polling/WebGL sites; DOM + a short hydrate wait is enough
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            status_code = response.status if response else 200
            ttfb_ms = (time.time() - start_time) * 1000

            try:
                await page.wait_for_selector("main, article, h1, [role='main'], body", timeout=4000)
            except Exception:
                pass

            # Dismiss cookie / protocol gates that hide the real page after hydration
            for selector in [
                "button:has-text('Accept')",
                "button:has-text('Accept Protocol')",
                "button:has-text('I agree')",
                "button:has-text('Allow')",
                "#cookie-banner button",
                "[id*='cookie'] button",
            ]:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() and await btn.is_visible():
                        await btn.click(timeout=800)
                        break
                except Exception:
                    continue

            try:
                await page.wait_for_timeout(600)
            except Exception:
                pass

            html_content = await page.content()
            inner_text = None
            try:
                inner_text = await page.evaluate(
                    """() => {
                        const main = document.querySelector('main, [role=main], article, #content, #main');
                        const root = main || document.body;
                        return root ? (root.innerText || root.textContent || '') : '';
                    }"""
                )
            except Exception:
                inner_text = None

            # Extract Navigation Timing Level 2 and Resource Timings for true TTFB and Lab CWV
            perf_data = None
            try:
                perf_data = await page.evaluate(
                    """() => {
                        try {
                            const nav = performance.getEntriesByType('navigation')[0] || {};
                            const paint = performance.getEntriesByType('paint') || [];
                            const resources = performance.getEntriesByType('resource') || [];

                            const fp = paint.find(p => p.name === 'first-paint');
                            const fcp = paint.find(p => p.name === 'first-contentful-paint');

                            let ttfb = 0;
                            if (nav.responseStart && nav.requestStart) {
                                ttfb = Math.max(0, nav.responseStart - nav.requestStart);
                            } else if (nav.responseStart) {
                                ttfb = Math.max(0, nav.responseStart);
                            }

                            const dns = (nav.domainLookupEnd && nav.domainLookupStart) ? Math.max(0, nav.domainLookupEnd - nav.domainLookupStart) : 0;
                            const tcp = (nav.connectEnd && nav.connectStart) ? Math.max(0, nav.connectEnd - nav.connectStart) : 0;
                            const tls = (nav.secureConnectionStart && nav.connectEnd) ? Math.max(0, nav.connectEnd - nav.secureConnectionStart) : 0;
                            const download = (nav.responseEnd && nav.responseStart) ? Math.max(0, nav.responseEnd - nav.responseStart) : 0;
                            const dom_content_loaded = nav.domContentLoadedEventEnd || 0;
                            const load_event = nav.loadEventEnd || 0;

                            let js_bytes = 0, css_bytes = 0, img_bytes = 0, font_bytes = 0, total_bytes = 0;
                            const counts = { document: 1, script: 0, stylesheet: 0, image: 0, font: 0, other: 0 };
                            const render_blocking = [];
                            const third_party_scripts = [];
                            const pageHost = window.location.hostname;

                            resources.forEach(r => {
                                const transfer = r.transferSize || r.encodedBodySize || 0;
                                total_bytes += transfer;
                                const itype = (r.initiatorType || 'other').toLowerCase();
                                if (itype === 'script') {
                                    js_bytes += transfer;
                                    counts.script = (counts.script || 0) + 1;
                                } else if (itype === 'css' || itype === 'link') {
                                    css_bytes += transfer;
                                    counts.stylesheet = (counts.stylesheet || 0) + 1;
                                } else if (itype === 'img' || itype === 'image') {
                                    img_bytes += transfer;
                                    counts.image = (counts.image || 0) + 1;
                                } else if (itype === 'font') {
                                    font_bytes += transfer;
                                    counts.font = (counts.font || 0) + 1;
                                } else {
                                    counts.other = (counts.other || 0) + 1;
                                }

                                if (r.renderBlockingStatus === 'blocking') {
                                    render_blocking.push({ url: r.name, initiator: itype, duration_ms: Math.round(r.duration || 0) });
                                }

                                try {
                                    const u = new URL(r.name);
                                    if (u.hostname !== pageHost && !u.hostname.endsWith('.' + pageHost)) {
                                        if (itype === 'script') {
                                            third_party_scripts.push({ url: r.name, hostname: u.hostname, transfer_bytes: transfer });
                                        }
                                    }
                                } catch(e) {}
                            });

                            return {
                                ttfb_ms: Math.round(ttfb * 10) / 10,
                                dns_ms: Math.round(dns * 10) / 10,
                                tcp_ms: Math.round(tcp * 10) / 10,
                                tls_ms: Math.round(tls * 10) / 10,
                                download_ms: Math.round(download * 10) / 10,
                                dom_content_loaded_ms: Math.round(dom_content_loaded * 10) / 10,
                                load_event_ms: Math.round(load_event * 10) / 10,
                                fcp_ms: fcp ? Math.round(fcp.startTime * 10) / 10 : null,
                                total_transferred_bytes: total_bytes,
                                js_bytes: js_bytes,
                                css_bytes: css_bytes,
                                img_bytes: img_bytes,
                                font_bytes: font_bytes,
                                request_counts: counts,
                                total_requests: resources.length + 1,
                                render_blocking: render_blocking,
                                third_party_scripts: third_party_scripts
                            };
                        } catch(err) {
                            return null;
                        }
                    }"""
                )
            except Exception:
                perf_data = None

            if perf_data and perf_data.get("ttfb_ms") and perf_data["ttfb_ms"] > 0:
                ttfb_ms = perf_data["ttfb_ms"]

            resp_headers = {"x-crawler": "playwright-local-js"}

            return html_content, status_code, ttfb_ms, resp_headers, None, inner_text, perf_data

        except Exception as e:
            ttfb_ms = (time.time() - start_time) * 1000
            return None, 0, ttfb_ms, {}, str(e), None, None

        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass

    @classmethod
    def _kill_process_tree(cls, pid: int) -> None:
        """SIGKILL a process and its children. Used when Chromium ignores cancellation."""
        if os.path.exists("/proc"):
            try:
                children: list[int] = []
                for entry in os.listdir("/proc"):
                    if not entry.isdigit():
                        continue
                    try:
                        stat = open(f"/proc/{entry}/stat", "r", encoding="utf-8", errors="replace").read()
                        ppid = int(stat.rsplit(")", 1)[1].split()[1])
                    except (OSError, IndexError, ValueError):
                        continue
                    if ppid == pid:
                        children.append(int(entry))
                for child in children:
                    cls._kill_process_tree(child)
            except Exception:
                pass
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    @classmethod
    def _kill_playwright_driver(cls, playwright: Any) -> None:
        try:
            proc = playwright._impl_obj._connection._transport._proc
            pid = getattr(proc, "pid", None)
        except Exception:
            return
        if pid:
            cls._kill_process_tree(int(pid))

    @classmethod
    async def _discard_browser(cls) -> None:
        """Drop a wedged Chromium so the next PDF download can launch a fresh one."""
        async with cls._lock:
            browser = cls._browser
            playwright = cls._playwright
            cls._browser = None
            cls._playwright = None
        if playwright is not None:
            cls._kill_playwright_driver(playwright)
        for closer in (
            getattr(browser, "close", None),
            getattr(playwright, "stop", None),
        ):
            if closer is None:
                continue
            try:
                result = closer()
                if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                    task = asyncio.create_task(result)
                    await asyncio.wait({task}, timeout=2)
            except Exception:
                pass

    @classmethod
    async def render_pdf(cls, html: str, timeout_ms: int = 90000) -> Optional[bytes]:
        """
        Renders standalone HTML to a PDF using headless Chromium.
        Honors the document's CSS @page size/margins and preserves backgrounds.
        Returns None when the browser is unavailable, rendering fails, or the
        print job exceeds timeout_ms. A timed-out job is killed so it cannot
        block later downloads.
        """
        async with cls._render_lock:
            browser = await cls.get_browser()
            if browser is None:
                return None
            context = None
            page = None
            pdf_task: Optional[asyncio.Task] = None
            timed_out = False
            try:
                context = await browser.new_context()
                page = await context.new_page()
                content_timeout = timeout_ms if timeout_ms and timeout_ms > 0 else 30000
                await page.set_content(html, wait_until="domcontentloaded", timeout=content_timeout)
                await page.emulate_media(media="print")
                # System fonts only. document.fonts.ready is not awaited: a font
                # that never settles would block the print, and cancelling that
                # Playwright call does not return on Python 3.12.
                pdf_task = asyncio.create_task(page.pdf(
                    prefer_css_page_size=True,
                    print_background=True,
                ))
                if timeout_ms and timeout_ms > 0:
                    done, _pending = await asyncio.wait({pdf_task}, timeout=timeout_ms / 1000.0)
                    if pdf_task not in done:
                        timed_out = True
                        logger.warning(
                            "PDF render exceeded %ss; recycling headless browser",
                            timeout_ms / 1000.0,
                        )
                        return None
                else:
                    await pdf_task
                exc = pdf_task.exception()
                if exc is not None:
                    logger.warning("Failed to render PDF with Playwright: %s", exc)
                    return None
                return pdf_task.result()
            except Exception as exc:
                logger.warning("Failed to render PDF with Playwright: %s", exc)
                return None
            finally:
                if timed_out or (pdf_task is not None and not pdf_task.done()):
                    if pdf_task is not None and not pdf_task.done():
                        def _swallow_pdf_task(task: asyncio.Task) -> None:
                            if task.cancelled():
                                return
                            try:
                                task.exception()
                            except Exception:
                                pass
                        pdf_task.add_done_callback(_swallow_pdf_task)
                        pdf_task.cancel()
                    # page.close() waits on the stuck print. Kill the browser instead.
                    await cls._discard_browser()
                else:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    if context is not None:
                        try:
                            await context.close()
                        except Exception:
                            pass

    @classmethod
    async def shutdown(cls):
        """Cleanly releases browser and playwright resources."""
        async with cls._lock:
            if cls._browser:
                try:
                    await cls._browser.close()
                except Exception:
                    pass
                cls._browser = None
            if cls._playwright:
                try:
                    await cls._playwright.stop()
                except Exception:
                    pass
                cls._playwright = None
