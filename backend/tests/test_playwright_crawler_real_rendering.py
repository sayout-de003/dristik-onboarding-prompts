import pytest

from app.seo.audit.crawlers.playwright_client import PlaywrightCrawler


def test_playwright_crawler_rejects_non_http_urls_without_claiming_success():
    import asyncio

    result = asyncio.run(PlaywrightCrawler().fetch_page("file:///etc/passwd"))
    assert result["state"] == "INVALID_URL"
    assert result["status_code"] is None
    assert result["rendered"] is False


@pytest.mark.asyncio
async def test_playwright_crawler_returns_actual_rendered_dom(monkeypatch):
    from playwright import async_api

    class FakeResponse:
        status = 200

        async def all_headers(self):
            return {"content-type": "text/html"}

    class FakePage:
        url = "https://example.com/final"

        async def goto(self, url, **kwargs):
            assert url == "https://example.com"
            assert kwargs["wait_until"] == "domcontentloaded"
            return FakeResponse()

        async def wait_for_load_state(self, *args, **kwargs):
            return None

        async def content(self):
            return "<html><body><h1>Actual test DOM</h1></body></html>"

        async def title(self):
            return "Example"

    class FakeBrowser:
        async def new_page(self, **kwargs):
            assert kwargs["viewport"]["width"] == 1440
            return FakePage()

        async def close(self):
            return None

    class FakeChromium:
        async def launch(self, **kwargs):
            assert kwargs["headless"] is True
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeManager:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(async_api, "async_playwright", lambda: FakeManager())
    result = await PlaywrightCrawler().fetch_page("https://example.com")
    assert result["state"] == "RENDERED"
    assert result["status_code"] == 200
    assert result["rendered"] is True
    assert "Actual test DOM" in result["rendered_dom"]
    assert result["url"] == "https://example.com/final"


@pytest.mark.asyncio
async def test_playwright_crawler_does_not_fabricate_200_when_browser_fails(monkeypatch):
    from playwright import async_api

    class FakeManager:
        async def __aenter__(self):
            raise RuntimeError("Chromium executable unavailable")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(async_api, "async_playwright", lambda: FakeManager())
    result = await PlaywrightCrawler().fetch_page("https://example.com")
    assert result["state"] == "UNAVAILABLE"
    assert result["status_code"] is None
    assert result["rendered_dom"] is None
    assert "Chromium executable unavailable" in result["error"]
