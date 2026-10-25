"""Contract tests for deterministic report quality and deep crawl primitives."""
from __future__ import annotations

import hashlib

import pytest

from app.crawl_orchestration import DeepCrawlStore, is_public_http_target, is_same_origin, normalize_url
from app.report_quality import validate_report_payload


def evidence(url="https://example.com/", evidence_id="ev_001", scope="PAGE_VERIFIED"):
    return {
        "evidence_id": evidence_id,
        "url": url,
        "observed_at": "2026-10-25T10:00:00Z",
        "collection_method": "http_dom",
        "scope": scope,
        "snapshot_sha256": hashlib.sha256(b"snapshot").hexdigest(),
        "observation": "The document title was absent in the captured DOM.",
    }


def finding(evidence_refs=None, affected_urls=None, **overrides):
    payload = {
        "finding_id": "f_001", "title": "Missing document title",
        "severity": "HIGH", "status": "verified", "evidence_refs": evidence_refs or ["ev_001"],
        "affected_urls": affected_urls or ["https://example.com/"],
        "what_observed": "The captured DOM contains no title element.",
        "what_it_means": "The page has no explicit title element for search engines.",
        "why_it_matters": "Search results may have less useful page-specific context.",
        "how_to_fix": "Add a unique descriptive title element in the document head.",
        "how_to_verify": "Fetch the page again and assert exactly one non-empty title exists.",
    }
    payload.update(overrides)
    return payload


def test_url_normalization_drops_fragments_tracking_and_default_ports():
    assert normalize_url("HTTPS://Example.com:443/path/?utm_source=x&b=2&a=1#section") == "https://example.com/path?a=1&b=2"


def test_origin_guard_rejects_external_hosts_and_ports():
    assert is_same_origin("https://example.com/a", "https://example.com/")
    assert not is_same_origin("https://evil.example/a", "https://example.com/")
    assert not is_same_origin("https://example.com:8443/a", "https://example.com/")


def test_report_gate_accepts_traceable_finding():
    result = validate_report_payload([finding()], [evidence()])
    assert result["valid"] is True
    assert result["finding_count"] == 1


def test_report_gate_rejects_dangling_evidence():
    with pytest.raises(ValueError, match="missing evidence"):
        validate_report_payload([finding(evidence_refs=["ev_missing"])], [evidence()])


def test_report_gate_rejects_verified_claim_from_inferred_scope():
    with pytest.raises(ValueError, match="outside verified scope"):
        validate_report_payload([finding()], [evidence(scope="SITE_INFERRED")])


def test_report_gate_rejects_duplicate_findings():
    duplicate = finding(finding_id="f_002")
    with pytest.raises(ValueError, match="duplicate finding"):
        validate_report_payload([finding(), duplicate], [evidence()])


def test_score_gate_reconciles_composite_and_weights():
    score = {"composite": 80, "components": {"seo": 70, "technical": 90}, "weights": {"seo": 0.5, "technical": 0.5}}
    assert validate_report_payload([], [], score)["score"]["composite"] == 80


def test_score_gate_rejects_inconsistent_composite():
    score = {"composite": 95, "components": {"seo": 70, "technical": 90}, "weights": {"seo": 0.5, "technical": 0.5}}
    with pytest.raises(ValueError, match="does not reconcile"):
        validate_report_payload([], [], score)


def test_deep_crawl_is_resumable_and_tenant_scoped(tmp_path):
    store = DeepCrawlStore(str(tmp_path / "crawl.sqlite"))
    store.create_job("job_1", "org_a", "https://example.com/", max_pages=10, max_depth=2)
    assert store.enqueue_discovered("job_1", "org_a", ["/about", "https://other.example/x"], "https://example.com/", 0) == {"discovered": 1, "excluded": 1}
    claimed = store.claim_next("job_1", "org_a")
    assert claimed["normalized_url"] == "https://example.com/"
    assert store.recover_interrupted("job_1", "org_a") == 1
    assert store.get_job("job_1", "org_a")["remaining"] == 2
    with pytest.raises(KeyError):
        store.get_job("job_1", "org_b")


def test_deep_crawl_reports_partial_coverage_and_failed_urls(tmp_path):
    store = DeepCrawlStore(str(tmp_path / "crawl.sqlite"))
    store.create_job("job_2", "org_a", "https://example.com/")
    store.finish_url("job_2", "org_a", "https://example.com/", "FAILED", error_code="TIMEOUT")
    snapshot = store.get_job("job_2", "org_a")
    assert snapshot["failed"] == 1
    assert snapshot["partial"] is True


def test_deep_crawl_rejects_loopback_targets():
    assert not is_public_http_target("http://127.0.0.1/")



def test_report_assembly_deduplicates_canonical_finding_ids():
    from types import SimpleNamespace
    from app.report_finding_registry import canonicalize_report_findings as _report_findings

    first = SimpleNamespace(
        finding_id="find_001", title="Missing homepage H1",
        affected_urls=["https://example.com/"], severity="HIGH",
    )
    duplicate_reference = SimpleNamespace(
        finding_id="find_001", title="Homepage heading missing",
        affected_urls=["https://example.com/"], severity="HIGH",
    )
    distinct_page = SimpleNamespace(
        finding_id="find_002", title="Missing homepage H1",
        affected_urls=["https://example.com/about"], severity="HIGH",
    )
    report = SimpleNamespace(findings=[first, duplicate_reference, distinct_page])

    result = _report_findings(report)
    assert len(result) == 2
    assert [item.finding_id for item in result] == ["find_001", "find_002"]


def test_report_assembly_deduplicates_same_title_and_url_but_not_distinct_pages():
    from types import SimpleNamespace
    from app.report_finding_registry import canonicalize_report_findings as _report_findings

    report = SimpleNamespace(findings=[
        {"finding_id": "f1", "title": "Missing title tag", "url": "https://example.com/", "root_cause_category": "metadata", "how_to_fix": "Add a unique title tag"},
        {"finding_id": "f2", "title": "  Missing   title tag ", "url": "https://example.com/", "root_cause_category": "metadata", "how_to_fix": "Add a unique title tag"},
        {"finding_id": "f3", "title": "Missing title tag", "url": "https://example.com/about", "root_cause_category": "metadata", "how_to_fix": "Add a unique title tag"},
    ])

    result = _report_findings(report)
    assert len(result) == 2
