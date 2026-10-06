"""Schema Registry connection validation and provider-aware connectivity test."""

from app.connectors.base import BaseConnector
from app.connectors.schemas import build_kc_config, defaults_kc_config
from app.connectors.schemas.schema_registry import SCHEMA_REGISTRY_SCHEMA
from app.services.schema_registry import SchemaRegistryError, get_schema_registry
from app.services.schema_registry.auth import AUTH_BASIC, AUTH_BEARER, AUTH_TYPES, apply_auth_type, resolve_auth_type
from app.utils.logger import get_logger

log = get_logger(__name__)


class SchemaRegistryConnector(BaseConnector):

    SUBTYPE = "schema-registry"
    TYPE    = "transport"
    SCHEMA  = SCHEMA_REGISTRY_SCHEMA

    REQUIRED_FIELDS = ["url"]
    OPTIONAL_FIELDS = ["username", "password", "token"]

    def validate(self, data: dict) -> list[str]:
        errors = []
        provider = (data.get("provider") or "").lower()
        if provider not in ("confluent", "apicurio"):
            errors.append("'provider' must be either 'confluent' or 'apicurio'; AWS Glue support is planned for Phase 2")
        if not data.get("url"):
            errors.append("'url' is required")
        auth = resolve_auth_type(data)
        declared = str(data.get("auth_type") or auth).lower()
        if declared not in AUTH_TYPES:
            errors.append("'auth_type' must be none, basic, or bearer")
        if auth == AUTH_BASIC:
            if not data.get("username"):
                errors.append("'username' is required for HTTP Basic authentication")
            if not data.get("password"):
                errors.append("'password' is required for HTTP Basic authentication")
        if auth == AUTH_BEARER and not (data.get("token") or data.get("bearer_token")):
            errors.append("'token' is required for Bearer authentication")
        return errors

    def build_config(self, form: dict, extra: dict) -> dict:
        config = defaults_kc_config(self.SCHEMA)
        config.update(build_kc_config(self.SCHEMA, form))
        config.update({k: str(v) for k, v in (extra or {}).items() if v != ""})
        config.pop("group_id", None)
        if not (form or {}).get("auth_type"):
            config.pop("auth_type", None)
        return apply_auth_type(config)

    def merge_preserved_secrets(self, new_cfg: dict, old_cfg: dict) -> dict:
        merged = super().merge_preserved_secrets(new_cfg, old_cfg or {})
        merged.pop("group_id", None)
        return apply_auth_type(merged)

    def test_connection(self, config: dict) -> dict:
        try:
            result = get_schema_registry(apply_auth_type(config)).test_connection()
            provider = result.get("provider", config.get("provider", "")).title()
            return {
                "success": True,
                "message": f"{provider} Schema Registry reachable at {config.get('url')}",
                **result,
            }
        except SchemaRegistryError as exc:
            log.warning("Schema Registry test failed: %s", exc)
            return {"success": False, "message": str(exc)}
