import io
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..config import get_settings
from ..db import get_runtime_config, update_runtime_config
from ..document_cleaner import CleaningPipeline, CleaningConfig
from ..document_loaders import load_document
from ..evaluation import compare_evaluation_strategies, export_evaluation_report, run_evaluation
from ..repositories import (
    assign_permission_to_role,
    assign_role_to_user,
    create_department,
    create_feedback,
    create_permission,
    create_position,
    create_role,
    create_user,
    list_audit_logs,
    list_departments,
    list_permissions,
    list_positions,
    list_roles,
    list_documents as list_documents_repository,
    list_message_logs,
    list_users,
    user_permissions,
    write_audit_log,
)
from ..schemas import (
    ChatRequest,
    ConfigUpdate,
    DepartmentCreate,
    FeedbackRequest,
    LoginRequest,
    PermissionCreate,
    PositionCreate,
    RoleCreate,
    UserCreate,
)
from ..security import RequestContext, get_request_context
from ..services import answer_question, current_user, ingest_upload, login, reindex_document


router = APIRouter(prefix="/api")


@router.post("/auth/login")
def auth_login(payload: LoginRequest):
    try:
        return login(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/auth/me")
def auth_me(context: RequestContext = Depends(get_request_context)):
    return current_user(context)


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), context: RequestContext = Depends(get_request_context)):
    require_permission(context, "documents:write")
    try:
        return await ingest_upload(file, context)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/documents")
def list_documents(context: RequestContext = Depends(get_request_context)):
    require_permission(context, "documents:read")
    return list_documents_repository(context)


@router.post("/documents/{document_id}/reindex")
def reindex(document_id: int, context: RequestContext = Depends(get_request_context)):
    require_permission(context, "documents:write")
    try:
        return reindex_document(document_id, context)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat")
async def chat(payload: ChatRequest, context: RequestContext = Depends(get_request_context)):
    require_permission(context, "chat:use")
    return await answer_question(payload.question, payload.conversation_id, payload.top_k, payload.rerank, payload.min_score, context)


@router.post("/feedback")
def feedback(payload: FeedbackRequest, context: RequestContext = Depends(get_request_context)):
    create_feedback(payload.message_id, payload.rating, payload.comment)
    write_audit_log(context, "feedback", "message", payload.message_id, {"rating": payload.rating})
    return {"ok": True}


@router.get("/config")
def config():
    return get_runtime_config()


@router.post("/config")
def save_config(payload: ConfigUpdate):
    data = payload.clean()
    if "chunk_overlap" in data and "chunk_size" in data and data["chunk_overlap"] >= data["chunk_size"]:
        raise HTTPException(status_code=400, detail="片段重叠长度必须小于片段长度")
    return update_runtime_config(data)


@router.get("/logs")
def logs(limit: int = 50):
    return list_message_logs(limit)


@router.post("/departments")
def add_department(payload: DepartmentCreate, context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    return create_department(payload.name)


@router.get("/departments")
def departments(context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    return list_departments()


@router.post("/users")
def add_user(payload: UserCreate, context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    return create_user(payload.id, payload.name, payload.role, payload.department_id, payload.username, payload.password, payload.position_id)


@router.get("/users")
def users(context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    return list_users()


@router.post("/users/{user_id}/roles/{role_code}")
def bind_user_role(user_id: str, role_code: str, context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    assign_role_to_user(user_id, role_code)
    return {"ok": True}


@router.post("/roles")
def add_role(payload: RoleCreate, context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    return create_role(payload.code, payload.name, payload.description)


@router.get("/roles")
def roles(context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    return list_roles()


@router.post("/permissions")
def add_permission(payload: PermissionCreate, context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    return create_permission(payload.code, payload.name, payload.description)


@router.get("/permissions")
def permissions(context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    return list_permissions()


@router.post("/roles/{role_code}/permissions/{permission_code}")
def bind_role_permission(role_code: str, permission_code: str, context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    assign_permission_to_role(role_code, permission_code)
    return {"ok": True}


@router.post("/positions")
def add_position(payload: PositionCreate, context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    return create_position(payload.name, payload.department_id, payload.description)


@router.get("/positions")
def positions(context: RequestContext = Depends(get_request_context)):
    require_permission(context, "admin:manage")
    return list_positions()


@router.get("/audit-logs")
def audit_logs(limit: int = 100, context: RequestContext = Depends(get_request_context)):
    require_permission(context, "audit:read")
    return list_audit_logs(limit)


def require_permission(context: RequestContext, permission_code: str) -> None:
    if context.is_admin:
        return
    if permission_code not in user_permissions(context.user_id):
        raise HTTPException(status_code=403, detail="没有访问该功能的权限")


@router.post("/evaluate")
async def evaluate():
    try:
        return await run_evaluation()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/evaluate/compare")
async def evaluate_compare():
    try:
        return await compare_evaluation_strategies()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/evaluate/export")
async def evaluate_export():
    try:
        return await export_evaluation_report()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── 文档清洗 ──────────────────────────────────────────────────────────

_clean_store: dict[str, dict[str, Any]] = {}


@router.post("/clean")
async def clean_document(
    file: UploadFile = File(...),
    enable_encoding_fix: str = Form("true"),
    enable_noise_filter: str = Form("true"),
    enable_sensitive_mask: str = Form("true"),
    enable_deduplication: str = Form("true"),
    enable_text_normalize: str = Form("true"),
    enable_structure_parse: str = Form("true"),
    enable_table_preserve: str = Form("true"),
):
    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)

    safe_name = Path(file.filename or "未命名文档").name
    tmp_path = os.path.join(settings.upload_dir, f"_clean_{uuid.uuid4().hex}_{safe_name}")
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        raw_text = load_document(tmp_path)
    except Exception as exc:
        os.remove(tmp_path)
        raise HTTPException(status_code=400, detail=f"无法解析文件：{exc}") from exc

    config = CleaningConfig(
        enable_encoding_fix=enable_encoding_fix == "true",
        enable_noise_filter=enable_noise_filter == "true",
        enable_sensitive_mask=enable_sensitive_mask == "true",
        enable_deduplication=enable_deduplication == "true",
        enable_text_normalize=enable_text_normalize == "true",
        enable_structure_parse=enable_structure_parse == "true",
        enable_table_preserve=enable_table_preserve == "true",
    )

    pipeline = CleaningPipeline(config)
    result = pipeline.run(raw_text, filename=safe_name)

    task_id = uuid.uuid4().hex
    _clean_store[task_id] = {
        "original_filename": safe_name,
        "cleaned_text": result.text,
        "stats": result.stats,
    }

    os.remove(tmp_path)

    return {
        "task_id": task_id,
        "original_filename": safe_name,
        "original_length": len(raw_text),
        "cleaned_length": len(result.text),
        "preview": result.text[:2000],
        "stats": result.stats,
    }


@router.get("/clean/download/{task_id}")
async def download_cleaned(task_id: str):
    entry = _clean_store.get(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="清洗结果已过期或不存在")

    name = entry["original_filename"]
    stem = Path(name).stem
    content = entry["cleaned_text"]

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{stem}_cleaned.txt"',
            "Content-Length": str(len(content.encode("utf-8"))),
        },
    )
