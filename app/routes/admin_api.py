"""Administration API: users, roles, and the permission catalog.

Guarded by RBAC admin permissions. The superuser (`User.is_admin`) bypasses
checks. Several invariants protect against lockout:
  - the last active superuser cannot be demoted, disabled, or deleted
  - built-in roles cannot be structurally edited or deleted
  - role inheritance cannot form a cycle
"""
from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.models.role import (
    SCOPE_ALL,
    SCOPE_GLOBAL,
    SCOPE_TYPES,
    Role,
    RoleParent,
    RolePermission,
    UserRole,
)
from app.models.user import User, normalize_username, valid_username
from app.models.audit import AuditEvent
from app.services.rbac.engine import resolve_inherited_role_ids
from app.services.rbac.permissions import catalog_json, is_valid_permission
from app.utils.auth import require
from app.utils.db import SessionLocal
from app.utils.logger import get_logger
from app.utils.passwords import password_error

log = get_logger(__name__)
admin_api = Blueprint("admin_api", __name__, url_prefix="/api/admin")


@admin_api.get("/audit")
@require("admin.read_audit")
def list_audit():
    """Recent audit events, newest first."""
    limit = request.args.get("limit", 100, type=int) or 100
    with SessionLocal() as db:
        rows = (
            db.query(AuditEvent)
            .order_by(AuditEvent.at.desc())
            .limit(max(1, min(limit, 500)))
            .all()
        )
        return jsonify({"items": [r.to_dict() for r in rows]})


# ── serialization ────────────────────────────────────────────────────────────

def _role_detail(db, role: Role) -> dict:
    perms = db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
    parents = db.query(RoleParent.parent_id).filter(RoleParent.role_id == role.id).all()
    user_count = db.query(UserRole).filter(UserRole.role_id == role.id).count()
    return {
        **role.to_dict(),
        "parents": [pid for (pid,) in parents],
        "permissions": [
            {"key": p.permission_key, "scopeType": p.scope_type, "scopeId": p.scope_id}
            for p in perms
        ],
        "userCount": user_count,
    }


def _user_detail(db, user: User) -> dict:
    role_ids = [rid for (rid,) in db.query(UserRole.role_id).filter(UserRole.user_id == user.id).all()]
    roles = db.query(Role).filter(Role.id.in_(role_ids)).all() if role_ids else []
    return {
        **user.to_public_dict(),
        "roleIds": role_ids,
        "roleNames": [r.name for r in roles],
    }


def _active_superusers(db, exclude_id: int | None = None):
    q = db.query(User).filter(User.is_admin.is_(True), User.active.is_(True))
    if exclude_id is not None:
        q = q.filter(User.id != exclude_id)
    return q.count()


# ── permission catalog ───────────────────────────────────────────────────────

@admin_api.get("/permissions")
@require("admin.manage_roles")
def get_permissions():
    return jsonify({
        "groups": catalog_json(),
        "scopeTypes": sorted(SCOPE_TYPES),
    })


# ── roles ────────────────────────────────────────────────────────────────────

@admin_api.get("/roles")
@require("admin.manage_roles")
def list_roles():
    with SessionLocal() as db:
        roles = db.query(Role).order_by(Role.name).all()
        return jsonify([_role_detail(db, r) for r in roles])


@admin_api.get("/roles/<int:role_id>")
@require("admin.manage_roles")
def get_role(role_id: int):
    with SessionLocal() as db:
        role = db.get(Role, role_id)
        if not role:
            return jsonify({"error": "Role not found"}), 404
        return jsonify(_role_detail(db, role))


@admin_api.post("/roles/effective-preview")
@require("admin.manage_roles")
def effective_preview():
    """Resolve direct + inherited grants for a draft role (powers the live preview)."""
    data = request.get_json(silent=True) or {}
    parent_ids = [int(p) for p in (data.get("parents") or [])]
    own, err = _validate_permissions(data.get("permissions"))
    if err:
        return jsonify({"error": err}), 400

    with SessionLocal() as db:
        inherited_ids = resolve_inherited_role_ids(db, set(parent_ids)) if parent_ids else set()
        inherited: dict[str, tuple[str, str]] = {}
        if inherited_ids:
            for g in db.query(RolePermission).filter(RolePermission.role_id.in_(inherited_ids)).all():
                inherited[g.permission_key] = (g.scope_type, g.scope_id)

    own_keys = {p["key"] for p in own}
    rows = []
    for p in own:
        rows.append({**p, "inherited": False})
    for key, (stype, sid) in inherited.items():
        if key not in own_keys:
            rows.append({"key": key, "scopeType": stype, "scopeId": sid, "inherited": True})
    rows.sort(key=lambda r: r["key"])
    return jsonify({"effective": rows})


def _validate_permissions(raw) -> tuple[list[dict] | None, str | None]:
    if raw is None:
        return [], None
    if not isinstance(raw, list):
        return None, "permissions must be a list"
    out = []
    for item in raw:
        if not isinstance(item, dict):
            return None, "each permission must be an object"
        key = item.get("key")
        if not is_valid_permission(key):
            return None, f"unknown permission '{key}'"
        scope_type = item.get("scopeType", SCOPE_GLOBAL)
        if scope_type not in SCOPE_TYPES:
            return None, f"invalid scopeType '{scope_type}'"
        scope_id = str(item.get("scopeId") or SCOPE_ALL)
        out.append({"key": key, "scopeType": scope_type, "scopeId": scope_id})
    return out, None


def _would_cycle(db, role_id: int, parent_ids: list[int]) -> bool:
    for pid in parent_ids:
        if pid == role_id:
            return True
        # A cycle forms if this role is already an ancestor of the proposed parent.
        if role_id in resolve_inherited_role_ids(db, {pid}):
            return True
    return False


@admin_api.post("/roles")
@require("admin.manage_roles")
def create_role():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    perms, err = _validate_permissions(data.get("permissions"))
    if err:
        return jsonify({"error": err}), 400

    with SessionLocal() as db:
        parent_ids = [int(p) for p in (data.get("parents") or [])]
        if parent_ids and db.query(Role).filter(Role.id.in_(parent_ids)).count() != len(set(parent_ids)):
            return jsonify({"error": "one or more parent roles do not exist"}), 400

        role = Role(name=name, description=(data.get("description") or "").strip(), is_builtin=False)
        try:
            db.add(role)
            db.flush()
        except IntegrityError:
            db.rollback()
            return jsonify({"error": f"Role '{name}' already exists"}), 409

        for pid in set(parent_ids):
            db.add(RoleParent(role_id=role.id, parent_id=pid))
        for p in perms:
            db.add(RolePermission(role_id=role.id, permission_key=p["key"],
                                  scope_type=p["scopeType"], scope_id=p["scopeId"]))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return jsonify({"error": f"Role '{name}' already exists"}), 409
        db.refresh(role)
        log.info("Created role '%s' (perms=%d parents=%d)", name, len(perms), len(set(parent_ids)))
        return jsonify(_role_detail(db, role)), 201


@admin_api.patch("/roles/<int:role_id>")
@require("admin.manage_roles")
def update_role(role_id: int):
    data = request.get_json(silent=True) or {}
    with SessionLocal() as db:
        role = db.get(Role, role_id)
        if not role:
            return jsonify({"error": "Role not found"}), 404
        if role.is_builtin:
            return jsonify({"error": "Built-in roles cannot be edited"}), 400

        if "name" in data:
            new_name = (data.get("name") or "").strip()
            if not new_name:
                return jsonify({"error": "name cannot be empty"}), 400
            role.name = new_name
        if "description" in data:
            role.description = (data.get("description") or "").strip()

        if "parents" in data:
            parent_ids = [int(p) for p in (data.get("parents") or [])]
            if parent_ids and db.query(Role).filter(Role.id.in_(parent_ids)).count() != len(set(parent_ids)):
                return jsonify({"error": "one or more parent roles do not exist"}), 400
            if _would_cycle(db, role.id, parent_ids):
                return jsonify({"error": "inheritance would create a cycle"}), 400
            db.query(RoleParent).filter(RoleParent.role_id == role.id).delete(synchronize_session=False)
            for pid in set(parent_ids):
                db.add(RoleParent(role_id=role.id, parent_id=pid))

        if "permissions" in data:
            perms, err = _validate_permissions(data.get("permissions"))
            if err:
                return jsonify({"error": err}), 400
            db.query(RolePermission).filter(RolePermission.role_id == role.id).delete(synchronize_session=False)
            for p in perms:
                db.add(RolePermission(role_id=role.id, permission_key=p["key"],
                                      scope_type=p["scopeType"], scope_id=p["scopeId"]))

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return jsonify({"error": "Role name already exists"}), 409
        db.refresh(role)
        log.info("Updated role '%s'", role.name)
        return jsonify(_role_detail(db, role))


@admin_api.delete("/roles/<int:role_id>")
@require("admin.manage_roles")
def delete_role(role_id: int):
    with SessionLocal() as db:
        role = db.get(Role, role_id)
        if not role:
            return jsonify({"error": "Role not found"}), 404
        if role.is_builtin:
            return jsonify({"error": "Built-in roles cannot be deleted"}), 400
        # Detach from children and users; delete grants.
        db.query(RoleParent).filter(
            (RoleParent.role_id == role.id) | (RoleParent.parent_id == role.id)
        ).delete(synchronize_session=False)
        db.query(RolePermission).filter(RolePermission.role_id == role.id).delete(synchronize_session=False)
        db.query(UserRole).filter(UserRole.role_id == role.id).delete(synchronize_session=False)
        db.delete(role)
        db.commit()
        log.info("Deleted role id=%d", role_id)
        return jsonify({"deleted": role_id})


# ── users ────────────────────────────────────────────────────────────────────

@admin_api.get("/users")
@require("admin.manage_users")
def list_users():
    with SessionLocal() as db:
        users = db.query(User).order_by(User.username).all()
        return jsonify([_user_detail(db, u) for u in users])


def _assign_roles(db, user: User, role_ids) -> str | None:
    ids = [int(r) for r in (role_ids or [])]
    if ids and db.query(Role).filter(Role.id.in_(ids)).count() != len(set(ids)):
        return "one or more roles do not exist"
    db.query(UserRole).filter(UserRole.user_id == user.id).delete(synchronize_session=False)
    for rid in set(ids):
        db.add(UserRole(user_id=user.id, role_id=rid))
    return None


@admin_api.post("/users")
@require("admin.manage_users")
def create_user():
    data = request.get_json(silent=True) or {}
    if not valid_username(data.get("username", "")):
        return jsonify({"error": "username must be 3-128 chars (letters, numbers, . _ @ + -)"}), 400
    username = normalize_username(data.get("username"))
    password = data.get("password") or ""
    perr = password_error(password)
    if perr:
        return jsonify({"error": perr}), 400

    with SessionLocal() as db:
        if db.query(User).filter(User.username == username).first():
            return jsonify({"error": f"User '{username}' already exists"}), 409

        user = User(
            username=username,
            active=bool(data.get("active", True)),
            is_admin=bool(data.get("isAdmin", False)),
            must_change_password=bool(data.get("mustChangePassword", True)),
        )
        user.set_password(password)
        db.add(user)
        db.flush()

        # Default new accounts to Public when no roles are specified.
        role_ids = data.get("roleIds")
        if role_ids is None:
            viewer = db.query(Role).filter(Role.name == "Public").first()
            role_ids = [viewer.id] if viewer else []
        err = _assign_roles(db, user, role_ids)
        if err:
            db.rollback()
            return jsonify({"error": err}), 400

        db.commit()
        db.refresh(user)
        log.info("Created user '%s' (admin=%s)", username, user.is_admin)
        return jsonify(_user_detail(db, user)), 201


@admin_api.patch("/users/<int:user_id>")
@require("admin.manage_users")
def update_user(user_id: int):
    data = request.get_json(silent=True) or {}
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Protect the last active superuser from demotion / deactivation.
        removing_super = (
            (("isAdmin" in data and not data["isAdmin"]) or ("active" in data and not data["active"]))
            and user.is_admin and user.active
        )
        if removing_super and _active_superusers(db, exclude_id=user.id) == 0:
            return jsonify({"error": "Cannot demote or disable the last active admin"}), 400

        if "active" in data:
            user.active = bool(data["active"])
        if "isAdmin" in data:
            user.is_admin = bool(data["isAdmin"])
        if "mustChangePassword" in data:
            user.must_change_password = bool(data["mustChangePassword"])
        if "roleIds" in data:
            err = _assign_roles(db, user, data["roleIds"])
            if err:
                db.rollback()
                return jsonify({"error": err}), 400

        db.commit()
        db.refresh(user)
        log.info("Updated user '%s'", user.username)
        return jsonify(_user_detail(db, user))


@admin_api.post("/users/<int:user_id>/reset-password")
@require("admin.manage_users")
def reset_user_password(user_id: int):
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    perr = password_error(password)
    if perr:
        return jsonify({"error": perr}), 400
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        user.set_password(password)
        user.must_change_password = bool(data.get("mustChangePassword", True))
        db.commit()
        log.info("Reset password for '%s'", user.username)
        return jsonify({"ok": True})


@admin_api.delete("/users/<int:user_id>")
@require("admin.manage_users")
def delete_user(user_id: int):
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        if user.is_admin and user.active and _active_superusers(db, exclude_id=user.id) == 0:
            return jsonify({"error": "Cannot delete the last active admin"}), 400
        db.query(UserRole).filter(UserRole.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.commit()
        log.info("Deleted user id=%d", user_id)
        return jsonify({"deleted": user_id})
