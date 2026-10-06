"""Login / logout / session endpoints and the login page."""
import re
import secrets

from flask import Blueprint, current_app, jsonify, request, send_from_directory, session

from app.models.role import Role
from app.models.user import User, normalize_username, valid_username
from app.utils.auth import (
    SESSION_ACTIVE_ROLE,
    admin_exists,
    auth_enabled,
    current_active_role_id,
    current_user,
    dummy_verify,
    login_user,
    logout_user,
)
from app.utils.config import STATIC_DIR
from app.utils.db import SessionLocal
from app.utils.logger import get_logger
from app.utils.passwords import password_error
from app.services.workspace import (
    MODE_PERSONAL,
    MODE_TEAM,
    MODE_UNSET,
    get_mode,
    set_mode,
)

log = get_logger(__name__)
auth_api = Blueprint("auth_api", __name__)


def _roles_for(db, user):
    from app.services.rbac.engine import user_role_ids
    ids = user_role_ids(db, user.id)
    rows = db.query(Role).filter(Role.id.in_(ids)).all() if ids else []
    return [{"id": r.id, "name": r.name} for r in sorted(rows, key=lambda r: r.name)]


@auth_api.get("/login")
def login_page():
    return send_from_directory(STATIC_DIR, "login.html")


@auth_api.get("/api/auth/status")
def auth_status():
    with SessionLocal() as db:
        mode = get_mode(db)
        has_admin = admin_exists(db)
    setup_required = (mode == MODE_UNSET) and not has_admin
    return jsonify({"authEnabled": auth_enabled(), "setupRequired": setup_required, "mode": mode})


def _personal_username(display: str) -> str:
    slug = re.sub(r"[^a-z0-9._+-]", "", (display or "").strip().lower().replace(" ", "."))
    return slug if len(slug) >= 3 else "owner"


@auth_api.post("/api/auth/setup")
def auth_setup():
    """First-run workspace setup. Open only until the workspace is initialized."""
    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode") or "").strip().lower()
    if mode not in (MODE_PERSONAL, MODE_TEAM):
        return jsonify({"error": "Choose Personal or Team."}), 400

    with SessionLocal() as db:
        # Self-closing: setup is only available on a brand-new workspace.
        if admin_exists(db) or get_mode(db) in (MODE_PERSONAL, MODE_TEAM):
            return jsonify({"error": "Setup is already complete."}), 409

        if mode == MODE_TEAM:
            username = normalize_username(data.get("username"))
            password = data.get("password") or ""
            if not valid_username(username):
                return jsonify({"error": "Enter a valid username (3+ characters)."}), 400
            perr = password_error(password)
            if perr:
                return jsonify({"error": perr}), 400
            user = User(username=username, active=True, is_admin=True)
            user.set_password(password)
            db.add(user)
            set_mode(db, MODE_TEAM)
            db.commit()
            db.refresh(user)
            login_user(user)
            current_app.config["AUTH_ENABLED"] = True  # team gate is on now, no restart
            log.info("Workspace setup: team  owner=%s", user.username)
            return jsonify({"ok": True, "mode": MODE_TEAM, "user": user.to_public_dict()})

        # Personal: a single passwordless owner (login is unused in this mode).
        username = _personal_username(data.get("displayName"))
        user = User(username=username, active=True, is_admin=True)
        user.set_password(secrets.token_urlsafe(32))
        db.add(user)
        set_mode(db, MODE_PERSONAL)
        db.commit()
        db.refresh(user)
        login_user(user)
        current_app.config["AUTH_ENABLED"] = False  # personal = no gate
        log.info("Workspace setup: personal  owner=%s", user.username)
        return jsonify({"ok": True, "mode": MODE_PERSONAL, "user": user.to_public_dict()})


@auth_api.get("/api/auth/me")
def auth_me():
    if not auth_enabled():
        return jsonify({"authEnabled": False, "authenticated": False})
    with SessionLocal() as db:
        user = current_user(db)
        if not user:
            return jsonify({"authEnabled": True, "authenticated": False})
        from app.services.rbac.engine import permission_summary
        active = current_active_role_id()
        summary = permission_summary(db, user, active)
        return jsonify({
            "authEnabled": True,
            "authenticated": True,
            "user": user.to_public_dict(),
            "permissions": summary["permissions"],
            "isAdmin": summary["isAdmin"],
            "roles": _roles_for(db, user),
            "activeRoleId": active,
            "defaultRoleId": user.default_role_id,
        })


@auth_api.post("/api/auth/login")
def auth_login():
    data = request.get_json(silent=True) or {}
    username = normalize_username(data.get("username"))
    password = data.get("password") or ""

    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first() if username else None
        if not user or not user.active or not user.check_password(password):
            if not user:
                dummy_verify(password)  # equalize timing; avoid username enumeration
            log.info("Login failed  username=%s", username or "-")
            return jsonify({"error": "Invalid username or password"}), 401

        login_user(user)
        # Start the session on the user's default role (None = all roles).
        from app.services.rbac.engine import user_role_ids
        if user.default_role_id and user.default_role_id in user_role_ids(db, user.id):
            session[SESSION_ACTIVE_ROLE] = user.default_role_id
        log.info("Login ok  username=%s", user.username)
        return jsonify({"user": user.to_public_dict()})


@auth_api.post("/api/auth/logout")
def auth_logout():
    logout_user()
    return jsonify({"ok": True})


@auth_api.post("/api/auth/active-role")
def set_active_role():
    """Switch the active role for this session (null = all roles)."""
    data = request.get_json(silent=True) or {}
    role_id = data.get("roleId")
    with SessionLocal() as db:
        user = current_user(db)
        if not user:
            return jsonify({"error": "authentication required"}), 401
        if role_id is None:
            session.pop(SESSION_ACTIVE_ROLE, None)
            return jsonify({"activeRoleId": None})
        from app.services.rbac.engine import user_role_ids
        if role_id not in user_role_ids(db, user.id):
            return jsonify({"error": "Role is not assigned to you"}), 400
        session[SESSION_ACTIVE_ROLE] = role_id
        return jsonify({"activeRoleId": role_id})


@auth_api.post("/api/auth/default-role")
def set_default_role():
    """Persist the user's default role and make it active now (null = all roles)."""
    data = request.get_json(silent=True) or {}
    role_id = data.get("roleId")
    with SessionLocal() as db:
        user = current_user(db)
        if not user:
            return jsonify({"error": "authentication required"}), 401
        if role_id is not None:
            from app.services.rbac.engine import user_role_ids
            if role_id not in user_role_ids(db, user.id):
                return jsonify({"error": "Role is not assigned to you"}), 400
        user.default_role_id = role_id
        db.commit()
        if role_id is None:
            session.pop(SESSION_ACTIVE_ROLE, None)
        else:
            session[SESSION_ACTIVE_ROLE] = role_id
        return jsonify({"defaultRoleId": role_id, "activeRoleId": role_id})


@auth_api.post("/api/auth/change-password")
def change_password():
    """Self-service password change; verifies the current password first."""
    data = request.get_json(silent=True) or {}
    current = data.get("currentPassword") or ""
    new = data.get("newPassword") or ""
    with SessionLocal() as db:
        user = current_user(db)
        if not user:
            return jsonify({"error": "authentication required"}), 401
        if not user.check_password(current):
            return jsonify({"error": "Current password is incorrect"}), 400
        perr = password_error(new)
        if perr:
            return jsonify({"error": perr}), 400
        if user.check_password(new):
            return jsonify({"error": "New password must be different"}), 400
        user.set_password(new)
        user.must_change_password = False
        db.commit()
        log.info("Password changed  username=%s", user.username)
        return jsonify({"ok": True})
