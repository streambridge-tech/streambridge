import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.role import Role, RoleParent, RolePermission, UserRole
from app.models.user import User
from app.services.rbac.engine import permission_summary, user_has_feature
from app.services.rbac.permissions import feature_operation_keys, has_feature
from app.utils.db import Base


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        User.__table__, Role.__table__, RoleParent.__table__,
        RolePermission.__table__, UserRole.__table__,
    ])
    return sessionmaker(bind=engine)()


class FeatureCatalogTests(unittest.TestCase):
    def test_explicit_nav_key(self):
        self.assertTrue(has_feature({"nav.connectors"}, "nav.connectors"))

    def test_operation_implies_feature(self):
        self.assertTrue(has_feature({"connector.deploy"}, "nav.connectors"))

    def test_unrelated_permission_does_not_imply(self):
        self.assertFalse(has_feature({"alert.read"}, "nav.connectors"))

    def test_operation_keys_exclude_nav(self):
        ops = feature_operation_keys("nav.connectors")
        self.assertIn("connector.read", ops)
        self.assertNotIn("nav.connectors", ops)


class FeatureEngineTests(unittest.TestCase):
    def setUp(self):
        self.db = _db()
        self.addCleanup(self.db.close)

    def _user_with_perm(self, key, is_admin=False):
        u = User(username="u@corp.com", active=True, is_admin=is_admin)
        u.set_password("launch-ready-pass")
        self.db.add(u); self.db.flush()
        if key:
            r = Role(name="r"); self.db.add(r); self.db.flush()
            self.db.add(RolePermission(role_id=r.id, permission_key=key, scope_type="global", scope_id="*"))
            self.db.add(UserRole(user_id=u.id, role_id=r.id))
        self.db.flush()
        return u

    def test_feature_implied_by_operation(self):
        u = self._user_with_perm("connector.deploy")
        self.assertTrue(user_has_feature(self.db, u, "nav.connectors"))
        self.assertFalse(user_has_feature(self.db, u, "nav.alerts"))

    def test_admin_has_all_features(self):
        u = self._user_with_perm(None, is_admin=True)
        self.assertTrue(user_has_feature(self.db, u, "nav.alerts"))

    def test_summary_includes_implied_nav(self):
        u = self._user_with_perm("connector.deploy")
        summary = permission_summary(self.db, u)
        self.assertIn("nav.connectors", summary["permissions"])
        self.assertNotIn("nav.alerts", summary["permissions"])


if __name__ == "__main__":
    unittest.main()
