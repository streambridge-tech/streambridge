from datetime import datetime, timezone

from app.models.alert import Alert
from app.models.alert_delivery_attempt import AlertDeliveryAttempt
from app.models.connection import Connection
from app.services.alerting.channels.factory import get_channel, supported_subtypes
from app.utils.logger import get_logger

log = get_logger(__name__)

CHANNEL_TYPE_TO_SUBTYPE = {
    "slack": "notification-slack",
    "gchat": "notification-gchat",
    "google-chat": "notification-gchat",
    "googlechat": "notification-gchat",
}

_STATE_WORD = {
    "PAUSED": "paused",
    "FAILED": "failed",
    "UNKNOWN": "unknown",
}
_LOG_MAX = 8000


def channel_names(alert: Alert) -> list[str]:
    return [n.strip() for n in (alert.channel_name or "").split(",") if n.strip()]


def compose_alert_message(connector: str, status: str, action: str, *, action_ok: bool = True, kind: str = "fire") -> str:
    name = connector or "connector"
    if kind == "test":
        return f"StreamBridge test for {name} — this channel is wired."
    state = _STATE_WORD.get((status or "").upper(), (status or "unhealthy").lower())
    if (action or "pause").lower() == "notify":
        return f"{name} was {state}."
    if (action or "pause").lower() == "re-trigger":
        did = "re-triggered it" if action_ok else "tried to re-trigger it, but the action failed"
    else:
        did = "paused it" if action_ok else "tried to pause it, but the action failed"
    return f"{name} was {state}. StreamBridge {did}."


def find_notification_connections(db, alert: Alert) -> list[Connection]:
    found: list[Connection] = []
    seen: set[int] = set()
    for name in channel_names(alert):
        row = db.query(Connection).filter(Connection.name == name).first()
        if row and row.id not in seen:
            found.append(row)
            seen.add(row.id)
    if found:
        return found
    subtype = CHANNEL_TYPE_TO_SUBTYPE.get((alert.channel_type or "").lower())
    if not subtype:
        return []
    row = db.query(Connection).filter(Connection.subtype == subtype).first()
    return [row] if row else []


def _send_channels(conns, message: str, meta: dict) -> tuple[list[dict], bool, int | None, str | None, int]:
    out = []
    first_error = None
    max_latency = 0
    http = None
    for conn in conns:
        ch = get_channel(conn.subtype)
        if not ch:
            err = f"Channel type '{conn.subtype}' is not implemented yet."
            out.append({"name": conn.name, "success": False, "error": err, "http": None, "latencyMs": 0})
            first_error = first_error or err
            continue
        result = ch.send(conn.config or {}, message, meta=meta)
        line = {
            "name": conn.name,
            "success": result.success,
            "error": result.error,
            "http": result.http_status,
            "latencyMs": result.latency_ms,
        }
        out.append(line)
        max_latency = max(max_latency, result.latency_ms or 0)
        if http is None:
            http = result.http_status
        if result.success:
            log.info(
                "Alert delivered  channel=%s  subtype=%s  http=%s  latency_ms=%s",
                conn.name, conn.subtype, result.http_status, result.latency_ms,
            )
        else:
            log.warning(
                "Alert deliver failed  channel=%s  subtype=%s  http=%s  err=%s",
                conn.name, conn.subtype, result.http_status, result.error,
            )
            first_error = first_error or result.error
    ok = bool(out) and all(c["success"] for c in out)
    return out, ok, http, first_error, max_latency


def _format_channel_log(channels: list[dict]) -> str:
    if not channels:
        return "Channels: none"
    lines = ["Channels:"]
    for c in channels:
        if c["success"]:
            lines.append(f"  {c['name']}  sent  HTTP {c.get('http') or '—'}  {c.get('latencyMs') or 0}ms")
        else:
            lines.append(f"  {c['name']}  failed  {c.get('error') or 'error'}")
    return "\n".join(lines)


def _build_log(*, connect_log: str, action: str, action_ok: bool, action_error: str | None, channels: list[dict]) -> str:
    bits = []
    if connect_log:
        bits.append(connect_log.strip())
    else:
        bits.append("No connector error.")
    verb = (action or "pause").lower()
    if verb in ("", "none"):
        bits.append("Action: none")
    elif action_ok:
        bits.append(f"Action: {verb} — ok")
    else:
        bits.append(f"Action: {verb} — failed" + (f" ({action_error})" if action_error else ""))
    bits.append(_format_channel_log(channels))
    text = "\n".join(bits)
    return text[:_LOG_MAX]


def _persist_run(db, alert: Alert, *, kind: str, status: str, message: str, success: bool,
                 http_status, error, latency_ms, log_text: str) -> None:
    db.add(AlertDeliveryAttempt(
        alert_id=alert.id,
        connection_id=None,
        channel=alert.channel_type or "unknown",
        kind=kind,
        success=1 if success else 0,
        http_status=http_status,
        error=error,
        latency_ms=latency_ms or 0,
        message=message,
        status=status,
        log_text=log_text,
    ))
    db.commit()


def fire_alert(db, alert: Alert, status: str, *, action: str = "pause", action_ok: bool = True,
               action_error: str | None = None, connect_log: str = "") -> None:
    now = datetime.now(timezone.utc)
    alert.state = "triggered"
    alert.last_fired_at = now
    alert.updated_at = now
    msg = compose_alert_message(alert.connector_name, status, action, action_ok=action_ok)
    conns = find_notification_connections(db, alert)
    if not conns:
        log.warning(
            "Alert deliver skipped  id=%s  connector=%s  reason=no-channel  wanted=%s",
            alert.id, alert.connector_name, alert.channel_name or alert.channel_type,
        )
        err = "No notification connection found"
        _persist_run(
            db, alert, kind="fire", status=status, message=msg, success=False,
            http_status=None, error=err, latency_ms=0,
            log_text=_build_log(
                connect_log=connect_log, action=action, action_ok=action_ok,
                action_error=action_error, channels=[],
            ) + f"\n{err}",
        )
        return
    channels, ok, http, err, latency = _send_channels(conns, msg, {"kind": "fire", "status": status})
    _persist_run(
        db, alert, kind="fire", status=status, message=msg, success=ok,
        http_status=http, error=err, latency_ms=latency,
        log_text=_build_log(
            connect_log=connect_log, action=action, action_ok=action_ok,
            action_error=action_error, channels=channels,
        ),
    )


def deliver_test(db, alert: Alert) -> tuple[dict, int]:
    conns = find_notification_connections(db, alert)
    msg = compose_alert_message(alert.connector_name, "test", "pause", kind="test")
    if not conns:
        return {
            "success": False,
            "error": (
                f"No {alert.channel_type} notification connection found for '{alert.channel_name or '(unset)'}'. "
                f"Supported subtypes: {', '.join(supported_subtypes())}."
            ),
            "channels": [],
        }, 404

    channels, ok, http, err, latency = _send_channels(conns, msg, {"kind": "test"})
    unimplemented = [c for c in channels if not c["success"] and "not implemented" in (c.get("error") or "")]
    _persist_run(
        db, alert, kind="test", status="test", message=msg, success=ok,
        http_status=http, error=err, latency_ms=latency,
        log_text=_build_log(
            connect_log="Send test — no connector poll.",
            action="none", action_ok=True, action_error=None, channels=channels,
        ),
    )
    first = channels[0]
    payload_channels = [{
        "name": c["name"], "success": c["success"], "error": c.get("error"),
        "httpStatus": c.get("http"), "latencyMs": c.get("latencyMs") or 0,
    } for c in channels]
    if unimplemented and len(unimplemented) == len(channels):
        return {
            "success": False, "error": first["error"],
            "channel": {"name": first["name"]},
            "channels": payload_channels,
        }, 501
    return {
        "success": ok,
        "httpStatus": http,
        "error": None if ok else err,
        "latencyMs": latency,
        "channel": {"name": first["name"]},
        "channels": payload_channels,
    }, (200 if ok else 502)
