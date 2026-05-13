import json
import statistics
import time
from pathlib import Path
from typing import Any

from .rag import answer_question

UNKNOWN_ANSWER_PREFIX = "我不知道"


async def run_evaluation(path: str = "data/eval_set.jsonl") -> dict[str, Any]:
    eval_path = Path(path)
    if not eval_path.exists():
        raise FileNotFoundError(path)
    items = [json.loads(line) for line in eval_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    started = time.perf_counter()
    for item in items:
        response = await answer_question(item["question"], None, item.get("top_k"), item.get("rerank"))
        answer = response["answer"]
        expected_keywords = item.get("expected_keywords", [])
        keyword_hits = [keyword for keyword in expected_keywords if keyword in answer]
        source_text = "\n".join(source["text"] for source in response["sources"])
        source_keyword_hits = [keyword for keyword in expected_keywords if keyword in source_text]
        keyword_score = _ratio(len(keyword_hits), len(expected_keywords))
        source_keyword_score = _ratio(len(source_keyword_hits), len(expected_keywords))
        top_source_score = response["sources"][0]["score"] if response["sources"] else 0.0
        is_refusal = answer.strip().startswith(UNKNOWN_ANSWER_PREFIX)
        results.append(
            {
                "id": item.get("id"),
                "question": item["question"],
                "answer": answer,
                "keyword_score": round(keyword_score, 3),
                "keyword_hits": keyword_hits,
                "source_keyword_score": round(source_keyword_score, 3),
                "source_keyword_hits": source_keyword_hits,
                "latency_ms": response["latency_ms"],
                "source_count": len(response["sources"]),
                "top_source_score": round(top_source_score, 3),
                "is_refusal": is_refusal,
            }
        )
    keyword_scores = [item["keyword_score"] for item in results]
    source_keyword_scores = [item["source_keyword_score"] for item in results]
    source_counts = [item["source_count"] for item in results]
    latencies = [item["latency_ms"] for item in results]
    return {
        "count": len(results),
        "avg_keyword_score": round(_average(keyword_scores), 3),
        "avg_source_keyword_score": round(_average(source_keyword_scores), 3),
        "retrieval_hit_rate": round(_ratio(sum(1 for item in results if item["source_count"] > 0), len(results)), 3),
        "refusal_rate": round(_ratio(sum(1 for item in results if item["is_refusal"]), len(results)), 3),
        "avg_source_count": round(_average(source_counts), 3),
        "avg_latency_ms": round(_average(latencies), 1),
        "p95_latency_ms": _percentile(latencies, 95),
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "results": results,
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _average(values: list[float | int]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _percentile(values: list[int], percentile: int) -> int:
    if not values:
        return 0
    if len(values) == 1:
        return values[0]
    quantiles = statistics.quantiles(sorted(values), n=100)
    return int(quantiles[min(max(percentile, 1), 99) - 1])
