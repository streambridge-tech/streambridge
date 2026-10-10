import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import requests
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

    def test_changed_host_with_the_stored_secret_asks_for_the_secret(self, post):
        row = self._slack()
        r = self.client.post("/api/connections/test", json={
            "id": row.id, "type": "notification", "subtype": "notification-slack",
            "host": "https://attacker.example", "password": self.MASK,
        })
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["success"])
        self.assertIn("re-enter", r.get_json()["message"].lower())
        post.assert_not_called()

    def test_unchanged_host_with_a_trailing_slash_uses_the_stored_secret(self, post):
        row = self._slack()
        r = self.client.post("/api/connections/test", json={
            "id": row.id, "type": "notification", "subtype": "notification-slack",
            "host": "https://hooks.slack.com/", "password": self.MASK,
        })
        self.assertEqual(r.status_code, 200, r.get_json())
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


class NotificationErrorScrubTests(_ConnectionsApiCase):
    """A failed delivery's message never carries the webhook secret or URL path."""

    MASK = "\u2022" * 8
    REFUSED = (
        "HTTPConnectionPool(host='127.0.0.1', port=9): Max retries exceeded with url: {path} "
        "(Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x1>: "
        "Failed to establish a new connection: [Errno 61] Connection refused'))"
    )

    def _test(self, body, error):
        with patch("app.services.alerting.channels.slack.requests.post",
                   side_effect=requests.ConnectionError(error)):
            r = self.client.post("/api/connections/test", json={
                "type": "notification", "subtype": "notification-slack", **body})
        self.assertFalse(r.get_json()["success"])
        return r.get_json()["message"]

    def test_stored_secret_is_masked_in_a_transport_error(self):
        row = self._saved(name="alerts", type="notification", subtype="notification-slack",
                          config={"host": "http://127.0.0.1:9", "password": "/services/T0/B0/SECRET"})
        message = self._test({"id": row.id, "host": "http://127.0.0.1:9", "password": self.MASK},
                             self.REFUSED.format(path="/services/T0/B0/SECRET"))
        self.assertNotIn("SECRET", message)
        self.assertNotIn("/services", message)
        self.assertIn("Connection refused", message)

    def test_typed_secret_is_masked_in_a_transport_error(self):
        message = self._test({"host": "http://127.0.0.1:9", "password": "T0/B0/TYPED"},
                             self.REFUSED.format(path="/T0/B0/TYPED"))
        self.assertNotIn("TYPED", message)

    def test_url_paths_and_queries_are_stripped(self):
        message = self._test(
            {"host": "https://hooks.slack.com", "password": "/services/a b"},
            "SSLError for https://hooks.slack.com/services/a%20b?token=abc and url: /services/a%20b",
        )
        self.assertNotIn("a%20b", message)
        self.assertNotIn("token=abc", message)
        self.assertIn("https://hooks.slack.com", message)


@patch("app.services.alerting.channels.slack.requests.post")
class NotificationRetargetOnSaveTests(_ConnectionsApiCase):
    MASK = "\u2022" * 8

    def _slack(self):
        return self._saved(name="alerts", type="notification", subtype="notification-slack",
                           config={"host": "https://hooks.slack.com", "password": "/services/T0/B0/real"})

    def test_new_host_with_the_masked_secret_is_rejected(self, _post):
        row = self._slack()
        r = self.client.put(f"/api/connections/{row.id}", json={
            "host": "https://attacker.example", "password": self.MASK})
        self.assertEqual(r.status_code, 400)
        self.assertIn("re-enter", r.get_json()["error"].lower())
        self.db.refresh(row)
        self.assertEqual(row.config["host"], "https://hooks.slack.com")

    def test_new_host_without_a_secret_is_rejected(self, _post):
        row = self._slack()
        r = self.client.put(f"/api/connections/{row.id}", json={"config": {"host": "https://attacker.example"}})
        self.assertEqual(r.status_code, 400)

    def test_new_host_with_a_new_secret_is_saved(self, _post):
        row = self._slack()
        r = self.client.put(f"/api/connections/{row.id}", json={
            "host": "https://hooks.example", "password": "/services/T1/B1/new"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.db.refresh(row)
        self.assertEqual(row.config, {"host": "https://hooks.example", "password": "/services/T1/B1/new"})

    def test_unchanged_host_keeps_the_stored_secret(self, _post):
        row = self._slack()
        r = self.client.put(f"/api/connections/{row.id}", json={
            "name": "alerts-2", "host": "https://hooks.slack.com", "password": self.MASK})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.db.refresh(row)
        self.assertEqual(row.config["password"], "/services/T0/B0/real")


def _ok():
    resp = MagicMock()
    resp.status_code = 200
    return resp


@patch("app.connectors.infra.kafka_connect.requests.get", return_value=_ok())
class ConnectRetargetTests(_ConnectionsApiCase):
    """A stored Connect password only goes to the URL it was saved with."""

    MASK = "\u2022" * 8

    def _kc(self, **config):
        return self._saved(name="kc", type="connect", subtype="kafka-connect", config={
            "deployment": "connect", "auth_type": "basic", "url": "http://kc:8083",
            "username": "admin", "password": "kc-secret", **config})

    def _form(self, **fields):
        return {"type": "connect", "subtype": "kafka-connect", "deployment": "connect",
                "auth_type": "basic", "username": "admin", **fields}

    def test_save_with_a_new_url_and_masked_password_is_rejected(self, _get):
        row = self._kc()
        r = self.client.put(f"/api/connections/{row.id}", json=self._form(url="http://evil:8083", password=self.MASK))
        self.assertEqual(r.status_code, 400)
        self.assertIn("re-enter", r.get_json()["error"].lower())
        self.db.refresh(row)
        self.assertEqual(row.config["url"], "http://kc:8083")

    def test_save_with_the_same_url_keeps_the_password(self, _get):
        row = self._kc()
        r = self.client.put(f"/api/connections/{row.id}", json=self._form(url="http://kc:8083"))
        self.assertEqual(r.status_code, 200, r.get_json())
        self.db.refresh(row)
        self.assertEqual(row.config["password"], "kc-secret")

    def test_save_with_a_new_url_and_no_stored_secret_is_allowed(self, _get):
        row = self._saved(name="kc", type="connect", subtype="kafka-connect",
                          config={"deployment": "connect", "auth_type": "none", "url": "http://kc:8083"})
        r = self.client.put(f"/api/connections/{row.id}", json={
            "type": "connect", "subtype": "kafka-connect", "auth_type": "none", "url": "http://kc2:8083"})
        self.assertEqual(r.status_code, 200, r.get_json())

    def test_test_with_a_new_url_and_masked_password_is_rejected(self, get):
        row = self._kc()
        r = self.client.post("/api/connections/test", json=self._form(id=row.id, url="http://evil:8083",
                                                                      password=self.MASK))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["success"])
        get.assert_not_called()

    def test_test_with_a_new_url_and_typed_password_tests_what_was_typed(self, get):
        row = self._kc()
        r = self.client.post("/api/connections/test", json=self._form(id=row.id, url="http://kc2:8083",
                                                                      password="typed"))
        self.assertTrue(r.get_json()["success"], r.get_json())
        self.assertEqual(get.call_args.args[0], "http://kc2:8083/connectors")
        self.assertEqual(get.call_args.kwargs["auth"], ("admin", "typed"))

    def test_test_with_the_same_url_uses_the_saved_password(self, get):
        row = self._kc()
        body = {"id": row.id, "type": "connect", "subtype": "kafka-connect", **row.to_dict()["config"]}
        r = self.client.post("/api/connections/test", json=body)
        self.assertTrue(r.get_json()["success"], r.get_json())
        self.assertEqual(get.call_args.args[0], "http://kc:8083/connectors")
        self.assertEqual(get.call_args.kwargs["auth"], ("admin", "kc-secret"))


class StoredSecretDestinationTests(_ConnectionsApiCase):
    """Kafka and Schema Registry: a new destination with a masked secret needs the secret again."""

    MASK = "•" * 8
    KAFKA = {"bootstrap.servers": "kafka:9092", "security.protocol": "SASL_SSL", "sasl.mechanism": "PLAIN",
             "sasl.username": "app", "sasl.password": "kafka-secret"}
    REGISTRY = {"provider": "confluent", "url": "http://sr:8081", "auth_type": "basic",
                "username": "app", "password": "sr-secret"}

    def setUp(self):
        super().setUp()
        tests = [patch(f"app.connectors.infra.{module}.{cls}.test_connection",
                       return_value={"success": True, "message": "ok"})
                 for module, cls in (("kafka_broker", "KafkaBrokerConnector"),
                                     ("schema_registry", "SchemaRegistryConnector"))]
        self.kafka_test, self.registry_test = (t.start() for t in tests)
        for t in tests:
            self.addCleanup(t.stop)

    def _kafka(self):
        return self._saved(name="kafka", type="transport", subtype="kafka", config=dict(self.KAFKA))

    def _registry(self):
        return self._saved(name="sr", type="transport", subtype="schema-registry", config=dict(self.REGISTRY))

    def _kafka_form(self, row, servers, **extra):
        return {"id": row.id, "type": "transport", "subtype": "kafka", "bootstrap_servers": servers,
                "security_protocol": "SASL_SSL", "sasl_mechanism": "PLAIN", "username": "app",
                "password": self.MASK, **extra}

    def _registry_form(self, row, url, **extra):
        return {"id": row.id, "type": "transport", "subtype": "schema-registry", "provider": "confluent",
                "url": url, "auth_type": "basic", "username": "app", "password": self.MASK, **extra}

    def test_kafka_save_to_new_brokers_with_masked_password_is_rejected(self):
        row = self._kafka()
        r = self.client.put(f"/api/connections/{row.id}", json=self._kafka_form(row, "evil:9092"))
        self.assertEqual(r.status_code, 400)
        self.db.refresh(row)
        self.assertEqual(row.config["bootstrap.servers"], "kafka:9092")

    def test_kafka_save_to_the_same_brokers_keeps_the_password(self):
        row = self._kafka()
        r = self.client.put(f"/api/connections/{row.id}", json=self._kafka_form(row, "kafka:9092"))
        self.assertEqual(r.status_code, 200, r.get_json())
        self.db.refresh(row)
        self.assertEqual(row.config["sasl.password"], "kafka-secret")

    def test_kafka_save_to_new_brokers_with_a_new_password_is_saved(self):
        row = self._kafka()
        r = self.client.put(f"/api/connections/{row.id}",
                            json=self._kafka_form(row, "kafka2:9092", password="new-secret"))
        self.assertEqual(r.status_code, 200, r.get_json())

    def test_kafka_test_against_new_brokers_with_masked_password_is_rejected(self):
        row = self._kafka()
        r = self.client.post("/api/connections/test", json=self._kafka_form(row, "evil:9092"))
        self.assertEqual(r.status_code, 400)
        self.kafka_test.assert_not_called()

    def test_kafka_test_against_the_same_brokers_uses_the_saved_config(self):
        row = self._kafka()
        r = self.client.post("/api/connections/test", json=self._kafka_form(row, "kafka:9092"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.kafka_test.call_args.args[0]["sasl.password"], "kafka-secret")

    def test_registry_save_to_new_url_with_masked_password_is_rejected(self):
        row = self._registry()
        r = self.client.put(f"/api/connections/{row.id}", json=self._registry_form(row, "http://evil:8081"))
        self.assertEqual(r.status_code, 400)

    def test_registry_test_against_new_url_with_masked_password_is_rejected(self):
        row = self._registry()
        r = self.client.post("/api/connections/test", json=self._registry_form(row, "http://evil:8081"))
        self.assertEqual(r.status_code, 400)
        self.registry_test.assert_not_called()
