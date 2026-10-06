import unittest

from app.utils.yaml_builder import build_pipeline


class DummyDB:
    pass


class BuildPipelineEnvValidationTests(unittest.TestCase):

    def test_selected_env_requires_kafka_connect_connection(self):
        raw = """pipeline:
  name: pg-to-s3
  env:
    dev:
      pg_conn: {{ conn('postgres_dev') }}
      s3_conn: {{ conn('s3_dev') }}
      kafka_conn: {{ conn('kafka_dev') }}
    prod:
      pg_conn: {{ conn('postgres_prod') }}
      s3_conn: {{ conn('s3_prod') }}
      kafka_connect.connection: {{ conn('kafka_connect_prod') }}
      kafka_conn: {{ conn('kafka_prod') }}

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

        result = build_pipeline(raw, "dev", DummyDB())

        self.assertFalse(result["ok"])
        error_texts = [log["text"] for log in result["logs"] if log["level"] == "error"]
        self.assertTrue(
            any("pipeline.env.dev.kafka_connect.connection is required" in text for text in error_texts),
            msg=f"expected env-level kafka_connect.connection error, got: {error_texts}",
        )


if __name__ == "__main__":
    unittest.main()
