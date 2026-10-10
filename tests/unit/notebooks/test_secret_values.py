"""Vault secrets are substituted as values, never spliced into JSON text."""

import unittest
from types import SimpleNamespace

from app.services.notebooks.secrets import SecretResolver


def _resolver(**secrets):
    rows = [{"key": key, "value": value, "masked": True} for key, value in secrets.items()]
    return SecretResolver([SimpleNamespace(name="prod", vars=rows)])


class TestSecretValues(unittest.TestCase):
    def test_secret_with_a_quote_resolves_verbatim(self):
        resolved, missing, refs = _resolver(DB_PASSWORD='pa"ss').resolve_config(
            {"database.password": "{prod.DB_PASSWORD}"}
        )
        self.assertEqual(resolved["database.password"], 'pa"ss')
        self.assertEqual((missing, refs), ([], 1))

    def test_secret_with_a_backslash_resolves_verbatim(self):
        resolved, _missing, _refs = _resolver(DIR="C:\\temp").resolve_config({"dir": "{prod.DIR}"})
        self.assertEqual(resolved["dir"], "C:\\temp")

    def test_secret_cannot_inject_or_override_keys(self):
        payload = 'x","connector.class":"evil'
        resolved, _missing, _refs = _resolver(DB_PASSWORD=payload).resolve_config({
            "database.password": "{prod.DB_PASSWORD}",
            "connector.class": "io.debezium.connector.mysql.MySqlConnector",
        })
        self.assertEqual(resolved, {
            "database.password": payload,
            "connector.class": "io.debezium.connector.mysql.MySqlConnector",
        })

    def test_token_inside_a_longer_string_is_substituted(self):
        resolved, _missing, refs = _resolver(USER="dbz", HOST="db").resolve_config(
            {"url": "jdbc:mysql://{prod.USER}@{prod.HOST}:3306"}
        )
        self.assertEqual(resolved["url"], "jdbc:mysql://dbz@db:3306")
        self.assertEqual(refs, 2)

    def test_missing_tokens_are_reported_and_left_in_place(self):
        resolved, missing, refs = _resolver(USER="dbz").resolve_config({
            "database.user": "{prod.USER}",
            "database.password": "{prod.DB_PASSWORD}",
        })
        self.assertEqual(missing, ["prod.DB_PASSWORD"])
        self.assertEqual(refs, 2)
        self.assertEqual(resolved["database.password"], "{prod.DB_PASSWORD}")

    def test_nested_dicts_and_lists_are_resolved(self):
        resolved, missing, refs = _resolver(A='a"1', B="b\\2").resolve_config({
            "outer": {"inner": "{prod.A}", "items": ["{prod.B}", 5, None, {"deep": "{prod.A}"}]},
            "tasks.max": 1,
            "enabled": True,
        })
        self.assertEqual(resolved, {
            "outer": {"inner": 'a"1', "items": ["b\\2", 5, None, {"deep": 'a"1'}]},
            "tasks.max": 1,
            "enabled": True,
        })
        self.assertEqual((missing, refs), ([], 3))

    def test_input_config_is_not_mutated(self):
        config = {"outer": {"password": "{prod.A}"}}
        _resolver(A="s3cret").resolve_config(config)
        self.assertEqual(config, {"outer": {"password": "{prod.A}"}})


if __name__ == "__main__":
    unittest.main()
