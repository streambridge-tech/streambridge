from app.connectors.source.postgres      import PostgresSourceConnector
from app.connectors.source.mysql         import MySQLSourceConnector
from app.connectors.sink.s3              import S3SinkConnector
from app.connectors.infra.kafka_broker   import KafkaBrokerConnector
from app.connectors.infra.kafka_connect  import KafkaConnectConnector
from app.connectors.infra.schema_registry import SchemaRegistryConnector
from app.utils.logger import get_logger

log = get_logger(__name__)

_REGISTRY: dict = {
    ("source",  "postgres"):      PostgresSourceConnector(),
    ("source",  "mysql"):         MySQLSourceConnector(),
    ("sink",    "s3"):            S3SinkConnector(),
    ("transport",   "kafka"):         KafkaBrokerConnector(),
    ("connect",   "kafka-connect"): KafkaConnectConnector(),
    ("transport", "schema-registry"): SchemaRegistryConnector(),
}

log.info("Connector registry loaded  connectors=%s", [f"{t}/{s}" for t, s in _REGISTRY])


def get(conn_type: str, subtype: str):
    """Return connector instance for (type, subtype), or None if not registered."""
    print(f"Getting connector for type={conn_type}, subtype={subtype}")
    return _REGISTRY.get((conn_type.lower(), subtype.lower()))
