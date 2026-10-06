"""HTTP tests for Kafka broker browse routes."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.routes.kafka_api import kafka_api
from app.services.kafka.errors import KafkaBrowseError


class KafkaApiTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(kafka_api)
        self.client = app.test_client()
        self.session_patch = patch("app.routes.kafka_api.SessionLocal")
        self.mock_session = self.session_patch.start()
        self.fake_db = MagicMock()
        self.mock_session.return_value.__enter__.return_value = self.fake_db
        self.mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)

    def _broker(self, name="kafka-prod"):
        row = MagicMock()
        row.name = name
        row.subtype = "kafka"
        row.status = "live"
        row.config = {"bootstrap.servers": "kafka:9092"}
        return row

    def test_list_brokers(self):
        self.fake_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [self._broker()]
        resp = self.client.get("/api/kafka-brokers")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()[0]["name"], "kafka-prod")

    def test_topics_not_found(self):
        self.fake_db.query.return_value.filter.return_value.first.return_value = None
        resp = self.client.get("/api/kafka-brokers/missing/topics")
        self.assertEqual(resp.status_code, 404)

    @patch("app.routes.kafka_api.list_topics")
    def test_topics_ok(self, mocked):
        self.fake_db.query.return_value.filter.return_value.first.return_value = self._broker()
        mocked.return_value = [{"name": "orders", "partitions": 1, "partitionIds": [0]}]
        resp = self.client.get("/api/kafka-brokers/kafka-prod/topics")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["topics"][0]["name"], "orders")

    def test_messages_require_topic(self):
        resp = self.client.get("/api/kafka-brokers/kafka-prod/messages")
        self.assertEqual(resp.status_code, 400)

    @patch("app.routes.kafka_api.consume_messages")
    def test_messages_ok(self, mocked):
        self.fake_db.query.return_value.filter.return_value.first.return_value = self._broker()
        mocked.return_value = {"topic": "orders", "messages": [], "count": 0, "hasOlder": False, "cursor": {}, "partitions": [0]}
        resp = self.client.get("/api/kafka-brokers/kafka-prod/messages?topic=orders&limit=20")
        self.assertEqual(resp.status_code, 200)
        mocked.assert_called_once()
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["limit"], 20)
        self.assertEqual(kwargs["value_subject"], "orders-value")

    @patch("app.routes.kafka_api.consume_messages")
    def test_messages_broker_error(self, mocked):
        self.fake_db.query.return_value.filter.return_value.first.return_value = self._broker()
        mocked.side_effect = KafkaBrowseError("timeout")
        resp = self.client.get("/api/kafka-brokers/kafka-prod/messages?topic=orders")
        self.assertEqual(resp.status_code, 502)

    def test_invalid_before_json(self):
        resp = self.client.get("/api/kafka-brokers/kafka-prod/messages?topic=orders&before=not-json")
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
