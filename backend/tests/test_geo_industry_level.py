"""
Unit and integration tests for Dristik Enterprise GEO capabilities.
Tests:
1. Brand Sentiment & Ground-Truth Hallucination Engine
2. RAG Chunking & Semantic Vector Retrieval Simulator
3. Off-Page Third-Party Citation Network Analyzer
4. Competitor Displacement Sentinel
5. Closed-Loop Attribution & Verification Engine
6. Funnel-Weighted Share of Model (SoM)
7. Zero-Fake data integrity & fail-closed behavior
"""
import pytest
from app.domain.models import BusinessProfile
from app.intelligence.geo.sentiment_engine import (
    geo_sentiment_engine,
    BrandPerceptionScore,
    HallucinationAuditReport,
)
from app.intelligence.geo.rag_simulator import (
    rag_retrieval_simulator,
    RagSimulationReport,
)
from app.intelligence.geo.semantic_retrieval import (
    semantic_retrieval_analyzer,
    SemanticRetrievalAnalyzer,
    RetrievalAnalysisConfig,
    RetrievalMethodology,
    ControlledRetrievalReport,
    AnalyzedChunk,
)
from app.intelligence.geo.adapters.perplexity import PerplexityAdapter
from app.intelligence.geo.offpage_network import (
    offpage_network_analyzer,
    AuthorityCategory,
    OffPageCitationReport,
)
from app.intelligence.geo.displacement_sentinel import (
    displacement_sentinel,
    DisplacementAnalysisResult,
)
from app.intelligence.geo.attribution_engine import (
    geo_attribution_engine,
    GeoAttributionReport,
)
from app.intelligence.geo.benchmark_runner import (
    benchmark_runner,
    EvaluatedQueryRun,
    ShareOfModelMetric,
)


def test_sentiment_engine_positive_polarity_and_traits():
    raw_response = (
        "Acme Cloud is an industry-standard, top-tier platform that offers "
        "scalable and robust infrastructure. It provides developer-centric APIs, SDKs, "
        "and is highly recommended for modern engineering teams."
    )
    res = geo_sentiment_engine.analyze_response_sentiment(
        raw_response=raw_response,
        brand_name="Acme Cloud",
    )
    assert res.sentiment == "POSITIVE"
    assert res.sentiment_score > 0.3
    assert "Developer Friendly" in res.attributed_traits
    assert not res.hallucination_detected


def test_sentiment_engine_hallucination_detection():
    profile = BusinessProfile(
        business_name="Acme Cloud",
        business_model="B2B Cloud SaaS",
        pricing_transparency="transparent",
        services=["Developer API", "Cloud Orchestration"],
    )
    raw_response = (
        "Acme Cloud is only available on-premise with self-hosted only deployments. "
        "Furthermore, Acme Cloud does not provide an API and pricing is not public."
    )
    res = geo_sentiment_engine.analyze_response_sentiment(
        raw_response=raw_response,
        brand_name="Acme Cloud",
        ground_truth_profile=profile,
    )
    assert res.hallucination_detected is True
    assert res.hallucination_details is not None
    assert "business model" in res.hallucination_details.lower() or "on-premise" in res.hallucination_details.lower()


def test_rag_chunking_and_retrieval_simulation():
    body_text = (
        "Welcome to SecureFlow. SecureFlow provides automated SOC2 and ISO27001 compliance for enterprise SaaS. "
        "Our platform connects with AWS, GitHub, and Okta in under 5 minutes. "
        "Pricing starts transparently at $499 per month for seed startups and scales to $1,499 per month for growth teams. "
        "We guarantee continuous audit readiness with 24/7 automated evidence collection and auditor collaboration dashboards. "
        "Trusted by over 500 security leaders globally."
    )
    report = rag_retrieval_simulator.simulate_page_retrieval(
        page_text=body_text,
        query="What is the pricing and compliance coverage for SecureFlow?",
        target_chunk_words=100,
        similarity_threshold=0.25,  # Lexical threshold
    )
    assert isinstance(report, RagSimulationReport)
    assert report.total_chunks >= 1
    assert report.retrieved_chunks >= 1
    assert report.top_chunk_similarity > 0.0
    assert len(report.chunks) == report.total_chunks
    assert report.chunks[0].chunk_id.startswith("CHUNK-")


def test_offpage_citation_network_analysis():
    runs = [
        EvaluatedQueryRun(
            query_id="Q-01",
            category="commercial",
            query_text="Best compliance platforms",
            engine_id="perplexity",
            engine_name="Perplexity",
            model_version="sonar",
            timestamp="2026-09-29T00:00:00Z",
            raw_response="Vanta and SecureFlow lead the space according to G2 and TechCrunch.",
            citations=[
                "https://www.g2.com/categories/security-compliance",
                "https://techcrunch.com/2026/01/enterprise-security-report",
                "https://reddit.com/r/devops/comments/best_soc2_tool",
            ],
            was_mentioned=True,
            was_first_party_cited=False,
            is_live=True,
            source_domains=["g2.com", "techcrunch.com", "reddit.com"],
        )
    ]
    report = offpage_network_analyzer.analyze_citation_network(
        evaluations=runs,
        target_domain="secureflow.io",
        brand_name="SecureFlow",
        competitors=["vanta.com"],
    )
    assert isinstance(report, OffPageCitationReport)
    assert report.total_external_citations == 3
    assert len(report.top_authority_hubs) >= 3
    hub_domains = [h.domain for h in report.top_authority_hubs]
    assert "g2.com" in hub_domains
    assert "reddit.com" in hub_domains


def test_displacement_sentinel_alert_generation():
    baseline = [
        EvaluatedQueryRun(
            query_id="Q-01",
            category="commercial",
            query_text="Top compliance automation software",
            engine_id="perplexity",
            engine_name="Perplexity",
            model_version="sonar",
            timestamp="2026-09-01T00:00:00Z",
            raw_response="SecureFlow is ranked #1 for compliance automation.",
            citations=["https://secureflow.io/soc2"],
            was_mentioned=True,
            mention_position=1,
            was_first_party_cited=True,
            is_live=True,
        )
    ]
    current = [
        EvaluatedQueryRun(
            query_id="Q-01",
            category="commercial",
            query_text="Top compliance automation software",
            engine_id="perplexity",
            engine_name="Perplexity",
            model_version="sonar",
            timestamp="2026-09-15T00:00:00Z",
            raw_response="Vanta leads the industry, followed by Drata.",
            citations=["https://vanta.com/features"],
            was_mentioned=False,
            mention_position=None,
            was_first_party_cited=False,
            is_live=True,
        )
    ]
    result = displacement_sentinel.detect_displacements(
        baseline_evaluations=baseline,
        current_evaluations=current,
        target_brand="SecureFlow",
        target_domain="secureflow.io",
        competitors=["Vanta", "Drata"],
    )
    assert isinstance(result, DisplacementAnalysisResult)
    assert result.displacements_suffered == 1
    assert result.net_displacement_score == -1
    assert len(result.critical_alerts) == 1
    assert result.critical_alerts[0].severity == "CRITICAL"
    assert "Vanta" in result.critical_alerts[0].displaced_by_competitors


def test_closed_loop_attribution_calculation():
    pre_patch = [
        EvaluatedQueryRun(
            query_id="Q-01",
            category="commercial",
            query_text="Top compliance automation software",
            engine_id="chatgpt",
            engine_name="ChatGPT",
            model_version="gpt-4o",
            timestamp="2026-09-01T00:00:00Z",
            raw_response="Generic answer without mentioning SecureFlow.",
            was_mentioned=False,
            mention_position=None,
            was_first_party_cited=False,
            is_live=True,
        )
    ]
    post_patch = [
        EvaluatedQueryRun(
            query_id="Q-01",
            category="commercial",
            query_text="Top compliance automation software",
            engine_id="chatgpt",
            engine_name="ChatGPT",
            model_version="gpt-4o",
            timestamp="2026-09-15T00:00:00Z",
            raw_response="SecureFlow is an enterprise-grade compliance automation provider.",
            citations=["https://secureflow.io"],
            was_mentioned=True,
            mention_position=1,
            was_first_party_cited=True,
            is_live=True,
        )
    ]
    attr = geo_attribution_engine.calculate_attribution(
        pre_patch_evaluations=pre_patch,
        post_patch_evaluations=post_patch,
        target_domain="secureflow.io",
        brand_name="SecureFlow",
    )
    assert isinstance(attr, GeoAttributionReport)
    assert attr.pre_mention_rate_pct == 0.0
    assert attr.post_mention_rate_pct == 100.0
    assert attr.mention_rate_delta_pct == 100.0
    assert attr.pre_citation_rate_pct == 0.0
    assert attr.post_citation_rate_pct == 100.0
    assert attr.improved_queries_count == 1
    assert attr.regressed_queries_count == 0


def test_funnel_weighted_share_of_model():
    evals = [
        EvaluatedQueryRun(
            query_id="Q-DECISION",
            category="commercial",  # Decision: weight 4.0
            query_text="Best SOC2 software pricing",
            engine_id="sonar",
            engine_name="Perplexity",
            model_version="sonar",
            timestamp="2026-09-29T00:00:00Z",
            raw_response="SecureFlow offers transparent pricing starting at $499.",
            was_mentioned=True,
            mention_position=1,
            was_first_party_cited=True,
            is_live=True,
        ),
        EvaluatedQueryRun(
            query_id="Q-AWARENESS",
            category="entity",  # Awareness: weight 1.0
            query_text="What is compliance automation?",
            engine_id="sonar",
            engine_name="Perplexity",
            model_version="sonar",
            timestamp="2026-09-29T00:00:00Z",
            raw_response="Vanta compliance automation is the process of monitoring security controls.",
            was_mentioned=False,
            mention_position=None,
            was_first_party_cited=False,
            is_live=True,
        ),
    ]
    som = benchmark_runner.calculate_share_of_model(
        evaluations=evals,
        target_domain="secureflow.io",
        brand_name="SecureFlow",
        competitors=["Vanta"],
    )
    # Target was mentioned in 1 of 2 queries (50% unweighted)
    assert som.share_of_model_pct == 50.0
    # But mentioned in Decision (4.0) and missed Awareness (1.0): 4.0 / 5.0 = 80%
    assert som.funnel_weighted_som_pct == 80.0
    assert "decision" in som.stage_breakdown
    assert som.stage_breakdown["decision"]["mention_rate_pct"] == 100.0
    assert som.stage_breakdown["awareness"]["mention_rate_pct"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# ZERO-FAKE DATA & ZERO-UNSUPPORTED-CLAIMS ACCEPTANCE CRITERIA (TESTS 1 - 8)
# ─────────────────────────────────────────────────────────────────────────────

def test_zero_fake_test_1_real_content_deterministic():
    """
    Test 1: Given actual crawled content, produces deterministic measurements
    without fabricating scores.
    """
    sample_page = (
        "Enterprise cloud security platform for healthcare and fintech organizations. "
        "Compliant with HIPAA, HITRUST, and SOC 2 Type II certifications. "
        "Continuous vulnerability monitoring, automated remediation, and audit logging. "
        "Pricing begins at $1,200 per month with annual enterprise discounts available."
    )
    report = semantic_retrieval_analyzer.analyze_page_content(
        page_text=sample_page,
        query="What certifications and compliance standards are supported?",
        config=RetrievalAnalysisConfig(chunk_size=50, chunk_overlap=10, similarity_threshold=0.20),
        force_lexical=True
    )
    assert isinstance(report, ControlledRetrievalReport)
    assert report.total_chunks > 0
    assert report.top_chunk_similarity > 0.0
    for chunk in report.chunks:
        assert 0.0 <= chunk.similarity_score <= 1.0
        assert chunk.content in sample_page
        assert chunk.char_end > chunk.char_start


def test_zero_fake_test_2_no_content_zero_fabrication():
    """
    Test 2: Given no page content (None or empty string), the system does NOT
    fabricate chunks, scores, or hallucinated content.
    """
    for empty_input in [None, "", "   \n\t  "]:
        report = semantic_retrieval_analyzer.analyze_page_content(
            page_text=empty_input,
            query="What is the pricing plan?",
            force_lexical=True
        )
        assert isinstance(report, ControlledRetrievalReport)
        assert report.total_chunks == 0
        assert report.qualifying_chunks_count == 0
        assert report.top_chunk_similarity == 0.0
        assert report.threshold_pass_rate_pct == 0.0
        assert len(report.chunks) == 0
        assert "No crawled page content available" in report.content_structure_recommendations[0]


@pytest.mark.asyncio
async def test_zero_fake_test_3_no_live_api_is_live_false():
    """
    Test 3: If external engine credentials are missing, is_live = False and
    no external engine result or fake citation is synthesized.
    """
    adapter = PerplexityAdapter(api_key="", model="sonar")
    assert adapter.is_configured() is False

    response = await adapter.execute_query("What is the top SOC2 tool?")
    assert response.is_live is False
    assert response.raw_content == ""
    assert len(response.citations) == 0
    assert response.status_code == 401
    assert "Missing PERPLEXITY_API_KEY" in (response.error or "")


def test_zero_fake_test_4_threshold_semantics_below_dristik_configured():
    """
    Test 4: Scores below threshold are reported strictly as
    'falls below Dristik's configured retrieval threshold', NOT 'Not retrievable by ChatGPT'.
    """
    sample_page = "Our headquarters is located in San Francisco, California."
    report = semantic_retrieval_analyzer.analyze_page_content(
        page_text=sample_page,
        query="Quantum cryptography hardware accelerators and photonics",
        config=RetrievalAnalysisConfig(similarity_threshold=0.72),
        force_lexical=True
    )
    assert report.total_chunks == 1
    chunk = report.chunks[0]
    assert chunk.passes_threshold is False
    assert chunk.retrieval_rank is None

    notes_text = " ".join(chunk.evaluation_notes).lower()
    assert "falls below dristik's configured retrieval threshold" in notes_text
    assert "chatgpt" not in notes_text
    assert "cannot retrieve" not in notes_text


def test_zero_fake_test_5_provider_isolation_no_unsupported_claims():
    """
    Test 5: Ensure no unsupported deterministic claims (e.g. 'ChatGPT will',
    'Perplexity will', 'AI engines will') are generated by the analyzer.
    """
    sample_page = (
        "Dristik provides automated Generative Engine Optimization auditing. "
        "It benchmarks brand visibility across AI search engines."
    )
    report = semantic_retrieval_analyzer.analyze_page_content(
        page_text=sample_page,
        query="How does Dristik measure AI search visibility?",
        force_lexical=True
    )
    # Serialize all report text
    all_text = report.model_dump_json().lower()

    forbidden_phrases = [
        "chatgpt will",
        "perplexity will",
        "gemini will",
        "claude will",
        "ai engines will",
        "chatgpt cannot",
        "perplexity cannot",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in all_text, f"Forbidden phrase '{phrase}' found in report!"


def test_zero_fake_test_6_evidence_provenance_metadata():
    """
    Test 6: Every controlled semantic retrieval result contains explicit methodology
    and provenance metadata.
    """
    sample_page = "Data ingestion pipeline processing 10M records hourly with Apache Kafka."
    report = semantic_retrieval_analyzer.analyze_page_content(
        page_text=sample_page,
        query="What is the pipeline throughput?",
        force_lexical=True
    )
    # Provenance fields on report
    assert report.evidence_type == "DERIVED"
    assert report.source_type == "CRAWLED_WEBSITE"

    # Methodology metadata
    assert isinstance(report.methodology, RetrievalMethodology)
    assert report.methodology.analyzer_name == "Dristik Controlled Semantic Retrieval Analysis"
    assert report.methodology.similarity_metric == "cosine"
    assert report.methodology.similarity_threshold == 0.72
    assert "These measurements represent Dristik's controlled semantic retrieval methodology" in report.methodology.disclaimer

    # Provenance fields on chunk
    chunk = report.chunks[0]
    assert chunk.evidence_type == "DERIVED"
    assert chunk.source_type == "CRAWLED_WEBSITE"
    assert chunk.methodology == "DRISTIK_CONTROLLED_SEMANTIC_RETRIEVAL"


def test_zero_fake_test_7_determinism_identical_runs():
    """
    Test 7: The same page_text, query, embedding/lexical model, chunking_config,
    and threshold produce identically matching results.
    """
    text = (
        "Dristik AI is an enterprise platform for generative search optimization. "
        "It includes closed-loop attribution, competitive displacement tracking, "
        "and brand sentiment analysis. Pricing starts at $799/month."
    )
    cfg = RetrievalAnalysisConfig(chunk_size=100, chunk_overlap=10, similarity_threshold=0.30)
    query = "What is the monthly pricing?"

    run1 = semantic_retrieval_analyzer.analyze_page_content(page_text=text, query=query, config=cfg, force_lexical=True)
    run2 = semantic_retrieval_analyzer.analyze_page_content(page_text=text, query=query, config=cfg, force_lexical=True)

    assert run1.total_chunks == run2.total_chunks
    assert run1.qualifying_chunks_count == run2.qualifying_chunks_count
    assert run1.top_chunk_similarity == run2.top_chunk_similarity
    assert run1.threshold_pass_rate_pct == run2.threshold_pass_rate_pct

    for c1, c2 in zip(run1.chunks, run2.chunks):
        assert c1.chunk_id == c2.chunk_id
        assert c1.content == c2.content
        assert c1.similarity_score == c2.similarity_score
        assert c1.passes_threshold == c2.passes_threshold
        assert c1.char_start == c2.char_start
        assert c1.char_end == c2.char_end


def test_zero_fake_test_8_live_engine_separation():
    """
    Test 8: Controlled semantic retrieval results are never serialized into
    live engine observation fields (e.g. chatgpt_retrieval_score, perplexity_retrieval_score).
    """
    report = semantic_retrieval_analyzer.analyze_page_content(
        page_text="Sample company information.",
        query="Test query",
        force_lexical=True
    )
    data = report.model_dump()
    forbidden_live_fields = [
        "chatgpt_retrieval_score",
        "perplexity_retrieval_score",
        "gemini_retrieval_score",
        "claude_retrieval_score",
        "engine_retrieval_score",
        "is_live",
    ]
    for field in forbidden_live_fields:
        assert field not in data, f"Live engine field '{field}' inappropriately present in controlled retrieval report!"


def test_geo_api_endpoints_schema_and_execution():
    """
    Test 9: Verify FastAPI endpoints for sentiment-audit, offpage-network,
    detect-displacements, and verify-attribution accept their schemas and execute.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Sentiment audit endpoint
    res = client.post("/api/v1/geo-pipeline/sentiment-audit", json={
        "evaluations": [],
        "brand_name": "Acme Inc"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["total_evaluated"] == 0
    assert "detected_distortions" in data

    # 2. Offpage network endpoint
    res = client.post("/api/v1/geo-pipeline/offpage-network", json={
        "evaluations": [],
        "domain": "acme.com",
        "brand_name": "Acme Inc",
        "competitors": ["rival.com"]
    })
    assert res.status_code == 200
    data = res.json()
    assert data["target_domain"] == "acme.com"

    # 3. Detect displacements endpoint
    res = client.post("/api/v1/geo-pipeline/detect-displacements", json={
        "baseline_evaluations": [],
        "current_evaluations": [],
        "brand_name": "Acme Inc",
        "domain": "acme.com",
        "competitors": ["rival.com"]
    })
    assert res.status_code == 200
    data = res.json()
    assert data["target_domain"] == "acme.com"

    # 4. Verify attribution endpoint
    res = client.post("/api/v1/geo-pipeline/verify-attribution", json={
        "pre_patch_evaluations": [],
        "post_patch_evaluations": [],
        "domain": "acme.com",
        "brand_name": "Acme Inc"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["target_domain"] == "acme.com"


