"""Workspace mode + persisted-secret helpers.

Mode is the single source of truth for Personal vs Team, stored in the DB so a
web setup choice takes effect without editing profile.yaml. Team is permanent.
All reads are defensive so a missing table (e.g. bare test apps) never crashes.
"""
import secrets

from app.models.workspace import WorkspaceSetting
from app.utils.logger import get_logger

log = get_logger(__name__)

MODE_UNSET = "unset"
MODE_PERSONAL = "personal"
MODE_TEAM = "team"
_SELECTABLE = {MODE_PERSONAL, MODE_TEAM}

KEY_MODE = "mode"
KEY_SECRET = "secret_key"


def get_setting(db, key: str, default=None):
    try:
        row = db.get(WorkspaceSetting, key)
        return row.value if row else default
    except Exception:
        return default


def set_setting(db, key: str, value: str) -> None:
    row = db.get(WorkspaceSetting, key)
    if row is None:
        db.add(WorkspaceSetting(key=key, value=value or ""))
    else:
        row.value = value or ""


def get_mode(db) -> str:
    mode = get_setting(db, KEY_MODE, MODE_UNSET)
    return mode if mode in (_SELECTABLE | {MODE_UNSET}) else MODE_UNSET


def set_mode(db, mode: str) -> None:
    if mode not in _SELECTABLE:
        raise ValueError(f"invalid workspace mode: {mode!r}")
    # Team is a one-way, permanent upgrade.
    if get_mode(db) == MODE_TEAM and mode != MODE_TEAM:
        raise ValueError("A Team workspace is permanent and cannot be changed back.")
    set_setting(db, KEY_MODE, mode)


def get_or_create_secret_key(db) -> str:
    """Return a stable, persisted Flask secret key, creating one on first boot."""
    try:
        key = get_setting(db, KEY_SECRET)
        if key:
            return key
        key = secrets.token_hex(32)
        set_setting(db, KEY_SECRET, key)
        db.commit()
        return key
    except Exception:
        # Never block startup on the settings table; fall back to ephemeral.
        return secrets.token_hex(32)
