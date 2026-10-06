import json
from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from app.utils.db import SessionLocal
from app.models.connection import Connection
from app.utils.logger import get_logger
from app.utils.auth import require
import app.connectors as registry
from app.connectors.schemas import get_schema, supported_subtypes as schema_subtypes, SECRET_MASK

log = get_logger(__name__)
connections_api = Blueprint("connections_api", __name__, url_prefix="/api")

_RETIRED_TYPES = frozenset({"source", "sink"})
_RETIRED_SUBTYPES = frozenset({"postgres", "mysql", "s3"})
_RETIRED_MSG = (
    "Source and destination connections are retired. "
    "Store credentials in a vault and put them in connector JSON."
)


def _retired_connection_error(conn_type: str, subtype: str):
    if (conn_type or "").lower() in _RETIRED_TYPES or (subtype or "").lower() in _RETIRED_SUBTYPES:
        return jsonify({"error": _RETIRED_MSG}), 400
    return None


@connections_api.get("/connector-schemas")
@require("connection.read")
def list_schemas():
    """List all connection subtypes that have a schema registered."""
    return jsonify({"subtypes": schema_subtypes()})


@connections_api.get("/connector-schemas/<subtype>")
@require("connection.read")
def get_connector_schema(subtype: str):
    """Return the form schema for one connector subtype (required + advanced fields)."""
    schema = get_schema(subtype)
    if not schema:
        return jsonify({"error": f"No schema registered for '{subtype}'"}), 404
    return jsonify(schema.to_json())


@connections_api.get("/connections")
@require("connection.read")
def list_connections():
    with SessionLocal() as db:
        conns = db.query(Connection).order_by(Connection.id).all()
        return jsonify([c.to_dict() for c in conns])


@connections_api.get("/connections/<int:conn_id>")
@require("connection.read")
def get_connection(conn_id: int):
    with SessionLocal() as db:
        conn = db.get(Connection, conn_id)
        if not conn:
            return jsonify({"error": f"Connection {conn_id} not found"}), 404
        return jsonify(conn.to_dict())


@connections_api.post("/connections")
@require("connection.create")
def create_connection():
    data = request.get_json(silent=True) or {}

    for field in ("name", "type", "subtype"):
        if not data.get(field):
            return jsonify({"error": f"Missing required field: '{field}'"}), 400

    retired = _retired_connection_error(data.get("type"), data.get("subtype"))
    if retired:
        return retired

    extra = data.get("extra", {})
    if isinstance(extra, str):
        try:
            extra = json.loads(extra) if extra.strip() else {}
        except json.JSONDecodeError as e:
            return jsonify({"error": f"Invalid JSON in 'extra': {e}"}), 400

    connector = registry.get(data["type"], data["subtype"])

    if connector:
        config = connector.build_config(form=data, extra=extra)
        errors = connector.validate(config)
        if errors:
            return jsonify({"error": "Validation failed", "details": errors}), 400
    else:
        # Generic path: no registered connector class (e.g. notification-slack, notification-gchat).
        # Pull known top-level form fields into a flat config, then merge `extra` on top.
        config = data.get("config") or {}
        if not isinstance(config, dict):
            return jsonify({"error": "'config' must be an object for generic connections"}), 400
        # Drop any masked secret echoed back by the client on create.
        config = {k: v for k, v in config.items() if v != SECRET_MASK}
        for k in ("host", "port", "database", "username", "password", "url", "token"):
            v = data.get(k)
            if v not in (None, "", SECRET_MASK):
                config[k] = v
        config = {**config, **extra}

    with SessionLocal() as db:
        conn = Connection(
            name=data["name"],
            type=data["type"],
            subtype=data["subtype"].lower(),
            status=data.get("status", "draft"),
            used_in=data.get("usedIn", []),
            config=config,
        )
        try:
            db.add(conn)
            db.commit()
            db.refresh(conn)
        except IntegrityError:
            db.rollback()
            return jsonify({"error": f"Connection name '{data['name']}' already exists"}), 409

        log.info("Created connection '%s' subtype=%s (id=%d)", conn.name, conn.subtype, conn.id)
        return jsonify(conn.to_dict()), 201


@connections_api.put("/connections/<int:conn_id>")
@require("connection.save")
def update_connection(conn_id: int):
    data = request.get_json(silent=True) or {}
    extra = data.get("extra", {})
    if isinstance(extra, str):
        try:
            extra = json.loads(extra) if extra.strip() else {}
        except json.JSONDecodeError as e:
            return jsonify({"error": f"Invalid JSON in 'extra': {e}"}), 400

    with SessionLocal() as db:
        conn = db.get(Connection, conn_id)
        if not conn:
            return jsonify({"error": f"Connection {conn_id} not found"}), 404

        retired = _retired_connection_error(
            data.get("type") or conn.type,
            data.get("subtype") or conn.subtype,
        )
        if retired:
            return retired

        for field in ("name", "type", "status"):
            if field in data:
                setattr(conn, field, data[field])

        if "usedIn" in data:
            conn.used_in = data["usedIn"]

        connector = registry.get(conn.type, conn.subtype)
        if connector:
            old_cfg = dict(conn.config or {})
            new_cfg = connector.build_config(form=data, extra=extra)
            # Preserve secret values that the client omitted from this update
            # (inline-edit password fields intentionally render blank so users can't accidentally
            # nuke a working credential just by clicking Save).
            new_cfg = connector.merge_preserved_secrets(new_cfg, old_cfg)
            errors = connector.validate(new_cfg)
            if errors:
                return jsonify({"error": "Validation failed", "details": errors}), 400
            conn.config = new_cfg
        else:
            # Generic path: merge known top-level fields + optional `config` + `extra`
            # Blank values are ignored so unchanged password fields keep their stored value.
            new_cfg = dict(conn.config or {})
            if "config" in data:
                override = data.get("config") or {}
                if not isinstance(override, dict):
                    return jsonify({"error": "'config' must be an object"}), 400
                # Skip masked secrets so the stored value is preserved.
                new_cfg.update({k: v for k, v in override.items() if v != SECRET_MASK})
            for k in ("host", "port", "database", "username", "password", "url", "token"):
                if k in data and data[k] not in (None, "", SECRET_MASK):
                    new_cfg[k] = data[k]
            if extra:
                new_cfg = {**new_cfg, **extra}
            conn.config = new_cfg

        db.commit()
        db.refresh(conn)
        log.info("Updated connection '%s' (id=%d)", conn.name, conn.id)
        return jsonify(conn.to_dict())


@connections_api.delete("/connections/<int:conn_id>")
@require("connection.delete")
def delete_connection(conn_id: int):
    with SessionLocal() as db:
        conn = db.get(Connection, conn_id)
        if not conn:
            return jsonify({"error": f"Connection {conn_id} not found"}), 404
        db.delete(conn)
        db.commit()
        log.info("Deleted connection '%s' (id=%d)", conn.name, conn_id)
        return jsonify({"deleted": conn_id})


@connections_api.post("/connections/test")
@require("connection.test")
def test_connection():
    data = request.get_json(silent=True) or {}
    conn_type = (data.get("type") or "").lower()
    subtype = (data.get("subtype") or "").lower()
    retired = _retired_connection_error(conn_type, subtype)
    if retired:
        return retired

    # Notification channels: delegate to the alerting Channel factory.
    if conn_type == "notification" or subtype.startswith("notification-"):
        from app.services.alerting.channels.factory import get_channel, supported_subtypes

        channel = get_channel(subtype)
        if not channel:
            return jsonify({
                "success": False,
                "message": f"'{subtype}' is not implemented. Supported: {', '.join(supported_subtypes())}",
            }), 400

        # Assemble a config dict from top-level form fields (same shape as create/update endpoints).
        cfg: dict = {}
        for k in ("host", "port", "database", "username", "password", "url", "token"):
            v = data.get(k)
            if v not in (None, ""):
                cfg[k] = v

        result = channel.test(cfg)
        log.info("Test notification subtype=%s success=%s latency=%dms", subtype, result.success, result.latency_ms)
        if result.success:
            msg = f"Delivered test message in {result.latency_ms}ms"
        else:
            msg = result.error or f"HTTP {result.http_status}" if result.http_status else "Delivery failed"
        return jsonify({
            "success":    result.success,
            "message":    msg,
            "httpStatus": result.http_status,
            "latencyMs":  result.latency_ms,
        })

    connector = registry.get(conn_type, subtype)
    if not connector:
        return jsonify({"success": False, "message": f"Test not supported for '{subtype}'"}), 400

    # Testing a saved connection: use its stored config (real secrets + flags).
    # The masked form echo does not carry secrets and may drop config keys.
    conn_id = data.get("id")
    if conn_id is not None:
        with SessionLocal() as db:
            saved = db.get(Connection, conn_id)
        if saved and isinstance(saved.config, dict) and saved.config:
            result = connector.test_connection(saved.config)
            log.info("Test saved connection id=%s subtype=%s success=%s", conn_id, subtype, result["success"])
            return jsonify(result)

    extra = data.get("extra", {})
    if isinstance(extra, str):
        try:
            extra = json.loads(extra) if extra.strip() else {}
        except json.JSONDecodeError:
            extra = {}

    config = connector.build_config(form=data, extra=extra)
    result = connector.test_connection(config)
    log.info("Test connection subtype=%s success=%s", subtype, result["success"])
    return jsonify(result)
