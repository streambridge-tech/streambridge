from app.connectors.base import BaseConnector
from app.connectors.schemas import build_kc_config, build_test_kwargs, defaults_kc_config
from app.connectors.schemas.mysql import MYSQL_SCHEMA
from app.utils.logger import get_logger
import re
log = get_logger(__name__)


class MySQLSourceConnector(BaseConnector):

    SUBTYPE = "mysql"
    TYPE    = "source"
    TOPIC_PREFIX_FIELD = "topic.prefix"
    SCHEMA = MYSQL_SCHEMA

    REQUIRED_FIELDS = [
        "database.hostname",
        "database.port",
        "database.include.list",
        "database.user",
        "database.password",
    ]

    OPTIONAL_FIELDS = [
        "database.server.id",
        "topic.prefix",
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
        "schema.history.internal.kafka.bootstrap.servers",
        "schema.history.internal.kafka.topic",
        "tasks.max",
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

        r.info("Checking source config fields (mysql)…")

        self.check_schema_registry_shape(config, has_sr_conn, plugin_format, "source", r)

        # db credentials — required only if no db.connection
        if not has_db_conn:
            for key in ("database.hostname", "database.port", "database.user",
                        "database.password", "database.include.list"):
                if not config.get(key):
                    r.error(f"source.config.{key} is required (no db.connection provided)",
                            f"add  {key}: <value>  under source.config: or set db.connection")
        else:
            r.success("db.connection present — credentials injected at deploy time  ✓")

        # table.include.list — always required
        if not config.get("table.include.list"):
            r.error("source.config.table.include.list is required",
                    "add  table.include.list: database.table  under source.config:")
        else:
            r.success(f'table.include.list: "{config["table.include.list"]}"  ✓')

        # database.server.name — always required
        if not config.get("database.server.name"):
            r.error("source.config.database.server.name is required",
                    "add  database.server.name: <name>  under source.config:")
        else:
            r.success(f'database.server.name: "{config["database.server.name"]}"  ✓')

        # schema history kafka bootstrap — required if no kafka.connection
        if not has_kafka_conn:
            has_schema_history = config.get("schema.history.internal.kafka.bootstrap.servers")
            has_bootstrap = config.get("bootstrap.servers")
            if not has_schema_history and not has_bootstrap:
                r.error(
                    "kafka.connection is not set. Provide either schema.history.internal.kafka.bootstrap.servers or bootstrap.servers.",
                    "add  schema.history.internal.kafka.bootstrap.servers: <brokers>  (or bootstrap.servers: <brokers>)  under source.config: or set kafka.connection"
                )
            else:
                val = has_schema_history or has_bootstrap
                key = "schema.history.internal.kafka.bootstrap.servers" if has_schema_history else "bootstrap.servers"
                r.success(f'{key}: "{val}"  ✓')
        else:
            r.success("kafka.connection present — schema history bootstrap injected at deploy time  ✓")

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
                log.warning("Validation failed — missing field: %s", field)
                errors.append(f"'{field}' is required")
        return errors

    def build_config(self, form: dict, extra: dict) -> dict:
        config = defaults_kc_config(self.SCHEMA)
        config.update(build_kc_config(self.SCHEMA, form))
        config.update({k: str(v) for k, v in (extra or {}).items() if v != ""})
        log.debug("Built MySQL config  keys=%s", list(config.keys()))
        return config

    def test_connection(self, config: dict) -> dict:
        host = config.get("database.hostname")
        port = config.get("database.port", 3306)
        log.info("Testing MySQL connection  host=%s  port=%s", host, port)
        try:
            import pymysql
        except ImportError:
            msg = "pymysql not installed — run: uv add pymysql"
            log.error(msg)
            return {"success": False, "message": msg}

        try:
            kwargs = build_test_kwargs(self.SCHEMA, config)
            if "port" in kwargs:
                kwargs["port"] = int(kwargs["port"])
            kwargs.setdefault("connect_timeout", 5)
            # database is a Debezium filter list, not a real DB — test without one.
            kwargs.setdefault("database", None)
            conn = pymysql.connect(**kwargs)
            conn.close()
            log.info("MySQL connection successful  host=%s", host)
            return {"success": True, "message": "Connection successful"}
        except Exception as e:
            log.error("MySQL connection failed  host=%s  error=%s", host, e)
            return {"success": False, "message": str(e)}
