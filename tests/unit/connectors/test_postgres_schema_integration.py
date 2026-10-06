"""Integration tests for the refactored PostgresSourceConnector.

Confirms the schema-driven build_config produces the same shape the old
hardcoded mapping did, so no existing pipeline breaks.
"""
import unittest
from unittest.mock import MagicMock, patch

from app.connectors.source.postgres import PostgresSourceConnector


class TestPostgresBuildConfig(unittest.TestCase):

    def setUp(self):
        self.c = PostgresSourceConnector()

    def test_backward_compatible_shape(self):
        """The output config must contain the same Debezium keys the old
        hardcoded `_FORM_MAP` produced, so existing pipelines keep deploying."""
        form = {
            "host":     "db.internal",
            "port":     5432,
            "database": "orders",
            "username": "debezium",
            "password": "hunter2",
        }
        cfg = self.c.build_config(form=form, extra={})
        self.assertEqual(cfg["database.hostname"], "db.internal")
        self.assertEqual(cfg["database.port"],     5432)
        self.assertEqual(cfg["database.dbname"],   "orders")
        self.assertEqual(cfg["database.user"],     "debezium")
        self.assertEqual(cfg["database.password"], "hunter2")

    def test_extra_overrides_form(self):
        """extra: {} still wins on conflict, same semantics as before."""
        form = {"host": "form-host", "port": 5432, "database": "d", "username": "u", "password": "p"}
        extra = {"database.hostname": "override-host"}
        cfg = self.c.build_config(form=form, extra=extra)
        self.assertEqual(cfg["database.hostname"], "override-host")

    def test_extra_can_add_pipeline_scoped_keys(self):
        """Escape hatch: extra can inject keys the connection form does not expose
        (used by pipelines to add slot.name, topic.prefix, etc.)."""
        form = {"host": "h", "port": 5432, "database": "d", "username": "u", "password": "p"}
        extra = {"slot.name": "orders_slot", "topic.prefix": "inventory"}
        cfg = self.c.build_config(form=form, extra=extra)
        self.assertEqual(cfg["slot.name"],    "orders_slot")
        self.assertEqual(cfg["topic.prefix"], "inventory")

    def test_defaults_applied_when_form_omits(self):
        """Schema declares default=5432 for port; when form omits it the default lands."""
        form = {"host": "h", "database": "d", "username": "u", "password": "p"}
        cfg = self.c.build_config(form=form, extra={})
        self.assertEqual(cfg["database.port"], 5432)

    def test_ignores_empty_extra(self):
        """extra with empty-string values must not overwrite real values."""
        form = {"host": "h", "port": 5432, "database": "d", "username": "u", "password": "p"}
        extra = {"database.hostname": ""}
        cfg = self.c.build_config(form=form, extra=extra)
        self.assertEqual(cfg["database.hostname"], "h")


class TestPostgresTestConnection(unittest.TestCase):
    """Verifies test_connection unpacks the config into the correct psycopg2 kwargs.

    psycopg2 isn't a runtime dep in the test env, so we inject a fake module
    into sys.modules before the connector's inline `import psycopg2` runs.
    """

    def setUp(self):
        self.c = PostgresSourceConnector()
        self.fake_psycopg2 = MagicMock()
        self._sys_patch = patch.dict("sys.modules", {"psycopg2": self.fake_psycopg2})
        self._sys_patch.start()
        self.addCleanup(self._sys_patch.stop)

    def test_unpacks_config_via_schema(self):
        config = {
            "database.hostname": "db.internal",
            "database.port":     5432,
            "database.dbname":   "orders",
            "database.user":     "cdc",
            "database.password": "hunter2",
        }
        result = self.c.test_connection(config)

        self.assertTrue(result["success"])
        self.fake_psycopg2.connect.assert_called_once()
        _, kwargs = self.fake_psycopg2.connect.call_args
        self.assertEqual(kwargs["host"],     "db.internal")
        self.assertEqual(kwargs["port"],     5432)
        self.assertIsInstance(kwargs["port"], int)
        self.assertEqual(kwargs["dbname"],   "orders")
        self.assertEqual(kwargs["user"],     "cdc")
        self.assertEqual(kwargs["password"], "hunter2")

    def test_passes_ssl_mode_when_set(self):
        config = {
            "database.hostname": "h", "database.port": 5432, "database.dbname": "d",
            "database.user": "u", "database.password": "p",
            "database.sslmode": "require",
        }
        self.c.test_connection(config)
        _, kwargs = self.fake_psycopg2.connect.call_args
        self.assertEqual(kwargs["sslmode"], "require")

    def test_connect_timeout_ms_converted_to_seconds(self):
        config = {
            "database.hostname": "h", "database.port": 5432, "database.dbname": "d",
            "database.user": "u", "database.password": "p",
            "database.connectTimeoutMs": 12000,
        }
        self.c.test_connection(config)
        _, kwargs = self.fake_psycopg2.connect.call_args
        self.assertEqual(kwargs["connect_timeout"], 12)

    def test_default_timeout_when_none_configured(self):
        config = {
            "database.hostname": "h", "database.port": 5432, "database.dbname": "d",
            "database.user": "u", "database.password": "p",
        }
        self.c.test_connection(config)
        _, kwargs = self.fake_psycopg2.connect.call_args
        self.assertEqual(kwargs["connect_timeout"], 5)

    def test_returns_failure_on_exception(self):
        config = {
            "database.hostname": "h", "database.port": 5432, "database.dbname": "d",
            "database.user": "u", "database.password": "p",
        }
        self.fake_psycopg2.connect.side_effect = Exception("could not connect: bad host")
        result = self.c.test_connection(config)
        self.assertFalse(result["success"])
        self.assertIn("bad host", result["message"])


class TestConnectionToDictDualView(unittest.TestCase):
    """Verifies to_dict() surfaces both `config` (canonical) and `testKwargs` (computed)."""

    def test_to_dict_includes_test_kwargs_view(self):
        from datetime import datetime, timezone
        from app.models.connection import Connection

        c = Connection(
            id=1, name="pg-test", type="source", subtype="postgres", status="draft",
            used_in=[], config={
                "database.hostname": "db.local",
                "database.port":     5432,
                "database.dbname":   "orders",
                "database.user":     "cdc",
                "database.password": "hunter2",
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        d = c.to_dict()
        self.assertIn("config",       d)
        self.assertIn("deployConfig", d)
        self.assertIn("testKwargs",   d)

        self.assertEqual(d["config"],       d["deployConfig"])
        self.assertEqual(d["testKwargs"]["host"],   "db.local")
        self.assertEqual(d["testKwargs"]["dbname"], "orders")

    def test_secrets_are_masked_in_test_kwargs(self):
        """Passwords must never round-trip through the API in cleartext."""
        from datetime import datetime, timezone
        from app.models.connection import Connection

        c = Connection(
            id=1, name="pg-test", type="source", subtype="postgres", status="draft",
            used_in=[], config={
                "database.hostname": "db.local", "database.port": 5432,
                "database.dbname":   "orders",   "database.user": "cdc",
                "database.password": "hunter2",
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        d = c.to_dict()
        self.assertEqual(d["testKwargs"]["password"], "••••••••")

    def test_to_dict_without_views(self):
        from datetime import datetime, timezone
        from app.models.connection import Connection

        c = Connection(
            id=1, name="pg-test", type="source", subtype="postgres", status="draft",
            used_in=[], config={"database.hostname": "x"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        d = c.to_dict(include_views=False)
        self.assertNotIn("deployConfig", d)
        self.assertNotIn("testKwargs",   d)


if __name__ == "__main__":
    unittest.main()
