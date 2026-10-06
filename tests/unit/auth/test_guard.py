import unittest
from unittest.mock import patch

from flask import Flask, g, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.user import User
from app.utils import auth as auth_mod
from app.utils.db import Base


def _engine_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[User.__table__])
    return sessionmaker(bind=engine)


class _CtxFactory:
    def __init__(self, Session):
        self.Session = Session

    def __call__(self):
        session = self.Session()

        class _Ctx:
            def __enter__(self_inner):
                return session

            def __exit__(self_inner, *exc):
                return False

        return _Ctx()


def _build_app(Session):
    app = Flask(__name__)
    app.secret_key = "test-key"
    app.before_request(auth_mod.auth_guard)

    @app.get("/")
    def home():
        return "home"

    @app.get("/api/connections")
    def list_conns():
        return jsonify({"ok": True})

    @app.post("/api/connections")
    def make_conn():
        return jsonify({"created": True})

    @app.post("/api/auth/login")
    def fake_login():
        # Simulate an authenticated session by stashing uid.
        from flask import session
        db = Session()
        try:
            u = db.query(User).first()
            session[auth_mod.SESSION_UID] = u.id
        finally:
            db.close()
        return jsonify({"ok": True})

    return app


class GuardDisabledTests(unittest.TestCase):
    def test_guard_noop_when_auth_disabled(self):
        Session = _engine_session()
        app = _build_app(Session)
        with patch.object(auth_mod, "auth_enabled", return_value=False):
            client = app.test_client()
            self.assertEqual(client.get("/api/connections").status_code, 200)
            self.assertEqual(client.get("/").status_code, 200)


class GuardEnabledTests(unittest.TestCase):
    def setUp(self):
        self.Session = _engine_session()
        factory = _CtxFactory(self.Session)
        self.p_enabled = patch.object(auth_mod, "auth_enabled", return_value=True)
        self.p_session = patch.object(auth_mod, "SessionLocal", side_effect=factory)
        self.p_enabled.start(); self.p_session.start()
        self.addCleanup(self.p_enabled.stop)
        self.addCleanup(self.p_session.stop)
        self.app = _build_app(self.Session)
        self.client = self.app.test_client()

    def _add_admin(self):
        db = self.Session()
        try:
            u = User(username="ana@corp.com", active=True, is_admin=True)
            u.set_password("launch-ready-pass")
            db.add(u)
            db.commit()
        finally:
            db.close()

    def test_setup_required_blocks_api_when_no_admin(self):
        r = self.client.get("/api/connections")
        self.assertEqual(r.status_code, 503)
        self.assertIn("setup required", r.get_json()["error"])

    def test_page_redirects_to_login_when_no_admin(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_unauthenticated_api_is_401(self):
        self._add_admin()
        r = self.client.get("/api/connections")
        self.assertEqual(r.status_code, 401)

    def test_unauthenticated_page_redirects(self):
        self._add_admin()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)

    def test_authenticated_access_allowed(self):
        self._add_admin()
        self.client.post("/api/auth/login")
        r = self.client.get("/api/connections")
        self.assertEqual(r.status_code, 200)

    def test_cross_origin_mutation_blocked(self):
        self._add_admin()
        self.client.post("/api/auth/login")
        r = self.client.post("/api/connections", headers={"Origin": "http://evil.example"})
        self.assertEqual(r.status_code, 403)

    def test_same_origin_mutation_allowed(self):
        self._add_admin()
        self.client.post("/api/auth/login")
        r = self.client.post("/api/connections", headers={"Origin": "http://localhost"})
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
