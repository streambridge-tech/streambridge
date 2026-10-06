"""Unit tests for provider-neutral Schema Registry adapters and routes."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.routes.schema_registry_api import schema_registry_api
from app.services.schema_registry.apicurio import ApicurioRegistry, normalize_apicurio_url
from app.services.schema_registry.confluent import ConfluentRegistry
from app.services.schema_registry.factory import get_schema_registry
from app.services.schema_registry.models import artifact_display_name, parse_content, resolve_group_id


class ParseContentTests(unittest.TestCase):
    def test_parses_json_string(self):
        self.assertEqual(parse_content('{"type":"record"}'), {"type": "record"})

    def test_keeps_protobuf_text(self):
        self.assertEqual(parse_content("syntax = \"proto3\";"), "syntax = \"proto3\";")

    def test_missing_group_is_default(self):
        self.assertEqual(resolve_group_id(None), "default")
        self.assertEqual(resolve_group_id(""), "default")
        self.assertEqual(resolve_group_id("my-group"), "my-group")

    def test_apicurio_key_value_uses_topic_subject(self):
        self.assertEqual(
            artifact_display_name("apicurio.inventory.products", "value"),
            "apicurio.inventory.products-value",
        )
        self.assertEqual(
            artifact_display_name("apicurio.inventory.products", "key", "Envelope"),
            "apicurio.inventory.products-key",
        )

    def test_named_artifact_keeps_human_name(self):
        self.assertEqual(artifact_display_name("my-group", "share-price", "Share Price"), "Share Price")


class ApicurioUrlTests(unittest.TestCase):
    def test_origin_becomes_core_v3(self):
        self.assertEqual(normalize_apicurio_url("http://localhost:8080"), "http://localhost:8080/apis/registry/v3")

    def test_ccompat_url_is_rewritten_to_core_v3(self):
        self.assertEqual(
            normalize_apicurio_url("http://localhost:8080/apis/ccompat/v7"),
            "http://localhost:8080/apis/registry/v3",
        )


class ApicurioAdapterTests(unittest.TestCase):
    def setUp(self):
        self.client = ApicurioRegistry({"url": "http://localhost:8080", "provider": "apicurio"})

    def test_catalog_is_groups_then_artifacts(self):
        with patch.object(self.client, "_request", side_effect=[
            {"groups": [{"groupId": "my-group"}]},
            {"artifacts": [
                {"artifactId": "share-price", "artifactType": "AVRO", "name": "Share Price", "groupId": "my-group"},
                {"artifactId": "city", "artifactType": "JSON"},
            ], "count": 2},
        ]):
            catalog = self.client.catalog()
        groups = {group["groupId"]: group for group in catalog}
        self.assertIn("default", groups)
        self.assertIn("my-group", groups)
        self.assertEqual(groups["my-group"]["artifacts"][0]["artifactId"], "share-price")
        self.assertEqual(groups["my-group"]["artifacts"][0]["name"], "Share Price")
        self.assertEqual(groups["default"]["artifacts"][0]["artifactId"], "city")
        self.assertEqual(groups["default"]["artifacts"][0]["schemaType"], "JSON")

    def test_key_value_artifacts_display_topic_subject(self):
        with patch.object(self.client, "_request", side_effect=[
            {"groups": [{"groupId": "apicurio.inventory.products"}]},
            {"artifacts": [
                {"artifactId": "key", "artifactType": "AVRO", "name": "KeyEnvelope", "groupId": "apicurio.inventory.products"},
                {"artifactId": "value", "artifactType": "AVRO", "name": "ValueEnvelope", "groupId": "apicurio.inventory.products"},
            ], "count": 2},
        ]):
            catalog = self.client.catalog()
        groups = {group["groupId"]: group for group in catalog}
        artifacts = {item["artifactId"]: item for item in groups["apicurio.inventory.products"]["artifacts"]}
        self.assertEqual(artifacts["key"]["artifactId"], "key")
        self.assertEqual(artifacts["key"]["name"], "apicurio.inventory.products-key")
        self.assertEqual(artifacts["value"]["name"], "apicurio.inventory.products-value")
        self.assertEqual(artifacts["value"]["subject"], "apicurio.inventory.products-value")

    def test_get_content_uses_latest_version(self):
        with patch.object(self.client, "_request", side_effect=[
            {"versions": [{"version": "1"}, {"version": "2"}]},
            {"type": "record", "name": "SharePrice"},
        ]):
            schema = self.client.get_content("my-group", "share-price", "latest")
        self.assertEqual(schema["version"], "2")
        self.assertTrue(schema["latest"])
        self.assertEqual(schema["content"]["name"], "SharePrice")


class ConfluentAdapterTests(unittest.TestCase):
    def setUp(self):
        self.client = ConfluentRegistry({"url": "http://localhost:8081", "provider": "confluent"})

    def test_catalog_uses_default_group(self):
        with patch.object(self.client, "_request", return_value=["users-value", "orders-value"]):
            catalog = self.client.catalog()
        self.assertEqual(catalog[0]["groupId"], "default")
        self.assertEqual([item["artifactId"] for item in catalog[0]["artifacts"]], ["users-value", "orders-value"])

    def test_get_content_normalizes_schema_string(self):
        with patch.object(self.client, "_request", side_effect=[
            [1, 2],
            {"subject": "users-value", "version": 2, "id": 12, "schemaType": "AVRO", "schema": '{"type":"record","name":"User"}'},
        ]):
            schema = self.client.get_content("default", "users-value", "latest")
        self.assertEqual(schema["schemaId"], 12)
        self.assertEqual(schema["artifactId"], "users-value")
        self.assertEqual(schema["content"]["name"], "User")


class FactoryTests(unittest.TestCase):
    def test_factory_returns_matching_provider(self):
        self.assertEqual(get_schema_registry({"provider": "apicurio", "url": "http://sr"}).provider, "apicurio")
        self.assertEqual(get_schema_registry({"provider": "confluent", "url": "http://sr"}).provider, "confluent")


class AuthRequestTests(unittest.TestCase):
    def _call(self, config):
        client = ConfluentRegistry(config)
        response = MagicMock()
        response.content = b"[]"
        response.json.return_value = []
        response.raise_for_status.return_value = None
        with patch("app.services.schema_registry.base.requests.request", return_value=response) as mocked:
            client.list_artifacts("default")
        return mocked.call_args.kwargs

    def test_none_sends_no_credentials(self):
        kwargs = self._call({
            "provider": "confluent",
            "url": "http://sr",
            "auth_type": "none",
            "username": "u",
            "password": "p",
            "token": "t",
        })
        self.assertIsNone(kwargs["auth"])
        self.assertNotIn("Authorization", kwargs["headers"])

    def test_basic_uses_http_basic(self):
        kwargs = self._call({
            "provider": "confluent",
            "url": "http://sr",
            "auth_type": "basic",
            "username": "api-key",
            "password": "api-secret",
        })
        self.assertEqual(kwargs["auth"], ("api-key", "api-secret"))
        self.assertNotIn("Authorization", kwargs["headers"])

    def test_bearer_sets_authorization_header(self):
        kwargs = self._call({
            "provider": "confluent",
            "url": "http://sr",
            "auth_type": "bearer",
            "token": "oidc-token",
            "username": "u",
            "password": "p",
        })
        self.assertIsNone(kwargs["auth"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer oidc-token")


class SchemaRegistryRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(schema_registry_api)
        self.client = app.test_client()
        self.session_patch = patch("app.routes.schema_registry_api.SessionLocal")
        self.factory_patch = patch("app.routes.schema_registry_api.get_schema_registry")
        self.mock_session = self.session_patch.start()
        self.mock_factory = self.factory_patch.start()
        self.fake_db = MagicMock()
        self.mock_session.return_value.__enter__.return_value = self.fake_db
        self.mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.factory_patch.stop)

    def test_catalog_route_returns_generic_groups(self):
        connection = MagicMock()
        connection.config = {"provider": "apicurio", "url": "http://localhost:8080"}
        self.fake_db.query.return_value.filter.return_value.first.return_value = connection
        registry = MagicMock()
        registry.provider = "apicurio"
        registry.catalog.return_value = [{"groupId": "my-group", "artifacts": [{"artifactId": "share-price"}]}]
        self.mock_factory.return_value = registry

        resp = self.client.get("/api/schema-registries/local-sr/catalog")
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload["provider"], "apicurio")
        self.assertEqual(payload["groups"][0]["groupId"], "my-group")

    def test_content_requires_artifact(self):
        resp = self.client.get("/api/schema-registries/local-sr/content")
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
