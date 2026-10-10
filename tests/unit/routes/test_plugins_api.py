import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.utils.db import Base
from app.models.plugin import Plugin
from app.routes.plugins_api import plugins_api


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Plugin.__table__])
    return sessionmaker(bind=engine)()


class PluginApiTests(unittest.TestCase):
    def setUp(self):
        self.db = _session()
        app = Flask(__name__)
        app.register_blueprint(plugins_api)
        self.client = app.test_client()
        self.session_patch = patch("app.routes.plugins_api.SessionLocal")
        mock_session = self.session_patch.start()
        mock_session.return_value.__enter__.return_value = self.db
        mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.db.close)

    def _add(self, name, *, builtin=False):
        self.db.add(Plugin(
            name=name,
            db="PostgreSQL",
            type="source",
            format="JSON",
            description="test",
            config=json.dumps({"connector.class": "x"}),
            is_builtin=builtin,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        self.db.commit()

    def test_list_plugins(self):
        self._add("postgres-json", builtin=True)
        r = self.client.get("/api/plugins")
        self.assertEqual(r.status_code, 200)
        names = [p["name"] for p in r.get_json()]
        self.assertIn("postgres-json", names)

    def test_builtin_cannot_be_edited(self):
        self._add("postgres-json", builtin=True)
        r = self.client.put("/api/plugins/postgres-json", json={"description": "nope"})
        self.assertEqual(r.status_code, 403)

    def test_builtin_cannot_be_deleted(self):
        self._add("postgres-json", builtin=True)
        r = self.client.delete("/api/plugins/postgres-json")
        self.assertEqual(r.status_code, 403)

    def test_custom_create_update_delete(self):
        r = self.client.post("/api/plugins", json={
            "name": "my-source",
            "type": "source",
            "format": "JSON",
            "db": "PostgreSQL",
            "config": {"connector.class": "demo"},
        })
        self.assertEqual(r.status_code, 201)
        r = self.client.put("/api/plugins/my-source", json={"description": "ok"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["description"], "ok")
        r = self.client.delete("/api/plugins/my-source")
        self.assertEqual(r.status_code, 200)

    def _create(self, config):
        return self.client.post("/api/plugins", json={
            "name": "my-source", "type": "source", "format": "JSON", "config": config,
        })

    def test_create_rejects_config_that_is_not_an_object(self):
        for config in ([1], 5, "[1]", "5", "null", '"text"'):
            with self.subTest(config=config):
                r = self._create(config)
                self.assertEqual(r.status_code, 400)
                self.assertIn("'config' must be a JSON object", r.get_json()["error"])
        self.assertIsNone(self.db.get(Plugin, "my-source"))

    def test_create_accepts_object_config_as_json_text(self):
        r = self._create('{"connector.class": "demo"}')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["config"], {"connector.class": "demo"})

    def test_update_rejects_config_that_is_not_an_object(self):
        self.assertEqual(self._create({"connector.class": "demo"}).status_code, 201)
        for config in (None, [1], 5, "[1]", "null"):
            with self.subTest(config=config):
                r = self.client.put("/api/plugins/my-source", json={"config": config})
                self.assertEqual(r.status_code, 400)
                self.assertIn("'config' must be a JSON object", r.get_json()["error"])
        self.assertEqual(json.loads(self.db.get(Plugin, "my-source").config), {"connector.class": "demo"})

    def test_create_and_update_reject_a_body_that_is_not_an_object(self):
        self.assertEqual(self._create({"connector.class": "demo"}).status_code, 201)
        for body in ([1], ["my-source"], "text", 5):
            with self.subTest(body=body):
                r = self.client.post("/api/plugins", json=body)
                self.assertEqual(r.status_code, 400)
                self.assertIn("JSON object", r.get_json()["error"])
                r = self.client.put("/api/plugins/my-source", json=body)
                self.assertEqual(r.status_code, 400)
                self.assertIn("JSON object", r.get_json()["error"])
