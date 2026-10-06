import json
import re
from flask import Blueprint, jsonify, request
from app.utils.db import SessionLocal
from app.models.pipeline import Pipeline
from app.models.connector_config import ConnectorConfig
from app.models.alert import Alert
from app.utils.yaml_builder import build_pipeline
from app.services.connect.orchestrator import deploy_pipeline
from app.utils.auth import require


def _extract_alerts_from_yaml(yaml_raw: str, pipeline_id: str, pipeline_name: str,
                               src_connector: str, snk_connector: str) -> list[Alert]:
    """Parse alert: blocks from source/sink sections and return Alert instances."""
    alerts = []

    def _parse_block(section_text: str, connector_name: str, connector_type: str):
        if not re.search(r'alert\s*:', section_text):
            return
        type_m    = re.search(r'type\s*:\s*([^\s#\n]+)', section_text)
        chan_m    = re.search(r'channel_name\s*:\s*([^\s#\n]+)', section_text)
        msg_m     = re.search(r'message\s*:\s*([^\n#]+)', section_text)
        sev_m     = re.search(r'severity\s*:\s*([^\s#\n]+)', section_text)
        retry_m   = re.search(r'attempts\s*:\s*([^\s#\n]+)', section_text)
        alerts.append(Alert(
            name=f"{connector_name}-alert",
            connector_name=connector_name,
            connector_type=connector_type,
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            condition_metric="connector_status",
            condition_op="eq",
            condition_value="FAILED",
            severity=sev_m.group(1).strip() if sev_m else "high",
            channel_type=type_m.group(1).strip() if type_m else "slack",
            channel_name=chan_m.group(1).strip() if chan_m else "",
            message=msg_m.group(1).strip() if msg_m else "",
            attempts=int(retry_m.group(1).strip()) if retry_m else 3,
            state="unknown",
        ))

    src_m = re.search(r'^source:[\s\S]*?(?=^(?:kafka|transforms|sink|on_failure|\Z))', yaml_raw, re.MULTILINE)
    snk_m = re.search(r'^sink:[\s\S]*?(?=^(?:on_failure|\Z))', yaml_raw, re.MULTILINE)
    if src_m and src_connector:
        _parse_block(src_m.group(0), src_connector, "source")
    if snk_m and snk_connector:
        _parse_block(snk_m.group(0), snk_connector, "sink")
    return alerts

pipelines_api = Blueprint("pipelines_api", __name__, url_prefix="/api")


@pipelines_api.post("/pipelines/build")
@require("connector.validate")
def build():
    data = request.get_json(force=True)
    raw  = data.get("yamlRaw", "")
    env  = data.get("env", "") or ""
    with SessionLocal() as db:
        result = build_pipeline(raw, env, db)
    return jsonify(result), 200 if result["ok"] else 422


@pipelines_api.post("/pipelines/deploy")
@require("connector.deploy")
def deploy():
    data = request.get_json(force=True)
    raw  = data.get("yamlRaw", "")
    env  = data.get("env", "") or ""
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
    with SessionLocal() as db:
        pipeline = Pipeline(
            name=data["name"],
            env=data.get("env", ""),
            yaml_raw=data.get("yamlRaw", ""),
            yaml_resolved=data.get("yamlResolved", ""),
            status="deploying",
        )
        db.add(pipeline)
        db.flush()

        src_connector_name = ""
        snk_connector_name = ""
        for connector in data.get("connectors", []):
            db.add(ConnectorConfig(
                pipeline_id=pipeline.id,
                connector_name=connector["connectorName"],
                type=connector["type"],
                plugin_name=connector.get("pluginName", ""),
                config=json.dumps(connector.get("config", {})),
            ))
            if connector["type"] == "source":
                src_connector_name = connector["connectorName"]
            elif connector["type"] == "sink":
                snk_connector_name = connector["connectorName"]

        for alert in _extract_alerts_from_yaml(
            data.get("yamlRaw", ""), pipeline.id, pipeline.name,
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
    limit = min(int(request.args.get("limit", 10) or 10), 100)
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
    with SessionLocal() as db:
        pipeline = db.query(Pipeline).filter(Pipeline.name == name).order_by(Pipeline.created_at.desc()).first()
        if not pipeline:
            return jsonify({"error": f"Pipeline '{name}' not found"}), 404
        if "status" in data:
            pipeline.status = data["status"]
        db.commit()
        db.refresh(pipeline)
        return jsonify(pipeline.to_dict())
