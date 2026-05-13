import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from fastapi import UploadFile
from sqlalchemy import text

from .config import get_settings
from .db import db, get_runtime_config, utc_now
from .document_loaders import load_document
from .llm import generate_answer
from .text_splitter import split_text
from .vector_store import VectorStore


async def ingest_upload(file: UploadFile) -> dict[str, Any]:
    settings = get_settings()
    config = get_runtime_config()
    os.makedirs(settings.upload_dir, exist_ok=True)

    safe_name = Path(file.filename or "未命名文档").name
    target = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}_{safe_name}")
    with open(target, "wb") as f:
        shutil.copyfileobj(file.file, f)

    with db() as conn:
        cur = conn.execute(
            text(
                "insert into documents(filename, file_type, path, status, error_message, chunk_count, created_at) "
                "values(:filename, :file_type, :path, 'uploaded', '', 0, :created_at) returning id"
            ),
            {
                "filename": safe_name,
                "file_type": Path(safe_name).suffix.lower(),
                "path": target,
                "created_at": utc_now(),
            },
        )
        document_id = int(cur.scalar_one())

    try:
        _update_document_status(document_id, "parsing")
        raw_text = load_document(target)

        _update_document_status(document_id, "chunking")
        chunks = split_text(raw_text, int(config["chunk_size"]), int(config["chunk_overlap"]))
        if not chunks:
            raise ValueError("文档没有解析出可入库文本")

        _update_document_status(document_id, "embedding")
        store = VectorStore()
        store.delete_document(document_id)

        with db() as conn:
            conn.execute(text("delete from chunks where document_id = :document_id"), {"document_id": document_id})
            for index, chunk_text in enumerate(chunks):
                chunk_id = f"doc-{document_id}-chunk-{index}"
                metadata = {"document_id": document_id, "filename": safe_name, "chunk_index": index}
                conn.execute(
                    text(
                        "insert into chunks(id, document_id, chunk_index, text, metadata_json, created_at) "
                        "values(:id, :document_id, :chunk_index, :text, :metadata_json, :created_at)"
                    ),
                    {
                        "id": chunk_id,
                        "document_id": document_id,
                        "chunk_index": index,
                        "text": chunk_text,
                        "metadata_json": json.dumps(metadata, ensure_ascii=False),
                        "created_at": utc_now(),
                    },
                )
                store.add(chunk_id, chunk_text, metadata)

            conn.execute(
                text(
                    "update documents set status = 'indexed', error_message = '', chunk_count = :chunk_count, "
                    "indexed_at = :indexed_at where id = :id"
                ),
                {"id": document_id, "chunk_count": len(chunks), "indexed_at": utc_now()},
            )
    except Exception as exc:
        _update_document_status(document_id, "failed", str(exc))
        raise

    return {"document_id": document_id, "filename": safe_name, "chunk_count": len(chunks), "status": "indexed"}


def reindex_document(document_id: int) -> dict[str, Any]:
    with db() as conn:
        document = conn.execute(
            text("select id, filename from documents where id = :id"),
            {"id": document_id},
        ).mappings().fetchone()
        if not document:
            raise ValueError("文档不存在")

        rows = conn.execute(
            text("select id, text, metadata_json from chunks where document_id = :document_id order by chunk_index"),
            {"document_id": document_id},
        ).mappings().fetchall()

    if not rows:
        raise ValueError("文档没有可重建的片段，请重新上传")

    _update_document_status(document_id, "embedding")
    store = VectorStore()
    store.delete_document(document_id)
    for row in rows:
        store.add(row["id"], row["text"], json.loads(row["metadata_json"]))

    with db() as conn:
        conn.execute(
            text("update documents set status = 'indexed', error_message = '', indexed_at = :indexed_at where id = :id"),
            {"id": document_id, "indexed_at": utc_now()},
        )

    return {"document_id": document_id, "filename": document["filename"], "chunk_count": len(rows), "status": "indexed"}


async def answer_question(
    question: str,
    conversation_id: str | None,
    top_k: int | None,
    rerank: bool | None,
    min_score: float | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    config = get_runtime_config()
    conversation_id = conversation_id or uuid.uuid4().hex
    top_k = top_k or int(config["top_k"])
    rerank = bool(config["rerank"] if rerank is None else rerank)
    min_score = float(config["min_score"] if min_score is None else min_score)

    ensure_conversation(conversation_id, question)
    history = load_history(conversation_id)
    hits = VectorStore().search(question, top_k=top_k, rerank=rerank)
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

    with db() as conn:
        conn.execute(
            text(
                "insert into messages(id, conversation_id, question, answer, sources_json, latency_ms, created_at) "
                "values(:id, :conversation_id, :question, :answer, :sources_json, :latency_ms, :created_at)"
            ),
            {
                "id": message_id,
                "conversation_id": conversation_id,
                "question": question,
                "answer": answer,
                "sources_json": json.dumps(contexts, ensure_ascii=False),
                "latency_ms": latency_ms,
                "created_at": utc_now(),
            },
        )
    return {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "answer": answer,
        "sources": contexts,
        "latency_ms": latency_ms,
        "min_score": min_score,
    }


def ensure_conversation(conversation_id: str, question: str) -> None:
    with db() as conn:
        exists = conn.execute(
            text("select id from conversations where id = :id"),
            {"id": conversation_id},
        ).fetchone()
        if not exists:
            title = question[: int(get_runtime_config()["conversation_title_length"])]
            conn.execute(
                text("insert into conversations(id, title, created_at) values(:id, :title, :created_at)"),
                {"id": conversation_id, "title": title, "created_at": utc_now()},
            )


def load_history(conversation_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            text("select question, answer from messages where conversation_id = :conversation_id order by created_at asc limit :limit"),
            {"conversation_id": conversation_id, "limit": int(get_runtime_config()["conversation_history_limit"])},
        ).mappings().fetchall()
    return [{"question": row["question"], "answer": row["answer"]} for row in rows]


def _update_document_status(document_id: int, status: str, error_message: str = "") -> None:
    with db() as conn:
        conn.execute(
            text("update documents set status = :status, error_message = :error_message where id = :id"),
            {"id": document_id, "status": status, "error_message": error_message[: int(get_runtime_config()["error_message_max_length"])]},
        )


def _dedupe_contexts(contexts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for context in contexts:
        key = " ".join(str(context["text"]).split())[: int(get_runtime_config()["dedupe_key_length"])]
        if key in seen:
            continue
        seen.add(key)
        unique.append(context)
    return unique
