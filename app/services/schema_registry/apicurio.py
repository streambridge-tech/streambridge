"""Apicurio Registry Core v3 adapter."""

from urllib.parse import quote, urlsplit, urlunsplit

from app.services.schema_registry.base import SchemaRegistry, SchemaRegistryError
from app.services.schema_registry.models import (
    DEFAULT_GROUP,
    as_items,
    artifact_record,
    group_record,
    pick,
    resolve_group_id,
    schema_record,
    version_record,
)

_CORE_PREFIX = "/apis/registry/v3"
_STRIP_PREFIXES = (
    "/apis/registry/v3",
    "/apis/registry/v2",
    "/apis/ccompat/v7",
    "/apis/ccompat/v6",
    "/apis/ccompat/v1",
)


def normalize_apicurio_url(url: str) -> str:
    """Point any Apicurio origin or compatibility URL at Core v3."""
    cleaned = (url or "").strip()
    if not cleaned:
        raise SchemaRegistryError("Schema Registry URL is required")
    parts = urlsplit(cleaned)
    path = parts.path or ""
    for prefix in _STRIP_PREFIXES:
        idx = path.find(prefix)
        if idx != -1:
            path = path[:idx]
            break
    core_path = path.rstrip("/") + _CORE_PREFIX
    return urlunsplit((parts.scheme, parts.netloc, core_path, "", "")).rstrip("/")


class ApicurioRegistry(SchemaRegistry):
    provider = "apicurio"

    def __init__(self, config: dict, timeout: float = 10.0):
        super().__init__(config, timeout)
        self.base_url = normalize_apicurio_url(self.base_url)

    def _group_path(self, group_id: str) -> str:
        return f"/groups/{quote(resolve_group_id(group_id), safe='')}"

    def _artifact_path(self, group_id: str, artifact_id: str) -> str:
        return f"{self._group_path(group_id)}/artifacts/{quote(artifact_id, safe='')}"

    def test_connection(self) -> dict:
        groups = self.list_groups()
        return {"success": True, "provider": self.provider, "groupCount": len(groups)}

    def list_groups(self) -> list[dict]:
        raw = self._request("GET", "/groups", params={"limit": 500})
        items = as_items(raw, "groups", "items")
        groups = []
        for item in items:
            group_id = item if isinstance(item, str) else pick(item, "groupId", "id", "name")
            if group_id:
                groups.append(group_record(str(group_id)))
        return groups

    def _artifact_from_item(self, item: dict, group_id: str | None = None) -> dict | None:
        artifact_id = pick(item, "artifactId", "id", "name")
        if not artifact_id:
            return None
        return artifact_record(
            group_id if group_id is not None else pick(item, "groupId"),
            artifact_id,
            name=pick(item, "name", "artifactId", "id"),
            schema_type=pick(item, "artifactType", "type") or "AVRO",
            description=pick(item, "description", default=""),
            created_at=pick(item, "createdOn", "createdAt"),
            updated_at=pick(item, "modifiedOn", "modifiedAt", "updatedAt"),
        )

    def list_artifacts(self, group_id: str) -> list[dict]:
        resolved = resolve_group_id(group_id)
        raw = self._request("GET", f"{self._group_path(resolved)}/artifacts", params={"limit": 500})
        items = as_items(raw, "artifacts", "items")
        artifacts = []
        for item in items:
            if not isinstance(item, dict):
                continue
            artifact = self._artifact_from_item(item, resolved)
            if artifact:
                artifacts.append(artifact)
        return artifacts

    def list_all_artifacts(self) -> list[dict]:
        artifacts = []
        offset = 0
        limit = 100
        while True:
            raw = self._request("GET", "/search/artifacts", params={"limit": limit, "offset": offset})
            items = as_items(raw, "artifacts", "items")
            for item in items:
                if isinstance(item, dict):
                    artifact = self._artifact_from_item(item)
                    if artifact:
                        artifacts.append(artifact)
            offset += len(items)
            total = raw.get("count") if isinstance(raw, dict) else None
            if not items or len(items) < limit or (total is not None and offset >= total):
                break
        return artifacts

    def list_versions(self, group_id: str, artifact_id: str) -> list[dict]:
        raw = self._request("GET", f"{self._artifact_path(group_id, artifact_id)}/versions")
        items = as_items(raw, "versions", "items")
        versions = []
        for item in items:
            version = item if not isinstance(item, dict) else pick(item, "version", "versionId")
            if version is None or version == "":
                continue
            versions.append(version_record(
                version,
                schemaId=pick(item, "globalId", "contentId", "id") if isinstance(item, dict) else None,
                schemaType=pick(item, "artifactType", "type") if isinstance(item, dict) else None,
                createdAt=pick(item, "createdOn", "createdAt") if isinstance(item, dict) else None,
            ))
        return versions

    def get_content(self, group_id: str, artifact_id: str, version: str = "latest") -> dict:
        versions = self.list_versions(group_id, artifact_id)
        if not versions:
            raise SchemaRegistryError(f"No versions found for {resolve_group_id(group_id)}/{artifact_id}")
        latest = str(versions[-1]["version"])
        resolved = latest if not version or version == "latest" else str(version)
        path = f"{self._artifact_path(group_id, artifact_id)}/versions/{quote(resolved, safe='')}/content"
        content = self._request("GET", path, allow_text=True)
        meta = next((item for item in versions if str(item["version"]) == resolved), {})
        return schema_record(
            group_id=resolve_group_id(group_id),
            artifact_id=artifact_id,
            version=resolved,
            content=content,
            schema_id=meta.get("schemaId"),
            schema_type=meta.get("schemaType"),
            latest=resolved == latest,
            created_at=meta.get("createdAt"),
        )

    def get_schema_by_id(self, schema_id: int) -> dict:
        path = f"/ids/globalIds/{int(schema_id)}/content"
        content = self._request("GET", path, allow_text=True)
        return schema_record(
            group_id=DEFAULT_GROUP,
            artifact_id=str(schema_id),
            version="id",
            content=content,
            schema_id=schema_id,
        )

    def register_schema(self, subject: str, schema: dict) -> dict:
        path = f"{self._group_path(DEFAULT_GROUP)}/artifacts/{quote(subject, safe='')}"
        return self._request("POST", path, json=schema)

    def get_compatibility(self, subject: str) -> dict:
        path = f"{self._artifact_path(DEFAULT_GROUP, subject)}/rules/VALIDITY"
        return self._request("GET", path)

    def set_compatibility(self, subject: str, level: str) -> dict:
        path = f"{self._artifact_path(DEFAULT_GROUP, subject)}/rules/VALIDITY"
        return self._request("PUT", path, json={"config": level})
