"""Unit tests for Kafka payload decoding."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.services.kafka.decode import decode_payload, parse_confluent_wire
from app.services.schema_registry.models import schema_record


def _wire(schema_id: int, payload: bytes) -> bytes:
    return b"\x00" + schema_id.to_bytes(4, "big") + payload


class ParseWireTests(unittest.TestCase):
    def test_reads_schema_id(self):
        schema_id, payload = parse_confluent_wire(_wire(12, b"{}"))
        self.assertEqual(schema_id, 12)
        self.assertEqual(payload, b"{}")

    def test_rejects_plain_json(self):
        self.assertIsNone(parse_confluent_wire(b'{"id":1}'))


class DecodePayloadTests(unittest.TestCase):
    def test_null_is_tombstone(self):
        result = decode_payload(None, "json")
        self.assertIsNone(result["value"])
        self.assertIsNone(result["error"])

    def test_string_and_json(self):
        self.assertEqual(decode_payload(b"hello", "string")["value"], "hello")
        self.assertEqual(decode_payload(b'{"id":1}', "json")["value"], {"id": 1})

    def test_auto_detects_json(self):
        result = decode_payload(b'{"op":"c"}', "auto")
        self.assertEqual(result["format"], "json")
        self.assertEqual(result["value"]["op"], "c")

    def test_avro_requires_registry_but_keeps_payload(self):
        result = decode_payload(_wire(9, b"abc"), "avro")
        self.assertEqual(result["schemaId"], 9)
        self.assertIsNotNone(result["error"])

    def test_avro_uses_registry_schema_id(self):
        registry = MagicMock()
        registry.get_schema_by_id.return_value = schema_record(
            group_id="default",
            artifact_id="users-value",
            version="1",
            content={"type": "object"},
            schema_id=9,
            schema_type="JSON",
        )
        result = decode_payload(_wire(9, b'{"id":1}'), "avro", registry=registry, subject="users-value")
        self.assertEqual(result["schemaId"], 9)
        self.assertEqual(result["value"], {"id": 1})
        registry.get_schema_by_id.assert_called_once_with(9)

    def test_json_schema_payload_via_registry(self):
        registry = MagicMock()
        registry.get_schema_by_id.return_value = schema_record(
            group_id="default",
            artifact_id="users-value",
            version="1",
            content={"type": "object"},
            schema_id=3,
            schema_type="JSON",
        )
        result = decode_payload(_wire(3, b'{"id":7}'), "auto", registry=registry)
        self.assertEqual(result["value"], {"id": 7})
        self.assertEqual(result["schemaId"], 3)

    def test_invalid_json_returns_error(self):
        result = decode_payload(b"{not-json", "json")
        self.assertIsNotNone(result["error"])


if __name__ == "__main__":
    unittest.main()
