from flask import Blueprint, jsonify, request

import math
from datetime import datetime, timezone

from app.models.connector_command_log import ConnectorCommandLog
from app.models.connector_notebook import ConnectorNotebook
from app.services.notebooks.deployer import NotebookDeployError, NotebookDeployer
from app.services.notebooks.logs import STEP_API, CommandLogWriter
from app.services.notebooks.store import NotebookStore
from app.services.notebooks.validator import NotebookValidator
from app.utils.auth import require
from app.utils.db import SessionLocal
from app.utils.logger import get_logger

log = get_logger("app.routes.notebooks")
notebooks_api = Blueprint("notebooks_api", __name__, url_prefix="/api/notebooks")
_store = NotebookStore()


def _logs(db, notebook_id: str, limit: int = 100):
    rows = (
        db.query(ConnectorCommandLog)
        .filter(ConnectorCommandLog.notebook_id == notebook_id)
        .order_by(ConnectorCommandLog.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [row.to_dict() for row in rows]


def _whole_number(value) -> int | None:
    """None for a missing value; numbers and numeric strings become ints, anything else is a ValueError."""
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"Not a number: {value!r}")
    number = float(value)  # ValueError for a non-numeric string
    if not math.isfinite(number):
        raise ValueError(f"Not a finite number: {value!r}")
    return int(number)


def _payload(db, notebook: ConnectorNotebook, logs=False, limit=100) -> dict:
    body = notebook.to_dict()
    if logs:
        body["logs"] = _logs(db, notebook.id, limit)
    return body


@notebooks_api.get("/")
@require("connector.read")
def list_notebooks():
    with SessionLocal() as db:
        rows = db.query(ConnectorNotebook).order_by(ConnectorNotebook.name).all()
        return jsonify([n.to_dict() for n in rows])


@notebooks_api.post("/")
@require("connector.create")
def create_notebook():
    data = request.get_json(force=True) or {}
    with SessionLocal() as db:
        name = str(data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name is required"}), 400
        notebook = ConnectorNotebook(name=name)
        if data.get("id"):
            notebook.id = str(data["id"])[:36]
        err = _store.apply(notebook, data)
        if err:
            return jsonify({"error": err}), 400
        db.add(notebook)
        db.commit()
        db.refresh(notebook)
        log.info("Notebook created  id=%s  name=%s", notebook.id, notebook.name)
        return jsonify(_payload(db, notebook)), 201


@notebooks_api.get("/<notebook_id>")
@require("connector.read")
def get_notebook(notebook_id: str):
    with SessionLocal() as db:
        notebook = db.get(ConnectorNotebook, notebook_id)
        if not notebook:
            return jsonify({"error": "Notebook not found"}), 404
        return jsonify(_payload(db, notebook, logs=True))


@notebooks_api.patch("/<notebook_id>")
@require("connector.save")
def update_notebook(notebook_id: str):
    data = request.get_json(force=True) or {}
    with SessionLocal() as db:
        notebook = db.get(ConnectorNotebook, notebook_id)
        if not notebook:
            return jsonify({"error": "Notebook not found"}), 404
        err = _store.apply(notebook, data)
        if err:
            return jsonify({"error": err}), 400
        db.commit()
        db.refresh(notebook)
        return jsonify(_payload(db, notebook))


@notebooks_api.delete("/<notebook_id>")
@require("connector.delete_record")
def delete_notebook(notebook_id: str):
    with SessionLocal() as db:
        notebook = db.get(ConnectorNotebook, notebook_id)
        if not notebook:
            return jsonify({"error": "Notebook not found"}), 404
        name = notebook.name
        db.query(ConnectorCommandLog).filter(ConnectorCommandLog.notebook_id == notebook_id).delete()
        db.delete(notebook)
        db.commit()
        log.info("Notebook deleted  id=%s", notebook_id)
        from app.services.audit import record_event
        record_event("connector.delete", target_type="connector", target_id=notebook_id,
                     summary=f"Deleted connector {name}")
        return jsonify({"ok": True})


@notebooks_api.post("/<notebook_id>/live")
@require("connector.read")
def set_live_status(notebook_id: str):
    """Cache the connector's observed Kafka Connect state. Does not bump updated_at."""
    data = request.get_json(force=True) or {}
    state = str(data.get("state") or "").strip().lower()[:16]
    tasks = str(data.get("tasks") or "")[:16]
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        updated = (
            db.query(ConnectorNotebook)
            .filter(ConnectorNotebook.id == notebook_id)
            .update(
                {
                    "live_state": state,
                    "live_tasks": tasks or None,
                    "live_checked_at": now,
                    # Keep updated_at from bumping on a status-only cache write.
                    "updated_at": ConnectorNotebook.updated_at,
                },
                synchronize_session=False,
            )
        )
        if not updated:
            return jsonify({"error": "Notebook not found"}), 404
        db.commit()
        return jsonify({"ok": True, "liveState": state, "liveTasks": tasks, "liveCheckedAt": now.isoformat()})


@notebooks_api.get("/<notebook_id>/logs")
@require("connector.read")
def list_logs(notebook_id: str):
    limit = request.args.get("limit", 100, type=int) or 100
    with SessionLocal() as db:
        notebook = db.get(ConnectorNotebook, notebook_id)
        if not notebook:
            return jsonify({"error": "Notebook not found"}), 404
        return jsonify({"items": _logs(db, notebook_id, limit)})


@notebooks_api.post("/<notebook_id>/logs")
@require("connector.save")
def append_log(notebook_id: str):
    data = request.get_json(force=True) or {}
    try:
        http_status = _whole_number(data.get("http"))
        latency_ms = _whole_number(data.get("timeMs")) or 0
    except ValueError:
        return jsonify({"error": "'http' and 'timeMs' must be numbers"}), 400
    with SessionLocal() as db:
        notebook = db.get(ConnectorNotebook, notebook_id)
        if not notebook:
            return jsonify({"error": "Notebook not found"}), 404
        writer = CommandLogWriter(db, notebook_id)
        status = "ok" if (http_status or 0) < 400 else "error"
        row = writer.record(
            str(data.get("step") or data.get("key") or STEP_API),
            status,
            message=str(data.get("action") or data.get("message") or "API command")[:512],
            detail=str(data.get("bodyText") or data.get("detail") or "")[:8000] or None,
            http_status=http_status,
            latency_ms=latency_ms,
        )
        db.commit()
        db.refresh(row)
        return jsonify(row.to_dict()), 201


@notebooks_api.post("/<notebook_id>/validate")
@require("connector.validate")
def validate_notebook(notebook_id: str):
    data = request.get_json(silent=True) or {}
    with SessionLocal() as db:
        notebook = db.get(ConnectorNotebook, notebook_id)
        if not notebook:
            return jsonify({"error": "Notebook not found"}), 404
        if data:
            err = _store.apply(notebook, data)
            if err:
                return jsonify({"ok": False, "error": err, "errors": [err]}), 400
            db.flush()
        result = NotebookValidator(db).validate(notebook)
        db.commit()
        db.refresh(notebook)
        status = 200 if result.get("ok") else int(result.get("httpStatus") or 400)
        log.info("Notebook validate  id=%s  ok=%s", notebook_id, result.get("ok"))
        return jsonify({
            "ok": result.get("ok"),
            "errors": result.get("errors") or [],
            "message": result.get("message"),
            "errorCount": result.get("errorCount") or 0,
            "notebook": _payload(db, notebook, logs=True),
        }), status


@notebooks_api.post("/<notebook_id>/deploy")
@require("connector.deploy")
def deploy_notebook(notebook_id: str):
    data = request.get_json(silent=True) or {}
    with SessionLocal() as db:
        notebook = db.get(ConnectorNotebook, notebook_id)
        if not notebook:
            return jsonify({"error": "Notebook not found"}), 404
        if data:
            err = _store.apply(notebook, data)
            if err:
                return jsonify({"error": err, "ok": False}), 400
            db.flush()
        try:
            result = NotebookDeployer(db).deploy(notebook)
        except NotebookDeployError as exc:
            db.commit()
            db.refresh(notebook)
            log.warning("Notebook deploy failed  id=%s  step=%s  err=%s", notebook_id, exc.step, exc.message)
            return jsonify({
                "ok": False,
                "error": exc.message,
                "step": exc.step,
                "notebook": _payload(db, notebook, logs=True),
            }), 502
        db.commit()
        db.refresh(notebook)
        from app.services.audit import record_event
        record_event("connector.deploy", target_type="connector", target_id=notebook.id,
                     summary=f"Deployed connector {notebook.name}")
        return jsonify({
            "ok": True,
            "result": result,
            "notebook": _payload(db, notebook, logs=True),
        })
