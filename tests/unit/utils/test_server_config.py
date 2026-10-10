"""server.* settings in profile.yaml and their STREAMBRIDGE__SERVER__* fallbacks."""
import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

CONFIG_SRC = Path(__file__).resolve().parents[3] / "app" / "utils" / "config.py"


class ServerConfigTests(unittest.TestCase):
    def setUp(self):
        saved = {k: v for k, v in os.environ.items() if k == "FLASK_ENV" or k.startswith("STREAMBRIDGE__SERVER__")}
        for key in saved:
            os.environ.pop(key)
        self.addCleanup(os.environ.update, saved)

    def _load(self, profile: str, env: dict | None = None):
        """Import a fresh copy of config.py that reads the given profile.yaml."""
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        (root / "app" / "utils").mkdir(parents=True)
        shutil.copy(CONFIG_SRC, root / "app" / "utils" / "config.py")
        (root / "profile.yaml").write_text(profile)
        env_patch = patch.dict(os.environ, env or {})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        spec = importlib.util.spec_from_file_location("config_under_test", root / "app" / "utils" / "config.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_allowed_hosts_default_empty(self):
        self.assertEqual(self._load("server: {}\n").Config.SERVER_ALLOWED_HOSTS, [])

    def test_allowed_hosts_from_profile_list(self):
        cfg = self._load("server:\n  allowed_hosts: [streambridge.lan, 10.0.0.5]\n").Config
        self.assertEqual(cfg.SERVER_ALLOWED_HOSTS, ["streambridge.lan", "10.0.0.5"])

    def test_allowed_hosts_from_env_comma_list(self):
        cfg = self._load(
            "server:\n  allowed_hosts: []\n",
            {"STREAMBRIDGE__SERVER__ALLOWED_HOSTS": "streambridge.lan, 10.0.0.5 ,"},
        ).Config
        self.assertEqual(cfg.SERVER_ALLOWED_HOSTS, ["streambridge.lan", "10.0.0.5"])


if __name__ == "__main__":
    unittest.main()
