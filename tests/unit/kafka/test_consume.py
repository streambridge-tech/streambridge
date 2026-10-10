"""Unit tests for topic listing and bounded consume."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from confluent_kafka import KafkaError

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


class PartitionEof:
    """What the consumer yields when it reaches the end of a partition."""

    def __init__(self, partition):
        self._partition = partition

    def error(self):
        return KafkaError(KafkaError._PARTITION_EOF)

    def partition(self):
        return self._partition


class LogConsumer(FakeConsumer):
    """Serves each assigned partition from its start offset to the end, then EOF, like Kafka."""

    def __init__(self, logs: dict[int, list[int]]):
        end = {part: max(offsets) + 1 for part, offsets in logs.items()}
        beginning = {part: min(offsets) for part, offsets in logs.items()}
        super().__init__(partitions=sorted(logs), beginning=beginning, end=end)
        self._logs = logs

    def assign(self, tps):
        super().assign(tps)
        self._records = []
        for tp in tps:
            self._records += [FakeMessage(tp.partition, offset, None, b"v")
                              for offset in self._logs[tp.partition] if offset >= tp.offset]
            self._records.append(PartitionEof(tp.partition))
        self._index = 0


def _page_back(logs, limit, max_pages=100):
    """Load the newest page, then "Load older" until hasOlder is False."""
    seen, before = [], None
    for _ in range(max_pages):
        fake = LogConsumer(logs)
        payload = consume_messages(
            {"bootstrap.servers": "kafka:9092"}, "orders",
            limit=limit, before=before, consumer_factory=lambda _conf: fake,
        )
        seen += [(item["partition"], item["offset"]) for item in payload["messages"]]
        if not payload["hasOlder"]:
            return seen
        before = payload["cursor"]
    raise AssertionError(f"still hasOlder after {max_pages} pages; seen {len(seen)} records")


class OlderPagingTests(unittest.TestCase):
    def test_pages_back_through_partitions_of_different_depth(self):
        seen = _page_back({0: list(range(10)), 1: list(range(30))}, limit=10)
        self.assertEqual(len(seen), len(set(seen)), "a record was served twice")
        self.assertEqual(set(seen), {(0, o) for o in range(10)} | {(1, o) for o in range(30)})

    def test_exhausted_partition_is_not_fetched_and_keeps_its_cursor(self):
        fake = LogConsumer({0: list(range(10)), 1: list(range(30))})
        payload = consume_messages(
            {"bootstrap.servers": "kafka:9092"}, "orders",
            limit=10, before={"0": 0, "1": 20}, consumer_factory=lambda _conf: fake,
        )
        self.assertEqual([tp.partition for tp in fake.assigned], [1])
        self.assertEqual({item["partition"] for item in payload["messages"]}, {1})
        self.assertEqual(payload["cursor"], {"0": 0, "1": 15})
        self.assertTrue(payload["hasOlder"])

    def test_last_partition_reaching_its_start_ends_paging(self):
        fake = LogConsumer({0: list(range(10)), 1: list(range(30))})
        payload = consume_messages(
            {"bootstrap.servers": "kafka:9092"}, "orders",
            limit=10, before={"0": 0, "1": 5}, consumer_factory=lambda _conf: fake,
        )
        self.assertEqual(payload["cursor"], {"0": 0, "1": 0})
        self.assertFalse(payload["hasOlder"])

    def test_compacted_gap_still_reaches_the_oldest_records(self):
        seen = _page_back({0: [0, 1, 50, 51]}, limit=2)
        self.assertEqual(sorted(seen), [(0, 0), (0, 1), (0, 50), (0, 51)])

    def test_partition_that_did_not_answer_is_retried_not_skipped(self):
        fake = FakeConsumer(records=[], partitions=[0], beginning={0: 0}, end={0: 30})
        payload = consume_messages(
            {"bootstrap.servers": "kafka:9092"}, "orders",
            limit=10, before={"0": 20}, consumer_factory=lambda _conf: fake,
        )
        self.assertEqual(payload["cursor"], {"0": 20})
        self.assertTrue(payload["hasOlder"])


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
