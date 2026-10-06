"""Integration tests for the new alerts endpoints:
    POST /api/alerts/<id>/test     — delivers via SlackChannel/GChatChannel, persists attempt
    GET  /api/alerts/<id>/history  — returns recent attempts
"""
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.routes.alerts_api import alerts_api


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(alerts_api)
    return app.test_client()


class TestAlertTestEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

        self.session_patch = patch("app.routes.alerts_api.SessionLocal")
        self.deliver_patch = patch("app.routes.alerts_api.deliver_test")

        self.mock_session = self.session_patch.start()
        self.mock_deliver = self.deliver_patch.start()

        self.fake_db = MagicMock(name="db")
        self.mock_session.return_value.__enter__.return_value = self.fake_db
        self.mock_session.return_value.__exit__.return_value  = False

        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.deliver_patch.stop)

    def test_alert_missing_returns_404(self):
        self.fake_db.get.return_value = None
        r = self.client.post("/api/alerts/nope/test")
        self.assertEqual(r.status_code, 404)
        self.mock_deliver.assert_not_called()

    def test_no_connection_returns_404(self):
        self.fake_db.get.return_value = MagicMock(id="a-1")
        self.mock_deliver.return_value = ({"success": False, "error": "No slack notification connection found", "channels": []}, 404)
        r = self.client.post("/api/alerts/a-1/test")
        self.assertEqual(r.status_code, 404)
        self.assertIn("No slack notification connection found", r.get_json()["error"])

    def test_channel_unimplemented_returns_501(self):
        self.fake_db.get.return_value = MagicMock(id="a-1")
        self.mock_deliver.return_value = ({"success": False, "error": "not implemented", "channels": []}, 501)
        r = self.client.post("/api/alerts/a-1/test")
        self.assertEqual(r.status_code, 501)

    def test_delivery_success_returns_200(self):
        self.fake_db.get.return_value = MagicMock(id="a-1")
        self.mock_deliver.return_value = ({
            "success": True, "latencyMs": 143,
            "channel": {"subtype": "notification-slack", "name": "cdc-alerts", "id": 42},
            "channels": [{"name": "cdc-alerts", "success": True}],
        }, 200)
        r = self.client.post("/api/alerts/a-1/test")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["latencyMs"], 143)
        self.assertEqual(body["channel"]["subtype"], "notification-slack")

    def test_delivery_failure_returns_502(self):
        self.fake_db.get.return_value = MagicMock(id="a-1")
        self.mock_deliver.return_value = ({"success": False, "error": "invalid_payload"}, 502)
        r = self.client.post("/api/alerts/a-1/test")
        self.assertEqual(r.status_code, 502)
        self.assertFalse(r.get_json()["success"])


class TestAlertHistoryEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

        self.session_patch = patch("app.routes.alerts_api.SessionLocal")
        self.mock_session = self.session_patch.start()

        self.fake_db = MagicMock(name="db")
        self.mock_session.return_value.__enter__.return_value = self.fake_db
        self.mock_session.return_value.__exit__.return_value  = False

        self.addCleanup(self.session_patch.stop)

    def _stub_rows(self, rows, total=None):
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.offset.return_value = chain
        chain.limit.return_value = chain
        chain.all.return_value = rows
        chain.count.return_value = total if total is not None else len(rows)
        self.fake_db.query.return_value = chain
        return chain

    def test_returns_empty_page_when_no_history(self):
        self._stub_rows([])
        r = self.client.get("/api/alerts/a-1/history")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["items"], [])
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["page"], 1)

    def test_returns_serialized_rows_newest_first(self):
        row = MagicMock()
        row.to_dict.return_value = {"id": "x1", "success": True, "kind": "fire"}
        self._stub_rows([row], total=1)
        r = self.client.get("/api/alerts/a-1/history")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["items"], [{"id": "x1", "success": True, "kind": "fire", "connectionName": None}])
        self.assertEqual(body["total"], 1)

    def test_page_size_capped_at_100(self):
        chain = self._stub_rows([])
        self.client.get("/api/alerts/a-1/history?pageSize=9999")
        chain.limit.assert_called_once_with(100)

    def test_default_page_size_is_20(self):
        chain = self._stub_rows([])
        self.client.get("/api/alerts/a-1/history")
        chain.limit.assert_called_once_with(20)

    def test_page_uses_offset(self):
        chain = self._stub_rows([], total=45)
        self.client.get("/api/alerts/a-1/history?page=3&pageSize=10")
        chain.offset.assert_called_with(20)
        chain.limit.assert_called_with(10)


class TestAlertActiveAndCheckEvery(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.utils.db import Base
        from app.models.alert import Alert

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[Alert.__table__])
        self.db = sessionmaker(bind=engine)()
        app = Flask(__name__)
        app.register_blueprint(alerts_api)
        self.client = app.test_client()
        self.session_patch = patch("app.routes.alerts_api.SessionLocal")
        mock_session = self.session_patch.start()
        mock_session.return_value.__enter__.return_value = self.db
        mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.db.close)

    def test_create_persists_active_and_check_every(self):
        r = self.client.post("/api/alerts", json={
            "name": "orders · FAILED",
            "connectorName": "postgres-orders-src",
            "conditionValue": "FAILED",
            "channelType": "gchat",
            "channelName": "de-oncall-prod",
            "active": True,
            "checkEveryMin": 10,
        })
        self.assertEqual(r.status_code, 201)
        body = r.get_json()
        self.assertTrue(body["active"])
        self.assertEqual(body["checkEveryMin"], 10)

    def test_create_persists_action_and_paused_rule(self):
        r = self.client.post("/api/alerts", json={
            "name": "orders · PAUSED",
            "connectorName": "postgres-orders-src",
            "conditionValue": "PAUSED",
            "channelName": "de-oncall-prod",
            "action": "re-trigger",
            "checkEveryMin": 7,
        })
        self.assertEqual(r.status_code, 201)
        body = r.get_json()
        self.assertEqual(body["conditionValue"], "PAUSED")
        self.assertEqual(body["action"], "re-trigger")
        self.assertEqual(body["checkEveryMin"], 7)

    def test_create_rules_and_rejects_duplicate_connector(self):
        r = self.client.post("/api/alerts", json={
            "connectorName": "pg-src",
            "channelName": "de-oncall-prod",
            "rules": [
                {"rule": "FAILED", "action": "re-trigger"},
                {"rule": "PAUSED", "action": "notify"},
            ],
        })
        self.assertEqual(r.status_code, 201)
        body = r.get_json()
        self.assertEqual(body["rules"], [
            {"rule": "FAILED", "action": "re-trigger"},
            {"rule": "PAUSED", "action": "notify"},
        ])
        again = self.client.post("/api/alerts", json={
            "connectorName": "pg-src",
            "channelName": "de-oncall-prod",
            "conditionValue": "UNKNOWN",
        })
        self.assertEqual(again.status_code, 409)

    def test_paused_pause_rejected(self):
        r = self.client.post("/api/alerts", json={
            "connectorName": "pg-src",
            "channelName": "oncall",
            "rules": [{"rule": "PAUSED", "action": "pause"}],
        })
        self.assertEqual(r.status_code, 400)

    def test_create_binds_notebook_and_drops_pipeline(self):
        from app.models.connector_notebook import ConnectorNotebook

        ConnectorNotebook.__table__.create(self.db.get_bind())
        self.db.add(ConnectorNotebook(
            id="nb-1",
            name="orders-src",
            connector_type="source",
            attached_cluster="kc-dev",
        ))
        self.db.commit()
        r = self.client.post("/api/alerts", json={
            "notebookId": "nb-1",
            "connectorName": "ignored",
            "pipelineId": "pipe-1",
            "pipelineName": "old-pipeline",
            "channelName": "oncall",
            "conditionValue": "FAILED",
            "checkEveryMin": 5,
        })
        self.assertEqual(r.status_code, 201)
        body = r.get_json()
        self.assertEqual(body["notebookId"], "nb-1")
        self.assertEqual(body["connectorName"], "orders-src")
        self.assertEqual(body["connectorType"], "source")
        self.assertIsNone(body["pipelineId"])
        self.assertIsNone(body["pipelineName"])

    def test_create_missing_notebook_returns_404(self):
        from app.models.connector_notebook import ConnectorNotebook

        ConnectorNotebook.__table__.create(self.db.get_bind(), checkfirst=True)
        r = self.client.post("/api/alerts", json={
            "notebookId": "missing",
            "channelName": "oncall",
            "conditionValue": "FAILED",
        })
        self.assertEqual(r.status_code, 404)

    def test_patch_disables_alert_and_accepts_any_positive_interval(self):
        created = self.client.post("/api/alerts", json={
            "name": "orders · FAILED",
            "connectorName": "postgres-orders-src",
            "conditionValue": "FAILED",
            "channelName": "de-oncall-prod",
            "checkEveryMin": 5,
        }).get_json()
        r = self.client.patch(f"/api/alerts/{created['id']}", json={
            "active": False,
            "checkEveryMin": 7,
        })
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertFalse(body["active"])
        self.assertEqual(body["checkEveryMin"], 7)


if __name__ == "__main__":
    unittest.main()
