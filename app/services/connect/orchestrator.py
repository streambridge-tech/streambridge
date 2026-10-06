"""Orchestrate a Kafka Connect deploy for a StreamBridge pipeline.

Deploys source connector → polls until RUNNING → deploys sink connector → polls
until RUNNING. Persists a Pipeline row plus one ConnectorConfig per side. On any
step failure the pipeline is marked FAILED and orchestration stops; already-deployed
connectors are left in place (no rollback).
"""

import json
import re
import time

from app.models.connection import Connection
from app.models.connector_config import ConnectorConfig
from app.models.pipeline import Pipeline
from app.services.connect.factory import deployment_of, get_backend
from app.services.connect.rest_backend import ConfigValidationError
from app.utils.yaml_builder import _extract_env_block, _extract_top_block, resolve_yaml


POLL_INTERVAL_SEC = 2
POLL_TIMEOUT_SEC  = 30

# Connection role → connector-level YAML key. Populated per side.
_SOURCE_ROLES = ("db", "kafka", "schema_registry")
_SINK_ROLES   = ("storage", "kafka", "schema_registry")


def _extract_env_conn_name(env_block: str, key: str) -> str | None:
    m = re.search(rf'^[ \t]+{re.escape(key)}\s*:\s*(.+)$', env_block, re.MULTILINE)
    if not m:
        return None
    val = m.group(1).strip()
    cm = re.match(r"\{\{\s*conn\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}", val)
    return cm.group(1) if cm else None


def _extract_side_conn_name(resolved_block: str, role: str) -> str | None:
    role_key = f"{role}.connection"
    m = re.search(
        rf'^[ \t]+{re.escape(role_key)}\s*:\s*\[connection:([^\]]+)\]',
        resolved_block, re.MULTILINE,
    )
    return m.group(1) if m else None


def _fetch_connection(db, name: str) -> Connection | None:
    return db.query(Connection).filter(Connection.name == name).first()


def _inject_creds(config: dict, connection: Connection | None) -> dict:
    if not connection or not connection.config:
        return config
    # existing config values (from plugin base + YAML) win over connection values
    return {**connection.config, **config}


def poll_until_running(
    backend, name: str,
    timeout: int = POLL_TIMEOUT_SEC,
    interval: int = POLL_INTERVAL_SEC,
    sleep=time.sleep,
    now=time.time,
) -> str:
    """Poll backend.poll_status until RUNNING or FAILED or timeout. Returns final state.

    Always polls at least once so callers using timeout=0 still get a real state.
    """
    deadline = now() + timeout
    while True:
        state = backend.poll_status(name)
        if state in ("RUNNING", "FAILED"):
            return state
        if now() >= deadline:
            return state
        sleep(interval)


def _save_connector(db, pipeline_id, connector_name, ctype, plugin_name, config):
    db.add(ConnectorConfig(
        pipeline_id=pipeline_id,
        connector_name=connector_name,
        type=ctype,
        plugin_name=plugin_name,
        config=json.dumps(config),
    ))
    db.commit()


def _fail_result(logs, pipeline_id, connectors):
    return {"ok": False, "logs": logs, "pipelineId": pipeline_id, "connectors": connectors}


def _log_validation_errors(log, side: str, name: str, err: ConfigValidationError) -> None:
    """Emit one log line per KC field error so the UI can render each on its own row."""
    log("error", f"{side} '{name}' — Kafka Connect rejected the config for plugin '{err.plugin_class}':")
    for fe in err.field_errors:
        field = fe.get("field") or "?"
        # Show first error per field; typical KC responses only have one anyway.
        msg   = (fe.get("errors") or ["invalid"])[0]
        log("error", f"  • {field}: {msg}")
    log("info", "Fix the fields above and re-deploy. No connector was created on Kafka Connect.")


def deploy_pipeline(
    raw_yaml: str,
    env: str,
    build_result: dict,
    db,
    poll_timeout: int = POLL_TIMEOUT_SEC,
    poll_interval: int = POLL_INTERVAL_SEC,
    sleep=time.sleep,
    now=time.time,
) -> dict:
    logs: list[dict] = []
    def log(level, text): logs.append({"level": level, "text": text})

    if not build_result.get("ok"):
        return _fail_result(
            build_result.get("logs", []) + [{"level": "error", "text": "cannot deploy: build failed"}],
            None, [],
        )

    resolved     = resolve_yaml(raw_yaml, env)
    env_block    = _extract_env_block(raw_yaml, env)
    src_block    = _extract_top_block(resolved, "source")
    snk_block    = _extract_top_block(resolved, "sink")

    kc_conn_name = _extract_env_conn_name(env_block, "kafka_connect.connection")
    if not kc_conn_name:
        log("error", "kafka_connect.connection not resolvable to a connection name")
        return _fail_result(logs, None, [])

    kc_connection = _fetch_connection(db, kc_conn_name)
    if not kc_connection:
        log("error", f"kafka_connect connection '{kc_conn_name}' not found in registry")
        return _fail_result(logs, None, [])

    kc_config = kc_connection.config or {}
    log("info", f"Kafka Connect backend from '{kc_conn_name}' (deployment={deployment_of(kc_config)})")
    backend = get_backend(kc_config)

    meta          = build_result.get("meta", {})
    pipeline_name = meta.get("name", "")
    src_name      = build_result["sourceConfig"].get("name", "")
    snk_name      = build_result["sinkConfig"].get("name", "")

    src_deployed = dict(build_result["sourceConfig"])
    snk_deployed = dict(build_result["sinkConfig"])

    for role in _SOURCE_ROLES:
        conn_name = _extract_side_conn_name(src_block, role)
        if conn_name:
            src_deployed = _inject_creds(src_deployed, _fetch_connection(db, conn_name))
            log("info", f"source {role}.connection: injected credentials from '{conn_name}'")
    for role in _SINK_ROLES:
        conn_name = _extract_side_conn_name(snk_block, role)
        if conn_name:
            snk_deployed = _inject_creds(snk_deployed, _fetch_connection(db, conn_name))
            log("info", f"sink {role}.connection: injected credentials from '{conn_name}'")

    pipeline = Pipeline(
        name=pipeline_name,
        env=env,
        yaml_raw=raw_yaml,
        yaml_resolved=resolved,
        status="deploying",
    )
    db.add(pipeline)
    db.flush()
    db.commit()

    connectors_status: list[dict] = []

    log("info", f"Deploying source connector '{src_name}'")
    try:
        backend.deploy(src_name, src_deployed)
    except ConfigValidationError as e:
        pipeline.status = "failed"
        db.commit()
        _log_validation_errors(log, "source", src_name, e)
        return _fail_result(logs, pipeline.id, connectors_status)
    except Exception as e:
        pipeline.status = "failed"
        db.commit()
        log("error", f"source deploy failed: {e}")
        return _fail_result(logs, pipeline.id, connectors_status)

    _save_connector(db, pipeline.id, src_name, "source", meta.get("sourcePluginName", ""), src_deployed)
    src_state = poll_until_running(backend, src_name, poll_timeout, poll_interval, sleep=sleep, now=now)
    connectors_status.append({"name": src_name, "type": "source", "status": src_state})

    if src_state != "RUNNING":
        pipeline.status = "failed"
        db.commit()
        log("error", f"source '{src_name}' did not reach RUNNING (state={src_state})")
        return _fail_result(logs, pipeline.id, connectors_status)
    log("success", f"source '{src_name}' is RUNNING ✓")

    log("info", f"Deploying sink connector '{snk_name}'")
    try:
        backend.deploy(snk_name, snk_deployed)
    except ConfigValidationError as e:
        pipeline.status = "failed"
        db.commit()
        _log_validation_errors(log, "sink", snk_name, e)
        return _fail_result(logs, pipeline.id, connectors_status)
    except Exception as e:
        pipeline.status = "failed"
        db.commit()
        log("error", f"sink deploy failed: {e}")
        return _fail_result(logs, pipeline.id, connectors_status)

    _save_connector(db, pipeline.id, snk_name, "sink", meta.get("sinkPluginName", ""), snk_deployed)
    snk_state = poll_until_running(backend, snk_name, poll_timeout, poll_interval, sleep=sleep, now=now)
    connectors_status.append({"name": snk_name, "type": "sink", "status": snk_state})

    if snk_state != "RUNNING":
        pipeline.status = "failed"
        db.commit()
        log("error", f"sink '{snk_name}' did not reach RUNNING (state={snk_state})")
        return _fail_result(logs, pipeline.id, connectors_status)
    log("success", f"sink '{snk_name}' is RUNNING ✓")

    pipeline.status = "running"
    db.commit()
    log("success", "pipeline is running ✓")
    return {"ok": True, "logs": logs, "pipelineId": pipeline.id, "connectors": connectors_status}
