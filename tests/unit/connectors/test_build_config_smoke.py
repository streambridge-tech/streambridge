"""Connector-level integration tests.

Each test constructs the real connector class and calls `build_config()` — the
exact method the Flask API hits. This locks down the connector's wrapper
method (not just the underlying schema helpers) so that copy-paste / merge
mistakes like `self._FORM_MAP` referenced after removal fail loudly here
instead of surfacing as a 500 in production.

`test_connection` is NOT exercised here — the native libs (psycopg2, pymysql,
boto3, confluent-kafka) are mocked at their own integration layer or are known to
be optional. This file is deliberately thin so it never gets stale.
"""

import unittest

from app.connectors.infra.kafka_broker    import KafkaBrokerConnector
from app.connectors.infra.kafka_connect   import KafkaConnectConnector
from app.connectors.infra.schema_registry import SchemaRegistryConnector
from app.connectors.sink.s3               import S3SinkConnector
from app.connectors.source.mysql          import MySQLSourceConnector
from app.connectors.source.postgres       import PostgresSourceConnector


class BuildConfigSmokeTests(unittest.TestCase):
    """One `build_config` call per refactored connector — proves the wrapper method wires up cleanly."""

    def test_postgres_build_config_shape(self):
        cfg = PostgresSourceConnector().build_config(
            form={"host": "db.internal", "port": "5432", "database": "orders",
                  "username": "cdc", "password": "s3cret"},
            extra={"topic.prefix": "orders", "slot.name": "debezium"},
        )
        self.assertEqual(cfg["database.hostname"], "db.internal")
        self.assertEqual(cfg["database.port"], 5432)
        self.assertEqual(cfg["database.dbname"], "orders")
        self.assertEqual(cfg["database.user"], "cdc")
        self.assertEqual(cfg["database.password"], "s3cret")
        self.assertEqual(cfg["topic.prefix"], "orders")
        self.assertEqual(cfg["slot.name"], "debezium")

    def test_mysql_build_config_shape(self):
        cfg = MySQLSourceConnector().build_config(
            form={"host": "mysql.internal", "port": "3306", "database": "shop",
                  "username": "cdc", "password": "s3cret"},
            extra={"topic.prefix": "shop"},
        )
        self.assertEqual(cfg["database.hostname"], "mysql.internal")
        self.assertEqual(cfg["database.port"], 3306)
        self.assertEqual(cfg["database.include.list"], "shop")
        self.assertEqual(cfg["database.user"], "cdc")
        self.assertEqual(cfg["database.password"], "s3cret")
        self.assertEqual(cfg["topic.prefix"], "shop")

    def test_s3_build_config_shape(self):
        cfg = S3SinkConnector().build_config(
            form={"bucket": "cdc-bkt", "region": "us-east-1",
                  "access_key": "AKIA", "secret_key": "shh"},
            extra={"flush.size": "1000"},
        )
        self.assertEqual(cfg["s3.bucket.name"], "cdc-bkt")
        self.assertEqual(cfg["s3.region"], "us-east-1")
        self.assertEqual(cfg["aws.access.key.id"], "AKIA")
        self.assertEqual(cfg["aws.secret.access.key"], "shh")
        self.assertEqual(cfg["flush.size"], "1000")

    def test_s3_build_config_session_token(self):
        # STS temporary creds — session_token field must flow through.
        cfg = S3SinkConnector().build_config(
            form={"bucket": "b", "region": "us-east-1",
                  "access_key": "ASIA...", "secret_key": "shh",
                  "session_token": "FQoGZ..."},
            extra={},
        )
        self.assertEqual(cfg["aws.session.token"], "FQoGZ...")

    def test_kafka_broker_build_config_shape(self):
        cfg = KafkaBrokerConnector().build_config(
            form={"bootstrap_servers": "b1:9092,b2:9092",
                  "security_protocol": "SASL_SSL",
                  "sasl_mechanism": "PLAIN",
                  "username": "apikey", "password": "apisec"},
            extra={},
        )
        self.assertEqual(cfg["bootstrap.servers"], "b1:9092,b2:9092")
        self.assertEqual(cfg["security.protocol"], "SASL_SSL")
        self.assertEqual(cfg["sasl.mechanism"], "PLAIN")
        self.assertEqual(cfg["sasl.username"], "apikey")
        self.assertEqual(cfg["sasl.password"], "apisec")

    def test_kafka_connect_build_config_shape(self):
        cfg = KafkaConnectConnector().build_config(
            form={"url": "http://kc:8083", "username": "u", "password": "p"},
            extra={},
        )
        self.assertEqual(cfg["url"], "http://kc:8083")
        self.assertEqual(cfg["username"], "u")
        self.assertEqual(cfg["password"], "p")

    def test_schema_registry_build_config_shape(self):
        cfg = SchemaRegistryConnector().build_config(
            form={"provider": "confluent", "url": "http://sr:8081", "username": "u", "password": "p"},
            extra={},
        )
        self.assertEqual(cfg["url"], "http://sr:8081")
        self.assertEqual(cfg["username"], "u")
        self.assertEqual(cfg["password"], "p")
        self.assertEqual(cfg["auth_type"], "basic")
        self.assertNotIn("group_id", cfg)


class BuildConfigExtraMergeTests(unittest.TestCase):
    """Extra keys should always merge into the KC config unchanged."""

    def test_extra_wins_on_conflict(self):
        cfg = PostgresSourceConnector().build_config(
            form={"host": "h", "port": "5432", "database": "d",
                  "username": "u", "password": "p"},
            extra={"database.port": "9999"},
        )
        self.assertEqual(cfg["database.port"], "9999")

    def test_empty_extra_values_skipped(self):
        cfg = S3SinkConnector().build_config(
            form={"bucket": "b", "region": "us-east-1", "access_key": "k", "secret_key": "s"},
            extra={"topics": "", "flush.size": "1000"},
        )
        self.assertNotIn("topics", cfg)
        self.assertEqual(cfg["flush.size"], "1000")


if __name__ == "__main__":
    unittest.main()
