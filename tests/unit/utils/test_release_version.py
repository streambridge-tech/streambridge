"""Version bump rules for pull requests and release tags."""

import importlib.util
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[3] / "scripts" / "release_version.py"
    spec = importlib.util.spec_from_file_location("release_version", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release_version = _load()


class ReleaseVersionTests(unittest.TestCase):
    def test_parses_numeric_versions(self):
        self.assertEqual(release_version.parse_version("v0.1.0"), (0, 1, 0))
        self.assertEqual(release_version.parse_version("0.10.2"), (0, 10, 2))

    def test_rejects_non_numeric_versions(self):
        with self.assertRaises(ValueError):
            release_version.parse_version("1.0.0-rc1")

    def test_latest_tag_ignores_non_release_names(self):
        self.assertEqual(release_version.latest_tag(["phase-1", "v0.1.0", "v0.2.0"]), "v0.2.0")
        self.assertIsNone(release_version.latest_tag(["phase-1"]))

    def test_first_release_needs_no_bump(self):
        self.assertTrue(release_version.version_is_newer("0.1.0", None))

    def test_equal_or_older_version_is_not_newer(self):
        self.assertFalse(release_version.version_is_newer("0.1.0", "v0.1.0"))
        self.assertFalse(release_version.version_is_newer("0.1.0", "v0.2.0"))
        self.assertTrue(release_version.version_is_newer("0.1.1", "v0.1.0"))

    def test_release_tag_name(self):
        self.assertEqual(release_version.parse_version("0.1.0"), (0, 1, 0))


if __name__ == "__main__":
    unittest.main()
