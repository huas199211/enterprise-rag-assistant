import json
import re
import statistics
import time
from pathlib import Path
from typing import Any

from .rag import answer_question

UNKNOWN_ANSWER_PREFIX = "我不知道"


async def run_evaluation(
    path: str = "data/eval_set.jsonl",
    *,
    top_k: int | None = None,
    rerank: bool | None = None,
    strategy_name: str = "当前配置",
) -> dict[str, Any]:
    eval_path = Path(path)
    if not eval_path.exists():
        raise FileNotFoundError(path)
    items = [json.loads(line) for line in eval_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    started = time.perf_counter()
    for item in items:
        response = await answer_question(
            item["question"],
            None,
            top_k if top_k is not None else item.get("top_k"),
            rerank if rerank is not None else item.get("rerank"),
        )
        answer = response["answer"]
        expected_keywords = item.get("expected_keywords", [])
        keyword_hits = [keyword for keyword in expected_keywords if keyword in answer]
        source_text = "\n".join(source["text"] for source in response["sources"])
        source_keyword_hits = [keyword for keyword in expected_keywords if keyword in source_text]
        keyword_score = _ratio(len(keyword_hits), len(expected_keywords))
        source_keyword_score = _ratio(len(source_keyword_hits), len(expected_keywords))
        top_source_score = response["sources"][0]["score"] if response["sources"] else 0.0
        is_refusal = answer.strip().startswith(UNKNOWN_ANSWER_PREFIX)
        citation_accuracy = _citation_accuracy(answer, len(response["sources"]))
        question_type = item.get("type") or _infer_question_type(item["question"])
        results.append(
            {
                "id": item.get("id"),
                "type": question_type,
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
                "citation_accuracy": round(citation_accuracy, 3),
            }
        )
    keyword_scores = [item["keyword_score"] for item in results]
    source_keyword_scores = [item["source_keyword_score"] for item in results]
    source_counts = [item["source_count"] for item in results]
    latencies = [item["latency_ms"] for item in results]
    citation_scores = [item["citation_accuracy"] for item in results]
    return {
        "strategy": strategy_name,
        "count": len(results),
        "avg_keyword_score": round(_average(keyword_scores), 3),
        "avg_source_keyword_score": round(_average(source_keyword_scores), 3),
        "avg_citation_accuracy": round(_average(citation_scores), 3),
        "retrieval_hit_rate": round(_ratio(sum(1 for item in results if item["source_count"] > 0), len(results)), 3),
        "refusal_rate": round(_ratio(sum(1 for item in results if item["is_refusal"]), len(results)), 3),
        "avg_source_count": round(_average(source_counts), 3),
        "avg_latency_ms": round(_average(latencies), 1),
        "p95_latency_ms": _percentile(latencies, 95),
        "group_summary": _group_summary(results),
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "results": results,
    }


async def compare_evaluation_strategies(path: str = "data/eval_set.jsonl") -> dict[str, Any]:
    strategies = [
        {"strategy_name": "不启用重排序", "rerank": False},
        {"strategy_name": "本地重排序", "rerank": True},
    ]
    results = [await run_evaluation(path, rerank=item["rerank"], strategy_name=item["strategy_name"]) for item in strategies]
    return {"count": len(results), "results": results}


async def export_evaluation_report(
    path: str = "data/eval_set.jsonl",
    output_path: str = "data/evaluation_report.json",
) -> dict[str, Any]:
    report = await run_evaluation(path)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(target), "report": report}


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


def _citation_accuracy(answer: str, source_count: int) -> float:
    citations = [int(value) for value in re.findall(r"\[来源?(\d+)\]", answer)]
    if not citations:
        return 1.0 if source_count == 0 else 0.0
    valid = sum(1 for value in citations if 1 <= value <= source_count)
    return _ratio(valid, len(citations))


def _infer_question_type(question: str) -> str:
    if any(keyword in question for keyword in ("多少", "标准", "上限", "金额")):
        return "标准查询"
    if any(keyword in question for keyword in ("能", "是否", "可以", "需要")):
        return "规则判断"
    return "事实问答"


def _group_summary(results: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        groups.setdefault(str(item["type"]), []).append(item)
    return {
        group: {
            "count": len(items),
            "avg_keyword_score": round(_average([item["keyword_score"] for item in items]), 3),
            "avg_source_keyword_score": round(_average([item["source_keyword_score"] for item in items]), 3),
            "avg_citation_accuracy": round(_average([item["citation_accuracy"] for item in items]), 3),
            "refusal_rate": round(_ratio(sum(1 for item in items if item["is_refusal"]), len(items)), 3),
        }
        for group, items in groups.items()
    }
