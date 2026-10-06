"""Confluent Schema Registry adapter."""

import json
from urllib.parse import quote

from app.services.schema_registry.base import SchemaRegistry
from app.services.schema_registry.models import (
    DEFAULT_GROUP,
    artifact_record,
    group_record,
    resolve_group_id,
    schema_record,
    version_record,
)


class ConfluentRegistry(SchemaRegistry):
    provider = "confluent"

    def test_connection(self) -> dict:
        subjects = self._request("GET", "/subjects")
        return {
            "success": True,
            "provider": self.provider,
            "subjectCount": len(subjects) if isinstance(subjects, list) else 0,
        }

    def list_groups(self) -> list[dict]:
        return [group_record(DEFAULT_GROUP)]

    def list_artifacts(self, group_id: str) -> list[dict]:
        subjects = self._request("GET", "/subjects") or []
        return [
            artifact_record(resolve_group_id(group_id), subject, name=subject)
            for subject in subjects
            if subject
        ]

    def list_all_artifacts(self) -> list[dict]:
        return self.list_artifacts(DEFAULT_GROUP)

    def list_versions(self, group_id: str, artifact_id: str) -> list[dict]:
        path = f"/subjects/{quote(artifact_id, safe='')}/versions"
        raw = self._request("GET", path) or []
        return [version_record(version) for version in raw]

    def get_content(self, group_id: str, artifact_id: str, version: str = "latest") -> dict:
        versions = self.list_versions(group_id, artifact_id)
        latest = str(versions[-1]["version"]) if versions else "latest"
        resolved = latest if not version or version == "latest" else str(version)
        path = f"/subjects/{quote(artifact_id, safe='')}/versions/{quote(resolved, safe='')}"
        raw = self._request("GET", path) or {}
        return schema_record(
            group_id=resolve_group_id(group_id),
            artifact_id=raw.get("subject") or artifact_id,
            version=raw.get("version", resolved),
            content=raw.get("schema"),
            schema_id=raw.get("id"),
            schema_type=raw.get("schemaType") or "AVRO",
            latest=str(raw.get("version", resolved)) == latest,
            references=raw.get("references") or [],
        )

    def get_schema_by_id(self, schema_id: int) -> dict:
        raw = self._request("GET", f"/schemas/ids/{int(schema_id)}") or {}
        return schema_record(
            group_id=DEFAULT_GROUP,
            artifact_id=str(schema_id),
            version="id",
            content=raw.get("schema"),
            schema_id=schema_id,
            schema_type=raw.get("schemaType") or "AVRO",
            references=raw.get("references") or [],
        )

    def register_schema(self, subject: str, schema: dict) -> dict:
        path = f"/subjects/{quote(subject, safe='')}/versions"
        payload = schema if isinstance(schema, str) else json.dumps(schema)
        return self._request("POST", path, json={"schema": payload})

    def get_compatibility(self, subject: str) -> dict:
        path = f"/config/{quote(subject, safe='')}"
        return self._request("GET", path)

    def set_compatibility(self, subject: str, level: str) -> dict:
        path = f"/config/{quote(subject, safe='')}"
        return self._request("PUT", path, json={"compatibility": level})
