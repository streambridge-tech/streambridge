"""Decode Kafka record payloads for the Topics UI."""

from __future__ import annotations

import base64
import json
import io
from typing import Any

from app.services.schema_registry.base import SchemaRegistry, SchemaRegistryError
from app.services.schema_registry.models import parse_content

CONFLUENT_MAGIC = 0
FORMATS = ("auto", "string", "json", "avro", "bytes")


def parse_confluent_wire(raw: bytes) -> tuple[int, bytes] | None:
    if not raw or len(raw) < 5 or raw[0] != CONFLUENT_MAGIC:
        return None
    schema_id = int.from_bytes(raw[1:5], "big")
    return schema_id, raw[5:]


def _as_text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _decode_json(raw: bytes) -> Any:
    return json.loads(_as_text(raw))


def _decode_avro(payload: bytes, schema: Any) -> Any:
    try:
        import fastavro
    except ImportError as exc:
        raise RuntimeError("fastavro is required to decode Avro payloads") from exc
    parsed = schema
    if isinstance(schema, str):
        parsed = json.loads(schema)
    elif isinstance(schema, dict) and "type" not in schema and "schema" in schema:
        parsed = parse_content(schema["schema"])
    return fastavro.schemaless_reader(io.BytesIO(payload), parsed)


def decode_payload(
    raw: bytes | None,
    fmt: str = "auto",
    *,
    registry: SchemaRegistry | None = None,
    subject: str | None = None,
) -> dict:
    """Return {value, schemaId, format, error} for one key or value."""
    requested = (fmt or "auto").lower()
    if requested not in FORMATS:
        requested = "auto"
    if raw is None:
        return {"value": None, "schemaId": None, "format": requested, "error": None}
    if not isinstance(raw, (bytes, bytearray)):
        return {"value": raw, "schemaId": None, "format": requested, "error": None}

    data = bytes(raw)
    try:
        if requested == "bytes":
            return {
                "value": base64.b64encode(data).decode("ascii"),
                "schemaId": None,
                "format": "bytes",
                "error": None,
            }
        if requested == "string":
            return {"value": _as_text(data), "schemaId": None, "format": "string", "error": None}
        if requested == "json":
            return {"value": _decode_json(data), "schemaId": None, "format": "json", "error": None}
        if requested == "avro":
            return _decode_registry_payload(data, registry, subject, strict=True)
        return _decode_auto(data, registry, subject)
    except Exception as exc:
        return {
            "value": _as_text(data) if requested != "bytes" else base64.b64encode(data).decode("ascii"),
            "schemaId": None,
            "format": requested,
            "error": str(exc),
        }


def _decode_registry_payload(
    data: bytes,
    registry: SchemaRegistry | None,
    subject: str | None,
    *,
    strict: bool,
) -> dict:
    wire = parse_confluent_wire(data)
    if wire is None:
        if strict:
            raise ValueError("Payload is not Confluent Avro wire format")
        return {"value": _as_text(data), "schemaId": None, "format": "string", "error": None}
    schema_id, payload = wire
    if registry is None:
        error = "Schema Registry connection is required to decode Avro"
        return {
            "value": base64.b64encode(payload).decode("ascii"),
            "schemaId": schema_id,
            "format": "avro",
            "error": error,
        }
    schema = _load_schema(registry, schema_id, subject)
    schema_type = str(schema.get("schemaType") or "AVRO").upper()
    content = schema.get("content")
    if schema_type in {"JSON", "JSONSCHEMA"}:
        value = _decode_json(payload) if payload else None
    else:
        value = _decode_avro(payload, content)
    return {"value": value, "schemaId": schema_id, "format": "avro", "error": None}


def _decode_auto(data: bytes, registry: SchemaRegistry | None, subject: str | None) -> dict:
    if parse_confluent_wire(data) is not None:
        return _decode_registry_payload(data, registry, subject, strict=False)
    text = _as_text(data).strip()
    if text[:1] in "{[":
        try:
            return {"value": json.loads(text), "schemaId": None, "format": "json", "error": None}
        except ValueError:
            pass
    return {"value": _as_text(data), "schemaId": None, "format": "string", "error": None}


def _load_schema(registry: SchemaRegistry, schema_id: int, subject: str | None) -> dict:
    try:
        return registry.get_schema_by_id(schema_id)
    except SchemaRegistryError:
        if not subject:
            raise
        return registry.get_content("default", subject, "latest")
