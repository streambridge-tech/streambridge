import unittest
from unittest.mock import patch

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.role import Role, RoleParent, RolePermission, UserRole
from app.models.user import User
from app.routes.auth_api import auth_api
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
        session = self.Session()
        outer = self

        class _Ctx:
            def __enter__(self_inner):
                self_inner.db = session
                return session

            def __exit__(self_inner, *exc):
                return False

        return _Ctx()


class AuthApiTests(unittest.TestCase):
    def setUp(self):
        self.Session = _engine_session()
        factory = _CtxFactory(self.Session)

        app = Flask(__name__)
        app.secret_key = "test-key"
        app.register_blueprint(auth_api)
        self.client = app.test_client()

        # Patch SessionLocal in both modules that use it for auth.
        self.p1 = patch("app.routes.auth_api.SessionLocal", side_effect=factory)
        self.p2 = patch("app.utils.auth.SessionLocal", side_effect=factory)
        self.p3 = patch("app.routes.auth_api.auth_enabled", return_value=True)
        self.p1.start(); self.p2.start(); self.p3.start()
        self.addCleanup(self.p1.stop)
        self.addCleanup(self.p2.stop)
        self.addCleanup(self.p3.stop)

    def _add_user(self, username="ana@corp.com", password="launch-ready-pass", active=True, is_admin=True):
        db = self.Session()
        try:
            u = User(username=username, active=active, is_admin=is_admin)
            u.set_password(password)
            db.add(u)
            db.commit()
        finally:
            db.close()

    def test_status_setup_required_when_no_admin(self):
        r = self.client.get("/api/auth/status")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["setupRequired"])

    def test_login_success_then_me(self):
        self._add_user()
        r = self.client.post("/api/auth/login", json={"username": "ANA@corp.com", "password": "launch-ready-pass"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["user"]["username"], "ana@corp.com")

        me = self.client.get("/api/auth/me")
        self.assertTrue(me.get_json()["authenticated"])

    def test_login_wrong_password(self):
        self._add_user()
        r = self.client.post("/api/auth/login", json={"username": "ana@corp.com", "password": "nope"})
        self.assertEqual(r.status_code, 401)
        self.assertIn("Invalid", r.get_json()["error"])

    def test_login_unknown_user_is_generic(self):
        r = self.client.post("/api/auth/login", json={"username": "ghost@corp.com", "password": "whatever-long"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error"], "Invalid username or password")

    def test_disabled_user_cannot_login(self):
        self._add_user(active=False)
        r = self.client.post("/api/auth/login", json={"username": "ana@corp.com", "password": "launch-ready-pass"})
        self.assertEqual(r.status_code, 401)

    def test_logout_clears_session(self):
        self._add_user()
        self.client.post("/api/auth/login", json={"username": "ana@corp.com", "password": "launch-ready-pass"})
        self.client.post("/api/auth/logout")
        me = self.client.get("/api/auth/me")
        self.assertFalse(me.get_json()["authenticated"])


if __name__ == "__main__":
    unittest.main()
