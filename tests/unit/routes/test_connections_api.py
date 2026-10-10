import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.connection import Connection
from app.routes.connections_api import connections_api
from app.utils.db import Base


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Connection.__table__])
    return sessionmaker(bind=engine)()


class ConnectionsApiRetiredTypesTests(unittest.TestCase):
    def setUp(self):
        self.db = _session()
        app = Flask(__name__)
        app.register_blueprint(connections_api)
        self.client = app.test_client()
        self.session_patch = patch("app.routes.connections_api.SessionLocal")
        mock_session = self.session_patch.start()
        mock_session.return_value.__enter__.return_value = self.db
        mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.db.close)

    def test_post_postgres_source_is_rejected(self):
        r = self.client.post("/api/connections", json={
            "name": "pg-prod",
            "type": "source",
            "subtype": "postgres",
            "host": "db.internal",
            "port": 5432,
            "database": "orders",
            "username": "cdc",
            "password": "x",
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("retired", (r.get_json() or {}).get("error", "").lower())
        self.assertEqual(self.db.query(Connection).count(), 0)

    def test_post_s3_sink_is_rejected(self):
        r = self.client.post("/api/connections", json={
            "name": "lake",
            "type": "sink",
            "subtype": "s3",
        })
        self.assertEqual(r.status_code, 400)

    def test_test_mysql_is_rejected(self):
        r = self.client.post("/api/connections/test", json={
            "type": "source",
            "subtype": "mysql",
            "host": "db",
        })
        self.assertEqual(r.status_code, 400)

    def test_put_existing_postgres_is_rejected(self):
        row = Connection(
            name="legacy-pg",
            type="source",
            subtype="postgres",
            status="draft",
            used_in=[],
            config={"database.hostname": "db"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        r = self.client.put(f"/api/connections/{row.id}", json={"name": "legacy-pg-2"})
        self.assertEqual(r.status_code, 400)


class _ConnectionsApiCase(unittest.TestCase):
    def setUp(self):
        self.db = _session()
        app = Flask(__name__)
        app.register_blueprint(connections_api)
        self.client = app.test_client()
        session_patch = patch("app.routes.connections_api.SessionLocal")
        mock_session = session_patch.start()
        mock_session.return_value.__enter__.return_value = self.db
        mock_session.return_value.__exit__.return_value = False
        self.addCleanup(session_patch.stop)
        self.addCleanup(self.db.close)

    def _saved(self, **fields):
        now = datetime.now(timezone.utc)
        row = Connection(status="draft", used_in=[], created_at=now, updated_at=now, **fields)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row


class ConnectionKindValidationTests(_ConnectionsApiCase):
    def _saved_connect(self):
        return self._saved(name="kc", type="connect", subtype="kafka-connect", config={"url": "http://kc:8083"})

    def test_put_null_type_is_rejected(self):
        row = self._saved_connect()
        r = self.client.put(f"/api/connections/{row.id}", json={"type": None})
        self.assertEqual(r.status_code, 400)
        self.assertIn("type", r.get_json()["error"])
        self.db.refresh(row)
        self.assertEqual(row.type, "connect")

    def test_put_non_string_type_or_subtype_is_rejected(self):
        row = self._saved_connect()
        for body in ({"type": 5}, {"type": ["connect"]}, {"type": ""}, {"subtype": 7}, {"subtype": {"a": 1}}):
            r = self.client.put(f"/api/connections/{row.id}", json=body)
            self.assertEqual(r.status_code, 400, body)

    def test_put_without_type_still_updates(self):
        row = self._saved_connect()
        r = self.client.put(f"/api/connections/{row.id}", json={"name": "kc-2", "url": "http://kc:8083"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["name"], "kc-2")

    def test_post_non_string_type_or_subtype_is_rejected(self):
        for kind in ({"type": 5, "subtype": "kafka-connect"}, {"type": "connect", "subtype": ["kafka-connect"]},
                     {"type": {"x": 1}, "subtype": "kafka-connect"}, {"type": "connect", "subtype": "  "}):
            r = self.client.post("/api/connections", json={"name": "kc", "url": "http://kc:8083", **kind})
            self.assertEqual(r.status_code, 400, kind)
            self.assertIn("error", r.get_json())
        self.assertEqual(self.db.query(Connection).count(), 0)

    def test_test_non_string_type_is_rejected(self):
        r = self.client.post("/api/connections/test", json={"type": 5, "subtype": "kafka-connect"})
        self.assertEqual(r.status_code, 400)

    def test_non_object_body_is_rejected(self):
        row = self._saved_connect()
        for method, url in (("post", "/api/connections"), ("put", f"/api/connections/{row.id}"),
                            ("post", "/api/connections/test")):
            r = getattr(self.client, method)(url, json=[1, 2])
            self.assertEqual(r.status_code, 400, url)
            self.assertIn("object", r.get_json()["error"])

    def test_test_id_must_be_an_integer(self):
        row = self._saved_connect()
        for bad in ([1, 2], {}, True, str(row.id), 1.5):
            r = self.client.post("/api/connections/test", json={
                "id": bad, "type": "connect", "subtype": "kafka-connect", "url": "http://kc:8083"})
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn("id", r.get_json()["error"])


class _Response:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


@patch("app.services.alerting.channels.slack.requests.post", return_value=_Response())
class SavedNotificationTestTests(_ConnectionsApiCase):
    """"Run now" and the inline "Test" post the masked secret; the stored one must be used."""

    MASK = "•" * 8

    def _slack(self):
        return self._saved(name="alerts", type="notification", subtype="notification-slack",
                           config={"host": "https://hooks.slack.com", "password": "/services/T0/B0/real"})

    def test_run_now_uses_the_stored_webhook_secret(self, post):
        row = self._slack()
        body = {"id": row.id, "type": "notification", "subtype": "notification-slack", **row.to_dict()["config"]}
        self.assertEqual(body["password"], self.MASK)
        r = self.client.post("/api/connections/test", json=body)
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertTrue(r.get_json()["success"])
        self.assertEqual(post.call_args.args[0], "https://hooks.slack.com/services/T0/B0/real")

    def test_inline_test_without_a_secret_uses_the_stored_one(self, post):
        row = self._slack()
        r = self.client.post("/api/connections/test", json={
            "id": row.id, "type": "notification", "subtype": "notification-slack",
            "host": "https://hooks.slack.com",
        })
        self.assertTrue(r.get_json()["success"])
        self.assertEqual(post.call_args.args[0], "https://hooks.slack.com/services/T0/B0/real")

    def test_stored_secret_is_never_sent_to_a_different_host(self, post):
        row = self._slack()
        self.client.post("/api/connections/test", json={
            "id": row.id, "type": "notification", "subtype": "notification-slack",
            "host": "https://attacker.example", "password": self.MASK,
        })
        self.assertEqual(post.call_args.args[0], "https://hooks.slack.com/services/T0/B0/real")

    def test_typed_secret_is_used_as_entered(self, post):
        row = self._slack()
        self.client.post("/api/connections/test", json={
            "id": row.id, "type": "notification", "subtype": "notification-slack",
            "host": "https://hooks.slack.com", "password": "/services/T0/B0/new",
        })
        self.assertEqual(post.call_args.args[0], "https://hooks.slack.com/services/T0/B0/new")

    def test_mask_without_a_saved_connection_is_a_validation_error(self, post):
        r = self.client.post("/api/connections/test", json={
            "type": "notification", "subtype": "notification-slack",
            "host": "https://hooks.slack.com", "password": self.MASK,
        })
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["success"])
        self.assertIn("password", r.get_json()["message"])
        post.assert_not_called()

    def test_missing_host_reports_the_validation_message(self, post):
        r = self.client.post("/api/connections/test", json={
            "type": "notification", "subtype": "notification-gchat", "password": "/v1/spaces/x",
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("host", r.get_json()["message"])
        self.assertNotEqual(r.get_json()["message"], "Delivery failed")

    def test_delivery_failure_reports_the_http_error(self, post):
        post.return_value = _Response(404, "no_service")
        r = self.client.post("/api/connections/test", json={
            "type": "notification", "subtype": "notification-slack",
            "host": "https://hooks.slack.com", "password": "/services/T0/B0/gone",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["message"], "no_service")
        self.assertEqual(r.get_json()["httpStatus"], 404)
