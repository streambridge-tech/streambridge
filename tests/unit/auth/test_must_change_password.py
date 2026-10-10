"""A user created or reset with must_change_password goes through the change first."""
import unittest
from unittest.mock import patch

from flask import Flask, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.role import Role, RoleParent, RolePermission, UserRole
from app.models.user import User
from app.routes.auth_api import auth_api
from app.utils import auth as auth_mod
from app.utils.db import Base

ORIGIN = {"Origin": "http://localhost"}


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


class MustChangePasswordFlowTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[
            User.__table__, Role.__table__, RoleParent.__table__,
            RolePermission.__table__, UserRole.__table__,
        ])
        Session = sessionmaker(bind=engine)
        factory = _CtxFactory(Session)
        for p in (
            patch("app.routes.auth_api.SessionLocal", side_effect=factory),
            patch("app.utils.auth.SessionLocal", side_effect=factory),
            patch("app.routes.auth_api.auth_enabled", return_value=True),
            patch("app.utils.auth.auth_enabled", return_value=True),
        ):
            p.start()
            self.addCleanup(p.stop)

        db = Session()
        u = User(username="ana@corp.com", active=True, is_admin=True, must_change_password=True)
        u.set_password("temporary-pass-1")
        db.add(u)
        db.commit()
        db.close()

        app = Flask(__name__)
        app.secret_key = "test-key"
        app.register_blueprint(auth_api)
        app.before_request(auth_mod.auth_guard)
        app.add_url_rule("/api/connections", "conns", lambda: jsonify({"ok": True}))
        self.client = app.test_client()

    def test_change_password_unlocks_the_api(self):
        r = self.client.post(
            "/api/auth/login", headers=ORIGIN,
            json={"username": "ana@corp.com", "password": "temporary-pass-1"},
        )
        self.assertTrue(r.get_json()["user"]["mustChangePassword"])
        self.assertEqual(self.client.get("/api/connections").status_code, 403)

        me = self.client.get("/api/auth/me").get_json()
        self.assertTrue(me["authenticated"])
        self.assertTrue(me["user"]["mustChangePassword"])

        r = self.client.post(
            "/api/auth/change-password", headers=ORIGIN,
            json={"currentPassword": "temporary-pass-1", "newPassword": "my-own-pass-22"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/connections").status_code, 200)


if __name__ == "__main__":
    unittest.main()
