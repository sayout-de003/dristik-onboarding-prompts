from contextlib import asynccontextmanager

import pytest

import app.crawl.crawler as crawler_module
from app.crawl.crawler import CrawlerService


class FakeResponse:
    def __init__(self, body: bytes, status_code: int = 200, content_type: str = "application/xml"):
        self.body = body
        self.status_code = status_code
        self.headers = {"content-type": content_type, "content-length": str(len(body))}

    async def aiter_bytes(self):
        if self.body:
            yield self.body


class FakeClient:
    def __init__(self, responses):
        self.responses = responses

    def stream(self, method, url, **kwargs):
        response = self.responses.get(url, FakeResponse(b"", status_code=404, content_type="text/plain"))

        @asynccontextmanager
        async def manager():
            yield response

        return manager()


@pytest.mark.asyncio
async def test_nested_sitemap_index_is_parsed_with_bounded_reads(monkeypatch):
    monkeypatch.setattr(crawler_module, "is_safe_url", lambda _url: (True, "test fixture"))
    index = b"""<?xml version="1.0"?><sitemapindex><sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap></sitemapindex>"""
    pages = b"""<?xml version="1.0"?><urlset><url><loc>https://example.com/</loc></url><url><loc>https://example.com/about</loc></url></urlset>"""
    client = FakeClient({
        "https://example.com/sitemap.xml": FakeResponse(index),
        "https://example.com/sitemap-pages.xml": FakeResponse(pages),
    })

    found, sitemap_url, urls, truncated = await CrawlerService()._fetch_sitemap_urls(
        base_origin="https://example.com",
        base_domain="example.com",
        declared_sitemaps=["https://example.com/sitemap.xml"],
        client=client,
        max_sitemap_urls=10,
    )
    assert found is True
    assert sitemap_url == "https://example.com/sitemap.xml"
    assert urls == ["https://example.com", "https://example.com/about"]
    assert truncated is False


@pytest.mark.asyncio
async def test_malformed_sitemap_is_not_reported_as_verified(monkeypatch):
    monkeypatch.setattr(crawler_module, "is_safe_url", lambda _url: (True, "test fixture"))
    client = FakeClient({
        "https://example.com/sitemap.xml": FakeResponse(b"<urlset><loc>broken"),
    })
    found, sitemap_url, urls, _truncated = await CrawlerService()._fetch_sitemap_urls(
        base_origin="https://example.com",
        base_domain="example.com",
        declared_sitemaps=["https://example.com/sitemap.xml"],
        client=client,
        max_sitemap_urls=10,
    )
    assert found is False
    assert sitemap_url is None
    assert urls == []


@pytest.mark.asyncio
async def test_sitemap_discovery_cap_is_explicitly_truncated(monkeypatch):
    monkeypatch.setattr(crawler_module, "is_safe_url", lambda _url: (True, "test fixture"))
    index = b"""<sitemapindex><sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap></sitemapindex>"""
    pages = b"""<urlset><url><loc>https://example.com/a</loc></url><url><loc>https://example.com/b</loc></url></urlset>"""
    client = FakeClient({
        "https://example.com/sitemap.xml": FakeResponse(index),
        "https://example.com/sitemap-pages.xml": FakeResponse(pages),
    })
    found, _sitemap_url, urls, truncated = await CrawlerService()._fetch_sitemap_urls(
        base_origin="https://example.com",
        base_domain="example.com",
        declared_sitemaps=["https://example.com/sitemap.xml"],
        client=client,
        max_sitemap_urls=1,
    )
    assert found is True
    assert len(urls) == 1
    assert truncated is True
