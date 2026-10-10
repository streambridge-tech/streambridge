"""Unit tests for orchestrator.deploy_pipeline with a fake backend + fake DB."""
import unittest
from unittest.mock import patch

from app.models.connector_config import ConnectorConfig
from app.models.pipeline import Pipeline
from app.services.connect import orchestrator
from tests.unit.yaml_builder._fixtures import (
    DEFAULT_CONNECTIONS, DEFAULT_PLUGINS, PLACEHOLDER_PLUGINS, FakeConnection, FakeDB,
    build, mysql_source_yaml, postgres_source_yaml,
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


class ConnectionLayeringTests(unittest.TestCase):
    """Deployed config layers plugin base < connection < YAML config.

    The plugins mirror the seeds: "" / "*******" placeholders and real defaults
    such as database.port that a connection must be able to override.
    """

    def _connections(self, **configs):
        configs = {"kafka_connect_dev": {"url": "http://kc.local:8083"}, **configs}
        connections = []
        for c in DEFAULT_CONNECTIONS:
            conn = FakeConnection(c.name)
            conn.config = configs.get(c.name, {})
            connections.append(conn)
        return connections

    def _deploy(self, raw, connections):
        db = FakeDB(list(PLACEHOLDER_PLUGINS), connections)
        build_result = build(raw, db=db)
        self.assertTrue(build_result["ok"], msg=build_result.get("logs"))
        backend = FakeBackend()
        with patch.object(orchestrator, "get_backend", _patch_backend(backend)):
            result = orchestrator.deploy_pipeline(
                raw, "dev", build_result, db,
                poll_timeout=0, poll_interval=0, sleep=lambda _s: None,
            )
        self.assertTrue(result["ok"], msg=result["logs"])
        return dict(backend.deploys)

    def test_connection_values_replace_empty_plugin_placeholders(self):
        deployed = self._deploy(
            postgres_source_yaml(VALID_PG_CONFIG),
            self._connections(
                postgres_dev={
                    "database.hostname": "pg.local",
                    "database.user": "dbz",
                    "database.password": "secret",
                    "database.dbname": "ecommerce",
                },
                s3_dev={"s3.region": "eu-west-1", "s3.bucket.name": "lake", "flush.size": "10"},
            ),
        )
        src = deployed["pg-to-s3-source"]
        self.assertEqual(src["database.hostname"], "pg.local")
        self.assertEqual(src["database.user"], "dbz")
        self.assertEqual(src["database.password"], "secret")
        self.assertEqual(src["database.dbname"], "ecommerce")
        snk = deployed["pg-to-s3-sink"]
        self.assertEqual(snk["s3.region"], "eu-west-1")
        self.assertEqual(snk["s3.bucket.name"], "lake")
        # connection values also beat real plugin defaults
        self.assertEqual(snk["flush.size"], "10")

    def test_connection_values_replace_masked_plugin_placeholders(self):
        deployed = self._deploy(
            mysql_source_yaml(
                "    database.server.name: ecommerce\n"
                "    table.include.list: ecommerce.orders"
            ),
            self._connections(
                mysql_dev={
                    "database.hostname": "mysql.local",
                    "database.user": "debezium",
                    "database.password": "dbz",
                },
            ),
        )
        src = deployed["mysql-to-s3-source"]
        self.assertEqual(src["database.hostname"], "mysql.local")
        self.assertEqual(src["database.user"], "debezium")
        self.assertEqual(src["database.password"], "dbz")

    def test_connection_port_beats_the_plugin_default_port(self):
        raw = mysql_source_yaml(
            "    database.server.name: ecommerce\n"
            "    table.include.list: ecommerce.orders"
        )
        deployed = self._deploy(raw, self._connections(mysql_dev={"database.port": "3307"}))
        self.assertEqual(deployed["mysql-to-s3-source"]["database.port"], "3307")

    def test_plugin_default_is_kept_when_the_connection_lacks_the_key(self):
        deployed = self._deploy(postgres_source_yaml(VALID_PG_CONFIG), self._connections())
        self.assertEqual(deployed["pg-to-s3-source"]["database.port"], "5432")

    def test_yaml_port_beats_the_connection_port(self):
        raw = postgres_source_yaml(VALID_PG_CONFIG + "\n    database.port: \"6543\"")
        deployed = self._deploy(raw, self._connections(postgres_dev={"database.port": "5433"}))
        self.assertEqual(deployed["pg-to-s3-source"]["database.port"], "6543")

    def test_connector_name_is_never_overridden_by_a_connection(self):
        deployed = self._deploy(
            postgres_source_yaml(VALID_PG_CONFIG), self._connections(postgres_dev={"name": "other"}),
        )
        self.assertIn("pg-to-s3-source", deployed)
        self.assertEqual(deployed["pg-to-s3-source"]["name"], "pg-to-s3-source")

    def test_yaml_values_still_win_over_the_connection(self):
        raw = postgres_source_yaml(VALID_PG_CONFIG + "\n    database.dbname: from_yaml")
        deployed = self._deploy(raw, self._connections(postgres_dev={"database.dbname": "from_connection"}))
        self.assertEqual(deployed["pg-to-s3-source"]["database.dbname"], "from_yaml")


if __name__ == "__main__":
    unittest.main()
