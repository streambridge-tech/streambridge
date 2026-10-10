import unittest

from tests.unit.yaml_builder._fixtures import (
    PLACEHOLDER_PLUGINS, build, error_texts, fake_db, mysql_source_yaml, postgres_source_yaml,
)


VALID_MYSQL_CONFIG = (
    "    database.server.name: ecommerce\n"
    "    table.include.list: ecommerce.orders"
)


def _texts(result, level):
    return [log["text"] for log in result["logs"] if log["level"] == level]


class MysqlTopicPrefixTests(unittest.TestCase):
    """The seeded mysql-json plugin ships topic.prefix as a "*******" placeholder."""

    def _build(self, raw):
        result = build(raw, db=fake_db(plugins=list(PLACEHOLDER_PLUGINS)))
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")
        return result

    def test_placeholder_topic_prefix_falls_back_to_connector_name(self):
        result = self._build(mysql_source_yaml(VALID_MYSQL_CONFIG))
        self.assertEqual(_texts(result, "warn"), [])
        self.assertIn("  → mysql-to-s3-source.ecommerce.orders", _texts(result, "success"))

    def test_placeholder_topic_prefix_is_replaced_by_connector_name(self):
        result = self._build(mysql_source_yaml(VALID_MYSQL_CONFIG))
        self.assertEqual(result["sourceConfig"].get("topic.prefix"), "mysql-to-s3-source")

    def test_empty_postgres_topic_prefix_is_replaced_by_connector_name(self):
        result = self._build(postgres_source_yaml(
            "    database.server.name: ecommerce\n"
            "    table.include.list: public.orders"
        ))
        self.assertEqual(result["sourceConfig"].get("topic.prefix"), "pg-to-s3-source")

    def test_missing_topic_prefix_is_set_to_connector_name(self):
        result = build(mysql_source_yaml(VALID_MYSQL_CONFIG))
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")
        self.assertEqual(result["sourceConfig"].get("topic.prefix"), "mysql-to-s3-source")

    def test_yaml_topic_prefix_replaces_the_placeholder(self):
        result = self._build(mysql_source_yaml(VALID_MYSQL_CONFIG + "\n    topic.prefix: shop"))
        self.assertEqual(result["sourceConfig"]["topic.prefix"], "shop")
        self.assertIn("  → shop.ecommerce.orders", _texts(result, "success"))

    def test_invalid_topic_prefix_warning_names_the_field_and_value(self):
        result = self._build(mysql_source_yaml(VALID_MYSQL_CONFIG + "\n    topic.prefix: bad/prefix"))
        warnings = _texts(result, "warn")
        self.assertTrue(any('topic.prefix "bad/prefix"' in w for w in warnings), msg=warnings)
        self.assertFalse(any("connector_name" in w for w in warnings), msg=warnings)

    def test_invalid_connector_name_warning_names_connector_name(self):
        raw = mysql_source_yaml(VALID_MYSQL_CONFIG).replace(
            "connector_name: mysql-to-s3-source", "connector_name: mysql:source",
        )
        warnings = _texts(self._build(raw), "warn")
        self.assertTrue(any('connector_name "mysql:source"' in w for w in warnings), msg=warnings)


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
