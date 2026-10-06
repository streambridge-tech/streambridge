"""Seed the built-in Public / Operator / Admin roles.

Each role stores only its own delta; the rest comes through inheritance
(Operator ⊃ Public, Admin ⊃ Operator). Runs on every boot and reconciles
built-in roles only — user-created roles are left untouched.
"""
from app.models.role import SCOPE_ALL, SCOPE_GLOBAL, Role, RoleParent, RolePermission
from app.services.rbac.permissions import is_valid_permission
from app.utils.logger import get_logger

log = get_logger(__name__)

PUBLIC_OWN = {
    "nav.connectors", "nav.connections", "nav.topics", "nav.registry",
    "nav.connect", "nav.plugins", "nav.alerts",
    "connector.read", "folder.read", "connection.read",
    "connect.get_status", "connect.get_config", "connect.get_tasks", "connect.get_topics",
    "topic.browse", "registry.browse", "registry.read_schema",
    "plugin.read", "alert.read", "vault.read_refs",
}

OPERATOR_OWN = {
    "connector.create", "connector.save", "connector.validate", "connector.deploy",
    "connector.clone", "connector.move",
    "folder.create", "folder.rename", "folder.move",
    "connection.create", "connection.save", "connection.test", "connection.use_for_deploy",
    "connect.pause", "connect.resume", "connect.restart", "connect.restart_task",
    "topic.read_messages", "vault.use_secrets",
    "plugin.create", "plugin.edit",
    "alert.create", "alert.edit", "alert.toggle", "alert.test",
}

ADMIN_OWN = {
    "connector.delete_record", "folder.delete", "connection.delete",
    "danger.delete_live", "danger.reset_offsets",
    "vault.create", "vault.add_secret", "vault.remove_secret", "vault.delete",
    "plugin.delete", "alert.delete",
    "admin.manage_users", "admin.manage_roles", "admin.assign_roles", "admin.read_audit",
}

# name, description, parent names, own permissions
BUILTIN = [
    ("Public", "Read-only access to approved metadata and status.", [], PUBLIC_OWN),
    ("Operator", "Build, validate, deploy, and operate connectors.", ["Public"], OPERATOR_OWN),
    ("Admin", "Full access including users, roles, and dangerous operations.", ["Operator"], ADMIN_OWN),
]


def _rename_legacy_role(db, old_name: str, new_name: str) -> None:
    """Rename a legacy built-in role in place, preserving id and assignments."""
    if db.query(Role).filter(Role.name == new_name).first():
        return
    legacy = db.query(Role).filter(Role.name == old_name).first()
    if legacy is not None:
        legacy.name = new_name
        db.flush()
        log.info("Renamed built-in role %s -> %s", old_name, new_name)


def seed_builtin_roles(db) -> None:
    _rename_legacy_role(db, "Viewer", "Public")
    name_to_role: dict[str, Role] = {}
    for name, desc, _parents, _perms in BUILTIN:
        role = db.query(Role).filter(Role.name == name).first()
        if role is None:
            role = Role(name=name, description=desc, is_builtin=True)
            db.add(role)
            db.flush()
        else:
            role.description = desc
            role.is_builtin = True
        name_to_role[name] = role
    db.flush()

    builtin_ids = [r.id for r in name_to_role.values()]
    db.query(RolePermission).filter(RolePermission.role_id.in_(builtin_ids)).delete(synchronize_session=False)
    db.query(RoleParent).filter(RoleParent.role_id.in_(builtin_ids)).delete(synchronize_session=False)

    granted = 0
    for name, _desc, parents, perms in BUILTIN:
        role = name_to_role[name]
        for pkey in sorted(perms):
            if not is_valid_permission(pkey):
                log.error("Built-in role %s references unknown permission %s", name, pkey)
                continue
            db.add(RolePermission(role_id=role.id, permission_key=pkey,
                                  scope_type=SCOPE_GLOBAL, scope_id=SCOPE_ALL))
            granted += 1
        for pname in parents:
            db.add(RoleParent(role_id=role.id, parent_id=name_to_role[pname].id))

    db.commit()
    log.info("Seeded %d built-in roles (%d grants)", len(BUILTIN), granted)
