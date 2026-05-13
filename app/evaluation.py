import json
import time
from pathlib import Path
from typing import Any

from .rag import answer_question


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
        hit_count = sum(1 for keyword in expected_keywords if keyword in answer)
        score = hit_count / max(1, len(expected_keywords))
        results.append(
            {
                "id": item.get("id"),
                "question": item["question"],
                "answer": answer,
                "score": round(score, 3),
                "latency_ms": response["latency_ms"],
                "source_count": len(response["sources"]),
            }
        )
    avg_score = sum(r["score"] for r in results) / max(1, len(results))
    return {
        "count": len(results),
        "avg_keyword_score": round(avg_score, 3),
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "results": results,
    }
