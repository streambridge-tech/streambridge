from abc import ABC, abstractmethod


class BaseConnector(ABC):

    SUBTYPE: str = ""
    TYPE: str = ""          # source | sink
    REQUIRED_FIELDS: list[str] = []
    OPTIONAL_FIELDS: list[str] = []
    TOPIC_PREFIX_FIELD: str | None = None   # source connectors: field that holds the topic prefix
    TOPIC_FIELD: str | None = None          # sink connectors: field that lists consumed topics

    @abstractmethod
    def validate(self, data: dict) -> list[str]:
        """Return list of validation error messages. Empty = valid."""

    @abstractmethod
    def build_config(self, form: dict, extra: dict) -> dict:
        """
        Merge form fields + extra into one flat Debezium-style config dict.
        form  — typed fields from the UI form (host, port, username …)
        extra — raw key/value pairs from the Extra textarea
        Returns the final merged dict to store in DB.
        """

    @abstractmethod
    def test_connection(self, config: dict) -> dict:
        """
        Actually connect using config.
        Returns {"success": bool, "message": str}
        """

    def compile(
        self,
        config: dict,
        has_db_conn: bool,
        has_kafka_conn: bool,
        has_kc_conn: bool,
        has_sr_conn: bool = False,
        plugin_format: str = "JSON",
    ) -> "CompileResult":
        """Connector-level compile-time validation. Override in each connector."""
        from app.connectors.compile_result import CompileResult
        return CompileResult()

    def check_schema_registry_shape(
        self,
        config: dict,
        has_sr_conn: bool,
        plugin_format: str,
        side: str,
        r: "CompileResult",
    ) -> None:
        """AVRO plugins require schema registry via connection ref or config key."""
        if plugin_format != "AVRO":
            return
        has_url = bool(
            config.get("schema.registry.url")
            or config.get("value.converter.schema.registry.url")
        )
        if has_sr_conn or has_url:
            r.success(f"schema registry present ({side})  ✓")
            return
        r.error(
            f"{side} uses an AVRO plugin — schema registry required",
            f"set  schema_registry.connection: {{{{ var('sr_conn') }}}}  under {side}: "
            f"or add  schema.registry.url: <url>  under {side}.config:",
        )

    def derive_topics(self, config: dict) -> list[str]:
        """Derive Kafka topic names this source will produce. Override in source connectors."""
        return []

    def merge_preserved_secrets(self, new_cfg: dict, old_cfg: dict) -> dict:
        """Keep previously stored secrets when the form omitted or masked them."""
        from app.connectors.schemas import SECRET_MASK
        schema = getattr(self, "SCHEMA", None)
        if schema is None:
            return new_cfg
        merged = dict(new_cfg)
        for f in schema.fields:
            if not (f.secret and f.kc_key):
                continue
            val = merged.get(f.kc_key)
            if val in (None, "", SECRET_MASK):
                if old_cfg.get(f.kc_key):
                    merged[f.kc_key] = old_cfg[f.kc_key]
                elif val == SECRET_MASK:
                    merged.pop(f.kc_key, None)
        return merged

    def validate_build(self, config: dict) -> list[tuple[str, str]]:
        """
        Check REQUIRED_FIELDS against merged YAML config (post plugin merge).
        Returns list of (missing_key, fix_suggestion) — empty = all present.
        """
        missing = []
        for key in self.REQUIRED_FIELDS:
            if not config.get(key):
                fix = f"add  {key}: <value>  under {self.TYPE}.config:"
                missing.append((key, fix))
        return missing
