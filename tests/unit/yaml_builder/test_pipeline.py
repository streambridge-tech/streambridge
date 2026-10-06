import unittest

from app.utils.yaml_builder import build_pipeline


class DummyDB:
    pass


def base_yaml() -> str:
    return """pipeline:
  name: pg-to-s3
  env:
    dev:
      pg_conn: {{ conn('postgres_dev') }}
      s3_conn: {{ conn('s3_dev') }}
      kafka_connect.connection: {{ conn('kafka_connect_dev') }}
      kafka_conn: {{ conn('kafka_dev') }}

source:
  type: postgres
  connector_name: pg-to-s3-source
  db.connection: {{ var('pg_conn') }}
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


def error_texts(result: dict) -> list[str]:
    return [log["text"] for log in result["logs"] if log["level"] == "error"]


class PipelineLevelValidationTests(unittest.TestCase):

    def _assert_failed_with(self, result: dict, needle: str):
        self.assertFalse(result["ok"], msg=f"expected failure, got ok=True; logs={result['logs']}")
        texts = error_texts(result)
        self.assertTrue(
            any(needle in t for t in texts),
            msg=f"expected an error containing {needle!r}, got: {texts}",
        )

    def test_missing_pipeline_name(self):
        raw = base_yaml().replace("  name: pg-to-s3\n", "")
        self._assert_failed_with(build_pipeline(raw, "dev", DummyDB()), "pipeline.name is missing")

    def test_pipeline_name_too_long(self):
        long_name = "x" * 129
        raw = base_yaml().replace("  name: pg-to-s3", f"  name: {long_name}")
        self._assert_failed_with(build_pipeline(raw, "dev", DummyDB()), "max 128")

    def test_missing_source_block(self):
        raw = base_yaml()
        raw = raw[: raw.index("source:")] + raw[raw.index("sink:") :]
        self._assert_failed_with(build_pipeline(raw, "dev", DummyDB()), "source: block is missing")

    def test_missing_sink_block(self):
        raw = base_yaml()
        raw = raw[: raw.index("sink:")]
        self._assert_failed_with(build_pipeline(raw, "dev", DummyDB()), "sink: block is missing")

    def test_env_block_present_but_no_env_selected(self):
        self._assert_failed_with(build_pipeline(base_yaml(), "", DummyDB()), "select a target env")

    def test_missing_source_connector_name(self):
        raw = base_yaml().replace("  connector_name: pg-to-s3-source\n", "")
        self._assert_failed_with(build_pipeline(raw, "dev", DummyDB()), "source.connector_name is missing")

    def test_missing_sink_connector_name(self):
        raw = base_yaml().replace("  connector_name: pg-to-s3-sink\n", "")
        self._assert_failed_with(build_pipeline(raw, "dev", DummyDB()), "sink.connector_name is missing")

    def test_source_connector_name_too_long(self):
        long_name = "s" * 65
        raw = base_yaml().replace("  connector_name: pg-to-s3-source", f"  connector_name: {long_name}")
        self._assert_failed_with(build_pipeline(raw, "dev", DummyDB()), "max 64")

    def test_unsupported_source_type(self):
        raw = base_yaml().replace("  type: postgres", "  type: oracle")
        self._assert_failed_with(build_pipeline(raw, "dev", DummyDB()), "source.type 'oracle' is not supported")

    def test_unsupported_sink_type(self):
        raw = base_yaml().replace("  type: s3", "  type: bigquery")
        self._assert_failed_with(build_pipeline(raw, "dev", DummyDB()), "sink.type 'bigquery' is not supported")


if __name__ == "__main__":
    unittest.main()
