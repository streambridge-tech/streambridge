import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.role import (
    SCOPE_ALL,
    SCOPE_CLUSTER,
    SCOPE_FOLDER,
    SCOPE_GLOBAL,
    Role,
    RoleParent,
    RolePermission,
    UserRole,
)
from app.models.user import User
from app.services.rbac.engine import (
    effective_permissions,
    has_permission,
    resolve_inherited_role_ids,
)
from app.utils.db import Base


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        User.__table__, Role.__table__, RoleParent.__table__,
        RolePermission.__table__, UserRole.__table__,
    ])
    return sessionmaker(bind=engine)()


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.db = _db()
        self.addCleanup(self.db.close)

    def _user(self, is_admin=False):
        u = User(username="u@corp.com", active=True, is_admin=is_admin)
        u.set_password("launch-ready-pass")
        self.db.add(u); self.db.flush()
        return u

    def _role(self, name):
        r = Role(name=name)
        self.db.add(r); self.db.flush()
        return r

    def _grant(self, role, key, stype=SCOPE_GLOBAL, sid=SCOPE_ALL):
        self.db.add(RolePermission(role_id=role.id, permission_key=key, scope_type=stype, scope_id=sid))
        self.db.flush()

    def _assign(self, user, role):
        self.db.add(UserRole(user_id=user.id, role_id=role.id)); self.db.flush()

    def test_deny_by_default(self):
        u = self._user()
        self.assertFalse(has_permission(self.db, u, "connector.deploy"))

    def test_admin_bypass(self):
        u = self._user(is_admin=True)
        self.assertTrue(has_permission(self.db, u, "danger.reset_offsets", SCOPE_CLUSTER, "c1"))

    def test_direct_global_grant(self):
        u = self._user(); r = self._role("r")
        self._grant(r, "connector.read")
        self._assign(u, r)
        self.assertTrue(has_permission(self.db, u, "connector.read"))
        self.assertFalse(has_permission(self.db, u, "connector.deploy"))

    def test_inheritance_chain(self):
        u = self._user()
        r1 = self._role("r1"); r2 = self._role("r2"); r3 = self._role("r3")
        self._grant(r1, "connector.read")
        self._grant(r2, "connector.save")
        self._grant(r3, "connector.deploy")
        self.db.add(RoleParent(role_id=r2.id, parent_id=r1.id))
        self.db.add(RoleParent(role_id=r3.id, parent_id=r2.id))
        self.db.flush()
        self._assign(u, r3)
        # r3 inherits r2 inherits r1
        self.assertTrue(has_permission(self.db, u, "connector.read"))
        self.assertTrue(has_permission(self.db, u, "connector.save"))
        self.assertTrue(has_permission(self.db, u, "connector.deploy"))

    def test_cycle_is_safe(self):
        r1 = self._role("r1"); r2 = self._role("r2")
        self.db.add(RoleParent(role_id=r1.id, parent_id=r2.id))
        self.db.add(RoleParent(role_id=r2.id, parent_id=r1.id))
        self.db.flush()
        ids = resolve_inherited_role_ids(self.db, {r1.id})
        self.assertEqual(ids, {r1.id, r2.id})

    def test_scoped_grant_folder(self):
        u = self._user(); r = self._role("r")
        self._grant(r, "connector.deploy", SCOPE_FOLDER, "dev")
        self._assign(u, r)
        self.assertTrue(has_permission(self.db, u, "connector.deploy", SCOPE_FOLDER, "dev"))
        self.assertFalse(has_permission(self.db, u, "connector.deploy", SCOPE_FOLDER, "prod"))

    def test_scope_all_within_type(self):
        u = self._user(); r = self._role("r")
        self._grant(r, "connector.deploy", SCOPE_FOLDER, SCOPE_ALL)
        self._assign(u, r)
        self.assertTrue(has_permission(self.db, u, "connector.deploy", SCOPE_FOLDER, "anything"))

    def test_global_grant_covers_any_scope(self):
        u = self._user(); r = self._role("r")
        self._grant(r, "connector.deploy", SCOPE_GLOBAL, SCOPE_ALL)
        self._assign(u, r)
        self.assertTrue(has_permission(self.db, u, "connector.deploy", SCOPE_CLUSTER, "c9"))

    def test_scoped_grant_does_not_satisfy_other_type(self):
        u = self._user(); r = self._role("r")
        self._grant(r, "connector.deploy", SCOPE_FOLDER, "dev")
        self._assign(u, r)
        self.assertFalse(has_permission(self.db, u, "connector.deploy", SCOPE_CLUSTER, "dev"))

    def test_effective_permissions_union(self):
        u = self._user()
        r1 = self._role("r1"); r2 = self._role("r2")
        self._grant(r1, "connector.read")
        self._grant(r2, "connector.save")
        self._assign(u, r1); self._assign(u, r2)
        eff = effective_permissions(self.db, u.id)
        self.assertIn("connector.read", eff)
        self.assertIn("connector.save", eff)


if __name__ == "__main__":
    unittest.main()
