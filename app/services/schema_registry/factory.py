"""Create the configured Schema Registry provider client."""

from app.services.schema_registry.apicurio import ApicurioRegistry
from app.services.schema_registry.base import SchemaRegistryError
from app.services.schema_registry.confluent import ConfluentRegistry


def get_schema_registry(config: dict):
    provider = (config or {}).get("provider", "").lower()
    clients = {"confluent": ConfluentRegistry, "apicurio": ApicurioRegistry}
    client_class = clients.get(provider)
    if client_class:
        return client_class(config)
    if provider == "glue":
        raise SchemaRegistryError("AWS Glue Schema Registry support is planned for Phase 2")
    raise SchemaRegistryError(f"Unsupported schema registry provider: {provider or '(missing)'}")
