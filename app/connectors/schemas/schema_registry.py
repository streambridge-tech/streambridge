"""Schema Registry connection schema — treated the same as any other connector.

There is no Kafka Connect config for Schema Registry itself (it's a REST service
that other connectors reference by URL), so `kc_key` is None for every field.
The schema exists purely so the frontend can render a schema-driven form and
the backend can dispatch a real test_connection.
"""

from app.connectors.schemas.base import FieldDef, Schema


SCHEMA_REGISTRY_SCHEMA = Schema(
    subtype="schema-registry",
    label="Schema Registry",
    fields=(
        FieldDef(
            id="provider",
            label="Registry Type",
            kc_key="provider",
            test_key="provider",
            type="enum",
            options=("confluent", "apicurio"),
            importance="required",
            default="confluent",
            doc="Confluent Schema Registry or Apicurio Registry. AWS Glue is planned for Phase 2.",
            group="connection", order=5,
        ),
        FieldDef(
            id="url",
            label="Registry URL",
            kc_key="url",
            test_key="url",
            importance="required",
            placeholder="http://schema-registry:8081",
            doc="HTTP origin of the registry. Apicurio origins are normalized to Core v3 automatically.",
            group="connection", order=10,
        ),
        FieldDef(
            id="auth_type",
            label="Authentication",
            kc_key="auth_type",
            test_key="auth_type",
            type="enum",
            options=("none", "basic", "bearer"),
            importance="recommended",
            default="none",
            doc="None for local/dev. HTTP Basic for Confluent Cloud API key/secret or Apicurio basic. Bearer for Apicurio OIDC / Keycloak.",
            group="auth", order=5,
        ),
        FieldDef(
            id="username",
            label="Username",
            kc_key="username",
            test_key="username",
            importance="required",
            placeholder="API key or username",
            doc="HTTP Basic username. Confluent Cloud uses the API key here.",
            group="auth", order=10,
            visible_when={"field": "auth_type", "in": ["basic"]},
        ),
        FieldDef(
            id="password",
            label="Password",
            kc_key="password",
            test_key="password",
            type="password",
            secret=True,
            importance="required",
            placeholder="••••••••",
            doc="HTTP Basic password. Confluent Cloud uses the API secret here.",
            group="auth", order=20,
            visible_when={"field": "auth_type", "in": ["basic"]},
        ),
        FieldDef(
            id="token",
            label="Bearer Token",
            kc_key="token",
            test_key="token",
            type="password",
            secret=True,
            importance="required",
            placeholder="••••••••",
            doc="Sent as Authorization: Bearer. Typical for Apicurio with OIDC / Keycloak.",
            group="auth", order=30,
            visible_when={"field": "auth_type", "in": ["bearer"]},
        ),
    ),
)
