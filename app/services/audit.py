"""Audit recording. Best-effort: never breaks the action it records.

`record_event(...)` opens its own session and commits, so it is called after an
action has succeeded and does not interfere with the caller's transaction.
"""
from app.utils.logger import get_logger

log = get_logger(__name__)


def _actor(db):
    """Resolve the acting user from the request/session, if any."""
    from flask import g, has_request_context, session
    from app.utils.auth import SESSION_UID
    from app.models.user import User

    uid = None
    try:
        if has_request_context():
            uid = getattr(g, "user_id", None) or session.get(SESSION_UID)
    except Exception:
        uid = None
    if not uid:
        return None, "-"
    try:
        user = db.get(User, uid)
        return (user.id, user.username) if user else (uid, str(uid))
    except Exception:
        return (uid, str(uid))


def record(db, action, *, target_type="", target_id="", summary="", status="ok") -> None:
    """Append an audit row to the caller's session (caller commits)."""
    from app.models.audit import AuditEvent
    try:
        actor_id, actor = _actor(db)
        db.add(AuditEvent(
            actor_id=actor_id, actor=actor, action=str(action)[:64],
            target_type=str(target_type or "")[:32], target_id=str(target_id or "")[:256],
            summary=str(summary or "")[:512], status=str(status or "ok")[:16],
        ))
        db.flush()
    except Exception as e:  # never let auditing break the action
        log.warning("audit record failed for %s: %s", action, e)


def record_event(action, *, target_type="", target_id="", summary="", status="ok") -> None:
    """Record an audit event in its own committed session (post-action)."""
    from app.utils.db import SessionLocal
    try:
        with SessionLocal() as db:
            record(db, action, target_type=target_type, target_id=target_id, summary=summary, status=status)
            db.commit()
    except Exception as e:
        log.warning("audit record_event failed for %s: %s", action, e)
