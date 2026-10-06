"""Tests for the shared schema primitives.

Covers FieldDef / Schema behavior and the two bidirectional helpers
(build_kc_config, build_test_kwargs) independently of any specific
connector schema so the pattern is proven before we spread it.
"""
import unittest

from app.connectors.schemas import (
    FieldDef,
    Schema,
    build_kc_config,
    build_test_kwargs,
    defaults_kc_config,
)


_SAMPLE_SCHEMA = Schema(
    subtype="testdb",
    label="TestDB",
    fields=(
        FieldDef(id="host",   label="Host", kc_key="db.hostname", test_key="host",
                 importance="required"),
        FieldDef(id="port",   label="Port", kc_key="db.port",     test_key="port",
                 type="number", cast=int, default=5432, importance="required"),
        FieldDef(id="user",   label="User", kc_key="db.user",     test_key="user",
                 importance="required"),
        FieldDef(id="pw",     label="Password", kc_key="db.password", test_key="password",
                 secret=True, importance="required"),
        FieldDef(id="ssl",    label="SSL", kc_key="db.sslmode",   test_key="sslmode",
                 type="enum", options=("disable", "require"), default="require",
                 importance="advanced"),
        FieldDef(id="timeout_ms", label="Timeout (ms)",
                 kc_key="db.timeoutMs", test_key="connect_timeout",
                 cast=int, test_transform=lambda ms: max(1, int(ms) // 1000),
                 importance="advanced"),
        # Field with no test_key: only Kafka Connect needs it, not the test lib.
        FieldDef(id="slot",   label="Slot", kc_key="db.slot",
                 importance="advanced"),
        # Field with no kc_key: pure UI field (shouldn't appear in kc config).
        FieldDef(id="comment", label="Comment",
                 importance="advanced"),
    ),
)


class TestSchemaAccessors(unittest.TestCase):

    def test_get_returns_field_by_id(self):
        f = _SAMPLE_SCHEMA.get("host")
        self.assertIsNotNone(f)
        self.assertEqual(f.kc_key, "db.hostname")

    def test_get_returns_none_for_unknown(self):
        self.assertIsNone(_SAMPLE_SCHEMA.get("nonexistent"))

    def test_by_kc_key(self):
        f = _SAMPLE_SCHEMA.by_kc_key("db.timeoutMs")
        self.assertIsNotNone(f)
        self.assertEqual(f.id, "timeout_ms")

    def test_required_fields_only_required(self):
        req_ids = [f.id for f in _SAMPLE_SCHEMA.required_fields()]
        self.assertEqual(sorted(req_ids), ["host", "port", "pw", "user"])

    def test_advanced_fields_only_advanced(self):
        adv_ids = [f.id for f in _SAMPLE_SCHEMA.advanced_fields()]
        self.assertEqual(sorted(adv_ids), ["comment", "slot", "ssl", "timeout_ms"])


class TestBuildKcConfig(unittest.TestCase):

    def test_maps_form_ids_to_kc_keys(self):
        form = {"host": "db.local", "port": "5432", "user": "alice", "pw": "secret"}
        cfg = build_kc_config(_SAMPLE_SCHEMA, form)
        self.assertEqual(cfg, {
            "db.hostname": "db.local",
            "db.port":     5432,          # cast applied
            "db.user":     "alice",
            "db.password": "secret",
        })

    def test_applies_cast_to_numeric(self):
        cfg = build_kc_config(_SAMPLE_SCHEMA, {"port": "8080"})
        self.assertEqual(cfg["db.port"], 8080)
        self.assertIsInstance(cfg["db.port"], int)

    def test_skips_empty_and_none(self):
        cfg = build_kc_config(_SAMPLE_SCHEMA, {"host": "", "port": None, "user": "alice"})
        self.assertNotIn("db.hostname", cfg)
        self.assertNotIn("db.port", cfg)
        self.assertEqual(cfg["db.user"], "alice")

    def test_ignores_fields_without_kc_key(self):
        cfg = build_kc_config(_SAMPLE_SCHEMA, {"comment": "leave me be", "host": "x"})
        self.assertNotIn("comment", cfg)
        self.assertEqual(cfg["db.hostname"], "x")

    def test_ignores_unknown_form_keys(self):
        cfg = build_kc_config(_SAMPLE_SCHEMA, {"nonsense": "junk", "host": "x"})
        self.assertNotIn("nonsense", cfg)
        self.assertEqual(cfg, {"db.hostname": "x"})

    def test_bad_cast_falls_back_to_string(self):
        # 'not-a-number' can't be int-cast; we preserve the raw string so validate() can flag it
        cfg = build_kc_config(_SAMPLE_SCHEMA, {"port": "not-a-number"})
        self.assertEqual(cfg["db.port"], "not-a-number")


class TestBuildTestKwargs(unittest.TestCase):

    def _config(self):
        return {
            "db.hostname":  "db.internal",
            "db.port":      5432,
            "db.user":      "alice",
            "db.password":  "secret",
            "db.sslmode":   "require",
            "db.timeoutMs": 10000,
            "db.slot":      "streambridge_slot",   # kc-only field, no test_key
        }

    def test_maps_kc_keys_to_test_keys(self):
        kwargs = build_test_kwargs(_SAMPLE_SCHEMA, self._config())
        self.assertEqual(kwargs["host"],     "db.internal")
        self.assertEqual(kwargs["port"],     5432)
        self.assertEqual(kwargs["user"],     "alice")
        self.assertEqual(kwargs["password"], "secret")
        self.assertEqual(kwargs["sslmode"],  "require")

    def test_test_transform_applied(self):
        kwargs = build_test_kwargs(_SAMPLE_SCHEMA, self._config())
        # 10000 ms → 10 seconds
        self.assertEqual(kwargs["connect_timeout"], 10)

    def test_test_transform_guards_against_zero(self):
        cfg = {"db.timeoutMs": 500}   # 500 ms → 0 sec without guard
        kwargs = build_test_kwargs(_SAMPLE_SCHEMA, cfg)
        self.assertEqual(kwargs["connect_timeout"], 1)  # clamped to 1

    def test_skips_missing_and_empty(self):
        kwargs = build_test_kwargs(_SAMPLE_SCHEMA, {"db.hostname": "x"})
        self.assertEqual(kwargs, {"host": "x"})

    def test_kc_only_fields_not_included(self):
        kwargs = build_test_kwargs(_SAMPLE_SCHEMA, self._config())
        # slot is kc-only (no test_key) so it must not leak into test kwargs
        self.assertNotIn("slot", kwargs)
        self.assertNotIn("db.slot", kwargs)


class TestDefaults(unittest.TestCase):

    def test_defaults_kc_config(self):
        defaults = defaults_kc_config(_SAMPLE_SCHEMA)
        self.assertEqual(defaults["db.port"],    5432)
        self.assertEqual(defaults["db.sslmode"], "require")
        # fields without a default are not present
        self.assertNotIn("db.hostname", defaults)


class TestSchemaJsonView(unittest.TestCase):

    def test_field_to_json_omits_callables(self):
        f = _SAMPLE_SCHEMA.get("timeout_ms")
        j = f.to_json()
        # Callables must not leak into JSON
        self.assertNotIn("cast", j)
        self.assertNotIn("test_transform", j)
        # But the primary attrs are there
        self.assertEqual(j["id"], "timeout_ms")
        self.assertEqual(j["kcKey"], "db.timeoutMs")
        self.assertEqual(j["testKey"], "connect_timeout")

    def test_schema_to_json_groups_required_advanced(self):
        j = _SAMPLE_SCHEMA.to_json()
        self.assertEqual(j["subtype"], "testdb")
        req_ids = [f["id"] for f in j["required"]]
        adv_ids = [f["id"] for f in j["advanced"]]
        self.assertEqual(sorted(req_ids), ["host", "port", "pw", "user"])
        self.assertIn("ssl", adv_ids)
        self.assertIn("timeout_ms", adv_ids)
        self.assertEqual(j["recommended"], [])

    def test_visible_when_serialized(self):
        field = FieldDef(
            id="token",
            label="Token",
            kc_key="token",
            visible_when={"field": "auth_type", "in": ["bearer"]},
        )
        self.assertEqual(field.to_json()["visibleWhen"]["in"], ["bearer"])


if __name__ == "__main__":
    unittest.main()
