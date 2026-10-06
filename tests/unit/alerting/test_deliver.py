import unittest
from unittest.mock import MagicMock, patch

from app.services.alerting.channels.base import DeliveryResult
from app.services.alerting.deliver import compose_alert_message, deliver_test, find_notification_connections, fire_alert


def _conn(cid, name, subtype="notification-slack"):
    c = MagicMock()
    c.id = cid
    c.name = name
    c.subtype = subtype
    c.config = {"host": "https://hooks.example", "password": "/x"}
    return c


class TestFindNotificationConnections(unittest.TestCase):
    def test_splits_comma_names(self):
        db = MagicMock()
        a = _conn(1, "prod")
        b = _conn(2, "dev")
        db.query.return_value.filter.return_value.first.side_effect = [a, b]
        alert = MagicMock(channel_name="prod, dev", channel_type="slack")
        found = find_notification_connections(db, alert)
        self.assertEqual([c.name for c in found], ["prod", "dev"])


class TestDeliverTest(unittest.TestCase):
    @patch("app.services.alerting.deliver.get_channel")
    def test_sends_to_every_named_channel(self, get_ch):
        db = MagicMock()
        a = _conn(1, "prod")
        b = _conn(2, "dev")
        db.query.return_value.filter.return_value.first.side_effect = [a, b]
        ch = MagicMock()
        ch.send.return_value = DeliveryResult(success=True, http_status=200, latency_ms=10)
        get_ch.return_value = ch
        alert = MagicMock(id="a-1", channel_name="prod, dev", channel_type="slack", connector_name="pg")
        body, status = deliver_test(db, alert)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertEqual(len(body["channels"]), 2)
        self.assertEqual(ch.send.call_count, 2)
        self.assertEqual(db.add.call_count, 1)
        self.assertEqual(db.add.call_args.args[0].kind, "test")


class TestFireAlertPersists(unittest.TestCase):
    @patch("app.services.alerting.deliver.get_channel")
    def test_writes_delivery_row_with_status_and_message(self, get_ch):
        db = MagicMock()
        conn = _conn(5, "de-oncall-prod", "notification-gchat")
        db.query.return_value.filter.return_value.first.return_value = conn
        ch = MagicMock()
        ch.send.return_value = DeliveryResult(success=True, http_status=200, latency_ms=12)
        get_ch.return_value = ch
        alert = MagicMock(
            id="a-1",
            channel_name="de-oncall-prod",
            channel_type="gchat",
            connector_name="mysql-apicurio-002",
            message="StreamBridge: connector mysql-apicurio-002 is PAUSED",
        )
        fire_alert(db, alert, "PAUSED", action="re-trigger")
        db.add.assert_called_once()
        row = db.add.call_args.args[0]
        self.assertEqual(row.kind, "fire")
        self.assertEqual(row.status, "PAUSED")
        self.assertEqual(row.message, "mysql-apicurio-002 was paused. StreamBridge re-triggered it.")
        self.assertTrue(row.log_text)
        self.assertEqual(row.success, 1)
        db.commit.assert_called_once()


class TestComposeMessage(unittest.TestCase):
    def test_paused_retrigger(self):
        self.assertEqual(
            compose_alert_message("mysql-apicurio-002", "PAUSED", "re-trigger"),
            "mysql-apicurio-002 was paused. StreamBridge re-triggered it.",
        )

    def test_failed_pause(self):
        self.assertEqual(
            compose_alert_message("mysql-apicurio-002", "PAUSED", "notify"),
            "mysql-apicurio-002 was paused.",
        )
