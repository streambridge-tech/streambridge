"""Integration tests for the POST /api/pipelines/deploy Flask route.

The orchestrator and backends are already covered by unit tests. These tests
lock down the route wiring: input parsing, status codes, response body shape,
and the alert-extraction side effect after a successful deploy.
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.alert import Alert
from app.models.connector_config import ConnectorConfig
from app.models.pipeline import Pipeline
from app.routes.pipelines_api import _extract_alerts_from_yaml, pipelines_api
from app.utils.db import Base


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(pipelines_api)
    return app.test_client()


def _post_json_text(client, url, body):
    """POST body serialised as-is, so None is sent as a literal JSON null."""
    return client.post(url, data=json.dumps(body), content_type="application/json")


ALERT_YAML = """pipeline:
  name: pg-to-s3

source:
  type: postgres
  connector_name: pg-to-s3-source
  config:
    table.include.list: public.orders
    connection.attempts: 9
  alert:
    type: slack
    channel_name: ops
    severity: critical
    message: source is down
    attempts: 5

sink:
  type: s3
  connector_name: pg-to-s3-sink
  config:
    topics.regex: ecommerce.public.*
    connection.attempts: 7
  alert:
    type: gchat
    channel_name: data
"""


class ExtractAlertsTests(unittest.TestCase):

    def _alerts(self, raw=ALERT_YAML):
        alerts = _extract_alerts_from_yaml(raw, "pid", "pg-to-s3", "pg-to-s3-source", "pg-to-s3-sink")
        return {a.connector_type: a for a in alerts}

    def test_channel_type_comes_from_the_alert_block(self):
        alerts = self._alerts()
        self.assertEqual(alerts["source"].channel_type, "slack")
        self.assertEqual(alerts["sink"].channel_type, "gchat")

    def test_alert_fields_come_from_the_alert_block(self):
        source = self._alerts()["source"]
        self.assertEqual(source.channel_name, "ops")
        self.assertEqual(source.severity, "critical")
        self.assertEqual(source.message, "source is down")
        self.assertEqual(source.attempts, 5)

    def test_attempts_outside_the_alert_block_are_ignored(self):
        self.assertEqual(self._alerts()["sink"].attempts, 3)

    def test_section_without_alert_block_has_no_alert(self):
        raw = ALERT_YAML.replace("  alert:\n    type: gchat\n    channel_name: data\n", "")
        self.assertEqual(set(self._alerts(raw)), {"source"})


BAD_ATTEMPTS_YAML = ALERT_YAML.replace("attempts: 5", "attempts: three")


class DeployRouteTests(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()

        self.session_patch = patch("app.routes.pipelines_api.SessionLocal")
        self.build_patch   = patch("app.routes.pipelines_api.build_pipeline")
        self.deploy_patch  = patch("app.routes.pipelines_api.deploy_pipeline")
        self.alerts_patch  = patch("app.routes.pipelines_api._extract_alerts_from_yaml", return_value=[])

        self.mock_session = self.session_patch.start()
        self.mock_build   = self.build_patch.start()
        self.mock_deploy  = self.deploy_patch.start()
        self.mock_alerts  = self.alerts_patch.start()

        self.fake_db = MagicMock(name="db")
        self.mock_session.return_value.__enter__.return_value = self.fake_db
        self.mock_session.return_value.__exit__.return_value  = False

        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.build_patch.stop)
        self.addCleanup(self.deploy_patch.stop)
        self.addCleanup(self.alerts_patch.stop)

    def _post(self, body):
        return self.client.post("/api/pipelines/deploy", json=body)

    def test_build_failure_returns_422_and_skips_deploy(self):
        self.mock_build.return_value = {
            "ok": False,
            "logs": [{"level": "error", "text": "bad yaml"}],
        }
        resp = self._post({"yamlRaw": "irrelevant", "env": "dev"})
        self.assertEqual(resp.status_code, 422)
        payload = resp.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["pipelineId"], None)
        self.assertEqual(payload["connectors"], [])
        self.mock_deploy.assert_not_called()

    def test_deploy_failure_returns_422(self):
        self.mock_build.return_value = {
            "ok": True,
            "logs": [],
            "meta": {"name": "pg-to-s3"},
        }
        self.mock_deploy.return_value = {
            "ok": False,
            "logs": [{"level": "error", "text": "source not RUNNING"}],
            "pipelineId": 42,
            "connectors": [{"name": "pg-to-s3-source", "type": "source", "status": "FAILED"}],
        }
        resp = self._post({"yamlRaw": "y", "env": "dev"})
        self.assertEqual(resp.status_code, 422)
        payload = resp.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["pipelineId"], 42)

    def test_deploy_success_returns_200_and_extracts_alerts(self):
        self.mock_build.return_value = {
            "ok": True,
            "logs": [],
            "meta": {"name": "pg-to-s3"},
        }
        self.mock_deploy.return_value = {
            "ok": True,
            "logs": [{"level": "success", "text": "pipeline running"}],
            "pipelineId": 7,
            "connectors": [
                {"name": "pg-to-s3-source", "type": "source", "status": "RUNNING"},
                {"name": "pg-to-s3-sink",   "type": "sink",   "status": "RUNNING"},
            ],
        }

        fake_alert = MagicMock(name="alert")
        self.mock_alerts.return_value = [fake_alert]

        resp = self._post({"yamlRaw": "y", "env": "dev"})

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["pipelineId"], 7)
        self.assertEqual(len(payload["connectors"]), 2)

        self.mock_alerts.assert_called_once_with(
            "y", 7, "pg-to-s3", "pg-to-s3-source", "pg-to-s3-sink"
        )
        self.fake_db.add.assert_called_with(fake_alert)
        self.fake_db.commit.assert_called()

    def test_non_numeric_alert_attempts_is_rejected_before_deploying(self):
        self.mock_build.return_value = {"ok": True, "logs": [], "meta": {"name": "pg-to-s3"}}
        resp = self._post({"yamlRaw": BAD_ATTEMPTS_YAML, "env": "dev"})
        self.assertEqual(resp.status_code, 400)
        error = resp.get_json()["error"]
        self.assertIn("source.alert.attempts", error)
        self.assertIn("three", error)
        self.mock_deploy.assert_not_called()

    def test_non_object_body_is_rejected(self):
        for body in (None, [], "yaml"):
            with self.subTest(body=body):
                resp = _post_json_text(self.client, "/api/pipelines/deploy", body)
                self.assertEqual(resp.status_code, 400)
                self.assertIn("error", resp.get_json())
        self.mock_build.assert_not_called()
        self.mock_deploy.assert_not_called()


class CreatePipelineRouteTests(unittest.TestCase):

    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine, tables=[Pipeline.__table__, ConnectorConfig.__table__, Alert.__table__],
        )
        self.db = sessionmaker(bind=engine)()
        self.addCleanup(self.db.close)
        self.client = _make_client()
        self.session_patch = patch("app.routes.pipelines_api.SessionLocal")
        mock_session = self.session_patch.start()
        mock_session.return_value.__enter__.return_value = self.db
        mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)

    def _post(self, body):
        return self.client.post("/api/pipelines", json=body)

    def _valid_body(self, **overrides):
        body = {
            "name": "pg-to-s3",
            "env": "dev",
            "yamlRaw": ALERT_YAML,
            "connectors": [
                {"connectorName": "pg-to-s3-source", "type": "source", "pluginName": "postgres-json"},
                {"connectorName": "pg-to-s3-sink", "type": "sink", "pluginName": "s3-json"},
            ],
        }
        body.update(overrides)
        return body

    def _assert_rejected(self, body, needle):
        resp = _post_json_text(self.client, "/api/pipelines", body)
        self.assertEqual(resp.status_code, 400, msg=resp.get_data(as_text=True))
        self.assertIn(needle, resp.get_json()["error"])
        self.assertEqual(self.db.query(Pipeline).count(), 0)

    def test_valid_body_creates_pipeline_connectors_and_alerts(self):
        resp = self._post(self._valid_body())
        self.assertEqual(resp.status_code, 201, msg=resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["name"], "pg-to-s3")
        self.assertEqual(self.db.query(ConnectorConfig).count(), 2)
        channels = {a.connector_type: a.channel_type for a in self.db.query(Alert).all()}
        self.assertEqual(channels, {"source": "slack", "sink": "gchat"})

    def test_non_object_body_is_rejected(self):
        for body in (None, [], ["pg-to-s3"], 5):
            with self.subTest(body=body):
                self._assert_rejected(body, "JSON object")

    def test_missing_name_is_rejected(self):
        body = self._valid_body()
        del body["name"]
        self._assert_rejected(body, "name")
        self._assert_rejected(self._valid_body(name=""), "name")
        self._assert_rejected(self._valid_body(name=None), "name")

    def test_connectors_must_be_a_list_of_objects(self):
        self._assert_rejected(self._valid_body(connectors={"type": "source"}), "connectors")
        self._assert_rejected(self._valid_body(connectors=["pg-to-s3-source"]), "connectors[0]")

    def test_connector_missing_name_or_type_is_rejected(self):
        self._assert_rejected(self._valid_body(connectors=[{"type": "source"}]), "connectors[0].connectorName")
        self._assert_rejected(
            self._valid_body(connectors=[{"connectorName": "pg-to-s3-source"}]), "connectors[0].type",
        )

    def test_non_numeric_alert_attempts_is_rejected(self):
        self._assert_rejected(self._valid_body(yamlRaw=BAD_ATTEMPTS_YAML), "source.alert.attempts")

    def test_patch_with_non_object_body_is_rejected(self):
        self.assertEqual(self._post(self._valid_body()).status_code, 201)
        resp = self.client.patch("/api/pipelines/pg-to-s3", data="null", content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("JSON object", resp.get_json()["error"])


class PipelineByIdRouteTests(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()
        self.session_patch = patch("app.routes.pipelines_api.SessionLocal")
        self.mock_session = self.session_patch.start()
        self.fake_db = MagicMock(name="db")
        self.mock_session.return_value.__enter__.return_value = self.fake_db
        self.mock_session.return_value.__exit__.return_value  = False
        self.addCleanup(self.session_patch.stop)

    def _fake_pipeline(self, pipeline_id: str, name: str = "pg-to-s3"):
        pipeline = MagicMock(name=f"pipeline-{pipeline_id}")
        pipeline.id = pipeline_id
        pipeline.name = name
        pipeline.to_dict.return_value = {
            "id": pipeline_id, "name": name, "env": "dev", "status": "running",
            "yamlRaw": "raw", "yamlResolved": "resolved",
            "createdAt": "2026-09-11T00:00:00", "updatedAt": "2026-09-11T00:00:00",
        }
        return pipeline

    def _fake_connector(self, name: str, ctype: str):
        connector = MagicMock(name=f"connector-{name}")
        connector.connector_name = name
        connector.type = ctype
        connector.to_dict.return_value = {
            "connectorName": name, "type": ctype, "pluginName": f"{ctype}-plugin", "config": {},
        }
        return connector

    def test_get_pipeline_by_id_returns_pipeline_and_connectors(self):
        pipeline = self._fake_pipeline("abc-123")
        source   = self._fake_connector("pg-to-s3-source", "source")
        sink     = self._fake_connector("pg-to-s3-sink",   "sink")
        self.fake_db.get.return_value = pipeline
        self.fake_db.query.return_value.filter.return_value.all.return_value = [source, sink]

        resp = self.client.get("/api/pipelines/id/abc-123")

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload["id"], "abc-123")
        self.assertEqual(len(payload["connectors"]), 2)
        self.assertEqual({c["type"] for c in payload["connectors"]}, {"source", "sink"})

    def test_get_pipeline_by_id_returns_404_when_missing(self):
        self.fake_db.get.return_value = None
        resp = self.client.get("/api/pipelines/id/missing-uuid")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.get_json()["error"])


class ConnectorSampleRouteTests(unittest.TestCase):

    def setUp(self):
        self.client = _make_client()
        self.session_patch = patch("app.routes.pipelines_api.SessionLocal")
        self.mock_session = self.session_patch.start()
        self.fake_db = MagicMock(name="db")
        self.mock_session.return_value.__enter__.return_value = self.fake_db
        self.mock_session.return_value.__exit__.return_value  = False
        self.addCleanup(self.session_patch.stop)

    def test_sample_returns_mock_rows_for_existing_connector(self):
        pipeline = MagicMock(); pipeline.id = "pipe-5"
        connector = MagicMock(); connector.type = "source"
        self.fake_db.get.return_value = pipeline
        self.fake_db.query.return_value.filter.return_value.first.return_value = connector

        resp = self.client.get("/api/pipelines/id/pipe-5/connectors/pg-to-s3-source/sample?limit=3")

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload["connector"], "pg-to-s3-source")
        self.assertEqual(payload["type"], "source")
        self.assertEqual(len(payload["rows"]), 3)
        self.assertIn("columns", payload)
        self.assertIn("meta", payload)

    def test_sample_returns_404_when_pipeline_missing(self):
        self.fake_db.get.return_value = None
        resp = self.client.get("/api/pipelines/id/nope/connectors/anything/sample")
        self.assertEqual(resp.status_code, 404)

    def test_sample_returns_404_when_connector_missing(self):
        pipeline = MagicMock(); pipeline.id = "pipe-5"
        self.fake_db.get.return_value = pipeline
        self.fake_db.query.return_value.filter.return_value.first.return_value = None
        resp = self.client.get("/api/pipelines/id/pipe-5/connectors/nope/sample")
        self.assertEqual(resp.status_code, 404)

    def _stub_source_connector(self):
        pipeline = MagicMock(); pipeline.id = "pipe-5"
        connector = MagicMock(); connector.type = "source"
        self.fake_db.get.return_value = pipeline
        self.fake_db.query.return_value.filter.return_value.first.return_value = connector

    def test_sample_limit_that_is_not_an_integer_uses_the_default(self):
        self._stub_source_connector()
        for limit in ("abc", "12.5"):
            with self.subTest(limit=limit):
                resp = self.client.get(f"/api/pipelines/id/pipe-5/connectors/src/sample?limit={limit}")
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(len(resp.get_json()["rows"]), 10)

    def test_sample_limit_is_clamped_to_at_least_one_row(self):
        self._stub_source_connector()
        resp = self.client.get("/api/pipelines/id/pipe-5/connectors/src/sample?limit=-4")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()["rows"]), 1)


if __name__ == "__main__":
    unittest.main()
