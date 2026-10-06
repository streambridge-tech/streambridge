import unittest
from unittest.mock import patch

from flask import Flask, jsonify, session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.role import Role, RoleParent, RolePermission, UserRole
from app.models.user import User
from app.routes.admin_api import admin_api
from app.services.rbac.seed import seed_builtin_roles
from app.utils import auth as auth_mod
from app.utils.db import Base


def _engine_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        User.__table__, Role.__table__, RoleParent.__table__,
        RolePermission.__table__, UserRole.__table__,
    ])
    return sessionmaker(bind=engine)


class _CtxFactory:
    def __init__(self, Session):
        self.Session = Session

    def __call__(self):
        s = self.Session()

        class _Ctx:
            def __enter__(self_inner):
                return s

            def __exit__(self_inner, *exc):
                return False

        return _Ctx()


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.Session = _engine_session()
        factory = _CtxFactory(self.Session)
        # Seed built-in roles + an admin superuser to act as.
        db = self.Session()
        seed_builtin_roles(db)
        admin = User(username="root@corp.com", active=True, is_admin=True)
        admin.set_password("launch-ready-pass")
        db.add(admin); db.commit()
        self.admin_id = admin.id
        db.close()

        self.p1 = patch.object(auth_mod, "SessionLocal", side_effect=factory)
        self.p2 = patch("app.routes.admin_api.SessionLocal", side_effect=factory)
        self.p1.start(); self.p2.start()
        self.addCleanup(self.p1.stop); self.addCleanup(self.p2.stop)

        app = Flask(__name__)
        app.secret_key = "k"
        app.config["AUTH_ENABLED"] = True
        app.register_blueprint(admin_api)

        @app.post("/login-as-admin")
        def _login():
            session[auth_mod.SESSION_UID] = self.admin_id
            return jsonify({"ok": True})

        self.client = app.test_client()
        self.client.post("/login-as-admin")

    # ── roles ──
    def test_create_and_list_role(self):
        r = self.client.post("/api/admin/roles", json={
            "name": "Connector Builder",
            "description": "dev builder",
            "permissions": [{"key": "connector.create"}, {"key": "connector.save"}],
        })
        self.assertEqual(r.status_code, 201, r.get_json())
        roles = self.client.get("/api/admin/roles").get_json()
        self.assertIn("Connector Builder", [x["name"] for x in roles])

    def test_reject_unknown_permission(self):
        r = self.client.post("/api/admin/roles", json={"name": "Bad", "permissions": [{"key": "nope.boom"}]})
        self.assertEqual(r.status_code, 400)

    def test_cannot_edit_builtin(self):
        roles = self.client.get("/api/admin/roles").get_json()
        viewer = next(x for x in roles if x["name"] == "Public")
        r = self.client.patch(f"/api/admin/roles/{viewer['id']}", json={"description": "x"})
        self.assertEqual(r.status_code, 400)

    def test_inheritance_cycle_rejected(self):
        a = self.client.post("/api/admin/roles", json={"name": "A"}).get_json()
        b = self.client.post("/api/admin/roles", json={"name": "B", "parents": [a["id"]]}).get_json()
        # Now make A inherit B -> cycle.
        r = self.client.patch(f"/api/admin/roles/{a['id']}", json={"parents": [b["id"]]})
        self.assertEqual(r.status_code, 400)

    def test_effective_preview_includes_inherited(self):
        roles = self.client.get("/api/admin/roles").get_json()
        operator = next(x for x in roles if x["name"] == "Operator")
        r = self.client.post("/api/admin/roles/effective-preview", json={
            "parents": [operator["id"]],
            "permissions": [{"key": "admin.read_audit"}],
        })
        body = r.get_json()
        keys = {row["key"]: row["inherited"] for row in body["effective"]}
        self.assertFalse(keys["admin.read_audit"])          # own
        self.assertTrue(keys["connector.read"])             # inherited from Public via Operator

    # ── users ──
    def test_create_user_defaults_to_viewer(self):
        r = self.client.post("/api/admin/users", json={
            "username": "ana@corp.com", "password": "launch-ready-pass",
        })
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertIn("Public", r.get_json()["roleNames"])

    def test_cannot_disable_last_admin(self):
        r = self.client.patch(f"/api/admin/users/{self.admin_id}", json={"active": False})
        self.assertEqual(r.status_code, 400)

    def test_cannot_delete_last_admin(self):
        r = self.client.delete(f"/api/admin/users/{self.admin_id}")
        self.assertEqual(r.status_code, 400)

    def test_reset_password_requires_policy(self):
        u = self.client.post("/api/admin/users", json={
            "username": "x@corp.com", "password": "launch-ready-pass",
        }).get_json()
        weak = self.client.post(f"/api/admin/users/{u['id']}/reset-password", json={"password": "short"})
        self.assertEqual(weak.status_code, 400)
        ok = self.client.post(f"/api/admin/users/{u['id']}/reset-password", json={"password": "another-strong-pass"})
        self.assertEqual(ok.status_code, 200)


if __name__ == "__main__":
    unittest.main()
