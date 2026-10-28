"""
Unit tests for Google Rich Results Schema Validator and X-Robots-Tag Inspection.
"""
import pytest
from bs4 import BeautifulSoup
from app.domain.models import PageEvidence
from app.evidence.store import EvidenceStore
from app.crawl.analyzers.meta import analyze_meta_tags
from app.seo.analyzers.schema_validator import analyze_schema_rich_results, validate_schema_entity


def test_meta_analyzer_extracts_x_robots_tag():
    evidence_store = EvidenceStore(run_id="test_run")
    html = "<html><head><title>Test Page</title></head><body><h1>Content</h1></body></html>"
    soup = BeautifulSoup(html, "lxml")
    
    # Header with noindex
    headers = {"X-Robots-Tag": "noindex, nofollow", "Content-Type": "text/html"}
    res = analyze_meta_tags(soup, "https://example.com/test", evidence_store, resp_headers=headers)
    
    assert res["x_robots_tag"] == "noindex, nofollow"
    assert "noindex" in (res["robots_meta"] or "").lower()
    
    # Verify evidence registered
    header_ev = [e for e in evidence_store.get_all() if e.source_type == "header"]
    assert len(header_ev) == 1
    assert "noindex" in header_ev[0].text.lower()


def test_schema_validator_organization_success_and_warnings():
    valid_org = {
        "@type": "Organization",
        "name": "Acme Corp",
        "url": "https://acme.com",
        "logo": "https://acme.com/logo.png",
        "sameAs": ["https://twitter.com/acme"]
    }
    issues = validate_schema_entity(valid_org, "https://acme.com")
    assert len(issues) == 0

    incomplete_org = {
        "@type": "Organization",
        "name": "Acme Corp",
        # missing url (ERROR), missing logo (WARNING), missing sameAs (WARNING)
    }
    issues = validate_schema_entity(incomplete_org, "https://acme.com")
    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]
    assert len(errors) == 1
    assert errors[0].field == "url"
    assert len(warnings) == 2


def test_schema_validator_product():
    product_without_offers = {
        "@type": "Product",
        "name": "Super Widget",
        "description": "A high-performance widget"
    }
    issues = validate_schema_entity(product_without_offers, "https://acme.com/product")
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 1
    assert "offers" in errors[0].field


def test_schema_validator_faq_page():
    faq = {
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "How does Dristik work?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "It uses deterministic evidence and a 105-specialist DAG across 7 workflows."
                }
            },
            {
                "@type": "Question",
                "name": "What is the cost?",
                "acceptedAnswer": None  # Invalid answer
            }
        ]
    }
    issues = validate_schema_entity(faq, "https://acme.com/faq")
    errors = [i for i in issues if i.severity == "ERROR"]
    assert len(errors) == 1
    assert "acceptedAnswer" in errors[0].field


def test_sitewide_schema_rich_results_rollup():
    p1 = PageEvidence(
        url="https://example.com/",
        raw_schema=[{
            "@type": "Organization",
            "name": "Example Corp",
            "url": "https://example.com"
        }]
    )
    p2 = PageEvidence(
        url="https://example.com/blog/1",
        raw_schema=[{
            "@type": "Article",
            "headline": "SEO in 2026",
            "image": "https://example.com/img.jpg",
            "datePublished": "2026-09-20"
        }]
    )
    p3 = PageEvidence(
        url="https://example.com/about",
        raw_schema=[]
    )

    report = analyze_schema_rich_results([p1, p2, p3])
    assert report.total_pages_with_schema == 2
    assert report.total_entities_detected == 2
    assert report.valid_entities_count == 2
    assert report.entities_with_errors_count == 0
    assert "Organization" in report.detected_types
    assert "Article" in report.detected_types
    assert "not an entity-graph quality score" in report.summary
    assert "satisfy Google Rich Results requirements" not in report.summary
