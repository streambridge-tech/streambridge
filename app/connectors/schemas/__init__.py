"""Registry of per-subtype connection Schemas.

Concrete schemas live in per-file modules (postgres.py, mysql.py, …) and
register themselves here via the `_REGISTRY` dict. Callers use `get_schema()`.
"""

from app.connectors.schemas.base import (
    FieldDef,
    Schema,
    SECRET_MASK,
    build_kc_config,
    build_test_kwargs,
    defaults_kc_config,
)
from app.connectors.schemas.postgres import POSTGRES_SCHEMA
from app.connectors.schemas.mysql import MYSQL_SCHEMA
from app.connectors.schemas.s3 import S3_SCHEMA
from app.connectors.schemas.kafka import KAFKA_SCHEMA
from app.connectors.schemas.kafka_connect import KAFKA_CONNECT_SCHEMA
from app.connectors.schemas.schema_registry import SCHEMA_REGISTRY_SCHEMA


_REGISTRY: dict[str, Schema] = {
    POSTGRES_SCHEMA.subtype:        POSTGRES_SCHEMA,
    MYSQL_SCHEMA.subtype:           MYSQL_SCHEMA,
    S3_SCHEMA.subtype:              S3_SCHEMA,
    KAFKA_SCHEMA.subtype:           KAFKA_SCHEMA,
    KAFKA_CONNECT_SCHEMA.subtype:   KAFKA_CONNECT_SCHEMA,
    SCHEMA_REGISTRY_SCHEMA.subtype: SCHEMA_REGISTRY_SCHEMA,
}


def get_schema(subtype: str) -> Schema | None:
    """Return the Schema for a connection subtype, or None if unsupported."""
    return _REGISTRY.get((subtype or "").lower())


def supported_subtypes() -> list[str]:
    return sorted(_REGISTRY.keys())


__all__ = [
    "FieldDef",
    "Schema",
    "SECRET_MASK",
    "build_kc_config",
    "build_test_kwargs",
    "defaults_kc_config",
    "get_schema",
    "supported_subtypes",
]
