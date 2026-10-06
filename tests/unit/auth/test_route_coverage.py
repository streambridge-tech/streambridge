"""Completeness guard: every /api route must carry an authorization check.

Fails if a new endpoint is added without a `require(...)` decorator (or, for the
dynamically-dispatched Connect endpoints, an explicit `authorize(...)` call).
This is the permission-matrix regression test.
"""
import unittest

from flask import Flask

from app.routes.admin_api import admin_api
from app.routes.alerts_api import alerts_api
from app.routes.connections_api import connections_api
from app.routes.folders_api import folders_api
from app.routes.kafka_api import kafka_api
from app.routes.kafka_connect_api import kc_api
from app.routes.notebooks_api import notebooks_api
from app.routes.pipelines_api import pipelines_api
from app.routes.plugins_api import plugins_api
from app.routes.schema_registry_api import schema_registry_api
from app.routes.vaults_api import vaults_api
from app.services.rbac.permissions import is_valid_permission

# Endpoints that are intentionally open (no permission) — auth + liveness.
OPEN_ENDPOINTS = {
    "auth_api.login_page", "auth_api.auth_status", "auth_api.auth_me",
    "auth_api.auth_login", "auth_api.auth_logout",
    "api.health",
    # Plugins are public to view; create/edit/delete stay permission-gated.
    "plugins_api.list_plugins", "plugins_api.get_plugin",
}

# Endpoints that enforce permission imperatively via authorize() because they
# dispatch by a dynamic action name.
DYNAMIC_ENDPOINTS = {
    "kc_api.run_action", "kc_api.run_connection_action",
}


def _app():
    app = Flask(__name__)
    for bp in (alerts_api, connections_api, folders_api, kafka_api, kc_api,
               notebooks_api, pipelines_api, plugins_api, schema_registry_api, vaults_api,
               admin_api):
        app.register_blueprint(bp)
    return app


class RouteCoverageTests(unittest.TestCase):
    def test_every_api_route_has_authorization(self):
        app = _app()
        unguarded = []
        for rule in app.url_map.iter_rules():
            if not rule.rule.startswith("/api/"):
                continue
            ep = rule.endpoint
            if ep in OPEN_ENDPOINTS or ep in DYNAMIC_ENDPOINTS:
                continue
            view = app.view_functions[ep]
            perm = getattr(view, "_rbac_permission", None)
            if perm is None:
                unguarded.append(ep)
            else:
                self.assertTrue(is_valid_permission(perm), f"{ep} -> unknown permission {perm}")
        self.assertEqual(unguarded, [], f"endpoints missing @require: {unguarded}")


if __name__ == "__main__":
    unittest.main()
