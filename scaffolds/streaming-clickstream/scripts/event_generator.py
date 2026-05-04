"""Synthetic pageview event generator. Provided — do not edit.

Two modes:

  * ``start`` — daemon process, emits ~50 events/sec to the pageviews topic
    with realistic distributions: Zipf-weighted page popularity, ~10% of
    events with backdated timestamps (30s–2m late) to simulate the lateness
    you'd see from real mobile clients.

  * ``stop`` / ``status`` / ``reset`` — control the daemon and inspect state.

The deterministic seeding helpers used by tests live in
``helpers.test_utils.deterministic_events`` rather than here.

CLI:

  python scripts/event_generator.py {start|stop|status|reset}
"""
from __future__ import annotations

import json
import os
import random
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

# Match defaults in pipeline/config.py — but this script is stand-alone for
# the bootstrap case where the package isn't yet importable.
BOOTSTRAP_SERVERS = os.environ.get(
    "KAFKA_BOOTSTRAP_SERVERS",
    "project-kafka-1:9092,project-kafka-2:9092,project-kafka-3:9092",
)
TOPIC = os.environ.get("PAGEVIEWS_TOPIC", "pageviews")
PIDFILE = Path("/tmp/streaming-clickstream-producer.pid")
EVENTS_PER_SEC = 50

PAGES = [
    "/", "/home", "/products", "/products/blue-widget",
    "/products/red-widget", "/products/green-widget", "/about", "/cart",
    "/checkout", "/account", "/account/orders", "/help",
]
REFERRERS = [None, "/", "/home", "/products"]


def _ensure_topic() -> None:
    admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP_SERVERS)
    try:
        admin.create_topics([NewTopic(TOPIC, num_partitions=6, replication_factor=3)])
        print(f"[generator] created topic {TOPIC}")
    except TopicAlreadyExistsError:
        pass
    finally:
        admin.close()


def _make_event(rng: random.Random) -> dict:
    # Zipf-ish bias toward early pages.
    idx = min(int(rng.paretovariate(1.16)) - 1, len(PAGES) - 1)
    page = PAGES[idx]
    user_id = f"user-{rng.randint(0, 9999):05d}"
    session_id = f"sess-{rng.randint(0, 0xFFFF):04x}"
    now = datetime.now(timezone.utc)
    # 10% of events are backdated by 30s to 2 minutes (late arrivals).
    if rng.random() < 0.10:
        ts = now - timedelta(seconds=rng.randint(30, 120))
    else:
        ts = now
    return {
        "user_id": user_id,
        "session_id": session_id,
        "page": page,
        "referrer": rng.choice(REFERRERS),
        "ts": ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }


def cmd_start() -> int:
    if PIDFILE.exists():
        print(f"[generator] already running (pid {PIDFILE.read_text().strip()})", file=sys.stderr)
        return 1
    _ensure_topic()
    pid = os.fork()
    if pid > 0:
        PIDFILE.write_text(str(pid))
        print(f"[generator] started pid={pid}, topic={TOPIC}, rate={EVENTS_PER_SEC}/s")
        return 0
    # Child: become the producer.
    rng = random.Random()
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
        linger_ms=10,
    )
    interval = 1.0 / EVENTS_PER_SEC
    try:
        while True:
            event = _make_event(rng)
            producer.send(TOPIC, key=event["user_id"], value=event)
            time.sleep(interval)
    finally:
        producer.flush()
        producer.close()
    return 0  # unreachable


def cmd_stop() -> int:
    if not PIDFILE.exists():
        print("[generator] not running", file=sys.stderr)
        return 1
    pid = int(PIDFILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
    except ProcessLookupError:
        pass
    PIDFILE.unlink(missing_ok=True)
    print(f"[generator] stopped pid={pid}")
    return 0


def cmd_status() -> int:
    if PIDFILE.exists():
        pid = PIDFILE.read_text().strip()
        try:
            os.kill(int(pid), 0)
            print(f"[generator] running, pid={pid}")
        except ProcessLookupError:
            print(f"[generator] stale pidfile (pid={pid} dead)")
            return 1
    else:
        print("[generator] not running")
    return 0


def cmd_reset() -> int:
    cmd_stop()
    admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP_SERVERS)
    try:
        admin.delete_topics([TOPIC])
        print(f"[generator] deleted topic {TOPIC}")
        time.sleep(2)
    except Exception as e:  # noqa: BLE001
        print(f"[generator] delete failed (ok if topic missing): {e}")
    finally:
        admin.close()
    _ensure_topic()
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"start", "stop", "status", "reset"}:
        print(f"usage: {Path(sys.argv[0]).name} {{start|stop|status|reset}}", file=sys.stderr)
        return 64
    return {"start": cmd_start, "stop": cmd_stop, "status": cmd_status, "reset": cmd_reset}[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
