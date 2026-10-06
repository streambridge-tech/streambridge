"""Schema Registry connection schema tests."""
import unittest

from app.connectors.infra.schema_registry import SchemaRegistryConnector
from app.connectors.schemas.schema_registry import SCHEMA_REGISTRY_SCHEMA
from app.services.schema_registry.auth import apply_auth_type, resolve_auth_type


class TestSchemaRegistrySchema(unittest.TestCase):

    def test_required_fields(self):
        self.assertEqual(
            {f.id for f in SCHEMA_REGISTRY_SCHEMA.required_fields()},
            {"provider", "url", "username", "password", "token"},
        )

    def test_group_id_removed(self):
        self.assertIsNone(SCHEMA_REGISTRY_SCHEMA.get("group_id"))

    def test_auth_fields_are_conditional(self):
        self.assertEqual(SCHEMA_REGISTRY_SCHEMA.get("username").visible_when["in"], ["basic"])
        self.assertEqual(SCHEMA_REGISTRY_SCHEMA.get("password").visible_when["in"], ["basic"])
        self.assertEqual(SCHEMA_REGISTRY_SCHEMA.get("token").visible_when["in"], ["bearer"])

    def test_json_includes_recommended_and_visible_when(self):
        payload = SCHEMA_REGISTRY_SCHEMA.to_json()
        rec_ids = {f["id"] for f in payload["recommended"]}
        req_ids = {f["id"] for f in payload["required"]}
        self.assertEqual(rec_ids, {"auth_type"})
        self.assertTrue({"username", "password", "token"}.issubset(req_ids))
        username = next(f for f in payload["required"] if f["id"] == "username")
        self.assertEqual(username["visibleWhen"]["field"], "auth_type")


class TestSchemaRegistryConnectorAuth(unittest.TestCase):

    def setUp(self):
        self.connector = SchemaRegistryConnector()

    def test_anonymous_config_strips_credentials(self):
        cfg = self.connector.build_config(
            form={"provider": "apicurio", "url": "http://sr", "auth_type": "none", "username": "u", "password": "p"},
            extra={},
        )
        self.assertEqual(cfg["auth_type"], "none")
        self.assertNotIn("username", cfg)
        self.assertNotIn("password", cfg)
        self.assertNotIn("group_id", cfg)

    def test_basic_requires_user_and_password(self):
        cfg = self.connector.build_config(
            form={"provider": "confluent", "url": "http://sr", "auth_type": "basic", "username": "key"},
            extra={},
        )
        errors = self.connector.validate(cfg)
        self.assertTrue(any("password" in e for e in errors))

    def test_bearer_keeps_token_only(self):
        cfg = self.connector.build_config(
            form={"provider": "apicurio", "url": "http://sr", "auth_type": "bearer", "token": "oidc", "username": "x"},
            extra={},
        )
        self.assertEqual(cfg["token"], "oidc")
        self.assertNotIn("username", cfg)
        self.assertEqual(self.connector.validate(cfg), [])

    def test_switching_to_none_drops_preserved_secrets(self):
        merged = self.connector.merge_preserved_secrets(
            {"provider": "confluent", "url": "http://sr", "auth_type": "none"},
            {"password": "secret", "username": "key", "auth_type": "basic"},
        )
        self.assertEqual(merged["auth_type"], "none")
        self.assertNotIn("password", merged)

    def test_basic_edit_preserves_password(self):
        merged = self.connector.merge_preserved_secrets(
            {"provider": "confluent", "url": "http://sr", "auth_type": "basic", "username": "key"},
            {"password": "secret", "username": "key", "auth_type": "basic"},
        )
        self.assertEqual(merged["password"], "secret")


class TestResolveAuthType(unittest.TestCase):

    def test_infers_basic_from_legacy_config(self):
        self.assertEqual(resolve_auth_type({"username": "u", "password": "p"}), "basic")

    def test_explicit_none_wins(self):
        self.assertEqual(resolve_auth_type({"auth_type": "none", "username": "u", "password": "p"}), "none")
        self.assertNotIn("username", apply_auth_type({"auth_type": "none", "username": "u", "password": "p"}))


if __name__ == "__main__":
    unittest.main()
