"""Kafka Connect REST schema tests."""
import unittest

from app.connectors.schemas import build_kc_config, build_test_kwargs
from app.connectors.schemas.kafka_connect import KAFKA_CONNECT_SCHEMA


class TestKafkaConnectSchemaIdentity(unittest.TestCase):

    def test_subtype(self):
        self.assertEqual(KAFKA_CONNECT_SCHEMA.subtype, "kafka-connect")

    def test_required_field_ids(self):
        ids = {f.id for f in KAFKA_CONNECT_SCHEMA.required_fields()}
        self.assertEqual(ids, {
            "url", "deployment", "username", "password",
            "api_host", "namespace", "cluster", "api_token",
        })

    def test_kc_keys_are_unique(self):
        kc_keys = [f.kc_key for f in KAFKA_CONNECT_SCHEMA.fields if f.kc_key]
        self.assertEqual(len(kc_keys), len(set(kc_keys)))

    def test_password_is_secret(self):
        self.assertTrue(KAFKA_CONNECT_SCHEMA.get("password").secret)

    def test_url_test_key_mirrors_kc_key(self):
        # Both consumers (KC deploy + test_connection) use "url".
        f = KAFKA_CONNECT_SCHEMA.get("url")
        self.assertEqual(f.kc_key, "url")
        self.assertEqual(f.test_key, "url")


class TestKafkaConnectConfigBuild(unittest.TestCase):

    def test_url_only(self):
        cfg = build_kc_config(KAFKA_CONNECT_SCHEMA, {"url": "http://kc:8083"})
        self.assertEqual(cfg["url"], "http://kc:8083")

    def test_basic_auth_passthrough(self):
        cfg = build_kc_config(KAFKA_CONNECT_SCHEMA, {
            "url": "http://kc:8083", "username": "admin", "password": "s"
        })
        kwargs = build_test_kwargs(KAFKA_CONNECT_SCHEMA, cfg)
        self.assertEqual(kwargs["username"], "admin")
        self.assertEqual(kwargs["password"], "s")

    def test_verify_ssl_bool_transform(self):
        cfg = build_kc_config(KAFKA_CONNECT_SCHEMA, {
            "url": "http://kc:8083", "verify_ssl": "false"
        })
        self.assertEqual(cfg["verify.ssl"], "false")
        kwargs = build_test_kwargs(KAFKA_CONNECT_SCHEMA, cfg)
        self.assertIs(kwargs["verify_ssl"], False)


if __name__ == "__main__":
    unittest.main()
