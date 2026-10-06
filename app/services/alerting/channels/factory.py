from app.services.alerting.channels.base import Channel
from app.services.alerting.channels.gchat import GChatChannel
from app.services.alerting.channels.slack import SlackChannel

_REGISTRY: dict[str, Channel] = {
    SlackChannel.SUBTYPE: SlackChannel(),
    GChatChannel.SUBTYPE: GChatChannel(),
}


def get_channel(connection_subtype: str) -> Channel | None:
    """Return the Channel instance for a given Connection.subtype, or None if unsupported."""
    return _REGISTRY.get((connection_subtype or "").lower())


def supported_subtypes() -> list[str]:
    return sorted(_REGISTRY.keys())
