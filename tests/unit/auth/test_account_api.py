import unittest
from unittest.mock import patch

from flask import Flask, jsonify, session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.role import Role, RoleParent, RolePermission, UserRole
from app.models.user import User
from app.routes.auth_api import auth_api
from app.services.rbac.engine import effective_permissions
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


class ActiveRoleEngineTests(unittest.TestCase):
    def setUp(self):
        self.Session = _engine_session()
        self.db = self.Session()
        self.addCleanup(self.db.close)
        self.u = User(username="u@corp.com", active=True)
        self.u.set_password("launch-ready-pass")
        self.db.add(self.u); self.db.flush()
        self.r1 = Role(name="Reader"); self.r2 = Role(name="Deployer")
        self.db.add_all([self.r1, self.r2]); self.db.flush()
        self.db.add(RolePermission(role_id=self.r1.id, permission_key="connector.read", scope_type="global", scope_id="*"))
        self.db.add(RolePermission(role_id=self.r2.id, permission_key="connector.deploy", scope_type="global", scope_id="*"))
        self.db.add(UserRole(user_id=self.u.id, role_id=self.r1.id))
        self.db.add(UserRole(user_id=self.u.id, role_id=self.r2.id))
        self.db.commit()

    def test_union_when_no_active_role(self):
        keys = set(effective_permissions(self.db, self.u.id).keys())
        self.assertEqual(keys, {"connector.read", "connector.deploy"})

    def test_narrowed_to_active_role(self):
        keys = set(effective_permissions(self.db, self.u.id, self.r1.id).keys())
        self.assertEqual(keys, {"connector.read"})

    def test_unassigned_active_role_falls_back_to_union(self):
        keys = set(effective_permissions(self.db, self.u.id, 9999).keys())
        self.assertEqual(keys, {"connector.read", "connector.deploy"})


class AccountApiTests(unittest.TestCase):
    def setUp(self):
        self.Session = _engine_session()
        factory = _CtxFactory(self.Session)
        db = self.Session()
        self.u = User(username="u@corp.com", active=True)
        self.u.set_password("launch-ready-pass")
        db.add(self.u); db.flush()
        self.r1 = Role(name="Reader"); db.add(self.r1); db.flush()
        db.add(UserRole(user_id=self.u.id, role_id=self.r1.id))
        db.commit(); self.uid = self.u.id; self.rid = self.r1.id; db.close()

        self.p1 = patch("app.routes.auth_api.SessionLocal", side_effect=factory)
        self.p1.start(); self.addCleanup(self.p1.stop)

        app = Flask(__name__); app.secret_key = "k"
        app.register_blueprint(auth_api)

        @app.post("/login-as")
        def _login():
            session[auth_mod.SESSION_UID] = self.uid
            return jsonify({"ok": True})

        self.client = app.test_client()
        self.client.post("/login-as")

    def test_set_active_role(self):
        r = self.client.post("/api/auth/active-role", json={"roleId": self.rid})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["activeRoleId"], self.rid)

    def test_set_active_role_rejects_unassigned(self):
        r = self.client.post("/api/auth/active-role", json={"roleId": 9999})
        self.assertEqual(r.status_code, 400)

    def test_set_active_role_null_clears(self):
        self.client.post("/api/auth/active-role", json={"roleId": self.rid})
        r = self.client.post("/api/auth/active-role", json={"roleId": None})
        self.assertIsNone(r.get_json()["activeRoleId"])

    def test_default_role_persists(self):
        r = self.client.post("/api/auth/default-role", json={"roleId": self.rid})
        self.assertEqual(r.status_code, 200)
        db = self.Session()
        try:
            self.assertEqual(db.get(User, self.uid).default_role_id, self.rid)
        finally:
            db.close()

    def test_change_password_success(self):
        r = self.client.post("/api/auth/change-password", json={"currentPassword": "launch-ready-pass", "newPassword": "a-brand-new-pass"})
        self.assertEqual(r.status_code, 200)

    def test_change_password_wrong_current(self):
        r = self.client.post("/api/auth/change-password", json={"currentPassword": "nope", "newPassword": "a-brand-new-pass"})
        self.assertEqual(r.status_code, 400)

    def test_change_password_weak_new(self):
        r = self.client.post("/api/auth/change-password", json={"currentPassword": "launch-ready-pass", "newPassword": "short"})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
