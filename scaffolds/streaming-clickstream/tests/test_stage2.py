"""Stage 2 — functional tests for the Kafka → parquet ingest job.

Both parts use the SAME ``build_stream`` function. Part A asserts the
pipeline parses Kafka records correctly using a memory sink (we override the
sink with foreachBatch). Part B asserts the parquet sink + checkpoint write
all events to disk and that a restart resumes from the checkpoint without
duplication.
"""
from __future__ import annotations

import time
from pathlib import Path
from uuid import uuid4

import pytest

from pipeline import config
from pipeline.config import KafkaConf, SinkConf
from pipeline.ingest_job import build_stream
from helpers import test_utils


@pytest.fixture
def patch_topic(monkeypatch, topic):
    monkeypatch.setattr(config, "PAGEVIEWS_TOPIC", topic)
    return topic


def _kc(topic: str, group_id: str | None = None) -> KafkaConf:
    return KafkaConf(
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        topic=topic,
        group_id=group_id or f"stage2-{uuid4().hex[:8]}",
    )


def _wait_until(predicate, timeout_s: float = 60.0, interval_s: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_s)
    return False


def test_part_a(spark, patch_topic, tmp_output, tmp_checkpoint):
    """The query reads from Kafka, parses correctly, and writes parquet rows."""
    events = test_utils.deterministic_events(20)
    test_utils.produce_events(config.KAFKA_BOOTSTRAP_SERVERS, patch_topic, events)

    sink_conf = SinkConf(
        output_path=str(tmp_output / "ingested"),
        checkpoint_path=str(tmp_checkpoint / "ingest"),
    )

    query = build_stream(spark=spark, kafka_conf=_kc(patch_topic), sink_conf=sink_conf)
    try:
        ok = _wait_until(
            lambda: len(test_utils.read_parquet(sink_conf.output_path)) >= len(events),
            timeout_s=90.0,
        )
        assert ok, (
            f"expected ≥{len(events)} parquet rows within timeout; "
            f"got {len(test_utils.read_parquet(sink_conf.output_path))}"
        )
    finally:
        query.stop()
        query.awaitTermination(20)

    rows = test_utils.read_parquet(sink_conf.output_path)
    pages_seen = {r["page"] for r in rows}
    expected_pages = {e["page"] for e in events}
    assert expected_pages.issubset(pages_seen), f"missing pages: {expected_pages - pages_seen}"
    # Schema check — the parse must produce these columns.
    assert {"user_id", "session_id", "page", "referrer", "ts"}.issubset(rows[0].keys())


def test_part_b(spark, patch_topic, tmp_output, tmp_checkpoint):
    """A restart of the query resumes from the checkpoint with no duplication.

    We produce 10 events, run the query until they appear in parquet, stop
    it, produce 10 more, restart it, and assert exactly 20 distinct rows.
    """
    first = test_utils.deterministic_events(10)
    test_utils.produce_events(config.KAFKA_BOOTSTRAP_SERVERS, patch_topic, first)

    sink_conf = SinkConf(
        output_path=str(tmp_output / "ingested"),
        checkpoint_path=str(tmp_checkpoint / "ingest"),
    )

    # First run.
    query = build_stream(spark=spark, kafka_conf=_kc(patch_topic), sink_conf=sink_conf)
    try:
        assert _wait_until(
            lambda: len(test_utils.read_parquet(sink_conf.output_path)) >= len(first),
            timeout_s=90.0,
        ), "first run never wrote the seeded events"
    finally:
        query.stop()
        query.awaitTermination(20)

    rows_after_first = test_utils.read_parquet(sink_conf.output_path)
    assert len(rows_after_first) == len(first), (
        f"first run wrote {len(rows_after_first)} rows, expected {len(first)}"
    )

    # Add more events, restart.
    base_ts = first[-1]["ts"]
    second = test_utils.deterministic_events(
        10,
        base_ts=__import__("datetime").datetime.fromisoformat(base_ts.replace("Z", "+00:00"))
        + __import__("datetime").timedelta(seconds=20),
    )
    test_utils.produce_events(config.KAFKA_BOOTSTRAP_SERVERS, patch_topic, second)

    query = build_stream(spark=spark, kafka_conf=_kc(patch_topic), sink_conf=sink_conf)
    try:
        assert _wait_until(
            lambda: len(test_utils.read_parquet(sink_conf.output_path)) >= len(first) + len(second),
            timeout_s=90.0,
        ), "second run did not pick up new events from the committed offset"
    finally:
        query.stop()
        query.awaitTermination(20)

    rows_total = test_utils.read_parquet(sink_conf.output_path)
    # The checkpoint must prevent re-processing of the first 10 events.
    assert len(rows_total) == len(first) + len(second), (
        f"got {len(rows_total)} rows, expected {len(first) + len(second)} — "
        "the first 10 events were probably re-processed (checkpoint not honored)"
    )
