import json
from typing import Any

from sqlalchemy import text

from ..config import get_settings
from ..db import db, row_to_dict, utc_now
from ..security import RequestContext, hash_password, verify_password


def ensure_request_user(context: RequestContext) -> None:
    if context.department_id is not None:
        ensure_department(context.department_id, f"部门 {context.department_id}")
    with db() as conn:
        conn.execute(
            text(
                "insert into users(id, username, name, role, department_id, status, created_at) "
                "values(:id, :username, :name, :role, :department_id, 'active', :created_at) "
                "on conflict(id) do update set name = excluded.name, role = excluded.role, department_id = excluded.department_id"
            ),
            {
                "id": context.user_id,
                "username": context.user_id,
                "name": context.user_name,
                "role": context.role,
                "department_id": context.department_id,
                "created_at": utc_now(),
            },
        )


def ensure_department(department_id: int, name: str) -> None:
    with db() as conn:
        conn.execute(
            text(
                "insert into departments(id, name, created_at) values(:id, :name, :created_at) "
                "on conflict(id) do nothing"
            ),
            {"id": department_id, "name": name, "created_at": utc_now()},
        )


def create_department(name: str) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            text("insert into departments(name, created_at) values(:name, :created_at) returning *"),
            {"name": name, "created_at": utc_now()},
        ).mappings().one()
    return dict(row)


def list_departments() -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(text("select * from departments order by id")).fetchall()
    return [row_to_dict(row) for row in rows]


def create_position(name: str, department_id: int | None, description: str = "") -> dict[str, Any]:
    if department_id is not None:
        ensure_department(department_id, f"部门 {department_id}")
    with db() as conn:
        row = conn.execute(
            text(
                "insert into positions(name, department_id, description, created_at) "
                "values(:name, :department_id, :description, :created_at) returning *"
            ),
            {"name": name, "department_id": department_id, "description": description, "created_at": utc_now()},
        ).mappings().one()
    return dict(row)


def list_positions() -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(text("select * from positions order by id")).fetchall()
    return [row_to_dict(row) for row in rows]


def create_user(
    user_id: str,
    name: str,
    role: str,
    department_id: int | None,
    username: str | None = None,
    password: str | None = None,
    position_id: int | None = None,
) -> dict[str, Any]:
    if department_id is not None:
        ensure_department(department_id, f"部门 {department_id}")
    password_hash = hash_password(password) if password else None
    with db() as conn:
        row = conn.execute(
            text(
                "insert into users(id, username, password_hash, name, role, department_id, position_id, status, created_at) "
                "values(:id, :username, :password_hash, :name, :role, :department_id, :position_id, 'active', :created_at) "
                "on conflict(id) do update set username = excluded.username, "
                "password_hash = coalesce(excluded.password_hash, users.password_hash), "
                "name = excluded.name, role = excluded.role, department_id = excluded.department_id, position_id = excluded.position_id "
                "returning *"
            ),
            {
                "id": user_id,
                "username": username or user_id,
                "password_hash": password_hash,
                "name": name,
                "role": role,
                "department_id": department_id,
                "position_id": position_id,
                "created_at": utc_now(),
            },
        ).mappings().one()
    return _public_user(dict(row))


def list_users() -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(text("select * from users order by created_at desc")).fetchall()
    return [_public_user(row_to_dict(row)) for row in rows]


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute(
            text("select * from users where username = :username and status = 'active'"),
            {"username": username},
        ).mappings().fetchone()
        if not row or not row["password_hash"] or not verify_password(password, row["password_hash"]):
            return None
        conn.execute(
            text("update users set last_login_at = :last_login_at where id = :id"),
            {"id": row["id"], "last_login_at": utc_now()},
        )
    return _public_user(dict(row))


def create_role(code: str, name: str, description: str = "") -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            text(
                "insert into roles(code, name, description, created_at) values(:code, :name, :description, :created_at) "
                "on conflict(code) do update set name = excluded.name, description = excluded.description returning *"
            ),
            {"code": code, "name": name, "description": description, "created_at": utc_now()},
        ).mappings().one()
    return dict(row)


def list_roles() -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(text("select * from roles order by id")).fetchall()
    return [row_to_dict(row) for row in rows]


def create_permission(code: str, name: str, description: str = "") -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            text(
                "insert into permissions(code, name, description, created_at) values(:code, :name, :description, :created_at) "
                "on conflict(code) do update set name = excluded.name, description = excluded.description returning *"
            ),
            {"code": code, "name": name, "description": description, "created_at": utc_now()},
        ).mappings().one()
    return dict(row)


def list_permissions() -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(text("select * from permissions order by id")).fetchall()
    return [row_to_dict(row) for row in rows]


def assign_role_to_user(user_id: str, role_code: str) -> None:
    with db() as conn:
        conn.execute(
            text(
                "insert into user_roles(user_id, role_id) "
                "select :user_id, id from roles where code = :role_code "
                "on conflict(user_id, role_id) do nothing"
            ),
            {"user_id": user_id, "role_code": role_code},
        )


def assign_permission_to_role(role_code: str, permission_code: str) -> None:
    with db() as conn:
        conn.execute(
            text(
                "insert into role_permissions(role_id, permission_id) "
                "select r.id, p.id from roles r, permissions p where r.code = :role_code and p.code = :permission_code "
                "on conflict(role_id, permission_id) do nothing"
            ),
            {"role_code": role_code, "permission_code": permission_code},
        )


def user_permissions(user_id: str) -> list[str]:
    with db() as conn:
        rows = conn.execute(
            text(
                "select distinct p.code from permissions p "
                "join role_permissions rp on rp.permission_id = p.id "
                "join user_roles ur on ur.role_id = rp.role_id "
                "where ur.user_id = :user_id order by p.code"
            ),
            {"user_id": user_id},
        ).mappings().fetchall()
    return [str(row["code"]) for row in rows]


def seed_default_auth_data() -> None:
    settings = get_settings()
    permissions = [
        ("documents:read", "查看文档"),
        ("documents:write", "上传和重建文档"),
        ("chat:use", "使用问答"),
        ("admin:manage", "管理用户、角色和权限"),
        ("audit:read", "查看审计日志"),
    ]
    roles = [
        ("admin", "管理员", [code for code, _ in permissions]),
        ("manager", "部门负责人", ["documents:read", "documents:write", "chat:use", "audit:read"]),
        ("user", "普通用户", ["documents:read", "chat:use"]),
    ]
    for code, name in permissions:
        create_permission(code, name)
    for code, name, role_permissions in roles:
        create_role(code, name)
        for permission_code in role_permissions:
            assign_permission_to_role(code, permission_code)
    admin = create_user(
        "admin",
        "系统管理员",
        "admin",
        None,
        username=settings.default_admin_username,
        password=settings.default_admin_password,
    )
    assign_role_to_user(admin["id"], "admin")


def write_audit_log(
    context: RequestContext,
    action: str,
    resource_type: str,
    resource_id: str,
    detail: dict[str, Any] | None = None,
) -> None:
    with db() as conn:
        conn.execute(
            text(
                "insert into audit_logs(actor_user_id, action, resource_type, resource_id, detail_json, created_at) "
                "values(:actor_user_id, :action, :resource_type, :resource_id, :detail_json, :created_at)"
            ),
            {
                "actor_user_id": context.user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "detail_json": json.dumps(detail or {}, ensure_ascii=False),
                "created_at": utc_now(),
            },
        )


def list_audit_logs(limit: int = 100) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            text("select * from audit_logs order by created_at desc limit :limit"),
            {"limit": min(limit, 500)},
        ).fetchall()
    items = []
    for row in rows:
        item = row_to_dict(row)
        item["detail"] = json.loads(item.pop("detail_json") or "{}")
        items.append(item)
    return items


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    user.pop("password_hash", None)
    return user
