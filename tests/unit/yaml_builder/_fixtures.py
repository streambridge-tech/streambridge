"""Shared test fixtures for yaml_builder unit tests: a minimal fake DB and valid base YAML."""
import json

from app.models.plugin import Plugin
from app.utils.yaml_builder import build_pipeline


class FakePlugin:
    def __init__(self, name: str, type_: str, format_: str, config: dict):
        self.name = name
        self.type = type_
        self.format = format_
        self.config = json.dumps(config)


class FakeConnection:
    def __init__(self, name: str):
        self.name = name


class FakeQuery:
    def __init__(self, rows: list, filters: list | None = None):
        self._rows = rows
        self._filters = filters or []

    def filter(self, *exprs):
        return FakeQuery(self._rows, self._filters + list(exprs))

    def _apply(self):
        result = self._rows
        for expr in self._filters:
            try:
                col = expr.left.key
                val = expr.right.value
                result = [r for r in result if getattr(r, col, None) == val]
            except AttributeError:
                pass
        return result

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        rows = self._apply()
        return rows[0] if rows else None

    def all(self):
        return self._apply()


class FakeDB:
    """Minimal SQLAlchemy-session stand-in used by build_pipeline and orchestrator tests.

    Supports read (query/filter/first/all) and write (add/flush/commit).
    Added rows get an incrementing integer id on flush() to mimic auto-increment PKs.
    """

    def __init__(self, plugins: list, connections: list):
        self._plugins = plugins
        self._connections = connections
        self.added: list = []
        self._next_id = 1

    def query(self, model):
        if model is Plugin:
            return FakeQuery(self._plugins)
        return FakeQuery(self._connections)

    def add(self, row):
        self.added.append(row)

    def flush(self):
        for row in self.added:
            if getattr(row, "id", None) is None:
                try:
                    setattr(row, "id", self._next_id)
                    self._next_id += 1
                except (AttributeError, TypeError):
                    pass

    def commit(self):
        self.flush()

    def refresh(self, _row):
        pass


DEFAULT_PLUGINS = [
    FakePlugin("postgres-json", "source", "JSON",
               {"connector.class": "io.debezium.connector.postgresql.PostgresConnector", "tasks.max": "1"}),
    FakePlugin("postgres-avro", "source", "AVRO",
               {"connector.class": "io.debezium.connector.postgresql.PostgresConnector", "tasks.max": "1"}),
    FakePlugin("mysql-json", "source", "JSON",
               {"connector.class": "io.debezium.connector.mysql.MySqlConnector", "tasks.max": "1"}),
    FakePlugin("mysql-avro", "source", "AVRO",
               {"connector.class": "io.debezium.connector.mysql.MySqlConnector", "tasks.max": "1"}),
    FakePlugin("s3-json", "sink", "JSON",
               {"connector.class": "io.confluent.connect.s3.S3SinkConnector", "tasks.max": "1"}),
    FakePlugin("s3-avro", "sink", "AVRO",
               {"connector.class": "io.confluent.connect.s3.S3SinkConnector", "tasks.max": "1"}),
]

DEFAULT_CONNECTIONS = [
    FakeConnection("postgres_dev"),
    FakeConnection("mysql_dev"),
    FakeConnection("s3_dev"),
    FakeConnection("kafka_connect_dev"),
    FakeConnection("kafka_dev"),
    FakeConnection("schema_registry_dev"),
]


def fake_db(plugins=None, connections=None) -> FakeDB:
    return FakeDB(
        plugins if plugins is not None else list(DEFAULT_PLUGINS),
        connections if connections is not None else list(DEFAULT_CONNECTIONS),
    )


def build(raw: str, env: str = "dev", db: FakeDB | None = None) -> dict:
    return build_pipeline(raw, env, db if db is not None else fake_db())


def error_texts(result: dict) -> list[str]:
    return [log["text"] for log in result["logs"] if log["level"] == "error"]


def postgres_source_yaml(source_config: str) -> str:
    """Valid pipeline with a postgres source; source_config is the indented body under source.config."""
    return f"""pipeline:
  name: pg-to-s3
  env:
    dev:
      pg_conn: {{{{ conn('postgres_dev') }}}}
      s3_conn: {{{{ conn('s3_dev') }}}}
      kafka_connect.connection: {{{{ conn('kafka_connect_dev') }}}}
      kafka_conn: {{{{ conn('kafka_dev') }}}}

source:
  type: postgres
  connector_name: pg-to-s3-source
  db.connection: {{{{ var('pg_conn') }}}}
  kafka.connection: {{{{ var('kafka_conn') }}}}
  config:
{source_config}

sink:
  type: s3
  connector_name: pg-to-s3-sink
  storage.connection: {{{{ var('s3_conn') }}}}
  config:
    topics.regex: ecommerce.public.*
"""


def mysql_source_yaml(source_config: str, source_top_extra: str = "") -> str:
    return f"""pipeline:
  name: mysql-to-s3
  env:
    dev:
      mysql_conn: {{{{ conn('mysql_dev') }}}}
      s3_conn: {{{{ conn('s3_dev') }}}}
      kafka_connect.connection: {{{{ conn('kafka_connect_dev') }}}}
      kafka_conn: {{{{ conn('kafka_dev') }}}}

source:
  type: mysql
  connector_name: mysql-to-s3-source
  db.connection: {{{{ var('mysql_conn') }}}}
  kafka.connection: {{{{ var('kafka_conn') }}}}{source_top_extra}
  config:
{source_config}

sink:
  type: s3
  connector_name: mysql-to-s3-sink
  storage.connection: {{{{ var('s3_conn') }}}}
  config:
    topics.regex: ecommerce.public.*
"""


def s3_sink_yaml(sink_config: str, sink_top_extra: str = "") -> str:
    """Valid pipeline with an s3 sink; sink_config is the indented body under sink.config.

    sink_top_extra is appended under sink: (e.g. connection refs). Include a leading newline.
    """
    return f"""pipeline:
  name: pg-to-s3
  env:
    dev:
      pg_conn: {{{{ conn('postgres_dev') }}}}
      s3_conn: {{{{ conn('s3_dev') }}}}
      kafka_connect.connection: {{{{ conn('kafka_connect_dev') }}}}
      kafka_conn: {{{{ conn('kafka_dev') }}}}

source:
  type: postgres
  connector_name: pg-to-s3-source
  db.connection: {{{{ var('pg_conn') }}}}
  kafka.connection: {{{{ var('kafka_conn') }}}}
  config:
    database.server.name: ecommerce
    table.include.list: public.orders

sink:
  type: s3
  connector_name: pg-to-s3-sink{sink_top_extra}
  config:
{sink_config}
"""
