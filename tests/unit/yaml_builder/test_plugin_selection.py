import unittest

from tests.unit.yaml_builder._fixtures import (
    DEFAULT_PLUGINS, FakePlugin, build, error_texts, fake_db, postgres_source_yaml,
)


VALID_PG_CONFIG = (
    "    database.server.name: ecommerce\n"
    "    table.include.list: public.orders"
)


class PluginSelectionTests(unittest.TestCase):

    def _assert_failed_with(self, result, needle):
        self.assertFalse(result["ok"], msg=f"expected failure; logs={result['logs']}")
        texts = error_texts(result)
        self.assertTrue(
            any(needle in t for t in texts),
            msg=f"expected an error containing {needle!r}, got: {texts}",
        )

    def _plugin_log(self, result, side):
        for log in result["logs"]:
            if log["level"] == "success" and f"plugin ({side})" in log["text"]:
                return log["text"]
        return ""

    def test_default_json_plugin_used_when_plugin_omitted(self):
        raw = postgres_source_yaml(VALID_PG_CONFIG)
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")
        self.assertIn('"postgres-json"', self._plugin_log(result, "source"))
        self.assertIn('"s3-json"',       self._plugin_log(result, "sink"))
        self.assertIn("default",         self._plugin_log(result, "source"))

    def test_explicit_plugin_overrides_default(self):
        raw = postgres_source_yaml(
            VALID_PG_CONFIG + "\n    schema.registry.url: http://sr:8081"
        ).replace(
            "  type: postgres\n  connector_name: pg-to-s3-source",
            "  type: postgres\n  plugin: postgres-avro\n  connector_name: pg-to-s3-source",
        )
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")
        self.assertIn('"postgres-avro"', self._plugin_log(result, "source"))
        self.assertIn("explicit",        self._plugin_log(result, "source"))

    def test_unknown_plugin_fails(self):
        raw = postgres_source_yaml(VALID_PG_CONFIG).replace(
            "  type: postgres\n  connector_name: pg-to-s3-source",
            "  type: postgres\n  plugin: postgres-does-not-exist\n  connector_name: pg-to-s3-source",
        )
        self._assert_failed_with(build(raw), "'postgres-does-not-exist' not found")

    def test_plugin_config_that_is_not_an_object_fails_the_build(self):
        for stored in ([1], 5, None):
            with self.subTest(stored=stored):
                plugins = [p for p in DEFAULT_PLUGINS if p.name != "postgres-json"]
                plugins.append(FakePlugin("postgres-json", "source", "JSON", stored))
                result = build(postgres_source_yaml(VALID_PG_CONFIG), db=fake_db(plugins=plugins))
                self._assert_failed_with(result, "plugin 'postgres-json' config is not a JSON object")

    def test_plugin_config_that_is_not_json_fails_the_build(self):
        broken = FakePlugin("s3-json", "sink", "JSON", {})
        broken.config = "{not json"
        plugins = [p for p in DEFAULT_PLUGINS if p.name != "s3-json"] + [broken]
        result = build(postgres_source_yaml(VALID_PG_CONFIG), db=fake_db(plugins=plugins))
        self._assert_failed_with(result, "plugin 's3-json' config is not a JSON object")


class AvroSchemaRegistryShapeTests(unittest.TestCase):

    def _assert_failed_with(self, result, needle):
        self.assertFalse(result["ok"], msg=f"expected failure; logs={result['logs']}")
        texts = error_texts(result)
        self.assertTrue(
            any(needle in t for t in texts),
            msg=f"expected an error containing {needle!r}, got: {texts}",
        )

    def _pg_avro_yaml(self, extra_source_config: str = "", extra_source_top: str = "") -> str:
        raw = postgres_source_yaml(
            "    database.server.name: ecommerce\n"
            "    table.include.list: public.orders" + extra_source_config
        )
        raw = raw.replace(
            "  type: postgres\n  connector_name: pg-to-s3-source",
            f"  type: postgres\n  plugin: postgres-avro\n  connector_name: pg-to-s3-source{extra_source_top}",
        )
        return raw

    def test_avro_passes_when_schema_registry_url_in_config(self):
        raw = self._pg_avro_yaml(extra_source_config="\n    schema.registry.url: http://sr:8081")
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")

    def test_avro_passes_when_schema_registry_connection_at_connector_level(self):
        raw = self._pg_avro_yaml(
            extra_source_top="\n  schema_registry.connection: {{ conn('schema_registry_dev') }}",
        )
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")

    def test_avro_fails_without_schema_registry(self):
        raw = self._pg_avro_yaml()
        self._assert_failed_with(build(raw), "AVRO plugin — schema registry required")


if __name__ == "__main__":
    unittest.main()
