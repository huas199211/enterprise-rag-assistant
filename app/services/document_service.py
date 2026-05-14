import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from ..config import get_settings
from ..db import get_runtime_config, utc_now
from ..document_loaders import load_document
from ..repositories import (
    create_document_record,
    delete_chunks_by_document_id,
    document_is_visible,
    ensure_request_user,
    get_document,
    insert_chunk,
    list_chunks_by_document_id,
    mark_document_indexed,
    update_document_status,
    write_audit_log,
)
from ..security import RequestContext, system_context
from ..text_splitter import split_text
from ..vector_store import VectorStore


def _fix_filename_encoding(filename: str) -> str:
    try:
        raw = filename.encode("latin-1")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return filename
    for enc in ("utf-8", "gbk", "gb18030", "shift_jis", "euc-kr"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return filename


async def ingest_upload(file: UploadFile, context: RequestContext | None = None) -> dict[str, Any]:
    context = context or system_context()
    ensure_request_user(context)
    settings = get_settings()
    config = get_runtime_config()
    os.makedirs(settings.upload_dir, exist_ok=True)

    safe_name = Path(file.filename or "未命名文档").name
    safe_name = _fix_filename_encoding(safe_name)
    target = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}_{safe_name}")
    with open(target, "wb") as f:
        shutil.copyfileobj(file.file, f)

    document_id = create_document_record(
        filename=safe_name,
        file_type=Path(safe_name).suffix.lower(),
        path=target,
        created_at=utc_now(),
        context=context,
    )

    try:
        update_document_status(document_id, "parsing")
        raw_text = load_document(target)

        update_document_status(document_id, "chunking")
        chunks = split_text(raw_text, int(config["chunk_size"]), int(config["chunk_overlap"]))
        if not chunks:
            raise ValueError("文档没有解析出可入库文本")

        update_document_status(document_id, "embedding")
        store = VectorStore()
        store.delete_document(document_id)
        delete_chunks_by_document_id(document_id)
        for index, chunk_text in enumerate(chunks):
            chunk_id = f"doc-{document_id}-chunk-{index}"
            metadata = {
                "document_id": document_id,
                "filename": safe_name,
                "chunk_index": index,
                "department_id": context.department_id,
                "visibility": "department",
            }
            insert_chunk(chunk_id, document_id, index, chunk_text, metadata)
            store.add(chunk_id, chunk_text, metadata)

        mark_document_indexed(document_id, len(chunks), utc_now())
        write_audit_log(context, "upload_document", "document", str(document_id), {"filename": safe_name, "chunk_count": len(chunks)})
    except Exception as exc:
        update_document_status(document_id, "failed", str(exc)[: int(config["error_message_max_length"])])
        write_audit_log(context, "upload_document_failed", "document", str(document_id), {"error": str(exc)})
        raise

    return {"document_id": document_id, "filename": safe_name, "chunk_count": len(chunks), "status": "indexed"}


def reindex_document(document_id: int, context: RequestContext | None = None) -> dict[str, Any]:
    context = context or system_context()
    ensure_request_user(context)
    if not document_is_visible(document_id, context):
        raise ValueError("文档不存在或无权访问")

    document = get_document(document_id)
    if not document:
        raise ValueError("文档不存在")

    rows = list_chunks_by_document_id(document_id)
    if not rows:
        raise ValueError("文档没有可重建的片段，请重新上传")

    update_document_status(document_id, "embedding")
    store = VectorStore()
    store.delete_document(document_id)
    for row in rows:
        store.add(row["id"], row["text"], json.loads(row["metadata_json"]))

    mark_document_indexed(document_id, len(rows), utc_now())
    write_audit_log(context, "reindex_document", "document", str(document_id), {"chunk_count": len(rows)})
    return {"document_id": document_id, "filename": document["filename"], "chunk_count": len(rows), "status": "indexed"}
