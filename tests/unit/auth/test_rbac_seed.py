import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.role import Role, RoleParent, RolePermission, UserRole
from app.models.user import User
from app.services.rbac.engine import has_permission
from app.services.rbac.seed import seed_builtin_roles
from app.utils.db import Base


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        User.__table__, Role.__table__, RoleParent.__table__,
        RolePermission.__table__, UserRole.__table__,
    ])
    return sessionmaker(bind=engine)()


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.db = _db()
        self.addCleanup(self.db.close)

    def _user_with_role(self, role_name):
        u = User(username="u@corp.com", active=True, is_admin=False)
        u.set_password("launch-ready-pass")
        self.db.add(u); self.db.flush()
        role = self.db.query(Role).filter(Role.name == role_name).first()
        self.db.add(UserRole(user_id=u.id, role_id=role.id)); self.db.flush()
        return u

    def test_seed_creates_three_builtin_roles(self):
        seed_builtin_roles(self.db)
        names = {r.name for r in self.db.query(Role).all()}
        self.assertEqual(names, {"Public", "Operator", "Admin"})

    def test_seed_is_idempotent(self):
        seed_builtin_roles(self.db)
        seed_builtin_roles(self.db)
        self.assertEqual(self.db.query(Role).count(), 3)
        # No duplicate grants.
        viewer = self.db.query(Role).filter(Role.name == "Public").first()
        reads = self.db.query(RolePermission).filter(
            RolePermission.role_id == viewer.id,
            RolePermission.permission_key == "connector.read",
        ).count()
        self.assertEqual(reads, 1)

    def test_viewer_is_read_only(self):
        seed_builtin_roles(self.db)
        u = self._user_with_role("Public")
        self.assertTrue(has_permission(self.db, u, "connector.read"))
        self.assertFalse(has_permission(self.db, u, "connector.deploy"))
        self.assertFalse(has_permission(self.db, u, "danger.delete_live"))

    def test_operator_inherits_viewer_and_can_deploy(self):
        seed_builtin_roles(self.db)
        u = self._user_with_role("Operator")
        self.assertTrue(has_permission(self.db, u, "connector.read"))     # inherited
        self.assertTrue(has_permission(self.db, u, "connector.deploy"))   # own
        self.assertFalse(has_permission(self.db, u, "danger.delete_live"))

    def test_admin_role_has_dangerous_and_admin_perms(self):
        seed_builtin_roles(self.db)
        u = self._user_with_role("Admin")
        self.assertTrue(has_permission(self.db, u, "connector.read"))      # inherited from Public
        self.assertTrue(has_permission(self.db, u, "connector.deploy"))    # inherited from Operator
        self.assertTrue(has_permission(self.db, u, "danger.reset_offsets"))
        self.assertTrue(has_permission(self.db, u, "admin.manage_roles"))


if __name__ == "__main__":
    unittest.main()
