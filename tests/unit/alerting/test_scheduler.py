import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

from app.services.alerting.scheduler import (
    AlertScheduler,
    apply_match_action,
    bound_connector_name,
    is_due,
    poll_connector,
    resolve_kc_connection,
    rule_matches,
    _status_from_payload,
)


def _alert(**kw):
    a = MagicMock()
    a.id = kw.get("id", "a1")
    a.active = True
    a.check_every_min = kw.get("check_every_min", 5)
    a.condition_value = kw.get("condition_value", "FAILED")
    a.connector_name = kw.get("connector_name", "pg-src")
    a.pipeline_id = kw.get("pipeline_id")
    a.match_action = kw.get("match_action", "pause")
    return a


class TestNotebookBinding(unittest.TestCase):
    def test_poll_name_and_cluster_come_from_the_notebook(self):
        notebook = MagicMock()
        notebook.name = "orders-src"
        notebook.attached_cluster = "kc-dev"
        conn = MagicMock()
        db = MagicMock()
        db.get.return_value = notebook
        db.query.return_value.filter.return_value.first.return_value = conn
        alert = MagicMock()
        alert.notebook_id = "nb-1"
        alert.connector_name = "stale-name"
        alert.pipeline_id = "old-pipe"
        self.assertEqual(bound_connector_name(db, alert), "orders-src")
        self.assertIs(resolve_kc_connection(db, alert), conn)

    def test_missing_notebook_keeps_the_stored_name(self):
        db = MagicMock()
        db.get.return_value = None
        alert = MagicMock()
        alert.notebook_id = "nb-gone"
        alert.connector_name = "orders-src"
        self.assertEqual(bound_connector_name(db, alert), "orders-src")


class TestRuleAndDue(unittest.TestCase):
    def test_failed_and_unknown_match_only_themselves(self):
        failed = _alert(condition_value="FAILED")
        unknown = _alert(condition_value="UNKNOWN")
        self.assertTrue(rule_matches(failed, "FAILED"))
        self.assertFalse(rule_matches(failed, "UNKNOWN"))
        self.assertFalse(rule_matches(failed, "RUNNING"))
        self.assertTrue(rule_matches(unknown, "UNKNOWN"))
        self.assertFalse(rule_matches(unknown, "FAILED"))

    def test_paused_matches_only_paused(self):
        paused = _alert(condition_value="PAUSED")
        self.assertTrue(rule_matches(paused, "PAUSED"))
        self.assertFalse(rule_matches(paused, "FAILED"))
        self.assertFalse(rule_matches(paused, "RUNNING"))

    def test_due_when_never_checked_or_interval_elapsed(self):
        now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
        a = _alert(check_every_min=10)
        self.assertTrue(is_due(a, now, {}))
        self.assertFalse(is_due(a, now, {a.id: now - timedelta(minutes=9)}))
        self.assertTrue(is_due(a, now, {a.id: now - timedelta(minutes=10)}))


class TestPollConnector(unittest.TestCase):
    def test_missing_backend_is_unknown(self):
        self.assertEqual(poll_connector(None, "pg"), "UNKNOWN")

    def test_poll_error_is_unknown(self):
        backend = MagicMock()
        backend.poll_status.side_effect = RuntimeError("kc down")
        self.assertEqual(poll_connector(backend, "pg"), "UNKNOWN")

    def test_task_failed_status_passthrough(self):
        backend = MagicMock()
        backend.poll_status.return_value = "FAILED"
        self.assertEqual(poll_connector(backend, "pg"), "FAILED")

    def test_status_payload_running_needs_all_tasks(self):
        self.assertEqual(_status_from_payload({
            "connector": {"state": "RUNNING"},
            "tasks": [{"state": "RUNNING"}, {"state": "FAILED"}],
        }), "FAILED")
        self.assertEqual(_status_from_payload({
            "connector": {"state": "RUNNING"},
            "tasks": [{"state": "RUNNING"}],
        }), "RUNNING")
        self.assertNotEqual(_status_from_payload({
            "connector": {"state": "RUNNING"},
            "tasks": [{"state": "STARTING"}],
        }), "RUNNING")


class TestSchedulerTick(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        session = MagicMock()
        session.__enter__.return_value = self.db
        session.__exit__.return_value = False
        self.sched = AlertScheduler(wake_sec=1, session_factory=lambda: session)
        self.now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)

    def _alerts(self, rows):
        self.db.query.return_value.filter.return_value.all.return_value = rows

    @patch("app.services.alerting.scheduler.fire_alert")
    @patch("app.services.alerting.scheduler.poll_connector_snapshot", return_value={"status": "RUNNING", "log": "State: RUNNING"})
    @patch("app.services.alerting.scheduler.resolve_kc_backend")
    def test_running_does_not_fire(self, _kc, _poll, fire):
        self._alerts([_alert()])
        self.sched.tick(self.now)
        fire.assert_not_called()
        self.assertEqual(self.sched.last_status["a1"], "RUNNING")

    @patch("app.services.alerting.scheduler.fire_alert")
    @patch("app.services.alerting.scheduler.poll_connector_snapshot", return_value={"status": "FAILED", "log": "State: FAILED"})
    @patch("app.services.alerting.scheduler.resolve_kc_backend")
    def test_failed_refires_each_interval(self, _kc, _poll, fire):
        alert = _alert()
        self._alerts([alert])
        self.sched.tick(self.now)
        fire.assert_called_once()
        fire.reset_mock()
        later = self.now + timedelta(minutes=5)
        self.sched.tick(later)
        fire.assert_called_once()

    @patch("app.services.alerting.scheduler.fire_alert")
    @patch("app.services.alerting.scheduler.poll_connector_snapshot")
    @patch("app.services.alerting.scheduler.resolve_kc_backend")
    def test_refires_after_recovery(self, _kc, poll, fire):
        alert = _alert()
        self._alerts([alert])
        poll.return_value = {"status": "FAILED", "log": "State: FAILED"}
        self.sched.tick(self.now)
        poll.return_value = {"status": "RUNNING", "log": "State: RUNNING"}
        self.sched.tick(self.now + timedelta(minutes=5))
        fire.reset_mock()
        poll.return_value = {"status": "FAILED", "log": "State: FAILED"}
        self.sched.tick(self.now + timedelta(minutes=10))
        fire.assert_called_once()

    @patch("app.services.alerting.scheduler.fire_alert")
    @patch("app.services.alerting.scheduler.poll_connector_snapshot")
    @patch("app.services.alerting.scheduler.resolve_kc_backend")
    def test_not_due_skips_poll(self, _kc, poll, fire):
        alert = _alert(check_every_min=60)
        self._alerts([alert])
        self.sched.last_checked[alert.id] = self.now
        self.sched.tick(self.now + timedelta(minutes=10))
        poll.assert_not_called()
        fire.assert_not_called()

    @patch("app.services.alerting.scheduler.fire_alert")
    @patch("app.services.alerting.scheduler.poll_connector_snapshot", return_value={"status": "UNKNOWN", "log": "State: UNKNOWN"})
    @patch("app.services.alerting.scheduler.resolve_kc_backend")
    def test_unknown_rule_fires_on_unknown(self, _kc, _poll, fire):
        alert = _alert(condition_value="UNKNOWN")
        self._alerts([alert])
        self.sched.tick(self.now)
        fire.assert_called_once()

    @patch("app.services.alerting.scheduler.fire_alert")
    @patch("app.services.alerting.scheduler.poll_connector_snapshot", return_value={"status": "PAUSED", "log": "State: PAUSED"})
    @patch("app.services.alerting.scheduler.resolve_kc_backend")
    def test_first_matching_rule_wins(self, _kc, _poll, fire):
        alert = _alert()
        alert.rules_json = '[{"rule":"FAILED","action":"re-trigger"},{"rule":"PAUSED","action":"notify"}]'
        self._alerts([alert])
        self.sched.tick(self.now)
        fire.assert_called_once()
        self.assertEqual(fire.call_args.kwargs["action"], "notify")


class TestMatchAction(unittest.TestCase):
    def test_pause_calls_backend_pause(self):
        backend = MagicMock()
        apply_match_action(backend, "pg-src", "FAILED", "pause")
        backend.pause.assert_called_once_with("pg-src")
        backend.restart.assert_not_called()

    def test_retrigger_restarts_failed_tasks_only(self):
        backend = MagicMock()
        snap = {
            "raw": {
                "connector": {"state": "RUNNING"},
                "tasks": [
                    {"id": 0, "state": "FAILED"},
                    {"id": 1, "state": "RUNNING"},
                ],
            }
        }
        apply_match_action(backend, "pg-src", "FAILED", "re-trigger", snapshot=snap)
        backend.restart.assert_not_called()
        backend.restart_task.assert_called_once_with("pg-src", 0)
        backend.resume.assert_not_called()

    def test_retrigger_restarts_all_tasks_when_none_failed(self):
        backend = MagicMock()
        snap = {
            "raw": {
                "connector": {"state": "RUNNING"},
                "tasks": [{"id": 0, "state": "STARTING"}, {"id": "1", "state": "RUNNING"}],
            }
        }
        apply_match_action(backend, "pg-src", "UNKNOWN", "re-trigger", snapshot=snap)
        backend.restart.assert_not_called()
        self.assertEqual(backend.restart_task.call_args_list, [
            call("pg-src", 0),
            call("pg-src", 1),
        ])

    def test_retrigger_paused_calls_resume(self):
        backend = MagicMock()
        apply_match_action(backend, "pg-src", "PAUSED", "re-trigger")
        backend.resume.assert_called_once_with("pg-src")
        backend.restart.assert_not_called()

    def test_notify_does_not_touch_connect(self):
        backend = MagicMock()
        result = apply_match_action(backend, "pg-src", "PAUSED", "notify")
        self.assertTrue(result["ok"])
        backend.pause.assert_not_called()
        backend.resume.assert_not_called()
        backend.restart.assert_not_called()

    def test_pause_skipped_when_already_paused(self):
        backend = MagicMock()
        result = apply_match_action(backend, "pg-src", "PAUSED", "pause")
        self.assertTrue(result["ok"])
        backend.pause.assert_not_called()


class TestFindChannels(unittest.TestCase):
    def test_splits_comma_names(self):
        from app.services.alerting.deliver import channel_names
        a = MagicMock(channel_name="de-oncall-prod, de-oncall-dev")
        self.assertEqual(channel_names(a), ["de-oncall-prod", "de-oncall-dev"])


if __name__ == "__main__":
    unittest.main()
