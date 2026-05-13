import os
import json
import math
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient, models
from sqlalchemy import text

from .config import get_settings
from .db import db, get_runtime_config
from .embeddings import embed_text, tokenize


@dataclass
class SearchHit:
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any]


class VectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.collection = settings.qdrant_collection
        self.vector_size = int(get_runtime_config()["embedding_dimensions"])
        _ensure_local_no_proxy()
        self.client = QdrantClient(url=settings.qdrant_url, timeout=10, check_compatibility=False)
        self._ensure_collection()

    def load(self) -> None:
        pass

    def save(self) -> None:
        pass

    def add(self, chunk_id: str, text: str, metadata: dict[str, Any]) -> None:
        payload = {
            "chunk_id": chunk_id,
            "text": text,
            "metadata": metadata,
            **metadata,
        }
        self.client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)),
                    vector=embed_text(text),
                    payload=payload,
                )
            ],
        )

    def search(self, query: str, top_k: int, rerank: bool = False) -> list[SearchHit]:
        config = get_runtime_config()
        candidate_multiplier = int(config["vector_candidate_multiplier"])
        candidate_limit = max(top_k * candidate_multiplier, top_k)
        vector_hits = self._vector_search(query, candidate_limit)
        bm25_hits = self._bm25_search(query, candidate_limit)
        hits = self._hybrid_fuse(vector_hits, bm25_hits, config)
        if rerank:
            hits = self._rerank(query, hits)
        return hits[:top_k]

    def _vector_search(self, query: str, limit: int) -> list[SearchHit]:
        response = self.client.query_points(
            collection_name=self.collection,
            query=embed_text(query),
            limit=limit,
            with_payload=True,
        )
        hits = []
        for point in response.points:
            payload = point.payload or {}
            hits.append(
                SearchHit(
                    chunk_id=str(payload.get("chunk_id", point.id)),
                    text=str(payload.get("text", "")),
                    score=float(point.score),
                    metadata=dict(payload.get("metadata") or {}),
                )
            )
        return hits

    def _bm25_search(self, query: str, limit: int) -> list[SearchHit]:
        query_terms = Counter(tokenize(query))
        if not query_terms:
            return []

        with db() as conn:
            rows = conn.execute(
                text("select id, text, metadata_json from chunks order by created_at desc")
            ).mappings().fetchall()
        if not rows:
            return []

        documents = []
        document_frequency: Counter[str] = Counter()
        total_length = 0
        for row in rows:
            terms = Counter(tokenize(row["text"]))
            length = sum(terms.values())
            total_length += length
            for term in query_terms:
                if terms.get(term, 0) > 0:
                    document_frequency[term] += 1
            documents.append((row, terms, length))

        avg_doc_length = total_length / max(1, len(documents))
        config = get_runtime_config()
        k1 = float(config["bm25_k1"])
        b = float(config["bm25_b"])
        hits: list[SearchHit] = []
        for row, terms, length in documents:
            score = 0.0
            for term, query_count in query_terms.items():
                term_frequency = terms.get(term, 0)
                if not term_frequency:
                    continue
                df = document_frequency[term]
                idf = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
                denominator = term_frequency + k1 * (1 - b + b * length / max(1.0, avg_doc_length))
                score += idf * (term_frequency * (k1 + 1) / denominator) * query_count
            if score <= 0:
                continue
            metadata = json.loads(row["metadata_json"])
            hits.append(SearchHit(chunk_id=row["id"], text=row["text"], score=score, metadata=metadata))

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def _hybrid_fuse(
        self,
        vector_hits: list[SearchHit],
        bm25_hits: list[SearchHit],
        config: dict[str, Any],
    ) -> list[SearchHit]:
        vector_scores = _normalize_scores(vector_hits)
        bm25_scores = _normalize_scores(bm25_hits)
        vector_weight = float(config["hybrid_vector_weight"])
        bm25_weight = float(config["hybrid_bm25_weight"])
        weight_sum = max(vector_weight + bm25_weight, 0.0001)
        hits_by_id = {hit.chunk_id: hit for hit in vector_hits}
        hits_by_id.update({hit.chunk_id: hit for hit in bm25_hits})

        fused = []
        for chunk_id, hit in hits_by_id.items():
            score = (
                vector_scores.get(chunk_id, 0.0) * vector_weight
                + bm25_scores.get(chunk_id, 0.0) * bm25_weight
            ) / weight_sum
            metadata = dict(hit.metadata)
            metadata["retrieval"] = {
                "vector_score": round(vector_scores.get(chunk_id, 0.0), 6),
                "bm25_score": round(bm25_scores.get(chunk_id, 0.0), 6),
            }
            fused.append(SearchHit(chunk_id=chunk_id, text=hit.text, score=score, metadata=metadata))
        fused.sort(key=lambda hit: hit.score, reverse=True)
        return fused

    def delete_document(self, document_id: int) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    def _ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection):
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(size=self.vector_size, distance=models.Distance.COSINE),
        )

    def _rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        config = get_runtime_config()
        original_score_weight = float(config["rerank_original_score_weight"])
        term_coverage_weight = float(config["rerank_term_coverage_weight"])
        weight_sum = max(original_score_weight + term_coverage_weight, 0.0001)
        query_terms = Counter(tokenize(query))
        reranked = []
        for hit in hits:
            doc_terms = Counter(tokenize(hit.text))
            overlap = sum(min(query_terms[t], doc_terms[t]) for t in query_terms)
            coverage = overlap / max(1, sum(query_terms.values()))
            score = (hit.score * original_score_weight + coverage * term_coverage_weight) / weight_sum
            reranked.append(SearchHit(hit.chunk_id, hit.text, score, hit.metadata))
        reranked.sort(key=lambda hit: hit.score, reverse=True)
        return reranked


def _ensure_local_no_proxy() -> None:
    settings = get_settings()
    additions = [item.strip() for item in settings.local_no_proxy_hosts.split(",") if item.strip()]
    for key in ("NO_PROXY", "no_proxy"):
        existing = os.environ.get(key, "")
        values = [part.strip() for part in existing.split(",") if part.strip()]
        for value in additions:
            if value not in values:
                values.append(value)
        os.environ[key] = ",".join(values)


def _normalize_scores(hits: list[SearchHit]) -> dict[str, float]:
    if not hits:
        return {}
    max_score = max(hit.score for hit in hits)
    if max_score <= 0:
        return {hit.chunk_id: 0.0 for hit in hits}
    return {hit.chunk_id: max(0.0, hit.score / max_score) for hit in hits}
