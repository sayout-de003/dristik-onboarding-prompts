from app.crawl.crawler import CrawlerService
from app.domain.models import CrawlInventory, CrawlManifest, PageEvidence


def test_truncated_discovery_inventory_cannot_be_labeled_full_crawl():
    root = "https://example.com/"
    manifest = CrawlerService()._build_crawl_manifest(
        base_domain="example.com",
        base_url=root,
        crawled_pages=[PageEvidence(url=root)],
        total_discovered=1,
        sitemap_found=False,
        sitemap_url=None,
        robots_txt_found=False,
        robots_txt_content=None,
        broken_links=[],
        sitemap_urls=[],
        target_max_pages=1,
        discovery_truncated=True,
        discovered_urls=[root],
    )
    assert manifest.sampling_status == "SAMPLED_AUDIT"
    assert manifest.crawl_health["sampling_status"] == "SAMPLED_AUDIT"
    assert manifest.crawl_health["discovery_truncated"] is True
    assert "floor, not the size of the site" in manifest.crawl_health["sampling_note"]


def test_failed_robots_fetch_is_not_reported_as_definitely_missing():
    root = "https://example.com/"
    manifest = CrawlerService()._build_crawl_manifest(
        base_domain="example.com",
        base_url=root,
        crawled_pages=[PageEvidence(url=root)],
        total_discovered=1,
        sitemap_found=False,
        sitemap_url=None,
        robots_txt_found=False,
        robots_txt_content=None,
        broken_links=[],
        sitemap_urls=[],
        target_max_pages=1,
        discovery_truncated=False,
        discovered_urls=[root],
    )
    assert manifest.crawl_health["robots_txt_status"] == "Missing / Inaccessible"



def test_unassessed_crawl_coverage_is_not_defaulted_to_full_coverage():
    manifest = CrawlManifest(domain="example.com", pages=[])
    inventory = CrawlInventory()
    assert manifest.url_coverage_pct is None
    assert manifest.sampling_status == "NOT_ASSESSED"
    assert inventory.url_coverage_pct is None
    assert inventory.sampling_status == "NOT_ASSESSED"
    assert inventory.calculate_coverage() is None
