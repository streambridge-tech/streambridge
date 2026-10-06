"""Kafka Connect REST API proxy for the pipeline detail page.

Exposes a curated set of KC REST operations against a specific deployed
connector belonging to a specific pipeline. The KC connection identity is
resolved from the pipeline's env block (`kafka_connect.connection`) so the
frontend never sees KC URLs or credentials.

One HTTP endpoint dispatches by action name — this keeps the route surface
small and makes it trivial to add / remove operations from a single registry.
"""

from __future__ import annotations

from typing import Any, Callable

from flask import Blueprint, jsonify, request

from app.models.connection import Connection
from app.models.pipeline import Pipeline
from app.services.connect.factory import get_backend
from app.services.connect.orchestrator import _extract_env_conn_name
from app.services.connect.rest_backend import RestBackend
from app.utils.auth import authorize, require
from app.utils.db import SessionLocal
from app.utils.logger import get_logger
from app.utils.yaml_builder import _extract_env_block


log = get_logger(__name__)
kc_api = Blueprint("kc_api", __name__, url_prefix="/api/kc")


# ── action registry ─────────────────────────────────────────────────────────
# Each entry declares:
#   label       — human name for the dropdown
#   method      — HTTP verb Kafka Connect will see (informational)
#   path        — KC path template (informational; shown in the UI hint)
#   group       — dropdown grouping: inspect | lifecycle | offsets | danger
#   danger      — bool, requires confirmation on the client
#   params      — list of {name, label, type, required, default, help}
#   run         — Callable(backend, connector_name, connector_config, **params) → any JSON
#
# `connector_config` is passed to run() for actions that default their params
# from the currently deployed config (e.g. validate).

def _run_status(backend: RestBackend, name, cfg, **_):        return backend.get_status(name)
def _run_config(backend: RestBackend, name, cfg, **_):        return backend.get_config(name)
def _run_offsets(backend: RestBackend, name, cfg, **_):       return backend.get_offsets(name)
def _run_tasks(backend: RestBackend, name, cfg, **_):         return backend.list_tasks(name)
def _run_topics(backend: RestBackend, name, cfg, **_):        return backend.get_topics(name)

def _run_pause(backend: RestBackend, name, cfg, **_):
    backend.pause(name); return {"message": f"Paused '{name}'"}

def _run_resume(backend: RestBackend, name, cfg, **_):
    backend.resume(name); return {"message": f"Resumed '{name}'"}

def _run_restart(backend: RestBackend, name, cfg, includeTasks="false", onlyFailed="false", **_):
    it = str(includeTasks).lower() in ("true", "1", "yes")
    of = str(onlyFailed).lower() in ("true", "1", "yes")
    return backend.restart(name, include_tasks=it, only_failed=of) or {"message": f"Restart requested for '{name}'"}

def _run_restart_task(backend: RestBackend, name, cfg, taskId=None, **_):
    if taskId in (None, ""):
        raise ValueError("taskId is required")
    backend.restart_task(name, int(taskId))
    return {"message": f"Task {taskId} restart requested for '{name}'"}

def _run_reset_offsets(backend: RestBackend, name, cfg, **_):
    return backend.reset_offsets(name)

def _run_delete(backend: RestBackend, name, cfg, **_):
    backend.delete(name); return {"message": f"Connector '{name}' deleted from Kafka Connect"}

def _run_validate(backend: RestBackend, name, cfg, config=None, **_):
    # Default to the connector's currently deployed config so the user can
    # inspect validation against the exact keys KC has today.
    payload = config if isinstance(config, dict) and config else (cfg or {})
    plugin_class = payload.get("connector.class")
    if not plugin_class:
        raise ValueError("config must contain 'connector.class'")
    return backend.validate_config(plugin_class, payload, connector_name=name)

def _run_plugin_config(backend: RestBackend, name, cfg, pluginClass=None, **_):
    plugin_class = pluginClass or (cfg or {}).get("connector.class")
    if not plugin_class:
        raise ValueError("pluginClass is required (or connector.class must be in the deployed config)")
    return backend.get_plugin_config(plugin_class)


ACTIONS: dict[str, dict[str, Any]] = {
    # ── inspect ──
    "status":         {"label": "Get Status",             "method": "GET",    "path": "/connectors/{name}/status",
                       "group": "inspect", "danger": False, "params": [],
                       "run": _run_status},
    "config":         {"label": "Get Config",             "method": "GET",    "path": "/connectors/{name}/config",
                       "group": "inspect", "danger": False, "params": [],
                       "run": _run_config},
    "tasks":          {"label": "List Tasks",             "method": "GET",    "path": "/connectors/{name}/tasks",
                       "group": "inspect", "danger": False, "params": [],
                       "run": _run_tasks},
    "topics":         {"label": "List Topics",            "method": "GET",    "path": "/connectors/{name}/topics",
                       "group": "inspect", "danger": False, "params": [],
                       "run": _run_topics},
    "plugin-config":  {"label": "Get Plugin Config",      "method": "GET",    "path": "/connector-plugins/{class}/config",
                       "group": "inspect", "danger": False,
                       "params": [{"name": "pluginClass", "label": "Plugin class", "type": "text", "required": False,
                                   "help": "Defaults to this connector's connector.class"}],
                       "run": _run_plugin_config},

    # ── lifecycle ──
    "pause":          {"label": "Pause",                  "method": "PUT",    "path": "/connectors/{name}/pause",
                       "group": "lifecycle", "danger": False, "params": [],
                       "run": _run_pause},
    "resume":         {"label": "Resume",                 "method": "PUT",    "path": "/connectors/{name}/resume",
                       "group": "lifecycle", "danger": False, "params": [],
                       "run": _run_resume},
    "restart":        {"label": "Restart Connector",      "method": "POST",   "path": "/connectors/{name}/restart",
                       "group": "lifecycle", "danger": False,
                       "params": [
                           {"name": "includeTasks", "label": "Also restart tasks", "type": "boolean", "default": False},
                           {"name": "onlyFailed",   "label": "Only failed tasks",  "type": "boolean", "default": False},
                       ],
                       "run": _run_restart},
    "restart-task":   {"label": "Restart Task",           "method": "POST",   "path": "/connectors/{name}/tasks/{taskId}/restart",
                       "group": "lifecycle", "danger": False,
                       "params": [{"name": "taskId", "label": "Task ID", "type": "number", "required": True, "default": 0}],
                       "run": _run_restart_task},

    # ── offsets ──
    "offsets":        {"label": "Show Offsets",           "method": "GET",    "path": "/connectors/{name}/offsets",
                       "group": "offsets", "danger": False, "params": [],
                       "run": _run_offsets},
    "reset-offsets":  {"label": "Reset Offsets",          "method": "DELETE", "path": "/connectors/{name}/offsets",
                       "group": "offsets", "danger": True, "params": [],
                       "run": _run_reset_offsets},

    # ── config & validation ──
    "validate-config":{"label": "Validate Config",        "method": "PUT",    "path": "/connector-plugins/{class}/config/validate",
                       "group": "inspect", "danger": False,
                       "params": [{"name": "config", "label": "Config JSON", "type": "json", "required": False,
                                   "help": "Leave empty to validate the currently deployed config"}],
                       "run": _run_validate},

    # ── danger ──
    "delete":         {"label": "Delete Connector",       "method": "DELETE", "path": "/connectors/{name}",
                       "group": "danger", "danger": True, "params": [],
                       "run": _run_delete},
}


def _action_metadata(key: str) -> dict:
    a = ACTIONS[key]
    return {
        "key":    key,
        "label":  a["label"],
        "method": a["method"],
        "path":   a["path"],
        "group":  a["group"],
        "danger": a["danger"],
        "params": a["params"],
    }


def _is_connect_connection(conn: Connection) -> bool:
    type_ = (conn.type or "").lower()
    subtype = (conn.subtype or "").lower()
    return type_ == "connect" or "kafka-connect" in subtype


def _filled_path(template: str, connector_name: str, params: dict) -> str:
    path = template.replace("{name}", connector_name)
    if "{taskId}" in path:
        path = path.replace("{taskId}", str(params.get("taskId", "0")))
    if "{class}" in path:
        plugin = params.get("pluginClass") or (params.get("config") or {}).get("connector.class") or "connector.class"
        path = path.replace("{class}", str(plugin))
    return path


def _public_url(conn_config: dict, path: str) -> str:
    base = str((conn_config or {}).get("url") or "").rstrip("/")
    return f"{base}{path}"


def _execute_action(backend, connector_name: str, connector_config: dict, action: str, params: dict):
    return ACTIONS[action]["run"](backend, connector_name, connector_config, **params)


# Each Connect action maps to the permission it requires.
ACTION_PERMISSION: dict[str, str] = {
    "status":          "connect.get_status",
    "config":          "connect.get_config",
    "tasks":           "connect.get_tasks",
    "topics":          "connect.get_topics",
    "plugin-config":   "connect.get_config",
    "offsets":         "connect.get_status",
    "pause":           "connect.pause",
    "resume":          "connect.resume",
    "restart":         "connect.restart",
    "restart-task":    "connect.restart_task",
    "validate-config": "connector.validate",
    "reset-offsets":   "danger.reset_offsets",
    "delete":          "danger.delete_live",
}


def _authorize_action(action: str):
    """Permission gate for a dynamic Connect action. None = allowed."""
    return authorize(ACTION_PERMISSION.get(action, "connect.get_status"))


# Lifecycle/danger actions worth recording to the audit log (reads are excluded).
AUDITED_ACTIONS = frozenset({"pause", "resume", "restart", "restart-task", "reset-offsets", "delete"})


@kc_api.get("/actions")
@require("connect.get_status")
def list_actions():
    """Return the action registry so the frontend can build the dropdown dynamically."""
    return jsonify({"actions": [_action_metadata(k) for k in ACTIONS.keys()]})


def _resolve_kc_backend(db, pipeline: Pipeline) -> tuple[RestBackend | None, str | None]:
    """Return (backend, error). Only one is set."""
    env_block = _extract_env_block(pipeline.yaml_raw or "", pipeline.env or "")
    kc_conn_name = _extract_env_conn_name(env_block, "kafka_connect.connection")
    if not kc_conn_name:
        return None, "kafka_connect.connection not set for this pipeline's env"
    kc_conn = db.query(Connection).filter(Connection.name == kc_conn_name).first()
    if not kc_conn:
        return None, f"Kafka Connect connection '{kc_conn_name}' not found in registry"
    return get_backend(kc_conn.config or {}), None


@kc_api.post("/pipelines/id/<pipeline_id>/connectors/<connector_name>/<action>")
def run_action(pipeline_id: str, connector_name: str, action: str):
    if action not in ACTIONS:
        return jsonify({"ok": False, "error": f"Unknown action '{action}'",
                        "actions": list(ACTIONS.keys())}), 400

    denied = _authorize_action(action)
    if denied:
        return denied

    with SessionLocal() as db:
        pipeline = db.get(Pipeline, pipeline_id)
        if not pipeline:
            return jsonify({"ok": False, "error": f"Pipeline id={pipeline_id} not found"}), 404

        backend, err = _resolve_kc_backend(db, pipeline)
        if err:
            return jsonify({"ok": False, "error": err}), 400

        # Look up the connector's deployed config so actions like validate/plugin-config
        # can default to it.
        from app.models.connector_config import ConnectorConfig
        import json
        connector = (
            db.query(ConnectorConfig)
            .filter(ConnectorConfig.pipeline_id == pipeline.id,
                    ConnectorConfig.connector_name == connector_name)
            .first()
        )
        connector_config = {}
        if connector and connector.config:
            try:
                connector_config = json.loads(connector.config)
            except (ValueError, TypeError):
                connector_config = {}

    body = request.get_json(silent=True) or {}
    log.info("KC action=%s pipeline=%s connector=%s params=%s",
             action, pipeline_id, connector_name, list(body.keys()))
    try:
        result = _execute_action(backend, connector_name, connector_config, action, body)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

    meta = ACTIONS[action]
    path = _filled_path(meta["path"], connector_name, {**body, "config": connector_config})
    if action in AUDITED_ACTIONS:
        from app.services.audit import record_event
        record_event(f"connect.{action}", target_type="connector", target_id=connector_name,
                     summary=f"{meta['label']} via pipeline {pipeline_id}")
    return jsonify({
        "ok": True,
        "action": action,
        "connector": connector_name,
        "method": meta["method"],
        "path": path,
        "data": result,
    })


@kc_api.post("/connections/<connection_name>/connectors/<connector_name>/<action>")
def run_connection_action(connection_name: str, connector_name: str, action: str):
    """Run a KC REST action using the attached Kafka Connect connection.

    Connectors editor uses this so the UI never asks for host/port or connector name.
    """
    if action not in ACTIONS:
        return jsonify({"ok": False, "error": f"Unknown action '{action}'",
                        "actions": list(ACTIONS.keys())}), 400

    denied = _authorize_action(action)
    if denied:
        return denied

    with SessionLocal() as db:
        kc_conn = db.query(Connection).filter(Connection.name == connection_name).first()
        if not kc_conn:
            return jsonify({"ok": False, "error": f"Kafka Connect connection '{connection_name}' not found"}), 404
        if not _is_connect_connection(kc_conn):
            return jsonify({"ok": False, "error": f"'{connection_name}' is not a Kafka Connect connection"}), 400
        conn_config = kc_conn.config or {}
        backend = get_backend(conn_config)

    body = request.get_json(silent=True) or {}
    connector_config = body.pop("config", None) or {}
    if not isinstance(connector_config, dict):
        connector_config = {}
    log.info("KC action=%s connection=%s connector=%s params=%s",
             action, connection_name, connector_name, list(body.keys()))
    try:
        result = _execute_action(backend, connector_name, connector_config, action, body)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

    meta = ACTIONS[action]
    path = _filled_path(meta["path"], connector_name, {**body, "config": connector_config})
    if action in AUDITED_ACTIONS:
        from app.services.audit import record_event
        record_event(f"connect.{action}", target_type="connector", target_id=connector_name,
                     summary=f"{meta['label']} via connection {connection_name}")
    return jsonify({
        "ok": True,
        "action": action,
        "connector": connector_name,
        "connection": connection_name,
        "method": meta["method"],
        "url": _public_url(conn_config, path),
        "path": path,
        "data": result,
    })
