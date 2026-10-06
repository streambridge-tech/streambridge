import re
from app.connectors.base import BaseConnector
from app.connectors.schemas import (
    build_kc_config,
    build_test_kwargs,
    defaults_kc_config,
)
from app.connectors.schemas.postgres import POSTGRES_SCHEMA


class PostgresSourceConnector(BaseConnector):

    SUBTYPE = "postgres"
    TYPE    = "source"
    TOPIC_PREFIX_FIELD = "topic.prefix"
    SCHEMA  = POSTGRES_SCHEMA

    REQUIRED_FIELDS = [
        "database.hostname",
        "database.port",
        "database.user",
        "database.password",
        "database.dbname",
    ]

    OPTIONAL_FIELDS = [
        "database.server.name",
        "slot.name",
        "plugin.name",
        "publication.name",
        "publication.autocreate.mode",
        "table.include.list",
        "table.exclude.list",
        "column.exclude.list",
        "snapshot.mode",
        "snapshot.include.collection.list",
        "decimal.handling.mode",
        "time.precision.mode",
        "tombstones.on.delete",
        "heartbeat.interval.ms",
        "transforms",
        "transforms.unwrap.type",
        "transforms.unwrap.drop.tombstones",
        "transforms.unwrap.add.fields",
        "topic.prefix",
        "max.batch.size",
        "max.queue.size",
        "poll.interval.ms",
        "skipped.operations",
    ]

    _VALID_TOPIC_PREFIX_RE = re.compile(r'^[a-zA-Z0-9._-]+$')

    def derive_topics(self, config: dict) -> list[str]:
        prefix = config.get("topic.prefix") or config.get("name", "")
        tables = config.get("table.include.list", "")
        if not prefix or not tables or not self._VALID_TOPIC_PREFIX_RE.match(prefix):
            return []
        return [f"{prefix}.{t.strip()}" for t in tables.split(",") if t.strip()]

    def compile(self, config, has_db_conn, has_kafka_conn, has_kc_conn, has_sr_conn=False, plugin_format="JSON"):
        from app.connectors.compile_result import CompileResult
        r = CompileResult()

        r.info("Checking source config fields (postgres)…")

        self.check_schema_registry_shape(config, has_sr_conn, plugin_format, "source", r)

        # db credentials — required only if no db.connection
        if not has_db_conn:
            for key in ("database.hostname", "database.port", "database.user",
                        "database.password", "database.dbname"):
                if not config.get(key):
                    r.error(f"source.config.{key} is required (no db.connection provided)",
                            f"add  {key}: <value>  under source.config: or set db.connection")
        else:
            r.success("db.connection present — credentials injected at deploy time  ✓")

        # table.include.list — always required
        if not config.get("table.include.list"):
            r.error("source.config.table.include.list is required",
                    "add  table.include.list: schema.table  under source.config:")
        else:
            r.success(f'table.include.list: "{config["table.include.list"]}"  ✓')

        # database.server.name — always required
        if not config.get("database.server.name"):
            r.error("source.config.database.server.name is required",
                    "add  database.server.name: <name>  under source.config:")
        else:
            r.success(f'database.server.name: "{config["database.server.name"]}"  ✓')

        # kafka broker bootstrap — required if no kafka.connection
        if not has_kafka_conn:
            if not config.get("bootstrap.servers"):
                r.error(
                    "kafka.connection is not set. Provide bootstrap.servers as a fallback.",
                    "add  bootstrap.servers: <brokers>  under source.config: or set kafka.connection"
                )
            else:
                r.success(f'bootstrap.servers: "{config["bootstrap.servers"]}"  ✓')
        else:
            r.success("kafka.connection present — broker bootstrap injected at deploy time  ✓")

        # topic.prefix — informational
        if not config.get("topic.prefix"):
            r.info(f'topic.prefix not set — connector_name "{config.get("name","")}" will be used as prefix')
        else:
            r.success(f'topic.prefix: "{config["topic.prefix"]}"  ✓')

        return r

    def validate(self, data: dict) -> list[str]:
        errors = []
        for field in self.REQUIRED_FIELDS:
            if not data.get(field):
                errors.append(f"'{field}' is required")
        return errors

    def build_config(self, form: dict, extra: dict) -> dict:
        # Schema-driven: FieldDef.kc_key + FieldDef.cast do the mapping.
        # Schema defaults are applied first so blank optional fields land on their default.
        config = defaults_kc_config(self.SCHEMA)
        config.update(build_kc_config(self.SCHEMA, form))
        # Extra escape hatch merges last (extra wins on conflict) — same semantics as before.
        config.update({k: str(v) for k, v in (extra or {}).items() if v != ""})
        return config

    def test_connection(self, config: dict) -> dict:
        try:
            import psycopg2
        except ImportError:
            return {"success": False, "message": "psycopg2 not installed — run: uv add psycopg2-binary"}

        try:
            kwargs = build_test_kwargs(self.SCHEMA, config)
            # port always needs int for psycopg2 (schema cast is str for storage).
            if "port" in kwargs:
                kwargs["port"] = int(kwargs["port"])
            kwargs.setdefault("connect_timeout", 5)
            conn = psycopg2.connect(**kwargs)
            conn.close()
            return {"success": True, "message": "Connection successful"}
        except Exception as e:
            return {"success": False, "message": str(e)}
