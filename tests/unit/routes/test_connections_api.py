import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.connection import Connection
from app.routes.connections_api import connections_api
from app.utils.db import Base


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Connection.__table__])
    return sessionmaker(bind=engine)()


class ConnectionsApiRetiredTypesTests(unittest.TestCase):
    def setUp(self):
        self.db = _session()
        app = Flask(__name__)
        app.register_blueprint(connections_api)
        self.client = app.test_client()
        self.session_patch = patch("app.routes.connections_api.SessionLocal")
        mock_session = self.session_patch.start()
        mock_session.return_value.__enter__.return_value = self.db
        mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.db.close)

    def test_post_postgres_source_is_rejected(self):
        r = self.client.post("/api/connections", json={
            "name": "pg-prod",
            "type": "source",
            "subtype": "postgres",
            "host": "db.internal",
            "port": 5432,
            "database": "orders",
            "username": "cdc",
            "password": "x",
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("retired", (r.get_json() or {}).get("error", "").lower())
        self.assertEqual(self.db.query(Connection).count(), 0)

    def test_post_s3_sink_is_rejected(self):
        r = self.client.post("/api/connections", json={
            "name": "lake",
            "type": "sink",
            "subtype": "s3",
        })
        self.assertEqual(r.status_code, 400)

    def test_test_mysql_is_rejected(self):
        r = self.client.post("/api/connections/test", json={
            "type": "source",
            "subtype": "mysql",
            "host": "db",
        })
        self.assertEqual(r.status_code, 400)

    def test_put_existing_postgres_is_rejected(self):
        row = Connection(
            name="legacy-pg",
            type="source",
            subtype="postgres",
            status="draft",
            used_in=[],
            config={"database.hostname": "db"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        r = self.client.put(f"/api/connections/{row.id}", json={"name": "legacy-pg-2"})
        self.assertEqual(r.status_code, 400)
