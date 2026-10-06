"""Unit tests for topic listing and bounded consume."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services.kafka.consume import consume_messages, list_topics
from app.services.kafka.errors import KafkaBrowseError


class FakeAdmin:
    def __init__(self, topics=None):
        self._topics = topics or {"orders": [0, 1, 2], "users": [0, 1]}

    def list_topics(self, timeout=None):
        topics = {}
        for name, parts in self._topics.items():
            topics[name] = SimpleNamespace(partitions={p: object() for p in parts}, error=None)
        return SimpleNamespace(topics=topics)


class FakeMessage:
    def __init__(self, partition, offset, key, value, timestamp=1_700_000_000_000):
        self._partition = partition
        self._offset = offset
        self._key = key
        self._value = value
        self._timestamp = timestamp

    def error(self):
        return None

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset

    def key(self):
        return self._key

    def value(self):
        return self._value

    def timestamp(self):
        return (1, self._timestamp)


class FakeConsumer:
    def __init__(self, records=None, partitions=None, beginning=None, end=None, topics=None):
        self._records = list(records or [])
        self._partitions = partitions or [0, 1]
        self._beginning = beginning or {0: 0, 1: 0}
        self._end = end or {0: 10, 1: 10}
        self._topics = topics if topics is not None else ["orders"]
        self._index = 0
        self.assigned = []
        self.seeks = {}
        self.closed = False

    def list_topics(self, topic=None, timeout=None):
        names = self._topics if topic is None else [topic] if topic in (self._topics or [topic]) else []
        topics = {}
        for name in names:
            topics[name] = SimpleNamespace(
                partitions={p: object() for p in self._partitions},
                error=None,
            )
        return SimpleNamespace(topics=topics)

    def get_watermark_offsets(self, tp, timeout=None):
        return (self._beginning.get(tp.partition, 0), self._end.get(tp.partition, 0))

    def assign(self, tps):
        self.assigned = list(tps)
        self.seeks = {tp.partition: tp.offset for tp in tps}

    def poll(self, timeout=None):
        if self._index >= len(self._records):
            return None
        message = self._records[self._index]
        self._index += 1
        return message

    def close(self):
        self.closed = True


class ListTopicsTests(unittest.TestCase):
    def test_returns_sorted_topics_with_partition_counts(self):
        fake = FakeAdmin(topics={"users": [0, 1, 2], "orders": [0, 1, 2]})
        topics = list_topics({"bootstrap.servers": "kafka:9092"}, admin_factory=lambda _conf: fake)
        self.assertEqual([item["name"] for item in topics], ["orders", "users"])
        self.assertEqual(topics[0]["partitions"], 3)

    def test_wraps_client_errors(self):
        def boom(_conf):
            raise RuntimeError("broker down")
        with self.assertRaises(KafkaBrowseError):
            list_topics({"bootstrap.servers": "kafka:9092"}, admin_factory=boom)


class ConsumeTests(unittest.TestCase):
    def _config(self):
        return {"bootstrap.servers": "kafka:9092", "security.protocol": "PLAINTEXT"}

    def test_requires_topic(self):
        with self.assertRaises(KafkaBrowseError):
            consume_messages(self._config(), "  ", consumer_factory=lambda _conf: FakeConsumer())

    def test_returns_latest_decoded_records(self):
        records = [
            FakeMessage(0, 8, b"k1", b'{"id":1}'),
            FakeMessage(0, 9, b"k2", b'{"id":2}'),
            FakeMessage(0, 10, b"k3", None),
        ]
        fake = FakeConsumer(records=records, partitions=[0], beginning={0: 0}, end={0: 11})
        payload = consume_messages(self._config(), "orders", limit=10, consumer_factory=lambda _conf: fake)
        self.assertEqual(payload["topic"], "orders")
        self.assertEqual(payload["count"], 3)
        self.assertTrue(payload["messages"][0]["offset"] >= payload["messages"][-1]["offset"])
        self.assertTrue(any(item["tombstone"] for item in payload["messages"]))
        self.assertIn(0, fake.seeks)
        self.assertTrue(fake.closed)

    def test_before_cursor_stops_at_older_offsets(self):
        records = [FakeMessage(0, 4, b"a", b"one"), FakeMessage(0, 5, b"b", b"two")]
        fake = FakeConsumer(records=records, partitions=[0], beginning={0: 0}, end={0: 10})
        payload = consume_messages(
            self._config(),
            "orders",
            limit=10,
            before={"0": 5},
            consumer_factory=lambda _conf: fake,
        )
        offsets = [item["offset"] for item in payload["messages"]]
        self.assertEqual(offsets, [4])
        self.assertTrue(payload["hasOlder"])

    def test_rejects_unknown_partition(self):
        fake = FakeConsumer(partitions=[0])
        with self.assertRaises(KafkaBrowseError):
            consume_messages(self._config(), "orders", partition=9, consumer_factory=lambda _conf: fake)


if __name__ == "__main__":
    unittest.main()
