import unittest

from tests.unit.yaml_builder._fixtures import build, error_texts, postgres_source_yaml


class PostgresSourceCompileTests(unittest.TestCase):

    def _assert_failed_with(self, result: dict, needle: str):
        self.assertFalse(result["ok"], msg=f"expected failure; logs={result['logs']}")
        texts = error_texts(result)
        self.assertTrue(
            any(needle in t for t in texts),
            msg=f"expected an error containing {needle!r}, got: {texts}",
        )

    def test_valid_postgres_source_builds(self):
        raw = postgres_source_yaml(
            "    database.server.name: ecommerce\n"
            "    table.include.list: public.orders"
        )
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok build; logs={result['logs']}")

    def test_missing_table_include_list(self):
        raw = postgres_source_yaml("    database.server.name: ecommerce")
        self._assert_failed_with(build(raw), "table.include.list is required")

    def test_missing_database_server_name(self):
        raw = postgres_source_yaml("    table.include.list: public.orders")
        self._assert_failed_with(build(raw), "database.server.name is required")

    def test_no_db_connection_requires_credentials(self):
        raw = """pipeline:
  name: pg-to-s3
  env:
    dev:
      s3_conn: {{ conn('s3_dev') }}
      kafka_connect.connection: {{ conn('kafka_connect_dev') }}
      kafka_conn: {{ conn('kafka_dev') }}

source:
  type: postgres
  connector_name: pg-to-s3-source
  kafka.connection: {{ var('kafka_conn') }}
  config:
    database.server.name: ecommerce
    table.include.list: public.orders

sink:
  type: s3
  connector_name: pg-to-s3-sink
  storage.connection: {{ var('s3_conn') }}
  config:
    topics.regex: ecommerce.public.*
"""
        self._assert_failed_with(build(raw), "database.hostname is required")

    def test_no_kafka_connection_requires_bootstrap_servers(self):
        raw = """pipeline:
  name: pg-to-s3
  env:
    dev:
      pg_conn: {{ conn('postgres_dev') }}
      s3_conn: {{ conn('s3_dev') }}
      kafka_connect.connection: {{ conn('kafka_connect_dev') }}

source:
  type: postgres
  connector_name: pg-to-s3-source
  db.connection: {{ var('pg_conn') }}
  config:
    database.server.name: ecommerce
    table.include.list: public.orders

sink:
  type: s3
  connector_name: pg-to-s3-sink
  storage.connection: {{ var('s3_conn') }}
  config:
    topics.regex: ecommerce.public.*
"""
        self._assert_failed_with(build(raw), "kafka.connection is not set")

    def test_kafka_connection_present_skips_bootstrap_check(self):
        raw = postgres_source_yaml(VALID_PG_CONFIG_MINIMAL := (
            "    database.server.name: ecommerce\n"
            "    table.include.list: public.orders"
        ))
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")
        success_texts = [log["text"] for log in result["logs"] if log["level"] == "success"]
        self.assertTrue(
            any("kafka.connection present" in t for t in success_texts),
            msg=f"expected kafka.connection acknowledgement; got: {success_texts}",
        )


if __name__ == "__main__":
    unittest.main()
