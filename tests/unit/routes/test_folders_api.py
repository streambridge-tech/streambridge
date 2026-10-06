import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.routes.folders_api import folders_api


def _client():
    app = Flask(__name__)
    app.register_blueprint(folders_api)
    return app.test_client()


class TestFoldersApi(unittest.TestCase):
    def setUp(self):
        self.client = _client()
        self.session_patch = patch("app.routes.folders_api.SessionLocal")
        self.mock_session = self.session_patch.start()
        self.db = MagicMock()
        self.mock_session.return_value.__enter__.return_value = self.db
        self.mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)
        self.db.query.return_value.all.return_value = []

    def test_create_requires_name(self):
        response = self.client.post("/api/folders/", json={"path": ""})
        self.assertEqual(response.status_code, 400)

    def test_create_stores_path(self):
        response = self.client.post("/api/folders/", json={"path": "orders"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["path"], "orders")
        self.db.add.assert_called()
        self.db.commit.assert_called()

    def test_create_rejects_parent_dotdot(self):
        response = self.client.post("/api/folders/", json={"path": "orders/../secrets"})
        self.assertEqual(response.status_code, 400)
