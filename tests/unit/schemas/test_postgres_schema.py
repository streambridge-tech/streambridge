"""Postgres-specific schema tests.

Locks down the Debezium key spelling for every Postgres field so a typo
here would fail a test rather than break real deploys silently.
"""
import unittest

from app.connectors.schemas import build_kc_config, build_test_kwargs
from app.connectors.schemas.postgres import POSTGRES_SCHEMA


class TestPostgresSchemaIdentity(unittest.TestCase):

    def test_subtype(self):
        self.assertEqual(POSTGRES_SCHEMA.subtype, "postgres")

    def test_required_field_ids(self):
        ids = {f.id for f in POSTGRES_SCHEMA.required_fields()}
        self.assertEqual(ids, {"host", "port", "database", "username", "password"})

    def test_field_ids_are_unique(self):
        ids = [f.id for f in POSTGRES_SCHEMA.fields]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate ids in schema: {ids}")

    def test_kc_keys_are_unique(self):
        kc_keys = [f.kc_key for f in POSTGRES_SCHEMA.fields if f.kc_key]
        self.assertEqual(len(kc_keys), len(set(kc_keys)), f"duplicate kc_keys: {kc_keys}")

    def test_debezium_key_spelling(self):
        """Prevent a typo in a Debezium key from silently breaking deploys."""
        expected = {
            "host":               "database.hostname",
            "port":               "database.port",
            "database":           "database.dbname",
            "username":           "database.user",
            "password":           "database.password",
            "ssl_mode":           "database.sslmode",
            "ssl_root_cert":      "database.sslrootcert",
            "ssl_cert":           "database.sslcert",
            "ssl_key":            "database.sslkey",
            "application_name":   "database.applicationName",
            "connect_timeout_ms": "database.connectTimeoutMs",
            "tcp_keep_alive":     "database.tcpKeepAlive",
        }
        for field_id, kc_key in expected.items():
            f = POSTGRES_SCHEMA.get(field_id)
            self.assertIsNotNone(f, f"missing field: {field_id}")
            self.assertEqual(f.kc_key, kc_key, f"kc_key mismatch on {field_id}")

    def test_psycopg2_kwarg_spelling(self):
        """Prevent a typo in a psycopg2 kwarg from silently breaking test_connection."""
        expected = {
            "host":               "host",
            "port":               "port",
            "database":           "dbname",           # psycopg2 uses 'dbname' not 'database'
            "username":           "user",
            "password":           "password",
            "ssl_mode":           "sslmode",
            "ssl_root_cert":      "sslrootcert",
            "ssl_cert":           "sslcert",
            "ssl_key":            "sslkey",
            "application_name":   "application_name",
            "connect_timeout_ms": "connect_timeout",  # + unit conversion (ms → sec)
            "tcp_keep_alive":     "keepalives",       # psycopg2 uses 'keepalives' (int 0/1)
        }
        for field_id, test_key in expected.items():
            f = POSTGRES_SCHEMA.get(field_id)
            self.assertIsNotNone(f, f"missing field: {field_id}")
            self.assertEqual(f.test_key, test_key, f"test_key mismatch on {field_id}")

    def test_secrets_are_marked(self):
        self.assertTrue(POSTGRES_SCHEMA.get("password").secret)
        self.assertTrue(POSTGRES_SCHEMA.get("ssl_key").secret)
        # sanity — non-secret field
        self.assertFalse(POSTGRES_SCHEMA.get("host").secret)


class TestPostgresBuildKcConfig(unittest.TestCase):

    def test_typical_form_produces_debezium_config(self):
        form = {
            "host":     "db.internal",
            "port":     "5432",
            "database": "orders",
            "username": "cdc",
            "password": "hunter2",
        }
        cfg = build_kc_config(POSTGRES_SCHEMA, form)
        self.assertEqual(cfg["database.hostname"], "db.internal")
        self.assertEqual(cfg["database.port"],     5432)
        self.assertEqual(cfg["database.dbname"],   "orders")
        self.assertEqual(cfg["database.user"],     "cdc")
        self.assertEqual(cfg["database.password"], "hunter2")

    def test_advanced_ssl_fields_pass_through(self):
        form = {
            "host": "db.internal", "port": "5432", "database": "x",
            "username": "u", "password": "p",
            "ssl_mode": "verify-full",
            "ssl_root_cert": "/etc/ssl/ca.crt",
        }
        cfg = build_kc_config(POSTGRES_SCHEMA, form)
        self.assertEqual(cfg["database.sslmode"],     "verify-full")
        self.assertEqual(cfg["database.sslrootcert"], "/etc/ssl/ca.crt")

    def test_tcp_keep_alive_normalizes_boolean(self):
        cfg = build_kc_config(POSTGRES_SCHEMA, {"tcp_keep_alive": True})
        self.assertEqual(cfg["database.tcpKeepAlive"], "true")
        cfg = build_kc_config(POSTGRES_SCHEMA, {"tcp_keep_alive": "false"})
        self.assertEqual(cfg["database.tcpKeepAlive"], "false")


class TestPostgresBuildTestKwargs(unittest.TestCase):

    def test_maps_kc_config_to_psycopg2_kwargs(self):
        config = {
            "database.hostname": "db.internal",
            "database.port":     5432,
            "database.dbname":   "orders",
            "database.user":     "cdc",
            "database.password": "hunter2",
        }
        kwargs = build_test_kwargs(POSTGRES_SCHEMA, config)
        self.assertEqual(kwargs, {
            "host": "db.internal", "port": 5432, "dbname": "orders",
            "user": "cdc", "password": "hunter2",
        })

    def test_connect_timeout_ms_to_seconds(self):
        config = {"database.connectTimeoutMs": 10000}
        kwargs = build_test_kwargs(POSTGRES_SCHEMA, config)
        self.assertEqual(kwargs["connect_timeout"], 10)

    def test_connect_timeout_clamped_to_one_second(self):
        config = {"database.connectTimeoutMs": 500}  # 0.5 sec → would round to 0
        kwargs = build_test_kwargs(POSTGRES_SCHEMA, config)
        self.assertEqual(kwargs["connect_timeout"], 1)

    def test_tcp_keep_alive_converts_to_psycopg2_int(self):
        config = {"database.tcpKeepAlive": "true"}
        kwargs = build_test_kwargs(POSTGRES_SCHEMA, config)
        self.assertEqual(kwargs["keepalives"], 1)
        config = {"database.tcpKeepAlive": "false"}
        kwargs = build_test_kwargs(POSTGRES_SCHEMA, config)
        self.assertEqual(kwargs["keepalives"], 0)


if __name__ == "__main__":
    unittest.main()
