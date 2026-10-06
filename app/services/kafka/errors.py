"""Errors while listing topics or consuming records."""


class KafkaBrowseError(RuntimeError):
    """A Kafka browse request failed."""
