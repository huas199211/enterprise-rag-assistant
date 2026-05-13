import json
from typing import Any

from sqlalchemy import text

from ..db import db, get_runtime_config, row_to_dict, utc_now


def list_message_logs(limit: int) -> list[dict[str, Any]]:
    max_limit = int(get_runtime_config()["max_log_limit"])
    with db() as conn:
        rows = conn.execute(
            text("select * from messages order by created_at desc limit :limit"),
            {"limit": min(limit, max_limit)},
        ).fetchall()
    items = []
    for row in rows:
        item = row_to_dict(row)
        item["sources"] = json.loads(item.pop("sources_json"))
        items.append(item)
    return items


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


def create_message(
    message_id: str,
    conversation_id: str,
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
    latency_ms: int,
    user_id: str,
) -> None:
    with db() as conn:
        conn.execute(
            text(
                "insert into messages(id, conversation_id, question, answer, sources_json, latency_ms, created_at, user_id) "
                "values(:id, :conversation_id, :question, :answer, :sources_json, :latency_ms, :created_at, :user_id)"
            ),
            {
                "id": message_id,
                "conversation_id": conversation_id,
                "question": question,
                "answer": answer,
                "sources_json": json.dumps(sources, ensure_ascii=False),
                "latency_ms": latency_ms,
                "created_at": utc_now(),
                "user_id": user_id,
            },
        )
