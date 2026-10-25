"""Real browser-backed page rendering for audits.

This crawler never fabricates a successful response. Browser startup, navigation,
and rendering failures are returned as explicit unavailable states for callers to
surface or fall back from deliberately.
"""
from typing import Any, Dict
from urllib.parse import urlparse

from app.seo.audit.crawlers.base import BaseCrawler


class PlaywrightCrawler(BaseCrawler):
    def __init__(
        self,
        *,
        timeout_ms: int = 30000,
        viewport_width: int = 1440,
        viewport_height: int = 900,
        headless: bool = True,
    ) -> None:
        self.timeout_ms = timeout_ms
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.headless = headless

    async def fetch_page(self, url: str) -> Dict[str, Any]:
        """Navigate with Chromium and return actual rendered DOM or an explicit failure."""
        parsed = urlparse(str(url or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return {
                "url": url,
                "state": "INVALID_URL",
                "status_code": None,
                "rendered": False,
                "error": "Only absolute HTTP(S) URLs can be rendered.",
            }

        browser = None
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=self.headless)
                page = await browser.new_page(
                    viewport={
                        "width": self.viewport_width,
                        "height": self.viewport_height,
                    }
                )
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )
                # Some pages keep long-lived requests open. A bounded best-effort
                # network-idle wait improves DOM stability without blocking forever.
                try:
                    await page.wait_for_load_state("networkidle", timeout=min(3000, self.timeout_ms))
                except Exception:
                    pass

                rendered_dom = await page.content()
                title = await page.title()
                status_code = response.status if response is not None else None
                headers = await response.all_headers() if response is not None else {}
                final_url = page.url
                return {
                    "url": final_url,
                    "requested_url": url,
                    "state": "RENDERED" if rendered_dom else "EMPTY_RENDER",
                    "status_code": status_code,
                    "headers": headers,
                    "title": title,
                    "html": rendered_dom,
                    "rendered_dom": rendered_dom,
                    "rendered": bool(rendered_dom),
                    "viewport": {
                        "width": self.viewport_width,
                        "height": self.viewport_height,
                    },
                    "http_error": bool(status_code is not None and status_code >= 400),
                    "error": None if rendered_dom else "The browser returned an empty DOM.",
                }
        except Exception as exc:
            return {
                "url": url,
                "requested_url": url,
                "state": "UNAVAILABLE",
                "status_code": None,
                "headers": {},
                "html": None,
                "rendered_dom": None,
                "rendered": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        finally:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass
