"""RBAC resolution and the central permission check.

Deny-by-default: a user is allowed only if some assigned or inherited role grants
the permission with a scope that covers the request. `User.is_admin` bypasses.
"""
from __future__ import annotations

from app.models.role import (
    SCOPE_ALL,
    SCOPE_GLOBAL,
    Role,
    RoleParent,
    RolePermission,
    UserRole,
)


def resolve_inherited_role_ids(db, role_ids: set[int]) -> set[int]:
    """Expand a set of role ids to include every ancestor, cycle-safe."""
    resolved: set[int] = set()
    stack = list(role_ids)
    while stack:
        rid = stack.pop()
        if rid in resolved:
            continue
        resolved.add(rid)
        parents = db.query(RoleParent.parent_id).filter(RoleParent.role_id == rid).all()
        for (pid,) in parents:
            if pid not in resolved:
                stack.append(pid)
    return resolved


def user_role_ids(db, user_id: int) -> set[int]:
    rows = db.query(UserRole.role_id).filter(UserRole.user_id == user_id).all()
    return {rid for (rid,) in rows}


def effective_permissions(db, user_id: int, active_role_id: int | None = None) -> dict[str, set[tuple[str, str]]]:
    """permission_key -> set of (scope_type, scope_id) grants, across inherited roles.

    `active_role_id` None means "all assigned roles" (union). A valid assigned role
    id narrows the base to just that role (plus its inheritance); an active role the
    user does not actually hold is ignored (falls back to all).
    """
    direct = user_role_ids(db, user_id)
    base = {active_role_id} if (active_role_id is not None and active_role_id in direct) else direct
    all_ids = resolve_inherited_role_ids(db, base)
    out: dict[str, set[tuple[str, str]]] = {}
    if not all_ids:
        return out
    grants = db.query(RolePermission).filter(RolePermission.role_id.in_(all_ids)).all()
    for g in grants:
        out.setdefault(g.permission_key, set()).add((g.scope_type, g.scope_id))
    return out


def _scope_covers(grant: tuple[str, str], scope_type: str | None, scope_id: str | None) -> bool:
    g_type, g_id = grant
    if g_type == SCOPE_GLOBAL:
        return True
    if scope_type is None:
        # Caller only asked "any grant for this permission?"
        return True
    if g_type != scope_type:
        return False
    return g_id == SCOPE_ALL or g_id == scope_id


def has_permission(
    db,
    user,
    permission_key: str,
    scope_type: str | None = None,
    scope_id: str | None = None,
    active_role_id: int | None = None,
) -> bool:
    if user is None:
        return False
    if getattr(user, "is_admin", False):
        return True
    grants = effective_permissions(db, user.id, active_role_id).get(permission_key)
    if not grants:
        return False
    return any(_scope_covers(g, scope_type, scope_id) for g in grants)


def permission_summary(db, user, active_role_id: int | None = None) -> dict:
    """Flat view for the UI: which permission keys the user holds (plus is_admin)."""
    from app.services.rbac.permissions import ALL_PERMISSIONS, NAV_PERMISSIONS, has_feature
    if getattr(user, "is_admin", False):
        return {"isAdmin": True, "permissions": sorted(ALL_PERMISSIONS)}
    perms = set(effective_permissions(db, user.id, active_role_id).keys())
    # Include implied nav keys so the rail reflects "any operation ⇒ feature access".
    for nav in NAV_PERMISSIONS:
        if has_feature(perms, nav):
            perms.add(nav)
    return {"isAdmin": False, "permissions": sorted(perms)}


def user_has_feature(db, user, nav_key: str, active_role_id: int | None = None) -> bool:
    from app.services.rbac.permissions import has_feature
    if getattr(user, "is_admin", False):
        return True
    perms = set(effective_permissions(db, user.id, active_role_id).keys())
    return has_feature(perms, nav_key)
