"""MySQL schema tests — locks Debezium key + pymysql kwarg spelling."""
import unittest

from app.connectors.schemas import build_kc_config, build_test_kwargs
from app.connectors.schemas.mysql import MYSQL_SCHEMA


class TestMysqlSchemaIdentity(unittest.TestCase):

    def test_subtype(self):
        self.assertEqual(MYSQL_SCHEMA.subtype, "mysql")

    def test_required_field_ids(self):
        ids = {f.id for f in MYSQL_SCHEMA.required_fields()}
        self.assertEqual(ids, {"host", "port", "database", "username", "password"})

    def test_field_ids_are_unique(self):
        ids = [f.id for f in MYSQL_SCHEMA.fields]
        self.assertEqual(len(ids), len(set(ids)))

    def test_kc_keys_are_unique(self):
        kc_keys = [f.kc_key for f in MYSQL_SCHEMA.fields if f.kc_key]
        self.assertEqual(len(kc_keys), len(set(kc_keys)))

    def test_debezium_key_spelling(self):
        expected = {
            "host":                      "database.hostname",
            "port":                      "database.port",
            "database":                  "database.include.list",
            "username":                  "database.user",
            "password":                  "database.password",
            "ssl_mode":                  "database.ssl.mode",
            "ssl_truststore":            "database.ssl.truststore",
            "server_id":                 "database.server.id",
            "connect_timeout_ms":        "database.connect.timeout.ms",
            "allow_public_key_retrieval":"database.allowPublicKeyRetrieval",
        }
        for field_id, kc_key in expected.items():
            f = MYSQL_SCHEMA.get(field_id)
            self.assertIsNotNone(f, f"missing field: {field_id}")
            self.assertEqual(f.kc_key, kc_key, f"kc_key mismatch on {field_id}")

    def test_pymysql_kwarg_spelling(self):
        expected = {
            "host":     "host",
            "port":     "port",
            "username": "user",
            "password": "password",
            # database intentionally has no test_key (Debezium filter, not real DB)
            "connect_timeout_ms": "connect_timeout",
        }
        for field_id, test_key in expected.items():
            self.assertEqual(MYSQL_SCHEMA.get(field_id).test_key, test_key)

    def test_database_field_not_leaked_to_test(self):
        self.assertIsNone(MYSQL_SCHEMA.get("database").test_key)

    def test_password_is_secret(self):
        self.assertTrue(MYSQL_SCHEMA.get("password").secret)


class TestMysqlConfigBuild(unittest.TestCase):

    def _form(self, **overrides):
        base = {"host": "db.internal", "port": "3306", "database": "orders",
                "username": "cdc", "password": "s3cret"}
        base.update(overrides)
        return base

    def test_required_flat_map(self):
        cfg = build_kc_config(MYSQL_SCHEMA, self._form())
        self.assertEqual(cfg["database.hostname"], "db.internal")
        self.assertEqual(cfg["database.port"], 3306)
        self.assertEqual(cfg["database.include.list"], "orders")
        self.assertEqual(cfg["database.user"], "cdc")
        self.assertEqual(cfg["database.password"], "s3cret")

    def test_connect_timeout_ms_to_sec_transform(self):
        form = self._form(connect_timeout_ms=45000)
        cfg = build_kc_config(MYSQL_SCHEMA, form)
        self.assertEqual(cfg["database.connect.timeout.ms"], 45000)  # KC keeps ms
        kwargs = build_test_kwargs(MYSQL_SCHEMA, cfg)
        self.assertEqual(kwargs["connect_timeout"], 45)  # pymysql wants seconds

    def test_allow_public_key_retrieval_bool_cast(self):
        form = self._form(allow_public_key_retrieval="true")
        cfg = build_kc_config(MYSQL_SCHEMA, form)
        self.assertEqual(cfg["database.allowPublicKeyRetrieval"], "true")

    def test_test_kwargs_excludes_database(self):
        cfg = build_kc_config(MYSQL_SCHEMA, self._form())
        kwargs = build_test_kwargs(MYSQL_SCHEMA, cfg)
        self.assertNotIn("database", kwargs)


if __name__ == "__main__":
    unittest.main()
