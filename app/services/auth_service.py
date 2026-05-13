from typing import Any

from ..repositories import authenticate_user, user_permissions, write_audit_log
from ..security import RequestContext, create_access_token


def login(username: str, password: str) -> dict[str, Any]:
    user = authenticate_user(username, password)
    if not user:
        raise ValueError("用户名或密码错误")
    context = RequestContext(
        user_id=str(user["id"]),
        user_name=str(user["name"]),
        role=str(user["role"]),
        department_id=user.get("department_id"),
    )
    token = create_access_token(context)
    write_audit_log(context, "login", "user", str(user["id"]), {"username": username})
    return {"access_token": token, "token_type": "bearer", "user": user, "permissions": user_permissions(str(user["id"]))}


def current_user(context: RequestContext) -> dict[str, Any]:
    return {
        "id": context.user_id,
        "name": context.user_name,
        "role": context.role,
        "department_id": context.department_id,
        "permissions": user_permissions(context.user_id),
    }
