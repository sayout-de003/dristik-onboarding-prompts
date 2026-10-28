from types import SimpleNamespace
from contextlib import asynccontextmanager

import pytest

from app.crawl.crawler import CrawlerService
from app.crawl.response_limits import ResponseTooLargeError, read_response_limited


class FakeStreamResponse:
    def __init__(self, chunks, content_length=None):
        self.chunks = chunks
        self.headers = {}
        if content_length is not None:
            self.headers["content-length"] = str(content_length)

    async def aiter_bytes(self):
        for chunk in self.chunks:
            yield chunk


@pytest.mark.asyncio
async def test_response_limit_accepts_body_at_limit():
    response = FakeStreamResponse([b"abc", b"de"])
    assert await read_response_limited(response, 5) == b"abcde"


@pytest.mark.asyncio
async def test_response_limit_rejects_oversized_stream_even_without_length():
    response = FakeStreamResponse([b"abc", b"def"])
    with pytest.raises(ResponseTooLargeError, match="configured 5-byte limit"):
        await read_response_limited(response, 5)


@pytest.mark.asyncio
async def test_response_limit_rejects_declared_oversize_before_reading():
    response = FakeStreamResponse([], content_length=100)
    with pytest.raises(ResponseTooLargeError, match="configured 5-byte limit"):
        await read_response_limited(response, 5)


@pytest.mark.asyncio
async def test_response_limit_rejects_non_positive_limit():
    with pytest.raises(ValueError, match="must be positive"):
        await read_response_limited(FakeStreamResponse([]), 0)



@pytest.mark.asyncio
async def test_oversized_direct_response_does_not_trigger_second_renderer(monkeypatch):
    class FakeHTTPResponse(FakeStreamResponse):
        status_code = 200
        encoding = "utf-8"
        headers = {"content-length": "100"}

    class FakeClient:
        @asynccontextmanager
        async def stream(self, method, url):
            yield FakeHTTPResponse([], content_length=6 * 1024 * 1024)

    import app.crawl.crawler as crawler_module
    monkeypatch.setattr(crawler_module, "is_safe_url", lambda url: (True, "test-safe"))
    crawler = CrawlerService()

    async def should_not_render(*args, **kwargs):
        raise AssertionError("oversized response must not trigger renderer fallback")

    monkeypatch.setattr(crawler, "_js_render_page", should_not_render)
    result = await crawler._fetch_page_with_fallbacks(
        "https://example.com/", FakeClient()
    )
    assert result[0] is None
    assert "response exceeds configured" in (result[5] or "")



@pytest.mark.asyncio
async def test_dynamic_render_rejects_unsafe_initial_url_before_provider_use(monkeypatch):
    import app.crawl.crawler as crawler_module

    monkeypatch.setattr(crawler_module.settings, "SSRF_PROTECTION_ENABLED", True)
    monkeypatch.setattr(crawler_module, "is_safe_url", lambda url: (False, "test private target"))

    def provider_must_not_be_used():
        raise AssertionError("render provider must not be called for an unsafe URL")

    monkeypatch.setattr(crawler_module.BrowserRenderService, "is_available", provider_must_not_be_used)
    crawler = CrawlerService()
    result = await crawler._js_render_page("http://127.0.0.1/", object(), 0.0)
    assert result[0] is None
    assert "SSRF blocked render target" in (result[6] or "")
