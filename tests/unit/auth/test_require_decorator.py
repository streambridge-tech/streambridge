import unittest
from unittest.mock import patch

from flask import Flask, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.role import Role, RoleParent, RolePermission, UserRole
from app.models.user import User
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
        session = self.Session()

        class _Ctx:
            def __enter__(self_inner):
                return session

            def __exit__(self_inner, *exc):
                return False

        return _Ctx()


def _app(Session):
    app = Flask(__name__)
    app.secret_key = "test-key"

    @app.post("/api/auth/login")
    def login():
        from flask import session
        db = Session()
        try:
            session[auth_mod.SESSION_UID] = db.query(User).first().id
        finally:
            db.close()
        return jsonify({"ok": True})

    @app.post("/deploy")
    @auth_mod.require("connector.deploy")
    def deploy():
        return jsonify({"deployed": True})

    @app.get("/read")
    @auth_mod.require("connector.read")
    def read():
        return jsonify({"ok": True})

    return app


class RequireDecoratorTests(unittest.TestCase):
    def setUp(self):
        self.Session = _engine_session()
        factory = _CtxFactory(self.Session)
        self.p_session = patch.object(auth_mod, "SessionLocal", side_effect=factory)
        self.p_session.start()
        self.addCleanup(self.p_session.stop)

    def _seed_user(self, *, is_admin=False, perms=()):
        db = self.Session()
        try:
            u = User(username="u@corp.com", active=True, is_admin=is_admin)
            u.set_password("launch-ready-pass")
            db.add(u); db.flush()
            if perms:
                r = Role(name="r"); db.add(r); db.flush()
                for p in perms:
                    db.add(RolePermission(role_id=r.id, permission_key=p,
                                          scope_type="global", scope_id="*"))
                db.add(UserRole(user_id=u.id, role_id=r.id))
            db.commit()
        finally:
            db.close()

    def test_personal_mode_allows(self):
        app = _app(self.Session)  # no AUTH_ENABLED in config
        c = app.test_client()
        self.assertEqual(c.post("/deploy").status_code, 200)

    def test_team_mode_unauthenticated_401(self):
        app = _app(self.Session)
        app.config["AUTH_ENABLED"] = True
        c = app.test_client()
        self.assertEqual(c.post("/deploy").status_code, 401)

    def test_team_mode_missing_permission_403(self):
        self._seed_user(perms=("connector.read",))
        app = _app(self.Session)
        app.config["AUTH_ENABLED"] = True
        c = app.test_client()
        c.post("/api/auth/login")
        self.assertEqual(c.get("/read").status_code, 200)
        r = c.post("/deploy")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["permission"], "connector.deploy")

    def test_team_mode_with_permission_200(self):
        self._seed_user(perms=("connector.read", "connector.deploy"))
        app = _app(self.Session)
        app.config["AUTH_ENABLED"] = True
        c = app.test_client()
        c.post("/api/auth/login")
        self.assertEqual(c.post("/deploy").status_code, 200)

    def test_admin_bypasses(self):
        self._seed_user(is_admin=True)
        app = _app(self.Session)
        app.config["AUTH_ENABLED"] = True
        c = app.test_client()
        c.post("/api/auth/login")
        self.assertEqual(c.post("/deploy").status_code, 200)


if __name__ == "__main__":
    unittest.main()
