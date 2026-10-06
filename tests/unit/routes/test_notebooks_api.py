import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.routes.notebooks_api import notebooks_api


def _client():
    app = Flask(__name__)
    app.register_blueprint(notebooks_api)
    return app.test_client()


class TestNotebooksApi(unittest.TestCase):
    def setUp(self):
        self.client = _client()
        self.session_patch = patch("app.routes.notebooks_api.SessionLocal")
        self.mock_session = self.session_patch.start()
        self.db = MagicMock()
        self.mock_session.return_value.__enter__.return_value = self.db
        self.mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)

    def test_create_requires_name(self):
        r = self.client.post("/api/notebooks/", json={"folder": "orders"})
        self.assertEqual(r.status_code, 400)

    def test_get_missing_404(self):
        self.db.get.return_value = None
        r = self.client.get("/api/notebooks/nope")
        self.assertEqual(r.status_code, 404)
