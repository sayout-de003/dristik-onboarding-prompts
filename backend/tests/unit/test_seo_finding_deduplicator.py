from app.seo.audit.findings.deduplicator import FindingDeduplicator


def test_deduplicator_normalizes_title_formatting_and_merges_evidence():
    rows = [
        {
            "category": "technical SEO",
            "title": "Missing  document-title!",
            "severity": "LOW",
            "affected_urls": ["https://example.com/a"],
            "evidence_refs": ["ev_001"],
            "description": "Title absent.",
        },
        {
            "category": "Technical SEO",
            "title": "missing document title",
            "severity": "HIGH",
            "affected_urls": ["https://example.com/b"],
            "evidence_refs": ["ev_002"],
            "recommendation": "Add a unique title.",
        },
    ]

    result = FindingDeduplicator().deduplicate(rows)

    assert len(result) == 1
    assert result[0]["severity"] == "HIGH"
    assert result[0]["affected_urls"] == [
        "https://example.com/a", "https://example.com/b"
    ]
    assert result[0]["evidence_refs"] == ["ev_001", "ev_002"]
    assert result[0]["duplicate_count"] == 1
    assert result[0]["recommendation"] == "Add a unique title."
    # Inputs are not mutated.
    assert "duplicate_count" not in rows[0]


def test_deduplicator_does_not_merge_different_categories_or_titles():
    rows = [
        {"category": "technical", "title": "Missing title", "severity": "HIGH"},
        {"category": "content", "title": "Missing title", "severity": "HIGH"},
        {"category": "technical", "title": "Missing canonical", "severity": "HIGH"},
    ]
    assert len(FindingDeduplicator().deduplicate(rows)) == 3


def test_deduplicator_rejects_non_dictionary_records():
    import pytest

    with pytest.raises(TypeError, match="each finding must be a dictionary"):
        FindingDeduplicator().deduplicate([None])
