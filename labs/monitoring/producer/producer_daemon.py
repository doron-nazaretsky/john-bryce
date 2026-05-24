"""Synthetic e-commerce click event producer (daemon).

Long-running process that streams JSON click events to Kafka topic ``clicks``.
Its behavior is driven by a small JSON control file (default
``/tmp/producer-control.json``) so the producer CLI can change rate or inject
bad records without restarting the daemon.

Control-file schema::

    {
      "rate_mult": 1.0,     # multiplier on the baseline rate (10 events/sec)
      "inject_bad": 0       # one-shot: when > 0, send N malformed records on
                            # the next tick and decrement back to 0
    }

The daemon writes a status snapshot to ``<control>.status`` after every tick so
``producer status`` can show what's currently happening.
"""

from __future__ import annotations

import json
import os
import random
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from kafka import KafkaProducer

CONTROL_PATH = Path(os.environ.get("PRODUCER_CONTROL_FILE", "/tmp/producer-control.json"))
STATUS_PATH = CONTROL_PATH.with_suffix(".status")
BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka-1:9092,kafka-2:9092")
TOPIC = os.environ.get("CLICKS_TOPIC", "clicks")
BASELINE_RATE = float(os.environ.get("PRODUCER_BASELINE_RATE", "100"))  # events/sec

PRODUCT_IDS = [f"P{n:03d}" for n in range(1, 21)]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_control() -> dict:
    if not CONTROL_PATH.exists():
        return {"rate_mult": 1.0, "inject_bad": 0}
    try:
        return json.loads(CONTROL_PATH.read_text())
    except json.JSONDecodeError:
        return {"rate_mult": 1.0, "inject_bad": 0}


def _write_control(state: dict) -> None:
    CONTROL_PATH.write_text(json.dumps(state))


def _write_status(state: dict, total_sent: int, total_bad: int) -> None:
    STATUS_PATH.write_text(
        json.dumps(
            {
                "rate_mult": state.get("rate_mult", 1.0),
                "pending_bad": state.get("inject_bad", 0),
                "total_sent": total_sent,
                "total_bad": total_bad,
                "updated_at": _now_iso(),
            }
        )
    )


def _good_event() -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "product_id": random.choice(PRODUCT_IDS),
        "user_id": f"U{random.randint(1, 5000):05d}",
        "ts": _now_iso(),
    }


def _bad_event() -> dict:
    # Missing product_id — the ETL should drop these with a WARN line that
    # students see in Loki (Scenario B).
    return {
        "event_id": str(uuid.uuid4()),
        "user_id": f"U{random.randint(1, 5000):05d}",
        "ts": _now_iso(),
    }


def main() -> int:
    if not CONTROL_PATH.exists():
        _write_control({"rate_mult": 1.0, "inject_bad": 0})

    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
        linger_ms=50,
    )

    total_sent = 0
    total_bad = 0
    running = True

    def _stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    print(f"[producer] starting; bootstrap={BOOTSTRAP} topic={TOPIC} baseline={BASELINE_RATE}/s", flush=True)

    while running:
        tick_start = time.monotonic()
        state = _read_control()
        rate_mult = float(state.get("rate_mult", 1.0))
        pending_bad = int(state.get("inject_bad", 0))

        events_this_tick = max(0, int(BASELINE_RATE * rate_mult))
        bad_this_tick = min(pending_bad, events_this_tick) if events_this_tick else pending_bad

        for _ in range(events_this_tick - bad_this_tick):
            producer.send(TOPIC, _good_event())
            total_sent += 1
        for _ in range(bad_this_tick):
            producer.send(TOPIC, _bad_event())
            total_bad += 1
            total_sent += 1

        if bad_this_tick:
            state["inject_bad"] = pending_bad - bad_this_tick
            _write_control(state)

        producer.flush(timeout=2.0)
        _write_status(state, total_sent, total_bad)

        elapsed = time.monotonic() - tick_start
        time.sleep(max(0.0, 1.0 - elapsed))

    producer.flush()
    producer.close()
    print("[producer] stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
