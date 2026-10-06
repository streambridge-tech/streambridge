"""Build a librdkafka config dict from a stored Kafka connection."""

from __future__ import annotations

from app.connectors.schemas import build_test_kwargs, get_schema
from app.services.kafka.errors import KafkaBrowseError

STANDARD_TIMEOUT_MS = 10_000
STANDARD_TIMEOUT_SEC = STANDARD_TIMEOUT_MS / 1000.0

_TIMEOUT_KEYS = {
    "request.timeout.ms",
    "socket.timeout.ms",
    "session.timeout.ms",
    "api.version.request.timeout.ms",
}


def kafka_client_config(config: dict) -> dict:
    """Native Kafka property map for confluent-kafka AdminClient / Consumer."""
    schema = get_schema("kafka")
    if schema is None:
        raise KafkaBrowseError("Kafka connection schema is not registered")

    stored = dict(config or {})
    mapped = build_test_kwargs(schema, stored)
    extras = {
        key: value
        for key, value in stored.items()
        if "." in str(key)
        and key not in mapped
        and key not in _TIMEOUT_KEYS
        and value not in (None, "")
    }
    conf = {**mapped, **extras}
    servers = str(conf.get("bootstrap.servers") or "").strip()
    if not servers:
        raise KafkaBrowseError("Kafka bootstrap servers are required")

    protocol = str(conf.get("security.protocol") or "PLAINTEXT").upper()
    conf["security.protocol"] = protocol
    if not protocol.startswith("SASL"):
        for key in [item for item in conf if str(item).startswith("sasl.")]:
            conf.pop(key, None)
    if "SSL" not in protocol:
        for key in [item for item in conf if str(item).startswith("ssl.")]:
            conf.pop(key, None)

    conf["socket.timeout.ms"] = str(STANDARD_TIMEOUT_MS)
    conf.setdefault("client.id", "streambridge")
    return {str(key): str(value) for key, value in conf.items() if value not in (None, "")}
