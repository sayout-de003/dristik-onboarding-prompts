"""Evidence-grounded AEO question clustering and answer-passage quality evaluation.

Semantic clusters are only reported when caller-supplied embeddings exist. Without
embeddings this module uses an explicitly labelled lexical fallback; it never calls
category labels or aggregate counts semantic evidence. Answer quality is assessed
from supplied question/passage records, not aggregate support counters.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
    "for", "from", "how", "i", "in", "is", "it", "of", "on", "or", "our",
    "the", "to", "we", "what", "when", "where", "which", "who", "why", "with",
    "you", "your", "does", "about", "into", "this", "that",
}


def _get(item: Any, *names: str) -> Any:
    for name in names:
        if isinstance(item, dict) and name in item:
            return item[name]
        value = getattr(item, name, None)
        if value is not None:
            return value
    return None


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS}


def _cosine(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    if not a or len(a) != len(b):
        return None
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    na = math.sqrt(sum(float(x) ** 2 for x in a))
    nb = math.sqrt(sum(float(y) ** 2 for y in b))
    return dot / (na * nb) if na and nb else None


def _valid_url(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


class SemanticQuestionClusterer:
    """Greedy, deterministic cosine clustering over real supplied question embeddings.

    If embeddings are absent, an explicitly non-semantic token-Jaccard fallback is
    available so callers can still inspect likely duplicates without overstating it.
    """

    @staticmethod
    def cluster(
        questions: Optional[Iterable[Any]],
        similarity_threshold: float = 0.78,
        allow_lexical_fallback: bool = True,
    ) -> Dict[str, Any]:
        records = list(questions or [])
        normalized = []
        for index, item in enumerate(records, start=1):
            text = str(_get(item, "question", "question_text", "text") or "").strip()
            if not text:
                continue
            raw_embedding = _get(item, "embedding", "question_embedding", "vector")
            embedding = None
            if isinstance(raw_embedding, (list, tuple)) and raw_embedding:
                try:
                    embedding = [float(v) for v in raw_embedding]
                    if not all(math.isfinite(v) for v in embedding):
                        embedding = None
                except (TypeError, ValueError):
                    embedding = None
            normalized.append({
                "question_id": str(_get(item, "question_id", "id") or f"Q-{index:04d}"),
                "question": text,
                "embedding": embedding,
                "tokens": _tokens(text),
                "source_url": _get(item, "source_url", "url", "evidence_url"),
                "category_label_ignored": _get(item, "category"),
            })

        if not normalized:
            return {
                "status": "NOT_TESTED", "method": "NONE", "threshold": similarity_threshold,
                "question_count": 0, "cluster_count": 0, "clusters": [],
                "limitations": ["No non-empty question text was supplied."],
            }

        all_embedded = all(q["embedding"] is not None for q in normalized)
        dims = {len(q["embedding"]) for q in normalized if q["embedding"] is not None}
        semantic_ready = all_embedded and len(dims) == 1
        if semantic_ready:
            method = "SUPPLIED_EMBEDDINGS_COSINE"
        elif allow_lexical_fallback:
            method = "TOKEN_JACCARD_FALLBACK"
        else:
            return {
                "status": "NOT_TESTED", "method": "NONE", "threshold": similarity_threshold,
                "question_count": len(normalized), "cluster_count": 0, "clusters": [],
                "limitations": ["Compatible question embeddings were not supplied; semantic clustering was not run."],
            }

        groups: List[List[dict]] = []
        for question in normalized:
            best_group = None
            best_score = -1.0
            for group in groups:
                scores = []
                for member in group:
                    if semantic_ready:
                        score = _cosine(question["embedding"], member["embedding"])
                    else:
                        union = question["tokens"] | member["tokens"]
                        score = len(question["tokens"] & member["tokens"]) / len(union) if union else 0.0
                    if score is not None:
                        scores.append(score)
                similarity = sum(scores) / len(scores) if scores else 0.0
                if similarity >= similarity_threshold and similarity > best_score:
                    best_group, best_score = group, similarity
            if best_group is None:
                groups.append([question])
            else:
                best_group.append(question)

        clusters = []
        for idx, group in enumerate(groups, start=1):
            # Representative is the most central question when embeddings exist;
            # otherwise choose the question with the most meaningful tokens.
            representative = max(
                group,
                key=lambda q: (
                    sum((_cosine(q["embedding"], other["embedding"]) or 0.0)
                        for other in group if semantic_ready and other is not q)
                    if semantic_ready else len(q["tokens"])
                ),
            )
            clusters.append({
                "cluster_id": f"QCL-{idx:03d}",
                "representative_question": representative["question"],
                "question_ids": [q["question_id"] for q in group],
                "questions": [q["question"] for q in group],
                "member_count": len(group),
                "source_urls": sorted({q["source_url"] for q in group if _valid_url(q["source_url"])}),
            })

        return {
            "status": "MEASURED" if semantic_ready else "INFERRED",
            "method": method,
            "threshold": similarity_threshold,
            "question_count": len(normalized),
            "cluster_count": len(clusters),
            "clusters": clusters,
            "limitations": (
                ["Uses caller-supplied embeddings; quality depends on the embedding model and version.",
                 "Similarity is topical proximity, not proof that questions have identical intent."]
                if semantic_ready else
                ["Lexical similarity fallback is not semantic understanding and may miss paraphrases.",
                 "Existing category labels were not used to create clusters.",
                 "Similarity is topical proximity, not proof that questions have identical intent."]
            ),
        }


class AnswerPassageQualityEvaluator:
    """Measures transparent passage-level heuristics from explicit answer text.

    This is not an LLM entailment/factuality judge. It does not infer answer presence
    from aggregate counts and leaves absent passage evidence untested.
    """

    @staticmethod
    def evaluate(questions: Optional[Iterable[Any]]) -> Dict[str, Any]:
        records = list(questions or [])
        results = []
        for index, item in enumerate(records, start=1):
            question = str(_get(item, "question", "question_text", "query") or "").strip()
            question_id = str(_get(item, "question_id", "id") or f"Q-{index:04d}")
            raw_passages = _get(item, "answer_passages", "passages", "answer_passage")
            answer = _get(item, "answer_text", "answer", "opening_answer", "passage_text")
            passages = []
            if isinstance(raw_passages, str) and raw_passages.strip():
                passages = [{"text": raw_passages, "source_url": _get(item, "source_url", "url", "evidence_url")}]
            elif isinstance(raw_passages, (list, tuple)):
                for passage in raw_passages:
                    text = str(_get(passage, "text", "passage_text", "content", "answer") or "").strip()
                    if text:
                        passages.append({
                            "text": text,
                            "source_url": _get(passage, "source_url", "url", "evidence_url")
                            or _get(item, "source_url", "url", "evidence_url"),
                            "heading": _get(passage, "section_heading", "heading"),
                        })
            if not passages and isinstance(answer, str) and answer.strip():
                passages = [{"text": answer.strip(), "source_url": _get(item, "source_url", "url", "evidence_url")}]

            if not question or not passages:
                results.append({
                    "question_id": question_id, "question": question, "status": "NOT_TESTED",
                    "passage_count": len(passages), "quality_score": None, "dimensions": {},
                    "findings": ["Question text or explicit answer passage is missing."],
                    "evidence": [],
                })
                continue

            q_tokens = _tokens(question)
            evaluated = []
            for passage in passages:
                text = passage["text"]
                tokens = _tokens(text)
                words = _TOKEN_RE.findall(text)
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
                overlap = len(q_tokens & tokens) / len(q_tokens) if q_tokens else None
                directness = 100.0 if sentences and len(words) <= 120 else (65.0 if sentences else 0.0)
                coverage = round(min(100.0, overlap * 100.0), 1) if overlap is not None else None
                concision = 100.0 if 25 <= len(words) <= 100 else (
                    75.0 if 12 <= len(words) <= 140 else 40.0
                )
                standalone = 100.0 if len(words) >= 8 and sentences else 0.0
                dimensions = {
                    "question_term_coverage_pct": coverage,
                    "directness_heuristic_score": directness,
                    "concision_heuristic_score": concision,
                    "standalone_completeness_heuristic_score": standalone,
                    "word_count": len(words),
                    "sentence_count": len(sentences),
                }
                measured = [v for k, v in dimensions.items() if k.endswith("_score") and isinstance(v, (int, float))]
                score = round(sum(measured) / len(measured), 1) if measured else None
                issues = []
                if coverage is not None and coverage < 20:
                    issues.append("Low lexical overlap with the question; manually verify topical relevance.")
                if len(words) < 8:
                    issues.append("Passage may be too short to stand alone.")
                if len(words) > 140:
                    issues.append("Passage is long; consider a concise answer-first summary.")
                if not _valid_url(passage.get("source_url")):
                    issues.append("Passage lacks an absolute HTTP(S) source URL.")
                evaluated.append({
                    "text": text,
                    "source_url": passage.get("source_url"),
                    "section_heading": passage.get("heading"),
                    "dimensions": dimensions,
                    "quality_score": score,
                    "findings": issues,
                })

            best = max(evaluated, key=lambda p: p["quality_score"] if p["quality_score"] is not None else -1)
            results.append({
                "question_id": question_id, "question": question, "status": "SAMPLE_VERIFIED",
                "passage_count": len(evaluated), "quality_score": best["quality_score"],
                "dimensions": best["dimensions"], "findings": best["findings"],
                "evidence": evaluated,
            })

        tested = [r for r in results if r["status"] == "SAMPLE_VERIFIED"]
        return {
            "status": "MEASURED" if tested else "NOT_TESTED",
            "questions_received": len(records),
            "questions_tested": len(tested),
            "quality_score_mean": round(sum(r["quality_score"] for r in tested if r["quality_score"] is not None)
                                         / len([r for r in tested if r["quality_score"] is not None]), 1)
                if any(r["quality_score"] is not None for r in tested) else None,
            "results": results,
            "limitations": [
                "Scores are transparent text heuristics, not semantic entailment, factuality, or answer-engine ranking predictions.",
                "Lexical overlap can penalize valid paraphrases and cannot establish full intent satisfaction.",
                "Source URLs establish provenance only; cited text must be independently checked for claim support.",
            ],
        }


__all__ = ["SemanticQuestionClusterer", "AnswerPassageQualityEvaluator"]
