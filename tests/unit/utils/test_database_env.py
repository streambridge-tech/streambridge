import os
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from app.utils.config import _load_dotenv, _prefer, get_database_url


_DB_KEYS = (
    "STREAMBRIDGE__DATABASE__BACKEND",
    "STREAMBRIDGE__DATABASE__MYSQL__HOST",
    "STREAMBRIDGE__DATABASE__MYSQL__PORT",
    "STREAMBRIDGE__DATABASE__MYSQL__DATABASE",
    "STREAMBRIDGE__DATABASE__MYSQL__USERNAME",
    "STREAMBRIDGE__DATABASE__MYSQL__PASSWORD",
    "STREAMBRIDGE__DATABASE__SQLITE__PATH",
)


class TestDatabaseEnv(unittest.TestCase):
    def setUp(self):
        self._saved = {key: os.environ.get(key) for key in _DB_KEYS}
        for key in _DB_KEYS:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_dotenv_fills_empty_env_and_keeps_shell_export(self):
        os.environ["STREAMBRIDGE__DATABASE__MYSQL__USERNAME"] = "from-shell"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                "export STREAMBRIDGE__DATABASE__MYSQL__USERNAME=from-file\n"
                "STREAMBRIDGE__DATABASE__MYSQL__PASSWORD=s3cret@x\n"
            )
            _load_dotenv(path)
        self.assertEqual(os.environ["STREAMBRIDGE__DATABASE__MYSQL__USERNAME"], "from-shell")
        self.assertEqual(os.environ["STREAMBRIDGE__DATABASE__MYSQL__PASSWORD"], "s3cret@x")

    def test_yaml_value_wins_over_env(self):
        os.environ["STREAMBRIDGE__DATABASE__BACKEND"] = "mysql"
        os.environ["STREAMBRIDGE__DATABASE__SQLITE__PATH"] = "/tmp/other.db"
        with tempfile.TemporaryDirectory() as tmp:
            yaml_path = str(Path(tmp) / "from-yaml.db")
            profile = {"database": {"backend": "sqlite", "sqlite": {"path": yaml_path}}}
            with patch("app.utils.config._profile", profile):
                url = get_database_url()
        self.assertEqual(url, f"sqlite:///{yaml_path}")

    def test_blank_yaml_uses_env_password(self):
        os.environ["STREAMBRIDGE__DATABASE__MYSQL__HOST"] = "db.internal"
        os.environ["STREAMBRIDGE__DATABASE__MYSQL__PORT"] = "3306"
        os.environ["STREAMBRIDGE__DATABASE__MYSQL__DATABASE"] = "streambridge"
        os.environ["STREAMBRIDGE__DATABASE__MYSQL__USERNAME"] = "app"
        os.environ["STREAMBRIDGE__DATABASE__MYSQL__PASSWORD"] = "p@ss:word"
        with patch("app.utils.config._get", return_value="mysql"), patch(
            "app.utils.config._get_nested",
            return_value="",
        ):
            url = get_database_url()
        self.assertIn("app:p%40ss%3Aword@db.internal:3306/streambridge", url)

    def test_prefer_keeps_yaml_and_falls_through_when_blank(self):
        self.assertEqual(_prefer("root", "from-env", "fallback"), "root")
        self.assertEqual(_prefer("", "from-env", "fallback"), "from-env")
        self.assertEqual(_prefer(None, None, "fallback"), "fallback")
