"""Browse topics and messages on saved Kafka broker connections."""

from __future__ import annotations

import json
from urllib.parse import unquote

from flask import Blueprint, jsonify, request

from app.models.connection import Connection
from app.services.kafka import KafkaBrowseError, consume_messages, list_topics
from app.services.schema_registry import SchemaRegistryError, get_schema_registry
from app.utils.auth import require
from app.utils.db import SessionLocal


kafka_api = Blueprint("kafka_api", __name__, url_prefix="/api/kafka-brokers")


def _broker(db, name: str) -> Connection | None:
    return (
        db.query(Connection)
        .filter(Connection.name == name, Connection.subtype == "kafka")
        .first()
    )


def _parse_int(value, default=None):
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@kafka_api.get("")
@require("topic.browse")
def list_brokers():
    with SessionLocal() as db:
        rows = db.query(Connection).filter(Connection.subtype == "kafka").order_by(Connection.name).all()
        return jsonify([
            {
                "name": row.name,
                "bootstrapServers": (row.config or {}).get("bootstrap.servers"),
                "status": row.status,
            }
            for row in rows
        ])


@kafka_api.get("/<path:name>/topics")
@require("topic.browse")
def get_topics(name: str):
    with SessionLocal() as db:
        connection = _broker(db, unquote(name))
        if not connection:
            return jsonify({"error": f"Kafka connection '{unquote(name)}' not found"}), 404
        try:
            topics = list_topics(connection.config or {})
        except KafkaBrowseError as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify({
            "connection": connection.name,
            "bootstrapServers": (connection.config or {}).get("bootstrap.servers"),
            "topics": topics,
        })


@kafka_api.get("/<path:name>/messages")
@require("topic.read_messages")
def get_messages(name: str):
    topic = (request.args.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "Query parameter 'topic' is required"}), 400
    limit = _parse_int(request.args.get("limit"), 100) or 100
    partition = _parse_int(request.args.get("partition"))
    before_raw = request.args.get("before") or ""
    before = None
    if before_raw:
        try:
            parsed = json.loads(before_raw)
            if isinstance(parsed, dict):
                before = parsed
        except ValueError:
            return jsonify({"error": "Query parameter 'before' must be a JSON object"}), 400

    with SessionLocal() as db:
        connection = _broker(db, unquote(name))
        if not connection:
            return jsonify({"error": f"Kafka connection '{unquote(name)}' not found"}), 404
        registry_name = (request.args.get("registry") or "").strip()
        registry = None
        if registry_name:
            row = (
                db.query(Connection)
                .filter(Connection.name == registry_name, Connection.subtype == "schema-registry")
                .first()
            )
            if not row:
                return jsonify({"error": f"Schema Registry connection '{registry_name}' not found"}), 404
            try:
                registry = get_schema_registry(row.config or {})
            except SchemaRegistryError as exc:
                return jsonify({"error": str(exc)}), 400
        try:
            payload = consume_messages(
                connection.config or {},
                topic,
                limit=limit,
                partition=partition,
                before=before,
                key_format=request.args.get("key_format") or "auto",
                value_format=request.args.get("value_format") or "auto",
                registry=registry,
                key_subject=request.args.get("key_subject") or f"{topic}-key",
                value_subject=request.args.get("value_subject") or f"{topic}-value",
            )
        except KafkaBrowseError as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify({
            "connection": connection.name,
            "registry": registry_name or None,
            **payload,
        })
