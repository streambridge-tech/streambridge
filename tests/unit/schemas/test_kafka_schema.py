"""Kafka broker schema tests — locks Connect / librdkafka key spelling."""
import unittest

from app.connectors.infra.kafka_broker import KafkaBrokerConnector
from app.connectors.schemas import build_kc_config, build_test_kwargs
from app.connectors.schemas.kafka import KAFKA_SCHEMA


class TestKafkaSchemaIdentity(unittest.TestCase):

    def test_subtype(self):
        self.assertEqual(KAFKA_SCHEMA.subtype, "kafka")

    def test_required_field_ids(self):
        ids = {f.id for f in KAFKA_SCHEMA.required_fields()}
        self.assertEqual(ids, {"bootstrap_servers", "security_protocol"})

    def test_timeout_is_not_a_connection_field(self):
        self.assertIsNone(KAFKA_SCHEMA.get("request_timeout_ms"))
        self.assertIsNone(KAFKA_SCHEMA.by_kc_key("request.timeout.ms"))

    def test_kc_keys_are_unique(self):
        kc_keys = [f.kc_key for f in KAFKA_SCHEMA.fields if f.kc_key]
        self.assertEqual(len(kc_keys), len(set(kc_keys)))

    def test_connect_key_spelling(self):
        expected = {
            "bootstrap_servers": "bootstrap.servers",
            "security_protocol": "security.protocol",
            "client_id": "client.id",
            "sasl_mechanism": "sasl.mechanism",
            "username": "sasl.username",
            "password": "sasl.password",
            "ssl_ca_location": "ssl.ca.location",
            "ssl_certificate_location": "ssl.certificate.location",
            "ssl_key_location": "ssl.key.location",
            "ssl_key_password": "ssl.key.password",
            "ssl_endpoint_identification_algorithm": "ssl.endpoint.identification.algorithm",
        }
        for field_id, kc_key in expected.items():
            f = KAFKA_SCHEMA.get(field_id)
            self.assertIsNotNone(f, f"missing field: {field_id}")
            self.assertEqual(f.kc_key, kc_key)
            self.assertEqual(f.test_key, kc_key)

    def test_password_is_secret(self):
        self.assertTrue(KAFKA_SCHEMA.get("password").secret)

    def test_sasl_fields_gated_on_protocol(self):
        self.assertEqual(KAFKA_SCHEMA.get("username").visible_when["in"], ["SASL_PLAINTEXT", "SASL_SSL"])


class TestKafkaConfigBuild(unittest.TestCase):

    def _form(self, **overrides):
        base = {"bootstrap_servers": "b1:9092,b2:9092",
                "security_protocol": "SASL_SSL"}
        base.update(overrides)
        return base

    def test_required_flat_map(self):
        cfg = build_kc_config(KAFKA_SCHEMA, self._form())
        self.assertEqual(cfg["bootstrap.servers"], "b1:9092,b2:9092")
        self.assertEqual(cfg["security.protocol"], "SASL_SSL")

    def test_sasl_credentials_map_to_librdkafka(self):
        cfg = build_kc_config(KAFKA_SCHEMA, self._form(
            sasl_mechanism="PLAIN", username="apikey", password="apisec"
        ))
        kwargs = build_test_kwargs(KAFKA_SCHEMA, cfg)
        self.assertEqual(kwargs["sasl.username"], "apikey")
        self.assertEqual(kwargs["sasl.password"], "apisec")
        self.assertEqual(kwargs["sasl.mechanism"], "PLAIN")

    def test_build_config_drops_timeout_and_unused_sasl(self):
        cfg = KafkaBrokerConnector().build_config(
            form={"bootstrap_servers": "localhost:9093", "security_protocol": "PLAINTEXT"},
            extra={"request.timeout.ms": "30000", "sasl.password": "leftover"},
        )
        self.assertNotIn("request.timeout.ms", cfg)
        self.assertNotIn("sasl.password", cfg)
        self.assertEqual(cfg["bootstrap.servers"], "localhost:9093")


if __name__ == "__main__":
    unittest.main()
