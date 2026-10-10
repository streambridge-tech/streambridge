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

    @app.route("/api/connections", methods=["POST", "PUT", "PATCH", "DELETE"])
    def make_conn():
        return jsonify({"created": True})

    @app.post("/api/auth/logout")
    def fake_logout():
        from flask import session
        session.clear()
        return jsonify({"ok": True})

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

    def test_cross_site_logout_blocked(self):
        self._add_admin()
        self.client.post("/api/auth/login")
        r = self.client.post("/api/auth/logout", headers={"Origin": "http://evil.example"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get("/api/connections").status_code, 200)

    def test_cross_site_login_blocked(self):
        self._add_admin()
        r = self.client.post("/api/auth/login", headers={"Origin": "http://evil.example"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get("/api/connections").status_code, 401)

    def test_host_header_not_checked(self):
        self._add_admin()
        r = self.client.get("/api/connections", headers={"Host": "rebind.evil.example"})
        self.assertEqual(r.status_code, 401)


class PersonalModeOriginTests(unittest.TestCase):
    """Personal mode has no session, so the Origin check is the only CSRF defense."""

    def setUp(self):
        p = patch.object(auth_mod, "auth_enabled", return_value=False)
        p.start()
        self.addCleanup(p.stop)
        self.client = _build_app(_engine_session()).test_client()

    def test_cross_site_text_plain_post_blocked(self):
        r = self.client.post(
            "/api/connections", data='{"name": "x"}', content_type="text/plain",
            headers={"Origin": "http://evil.example"},
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json(), {"error": "invalid origin"})

    def test_every_mutating_method_is_checked(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                r = self.client.open("/api/connections", method=method, headers={"Origin": "http://evil.example"})
                self.assertEqual(r.status_code, 403)

    def test_cross_site_referer_blocked(self):
        r = self.client.post("/api/connections", headers={"Referer": "http://evil.example/page"})
        self.assertEqual(r.status_code, 403)

    def test_opaque_origin_blocked(self):
        r = self.client.post("/api/connections", headers={"Origin": "null"})
        self.assertEqual(r.status_code, 403)

    def test_cross_site_auth_endpoint_blocked(self):
        r = self.client.post("/api/auth/logout", headers={"Origin": "http://evil.example"})
        self.assertEqual(r.status_code, 403)

    def test_same_origin_post_allowed(self):
        r = self.client.post("/api/connections", headers={"Origin": "http://localhost"})
        self.assertEqual(r.status_code, 200)

    def test_post_without_origin_or_referer_allowed(self):
        # CLI clients send neither header; browsers always send Origin on a POST.
        self.assertEqual(self.client.post("/api/connections").status_code, 200)

    def test_cross_site_get_allowed(self):
        r = self.client.get("/api/connections", headers={"Origin": "http://evil.example"})
        self.assertEqual(r.status_code, 200)


class PersonalModeHostTests(unittest.TestCase):
    """A DNS-rebinding page reaches the loopback server under its own Host name."""

    def setUp(self):
        p = patch.object(auth_mod, "auth_enabled", return_value=False)
        p.start()
        self.addCleanup(p.stop)
        self.app = _build_app(_engine_session())
        self.client = self.app.test_client()

    def _get(self, path, host):
        return self.client.get(path, headers={"Host": host})

    def test_loopback_hosts_allowed_on_any_port(self):
        for host in ("localhost", "localhost:5000", "127.0.0.1:5302", "[::1]:5000", "LOCALHOST:8080"):
            with self.subTest(host=host):
                self.assertEqual(self._get("/api/connections", host).status_code, 200)

    def test_unknown_host_blocked_for_api_with_json(self):
        r = self._get("/api/connections", "rebind.evil.example:5000")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json(), {"error": "invalid host"})

    def test_unknown_host_blocked_for_pages_with_text(self):
        r = self._get("/", "rebind.evil.example")
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.content_type.startswith("text/plain"))

    def test_unknown_host_blocked_for_static_and_login(self):
        for path in ("/static/app.js", "/login", "/api/auth/status"):
            with self.subTest(path=path):
                self.assertEqual(self._get(path, "rebind.evil.example").status_code, 403)

    def test_rebound_same_origin_post_blocked(self):
        r = self.client.post(
            "/api/connections",
            headers={"Host": "rebind.evil.example", "Origin": "http://rebind.evil.example"},
        )
        self.assertEqual(r.status_code, 403)

    def test_configured_server_host_allowed(self):
        self.app.config["SERVER_HOST"] = "10.0.0.5"
        self.assertEqual(self._get("/api/connections", "10.0.0.5:5000").status_code, 200)
        self.assertEqual(self._get("/api/connections", "10.0.0.6:5000").status_code, 403)

    def test_allowed_hosts_list_allowed(self):
        self.app.config["SERVER_ALLOWED_HOSTS"] = ["streambridge.lan", "FD00::1"]
        self.assertEqual(self._get("/api/connections", "streambridge.lan:5000").status_code, 200)
        self.assertEqual(self._get("/api/connections", "[fd00::1]:5000").status_code, 200)
        self.assertEqual(self._get("/api/connections", "other.lan").status_code, 403)


if __name__ == "__main__":
    unittest.main()
