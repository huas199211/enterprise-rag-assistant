import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

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
    provider = str(config["embedding_provider"]).lower()
    dimensions = int(config["embedding_dimensions"])
    if provider == "openai_compatible":
        settings = get_settings()
        if settings.openai_api_key:
            return _openai_compatible_embed(text, str(config["embedding_model"]), dimensions)
        raise RuntimeError("当前向量模型提供方为 openai_compatible，但未配置 OPENAI_API_KEY")
    if provider in {"local", "bge_m3", "bge-m3"}:
        return _bge_m3_embed_text(text, str(config["embedding_model"]), dimensions, config)
    if provider in {"hash", "debug_hash"}:
        return _hash_embed_text(text, dimensions)
    raise ValueError(f"不支持的向量模型提供方：{provider}")


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _bge_m3_embed_text(text: str, model_name: str, dimensions: int, config: dict[str, Any]) -> list[float]:
    model = _load_bge_m3_model(model_name, bool(config["bge_m3_use_fp16"]))
    result = model.encode(
        [text],
        batch_size=int(config["bge_m3_batch_size"]),
        max_length=int(config["bge_m3_max_length"]),
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    vector = _extract_dense_vector(result)
    if len(vector) != dimensions:
        raise ValueError(f"向量维度不匹配：期望 {dimensions}，实际 {len(vector)}")
    return _normalize(vector)


@lru_cache(maxsize=2)
def _load_bge_m3_model(model_name: str, use_fp16: bool) -> Any:
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("使用本地 BGE-M3 向量化需要安装 torch 和 transformers，请先执行：pip install -r requirements.txt") from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_kwargs: dict[str, Any] = {}
    if use_fp16 and device == "cuda":
        model_kwargs["torch_dtype"] = torch.float16

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name, **model_kwargs)
    model.to(device)
    model.eval()
    return _TransformersBgeM3Model(tokenizer=tokenizer, model=model, torch_module=torch, device=device)


@dataclass
class _TransformersBgeM3Model:
    tokenizer: Any
    model: Any
    torch_module: Any
    device: str

    def encode(
        self,
        texts: list[str],
        batch_size: int,
        max_length: int,
        return_dense: bool,
        return_sparse: bool,
        return_colbert_vecs: bool,
    ) -> dict[str, list[list[float]]]:
        if not return_dense or return_sparse or return_colbert_vecs:
            raise ValueError("当前本地 BGE-M3 只启用 dense embedding")

        dense_vecs = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encoded = self.tokenizer(batch, padding=True, truncation=True, max_length=max_length, return_tensors="pt")
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            with self.torch_module.inference_mode():
                outputs = self.model(**encoded)
                embeddings = outputs.last_hidden_state[:, 0]
                embeddings = self.torch_module.nn.functional.normalize(embeddings, p=2, dim=1)
            dense_vecs.extend(embeddings.cpu().tolist())
        return {"dense_vecs": dense_vecs}


def _extract_dense_vector(result: dict[str, Any]) -> list[float]:
    dense_vecs = result.get("dense_vecs")
    if dense_vecs is None:
        raise ValueError("BGE-M3 向量化结果缺少 dense_vecs")
    if hasattr(dense_vecs, "tolist"):
        dense_vecs = dense_vecs.tolist()
    if not dense_vecs:
        raise ValueError("BGE-M3 向量化结果为空")
    vector = dense_vecs[0] if isinstance(dense_vecs[0], (list, tuple)) else dense_vecs
    return [float(value) for value in vector]


def _hash_embed_text(text: str, dims: int) -> list[float]:
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
        "embedding_provider": config.get("embedding_provider", settings.embedding_provider),
        "embedding_model": config.get("embedding_model", settings.embedding_model),
        "embedding_dimensions": config.get("embedding_dimensions", settings.embedding_dimensions),
        "embedding_timeout_seconds": config.get("embedding_timeout_seconds", settings.embedding_timeout_seconds),
        "bge_m3_use_fp16": config.get("bge_m3_use_fp16", settings.bge_m3_use_fp16),
        "bge_m3_batch_size": config.get("bge_m3_batch_size", settings.bge_m3_batch_size),
        "bge_m3_max_length": config.get("bge_m3_max_length", settings.bge_m3_max_length),
    }


def _mostly_cjk(token: str) -> bool:
    cjk = sum(1 for ch in token if "\u4e00" <= ch <= "\u9fff")
    return cjk >= max(1, len(token) // 2)
