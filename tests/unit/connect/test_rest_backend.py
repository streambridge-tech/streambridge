"""Unit tests for RestBackend using a fake requests module — no real HTTP."""
import json
import unittest
from unittest.mock import patch

from app.services.connect.rest_backend import RestBackend, effective_connect_status


class FakeResponse:
    def __init__(self, status_code: int, body=None, text: str = ""):
        self.status_code = status_code
        self._body = body
        self.text = text or (json.dumps(body) if body is not None else "")

    def json(self):
        return self._body


class FakeRequests:
    """Records calls and returns queued responses per (method, url) key."""

    def __init__(self):
        self.calls: list[tuple] = []
        self._queued: dict[tuple[str, str], FakeResponse] = {}

    def queue(self, method: str, url: str, response: FakeResponse):
        self._queued[(method.upper(), url)] = response

    def _dispatch(self, method: str, url: str, **kwargs):
        self.calls.append((method.upper(), url, kwargs))
        key = (method.upper(), url)
        if key not in self._queued:
            raise AssertionError(f"unexpected HTTP call: {method} {url}")
        return self._queued[key]

    def get(self, url, **kwargs):    return self._dispatch("GET",    url, **kwargs)
    def post(self, url, **kwargs):   return self._dispatch("POST",   url, **kwargs)
    def put(self, url, **kwargs):    return self._dispatch("PUT",    url, **kwargs)
    def delete(self, url, **kwargs): return self._dispatch("DELETE", url, **kwargs)


class RestBackendTests(unittest.TestCase):

    URL = "http://kc.local:8083"

    def setUp(self):
        self.fake = FakeRequests()
        self.patcher = patch("app.services.connect.rest_backend.requests", self.fake)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.backend = RestBackend({"url": self.URL})

    def test_exists_true_on_200(self):
        self.fake.queue("GET", f"{self.URL}/connectors/pg", FakeResponse(200, {"name": "pg"}))
        self.assertTrue(self.backend.exists("pg"))

    def test_exists_false_on_404(self):
        self.fake.queue("GET", f"{self.URL}/connectors/pg", FakeResponse(404, text="not found"))
        self.assertFalse(self.backend.exists("pg"))

    def test_exists_raises_on_500(self):
        self.fake.queue("GET", f"{self.URL}/connectors/pg", FakeResponse(500, text="boom"))
        with self.assertRaises(RuntimeError):
            self.backend.exists("pg")

    def test_deploy_new_uses_post(self):
        self.fake.queue("PUT", f"{self.URL}/connector-plugins/X/config/validate",
                        FakeResponse(200, {"error_count": 0, "configs": []}))
        self.fake.queue("GET", f"{self.URL}/connectors/pg", FakeResponse(404))
        self.fake.queue("POST", f"{self.URL}/connectors", FakeResponse(201, {"name": "pg"}))
        self.backend.deploy("pg", {"connector.class": "X"})
        method, url, kwargs = self.fake.calls[-1]
        self.assertEqual((method, url), ("POST", f"{self.URL}/connectors"))
        self.assertEqual(kwargs["json"], {"name": "pg", "config": {"connector.class": "X"}})
        validate_body = self.fake.calls[0][2]["json"]
        self.assertEqual(validate_body["name"], "pg")
        self.assertEqual(validate_body["connector.class"], "X")

    def test_deploy_existing_uses_put(self):
        self.fake.queue("PUT", f"{self.URL}/connector-plugins/X/config/validate",
                        FakeResponse(200, {"error_count": 0, "configs": []}))
        self.fake.queue("GET", f"{self.URL}/connectors/pg", FakeResponse(200, {"name": "pg"}))
        self.fake.queue("PUT", f"{self.URL}/connectors/pg/config", FakeResponse(200, {}))
        self.backend.deploy("pg", {"connector.class": "X"})
        method, url, kwargs = self.fake.calls[-1]
        self.assertEqual((method, url), ("PUT", f"{self.URL}/connectors/pg/config"))
        self.assertEqual(kwargs["json"], {"connector.class": "X"})

    def test_deploy_error_raises(self):
        self.fake.queue("PUT", f"{self.URL}/connector-plugins/X/config/validate",
                        FakeResponse(200, {"error_count": 0, "configs": []}))
        self.fake.queue("GET", f"{self.URL}/connectors/pg", FakeResponse(404))
        self.fake.queue("POST", f"{self.URL}/connectors", FakeResponse(400, text="bad request"))
        with self.assertRaises(RuntimeError):
            self.backend.deploy("pg", {"connector.class": "X"})

    def test_deploy_raises_config_validation_error_on_field_errors(self):
        from app.services.connect.rest_backend import ConfigValidationError
        # Simulate KC reporting two missing fields.
        report = {
            "error_count": 2, "configs": [
                {"definition": {"name": "database.hostname"},
                 "value": {"name": "database.hostname", "value": None,
                           "errors": ["Missing required configuration \"database.hostname\""]}},
                {"definition": {"name": "database.user"},
                 "value": {"name": "database.user", "value": None,
                           "errors": ["Missing required configuration \"database.user\""]}},
            ],
        }
        self.fake.queue("PUT", f"{self.URL}/connector-plugins/X/config/validate",
                        FakeResponse(200, report))
        with self.assertRaises(ConfigValidationError) as ctx:
            self.backend.deploy("pg", {"connector.class": "X"})
        # No create/update call was made — validation must abort before touching /connectors.
        self.assertEqual([c for c in self.fake.calls if "/connectors/pg" in c[1]], [])
        err = ctx.exception
        self.assertEqual(err.plugin_class, "X")
        self.assertEqual(len(err.field_errors), 2)
        self.assertEqual(err.field_errors[0]["field"], "database.hostname")

    def test_deploy_skips_validate_when_connector_class_missing(self):
        # No connector.class — nothing to validate against, deploy proceeds to POST /connectors.
        self.fake.queue("GET", f"{self.URL}/connectors/pg", FakeResponse(404))
        self.fake.queue("POST", f"{self.URL}/connectors", FakeResponse(400, text="config error"))
        with self.assertRaises(RuntimeError):
            self.backend.deploy("pg", {})
        # No validate call was made.
        self.assertEqual([c for c in self.fake.calls if "/config/validate" in c[1]], [])

    def test_poll_status_running(self):
        self.fake.queue(
            "GET", f"{self.URL}/connectors/pg/status",
            FakeResponse(200, {"connector": {"state": "RUNNING"}, "tasks": [{"state": "RUNNING"}]}),
        )
        self.assertEqual(self.backend.poll_status("pg"), "RUNNING")

    def test_poll_status_failed_task_overrides_running_connector(self):
        self.fake.queue(
            "GET", f"{self.URL}/connectors/pg/status",
            FakeResponse(200, {"connector": {"state": "RUNNING"}, "tasks": [{"state": "FAILED"}]}),
        )
        self.assertEqual(self.backend.poll_status("pg"), "FAILED")

    def test_poll_status_starting_task_is_not_running(self):
        self.fake.queue(
            "GET", f"{self.URL}/connectors/pg/status",
            FakeResponse(200, {
                "connector": {"state": "RUNNING"},
                "tasks": [{"state": "RUNNING"}, {"state": "STARTING"}],
            }),
        )
        self.assertEqual(self.backend.poll_status("pg"), "STARTING")

    def test_poll_status_404_returns_unknown(self):
        self.fake.queue("GET", f"{self.URL}/connectors/pg/status", FakeResponse(404))
        self.assertEqual(self.backend.poll_status("pg"), "UNKNOWN")

    def test_delete_success(self):
        self.fake.queue("DELETE", f"{self.URL}/connectors/pg", FakeResponse(204))
        self.backend.delete("pg")
        self.assertEqual(self.fake.calls[-1][0], "DELETE")

    def test_delete_404_is_not_an_error(self):
        self.fake.queue("DELETE", f"{self.URL}/connectors/pg", FakeResponse(404))
        self.backend.delete("pg")

    def test_delete_500_raises(self):
        self.fake.queue("DELETE", f"{self.URL}/connectors/pg", FakeResponse(500, text="oops"))
        with self.assertRaises(RuntimeError):
            self.backend.delete("pg")

    def test_basic_auth_forwarded(self):
        backend = RestBackend({"url": self.URL, "username": "u", "password": "p"})
        self.fake.queue("GET", f"{self.URL}/connectors/pg", FakeResponse(200, {"name": "pg"}))
        backend.exists("pg")
        self.assertEqual(self.fake.calls[-1][2]["auth"], ("u", "p"))


class ExtractFieldErrorsTests(unittest.TestCase):
    """Parser for KC /validate responses — small pure fn, easy to lock down."""

    def _run(self, report):
        from app.services.connect.rest_backend import _extract_field_errors
        return _extract_field_errors(report)

    def test_zero_errors_returns_empty(self):
        self.assertEqual(self._run({"error_count": 0, "configs": []}), [])

    def test_extracts_field_name_value_and_errors(self):
        report = {
            "error_count": 1,
            "configs": [{
                "definition": {"name": "database.hostname"},
                "value": {"name": "database.hostname", "value": None,
                          "errors": ["Missing required configuration \"database.hostname\""]},
            }],
        }
        out = self._run(report)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["field"], "database.hostname")
        self.assertIsNone(out[0]["value"])
        self.assertEqual(out[0]["errors"],
                         ["Missing required configuration \"database.hostname\""])

    def test_skips_entries_without_errors(self):
        report = {
            "error_count": 1,
            "configs": [
                {"value": {"name": "ok.key",  "value": "x", "errors": []}},
                {"value": {"name": "bad.key", "value": "y", "errors": ["Bad"]}},
            ],
        }
        out = self._run(report)
        self.assertEqual([e["field"] for e in out], ["bad.key"])

    def test_falls_back_to_definition_name_when_value_name_missing(self):
        report = {
            "error_count": 1,
            "configs": [{
                "definition": {"name": "fallback.name"},
                "value": {"value": "x", "errors": ["Bad"]},
            }],
        }
        self.assertEqual(self._run(report)[0]["field"], "fallback.name")

    def test_non_dict_input_returns_empty(self):
        self.assertEqual(self._run(None), [])
        self.assertEqual(self._run("not a dict"), [])


class EffectiveConnectStatusTests(unittest.TestCase):
    def test_running_requires_connector_and_all_tasks(self):
        self.assertEqual(effective_connect_status({
            "connector": {"state": "RUNNING"},
            "tasks": [{"state": "RUNNING"}, {"state": "RUNNING"}],
        }), "RUNNING")

    def test_connector_running_without_tasks_is_not_running(self):
        self.assertEqual(effective_connect_status({
            "connector": {"state": "RUNNING"},
            "tasks": [],
        }), "UNKNOWN")

    def test_paused_task_is_not_running(self):
        self.assertEqual(effective_connect_status({
            "connector": {"state": "RUNNING"},
            "tasks": [{"state": "RUNNING"}, {"state": "PAUSED"}],
        }), "PAUSED")


if __name__ == "__main__":
    unittest.main()
