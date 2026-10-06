"""Unit tests for librdkafka client config mapping."""

from __future__ import annotations

import unittest

from app.services.kafka.client import STANDARD_TIMEOUT_MS, kafka_client_config
from app.services.kafka.errors import KafkaBrowseError


class KafkaClientConfigTests(unittest.TestCase):
    def test_maps_native_keys_and_applies_standard_timeout(self):
        conf = kafka_client_config({
            "bootstrap.servers": "localhost:9092",
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": "PLAIN",
            "sasl.username": "user",
            "sasl.password": "secret",
            "request.timeout.ms": 30000,
        })
        self.assertEqual(conf["bootstrap.servers"], "localhost:9092")
        self.assertEqual(conf["sasl.username"], "user")
        self.assertEqual(conf["socket.timeout.ms"], str(STANDARD_TIMEOUT_MS))
        self.assertNotIn("request.timeout.ms", conf)

    def test_strips_sasl_for_plaintext(self):
        conf = kafka_client_config({
            "bootstrap.servers": "localhost:9093",
            "security.protocol": "PLAINTEXT",
            "sasl.mechanism": "PLAIN",
            "sasl.password": "leftover",
        })
        self.assertEqual(conf["security.protocol"], "PLAINTEXT")
        self.assertFalse(any(key.startswith("sasl.") for key in conf))

    def test_keeps_extra_librdkafka_properties(self):
        conf = kafka_client_config({
            "bootstrap.servers": "kafka:9092",
            "security.protocol": "PLAINTEXT",
            "connections.max.idle.ms": "60000",
        })
        self.assertEqual(conf["connections.max.idle.ms"], "60000")

    def test_requires_bootstrap(self):
        with self.assertRaises(KafkaBrowseError):
            kafka_client_config({})


if __name__ == "__main__":
    unittest.main()
