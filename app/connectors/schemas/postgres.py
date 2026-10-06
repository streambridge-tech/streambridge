"""Postgres source connection schema.

Fields cover the connection identity only (host, port, DB, credentials, SSL).
Pipeline-specific things (slot.name, topic.prefix, table.include.list) belong
on the pipeline's source config block, not on the Connection.
"""

from app.connectors.schemas.base import FieldDef, Schema


POSTGRES_SCHEMA = Schema(
    subtype="postgres",
    label="PostgreSQL",
    fields=(
        # ── Required: connection identity ──────────────────────────────────
        FieldDef(
            id="host",
            label="Host",
            kc_key="database.hostname",
            test_key="host",
            importance="required",
            placeholder="e.g. db.internal",
            doc="IP address or DNS name of the Postgres server.",
            group="connection", order=10,
        ),
        FieldDef(
            id="port",
            label="Port",
            kc_key="database.port",
            test_key="port",
            type="number",
            importance="required",
            default=5432,
            placeholder="5432",
            doc="TCP port for the Postgres server.",
            cast=int,
            group="connection", order=20,
        ),
        FieldDef(
            id="database",
            label="Database",
            kc_key="database.dbname",
            test_key="dbname",
            importance="required",
            placeholder="database name",
            doc="Name of the Postgres database to connect to.",
            group="connection", order=30,
        ),
        FieldDef(
            id="username",
            label="Username",
            kc_key="database.user",
            test_key="user",
            importance="required",
            placeholder="debezium",
            default="debezium",
            doc="Postgres role. Needs REPLICATION and CREATE privileges for CDC.",
            group="connection", order=40,
        ),
        FieldDef(
            id="password",
            label="Password",
            kc_key="database.password",
            test_key="password",
            type="password",
            secret=True,
            importance="required",
            placeholder="••••••••",
            doc="Password for the Postgres role.",
            group="connection", order=50,
        ),

        # ── Advanced: TLS / SSL ───────────────────────────────────────────
        FieldDef(
            id="ssl_mode",
            label="SSL Mode",
            kc_key="database.sslmode",
            test_key="sslmode",
            type="enum",
            options=("disable", "allow", "prefer", "require", "verify-ca", "verify-full"),
            importance="advanced",
            default="prefer",
            doc="How to negotiate TLS with the server. Managed clouds usually require 'require' or stricter.",
            group="tls", order=10,
        ),
        FieldDef(
            id="ssl_root_cert",
            label="SSL Root Certificate",
            kc_key="database.sslrootcert",
            test_key="sslrootcert",
            importance="advanced",
            placeholder="/etc/ssl/ca.crt",
            doc="Path (readable by both StreamBridge and Kafka Connect) to the CA bundle used to verify the server.",
            group="tls", order=20,
        ),
        FieldDef(
            id="ssl_cert",
            label="Client Certificate",
            kc_key="database.sslcert",
            test_key="sslcert",
            importance="advanced",
            placeholder="/etc/ssl/client.crt",
            doc="Client TLS certificate for mutual-TLS auth (rarely used).",
            group="tls", order=30,
        ),
        FieldDef(
            id="ssl_key",
            label="Client Key",
            kc_key="database.sslkey",
            test_key="sslkey",
            secret=True,
            importance="advanced",
            placeholder="/etc/ssl/client.key",
            doc="Client TLS private key for mutual-TLS auth.",
            group="tls", order=40,
        ),

        # ── Advanced: observability / tuning ──────────────────────────────
        FieldDef(
            id="application_name",
            label="Application Name",
            kc_key="database.applicationName",
            test_key="application_name",
            importance="advanced",
            default="streambridge",
            placeholder="streambridge",
            doc="Appears in pg_stat_activity so DBAs can identify connections from this pipeline.",
            group="tuning", order=10,
        ),
        FieldDef(
            id="connect_timeout_ms",
            label="Connect Timeout (ms)",
            kc_key="database.connectTimeoutMs",
            test_key="connect_timeout",
            # Debezium takes milliseconds; psycopg2 takes seconds. Round up so we
            # never pass 0 to psycopg2, which would mean "no timeout".
            test_transform=lambda ms: max(1, int(ms) // 1000),
            type="number",
            importance="advanced",
            default=10000,
            placeholder="10000",
            doc="Milliseconds to wait for the initial TCP handshake before failing.",
            cast=int,
            group="tuning", order=20,
        ),
        FieldDef(
            id="tcp_keep_alive",
            label="TCP Keep-Alive",
            kc_key="database.tcpKeepAlive",
            test_key="keepalives",
            type="boolean",
            importance="advanced",
            default=True,
            doc="Enable TCP keep-alive probes on the connection socket.",
            # Debezium takes boolean-ish string; psycopg2 keepalives takes int (0 or 1).
            cast=lambda v: "true" if str(v).lower() in ("true", "1", "yes", "on") else "false",
            test_transform=lambda v: 1 if str(v).lower() in ("true", "1", "yes", "on") else 0,
            group="tuning", order=30,
        ),
    ),
)
