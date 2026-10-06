import unittest

from app.connectors.schemas import SECRET_MASK, build_kc_config, get_schema
from app.models.connection import Connection


class SecretMaskingTests(unittest.TestCase):
    def test_schema_connection_masks_secret_in_config(self):
        schema = get_schema("postgres")
        secret_field = next(f for f in schema.fields if f.secret and f.kc_key)
        conn = Connection(
            name="pg", type="source", subtype="postgres",
            status="draft", used_in=[],
            config={secret_field.kc_key: "super-secret-pw", "database.hostname": "db"},
        )
        import datetime
        conn.created_at = conn.updated_at = datetime.datetime.now(datetime.timezone.utc)
        d = conn.to_dict()
        self.assertEqual(d["config"][secret_field.kc_key], SECRET_MASK)
        self.assertEqual(d["config"]["database.hostname"], "db")
        self.assertEqual(d["deployConfig"][secret_field.kc_key], SECRET_MASK)
        # No secret appears anywhere in the serialized payload.
        self.assertNotIn("super-secret-pw", str(d))

    def test_generic_connection_masks_password_and_token(self):
        conn = Connection(
            name="slack", type="notification", subtype="notification-slack",
            status="draft", used_in=[],
            config={"host": "https://hooks.slack.com", "password": "/services/T/B/xxx", "token": "abc"},
        )
        import datetime
        conn.created_at = conn.updated_at = datetime.datetime.now(datetime.timezone.utc)
        d = conn.to_dict()
        self.assertEqual(d["config"]["password"], SECRET_MASK)
        self.assertEqual(d["config"]["token"], SECRET_MASK)
        self.assertEqual(d["config"]["host"], "https://hooks.slack.com")
        self.assertNotIn("/services/T/B/xxx", str(d))

    def test_masked_value_is_stripped_on_write(self):
        schema = get_schema("postgres")
        secret_field = next(f for f in schema.fields if f.secret and f.kc_key)
        # Simulate a form that echoes the mask back for the secret field.
        form = {secret_field.id: SECRET_MASK, "database.hostname": "db"}
        cfg = build_kc_config(schema, form)
        self.assertNotIn(secret_field.kc_key, cfg)


if __name__ == "__main__":
    unittest.main()
