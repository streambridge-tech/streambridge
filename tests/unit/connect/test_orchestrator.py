"""Unit tests for orchestrator.deploy_pipeline with a fake backend + fake DB."""
import unittest

from app.models.connector_config import ConnectorConfig
from app.models.pipeline import Pipeline
from app.services.connect import orchestrator
from tests.unit.yaml_builder._fixtures import (
    DEFAULT_CONNECTIONS, DEFAULT_PLUGINS, FakeConnection, FakeDB,
    build, postgres_source_yaml,
)


class FakeBackend:
    """DeploymentBackend stand-in. Records deploys and replays queued states per name."""

    def __init__(self, raise_on_deploy=None, states=None):
        self.deploys: list[tuple[str, dict]] = []
        self._states = states or {}
        self._raise_on_deploy = raise_on_deploy or set()

    def deploy(self, name, config):
        self.deploys.append((name, dict(config)))
        if name in self._raise_on_deploy:
            raise RuntimeError(f"deploy failure for {name}")

    def poll_status(self, name):
        seq = self._states.get(name, ["RUNNING"])
        return seq.pop(0) if len(seq) > 1 else seq[0]


def _patch_backend(backend):
    """Return a get_backend replacement that always returns the given backend."""
    return lambda kc_config: backend


VALID_PG_CONFIG = (
    "    database.server.name: ecommerce\n"
    "    table.include.list: public.orders"
)


class DeployPipelineTests(unittest.TestCase):

    def setUp(self):
        self.raw = postgres_source_yaml(VALID_PG_CONFIG)
        # Connections list needs a Kafka Connect entry with a proper config
        kc = FakeConnection("kafka_connect_dev")
        kc.config = {"mode": "rest", "url": "http://kc.local:8083"}
        self.connections = [
            c if c.name != "kafka_connect_dev" else kc
            for c in DEFAULT_CONNECTIONS
        ]
        for c in self.connections:
            if not hasattr(c, "config"):
                c.config = {}
        # Give the postgres_dev connection some credentials so injection is testable
        for c in self.connections:
            if c.name == "postgres_dev":
                c.config = {
                    "database.hostname": "pg.local",
                    "database.port": "5432",
                    "database.user": "dbz",
                    "database.password": "dbz",
                    "database.dbname": "ecommerce",
                }
        self.db = FakeDB(list(DEFAULT_PLUGINS), self.connections)
        self.build_result = build(self.raw, db=self.db)
        self.assertTrue(self.build_result["ok"], msg=self.build_result.get("logs"))

    def _deploy(self, backend, **kwargs):
        original = orchestrator.get_backend
        orchestrator.get_backend = _patch_backend(backend)
        try:
            return orchestrator.deploy_pipeline(
                self.raw, "dev", self.build_result, self.db,
                poll_timeout=0, poll_interval=0, sleep=lambda _s: None, **kwargs,
            )
        finally:
            orchestrator.get_backend = original

    def test_full_success_persists_pipeline_and_connectors(self):
        backend = FakeBackend()
        result = self._deploy(backend)
        self.assertTrue(result["ok"], msg=result["logs"])

        deploy_names = [n for n, _ in backend.deploys]
        self.assertEqual(deploy_names, ["pg-to-s3-source", "pg-to-s3-sink"])

        pipelines = [r for r in self.db.added if isinstance(r, Pipeline)]
        connectors = [r for r in self.db.added if isinstance(r, ConnectorConfig)]
        self.assertEqual(len(pipelines), 1)
        self.assertEqual(pipelines[0].status, "running")
        self.assertEqual({c.type for c in connectors}, {"source", "sink"})
        self.assertEqual({c.plugin_name for c in connectors}, {"postgres-json", "s3-json"})

    def test_source_deploy_exception_marks_failed(self):
        backend = FakeBackend(raise_on_deploy={"pg-to-s3-source"})
        result = self._deploy(backend)
        self.assertFalse(result["ok"])
        pipelines = [r for r in self.db.added if isinstance(r, Pipeline)]
        self.assertEqual(pipelines[0].status, "failed")
        connectors = [r for r in self.db.added if isinstance(r, ConnectorConfig)]
        self.assertEqual(connectors, [])

    def test_source_not_running_stops_before_sink(self):
        backend = FakeBackend(states={"pg-to-s3-source": ["FAILED"]})
        result = self._deploy(backend)
        self.assertFalse(result["ok"])
        deploy_names = [n for n, _ in backend.deploys]
        self.assertEqual(deploy_names, ["pg-to-s3-source"])
        pipelines = [r for r in self.db.added if isinstance(r, Pipeline)]
        self.assertEqual(pipelines[0].status, "failed")

    def test_sink_failure_after_source_success(self):
        backend = FakeBackend(states={
            "pg-to-s3-source": ["RUNNING"],
            "pg-to-s3-sink":   ["FAILED"],
        })
        result = self._deploy(backend)
        self.assertFalse(result["ok"])
        deploy_names = [n for n, _ in backend.deploys]
        self.assertEqual(deploy_names, ["pg-to-s3-source", "pg-to-s3-sink"])
        pipelines = [r for r in self.db.added if isinstance(r, Pipeline)]
        self.assertEqual(pipelines[0].status, "failed")

    def test_missing_kafka_connect_connection_row(self):
        self.connections = [c for c in self.connections if c.name != "kafka_connect_dev"]
        self.db = FakeDB(list(DEFAULT_PLUGINS), self.connections)
        self.build_result = build(self.raw, db=FakeDB(list(DEFAULT_PLUGINS), self.connections + [FakeConnection("kafka_connect_dev")]))
        result = self._deploy(FakeBackend())
        self.assertFalse(result["ok"])
        error_texts = [log["text"] for log in result["logs"] if log["level"] == "error"]
        self.assertTrue(any("kafka_connect connection 'kafka_connect_dev' not found" in t for t in error_texts))

    def test_credentials_injected_from_connection(self):
        backend = FakeBackend()
        self._deploy(backend)
        src_name, src_deployed = backend.deploys[0]
        self.assertEqual(src_name, "pg-to-s3-source")
        # postgres_dev connection provided these; YAML did not override them
        self.assertEqual(src_deployed.get("database.hostname"), "pg.local")
        self.assertEqual(src_deployed.get("database.port"), "5432")
        # YAML-provided value must win over connection value
        self.assertEqual(src_deployed.get("database.server.name"), "ecommerce")


if __name__ == "__main__":
    unittest.main()
