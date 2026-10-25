from types import SimpleNamespace

from app.aeo.scoring import EvidenceState
from app.aeo.semantic_quality import AnswerPassageQualityEvaluator, SemanticQuestionClusterer
from app.aeo.specialists import AnswerQualitySpecialist, QuestionClusteringSpecialist


def test_embedding_clusters_use_question_vectors_not_category_labels():
    questions = [
        {"id": "q1", "question": "How do I reset my password?", "category": "billing", "embedding": [1.0, 0.0]},
        {"id": "q2", "question": "I forgot my login password; how can I change it?", "category": "shipping", "embedding": [0.99, 0.01]},
        {"id": "q3", "question": "What is your annual subscription price?", "category": "billing", "embedding": [0.0, 1.0]},
    ]
    result = SemanticQuestionClusterer.cluster(questions, similarity_threshold=0.9)
    assert result["status"] == "MEASURED"
    assert result["method"] == "SUPPLIED_EMBEDDINGS_COSINE"
    assert result["question_count"] == 3
    assert result["cluster_count"] == 2
    assert sorted(len(c["question_ids"]) for c in result["clusters"]) == [1, 2]


def test_missing_embeddings_are_explicitly_lexical_not_claimed_semantic():
    result = SemanticQuestionClusterer.cluster([
        {"question": "How can I reset my password?", "category": "alpha"},
        {"question": "How do I change my password?", "category": "beta"},
    ])
    assert result["status"] == "INFERRED"
    assert result["method"] == "TOKEN_JACCARD_FALLBACK"
    assert any("not semantic understanding" in limitation.lower() for limitation in result["limitations"])


def test_category_only_or_empty_question_inventory_is_not_tested():
    result = SemanticQuestionClusterer.cluster([{"category": "Core Offering"}])
    assert result["status"] == "NOT_TESTED"
    assert result["cluster_count"] == 0


def test_incompatible_embedding_dimensions_fall_back_without_false_semantic_status():
    result = SemanticQuestionClusterer.cluster([
        {"question": "A question", "embedding": [1.0, 0.0]},
        {"question": "Another question", "embedding": [1.0, 0.0, 0.0]},
    ])
    assert result["status"] == "INFERRED"
    assert result["method"] == "TOKEN_JACCARD_FALLBACK"


def test_answer_quality_uses_actual_passage_and_reports_dimensions():
    result = AnswerPassageQualityEvaluator.evaluate([{
        "question_id": "q-payment",
        "question": "What payment methods do you accept?",
        "answer_passages": [{
            "text": "We accept Visa, Mastercard, and bank transfer for annual subscriptions. Payment receipts are emailed to the billing contact after each successful transaction.",
            "source_url": "https://example.com/billing",
            "section_heading": "Payment methods",
        }],
    }])
    assert result["status"] == "MEASURED"
    assert result["questions_tested"] == 1
    item = result["results"][0]
    assert item["status"] == "SAMPLE_VERIFIED"
    assert item["evidence"][0]["text"].startswith("We accept Visa")
    assert item["dimensions"]["word_count"] > 0
    assert "question_term_coverage_pct" in item["dimensions"]
    assert result["quality_score_mean"] is not None


def test_missing_answer_passage_is_not_scored_as_zero():
    result = AnswerPassageQualityEvaluator.evaluate([{
        "question_id": "q-missing",
        "question": "How does billing work?",
        "category": "billing",
    }])
    assert result["status"] == "NOT_TESTED"
    assert result["quality_score_mean"] is None
    assert result["results"][0]["quality_score"] is None


def test_passage_without_source_url_is_flagged():
    result = AnswerPassageQualityEvaluator.evaluate([{
        "question": "How does billing work?",
        "answer_text": "Billing renews every month. The account owner can change the payment method in settings.",
    }])
    assert any("lacks an absolute http" in finding.lower() for finding in result["results"][0]["findings"])


def test_clustering_specialist_exposes_method_and_evidence():
    report = SimpleNamespace(geo_readiness=SimpleNamespace(questions=[
        {"id": "q1", "question": "How do I reset my password?"},
        {"id": "q2", "question": "How can I change my password?"},
    ]))
    result = QuestionClusteringSpecialist().evaluate(report)
    assert result.status == EvidenceState.INFERRED
    assert result.metadata["method"] == "TOKEN_JACCARD_FALLBACK"
    assert result.evidence_items


def test_answer_quality_specialist_only_scores_explicit_passages():
    report = SimpleNamespace(
        website_url="https://example.com",
        geo_readiness=SimpleNamespace(questions=[
            {"question_id": "q1", "question": "How does billing work?", "answer_text": "Billing renews every month. Account owners can change payment settings from their dashboard."},
            {"question_id": "q2", "question": "Where is support?", "category": "support"},
        ]),
    )
    result = AnswerQualitySpecialist().evaluate(report)
    assert result.status == EvidenceState.SAMPLE_VERIFIED
    assert len(result.evidence_items) == 2
    assert result.evidence_items[0]["status"] == "SAMPLE_VERIFIED"
    assert result.evidence_items[1]["status"] == "NOT_TESTED"
