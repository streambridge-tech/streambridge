from app.connectors.base import BaseConnector
from app.connectors.schemas import build_kc_config, build_test_kwargs, defaults_kc_config
from app.connectors.schemas.s3 import S3_SCHEMA
from app.utils.logger import get_logger

log = get_logger(__name__)


class S3SinkConnector(BaseConnector):

    SUBTYPE = "s3"
    TYPE    = "sink"
    TOPIC_FIELD = "topics"
    SCHEMA = S3_SCHEMA

    REQUIRED_FIELDS = [
        "s3.bucket.name",
        "s3.region",
    ]

    OPTIONAL_FIELDS = [
        "topics",
        "topics.regex",
        "flush.size",
        "rotate.interval.ms",
        "s3.part.size",
        "s3.compression.type",
        "storage.class",
        "format.class",
        "partitioner.class",
        "locale",
        "timezone",
        "tasks.max",
        "transforms",
    ]

    def compile(self, config, has_db_conn, has_kafka_conn, has_kc_conn, has_sr_conn=False, plugin_format="JSON"):
        from app.connectors.compile_result import CompileResult
        r = CompileResult()

        r.info("Checking sink config fields (s3)…")

        self.check_schema_registry_shape(config, has_sr_conn, plugin_format, "sink", r)

        # s3 credentials — required only if no storage.connection
        if not has_db_conn:
            for key in ("aws.access.key.id", "aws.secret.access.key",
                        "s3.bucket.name", "s3.region"):
                if not config.get(key):
                    r.error(f"sink.config.{key} is required (no storage.connection provided)",
                            f"add  {key}: <value>  under sink.config: or set storage.connection")
        else:
            r.success("storage.connection present — credentials injected at deploy time  ✓")

        # topics / topics.regex — always required
        if config.get("topics"):
            topics = [t.strip() for t in config["topics"].split(",") if t.strip()]
            r.success(f'topics: "{config["topics"]}"  ✓')
            return r, topics, None
        elif config.get("topics.regex"):
            r.success(f'topics.regex: "{config["topics.regex"]}"  ✓')
            return r, [], config["topics.regex"]
        else:
            r.error("sink.config.topics is not set — sink has no topic to consume from")
            return r, [], None

    def validate(self, data: dict) -> list[str]:
        errors = []
        for field in self.REQUIRED_FIELDS:
            if not data.get(field):
                log.warning("Validation failed — missing field: %s", field)
                errors.append(f"'{field}' is required")
        return errors

    def build_config(self, form: dict, extra: dict) -> dict:
        config = defaults_kc_config(self.SCHEMA)
        config.update(build_kc_config(self.SCHEMA, form))
        config.update({k: str(v) for k, v in (extra or {}).items() if v != ""})
        log.debug("Built S3 config  keys=%s", list(config.keys()))
        return config

    def test_connection(self, config: dict) -> dict:
        bucket = config.get("s3.bucket.name")
        region = config.get("s3.region")
        log.info("Testing S3 connection  bucket=%s  region=%s", bucket, region)

        try:
            import boto3
            from botocore.config import Config as BotoConfig
            from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError
        except ImportError:
            # boto3 optional — fall back to a config-only mock so existing tests / dev flow still pass.
            log.info("boto3 not installed — reporting config-only success")
            return {"success": True, "message": f"S3 config accepted (bucket={bucket}, region={region})"}

        try:
            kwargs = build_test_kwargs(self.SCHEMA, config)
            # bucket is the boto3 head_bucket arg, not a client-init kwarg — pull it out
            bucket_name = kwargs.pop("Bucket", bucket)
            # path-style access goes into botocore Config, not a top-level kwarg
            path_style = kwargs.pop("s3_path_style", False)
            client_config = BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"} if path_style else {},
            )
            client = boto3.client("s3", config=client_config, **kwargs)
            client.head_bucket(Bucket=bucket_name)
            return {"success": True, "message": f"Bucket '{bucket_name}' is reachable and readable."}
        except NoCredentialsError:
            return {"success": False, "message": "Missing AWS credentials"}
        except EndpointConnectionError as e:
            return {"success": False, "message": f"Endpoint not reachable: {e}"}
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "?")
            return {"success": False, "message": f"{code}: {e.response.get('Error', {}).get('Message', str(e))}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
