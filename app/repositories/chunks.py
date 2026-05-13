import json
from typing import Any

from sqlalchemy import text

from ..db import db, utc_now


def delete_chunks_by_document_id(document_id: int) -> None:
    with db() as conn:
        conn.execute(text("delete from chunks where document_id = :document_id"), {"document_id": document_id})


def insert_chunk(chunk_id: str, document_id: int, chunk_index: int, chunk_text: str, metadata: dict[str, Any]) -> None:
    with db() as conn:
        conn.execute(
            text(
                "insert into chunks(id, document_id, chunk_index, text, metadata_json, created_at) "
                "values(:id, :document_id, :chunk_index, :text, :metadata_json, :created_at)"
            ),
            {
                "id": chunk_id,
                "document_id": document_id,
                "chunk_index": chunk_index,
                "text": chunk_text,
                "metadata_json": json.dumps(metadata, ensure_ascii=False),
                "created_at": utc_now(),
            },
        )


def list_chunks_by_document_id(document_id: int) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            text("select id, text, metadata_json from chunks where document_id = :document_id order by chunk_index"),
            {"document_id": document_id},
        ).mappings().fetchall()
    return [dict(row) for row in rows]
