from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone

from app.models.alert import Alert
from app.models.connection import Connection
from app.models.connector_notebook import ConnectorNotebook
from app.models.pipeline import Pipeline
from app.services.alerting.deliver import fire_alert
from app.services.alerting.policy import first_match, rules_for
from app.services.connect.factory import get_backend
from app.services.connect.orchestrator import _extract_env_conn_name
from app.services.connect.rest_backend import effective_connect_status
from app.utils.db import SessionLocal, reopen_db
from app.utils.logger import get_logger
from app.utils.yaml_builder import _extract_env_block

log = get_logger(__name__)

WAKE_SEC = 30
_lock = threading.Lock()
_instance: AlertScheduler | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def rule_matches(alert, status: str) -> bool:
    _, item = first_match(rules_for(alert), status)
    return item is not None


def is_due(alert: Alert, now: datetime, last_checked: dict[str, datetime]) -> bool:
    prev = last_checked.get(alert.id)
    if prev is None:
        return True
    mins = max(1, int(alert.check_every_min or 5))
    return now >= prev + timedelta(minutes=mins)


def bound_connector_name(db, alert: Alert) -> str:
    """Live Connect name. A bound notebook wins over a stored copy of the name."""
    notebook_id = getattr(alert, "notebook_id", None)
    if isinstance(notebook_id, str) and notebook_id:
        notebook = db.get(ConnectorNotebook, notebook_id)
        if notebook and (notebook.name or "").strip():
            return notebook.name.strip()
    return (alert.connector_name or "").strip()


def resolve_kc_connection(db, alert: Alert):
    notebook_id = getattr(alert, "notebook_id", None)
    if isinstance(notebook_id, str) and notebook_id:
        notebook = db.get(ConnectorNotebook, notebook_id)
        cluster = (notebook.attached_cluster or "").strip() if notebook else ""
        if cluster:
            conn = db.query(Connection).filter(Connection.name == cluster).first()
            if conn:
                return conn
    if alert.pipeline_id:
        pipeline = db.get(Pipeline, alert.pipeline_id)
        if pipeline:
            env_block = _extract_env_block(pipeline.yaml_raw or "", pipeline.env or "")
            name = _extract_env_conn_name(env_block, "kafka_connect.connection")
            if name:
                conn = db.query(Connection).filter(Connection.name == name).first()
                if conn:
                    return conn
    return (
        db.query(Connection)
        .filter(Connection.subtype == "kafka-connect")
        .first()
    )


def resolve_kc_backend(db, alert: Alert):
    conn = resolve_kc_connection(db, alert)
    return get_backend(conn.config or {}) if conn else None


def _status_from_payload(data: dict) -> str:
    return effective_connect_status(data)


def format_connect_status(data: dict) -> str:
    lines = []
    connector = data.get("connector") or {}
    lines.append(f"Connector: {(connector.get('state') or 'UNKNOWN')}")
    worker = connector.get("worker_id")
    if worker:
        lines.append(f"Worker: {worker}")
    tasks = data.get("tasks") or []
    if not tasks:
        lines.append("Tasks: none")
    for task in tasks:
        tid = task.get("id", "?")
        tstate = task.get("state") or "UNKNOWN"
        lines.append(f"Task {tid}: {tstate}")
        trace = (task.get("trace") or "").strip()
        if trace:
            lines.append(trace[:4000])
    return "\n".join(lines)


def poll_connector_snapshot(backend, connector_name: str) -> dict:
    if backend is None:
        log.warning("Alert scheduler no Kafka Connect connection  connector=%s", connector_name)
        return {"status": "UNKNOWN", "log": "No Kafka Connect connection.", "raw": {}}
    try:
        if hasattr(backend, "get_status"):
            raw = backend.get_status(connector_name)
            if isinstance(raw, dict):
                return {
                    "status": _status_from_payload(raw),
                    "log": format_connect_status(raw),
                    "raw": raw,
                }
        status = (backend.poll_status(connector_name) or "UNKNOWN").upper()
        return {"status": status, "log": f"State: {status}", "raw": {}}
    except Exception as exc:
        log.warning("Alert scheduler poll failed  connector=%s  err=%s", connector_name, type(exc).__name__)
        return {"status": "UNKNOWN", "log": f"Status poll failed: {type(exc).__name__}", "raw": {}}


def poll_connector(backend, connector_name: str) -> str:
    return poll_connector_snapshot(backend, connector_name)["status"]


def _task_ids_for_retrigger(data: dict) -> list[int]:
    tasks = (data or {}).get("tasks") or []
    all_ids: list[int] = []
    failed_ids: list[int] = []
    for task in tasks:
        raw_id = (task or {}).get("id")
        if raw_id is None:
            continue
        try:
            tid = int(raw_id)
        except (TypeError, ValueError):
            continue
        all_ids.append(tid)
        if str((task or {}).get("state") or "").upper() == "FAILED":
            failed_ids.append(tid)
    return failed_ids or all_ids


def apply_match_action(backend, connector_name: str, status: str, action: str, snapshot: dict | None = None) -> dict:
    act = (action or "pause").lower()
    if act not in ("pause", "re-trigger", "notify"):
        act = "pause"
    if act == "notify":
        log.info("Alert action notify  connector=%s  status=%s", connector_name, status)
        return {"action": act, "ok": True, "error": None}
    if act == "pause" and (status or "").upper() == "PAUSED":
        log.info("Alert action skipped  connector=%s  action=pause  reason=already-paused", connector_name)
        return {"action": act, "ok": True, "error": None}
    if backend is None:
        log.warning(
            "Alert action skipped  connector=%s  action=%s  reason=no-kc",
            connector_name, act,
        )
        return {"action": act, "ok": False, "error": "no Kafka Connect connection"}
    try:
        if act == "re-trigger":
            if (status or "").upper() == "PAUSED":
                backend.resume(connector_name)
            else:
                raw = (snapshot or {}).get("raw") if isinstance(snapshot, dict) else None
                if not isinstance(raw, dict) and hasattr(backend, "get_status"):
                    fetched = backend.get_status(connector_name)
                    raw = fetched if isinstance(fetched, dict) else {}
                task_ids = _task_ids_for_retrigger(raw if isinstance(raw, dict) else {})
                if not task_ids:
                    raise RuntimeError("no tasks to restart")
                if not hasattr(backend, "restart_task"):
                    raise RuntimeError("backend cannot restart tasks")
                for tid in task_ids:
                    backend.restart_task(connector_name, tid)
                log.info(
                    "Alert action retrigger tasks  connector=%s  tasks=%s",
                    connector_name, ",".join(str(t) for t in task_ids),
                )
        else:
            backend.pause(connector_name)
        log.info(
            "Alert action ran  connector=%s  action=%s  status=%s",
            connector_name, act, status,
        )
        return {"action": act, "ok": True, "error": None}
    except Exception as exc:
        log.warning(
            "Alert action failed  connector=%s  action=%s  err=%s",
            connector_name, act, type(exc).__name__,
        )
        return {"action": act, "ok": False, "error": type(exc).__name__}


class AlertScheduler:
    def __init__(self, wake_sec: int = WAKE_SEC, session_factory=SessionLocal):
        self._wake = wake_sec
        self._session_factory = session_factory
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_checked: dict[str, datetime] = {}
        self.last_status: dict[str, str] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="alert-scheduler", daemon=True)
        self._thread.start()
        log.info("Alert scheduler started  wake=%ss", self._wake)

    def stop(self) -> None:
        self._stop.set()
        log.info("Alert scheduler stopping")

    def _loop(self) -> None:
        while True:
            try:
                self.tick()
            except Exception as exc:
                if "readonly database" in str(exc).lower():
                    log.warning("Alert scheduler database file changed; reopening it")
                    reopen_db()
                else:
                    log.exception("Alert scheduler tick failed")
            if self._stop.wait(self._wake):
                break

    def tick(self, now: datetime | None = None) -> None:
        now = now or _now()
        stats = {"active": 0, "due": 0, "fired": 0, "quiet": 0, "hold": 0}
        with self._session_factory() as db:
            alerts = db.query(Alert).filter(Alert.active.is_(True)).all()
            stats["active"] = len(alerts)
            for alert in alerts:
                self._eval(db, alert, now, stats)
        log.info(
            "Alert scheduler tick  active=%s  due=%s  fired=%s  quiet=%s  hold=%s",
            stats["active"], stats["due"], stats["fired"], stats["quiet"], stats["hold"],
        )

    def _eval(self, db, alert: Alert, now: datetime, stats: dict) -> None:
        if not is_due(alert, now, self.last_checked):
            stats["hold"] += 1
            log.debug(
                "Alert scheduler hold  id=%s  connector=%s  every=%smin",
                alert.id, alert.connector_name, alert.check_every_min,
            )
            return
        stats["due"] += 1
        backend = resolve_kc_backend(db, alert)
        connector_name = bound_connector_name(db, alert)
        snap = poll_connector_snapshot(backend, connector_name)
        status = snap["status"]
        self.last_checked[alert.id] = now
        prev = self.last_status.get(alert.id)
        self.last_status[alert.id] = status
        rules = rules_for(alert)
        log.info(
            "Alert scheduler poll  id=%s  connector=%s  status=%s  prev=%s  rules=%s",
            alert.id, alert.connector_name, status, prev or "-",
            ",".join(f"{r['rule']}:{r['action']}" for r in rules) or "-",
        )
        idx, matched = first_match(rules, status)
        if matched is None:
            stats["quiet"] += 1
            log.info(
                "Alert policy quiet  id=%s  connector=%s  status=%s  reason=no-rule-match",
                alert.id, alert.connector_name, status,
            )
            return
        for skip_i, skip in enumerate(rules):
            if skip_i >= idx:
                break
            log.info(
                "Alert policy skip  id=%s  connector=%s  idx=%s  rule=%s  status=%s",
                alert.id, alert.connector_name, skip_i, skip["rule"], status,
            )
        stats["fired"] += 1
        log.info(
            "Alert policy match  id=%s  connector=%s  idx=%s  rule=%s  action=%s  status=%s  prev=%s",
            alert.id, alert.connector_name, idx, matched["rule"], matched["action"], status, prev or "-",
        )
        action_res = apply_match_action(
            backend, connector_name, status, matched["action"], snapshot=snap,
        )
        fire_alert(
            db, alert, status,
            action=action_res["action"],
            action_ok=action_res["ok"],
            action_error=action_res.get("error"),
            connect_log=snap.get("log") or "",
        )


def start_alert_scheduler(*, debug: bool = False) -> AlertScheduler | None:
    if os.environ.get("STREAMBRIDGE_ALERT_SCHEDULER", "1").lower() in ("0", "false", "off", "no"):
        log.info("Alert scheduler disabled  STREAMBRIDGE_ALERT_SCHEDULER=off")
        return None
    if debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        log.debug("Alert scheduler skip  werkzeug reloader parent")
        return None
    global _instance
    with _lock:
        if _instance is None:
            _instance = AlertScheduler()
            _instance.start()
        return _instance
