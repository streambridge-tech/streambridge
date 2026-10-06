"""Integration tests for the POST /api/pipelines/deploy Flask route.

The orchestrator and backends are already covered by unit tests. These tests
lock down the route wiring: input parsing, status codes, response body shape,
and the alert-extraction side effect after a successful deploy.
"""
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.routes.pipelines_api import pipelines_api


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(pipelines_api)
    return app.test_client()


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


if __name__ == "__main__":
    unittest.main()
