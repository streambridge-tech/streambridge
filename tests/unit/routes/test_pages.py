import unittest

from flask import Flask

from app.routes.pages import pages


class TestConnectorPageRoutes(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(pages)
        self.client = app.test_client()

    def test_configs_redirects_to_connectors(self):
        r = self.client.get("/configs")
        self.assertEqual(r.status_code, 301)
        self.assertTrue(r.headers["Location"].endswith("/connectors"))
