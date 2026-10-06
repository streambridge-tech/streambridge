import unittest

from tests.unit.yaml_builder._fixtures import build, error_texts, s3_sink_yaml


class S3SinkCompileTests(unittest.TestCase):

    def _assert_failed_with(self, result, needle):
        self.assertFalse(result["ok"], msg=f"expected failure; logs={result['logs']}")
        texts = error_texts(result)
        self.assertTrue(
            any(needle in t for t in texts),
            msg=f"expected an error containing {needle!r}, got: {texts}",
        )

    def test_valid_s3_sink_with_topics(self):
        raw = s3_sink_yaml(
            "    topics: ecommerce.public.orders",
            sink_top_extra="\n  storage.connection: {{ var('s3_conn') }}",
        )
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")

    def test_valid_s3_sink_with_topics_regex(self):
        raw = s3_sink_yaml(
            "    topics.regex: ecommerce.public.*",
            sink_top_extra="\n  storage.connection: {{ var('s3_conn') }}",
        )
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")

    def test_missing_topics_and_topics_regex(self):
        raw = s3_sink_yaml(
            "    flush.size: 1000",
            sink_top_extra="\n  storage.connection: {{ var('s3_conn') }}",
        )
        self._assert_failed_with(build(raw), "sink.config.topics is not set")

    def test_no_storage_connection_requires_s3_credentials(self):
        raw = s3_sink_yaml("    topics.regex: ecommerce.public.*")
        self._assert_failed_with(build(raw), "aws.access.key.id is required")

    def test_storage_connection_present_skips_credentials_check(self):
        raw = s3_sink_yaml(
            "    topics.regex: ecommerce.public.*",
            sink_top_extra="\n  storage.connection: {{ var('s3_conn') }}",
        )
        result = build(raw)
        self.assertTrue(result["ok"], msg=f"expected ok; logs={result['logs']}")
        success_texts = [log["text"] for log in result["logs"] if log["level"] == "success"]
        self.assertTrue(
            any("storage.connection present" in t for t in success_texts),
            msg=f"expected storage.connection acknowledgement; got: {success_texts}",
        )


if __name__ == "__main__":
    unittest.main()
