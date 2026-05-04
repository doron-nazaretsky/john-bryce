"""Test helpers. Provided — do not edit.

Functions here support deterministic, fast pytest runs:
  * ``reset_topic`` — delete + recreate a Kafka topic so each test starts clean.
  * ``deterministic_events`` — build a fixed list of pageview dicts for tests.
  * ``produce_events`` — synchronous send of a list of events to Kafka.
  * ``read_parquet`` — read a parquet output directory into a list of dicts.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow.parquet as pq
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import UnknownTopicOrPartitionError


def reset_topic(
    bootstrap_servers: str,
    topic: str,
    *,
    partitions: int = 6,
    replication_factor: int = 3,
) -> None:
    """Delete (if present) and recreate ``topic`` with the given shape."""
    admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers)
    try:
        try:
            admin.delete_topics([topic])
        except UnknownTopicOrPartitionError:
            pass
        # Wait for delete to propagate; re-create.
        for _ in range(30):
            try:
                admin.create_topics(
                    [NewTopic(topic, num_partitions=partitions, replication_factor=replication_factor)]
                )
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError(f"failed to recreate topic {topic}")
    finally:
        admin.close()


def deterministic_events(
    n: int,
    *,
    base_ts: datetime | None = None,
    pages: list[str] | None = None,
    seconds_apart: float = 1.0,
) -> list[dict]:
    """Return ``n`` events with deterministic content, one per ``seconds_apart``."""
    base_ts = base_ts or datetime(2026, 5, 3, 10, 0, 0, tzinfo=timezone.utc)
    pages = pages or ["/home", "/about", "/products", "/cart"]
    events = []
    for i in range(n):
        events.append(
            {
                "user_id": f"user-{i % 100:05d}",
                "session_id": f"sess-{i % 50:04x}",
                "page": pages[i % len(pages)],
                "referrer": "/home",
                "ts": (base_ts + timedelta(seconds=i * seconds_apart)).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
            }
        )
    return events


def produce_events(
    bootstrap_servers: str,
    topic: str,
    events: list[dict],
    *,
    flush: bool = True,
) -> None:
    """Send ``events`` to ``topic`` synchronously (waits until all are acked)."""
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
        retries=5,
        retry_backoff_ms=500,
    )
    try:
        for event in events:
            producer.send(topic, key=event["user_id"], value=event)
        if flush:
            producer.flush()
    finally:
        producer.close()


def read_parquet(path: str | Path) -> list[dict]:
    """Read every parquet file under ``path`` and return rows as dicts.

    Skips files that are still mid-write (0 bytes). Spark's streaming sink
    occasionally surfaces such transient files between commits, and pyarrow
    fails the whole read if any input is empty.
    """
    p = Path(path)
    if not p.exists():
        return []
    files = [f for f in p.rglob("*.parquet") if f.stat().st_size > 0]
    if not files:
        return []
    table = pq.read_table([str(f) for f in files])
    return table.to_pylist()
