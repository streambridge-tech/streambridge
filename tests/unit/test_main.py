"""`python main.py` serves on the host, port, and debug setting from config."""
import runpy
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

MAIN = Path(__file__).resolve().parents[2] / "main.py"


class MainTests(unittest.TestCase):
    def _run_main(self, debug: bool):
        app = MagicMock()
        app.config = {"SERVER_HOST": "0.0.0.0", "SERVER_PORT": 5302, "DEBUG": debug}
        app.debug = debug
        with patch("app.create_app", return_value=app):
            runpy.run_path(str(MAIN), run_name="__main__")
        return app

    def test_runs_on_configured_host_and_port(self):
        app = self._run_main(debug=False)
        app.run.assert_called_once_with(host="0.0.0.0", port=5302, debug=False)

    def test_debug_matches_the_app(self):
        # The alert scheduler's reloader guard read app.debug at startup.
        app = self._run_main(debug=True)
        app.run.assert_called_once_with(host="0.0.0.0", port=5302, debug=True)


if __name__ == "__main__":
    unittest.main()
