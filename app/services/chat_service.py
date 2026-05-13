import time
import uuid
from typing import Any, Iterable

from ..db import get_runtime_config
from ..llm import generate_answer
from ..repositories import (
    create_message,
    ensure_conversation,
    ensure_request_user,
    load_history,
    visible_document_ids,
    write_audit_log,
)
from ..security import RequestContext, system_context
from ..vector_store import VectorStore


async def answer_question(
    question: str,
    conversation_id: str | None,
    top_k: int | None,
    rerank: bool | None,
    min_score: float | None = None,
    context: RequestContext | None = None,
) -> dict[str, Any]:
    context = context or system_context()
    ensure_request_user(context)
    started = time.perf_counter()
    config = get_runtime_config()
    conversation_id = conversation_id or uuid.uuid4().hex
    top_k = top_k or int(config["top_k"])
    rerank = bool(config["rerank"] if rerank is None else rerank)
    min_score = float(config["min_score"] if min_score is None else min_score)

    ensure_conversation(conversation_id, question)
    history = load_history(conversation_id)
    allowed_document_ids = visible_document_ids(context)
    hits = VectorStore().search(question, top_k=top_k, rerank=rerank, document_ids=allowed_document_ids)
    contexts = _dedupe_contexts(
        {"chunk_id": hit.chunk_id, "text": hit.text, "score": hit.score, "metadata": hit.metadata}
        for hit in hits
        if hit.score >= min_score
    )

    if not contexts:
        answer = "我不知道。当前知识库没有检索到足够相关的资料。"
    else:
        answer = await generate_answer(
            question=question,
            contexts=contexts,
            history=history,
            provider=str(config["llm_provider"]),
            model=str(config["chat_model"]),
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    message_id = uuid.uuid4().hex
    create_message(message_id, conversation_id, question, answer, contexts, latency_ms, context.user_id)
    write_audit_log(context, "chat", "message", message_id, {"source_count": len(contexts), "latency_ms": latency_ms})
    return {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "answer": answer,
        "sources": contexts,
        "latency_ms": latency_ms,
        "min_score": min_score,
    }


def _dedupe_contexts(contexts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    config = get_runtime_config()
    seen = set()
    unique = []
    for context in contexts:
        key = " ".join(str(context["text"]).split())[: int(config["dedupe_key_length"])]
        if key in seen:
            continue
        seen.add(key)
        unique.append(context)
    return unique
