import unittest
from unittest.mock import MagicMock, patch

from app.services.alerting.channels.factory import get_channel, supported_subtypes
from app.services.alerting.channels.slack import SlackChannel
from app.services.alerting.channels.gchat import GChatChannel


class TestFactory(unittest.TestCase):
    def test_returns_slack(self):
        self.assertIsInstance(get_channel("notification-slack"), SlackChannel)

    def test_returns_gchat(self):
        self.assertIsInstance(get_channel("notification-gchat"), GChatChannel)

    def test_case_insensitive(self):
        self.assertIsInstance(get_channel("NOTIFICATION-SLACK"), SlackChannel)

    def test_unknown_returns_none(self):
        self.assertIsNone(get_channel("notification-email"))
        self.assertIsNone(get_channel(""))
        self.assertIsNone(get_channel(None))  # type: ignore[arg-type]

    def test_supported_subtypes(self):
        self.assertEqual(
            supported_subtypes(),
            ["notification-gchat", "notification-slack"],
        )


class TestSlackValidate(unittest.TestCase):
    def setUp(self):
        self.ch = SlackChannel()

    def test_valid_config(self):
        self.assertEqual(self.ch.validate({"host": "https://hooks.slack.com", "password": "/services/T00/B00/xxx"}), [])

    def test_missing_host(self):
        errs = self.ch.validate({"host": "", "password": "/services/T00/B00/xxx"})
        self.assertTrue(any("host" in e for e in errs))

    def test_bad_host_scheme(self):
        errs = self.ch.validate({"host": "hooks.slack.com", "password": "/services/T00/B00/xxx"})
        self.assertTrue(any("http" in e for e in errs))

    def test_missing_password(self):
        errs = self.ch.validate({"host": "https://hooks.slack.com", "password": ""})
        self.assertTrue(any("password" in e for e in errs))


class TestSlackSend(unittest.TestCase):
    def setUp(self):
        self.ch = SlackChannel()
        self.cfg = {"host": "https://hooks.slack.com", "password": "/services/T00/B00/xxx"}

    def _mock_response(self, status_code: int = 200, text: str = "ok"):
        r = MagicMock()
        r.status_code = status_code
        r.text = text
        return r

    def test_success(self):
        with patch("app.services.alerting.channels.slack.requests.post", return_value=self._mock_response()) as post:
            result = self.ch.send(self.cfg, "hello")
        self.assertTrue(result.success)
        self.assertEqual(result.http_status, 200)
        self.assertIsNone(result.error)
        post.assert_called_once()
        url = post.call_args.args[0]
        self.assertEqual(url, "https://hooks.slack.com/services/T00/B00/xxx")
        self.assertEqual(post.call_args.kwargs["json"], {"text": "hello"})

    def test_url_normalization_trailing_slash(self):
        cfg = {"host": "https://hooks.slack.com/", "password": "services/T00/B00/xxx"}
        with patch("app.services.alerting.channels.slack.requests.post", return_value=self._mock_response()) as post:
            self.ch.send(cfg, "hi")
        self.assertEqual(post.call_args.args[0], "https://hooks.slack.com/services/T00/B00/xxx")

    def test_http_error_status(self):
        with patch("app.services.alerting.channels.slack.requests.post", return_value=self._mock_response(500, "invalid_payload")):
            result = self.ch.send(self.cfg, "hello")
        self.assertFalse(result.success)
        self.assertEqual(result.http_status, 500)
        self.assertIn("invalid_payload", result.error or "")

    def test_network_error(self):
        import requests as _rq
        with patch("app.services.alerting.channels.slack.requests.post", side_effect=_rq.ConnectionError("dns fail")):
            result = self.ch.send(self.cfg, "hello")
        self.assertFalse(result.success)
        self.assertIn("dns fail", result.error or "")

    def test_invalid_config_short_circuits_before_post(self):
        with patch("app.services.alerting.channels.slack.requests.post") as post:
            result = self.ch.send({"host": "", "password": ""}, "hello")
        self.assertFalse(result.success)
        post.assert_not_called()

    def test_test_method_uses_canned_message(self):
        with patch("app.services.alerting.channels.slack.requests.post", return_value=self._mock_response()) as post:
            self.ch.test(self.cfg)
        self.assertIn("StreamBridge", post.call_args.kwargs["json"]["text"])


class TestGChatValidate(unittest.TestCase):
    def setUp(self):
        self.ch = GChatChannel()

    def test_valid_config(self):
        self.assertEqual(
            self.ch.validate({"host": "https://chat.googleapis.com", "password": "/v1/spaces/AAA/messages?key=1&token=2"}),
            [],
        )

    def test_missing_password(self):
        errs = self.ch.validate({"host": "https://chat.googleapis.com", "password": ""})
        self.assertTrue(any("password" in e for e in errs))


class TestGChatSend(unittest.TestCase):
    def setUp(self):
        self.ch = GChatChannel()
        self.cfg = {"host": "https://chat.googleapis.com", "password": "/v1/spaces/AAA/messages?key=1&token=2"}

    def _mock_response(self, status_code: int = 200, text: str = ""):
        r = MagicMock()
        r.status_code = status_code
        r.text = text
        return r

    def test_success(self):
        with patch("app.services.alerting.channels.gchat.requests.post", return_value=self._mock_response()) as post:
            result = self.ch.send(self.cfg, "ping")
        self.assertTrue(result.success)
        self.assertEqual(
            post.call_args.args[0],
            "https://chat.googleapis.com/v1/spaces/AAA/messages?key=1&token=2",
        )

    def test_http_error(self):
        with patch("app.services.alerting.channels.gchat.requests.post", return_value=self._mock_response(403, "PERMISSION_DENIED")):
            result = self.ch.send(self.cfg, "ping")
        self.assertFalse(result.success)
        self.assertEqual(result.http_status, 403)


if __name__ == "__main__":
    unittest.main()
