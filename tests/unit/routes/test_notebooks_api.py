import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.routes.notebooks_api import notebooks_api


def _client():
    app = Flask(__name__)
    app.register_blueprint(notebooks_api)
    return app.test_client()


class _NotebooksApiCase(unittest.TestCase):
    def setUp(self):
        self.client = _client()
        self.session_patch = patch("app.routes.notebooks_api.SessionLocal")
        self.mock_session = self.session_patch.start()
        self.db = MagicMock()
        self.mock_session.return_value.__enter__.return_value = self.db
        self.mock_session.return_value.__exit__.return_value = False
        self.addCleanup(self.session_patch.stop)


class TestNotebooksApi(_NotebooksApiCase):
    def test_create_requires_name(self):
        r = self.client.post("/api/notebooks/", json={"folder": "orders"})
        self.assertEqual(r.status_code, 400)

    def test_get_missing_404(self):
        self.db.get.return_value = None
        r = self.client.get("/api/notebooks/nope")
        self.assertEqual(r.status_code, 404)


class TestAppendLog(_NotebooksApiCase):
    """The page posts numbers; numeric strings and floats are coerced, anything else is a 400."""

    def setUp(self):
        super().setUp()
        self.db.get.return_value = MagicMock(id="nb-1")

    def _post(self, **body):
        return self.client.post("/api/notebooks/nb-1/logs", json={"action": "Status", **body})

    def _row(self):
        return self.db.add.call_args.args[0]

    def test_numbers_from_the_page_are_stored(self):
        r = self._post(http=200, timeMs=42)
        self.assertEqual(r.status_code, 201)
        self.assertEqual((self._row().http_status, self._row().latency_ms, self._row().status), (200, 42, "ok"))

    def test_numeric_strings_are_coerced(self):
        r = self._post(http="404", timeMs="12")
        self.assertEqual(r.status_code, 201)
        self.assertEqual((self._row().http_status, self._row().latency_ms, self._row().status), (404, 12, "error"))

    def test_floats_are_coerced(self):
        r = self._post(http=500.0, timeMs="12.5")
        self.assertEqual(r.status_code, 201)
        self.assertEqual((self._row().http_status, self._row().latency_ms), (500, 12))

    def test_missing_numbers_default(self):
        r = self._post()
        self.assertEqual(r.status_code, 201)
        self.assertEqual((self._row().http_status, self._row().latency_ms, self._row().status), (None, 0, "ok"))

    def test_non_numeric_values_are_rejected(self):
        for body in ({"http": "abc"}, {"timeMs": "abc"}, {"http": [200]}, {"timeMs": {"ms": 1}},
                     {"http": True}, {"timeMs": "NaN"}, {"timeMs": "inf"}):
            r = self._post(**body)
            self.assertEqual(r.status_code, 400, body)
            self.assertIn("error", r.get_json())
        self.db.add.assert_not_called()
