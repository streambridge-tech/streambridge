import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.utils.db import Base
from app.models.vault import Vault
from app.routes.vaults_api import vaults_api
from app.utils.vaults import merge_vars, resolve_internal, resolve_public


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Vault.__table__])
    return sessionmaker(bind=engine)()


class VaultApiTests(unittest.TestCase):
    def setUp(self):
        self.db = _session()
        app = Flask(__name__)
        app.register_blueprint(vaults_api)
        self.client = app.test_client()
        self.session_patch = patch("app.routes.vaults_api.SessionLocal")
        mock_session = self.session_patch.start()
        mock_session.return_value.__enter__.return_value = self.db
        mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.db.close)

    def _seed(self):
        self.db.add(Vault(
            name="prod",
            vars=[
                {"key": "DB_HOST", "value": "pg.internal", "masked": False},
                {"key": "DB_PASSWORD", "value": "super-secret", "masked": True},
            ],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        self.db.commit()

    def test_list_hides_masked_values(self):
        self._seed()
        r = self.client.get("/api/secrets")
        self.assertEqual(r.status_code, 200)
        prod = r.get_json()[0]
        by_key = {v["key"]: v for v in prod["vars"]}
        self.assertEqual(by_key["DB_HOST"]["value"], "pg.internal")
        self.assertTrue(by_key["DB_PASSWORD"]["masked"])
        self.assertTrue(by_key["DB_PASSWORD"]["hasValue"])
        self.assertNotIn("value", by_key["DB_PASSWORD"])

    def test_create_and_put_vars(self):
        r = self.client.post("/api/secrets", json={"name": "dev"})
        self.assertEqual(r.status_code, 201)
        r = self.client.put("/api/secrets/dev", json={
            "vars": [
                {"key": "xyz", "value": "dev-xyz", "masked": False},
                {"key": "TOKEN", "value": "abcdefgh", "masked": True},
            ],
        })
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["vars"][0]["value"], "dev-xyz")
        self.assertNotIn("value", body["vars"][1])

    def test_masked_keep_on_blank_put(self):
        self._seed()
        r = self.client.put("/api/secrets/prod", json={
            "vars": [
                {"key": "DB_HOST", "value": "pg.internal", "masked": False},
                {"key": "DB_PASSWORD", "masked": True},
            ],
        })
        self.assertEqual(r.status_code, 200)
        stored = self.db.get(Vault, "prod")
        pwd = next(v for v in stored.vars if v["key"] == "DB_PASSWORD")
        self.assertEqual(pwd["value"], "super-secret")

    def test_resolve_leaves_masked_tokens(self):
        self._seed()
        r = self.client.post("/api/secrets/resolve", json={
            "text": "host={prod.DB_HOST} pass={prod.DB_PASSWORD} miss={prod.NOPE}",
        })
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["text"], "host=pg.internal pass={prod.DB_PASSWORD} miss={prod.NOPE}")
        self.assertEqual(data["missing"], ["prod.NOPE"])
        self.assertEqual(data["redacted"], ["prod.DB_PASSWORD"])

    def test_delete_refuses_when_not_empty(self):
        self._seed()
        r = self.client.delete("/api/secrets/prod")
        self.assertEqual(r.status_code, 409)

    def test_delete(self):
        self._seed()
        self.client.put("/api/secrets/prod", json={"vars": []})
        r = self.client.delete("/api/secrets/prod")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/secrets/prod").status_code, 404)

    def test_invalid_name(self):
        r = self.client.post("/api/secrets", json={"name": "1prod"})
        self.assertEqual(r.status_code, 400)


class VaultMergeTests(unittest.TestCase):
    def test_masked_allows_short_value(self):
        merged, err = merge_vars([], [{"key": "T", "value": "123", "masked": True}])
        self.assertIsNone(err)
        self.assertEqual(merged[0]["value"], "123")
        self.assertTrue(merged[0]["masked"])

    def test_internal_resolve_includes_masked(self):
        vaults = {"prod": [{"key": "DB_PASSWORD", "value": "super-secret", "masked": True}]}
        text, missing = resolve_internal("p={prod.DB_PASSWORD}", vaults)
        self.assertEqual(text, "p=super-secret")
        self.assertEqual(missing, [])
        public = resolve_public("p={prod.DB_PASSWORD}", vaults)
        self.assertEqual(public["text"], "p={prod.DB_PASSWORD}")
