"""List topics and consume a bounded window of records via confluent-kafka."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition
from confluent_kafka.admin import AdminClient

from app.services.kafka.client import STANDARD_TIMEOUT_SEC, kafka_client_config
from app.services.kafka.decode import decode_payload
from app.services.kafka.errors import KafkaBrowseError
from app.services.schema_registry.base import SchemaRegistry

MAX_LIMIT = 100


def _admin_config(config: dict) -> dict:
    return kafka_client_config(config)


def _consumer_config(config: dict) -> dict:
    conf = kafka_client_config(config)
    conf.update({
        "group.id": f"streambridge-browse-{uuid4().hex[:10]}",
        "enable.auto.commit": "false",
        "auto.offset.reset": "earliest",
        "enable.partition.eof": "true",
        "allow.auto.create.topics": "false",
    })
    return conf


def list_topics(config: dict, *, admin_factory: Callable | None = None) -> list[dict]:
    factory = admin_factory or (lambda conf: AdminClient(conf))
    try:
        admin = factory(_admin_config(config))
        metadata = admin.list_topics(timeout=STANDARD_TIMEOUT_SEC)
    except KafkaBrowseError:
        raise
    except Exception as exc:
        raise KafkaBrowseError(str(exc)) from exc

    topics = []
    for name in sorted(metadata.topics or {}):
        meta = metadata.topics[name]
        error = getattr(meta, "error", None)
        if error is not None:
            continue
        partitions = sorted((meta.partitions or {}).keys())
        topics.append({"name": name, "partitions": len(partitions), "partitionIds": partitions})
    return topics


def consume_messages(
    config: dict,
    topic: str,
    *,
    limit: int = 50,
    partition: int | None = None,
    before: dict | None = None,
    key_format: str = "auto",
    value_format: str = "auto",
    registry: SchemaRegistry | None = None,
    key_subject: str | None = None,
    value_subject: str | None = None,
    consumer_factory: Callable | None = None,
) -> dict:
    topic = (topic or "").strip()
    if not topic:
        raise KafkaBrowseError("topic is required")
    limit = max(1, min(int(limit or 50), MAX_LIMIT))
    factory = consumer_factory or (lambda conf: Consumer(conf))
    try:
        consumer = factory(_consumer_config(config))
    except Exception as exc:
        raise KafkaBrowseError(str(exc)) from exc

    try:
        metadata = consumer.list_topics(topic, timeout=STANDARD_TIMEOUT_SEC)
        topic_meta = (metadata.topics or {}).get(topic)
        if topic_meta is None:
            raise KafkaBrowseError(f"Topic '{topic}' was not found")
        error = getattr(topic_meta, "error", None)
        if error is not None:
            raise KafkaBrowseError(str(error))
        partitions = sorted((topic_meta.partitions or {}).keys())
        if partition is not None:
            if partition not in partitions:
                raise KafkaBrowseError(f"Partition {partition} is not in topic '{topic}'")
            partitions = [partition]
        if not partitions:
            return {
                "topic": topic,
                "messages": [],
                "count": 0,
                "hasOlder": False,
                "cursor": {},
                "partitions": [],
            }

        beginning = {}
        bound = {}  # exclusive upper offset for this page
        for part in partitions:
            tp = TopicPartition(topic, part)
            low, high = consumer.get_watermark_offsets(tp, timeout=STANDARD_TIMEOUT_SEC)
            beginning[part] = int(low or 0)
            high_bound = int(high or 0)
            if before and str(part) in before:
                try:
                    high_bound = min(high_bound, int(before[str(part)]))
                except (TypeError, ValueError):
                    pass
            bound[part] = high_bound

        # A partition with nothing below its bound is exhausted: it is not fetched.
        live = [part for part in partitions if bound[part] > beginning[part]]
        per_partition = max(1, limit // len(live)) if live else 0
        starts = {part: max(beginning[part], bound[part] - per_partition) for part in live}
        consumer.assign([TopicPartition(topic, part, starts[part]) for part in live])

        records: list[Any] = []
        complete: set[int] = set()  # partitions whose whole window has been read
        deadline = time.monotonic() + STANDARD_TIMEOUT_SEC
        idle = 0
        while not complete.issuperset(live) and len(records) < limit and time.monotonic() < deadline:
            message = consumer.poll(0.5)
            if message is None:
                idle += 1
                if idle >= 4:
                    break
                continue
            idle = 0
            err = message.error()
            part = message.partition()
            if err:
                if err.code() == KafkaError._PARTITION_EOF:
                    complete.add(part)
                    continue
                raise KafkaBrowseError(err.str() or str(err))
            if message.offset() >= bound.get(part, 0):
                complete.add(part)
                continue
            records.append(message)
            if message.offset() == bound[part] - 1:
                complete.add(part)  # partitions arrive in offset order, so the window is all read
        # A window cut off by the deadline or idle break is served whole on a later page.
        records = [item for item in records if item.partition() in complete]
        records.sort(key=lambda item: (_message_ts(item) or 0, item.offset()), reverse=True)
        records = records[:limit]
        messages = [
            _record_payload(item, key_format, value_format, registry, key_subject, value_subject)
            for item in records
        ]
        cursor = {}
        has_older = False
        for part in partitions:
            offsets = [item.offset() for item in records if item.partition() == part]
            if part not in complete:
                oldest = bound[part]  # exhausted, or not fully read: keep the cursor
            elif offsets:
                oldest = min(offsets)
            else:
                oldest = starts[part]  # the window was empty (e.g. compacted); move past it
            cursor[str(part)] = oldest
            if oldest > beginning[part]:
                has_older = True
        return {
            "topic": topic,
            "messages": messages,
            "count": len(messages),
            "hasOlder": has_older,
            "cursor": cursor,
            "partitions": partitions,
        }
    except KafkaBrowseError:
        raise
    except KafkaException as exc:
        raise KafkaBrowseError(str(exc)) from exc
    except Exception as exc:
        raise KafkaBrowseError(str(exc)) from exc
    finally:
        try:
            consumer.close()
        except Exception:
            pass


def _message_ts(message) -> int | None:
    stamp = message.timestamp()
    if isinstance(stamp, tuple):
        value = stamp[1] if len(stamp) > 1 else None
        return value if value and value > 0 else None
    if isinstance(stamp, (int, float)) and stamp > 0:
        return int(stamp)
    return None


def _record_payload(record, key_format, value_format, registry, key_subject, value_subject) -> dict:
    key = decode_payload(record.key(), key_format, registry=registry, subject=key_subject)
    value = decode_payload(record.value(), value_format, registry=registry, subject=value_subject)
    ts = _message_ts(record)
    iso = None
    if ts:
        iso = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
    return {
        "partition": record.partition(),
        "offset": record.offset(),
        "timestamp": iso,
        "timestampMs": ts,
        "key": key.get("value"),
        "value": value.get("value"),
        "keyFormat": key.get("format"),
        "valueFormat": value.get("format"),
        "schemaId": value.get("schemaId") or key.get("schemaId"),
        "decodeError": value.get("error") or key.get("error"),
        "tombstone": record.value() is None,
    }
