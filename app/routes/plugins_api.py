import json
import re
from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from app.utils.db import SessionLocal
from app.models.plugin import Plugin
from app.utils.auth import require
from app.utils.logger import get_logger

log = get_logger(__name__)
plugins_api = Blueprint("plugins_api", __name__, url_prefix="/api")

_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$')


def _valid_slug(name: str) -> bool:
    return bool(_SLUG_RE.match(name)) if name else False


def _parse_config(config) -> tuple[dict | None, str | None]:
    """Accept a config object or its JSON text. Returns (config, error)."""
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON in 'config': {e}"
    if not isinstance(config, dict):
        return None, "'config' must be a JSON object"
    return config, None


@plugins_api.get("/plugins")
def list_plugins():
    with SessionLocal() as db:
        type_filter = request.args.get("type")
        query = db.query(Plugin)
        if type_filter:
            query = query.filter(Plugin.type == type_filter)
        plugins = query.order_by(Plugin.type, Plugin.name).all()
        return jsonify([p.to_dict() for p in plugins])


@plugins_api.get("/plugins/<name>")
def get_plugin(name: str):
    with SessionLocal() as db:
        plugin = db.get(Plugin, name)
        if not plugin:
            return jsonify({"error": f"Plugin '{name}' not found"}), 404
        return jsonify(plugin.to_dict())


@plugins_api.post("/plugins")
@require("plugin.create")
def create_plugin():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    name = (data.get("name") or "").strip().lower()
    if not _valid_slug(name):
        return jsonify({"error": "name must be lowercase letters, numbers and hyphens (e.g. postgres-source-1)"}), 400

    for field in ("type", "format", "config"):
        if not data.get(field):
            return jsonify({"error": f"Missing required field: '{field}'"}), 400

    if data["type"] not in ("source", "sink"):
        return jsonify({"error": "type must be 'source' or 'sink'"}), 400

    config, error = _parse_config(data["config"])
    if error:
        return jsonify({"error": error}), 400

    with SessionLocal() as db:
        plugin = Plugin(
            name=name,
            db=data.get("db", ""),
            type=data["type"],
            format=data["format"].upper(),
            description=data.get("description", ""),
            config=json.dumps(config),
            is_builtin=False,
        )
        try:
            db.add(plugin)
            db.commit()
            db.refresh(plugin)
        except IntegrityError:
            db.rollback()
            return jsonify({"error": f"Plugin '{name}' already exists"}), 409

        log.info("Created plugin '%s'", name)
        return jsonify(plugin.to_dict()), 201


@plugins_api.put("/plugins/<name>")
@require("plugin.edit")
def update_plugin(name: str):
    with SessionLocal() as db:
        plugin = db.get(Plugin, name)
        if not plugin:
            return jsonify({"error": f"Plugin '{name}' not found"}), 404
        if plugin.is_builtin:
            return jsonify({"error": "Built-in plugins cannot be edited"}), 403

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Request body must be a JSON object"}), 400

        if "config" in data:
            config, error = _parse_config(data["config"])
            if error:
                return jsonify({"error": error}), 400
            plugin.config = json.dumps(config)

        for field in ("db", "type", "format", "description"):
            if field in data:
                setattr(plugin, field, data[field])

        db.commit()
        db.refresh(plugin)
        log.info("Updated plugin '%s'", name)
        return jsonify(plugin.to_dict())


@plugins_api.delete("/plugins/<name>")
@require("plugin.delete")
def delete_plugin(name: str):
    with SessionLocal() as db:
        plugin = db.get(Plugin, name)
        if not plugin:
            return jsonify({"error": f"Plugin '{name}' not found"}), 404
        if plugin.is_builtin:
            return jsonify({"error": "Built-in plugins cannot be deleted"}), 403
        db.delete(plugin)
        db.commit()
        log.info("Deleted plugin '%s'", name)
        return jsonify({"deleted": name})
