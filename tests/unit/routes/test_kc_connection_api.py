import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.routes.kafka_connect_api import kc_api


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(kc_api)
    return app.test_client()


class TestKcConnectionAction(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()
        self.session_patch = patch("app.routes.kafka_connect_api.SessionLocal")
        self.backend_patch = patch("app.routes.kafka_connect_api.get_backend")
        self.mock_session = self.session_patch.start()
        self.mock_get_backend = self.backend_patch.start()
        self.fake_db = MagicMock(name="db")
        self.mock_session.return_value.__enter__.return_value = self.fake_db
        self.mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.backend_patch.stop)

    def _connect(self, name="localhost-kafkaconnect"):
        conn = MagicMock()
        conn.name = name
        conn.type = "connect"
        conn.subtype = "kafka-connect"
        conn.config = {"url": "http://localhost:8083"}
        self.fake_db.query.return_value.filter.return_value.first.return_value = conn
        return conn

    def test_unknown_action_400(self):
        r = self.client.post("/api/kc/connections/kc/connectors/pg/nope")
        self.assertEqual(r.status_code, 400)

    def test_missing_connection_404(self):
        self.fake_db.query.return_value.filter.return_value.first.return_value = None
        r = self.client.post("/api/kc/connections/missing/connectors/pg/status")
        self.assertEqual(r.status_code, 404)

    def test_status_uses_attached_connection(self):
        self._connect()
        backend = MagicMock()
        backend.get_status.return_value = {"name": "pg-orders-src", "connector": {"state": "RUNNING"}}
        self.mock_get_backend.return_value = backend
        r = self.client.post("/api/kc/connections/localhost-kafkaconnect/connectors/pg-orders-src/status")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["method"], "GET")
        self.assertEqual(body["url"], "http://localhost:8083/connectors/pg-orders-src/status")
        self.assertEqual(body["data"]["connector"]["state"], "RUNNING")
        backend.get_status.assert_called_once_with("pg-orders-src")

    def test_pause_delete_dispatch(self):
        self._connect()
        backend = MagicMock()
        self.mock_get_backend.return_value = backend
        r = self.client.post("/api/kc/connections/localhost-kafkaconnect/connectors/pg-orders-src/pause")
        self.assertEqual(r.status_code, 200)
        backend.pause.assert_called_once_with("pg-orders-src")
        r = self.client.post("/api/kc/connections/localhost-kafkaconnect/connectors/pg-orders-src/delete")
        self.assertEqual(r.status_code, 200)
        backend.delete.assert_called_once_with("pg-orders-src")
