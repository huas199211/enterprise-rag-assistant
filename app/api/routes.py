from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..db import get_runtime_config, update_runtime_config
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
