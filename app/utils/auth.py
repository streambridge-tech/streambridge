"""Auth helpers, request guard, and app wiring (team mode).

In both modes, mutating requests must be same-origin. When `auth.enabled` is
false (personal mode) there is no login, so the guard also rejects any Host
name the server was not configured for (DNS rebinding). When true, every
request must carry a valid session.
"""
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import current_app, g, jsonify, redirect, request, session

from app.models.user import User
from app.utils.config import get_config
from app.utils.db import SessionLocal
from app.utils.passwords import hash_password

SESSION_UID = "uid"
SESSION_ACTIVE_ROLE = "active_role_id"

# Page routes gated by a feature/nav permission (same keys as the rail items).
PAGE_FEATURE = {
    "/connectors":      "nav.connectors",
    "/connections":     "nav.connections",
    "/kafka-topics":    "nav.topics",
    "/schema-registry": "nav.registry",
    "/alerts":          "nav.alerts",
}

# What a user who must change their password can still reach, besides static files.
PASSWORD_CHANGE_PATHS = frozenset({
    "/login",
    "/api/auth/status",
    "/api/auth/login",
    "/api/auth/me",
    "/api/auth/change-password",
    "/api/auth/logout",
})

# Used to equalize timing when a username does not exist, so login does not leak
# which usernames are registered.
_DUMMY_HASH = hash_password("dummy-timing-equalizer")


def auth_enabled() -> bool:
    # Prefer the per-app config so bare test apps (no auth installed) are unaffected
    # by the developer's profile.yaml.
    from flask import current_app, has_app_context

    if has_app_context():
        return bool(current_app.config.get("AUTH_ENABLED", False))
    return bool(getattr(get_config(), "AUTH_ENABLED", False))


def admin_exists(db) -> bool:
    return (
        db.query(User)
        .filter(User.is_admin.is_(True), User.active.is_(True))
        .first()
        is not None
    )


def dummy_verify(password: str) -> None:
    from app.utils.passwords import verify_password

    verify_password(_DUMMY_HASH, password or "")


def login_user(user: User) -> None:
    session.clear()
    session[SESSION_UID] = user.id
    session.permanent = True


def logout_user() -> None:
    session.clear()


def current_user(db):
    uid = session.get(SESSION_UID)
    if not uid:
        return None
    user = db.get(User, uid)
    if not user or not user.active:
        return None
    return user


def current_active_role_id():
    """The role selected for this session (None = all roles)."""
    rid = session.get(SESSION_ACTIVE_ROLE)
    return rid if isinstance(rid, int) else None


def _same_origin_ok() -> bool:
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if not origin:
        # No Origin/Referer: rely on the SameSite=Lax session cookie to block
        # cross-site cookie-bearing requests.
        return True
    return urlparse(origin).netloc == request.host


def _hostname(value) -> str:
    """Host header or setting without its port, lowercased. IPv6 keeps brackets."""
    value = str(value or "").strip().lower()
    if value.startswith("["):
        return value.split("]", 1)[0] + "]"
    if value.count(":") > 1:
        return f"[{value}]"
    return value.split(":", 1)[0]


def _host_allowed() -> bool:
    names = [
        "localhost", "127.0.0.1", "[::1]",
        current_app.config.get("SERVER_HOST"),
        *(current_app.config.get("SERVER_ALLOWED_HOSTS") or ()),
    ]
    allowed = {_hostname(name) for name in names} - {""}
    return _hostname(request.host) in allowed


def _is_static_path(path: str) -> bool:
    return path.startswith("/static/") or path == "/favicon.ico"


def _is_open_path(path: str) -> bool:
    return path == "/login" or path.startswith("/api/auth/")


def auth_guard():
    """before_request handler. Returns a response to short-circuit, else None."""
    path = request.path
    is_api = path.startswith("/api/")
    personal = not auth_enabled()

    # Personal mode has no sign-in, so a page on a rebound DNS name could act as
    # the owner. Answer only to the names the server is meant to be reached by.
    if personal and not _host_allowed():
        if is_api:
            return jsonify({"error": "invalid host"}), 403
        return "Host not allowed. Add it to server.allowed_hosts in profile.yaml.", 403, {"Content-Type": "text/plain"}

    if request.method not in ("GET", "HEAD", "OPTIONS") and not _same_origin_ok():
        return jsonify({"error": "invalid origin"}), 403

    if personal or _is_static_path(path):
        return None

    with SessionLocal() as db:
        user = current_user(db)
        if user is not None and user.must_change_password and path not in PASSWORD_CHANGE_PATHS:
            if is_api:
                return jsonify({"error": "Password change required", "code": "must_change_password"}), 403
            return redirect("/login")  # the login page shows the change-password form

        if _is_open_path(path):
            return None

        if not admin_exists(db):
            if is_api:
                return jsonify({"error": "setup required"}), 503
            return redirect("/login")

        if user is None:
            if is_api:
                return jsonify({"error": "authentication required"}), 401
            return redirect("/login")

        # Page routes behind a feature gate (rail + page). APIs enforce their own ops.
        if not is_api and path in PAGE_FEATURE:
            from app.services.rbac.engine import user_has_feature
            if not user_has_feature(db, user, PAGE_FEATURE[path], current_active_role_id()):
                return redirect("/docs")

        g.user_id = user.id
        g.user_is_admin = user.is_admin
    return None


def require(permission_key: str, scope_type: str | None = None, scope_arg: str | None = None):
    """Decorator enforcing a permission on a route.

    In personal mode (auth disabled) it is a no-op. In team mode it loads the
    logged-in user and denies with 403 unless RBAC grants the permission.
    `scope_arg` names the view kwarg holding the entity id for scoped checks.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not auth_enabled():
                return fn(*args, **kwargs)
            from app.services.rbac.engine import has_permission

            with SessionLocal() as db:
                user = current_user(db)
                if user is None:
                    return jsonify({"error": "authentication required"}), 401
                scope_id = kwargs.get(scope_arg) if scope_arg else None
                allowed = has_permission(
                    db, user, permission_key, scope_type,
                    str(scope_id) if scope_id is not None else None,
                    current_active_role_id(),
                )
            if not allowed:
                from app.services.rbac.permissions import forbidden_message
                return jsonify({
                    "error": "forbidden",
                    "permission": permission_key,
                    "message": forbidden_message(permission_key),
                }), 403
            return fn(*args, **kwargs)

        wrapper._rbac_permission = permission_key  # introspectable by the matrix test
        return wrapper

    return decorator


def authorize(permission_key: str, scope_type: str | None = None, scope_id: str | None = None):
    """Imperative permission check for handlers that dispatch dynamically.

    Returns None when allowed (including personal mode), or a Flask (body, status)
    tuple to return directly when denied.
    """
    if not auth_enabled():
        return None
    from app.services.rbac.engine import has_permission

    with SessionLocal() as db:
        user = current_user(db)
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        if not has_permission(db, user, permission_key, scope_type, scope_id, current_active_role_id()):
            from app.services.rbac.permissions import forbidden_message
            return jsonify({
                "error": "forbidden",
                "permission": permission_key,
                "message": forbidden_message(permission_key),
            }), 403
    return None


def install_auth(app) -> None:
    cfg = get_config()

    import secrets as _secrets

    # Resolve a stable secret key: explicit config wins, else a persisted one so
    # sessions survive restarts and a runtime Personal→Team switch keeps working.
    key = cfg.AUTH_SECRET_KEY
    if not key:
        try:
            from app.utils.db import SessionLocal
            from app.services.workspace import get_or_create_secret_key
            with SessionLocal() as db:
                key = get_or_create_secret_key(db)
        except Exception:
            key = _secrets.token_hex(32)
    app.secret_key = key or _secrets.token_hex(32)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(cfg.AUTH_COOKIE_SECURE),
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=cfg.AUTH_SESSION_LIFETIME_MIN),
    )

    # A persisted workspace mode overrides the profile default, so a web setup
    # choice (Personal/Team) takes effect without editing profile.yaml.
    try:
        from app.utils.db import SessionLocal
        from app.services.workspace import MODE_PERSONAL, MODE_TEAM, get_mode
        with SessionLocal() as db:
            mode = get_mode(db)
        if mode == MODE_TEAM:
            app.config["AUTH_ENABLED"] = True
        elif mode == MODE_PERSONAL:
            app.config["AUTH_ENABLED"] = False
    except Exception:
        pass

    app.before_request(auth_guard)
