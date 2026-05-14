import math
import re

import httpx

from .config import get_settings


TOKEN_RE = re.compile(r"[\w一-鿿]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    tokens = TOKEN_RE.findall(text.lower())
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        if _mostly_cjk(token) and len(token) > 1:
            expanded.extend(token[i : i + 2] for i in range(len(token) - 1))
    return expanded


def embed_text(text: str) -> list[float]:
    config = _runtime_embedding_config()
    base_url = str(config.get("embedding_base_url") or "").rstrip("/")
    api_key = str(config.get("embedding_api_key") or "")
    model = str(config["embedding_model"])
    dimensions = int(config["embedding_dimensions"])
    if not base_url or not api_key:
        raise RuntimeError("Embedding API 地址或密钥未配置")
    payload: dict[str, object] = {"model": model, "input": text, "dimensions": dimensions}
    with httpx.Client(timeout=int(config["embedding_timeout_seconds"])) as client:
        response = client.post(
            f"{base_url}/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    vector = [float(value) for value in data["data"][0]["embedding"]]
    if len(vector) != dimensions:
        raise ValueError(f"向量维度不匹配：期望 {dimensions}，实际 {len(vector)}")
    return _normalize(vector)


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if not norm:
        return vector
    return [v / norm for v in vector]


def _runtime_embedding_config() -> dict[str, object]:
    settings = get_settings()
    try:
        from .db import get_runtime_config

        config = get_runtime_config()
    except Exception:
        config = {}
    return {
        "embedding_model": config.get("embedding_model", settings.embedding_model),
        "embedding_dimensions": config.get("embedding_dimensions", settings.embedding_dimensions),
        "embedding_base_url": config.get("embedding_base_url", settings.embedding_base_url),
        "embedding_api_key": config.get("embedding_api_key", settings.embedding_api_key),
        "embedding_timeout_seconds": config.get("embedding_timeout_seconds", settings.embedding_timeout_seconds),
    }


def _mostly_cjk(token: str) -> bool:
    cjk = sum(1 for ch in token if "一" <= ch <= "鿿")
    return cjk >= max(1, len(token) // 2)
