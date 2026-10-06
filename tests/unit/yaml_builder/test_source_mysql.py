import unittest

from tests.unit.yaml_builder._fixtures import build, error_texts, mysql_source_yaml


VALID_MYSQL_CONFIG = (
    "    database.server.name: ecommerce\n"
    "    table.include.list: ecommerce.orders"
)


class MysqlSourceCompileTests(unittest.TestCase):

    def _assert_failed_with(self, result, needle):
        self.assertFalse(result["ok"], msg=f"expected failure; logs={result['logs']}")
        texts = error_texts(result)
        self.assertTrue(
            any(needle in t for t in texts),
            msg=f"expected an error containing {needle!r}, got: {texts}",
        )

    def test_valid_mysql_source_builds(self):
        raw = mysql_source_yaml(VALID_MYSQL_CONFIG)
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")

    def test_missing_table_include_list(self):
        raw = mysql_source_yaml("    database.server.name: ecommerce")
        self._assert_failed_with(build(raw), "table.include.list is required")

    def test_missing_database_server_name(self):
        raw = mysql_source_yaml("    table.include.list: ecommerce.orders")
        self._assert_failed_with(build(raw), "database.server.name is required")

    def test_no_db_connection_requires_database_include_list(self):
        raw = """pipeline:
  name: mysql-to-s3
  env:
    dev:
      s3_conn: {{ conn('s3_dev') }}
      kafka_connect.connection: {{ conn('kafka_connect_dev') }}
      kafka_conn: {{ conn('kafka_dev') }}

source:
  type: mysql
  connector_name: mysql-to-s3-source
  kafka.connection: {{ var('kafka_conn') }}
  config:
    database.hostname: mysql.local
    database.port: 3306
    database.user: dbz
    database.password: dbz
    database.server.name: ecommerce
    table.include.list: ecommerce.orders

sink:
  type: s3
  connector_name: mysql-to-s3-sink
  storage.connection: {{ var('s3_conn') }}
  config:
    topics.regex: ecommerce.public.*
"""
        self._assert_failed_with(build(raw), "database.include.list is required")

    def test_no_kafka_connection_requires_schema_history_bootstrap(self):
        raw = """pipeline:
  name: mysql-to-s3
  env:
    dev:
      mysql_conn: {{ conn('mysql_dev') }}
      s3_conn: {{ conn('s3_dev') }}
      kafka_connect.connection: {{ conn('kafka_connect_dev') }}

source:
  type: mysql
  connector_name: mysql-to-s3-source
  db.connection: {{ var('mysql_conn') }}
  config:
    database.server.name: ecommerce
    table.include.list: ecommerce.orders

sink:
  type: s3
  connector_name: mysql-to-s3-sink
  storage.connection: {{ var('s3_conn') }}
  config:
    topics.regex: ecommerce.public.*
"""
        self._assert_failed_with(
            build(raw),
            "kafka.connection is not set",
        )


if __name__ == "__main__":
    unittest.main()
