from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from app.utils.db import SessionLocal
from app.models.alert import Alert
from app.models.alert_delivery_attempt import AlertDeliveryAttempt
from app.models.connection import Connection
from app.models.connector_notebook import ConnectorNotebook
from app.services.alerting.deliver import deliver_test
from app.services.alerting.policy import dump_rules, policy_name, rules_from_payload
from app.services.alerting.scheduler import resolve_kc_connection
from app.utils.auth import require

alerts_api = Blueprint("alerts_api", __name__, url_prefix="/api/alerts")
_RULES = {"FAILED", "UNKNOWN", "PAUSED"}
_ACTIONS = {"pause", "re-trigger", "notify"}


def _check_every_min(data, default=5):
    try:
        n = int(data.get("checkEveryMin", default))
    except (TypeError, ValueError):
        return default
    if n < 1:
        return default
    return min(n, 10080)


def _rule(data, default="FAILED"):
    v = str(data.get("conditionValue", default) or default).upper()
    return v if v in _RULES else default


def _action(data, default="pause"):
    v = str(data.get("action", default) or default).lower()
    return v if v in _ACTIONS else default

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _alert_dict(db, alert: Alert) -> dict:
    d = alert.to_dict()
    d["kafkaConnectName"] = None
    try:
        conn = resolve_kc_connection(db, alert)
        if conn:
            d["kafkaConnectName"] = conn.name
    except Exception:
        pass
    return d


def _bind_notebook(db, alert: Alert, data: dict) -> tuple[dict | None, int | None]:
    """Attach the policy to a connector notebook and drop any pipeline binding."""
    if "notebookId" not in data:
        return None, None
    notebook_id = (data.get("notebookId") or "").strip()
    if not notebook_id:
        return {"error": "notebookId is required"}, 400
    notebook = db.get(ConnectorNotebook, notebook_id)
    if not notebook:
        return {"error": "Connector not found"}, 404
    name = (notebook.name or "").strip()
    if not name:
        return {"error": "Connector has no name"}, 400
    def _other(column, value):
        q = db.query(Alert).filter(column == value)
        if alert.id:
            q = q.filter(Alert.id != alert.id)
        return q.first()

    clash = _other(Alert.notebook_id, notebook.id) or _other(Alert.connector_name, name)
    if clash:
        return {
            "error": f"Alert already exists for connector '{name}'. Edit that policy instead.",
            "id": clash.id,
        }, 409
    alert.notebook_id = notebook.id
    alert.connector_name = name
    alert.connector_type = (notebook.connector_type or "source")[:16]
    alert.pipeline_id = None
    alert.pipeline_name = None
    return None, None


def _apply_policy(alert: Alert, data: dict, *, creating: bool) -> str | None:
    fallback_rule = "FAILED" if creating else alert.condition_value
    fallback_action = "pause" if creating else alert.match_action
    if creating or "rules" in data or "conditionValue" in data or "action" in data:
        rules, err = rules_from_payload(data, fallback_rule, fallback_action)
        if err:
            return err
        alert.rules_json = dump_rules(rules)
        alert.condition_value = rules[0]["rule"]
        alert.match_action = rules[0]["action"]
        if data.get("name"):
            alert.name = data["name"]
        else:
            alert.name = policy_name(alert.connector_name, rules)
    return None


@alerts_api.get("")
@require("alert.read")
def list_alerts():
    with SessionLocal() as db:
        alerts = db.query(Alert).order_by(Alert.created_at.desc()).all()
        alerts.sort(key=lambda a: (_SEVERITY_ORDER.get(a.severity, 9), a.created_at))
        return jsonify([_alert_dict(db, a) for a in alerts])


@alerts_api.post("")
@require("alert.create")
def create_alert():
    data = request.get_json(force=True)
    notebook_id = (data.get("notebookId") or "").strip()
    connector = (data.get("connectorName") or "").strip()
    if not connector and not notebook_id:
        return jsonify({"error": "connectorName is required"}), 400
    with SessionLocal() as db:
        existing = db.query(Alert).filter(Alert.connector_name == connector).first() if connector else None
        if existing and not notebook_id:
            return jsonify({
                "error": f"Alert already exists for connector '{connector}'. Edit that policy instead.",
                "id": existing.id,
            }), 409
        alert = Alert(
            name=data.get("name") or connector or "alert",
            connector_name=connector or notebook_id,
            connector_type=data.get("connectorType", "source"),
            pipeline_id=None if notebook_id else data.get("pipelineId"),
            pipeline_name=None if notebook_id else data.get("pipelineName"),
            notebook_id=None,
            condition_metric=data.get("conditionMetric", "connector_status"),
            condition_op=data.get("conditionOp", "eq"),
            condition_value="FAILED",
            severity=data.get("severity", "high"),
            channel_type=data.get("channelType", "slack"),
            channel_name=data.get("channelName", ""),
            message=data.get("message", ""),
            attempts=1,
            active=bool(data["active"]) if "active" in data else True,
            check_every_min=_check_every_min(data),
            match_action="pause",
            rules_json="[]",
            state="unknown",
        )
        err_body, err_status = _bind_notebook(db, alert, data)
        if err_body:
            return jsonify(err_body), err_status
        err = _apply_policy(alert, data, creating=True)
        if err:
            return jsonify({"error": err}), 400
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return jsonify(_alert_dict(db, alert)), 201


@alerts_api.patch("/<alert_id>")
@require("alert.edit")
def update_alert(alert_id: str):
    data = request.get_json(force=True)
    with SessionLocal() as db:
        alert = db.get(Alert, alert_id)
        if not alert:
            return jsonify({"error": "Alert not found"}), 404
        err_body, err_status = _bind_notebook(db, alert, data)
        if err_body:
            return jsonify(err_body), err_status
        if "notebookId" not in data and "connectorName" in data:
            next_name = (data.get("connectorName") or "").strip()
            if not next_name:
                return jsonify({"error": "connectorName is required"}), 400
            clash = (
                db.query(Alert)
                .filter(Alert.connector_name == next_name, Alert.id != alert.id)
                .first()
            )
            if clash:
                return jsonify({
                    "error": f"Alert already exists for connector '{next_name}'.",
                    "id": clash.id,
                }), 409
            alert.connector_name = next_name
        fields = [
            ("connectorType",   "connector_type"),
            ("conditionMetric", "condition_metric"),
            ("conditionOp",     "condition_op"),
            ("severity",        "severity"),
            ("channelType",     "channel_type"),
            ("channelName",     "channel_name"),
            ("message",         "message"),
            ("state",           "state"),
        ]
        if "notebookId" not in data:
            fields[1:1] = [
                ("pipelineId", "pipeline_id"),
                ("pipelineName", "pipeline_name"),
            ]
        for field, col in fields:
            if field in data and not (field == "connectorType" and "notebookId" in data):
                setattr(alert, col, data[field])
        err = _apply_policy(alert, data, creating=False)
        if err:
            return jsonify({"error": err}), 400
        if "active" in data:
            alert.active = bool(data["active"])
        if "checkEveryMin" in data:
            alert.check_every_min = _check_every_min(data, alert.check_every_min)
        if data.get("state") == "triggered":
            alert.last_fired_at = datetime.now(timezone.utc)
        alert.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(alert)
        return jsonify(_alert_dict(db, alert))


@alerts_api.delete("/<alert_id>")
@require("alert.delete")
def delete_alert(alert_id: str):
    with SessionLocal() as db:
        alert = db.get(Alert, alert_id)
        if not alert:
            return jsonify({"error": "Alert not found"}), 404
        db.query(AlertDeliveryAttempt).filter(AlertDeliveryAttempt.alert_id == alert_id).delete()
        db.delete(alert)
        db.commit()
        return jsonify({"ok": True})


@alerts_api.post("/<alert_id>/test")
@require("alert.test")
def test_alert(alert_id: str):
    """Fire a canned test message to every notification channel on this alert."""
    with SessionLocal() as db:
        alert = db.get(Alert, alert_id)
        if not alert:
            return jsonify({"error": "Alert not found"}), 404
        payload, status = deliver_test(db, alert)
        return jsonify(payload), status


def _history_page():
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    return max(1, page)


def _history_page_size():
    try:
        size = int(request.args.get("pageSize", request.args.get("limit", 20)))
    except (TypeError, ValueError):
        size = 20
    if size < 1:
        size = 20
    return min(size, 100)


@alerts_api.get("/<alert_id>/history")
@require("alert.read")
def alert_history(alert_id: str):
    """Latest delivery runs first, paginated."""
    page = _history_page()
    page_size = _history_page_size()
    with SessionLocal() as db:
        q = db.query(AlertDeliveryAttempt).filter(AlertDeliveryAttempt.alert_id == alert_id)
        total = q.count()
        pages = max(1, (total + page_size - 1) // page_size) if total else 1
        if page > pages:
            page = pages
        rows = (
            q.order_by(AlertDeliveryAttempt.created_at.desc(), AlertDeliveryAttempt.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        ids = [r.connection_id for r in rows if isinstance(r.connection_id, int)]
        names = {}
        if ids:
            for conn in db.query(Connection).filter(Connection.id.in_(ids)).all():
                names[conn.id] = conn.name
        items = []
        for r in rows:
            d = r.to_dict()
            d["connectionName"] = names.get(r.connection_id)
            items.append(d)
        return jsonify({
            "items": items,
            "page": page,
            "pageSize": page_size,
            "total": total,
            "pages": pages,
        })
