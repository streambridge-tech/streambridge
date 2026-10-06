"""S3 sink connection schema.

Covers vanilla AWS S3 plus S3-compatible endpoints (MinIO local, Cloudflare R2,
Backblaze B2). Advanced fields target the last group: `endpoint_url` overrides
where boto3 talks to, `path_style_access` toggles URL style needed by MinIO/R2.
"""

from app.connectors.schemas.base import FieldDef, Schema


S3_SCHEMA = Schema(
    subtype="s3",
    label="Amazon S3 / S3-compatible",
    fields=(
        # ── Required: bucket & auth ────────────────────────────────────────
        FieldDef(
            id="bucket",
            label="Bucket",
            kc_key="s3.bucket.name",
            # boto3.head_bucket takes the bucket name per-call, not on client init.
            # Use a synthetic test_key that the S3SinkConnector.test_connection reads.
            test_key="Bucket",
            importance="required",
            placeholder="my-cdc-bucket",
            doc="Target S3 bucket. Must already exist.",
            group="connection", order=10,
        ),
        FieldDef(
            id="region",
            label="Region",
            kc_key="s3.region",
            test_key="region_name",
            importance="required",
            placeholder="us-east-1",
            default="us-east-1",
            doc="AWS region. Use 'auto' for Cloudflare R2.",
            group="connection", order=20,
        ),
        FieldDef(
            id="access_key",
            label="Access Key ID",
            kc_key="aws.access.key.id",
            test_key="aws_access_key_id",
            importance="required",
            placeholder="AKIAIOSFODNN7EXAMPLE",
            doc="AWS access key. For R2 use an R2 API token access key.",
            group="connection", order=30,
        ),
        FieldDef(
            id="secret_key",
            label="Secret Access Key",
            kc_key="aws.secret.access.key",
            test_key="aws_secret_access_key",
            type="password",
            secret=True,
            importance="required",
            placeholder="••••••••",
            doc="AWS secret key matching the access key ID.",
            group="connection", order=40,
        ),
        FieldDef(
            id="session_token",
            label="Session Token",
            kc_key="aws.session.token",
            test_key="aws_session_token",
            type="password",
            secret=True,
            importance="advanced",
            placeholder="(temporary STS credentials)",
            doc="Only required when using temporary credentials from AWS STS (AssumeRole, SSO, federated login). Leave blank for long-lived IAM user access keys.",
            group="connection", order=50,
        ),

        # ── Advanced: S3-compatible endpoints ─────────────────────────────
        FieldDef(
            id="endpoint_url",
            label="Endpoint URL",
            kc_key="store.url",
            test_key="endpoint_url",
            importance="advanced",
            placeholder="https://<accountid>.r2.cloudflarestorage.com",
            doc="Override for S3-compatible services. Leave blank for AWS S3. "
                "Examples: R2 (https://<id>.r2.cloudflarestorage.com), "
                "MinIO (http://minio:9000).",
            group="endpoint", order=10,
        ),
        FieldDef(
            id="path_style_access",
            label="Path-style URLs",
            kc_key="s3.path.style.access.enabled",
            # boto3 sets this via botocore Config, not a top-level kwarg.
            # S3SinkConnector.test_connection reads this to build the Config.
            test_key="s3_path_style",
            type="boolean",
            importance="advanced",
            default=False,
            doc="Enable for MinIO or older S3-compatible services. Modern R2/AWS use virtual-hosted URLs.",
            cast=lambda v: "true" if str(v).lower() in ("true", "1", "yes", "on") else "false",
            test_transform=lambda v: str(v).lower() in ("true", "1", "yes", "on"),
            group="endpoint", order=20,
        ),

        # ── Advanced: tuning ──────────────────────────────────────────────
        FieldDef(
            id="signature_version",
            label="Signature Version",
            kc_key="s3.signature.version",
            test_key=None,
            type="enum",
            options=("v4", "v2"),
            importance="advanced",
            default="v4",
            doc="Modern services (AWS, R2) require v4. v2 is only for very old S3-compatible endpoints.",
            group="endpoint", order=30,
        ),
    ),
)
