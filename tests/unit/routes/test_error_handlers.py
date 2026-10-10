"""API errors come back as JSON; pages keep Flask's HTML error pages."""

import unittest

from flask import Flask, jsonify, request

from app.routes.errors import register_error_handlers


def _app(**config):
    app = Flask(__name__)
    app.config.update(config)

    @app.get("/api/items")
    def items():
        return jsonify([])

    @app.post("/api/echo")
    def echo():
        return jsonify(request.get_json(force=True))

    @app.get("/api/boom")
    def api_boom():
        raise RuntimeError("db password is hunter2")

    @app.get("/boom")
    def page_boom():
        raise RuntimeError("page failure")

    register_error_handlers(app)
    return app


class ApiErrorTests(unittest.TestCase):
    def setUp(self):
        self.client = _app().test_client()

    def test_unknown_api_route_is_json_404(self):
        r = self.client.get("/api/nope")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(r.is_json)
        self.assertIn("not found", r.get_json()["error"].lower())

    def test_wrong_method_is_json_405_with_allow(self):
        r = self.client.delete("/api/items")
        self.assertEqual(r.status_code, 405)
        self.assertTrue(r.is_json)
        self.assertIn("GET", r.headers["Allow"])
        self.assertIn("error", r.get_json())

    def test_malformed_json_body_is_json_400(self):
        r = self.client.post("/api/echo", data="{not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.is_json)
        self.assertIn("error", r.get_json())

    def test_unhandled_error_is_generic_json_500_and_logged(self):
        with self.assertLogs("app.routes.errors", level="ERROR") as logs:
            r = self.client.get("/api/boom")
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.get_json(), {"error": "Internal server error"})
        self.assertNotIn("hunter2", r.get_data(as_text=True))
        self.assertIn("RuntimeError", "\n".join(logs.output))

    def test_debug_and_testing_still_return_json_for_the_api(self):
        client = _app(DEBUG=True, TESTING=True).test_client()
        with self.assertLogs("app.routes.errors", level="ERROR"):
            r = client.get("/api/boom")
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.get_json(), {"error": "Internal server error"})


class PageErrorTests(unittest.TestCase):
    def test_unknown_page_keeps_html_404(self):
        r = _app().test_client().get("/nope")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.mimetype, "text/html")

    def test_page_error_keeps_html_500(self):
        app = _app()
        with self.assertLogs(app.logger, level="ERROR"):
            r = app.test_client().get("/boom")
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.mimetype, "text/html")
        self.assertNotIn("page failure", r.get_data(as_text=True))

    def test_page_error_still_propagates_when_testing(self):
        client = _app(TESTING=True).test_client()
        with self.assertRaises(RuntimeError):
            client.get("/boom")


if __name__ == "__main__":
    unittest.main()
