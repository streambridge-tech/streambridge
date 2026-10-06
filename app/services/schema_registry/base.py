"""Shared contract and HTTP helpers for Schema Registry providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import requests

from app.services.schema_registry.auth import AUTH_BASIC, AUTH_BEARER, resolve_auth_type
from app.services.schema_registry.models import DEFAULT_GROUP, build_catalog, resolve_group_id


class SchemaRegistryError(RuntimeError):
    """A provider request failed or returned an unsupported response."""


class SchemaRegistry(ABC):
    """Common interface used by the portal API and future Kafka decoders."""

    provider = "unknown"

    def __init__(self, config: dict[str, Any], timeout: float = 10.0):
        self.config = config or {}
        self.base_url = (self.config.get("url") or "").rstrip("/")
        self.timeout = timeout
        if not self.base_url:
            raise SchemaRegistryError("Schema Registry URL is required")

    def _auth_type(self) -> str:
        return resolve_auth_type(self.config)

    def _auth(self):
        if self._auth_type() != AUTH_BASIC:
            return None
        username = self.config.get("username")
        password = self.config.get("password")
        return (username, password) if username and password else None

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {"Accept": "application/json", **(extra or {})}
        if self._auth_type() != AUTH_BEARER:
            return headers
        token = self.config.get("token") or self.config.get("bearer_token")
        if token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(self, method: str, path: str, *, allow_text: bool = False, **kwargs) -> Any:
        headers = self._headers(kwargs.pop("headers", {}))
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                auth=self._auth(),
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = getattr(exc.response, "text", "")[:240] if exc.response is not None else str(exc)
            raise SchemaRegistryError(f"{self.provider} registry request failed: {detail}") from exc
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            if allow_text:
                return response.text
            raise SchemaRegistryError(f"{self.provider} registry returned invalid JSON") from None

    @abstractmethod
    def test_connection(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def list_groups(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def list_artifacts(self, group_id: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def list_versions(self, group_id: str, artifact_id: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def get_content(self, group_id: str, artifact_id: str, version: str = "latest") -> dict:
        raise NotImplementedError

    def get_schema_by_id(self, schema_id: int) -> dict:
        """Resolve a Confluent-wire schema id to content. Override per provider."""
        raise SchemaRegistryError(f"{self.provider} does not support lookup by schema id")

    def list_all_artifacts(self) -> list[dict]:
        artifacts = []
        for group in self.list_groups():
            group_id = resolve_group_id(group.get("groupId"))
            artifacts.extend(self.list_artifacts(group_id))
        return artifacts

    def catalog(self) -> list[dict]:
        group_ids = [resolve_group_id(group.get("groupId")) for group in self.list_groups()]
        try:
            artifacts = self.list_all_artifacts()
        except SchemaRegistryError:
            artifacts = []
        return build_catalog(group_ids, artifacts)

    def list_subjects(self) -> list[dict]:
        subjects = []
        for group in self.catalog():
            for artifact in group.get("artifacts") or []:
                subjects.append({
                    "subject": artifact.get("artifactId"),
                    "groupId": group.get("groupId"),
                    "schemaType": artifact.get("schemaType"),
                })
        return subjects

    def get_schema(self, subject: str, version: str = "latest") -> dict:
        schema = self.get_content(DEFAULT_GROUP, subject, version)
        return {
            "subject": schema["artifactId"],
            "version": schema["version"],
            "schemaId": schema.get("schemaId"),
            "schemaType": schema.get("schemaType"),
            "schema": schema.get("content"),
            "providerMetadata": schema,
        }
