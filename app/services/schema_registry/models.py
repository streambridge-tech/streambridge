"""Provider-neutral records for the Schema Registry portal."""

from __future__ import annotations

import json
from typing import Any

DEFAULT_GROUP = "default"


def resolve_group_id(value: Any) -> str:
    """Databricks-style fallback: missing/blank group lands in `default`."""
    if value is None:
        return DEFAULT_GROUP
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "undefined"}:
        return DEFAULT_GROUP
    return text


def pick(record: Any, *keys: str, default: Any = None) -> Any:
    if not isinstance(record, dict):
        return default
    for key in keys:
        value = record.get(key)
        if value is not None:
            return value
    return default


def as_items(raw: Any, *keys: str) -> list:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in keys:
            value = raw.get(key)
            if isinstance(value, list):
                return value
    return []


def parse_content(raw: Any) -> Any:
    """Turn registry payloads into JSON when possible, otherwise keep the original text."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        schema = raw.get("schema") if isinstance(raw, dict) else None
        if isinstance(schema, str):
            parsed = parse_content(schema)
            return parsed if parsed is not None else schema
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return ""
        if text[0] in "{[":
            try:
                return json.loads(text)
            except ValueError:
                return raw
        return raw
    return raw


def group_record(group_id: str, **extra: Any) -> dict:
    record = {"groupId": resolve_group_id(group_id), **extra}
    record.setdefault("artifacts", extra.get("artifacts", []))
    return record


_MESSAGE_PARTS = {"key", "value"}


def artifact_display_name(group_id: str, artifact_id: str, name: str | None = None) -> str:
    """Confluent-style label: Apicurio stores the topic as groupId and key/value as artifactId."""
    resolved_group = resolve_group_id(group_id)
    artifact = str(artifact_id)
    if artifact.lower() in _MESSAGE_PARTS and resolved_group != DEFAULT_GROUP:
        return f"{resolved_group}-{artifact}"
    label = str(name).strip() if name is not None else ""
    if label and label.lower() not in _MESSAGE_PARTS:
        return label
    return artifact


def artifact_record(
    group_id: str,
    artifact_id: str,
    *,
    name: str | None = None,
    schema_type: str | None = None,
    description: str | None = None,
    created_at: Any = None,
    updated_at: Any = None,
    **extra: Any,
) -> dict:
    resolved_group = resolve_group_id(group_id)
    artifact = str(artifact_id)
    display = artifact_display_name(resolved_group, artifact, name)
    return {
        "groupId": resolved_group,
        "artifactId": artifact,
        "name": display,
        "subject": extra.pop("subject", None) or display,
        "schemaType": schema_type or "AVRO",
        "description": description or "",
        "createdAt": created_at,
        "updatedAt": updated_at,
        **extra,
    }


def version_record(version: Any, **extra: Any) -> dict:
    return {"version": str(version), **extra}


def schema_record(
    *,
    group_id: str,
    artifact_id: str,
    version: Any,
    content: Any,
    schema_id: Any = None,
    schema_type: str | None = None,
    latest: bool = False,
    references: list | None = None,
    created_at: Any = None,
    updated_at: Any = None,
    description: str | None = None,
) -> dict:
    return {
        "groupId": resolve_group_id(group_id),
        "artifactId": str(artifact_id),
        "version": str(version),
        "latest": latest,
        "schemaId": schema_id,
        "schemaType": schema_type or "AVRO",
        "content": parse_content(content),
        "references": references or [],
        "createdAt": created_at,
        "updatedAt": updated_at,
        "description": description or "",
    }


def build_catalog(group_ids: list[str], artifacts: list[dict]) -> list[dict]:
    """Merge named groups with discovered artifacts. Always includes `default`."""
    buckets: dict[str, list] = {DEFAULT_GROUP: []}
    for group_id in group_ids:
        buckets.setdefault(resolve_group_id(group_id), [])
    for artifact in artifacts:
        group_id = resolve_group_id(artifact.get("groupId") if isinstance(artifact, dict) else None)
        record = dict(artifact)
        record["groupId"] = group_id
        buckets.setdefault(group_id, []).append(record)
    ordered = [DEFAULT_GROUP, *sorted(group_id for group_id in buckets if group_id != DEFAULT_GROUP)]
    return [group_record(group_id, artifacts=buckets[group_id]) for group_id in ordered]
