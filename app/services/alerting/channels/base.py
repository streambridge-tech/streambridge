from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeliveryResult:
    success: bool
    http_status: int | None = None
    error: str | None = None
    latency_ms: int = 0


class Channel(ABC):
    """Abstract delivery target for an alert notification.

    Concrete channels: SlackChannel, GChatChannel (Phase 1).
    Future: WebhookChannel, PagerDutyChannel, EmailChannel.
    """

    SUBTYPE: str = ""

    @abstractmethod
    def validate(self, connection_config: dict) -> list[str]:
        """Return list of validation error messages. Empty = valid."""

    @abstractmethod
    def send(self, connection_config: dict, message: str, meta: dict | None = None) -> DeliveryResult:
        """Deliver `message` to this channel. `meta` is optional context for templating."""

    def test(self, connection_config: dict) -> DeliveryResult:
        """Send a canned test message. Default implementation reuses `send`."""
        return self.send(
            connection_config,
            "✅ StreamBridge test notification — this channel is wired up correctly.",
            meta={"kind": "test"},
        )
