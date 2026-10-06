"""Normalized API for browsing configured Schema Registry connections."""

from __future__ import annotations

from urllib.parse import unquote

from flask import Blueprint, jsonify, request

from app.models.connection import Connection
from app.services.schema_registry import SchemaRegistryError, get_schema_registry
from app.utils.auth import require
from app.utils.db import SessionLocal


schema_registry_api = Blueprint("schema_registry_api", __name__, url_prefix="/api/schema-registries")


def _registry_connection(db, name: str) -> Connection | None:
    return (
        db.query(Connection)
        .filter(Connection.name == name, Connection.subtype == "schema-registry")
        .first()
    )


def _client(db, name: str):
    connection = _registry_connection(db, name)
    if not connection:
        return None, None, (jsonify({"error": f"Schema Registry connection '{name}' not found"}), 404)
    try:
        return get_schema_registry(connection.config or {}), connection, None
    except SchemaRegistryError as exc:
        return None, connection, (jsonify({"error": str(exc)}), 400)


def _envelope(name: str, client, connection=None, **extra):
    config = (connection.config if connection is not None else None) or {}
    return {
        "registry": name,
        "provider": client.provider,
        "url": config.get("url"),
        **extra,
    }


@schema_registry_api.get("")
@require("registry.browse")
def list_registries():
    with SessionLocal() as db:
        rows = db.query(Connection).filter(Connection.subtype == "schema-registry").order_by(Connection.name).all()
        return jsonify([
            {
                "name": row.name,
                "provider": (row.config or {}).get("provider"),
                "url": (row.config or {}).get("url"),
                "status": row.status,
            }
            for row in rows
        ])


@schema_registry_api.get("/<path:name>/test")
@require("registry.browse")
def test_registry(name: str):
    with SessionLocal() as db:
        client, connection, error = _client(db, unquote(name))
        if error:
            return error
        try:
            return jsonify(_envelope(unquote(name), client, connection, **client.test_connection()))
        except SchemaRegistryError as exc:
            return jsonify({"success": False, "error": str(exc)}), 502


@schema_registry_api.get("/<path:name>/catalog")
@require("registry.browse")
def get_catalog(name: str):
    with SessionLocal() as db:
        client, connection, error = _client(db, unquote(name))
        if error:
            return error
        try:
            return jsonify(_envelope(unquote(name), client, connection, groups=client.catalog()))
        except SchemaRegistryError as exc:
            return jsonify({"error": str(exc)}), 502


@schema_registry_api.get("/<path:name>/versions")
@require("registry.read_schema")
def list_versions(name: str):
    group_id = request.args.get("group") or "default"
    artifact_id = request.args.get("artifact")
    if not artifact_id:
        return jsonify({"error": "Query parameter 'artifact' is required"}), 400
    with SessionLocal() as db:
        client, connection, error = _client(db, unquote(name))
        if error:
            return error
        try:
            versions = client.list_versions(group_id, artifact_id)
            latest = versions[-1]["version"] if versions else None
            return jsonify(_envelope(
                unquote(name), client, connection,
                groupId=group_id,
                artifactId=artifact_id,
                versions=versions,
                latest=latest,
            ))
        except SchemaRegistryError as exc:
            return jsonify({"error": str(exc)}), 502


@schema_registry_api.get("/<path:name>/content")
@require("registry.read_schema")
def get_content(name: str):
    group_id = request.args.get("group") or "default"
    artifact_id = request.args.get("artifact")
    version = request.args.get("version") or "latest"
    if not artifact_id:
        return jsonify({"error": "Query parameter 'artifact' is required"}), 400
    with SessionLocal() as db:
        client, connection, error = _client(db, unquote(name))
        if error:
            return error
        try:
            schema = client.get_content(group_id, artifact_id, version)
            return jsonify(_envelope(unquote(name), client, connection, **schema))
        except SchemaRegistryError as exc:
            return jsonify({"error": str(exc)}), 502
