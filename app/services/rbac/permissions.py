"""The catalog of permission keys, grouped for the role editor UI.

Every key here is a stable identifier used in `role_permissions.permission_key`
and in the backend `require(...)` checks. Keys never change once shipped.
Sensitive keys are flagged so the UI can mark them and never fold them into a
Read/Write preset.
"""

# group -> { permission_key: label }
PERMISSION_GROUPS: dict[str, dict[str, str]] = {
    "Connectors": {
        "nav.connectors":          "Access Connectors",
        "connector.read":          "List / read connectors",
        "connector.create":        "Create connector",
        "connector.save":          "Edit / save connector",
        "connector.validate":      "Validate connector",
        "connector.deploy":        "Deploy connector",
        "connector.clone":         "Clone connector",
        "connector.move":          "Move connector",
        "connector.delete_record": "Delete saved connector record",
    },
    "Connector Folders": {
        "folder.read":   "List / read folders",
        "folder.create": "Create folder",
        "folder.rename": "Rename folder",
        "folder.move":   "Move folder",
        "folder.delete": "Delete folder",
    },
    "Connections": {
        "nav.connections":          "Access Connections",
        "connection.read":           "List / read connections (redacted)",
        "connection.create":         "Create connection",
        "connection.save":           "Edit / save connection",
        "connection.test":           "Test connection",
        "connection.delete":         "Delete connection",
        "connection.use_for_deploy": "Use connection for deployment",
    },
    "Connect Operations": {
        "nav.connect":        "Access Connect",
        "connect.get_status":  "Get status",
        "connect.get_config":  "Get config (redacted)",
        "connect.get_tasks":   "Get tasks",
        "connect.get_topics":  "Get topics",
        "connect.pause":       "Pause connector",
        "connect.resume":      "Resume connector",
        "connect.restart":     "Restart connector",
        "connect.restart_task": "Restart task",
    },
    "Dangerous Operations": {
        "danger.delete_live":   "Delete live connector",
        "danger.reset_offsets": "Reset offsets",
    },
    "Kafka Topics": {
        "nav.topics":         "Access Kafka Topics",
        "topic.browse":        "Browse topic metadata",
        "topic.read_messages": "Read topic messages",
    },
    "Schema Registry": {
        "nav.registry":        "Access Schema Registry",
        "registry.browse":      "Browse catalog",
        "registry.read_schema": "Read schema / versions",
    },
    "Vaults": {
        "vault.read_refs":     "List secret references",
        "vault.create":        "Create vault",
        "vault.add_secret":    "Add / replace secret",
        "vault.remove_secret": "Remove secret",
        "vault.delete":        "Delete vault",
        "vault.use_secrets":   "Use secrets in operations",
    },
    "Plugins": {
        "nav.plugins":  "Access Plugins",
        "plugin.read":   "Read plugins",
        "plugin.create": "Create plugin",
        "plugin.edit":   "Edit plugin",
        "plugin.delete": "Delete plugin",
    },
    "Alerts": {
        "nav.alerts":  "Access Alerts",
        "alert.read":   "Read alerts",
        "alert.create": "Create alert",
        "alert.edit":   "Edit alert",
        "alert.toggle": "Enable / disable alert",
        "alert.test":   "Test notification",
        "alert.delete": "Delete alert",
    },
    "Administration": {
        "admin.manage_users": "Manage users",
        "admin.manage_roles": "Manage roles",
        "admin.assign_roles": "Assign roles",
        "admin.read_audit":   "Read audit events",
    },
}

SENSITIVE_PERMISSIONS: frozenset[str] = frozenset({
    "connector.delete_record",
    "danger.delete_live",
    "danger.reset_offsets",
    "connection.delete",
    "vault.add_secret",
    "vault.remove_secret",
    "vault.delete",
    "vault.use_secrets",
    "admin.manage_users",
    "admin.manage_roles",
    "admin.assign_roles",
})

ALL_PERMISSIONS: frozenset[str] = frozenset(
    key for group in PERMISSION_GROUPS.values() for key in group
)


# Feature/nav access keys: the first checkbox in each rail-backed group.
# Controls main-rail visibility and page-route access, independent of operations.
NAV_FEATURES: dict[str, str] = {
    "nav.connectors":  "Connectors",
    "nav.connections": "Connections",
    "nav.topics":      "Kafka Topics",
    "nav.registry":    "Schema Registry",
    "nav.connect":     "Connect Operations",
    "nav.plugins":     "Plugins",
    "nav.alerts":      "Alerts",
}
NAV_PERMISSIONS: frozenset[str] = frozenset(NAV_FEATURES)


def feature_operation_keys(nav_key: str) -> frozenset[str]:
    """Operation keys that imply access to a feature (everything in its group but the nav key)."""
    group = NAV_FEATURES.get(nav_key)
    if not group:
        return frozenset()
    return frozenset(k for k in PERMISSION_GROUPS.get(group, {}) if k != nav_key)


def has_feature(perm_keys, nav_key: str) -> bool:
    """A role has feature access if granted the nav key or any operation in that group."""
    if nav_key in perm_keys:
        return True
    return bool(set(perm_keys) & feature_operation_keys(nav_key))


def is_valid_permission(key: str) -> bool:
    return key in ALL_PERMISSIONS


# Flat key -> (group, label) for human-readable denial messages.
_PERMISSION_LABELS: dict[str, tuple[str, str]] = {
    key: (group, label)
    for group, perms in PERMISSION_GROUPS.items()
    for key, label in perms.items()
}


def describe_permission(key: str) -> tuple[str, str]:
    """Return (group, label) for a permission key; falls back to the raw key."""
    return _PERMISSION_LABELS.get(key, ("", key))


def forbidden_message(key: str) -> str:
    """Human-readable reason shown to the user when a permission is denied."""
    group, label = describe_permission(key)
    action = label or key
    where = f" in {group}" if group else ""
    return (
        f"Access denied: your current role doesn't allow \u201c{action}\u201d{where}. "
        f"Ask an administrator to grant the \u201c{key}\u201d permission or switch to a role that has it."
    )



def catalog_json() -> list[dict]:
    """Shape consumed by the role-editor UI."""
    out = []
    for group, perms in PERMISSION_GROUPS.items():
        out.append({
            "group": group,
            "permissions": [
                {"key": k, "label": label, "sensitive": k in SENSITIVE_PERMISSIONS}
                for k, label in perms.items()
            ],
        })
    return out
