import time
from urllib.parse import urljoin

import requests

from app.services.alerting.channels.base import Channel, DeliveryResult
from app.utils.logger import get_logger

log = get_logger(__name__)

_HTTP_TIMEOUT = 10


class SlackChannel(Channel):
    """Delivers to Slack Incoming Webhooks.

    Expected connection_config shape (matches saved Connection.config for notification-slack):
        {
          "host":     "https://hooks.slack.com",           # base URL
          "password": "/services/T0000/B0000/xxxxxxxxxxxx" # secret path
        }
    """

    SUBTYPE = "notification-slack"

    def validate(self, connection_config: dict) -> list[str]:
        errors: list[str] = []
        host = (connection_config.get("host") or "").strip()
        path = (connection_config.get("password") or "").strip()
        if not host:
            errors.append("Slack channel is missing 'host' (webhook base URL)")
        elif not host.startswith(("http://", "https://")):
            errors.append("Slack 'host' must be a full URL (starts with http:// or https://)")
        if not path:
            errors.append("Slack channel is missing 'password' (webhook path/token)")
        return errors

    def send(self, connection_config: dict, message: str, meta: dict | None = None) -> DeliveryResult:
        errs = self.validate(connection_config)
        if errs:
            return DeliveryResult(success=False, error="; ".join(errs))

        host = connection_config["host"].rstrip("/")
        path = connection_config["password"]
        if not path.startswith("/"):
            path = "/" + path
        webhook_url = host + path

        payload = {"text": message}

        started = time.monotonic()
        try:
            r = requests.post(webhook_url, json=payload, timeout=_HTTP_TIMEOUT)
        except requests.RequestException as e:
            return DeliveryResult(
                success=False,
                error=f"HTTP error: {e}",
                latency_ms=int((time.monotonic() - started) * 1000),
            )

        latency_ms = int((time.monotonic() - started) * 1000)
        ok = 200 <= r.status_code < 300
        # Slack returns literal "ok" body on success for Incoming Webhooks.
        return DeliveryResult(
            success=ok,
            http_status=r.status_code,
            error=None if ok else (r.text[:200] if r.text else f"HTTP {r.status_code}"),
            latency_ms=latency_ms,
        )
