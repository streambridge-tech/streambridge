import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import cli
from app.models.user import User
from app.utils.db import Base


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[User.__table__])
    Session = sessionmaker(bind=engine)

    class _Ctx:
        def __enter__(self_inner):
            self_inner.db = Session()
            return self_inner.db

        def __exit__(self_inner, *exc):
            self_inner.db.close()
            return False

    # Same engine across calls so state persists within a test.
    return lambda: _Ctx(), Session


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        factory, self.Session = _session_factory()
        self.session_patch = patch("app.cli.SessionLocal", side_effect=factory)
        self.session_patch.start()
        self.init_patch = patch("app.cli.init_db", lambda: None)
        self.init_patch.start()
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.init_patch.stop)

    def _count_admins(self):
        db = self.Session()
        try:
            return db.query(User).filter(User.is_admin.is_(True)).count()
        finally:
            db.close()

    @patch("app.cli.getpass.getpass", return_value="launch-ready-pass")
    @patch("builtins.input", return_value="ana@corp.com")
    def test_bootstrap_creates_admin(self, _inp, _gp):
        rc = cli.main(["admin", "bootstrap"])
        self.assertEqual(rc, 0)
        self.assertEqual(self._count_admins(), 1)

    @patch("app.cli.getpass.getpass", return_value="launch-ready-pass")
    @patch("builtins.input", return_value="ana@corp.com")
    def test_bootstrap_refuses_second_admin(self, _inp, _gp):
        self.assertEqual(cli.main(["admin", "bootstrap"]), 0)
        rc = cli.main(["admin", "bootstrap"])
        self.assertEqual(rc, 1)
        self.assertEqual(self._count_admins(), 1)

    @patch("app.cli.getpass.getpass", return_value="short")
    @patch("builtins.input", return_value="ana@corp.com")
    def test_bootstrap_rejects_weak_password(self, _inp, _gp):
        rc = cli.main(["admin", "bootstrap"])
        self.assertEqual(rc, 1)
        self.assertEqual(self._count_admins(), 0)

    @patch("app.cli.getpass.getpass", return_value="launch-ready-pass")
    @patch("builtins.input", return_value="bad name")
    def test_bootstrap_rejects_bad_username(self, _inp, _gp):
        rc = cli.main(["admin", "bootstrap"])
        self.assertEqual(rc, 1)
        self.assertEqual(self._count_admins(), 0)


if __name__ == "__main__":
    unittest.main()
