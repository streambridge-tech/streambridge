"""server.* settings in profile.yaml and their STREAMBRIDGE__SERVER__* fallbacks."""
import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
CONFIG_SRC = ROOT / "app" / "utils" / "config.py"


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

    def test_host_and_port_defaults(self):
        cfg = self._load("server: {}\n").Config
        self.assertEqual((cfg.SERVER_HOST, cfg.SERVER_PORT), ("127.0.0.1", 5000))

    def test_host_and_port_from_profile(self):
        cfg = self._load('server:\n  host: "0.0.0.0"\n  port: 5302\n').Config
        self.assertEqual((cfg.SERVER_HOST, cfg.SERVER_PORT), ("0.0.0.0", 5302))

    def test_host_and_port_from_env_when_profile_blank(self):
        cfg = self._load(
            'server:\n  host: ""\n  port:\n',
            {"STREAMBRIDGE__SERVER__HOST": "10.0.0.5", "STREAMBRIDGE__SERVER__PORT": "5302"},
        ).Config
        self.assertEqual((cfg.SERVER_HOST, cfg.SERVER_PORT), ("10.0.0.5", 5302))

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

    def test_debug_off_by_default(self):
        self.assertFalse(self._load("server: {}\n").get_config().DEBUG)

    def test_shipped_profile_has_debug_off(self):
        self.assertFalse(self._load((ROOT / "profile.yaml").read_text()).get_config().DEBUG)

    def test_debug_from_profile(self):
        self.assertTrue(self._load("server:\n  debug: true\n").get_config().DEBUG)

    def test_debug_from_env_when_profile_blank(self):
        config = self._load("server:\n  debug:\n", {"STREAMBRIDGE__SERVER__DEBUG": "true"})
        self.assertTrue(config.get_config().DEBUG)

    def test_flask_env_development_turns_debug_on(self):
        self.assertTrue(self._load("server: {}\n", {"FLASK_ENV": "development"}).get_config().DEBUG)

    def test_flask_env_production_keeps_debug_off(self):
        config = self._load("server:\n  debug: true\n", {"FLASK_ENV": "production"})
        self.assertFalse(config.get_config().DEBUG)


if __name__ == "__main__":
    unittest.main()
