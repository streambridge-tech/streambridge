from app.connectors.base import BaseConnector
from app.connectors.schemas import build_kc_config, defaults_kc_config
from app.connectors.schemas.kafka import KAFKA_SCHEMA
from app.utils.logger import get_logger

log = get_logger(__name__)


class KafkaBrokerConnector(BaseConnector):

    SUBTYPE = "kafka"
    TYPE    = "kafka"
    SCHEMA  = KAFKA_SCHEMA

    REQUIRED_FIELDS = [
        "bootstrap.servers",
    ]

    OPTIONAL_FIELDS = [
        "security.protocol",
        "client.id",
        "sasl.username",
        "sasl.password",
        "sasl.mechanism",
        "ssl.ca.location",
        "ssl.certificate.location",
        "ssl.key.location",
        "ssl.key.password",
        "ssl.endpoint.identification.algorithm",
    ]

    def validate(self, data: dict) -> list[str]:
        errors = []
        for field in self.REQUIRED_FIELDS:
            if not data.get(field):
                errors.append(f"'{field}' is required")
        protocol = str(data.get("security.protocol") or "PLAINTEXT").upper()
        if protocol.startswith("SASL") and not (data.get("sasl.username") or data.get("sasl.password")):
            errors.append("SASL username and password are required for SASL_* protocols")
        return errors

    def build_config(self, form: dict, extra: dict) -> dict:
        config = defaults_kc_config(self.SCHEMA)
        config.update(build_kc_config(self.SCHEMA, form))
        config.update({k: str(v) for k, v in (extra or {}).items() if v != ""})
        config.pop("request.timeout.ms", None)
        protocol = str(config.get("security.protocol") or "PLAINTEXT").upper()
        if not protocol.startswith("SASL"):
            for key in [item for item in config if str(item).startswith("sasl.")]:
                config.pop(key, None)
        if "SSL" not in protocol:
            for key in [item for item in config if str(item).startswith("ssl.")]:
                config.pop(key, None)
        return config

    def test_connection(self, config: dict) -> dict:
        servers = config.get("bootstrap.servers", "")
        log.info("Testing Kafka broker connection  servers=%s", servers)
        try:
            from confluent_kafka.admin import AdminClient
        except ImportError:
            return {"success": False, "message": "confluent-kafka not installed — run: uv add confluent-kafka"}

        import os
        from app.services.kafka.client import STANDARD_TIMEOUT_SEC, kafka_client_config
        from app.services.kafka.errors import KafkaBrowseError
        try:
            kwargs = kafka_client_config(config)
        except KafkaBrowseError as exc:
            return {"success": False, "message": str(exc)}

        ssl_cafile = kwargs.get("ssl.ca.location")
        if ssl_cafile and not os.path.exists(ssl_cafile):
            return {"success": False, "message":
                    f"SSL CA Bundle file not found: {ssl_cafile}. "
                    f"Download the CA cert from Aiven / your broker admin and save it locally, "
                    f"then paste the correct absolute path."}

        try:
            admin = AdminClient(kwargs)
            admin.list_topics(timeout=STANDARD_TIMEOUT_SEC)
            return {"success": True, "message": f"Connected to Kafka broker ({servers})"}
        except Exception as e:
            return {"success": False, "message": str(e)}
