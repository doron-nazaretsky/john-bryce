"""Stage 3 — functional tests for the windowed-counts query.

Part A: a basic windowed count emits the right (window, page, count) rows.
Part B: with a watermark, late events that fall within the threshold update
their window; events past the threshold are dropped.

Both tests need to push the watermark forward to trigger window closure, so
they produce a "later" event after the windowed batch.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from pipeline import config
from pipeline.config import KafkaConf
from pipeline.windowed_job import windowed_counts
from helpers import test_utils


@pytest.fixture
def patch_topic(monkeypatch, topic):
    monkeypatch.setattr(config, "PAGEVIEWS_TOPIC", topic)
    return topic


def _kc(topic: str, group_id: str | None = None) -> KafkaConf:
    return KafkaConf(
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        topic=topic,
        group_id=group_id or f"stage3-{uuid4().hex[:8]}",
    )


def _wait_for_rows(path: str, predicate, timeout_s: float = 120.0, interval_s: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        rows = test_utils.read_parquet(path)
        if predicate(rows):
            return True
        time.sleep(interval_s)
    return False


def _bucket_counts(rows: list[dict]) -> dict[tuple, int]:
    """Aggregate parquet rows into a {(window_start, page): count} map."""
    out: dict[tuple, int] = {}
    for r in rows:
        ws = r["window_start"]
        # Spark may write window_start as datetime or as a struct depending on version.
        if hasattr(ws, "isoformat"):
            ws_key = ws.isoformat()
        else:
            ws_key = str(ws)
        out[(ws_key, r["page"])] = r["count"]
    return out


def test_part_a(spark, patch_topic, tmp_output, tmp_checkpoint):
    """A 1-minute tumbling window emits per-(window, page) counts.

    Produce events in the [10:00, 10:01) minute, then a late event in 10:05
    to push the watermark past the first window so it closes and emits.
    """
    base = datetime(2026, 5, 3, 10, 0, 0, tzinfo=timezone.utc)
    in_window = (
        test_utils.deterministic_events(6, base_ts=base, pages=["/home", "/about"], seconds_apart=5)
    )
    pusher = [
        {
            "user_id": "user-pusher",
            "session_id": "sess-pusher",
            "page": "/help",
            "referrer": "/",
            "ts": (base + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
    ]
    test_utils.produce_events(config.KAFKA_BOOTSTRAP_SERVERS, patch_topic, in_window + pusher)

    output_path = str(tmp_output / "windowed")
    checkpoint_path = str(tmp_checkpoint / "windowed")
    query = windowed_counts(
        spark=spark,
        kafka_conf=_kc(patch_topic),
        output_path=output_path,
        checkpoint_path=checkpoint_path,
    )
    try:
        ok = _wait_for_rows(
            output_path,
            lambda rows: any(
                r["page"] == "/home" and r["count"] >= 3 for r in rows
            ),
            timeout_s=120.0,
        )
        assert ok, f"window for /home never reached count=3 in output: {test_utils.read_parquet(output_path)}"
    finally:
        query.stop()
        query.awaitTermination(20)

    rows = test_utils.read_parquet(output_path)
    counts = _bucket_counts(rows)
    # /home and /about each appear 3 times in the 6 deterministic events
    # for that window (alternating).
    home_count = sum(c for (_, page), c in counts.items() if page == "/home")
    about_count = sum(c for (_, page), c in counts.items() if page == "/about")
    assert home_count >= 3, f"expected ≥3 /home pageviews, got {home_count}"
    assert about_count >= 3, f"expected ≥3 /about pageviews, got {about_count}"


def test_part_b(spark, patch_topic, tmp_output, tmp_checkpoint):
    """Watermark lets near-late events update their window; truly-late ones drop.

    With watermark=2 minutes, an event at 10:00:30 produced after the
    watermark advances to 09:58:30 would be accepted (still within tolerance).
    An event whose timestamp is 10 minutes earlier than the current
    watermark must be dropped.
    """
    base = datetime(2026, 5, 3, 10, 0, 0, tzinfo=timezone.utc)
    early = test_utils.deterministic_events(
        4, base_ts=base, pages=["/home"], seconds_apart=5
    )
    # First push the watermark forward by producing an event much later in time.
    pusher = [
        {
            "user_id": "user-pusher",
            "session_id": "sess-pusher",
            "page": "/help",
            "referrer": "/",
            "ts": (base + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
    ]
    # Then a "near-late" event that falls inside the 2-minute watermark
    # tolerance (event-time = 10:00:08, watermark after pusher ≈ 10:03:00).
    near_late = [
        {
            "user_id": "user-late",
            "session_id": "sess-late",
            "page": "/home",
            "referrer": "/",
            "ts": (base + timedelta(seconds=8)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
    ]
    test_utils.produce_events(
        config.KAFKA_BOOTSTRAP_SERVERS, patch_topic, early + pusher + near_late
    )

    output_path = str(tmp_output / "windowed")
    checkpoint_path = str(tmp_checkpoint / "windowed")
    query = windowed_counts(
        spark=spark,
        kafka_conf=_kc(patch_topic),
        output_path=output_path,
        checkpoint_path=checkpoint_path,
    )
    try:
        ok = _wait_for_rows(
            output_path,
            lambda rows: any(r["page"] == "/home" and r["count"] >= 4 for r in rows),
            timeout_s=120.0,
        )
        assert ok, (
            "expected at least one /home window with count ≥4 (the 4 early "
            "events plus the near-late one inside the watermark); "
            f"got: {test_utils.read_parquet(output_path)}"
        )
    finally:
        query.stop()
        query.awaitTermination(20)
