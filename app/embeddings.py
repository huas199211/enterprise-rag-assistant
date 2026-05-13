import hashlib
import math
import re
from collections import Counter

import httpx

from .config import get_settings


TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


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
    provider = str(config["embedding_provider"])
    dimensions = int(config["embedding_dimensions"])
    if provider == "openai_compatible":
        settings = get_settings()
        if settings.openai_api_key:
            return _openai_compatible_embed(text, str(config["embedding_model"]), dimensions)
    return _local_embed_text(text, dimensions)


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _local_embed_text(text: str, dims: int) -> list[float]:
    counts = Counter(tokenize(text))
    vector = [0.0] * dims
    for token, count in counts.items():
        digest = hashlib.md5(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dims
        sign = 1 if digest[4] % 2 == 0 else -1
        vector[idx] += sign * (1.0 + math.log(count))
    return _normalize(vector)


def _openai_compatible_embed(text: str, model: str, dimensions: int) -> list[float]:
    settings = get_settings()
    payload: dict[str, object] = {"model": model, "input": text}
    if model.startswith("text-embedding-3"):
        payload["dimensions"] = dimensions
    config = _runtime_embedding_config()
    with httpx.Client(timeout=int(config["embedding_timeout_seconds"])) as client:
        response = client.post(
            f"{settings.openai_base_url.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    vector = [float(value) for value in data["data"][0]["embedding"]]
    if len(vector) != dimensions:
        raise ValueError(f"Embedding dimensions mismatch: expected {dimensions}, got {len(vector)}")
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
        "embedding_provider": config.get("embedding_provider", settings.embedding_provider),
        "embedding_model": config.get("embedding_model", settings.embedding_model),
        "embedding_dimensions": config.get("embedding_dimensions", settings.embedding_dimensions),
        "embedding_timeout_seconds": config.get("embedding_timeout_seconds", settings.embedding_timeout_seconds),
    }


def _mostly_cjk(token: str) -> bool:
    cjk = sum(1 for ch in token if "\u4e00" <= ch <= "\u9fff")
    return cjk >= max(1, len(token) // 2)
