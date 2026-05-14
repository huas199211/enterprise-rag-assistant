"""重排序 — 仅保留远程 API 重排（Qwen3-Rerank / Dashscope）"""

from typing import Any

import httpx

from .config import get_settings


def rerank_hits(query: str, hits: list[Any], config: dict[str, Any]) -> list[Any]:
    return _remote_rerank(query, hits, config)


def _remote_rerank(query: str, hits: list[Any], config: dict[str, Any]) -> list[Any]:
    settings = get_settings()
    base_url = str(config.get("rerank_base_url") or "").rstrip("/")
    api_key = str(config.get("rerank_api_key") or settings.rerank_api_key or "")
    if not api_key:
        api_key = str(config.get("embedding_api_key") or settings.embedding_api_key or "")
    if not base_url or not api_key:
        return []

    model = str(config.get("rerank_model", "qwen3-rerank"))
    payload = {
        "model": model,
        "input": {
            "query": query,
            "documents": [hit.text for hit in hits],
        },
        "parameters": {
            "top_n": len(hits),
            "return_documents": False,
        },
    }
    try:
        with httpx.Client(timeout=int(config["rerank_timeout_seconds"])) as client:
            response = client.post(
                f"{base_url}/text-rerank",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        return []

    from dataclasses import replace

    results = data.get("output", {}).get("results", [])
    scored_hits = []
    for item in results:
        index = int(item.get("index", -1))
        if index < 0 or index >= len(hits):
            continue
        score = float(item.get("relevance_score", 0.0))
        hit = hits[index]
        metadata = dict(hit.metadata)
        metadata["rerank"] = {
            "provider": "remote",
            "model": model,
            "score": round(score, 6),
        }
        scored_hits.append(replace(hit, score=score, metadata=metadata))

    scored_hits.sort(key=lambda hit: hit.score, reverse=True)
    return scored_hits
