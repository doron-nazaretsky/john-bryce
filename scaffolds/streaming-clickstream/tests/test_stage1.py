"""Stage 1 — functional tests for the producer (Part A) and consumer (Part B).

No latency assertions. Both tests drive student code with deterministic
events seeded by helpers.test_utils.
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from kafka import KafkaConsumer

from pipeline import config
from pipeline.consumer import run_consumer
from pipeline.producer import send_event
from helpers import test_utils


@pytest.fixture
def patch_topic(monkeypatch, topic):
    """Point the producer/consumer modules at the per-test topic."""
    monkeypatch.setattr(config, "PAGEVIEWS_TOPIC", topic)
    return topic


def test_part_a(patch_topic):
    """Producer publishes events that are readable from a fresh consumer."""
    events = test_utils.deterministic_events(5)
    for e in events:
        send_event(e)

    # Independent verifier consumer in a unique group.
    verifier = KafkaConsumer(
        patch_topic,
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        group_id=f"verifier-{uuid4().hex[:8]}",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=10000,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
    )
    received = []
    for record in verifier:
        received.append((record.key, record.value))
        if len(received) >= len(events):
            break
    verifier.close()

    assert len(received) == len(events), f"expected {len(events)} records, got {len(received)}"
    # Producer must key by user_id so per-user ordering is preserved.
    for (key, value), expected in zip(received, events):
        assert key == expected["user_id"], "events should be keyed by user_id"
        assert value["page"] == expected["page"]
        assert value["ts"] == expected["ts"]


def test_part_b(patch_topic):
    """Consumer returns the events that were produced, in order."""
    events = test_utils.deterministic_events(8)
    test_utils.produce_events(config.KAFKA_BOOTSTRAP_SERVERS, patch_topic, events)

    group_id = f"stage1b-{uuid4().hex[:8]}"
    consumed = run_consumer(group_id=group_id, max_records=len(events))

    assert isinstance(consumed, list), "run_consumer must return a list"
    assert len(consumed) == len(events), f"expected {len(events)}, got {len(consumed)}"
    # Order is per-partition, but with the same key (user_id) on each event
    # and a single producer, the global order on each partition matches
    # production order. We assert the multiset of (page, ts) pairs.
    expected_pairs = {(e["page"], e["ts"]) for e in events}
    actual_pairs = {(e["page"], e["ts"]) for e in consumed}
    assert actual_pairs == expected_pairs

    # Re-consuming with the SAME group_id must return zero records — the
    # previous run's commit advanced the offset past the last message.
    again = run_consumer(group_id=group_id, max_records=len(events))
    assert again == [], "manual commit should advance the group's offset"
