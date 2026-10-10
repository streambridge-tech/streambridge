"""First-run setup hands out the admin account, so a rebound DNS name must not reach it."""
import unittest
from unittest.mock import patch

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.role import Role, RoleParent, RolePermission, UserRole
from app.models.user import User
from app.models.workspace import WorkspaceSetting
from app.routes.auth_api import auth_api
from app.utils import auth as auth_mod
from app.utils.db import Base

REBOUND = {"Host": "rebind.evil.example:5000", "Origin": "http://rebind.evil.example:5000"}
ADMIN = {"mode": "team", "username": "ana@corp.com", "password": "launch-ready-pass"}


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


class TeamSetupHostTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[
            User.__table__, Role.__table__, RoleParent.__table__,
            RolePermission.__table__, UserRole.__table__, WorkspaceSetting.__table__,
        ])
        self.Session = sessionmaker(bind=engine)
        factory = _CtxFactory(self.Session)
        for p in (
            patch("app.routes.auth_api.SessionLocal", side_effect=factory),
            patch("app.utils.auth.SessionLocal", side_effect=factory),
            patch("app.routes.auth_api.auth_enabled", return_value=True),
            patch("app.utils.auth.auth_enabled", return_value=True),
        ):
            p.start()
            self.addCleanup(p.stop)

        self.app = Flask(__name__)
        self.app.secret_key = "test-key"
        self.app.register_blueprint(auth_api)
        self.app.before_request(auth_mod.auth_guard)
        self.client = self.app.test_client()

    def _users(self):
        db = self.Session()
        try:
            return db.query(User).count()
        finally:
            db.close()

    def test_rebound_host_cannot_run_setup(self):
        r = self.client.post("/api/auth/setup", headers=REBOUND, json=ADMIN)
        self.assertEqual(r.status_code, 403)
        body = r.get_json()
        self.assertEqual(body["error"], "invalid host")
        self.assertIn("server.allowed_hosts", body["message"])
        self.assertIn("manage.py admin bootstrap", body["message"])
        self.assertEqual(self._users(), 0)

    def test_loopback_host_can_run_setup(self):
        r = self.client.post("/api/auth/setup", headers={"Origin": "http://localhost"}, json=ADMIN)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._users(), 1)

    def test_allowed_host_can_run_setup(self):
        self.app.config["SERVER_ALLOWED_HOSTS"] = ["streambridge.corp.example"]
        r = self.client.post(
            "/api/auth/setup", json=ADMIN,
            headers={"Host": "streambridge.corp.example", "Origin": "http://streambridge.corp.example"},
        )
        self.assertEqual(r.status_code, 200)

    def test_other_hosts_still_reach_team_mode_after_setup(self):
        self.client.post("/api/auth/setup", headers={"Origin": "http://localhost"}, json=ADMIN)
        r = self.client.post(
            "/api/auth/login", headers=REBOUND,
            json={"username": ADMIN["username"], "password": ADMIN["password"]},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/login", headers=REBOUND).status_code, 200)


if __name__ == "__main__":
    unittest.main()
