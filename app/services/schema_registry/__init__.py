"""Provider-neutral Schema Registry clients."""

from app.services.schema_registry.base import SchemaRegistry, SchemaRegistryError
from app.services.schema_registry.factory import get_schema_registry

__all__ = ["SchemaRegistry", "SchemaRegistryError", "get_schema_registry"]
