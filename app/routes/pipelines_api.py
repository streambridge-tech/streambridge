import json
import re
from flask import Blueprint, jsonify, request
from app.utils.db import SessionLocal
from app.models.pipeline import Pipeline
from app.models.connector_config import ConnectorConfig
from app.models.alert import Alert
from app.utils.yaml_builder import _extract_top_block, build_pipeline
from app.services.connect.orchestrator import deploy_pipeline
from app.utils.auth import require


# `alert:` under source:/sink: plus every line indented deeper than it.
_ALERT_BLOCK_RE = re.compile(r'^([ \t]+)alert[ \t]*:[^\n]*\n?((?:\1[ \t]+[^\n]*\n?|[ \t]*\n)*)', re.MULTILINE)
_DEFAULT_ALERT_ATTEMPTS = 3


def _alert_blocks(yaml_raw: str) -> dict[str, str]:
    """Return {"source"|"sink": alert block text} for the sections that define an alert:."""
    blocks = {}
    for side in ("source", "sink"):
        m = _ALERT_BLOCK_RE.search(_extract_top_block(yaml_raw, side))
        if m:
            blocks[side] = m.group(2)
    return blocks


def _alert_value(block: str, key: str, value_re: str = r'[^\s#]+') -> str | None:
    m = re.search(rf'^[ \t]*{key}[ \t]*:[ \t]*({value_re})', block, re.MULTILINE)
    return m.group(1).strip() if m else None


def _alert_attempts_error(yaml_raw: str) -> str | None:
    """Return an error message when an alert's attempts is not a positive whole number."""
    for side, block in _alert_blocks(yaml_raw).items():
        attempts = _alert_value(block, "attempts")
        if attempts is not None and not (attempts.isdigit() and int(attempts) > 0):
            return f"{side}.alert.attempts must be a positive whole number, got '{attempts}'"
    return None


def _extract_alerts_from_yaml(yaml_raw: str, pipeline_id: str, pipeline_name: str,
                               src_connector: str, snk_connector: str) -> list[Alert]:
    """Parse alert: blocks from source/sink sections and return Alert instances.

    Callers validate attempts first with _alert_attempts_error().
    """
    alerts = []
    connectors = {"source": src_connector, "sink": snk_connector}
    for side, block in _alert_blocks(yaml_raw).items():
        connector_name = connectors[side]
        if not connector_name:
            continue
        attempts = _alert_value(block, "attempts")
        alerts.append(Alert(
            name=f"{connector_name}-alert",
            connector_name=connector_name,
            connector_type=side,
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            condition_metric="connector_status",
            condition_op="eq",
            condition_value="FAILED",
            severity=_alert_value(block, "severity") or "high",
            channel_type=_alert_value(block, "type") or "slack",
            channel_name=_alert_value(block, "channel_name") or "",
            message=_alert_value(block, "message", r'[^\n#]+') or "",
            attempts=int(attempts) if attempts else _DEFAULT_ALERT_ATTEMPTS,
            state="unknown",
        ))
    return alerts


def _bad_request(message: str):
    return jsonify({"error": message}), 400


def _yaml_request() -> tuple[str, str, str | None]:
    """Read yamlRaw/env from a build or deploy body. Returns (raw, env, error)."""
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        return "", "", "Request body must be a JSON object"
    raw = data.get("yamlRaw") or ""
    env = data.get("env") or ""
    if not isinstance(raw, str) or not isinstance(env, str):
        return "", "", "yamlRaw and env must be strings"
    return raw, env, None


def _create_request_error(data) -> str | None:
    """Validate a POST /api/pipelines body before anything is written."""
    if not isinstance(data, dict):
        return "Request body must be a JSON object"
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return "name is required"
    for field in ("env", "yamlRaw", "yamlResolved"):
        if not isinstance(data.get(field) or "", str):
            return f"{field} must be a string"
    connectors = data.get("connectors") or []
    if not isinstance(connectors, list):
        return "connectors must be a list"
    for i, connector in enumerate(connectors):
        if not isinstance(connector, dict):
            return f"connectors[{i}] must be an object"
        for field in ("connectorName", "type"):
            value = connector.get(field)
            if not isinstance(value, str) or not value.strip():
                return f"connectors[{i}].{field} is required"
    return _alert_attempts_error(data.get("yamlRaw") or "")

pipelines_api = Blueprint("pipelines_api", __name__, url_prefix="/api")


@pipelines_api.post("/pipelines/build")
@require("connector.validate")
def build():
    raw, env, error = _yaml_request()
    if error:
        return _bad_request(error)
    with SessionLocal() as db:
        result = build_pipeline(raw, env, db)
    return jsonify(result), 200 if result["ok"] else 422


@pipelines_api.post("/pipelines/deploy")
@require("connector.deploy")
def deploy():
    raw, env, error = _yaml_request()
    # Alerts are saved after the connectors deploy, so check them before deploying.
    error = error or _alert_attempts_error(raw)
    if error:
        return _bad_request(error)
    with SessionLocal() as db:
        build_result = build_pipeline(raw, env, db)
        if not build_result["ok"]:
            return jsonify({
                "ok": False,
                "logs": build_result["logs"],
                "pipelineId": None,
                "connectors": [],
            }), 422
        deploy_result = deploy_pipeline(raw, env, build_result, db)
        pid = deploy_result.get("pipelineId")
        if pid:
            connectors    = deploy_result.get("connectors", []) or []
            src_name      = next((c["name"] for c in connectors if c.get("type") == "source"), "")
            snk_name      = next((c["name"] for c in connectors if c.get("type") == "sink"),   "")
            pipeline_name = (build_result.get("meta") or {}).get("name", "")
            for alert in _extract_alerts_from_yaml(raw, pid, pipeline_name, src_name, snk_name):
                db.add(alert)
            db.commit()
    return jsonify(deploy_result), 200 if deploy_result["ok"] else 422


@pipelines_api.post("/pipelines")
@require("connector.create")
def create_pipeline():
    data = request.get_json(force=True)
    error = _create_request_error(data)
    if error:
        return _bad_request(error)
    with SessionLocal() as db:
        pipeline = Pipeline(
            name=data["name"],
            env=data.get("env") or "",
            yaml_raw=data.get("yamlRaw") or "",
            yaml_resolved=data.get("yamlResolved") or "",
            status="deploying",
        )
        db.add(pipeline)
        db.flush()

        src_connector_name = ""
        snk_connector_name = ""
        for connector in data.get("connectors") or []:
            db.add(ConnectorConfig(
                pipeline_id=pipeline.id,
                connector_name=connector["connectorName"],
                type=connector["type"],
                plugin_name=connector.get("pluginName") or "",
                config=json.dumps(connector.get("config", {})),
            ))
            if connector["type"] == "source":
                src_connector_name = connector["connectorName"]
            elif connector["type"] == "sink":
                snk_connector_name = connector["connectorName"]

        for alert in _extract_alerts_from_yaml(
            pipeline.yaml_raw, pipeline.id, pipeline.name,
            src_connector_name, snk_connector_name
        ):
            db.add(alert)

        db.commit()
        db.refresh(pipeline)
        return jsonify(pipeline.to_dict()), 201


@pipelines_api.get("/pipelines")
@require("connector.read")
def list_pipelines():
    with SessionLocal() as db:
        pipelines = db.query(Pipeline).order_by(Pipeline.created_at.desc()).all()
        return jsonify([p.to_dict() for p in pipelines])


@pipelines_api.get("/pipelines/<name>")
@require("connector.read")
def get_pipeline(name: str):
    with SessionLocal() as db:
        pipeline = db.query(Pipeline).filter(Pipeline.name == name).order_by(Pipeline.created_at.desc()).first()
        if not pipeline:
            return jsonify({"error": f"Pipeline '{name}' not found"}), 404
        connectors = db.query(ConnectorConfig).filter(ConnectorConfig.pipeline_id == pipeline.id).all()
        result = pipeline.to_dict()
        result["connectors"] = [c.to_dict() for c in connectors]
        return jsonify(result)


@pipelines_api.get("/pipelines/id/<pipeline_id>")
@require("connector.read")
def get_pipeline_by_id(pipeline_id: str):
    with SessionLocal() as db:
        pipeline = db.get(Pipeline, pipeline_id)
        if not pipeline:
            return jsonify({"error": f"Pipeline id={pipeline_id} not found"}), 404
        connectors = db.query(ConnectorConfig).filter(ConnectorConfig.pipeline_id == pipeline.id).all()
        result = pipeline.to_dict()
        result["connectors"] = [c.to_dict() for c in connectors]
        return jsonify(result)


_MOCK_SAMPLE_COLUMNS = ["op", "ts", "id", "name", "email", "amount"]
_MOCK_SAMPLE_OPS = ["c", "u", "d", "c", "c", "u", "c", "d", "u", "c"]


def _mock_sample_rows(limit: int, seed: str) -> list[list]:
    """Return up to `limit` deterministic-looking rows for a connector. Mocked for MVP."""
    from datetime import datetime, timedelta, timezone
    base = datetime.now(timezone.utc)
    names  = ["Alice Chen", "Bob Ortiz", "Carol Nakamura", "David Ehrenberg", "Emma Silva",
              "Farid Khan", "Grace Park", "Henri Dubois", "Iris Nguyen", "Jack Rivera"]
    domains = ["example.com", "acme.io", "biglab.dev", "ecom.co"]
    rows = []
    for i in range(min(limit, 10)):
        rows.append([
            _MOCK_SAMPLE_OPS[i % len(_MOCK_SAMPLE_OPS)],
            (base - timedelta(seconds=(9 - i) * 7)).isoformat(timespec="seconds"),
            1000 + i,
            names[i % len(names)],
            f"{names[i % len(names)].split()[0].lower()}@{domains[i % len(domains)]}",
            round(12.5 + (i * 4.75), 2),
        ])
    return rows


@pipelines_api.get("/pipelines/id/<pipeline_id>/connectors/<name>/sample")
@require("connector.read")
def sample_connector_rows(pipeline_id: str, name: str):
    limit = max(1, min(request.args.get("limit", 10, type=int) or 10, 100))
    with SessionLocal() as db:
        pipeline = db.get(Pipeline, pipeline_id)
        if not pipeline:
            return jsonify({"error": f"Pipeline id={pipeline_id} not found"}), 404
        connector = (
            db.query(ConnectorConfig)
            .filter(ConnectorConfig.pipeline_id == pipeline_id, ConnectorConfig.connector_name == name)
            .first()
        )
        if not connector:
            return jsonify({"error": f"Connector '{name}' not found for pipeline id={pipeline_id}"}), 404
    return jsonify({
        "connector": name,
        "type": connector.type,
        "columns": _MOCK_SAMPLE_COLUMNS,
        "rows": _mock_sample_rows(limit, f"{pipeline_id}:{name}"),
        "meta": {
            "note": "Sample data is mocked for MVP; real Kafka/DB sampling comes next.",
            "generatedAt": None,
        },
    })


@pipelines_api.patch("/pipelines/<name>")
@require("connector.save")
def update_pipeline(name: str):
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        return _bad_request("Request body must be a JSON object")
    with SessionLocal() as db:
        pipeline = db.query(Pipeline).filter(Pipeline.name == name).order_by(Pipeline.created_at.desc()).first()
        if not pipeline:
            return jsonify({"error": f"Pipeline '{name}' not found"}), 404
        if "status" in data:
            pipeline.status = data["status"]
        db.commit()
        db.refresh(pipeline)
        return jsonify(pipeline.to_dict())
