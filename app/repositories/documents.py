from typing import Any

from sqlalchemy import text

from ..db import db, row_to_dict
from ..security import RequestContext, system_context


def create_document_record(
    filename: str,
    file_type: str,
    path: str,
    created_at: str,
    context: RequestContext | None = None,
    visibility: str = "department",
) -> int:
    context = context or system_context()
    with db() as conn:
        cur = conn.execute(
            text(
                "insert into documents(filename, file_type, path, status, error_message, chunk_count, created_at, department_id, uploaded_by, visibility) "
                "values(:filename, :file_type, :path, 'uploaded', '', 0, :created_at, :department_id, :uploaded_by, :visibility) returning id"
            ),
            {
                "filename": filename,
                "file_type": file_type,
                "path": path,
                "created_at": created_at,
                "department_id": context.department_id,
                "uploaded_by": context.user_id,
                "visibility": visibility,
            },
        )
        return int(cur.scalar_one())


def list_documents(context: RequestContext | None = None) -> list[dict[str, Any]]:
    context = context or system_context()
    with db() as conn:
        if context.is_admin:
            rows = conn.execute(text("select * from documents order by created_at desc")).fetchall()
        else:
            rows = conn.execute(
                text(
                    "select * from documents where visibility = 'public' "
                    "or uploaded_by = :user_id "
                    "or (visibility = 'department' and department_id = :department_id) "
                    "order by created_at desc"
                ),
                {"user_id": context.user_id, "department_id": context.department_id},
            ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_document(document_id: int) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute(text("select * from documents where id = :id"), {"id": document_id}).fetchone()
    return row_to_dict(row) if row else None


def document_is_visible(document_id: int, context: RequestContext | None = None) -> bool:
    context = context or system_context()
    document = get_document(document_id)
    if not document:
        return False
    if context.is_admin or document.get("visibility") == "public":
        return True
    if document.get("uploaded_by") == context.user_id:
        return True
    return document.get("visibility") == "department" and document.get("department_id") == context.department_id


def visible_document_ids(context: RequestContext | None = None) -> list[int] | None:
    context = context or system_context()
    if context.is_admin:
        return None
    return [int(item["id"]) for item in list_documents(context)]


def update_document_status(document_id: int, status: str, error_message: str = "") -> None:
    with db() as conn:
        conn.execute(
            text("update documents set status = :status, error_message = :error_message where id = :id"),
            {"id": document_id, "status": status, "error_message": error_message},
        )


def mark_document_indexed(document_id: int, chunk_count: int, indexed_at: str) -> None:
    with db() as conn:
        conn.execute(
            text(
                "update documents set status = 'indexed', error_message = '', chunk_count = :chunk_count, "
                "indexed_at = :indexed_at where id = :id"
            ),
            {"id": document_id, "chunk_count": chunk_count, "indexed_at": indexed_at},
        )
