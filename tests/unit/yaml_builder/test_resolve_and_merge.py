import os
import unittest

from app.utils.yaml_builder import _section_config, resolve_yaml
from tests.unit.yaml_builder._fixtures import build, error_texts, fake_db, postgres_source_yaml


VALID_PG_CONFIG = (
    "    database.server.name: ecommerce\n"
    "    table.include.list: public.orders"
)


class ResolveYamlTests(unittest.TestCase):

    RAW = """pipeline:
  name: p
  vars:
    pg_host: localhost
source:
  config:
    host: {{ var('pg_host') }}
    spaced: {{var( "pg_host" )}}
    conn_ref: {{ conn('c1') }}
"""

    def test_var_expression_is_replaced_whole(self):
        out = resolve_yaml(self.RAW, "")
        self.assertIn("    host: localhost\n", out)
        self.assertIn("    spaced: localhost\n", out)

    def test_conn_expression_is_replaced_whole(self):
        out = resolve_yaml(self.RAW, "")
        self.assertIn("    conn_ref: [connection:c1]\n", out)

    def test_nothing_is_left_after_a_resolved_expression(self):
        self.assertNotRegex(resolve_yaml(self.RAW, ""), r"\)\s*\}\}")


class SectionConfigTests(unittest.TestCase):

    def test_source_without_config_does_not_take_the_sink_config(self):
        raw = """source:
  type: postgres
  connector_name: pg-source

sink:
  type: s3
  config:
    topics.regex: ecommerce.public.*
"""
        self.assertEqual(_section_config(raw, "source"), {})
        self.assertEqual(_section_config(raw, "sink"), {"topics.regex": "ecommerce.public.*"})

    def test_config_stops_at_the_next_sibling_key(self):
        raw = """source:
  type: postgres
  config:
    table.include.list: public.orders
  alert:
    type: slack
    channel_name: ops
"""
        self.assertEqual(_section_config(raw, "source"), {"table.include.list": "public.orders"})


class ResolveAndMergeTests(unittest.TestCase):

    def _assert_failed_with(self, result, needle):
        self.assertFalse(result["ok"], msg=f"expected failure; logs={result['logs']}")
        texts = error_texts(result)
        self.assertTrue(
            any(needle in t for t in texts),
            msg=f"expected an error containing {needle!r}, got: {texts}",
        )

    def test_valid_build_returns_merged_source_and_sink_config(self):
        raw = postgres_source_yaml(VALID_PG_CONFIG)
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")

        src = result["sourceConfig"]
        snk = result["sinkConfig"]

        # plugin base key
        self.assertEqual(src.get("connector.class"), "io.debezium.connector.postgresql.PostgresConnector")
        self.assertEqual(snk.get("connector.class"), "io.confluent.connect.s3.S3SinkConnector")

        # YAML config keys
        self.assertEqual(src.get("database.server.name"), "ecommerce")
        self.assertEqual(src.get("table.include.list"), "public.orders")
        self.assertEqual(snk.get("topics.regex"), "ecommerce.public.*")

        # connector_name → name (always highest priority)
        self.assertEqual(src.get("name"), "pg-to-s3-source")
        self.assertEqual(snk.get("name"), "pg-to-s3-sink")

    def test_unresolved_jinja_expression_fails(self):
        raw = postgres_source_yaml(
            VALID_PG_CONFIG + "\n    something: {{ unknown_func('x') }}"
        )
        self._assert_failed_with(build(raw), "Unresolved expression")

    def test_missing_connection_ref_fails(self):
        raw = postgres_source_yaml(VALID_PG_CONFIG).replace(
            "pg_conn: {{ conn('postgres_dev') }}",
            "pg_conn: {{ conn('postgres_missing') }}",
        )
        self._assert_failed_with(build(raw), "Connection not found in registry: 'postgres_missing'")

    def test_missing_env_level_kafka_connect_connection_fails(self):
        raw = postgres_source_yaml(VALID_PG_CONFIG).replace(
            "kafka_connect.connection: {{ conn('kafka_connect_dev') }}",
            "kafka_connect.connection: {{ conn('kafka_connect_missing') }}",
        )
        self._assert_failed_with(build(raw), "Connection not found in registry: 'kafka_connect_missing'")

    def test_missing_env_var_fails(self):
        marker = "SB_TEST_UNSET_DO_NOT_SET_ME"
        self.assertNotIn(marker, os.environ)
        raw = postgres_source_yaml(
            VALID_PG_CONFIG + f"\n    some.env.key: {{{{ env_var('{marker}') }}}}"
        )
        self._assert_failed_with(build(raw), f"env_var '{marker}' is not set")

    def test_yaml_config_overrides_plugin_base(self):
        raw = postgres_source_yaml(VALID_PG_CONFIG + "\n    tasks.max: \"4\"")
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")
        self.assertEqual(result["sourceConfig"].get("tasks.max"), "4")

    def test_var_in_source_config_builds_the_resolved_value(self):
        raw = postgres_source_yaml(
            VALID_PG_CONFIG + "\n    database.hostname: {{ var('pg_host') }}"
        ).replace("    dev:\n", "    dev:\n      pg_host: pg.internal\n")
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")
        self.assertEqual(result["sourceConfig"].get("database.hostname"), "pg.internal")

    def test_connector_name_overrides_yaml_name_field(self):
        raw = postgres_source_yaml(VALID_PG_CONFIG + "\n    name: user-provided-name")
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")
        self.assertEqual(result["sourceConfig"].get("name"), "pg-to-s3-source")


if __name__ == "__main__":
    unittest.main()
