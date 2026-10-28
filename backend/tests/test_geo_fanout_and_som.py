"""
Unit & Integration Tests for Dristik GEO Phase 1 & 2 Upgrades:
- Dynamic Query Fan-Out Expansion & Intent Clustering
- Share of Model (SoM) & Competitor Displacement Metrics
- AI Crawler Access Log Analyzer (Cloudflare/Nginx)
- New GEO Pipeline API Endpoints
"""
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.intelligence.geo.benchmark_generator import benchmark_generator
from app.intelligence.geo.benchmark_runner import (
    benchmark_runner,
    EvaluatedQueryRun,
)
from app.intelligence.geo.crawler_logs import crawler_log_analyzer

client = TestClient(app)


def test_fanout_queries_attached_to_benchmark_suite():
    """Verifies that generated benchmark queries include synthetic AI engine fan-out queries."""
    suite = benchmark_generator.generate_suite(
        domain="datadog.com",
        brand_name="Datadog",
        industry="Cloud Monitoring & Observability",
        competitors=["Dynatrace", "New Relic"],
        mode="concise",
    )

    assert suite.total_queries > 0
    assert suite.total_fan_out_queries > 0

    # Ensure each query has at least 1 fan-out query modeled
    for q in suite.queries:
        assert len(q.fan_out_queries) >= 1
        for fo in q.fan_out_queries:
            assert fo.sub_query_text
            assert fo.search_intent
            assert len(fo.expected_source_types) > 0


def test_dynamic_persona_cluster_expansion():
    """Verifies dynamic persona intent clustering expands beyond baseline suites."""
    suite = benchmark_generator.generate_dynamic_cluster(
        domain="vanta.com",
        brand_name="Vanta",
        industry="Automated Compliance & Trust Management",
        competitors=["Drata", "Secureframe"],
        personas=["Enterprise Architect", "CFO & Procurement"],
        target_size=75,
    )

    assert suite.total_queries >= 70
    assert suite.matrix_grounding == "dynamic_persona_expansion"

    # Verify presence of persona-specific intents
    persona_labels = [q.category_label for q in suite.queries]
    assert any("Enterprise Architect" in label for label in persona_labels)
    assert any("CFO & Procurement" in label for label in persona_labels)


def test_share_of_model_calculation_and_displacement():
    """Verifies calculation of Share of Model (SoM), ordinal position scores, and displacements."""
    evals = [
        EvaluatedQueryRun(
            query_id="Q-01",
            category="commercial",
            query_text="Best observability tools 2026",
            engine_id="perplexity",
            engine_name="Perplexity Sonar",
            model_version="sonar",
            timestamp="2026-09-27T12:00:00Z",
            raw_response="Top tools are 1. Dynatrace 2. Datadog 3. New Relic",
            was_mentioned=True,
            mention_position=2,
            was_first_party_cited=True,
            source_domains=["dynatrace.com", "datadog.com", "g2.com"],
            status="SUCCESS",
            is_live=True,
        ),
        EvaluatedQueryRun(
            query_id="Q-02",
            category="comparative",
            query_text="Dynatrace alternatives",
            engine_id="perplexity",
            engine_name="Perplexity Sonar",
            model_version="sonar",
            timestamp="2026-09-27T12:01:00Z",
            raw_response="Leading alternative is Dynatrace itself with APM features, also Splunk.",
            was_mentioned=False,
            mention_position=None,
            was_first_party_cited=False,
            source_domains=["dynatrace.com", "splunk.com"],
            status="SUCCESS",
            is_live=True,
        ),
        EvaluatedQueryRun(
            query_id="Q-03",
            category="high_intent",
            query_text="Datadog pricing breakdown",
            engine_id="chatgpt",
            engine_name="OpenAI Search",
            model_version="gpt-4o-mini",
            timestamp="2026-09-27T12:02:00Z",
            raw_response="1. Datadog charges $15 per host for infrastructure monitoring.",
            was_mentioned=True,
            mention_position=1,
            was_first_party_cited=True,
            source_domains=["datadog.com"],
            status="SUCCESS",
            is_live=True,
        ),
    ]

    som = benchmark_runner.calculate_share_of_model(
        evaluations=evals,
        target_domain="datadog.com",
        brand_name="Datadog",
        competitors=["Dynatrace", "New Relic"],
    )

    assert som.total_evaluated_queries == 3
    # Target and competitor shares use observed target + tracked competitor mentions:
    # target=2, Dynatrace=2, New Relic=1, total=5.
    assert som.share_of_model_pct == 40.0
    # Competitor citation share is unmeasured because the competitor universe has no domains.
    assert som.first_party_citation_share_pct is None
    assert som.ordinal_distribution["rank_1"] == 1
    assert som.ordinal_distribution["rank_2_3"] == 1

    # Dynatrace share: 2 of the 5 observed target + competitor mentions.
    assert "dynatrace" in som.competitor_shares
    assert som.competitor_shares["dynatrace"] == 40.0

    # Displacements: Q-02 where Dynatrace was recommended but Datadog omitted
    assert len(som.competitor_displacements) >= 1
    disp_q2 = next((d for d in som.competitor_displacements if d["query_id"] == "Q-02"), None)
    assert disp_q2 is not None
    assert disp_q2["displacing_competitor"] == "dynatrace"
    assert disp_q2["target_mentioned"] is False


def test_crawler_log_analyzer_clf_format():
    """Verifies that the access log analyzer extracts bot traffic, detects blocks, and computes health score."""
    sample_logs = """
198.51.100.1 - - [27/Sep/2026:10:00:00 +0000] "GET /docs/pricing HTTP/2.0" 200 4520 "-" "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)"
198.51.100.2 - - [27/Sep/2026:10:01:00 +0000] "GET /enterprise HTTP/2.0" 403 520 "-" "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"
198.51.100.3 - - [27/Sep/2026:10:02:00 +0000] "GET /blog/soc2 HTTP/2.0" 200 8120 "-" "ClaudeBot/1.0; +claudebot@anthropic.com"
198.51.100.4 - - [27/Sep/2026:10:03:00 +0000] "GET /home HTTP/2.0" 200 12000 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
"""
    result = crawler_log_analyzer.analyze_logs(sample_logs)

    assert result.total_lines_parsed == 4
    assert result.total_ai_bot_hits == 3
    assert result.blocked_bot_hits == 1
    assert result.bot_breakdown.get("GPTBot") == 1
    assert result.bot_breakdown.get("PerplexityBot") == 1
    assert result.bot_breakdown.get("ClaudeBot") == 1
    assert result.status_code_breakdown.get("200") == 2
    assert result.status_code_breakdown.get("403") == 1

    # Health score: 2 out of 3 succeeded -> ~66.7%
    assert result.bot_health_score == 66.7
    assert any("blocked" in r.lower() for r in result.recommendations)


def test_api_endpoints_fanout_som_crawler():
    """Tests the new FastAPI endpoints for fanout-cluster, share-of-model, and crawler-logs."""
    # 1. Fanout cluster endpoint
    resp1 = client.post("/api/v1/geo-pipeline/fanout-cluster", json={
        "domain": "linear.app",
        "brand_name": "Linear",
        "industry": "Project Management & Issue Tracking",
        "competitors": ["Jira", "Asana"],
        "target_size": 30,
    })
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert "queries" in data1
    assert len(data1["queries"]) >= 10
    assert "fan_out_queries" in data1["queries"][0]

    # 2. Share of Model endpoint
    resp2 = client.post("/api/v1/geo-pipeline/share-of-model", json={
        "domain": "linear.app",
        "brand_name": "Linear",
        "competitors": ["jira"],
        "evaluations": [
            {
                "query_id": "Q-01",
                "category": "commercial",
                "query_text": "Best issue tracking tools",
                "engine_id": "perplexity",
                "engine_name": "Perplexity",
                "model_version": "sonar",
                "timestamp": "2026-09-27T12:00:00Z",
                "raw_response": "1. Linear 2. Jira",
                "was_mentioned": True,
                "mention_position": 1,
                "was_first_party_cited": True,
                "source_domains": ["linear.app"],
                "status": "SUCCESS",
                "is_live": True,
            }
        ],
    })
    assert resp2.status_code == 200
    data2 = resp2.json()
    # Linear and Jira are both mentioned, so Linear has half of the tracked mentions.
    assert data2["share_of_model_pct"] == 50.0
    assert data2["competitor_shares"]["jira"] == 50.0
    # Citation share requires a competitor domain, not a brand name only.
    assert data2["first_party_citation_share_pct"] is None
    assert data2["ordinal_distribution"]["rank_1"] == 1

    # 3. Crawler log analysis endpoint
    resp3 = client.post("/api/v1/geo-pipeline/crawler-logs/analyze", json={
        "log_content": '1.1.1.1 - - [27/Sep/2026:12:00:00 +0000] "GET / HTTP/1.1" 200 1024 "-" "GPTBot/1.2"'
    })
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["total_ai_bot_hits"] == 1
    assert data3["bot_breakdown"]["GPTBot"] == 1
