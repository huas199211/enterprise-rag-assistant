import os
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient, models

from .config import get_settings
from .db import get_runtime_config
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
        response = self.client.query_points(
            collection_name=self.collection,
            query=embed_text(query),
            limit=max(top_k * 4, top_k) if rerank else top_k,
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
        if rerank:
            hits = self._rerank(query, hits)
        return hits[:top_k]

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
        query_terms = Counter(tokenize(query))
        reranked = []
        for hit in hits:
            doc_terms = Counter(tokenize(hit.text))
            overlap = sum(min(query_terms[t], doc_terms[t]) for t in query_terms)
            coverage = overlap / max(1, sum(query_terms.values()))
            score = hit.score * 0.7 + coverage * 0.3
            reranked.append(SearchHit(hit.chunk_id, hit.text, score, hit.metadata))
        reranked.sort(key=lambda hit: hit.score, reverse=True)
        return reranked


def _ensure_local_no_proxy() -> None:
    additions = ["127.0.0.1", "localhost", "::1"]
    for key in ("NO_PROXY", "no_proxy"):
        existing = os.environ.get(key, "")
        values = [part.strip() for part in existing.split(",") if part.strip()]
        for value in additions:
            if value not in values:
                values.append(value)
        os.environ[key] = ",".join(values)
