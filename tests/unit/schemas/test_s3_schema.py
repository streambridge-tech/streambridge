"""S3 schema tests — locks Connect key + boto3 kwarg spelling."""
import unittest

from app.connectors.schemas import build_kc_config, build_test_kwargs
from app.connectors.schemas.s3 import S3_SCHEMA


class TestS3SchemaIdentity(unittest.TestCase):

    def test_subtype(self):
        self.assertEqual(S3_SCHEMA.subtype, "s3")

    def test_required_field_ids(self):
        ids = {f.id for f in S3_SCHEMA.required_fields()}
        self.assertEqual(ids, {"bucket", "region", "access_key", "secret_key"})

    def test_kc_keys_are_unique(self):
        kc_keys = [f.kc_key for f in S3_SCHEMA.fields if f.kc_key]
        self.assertEqual(len(kc_keys), len(set(kc_keys)))

    def test_connect_key_spelling(self):
        expected = {
            "bucket":            "s3.bucket.name",
            "region":            "s3.region",
            "access_key":        "aws.access.key.id",
            "secret_key":        "aws.secret.access.key",
            "session_token":     "aws.session.token",
            "endpoint_url":      "store.url",
            "path_style_access": "s3.path.style.access.enabled",
            "signature_version": "s3.signature.version",
        }
        for field_id, kc_key in expected.items():
            f = S3_SCHEMA.get(field_id)
            self.assertIsNotNone(f, f"missing field: {field_id}")
            self.assertEqual(f.kc_key, kc_key)

    def test_boto3_kwarg_spelling(self):
        expected = {
            "bucket":            "Bucket",              # per-call head_bucket arg
            "region":            "region_name",
            "access_key":        "aws_access_key_id",
            "secret_key":        "aws_secret_access_key",
            "session_token":     "aws_session_token",
            "endpoint_url":      "endpoint_url",
            "path_style_access": "s3_path_style",       # consumed by connector, not boto3 directly
        }
        for field_id, test_key in expected.items():
            self.assertEqual(S3_SCHEMA.get(field_id).test_key, test_key)

    def test_secret_key_is_secret(self):
        self.assertTrue(S3_SCHEMA.get("secret_key").secret)
        self.assertTrue(S3_SCHEMA.get("session_token").secret)
        self.assertFalse(S3_SCHEMA.get("access_key").secret)


class TestS3ConfigBuild(unittest.TestCase):

    def _form(self, **overrides):
        base = {"bucket": "cdc-bkt", "region": "us-east-1",
                "access_key": "AKIA", "secret_key": "shh"}
        base.update(overrides)
        return base

    def test_required_flat_map(self):
        cfg = build_kc_config(S3_SCHEMA, self._form())
        self.assertEqual(cfg["s3.bucket.name"], "cdc-bkt")
        self.assertEqual(cfg["s3.region"], "us-east-1")
        self.assertEqual(cfg["aws.access.key.id"], "AKIA")
        self.assertEqual(cfg["aws.secret.access.key"], "shh")

    def test_path_style_bool_cast_to_string(self):
        cfg = build_kc_config(S3_SCHEMA, self._form(path_style_access="true"))
        self.assertEqual(cfg["s3.path.style.access.enabled"], "true")

    def test_path_style_test_transform_to_bool(self):
        cfg = build_kc_config(S3_SCHEMA, self._form(path_style_access="true"))
        kwargs = build_test_kwargs(S3_SCHEMA, cfg)
        self.assertIs(kwargs["s3_path_style"], True)

    def test_endpoint_url_forwarded_to_test(self):
        cfg = build_kc_config(S3_SCHEMA, self._form(endpoint_url="https://minio:9000"))
        kwargs = build_test_kwargs(S3_SCHEMA, cfg)
        self.assertEqual(kwargs["endpoint_url"], "https://minio:9000")


if __name__ == "__main__":
    unittest.main()
