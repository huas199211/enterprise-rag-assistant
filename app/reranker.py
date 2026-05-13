from dataclasses import replace
from typing import Any

import httpx

from .config import get_settings
from .embeddings import tokenize


def rerank_hits(query: str, hits: list[Any], config: dict[str, Any]) -> list[Any]:
    provider = str(config.get("rerank_provider", "local"))
    if provider == "remote":
        remote_hits = _remote_rerank(query, hits, config)
        if remote_hits:
            return remote_hits
    return _local_rerank(query, hits, config)


def _local_rerank(query: str, hits: list[Any], config: dict[str, Any]) -> list[Any]:
    original_score_weight = float(config["rerank_original_score_weight"])
    term_coverage_weight = float(config["rerank_term_coverage_weight"])
    weight_sum = max(original_score_weight + term_coverage_weight, 0.0001)
    query_terms = tokenize(query)
    reranked = []
    for hit in hits:
        doc_terms = tokenize(hit.text)
        coverage = _term_coverage(query_terms, doc_terms)
        score = (hit.score * original_score_weight + coverage * term_coverage_weight) / weight_sum
        metadata = dict(hit.metadata)
        metadata["rerank"] = {
            "provider": "local",
            "term_coverage": round(coverage, 6),
        }
        reranked.append(replace(hit, score=score, metadata=metadata))
    reranked.sort(key=lambda hit: hit.score, reverse=True)
    return reranked


def _remote_rerank(query: str, hits: list[Any], config: dict[str, Any]) -> list[Any]:
    settings = get_settings()
    base_url = str(config.get("rerank_base_url") or "").rstrip("/")
    if not base_url or not settings.rerank_api_key:
        return []

    payload = {
        "model": str(config["rerank_model"]),
        "query": query,
        "documents": [hit.text for hit in hits],
        "top_n": len(hits),
    }
    try:
        with httpx.Client(timeout=int(config["rerank_timeout_seconds"])) as client:
            response = client.post(
                f"{base_url}/rerank",
                headers={"Authorization": f"Bearer {settings.rerank_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        return []

    scored_hits = []
    for item in data.get("results", []):
        index = int(item.get("index", -1))
        if index < 0 or index >= len(hits):
            continue
        score = float(item.get("relevance_score", item.get("score", 0.0)))
        hit = hits[index]
        metadata = dict(hit.metadata)
        metadata["rerank"] = {
            "provider": "remote",
            "model": str(config["rerank_model"]),
            "score": round(score, 6),
        }
        scored_hits.append(replace(hit, score=score, metadata=metadata))

    scored_hits.sort(key=lambda hit: hit.score, reverse=True)
    return scored_hits


def _term_coverage(query_terms: list[str], document_terms: list[str]) -> float:
    if not query_terms:
        return 0.0
    document_set = set(document_terms)
    return sum(1 for term in query_terms if term in document_set) / len(query_terms)
