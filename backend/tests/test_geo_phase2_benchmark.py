"""
Comprehensive Test Suite for Phase 2: Live AI Retrieval Benchmark Engine (Layer 2).
Tests:
2.1 Pluggable Engine Adapter Architecture (Perplexity, ChatGPT, Gemini, Claude, Groq)
2.2 Scaled 66-Query Benchmark Generator across 8 intent categories
2.3 Benchmark Execution Runner, Mention/Position extraction & Source Attribution
2.4 Fail-closed Zero-Fake standard when engines are unconfigured
2.5 FastAPI API endpoint integration
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.geo.adapters.base import BaseGeoEngineAdapter, EngineRawResponse
from app.geo.adapters.perplexity import PerplexityAdapter
from app.geo.adapters.openai_search import OpenAISearchAdapter
from app.geo.adapters.gemini import GeminiAdapter
from app.geo.adapters.claude import ClaudeAdapter
from app.geo.adapters.groq import GroqAdapter
from app.geo.adapters.registry import get_adapter
from app.geo.benchmark_generator import benchmark_generator, BenchmarkSuite
from app.geo.benchmark_runner import benchmark_runner, GeoBenchmarkReport


def test_engine_adapters_instantiation_and_defaults():
    """Tests all 5 concrete engine adapters instantiate with proper IDs and models."""
    p_ad = PerplexityAdapter(api_key="test-key", model="sonar")
    assert p_ad.engine_id == "perplexity"
    assert p_ad.is_configured() is True
    assert p_ad.model == "sonar"

    o_ad = OpenAISearchAdapter(api_key="test-key", model="gpt-4o-mini")
    assert o_ad.engine_id == "chatgpt"
    assert o_ad.is_configured() is True

    g_ad = GeminiAdapter(api_key="test-key")
    assert g_ad.engine_id == "gemini"
    assert g_ad.is_configured() is True

    c_ad = ClaudeAdapter(api_key="test-key")
    assert c_ad.engine_id == "claude"
    assert c_ad.is_configured() is True

    gr_ad = GroqAdapter(api_key="test-key")
    assert gr_ad.engine_id == "groq"
    assert gr_ad.is_configured() is True


def test_benchmark_generator_comprehensive_66_queries():
    """Tests generating a full 66-query benchmark suite across all 8 categories."""
    suite = benchmark_generator.generate_suite(
        domain="alienhouse.ai",
        brand_name="AlienHouse Networks",
        industry="AI Software Development",
        services=["FastAPI AI backends", "LLM pipelines"],
        competitors=["Turing", "Scale AI"],
        locations=["India", "USA"],
        mode="comprehensive",
    )

    assert suite.total_queries == 66
    assert len(suite.queries) == 66
    assert suite.brand_name == "AlienHouse Networks"
    assert suite.domain == "alienhouse.ai"

    # Verify all 8 categories exist
    categories = {q.category for q in suite.queries}
    expected_categories = {"entity", "services", "audience", "commercial", "comparative", "problem", "geographic", "high_intent"}
    assert categories == expected_categories

    # Verify category quotas
    entity_queries = [q for q in suite.queries if q.category == "entity"]
    assert len(entity_queries) == 10
    service_queries = [q for q in suite.queries if q.category == "services"]
    assert len(service_queries) == 12
    audience_queries = [q for q in suite.queries if q.category == "audience"]
    assert len(audience_queries) == 8


def test_benchmark_generator_concise_16_queries():
    """Tests generating a 16-query concise suite (2 queries per category)."""
    suite = benchmark_generator.generate_suite(
        domain="acmecrm.com",
        brand_name="Acme CRM",
        industry="B2B Sales CRM",
        mode="concise",
    )

    assert suite.total_queries == 16
    assert len(suite.queries) == 16
    categories = {q.category for q in suite.queries}
    assert len(categories) == 8


class MockSuccessAdapter(BaseGeoEngineAdapter):
    engine_id = "mock_engine"
    display_name = "Mock Engine"
    default_model = "mock-v1"

    async def execute_query(self, prompt: str, locale: str = "en-US", client=None) -> EngineRawResponse:
        return EngineRawResponse(
            engine_id=self.engine_id,
            engine_name=self.display_name,
            model_version=self.default_model,
            raw_content="According to official records, AlienHouse Networks is a top choice (#1) for AI software development.",
            citations=["https://alienhouse.ai/services", "https://techcrunch.com/features"],
            status_code=200,
            latency_ms=120.5,
            is_live=True,  # Test double simulates a successful live provider response.
        )


@pytest.mark.asyncio
async def test_benchmark_runner_execution_and_metrics():
    """Tests running benchmark with mock adapter to verify mention, position, and source attribution."""
    mock_adapter = MockSuccessAdapter(api_key="mock-key")

    with patch("app.geo.benchmark_runner.get_available_adapters", return_value=[mock_adapter]):
        report = await benchmark_runner.execute_benchmark(
            domain="alienhouse.ai",
            brand_name="AlienHouse Networks",
            mode="concise",
        )

        assert report.total_queries == 16
        assert len(report.evaluations) == 16
        assert "mock_engine" in report.engine_aggregates

        agg = report.engine_aggregates["mock_engine"]
        assert agg.mention_count == 16
        assert agg.mention_rate_pct == 100.0
        assert agg.first_party_citation_count == 16
        assert agg.first_party_citation_rate_pct == 100.0
        assert report.reproducibility_hash is not None

        # Verify evaluations fields
        first_eval = report.evaluations[0]
        assert first_eval.was_mentioned is True
        assert first_eval.mention_position == 1
        assert first_eval.was_first_party_cited is True
        assert first_eval.source_quality == "first_party"
        assert "alienhouse.ai" in first_eval.source_domains


@pytest.mark.asyncio
async def test_fail_closed_unconfigured_engines():
    """Tests zero-fake principle: unconfigured engines fail closed with KEY_MISSING rather than faked answers."""
    unconfigured_adapter = PerplexityAdapter(api_key="")

    res = await unconfigured_adapter.execute_query("What is Acme?")
    assert res.status_code == 401
    assert "Missing PERPLEXITY_API_KEY" in res.error
    assert res.is_live is False
    assert res.raw_content == ""


def test_geo_benchmark_api_endpoint():
    """Tests the /api/v1/intelligence/geo-benchmark FastAPI endpoint."""
    client = TestClient(app)
    mock_adapter = MockSuccessAdapter(api_key="mock-key")

    with patch("app.intelligence.geo.benchmark_runner.get_available_adapters", return_value=[mock_adapter]):
        resp = client.get("/api/v1/intelligence/geo-benchmark", params={
            "domain": "alienhouse.ai",
            "biz_name": "AlienHouse Networks",
            "mode": "concise"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "benchmark_id" in data
        assert data["total_queries"] == 16
        assert "engine_aggregates" in data
        assert "evaluations" in data
