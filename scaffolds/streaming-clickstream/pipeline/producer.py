"""Stage 1A — Producer.

Implement ``send_event`` so it serializes a pageview event and publishes it
to the Kafka pageviews topic, keyed by ``user_id`` so per-user events stay
ordered on the same partition.

A single module-level producer instance is fine (and is what production code
usually does). You can lazy-create it on first call.
"""
from __future__ import annotations


def send_event(event: dict) -> None:
    """Send one pageview event to Kafka.

    Args:
        event: A dict with keys ``user_id``, ``session_id``, ``page``,
            ``referrer``, ``ts``. Treat ``user_id`` as the partition key so
            per-user ordering is preserved.

    Behavior:
        * Serialize the event as JSON.
        * Use the bootstrap servers from
          ``pipeline.config.KAFKA_BOOTSTRAP_SERVERS``.
        * Either flush after each send (simple) or rely on a long-lived
          producer + manual flush from callers (faster). Either is fine.

    Durability tuning (``acks="all"``) is deliberately out of scope for
    this stage — Session 2 returns to it alongside replication.

    Raise NotImplementedError until you've implemented the function — the
    test ``test_part_a`` will fail with that marker, which is what the
    scaffold harness expects.
    """
    raise NotImplementedError("Stage 1A: implement pipeline.producer.send_event")
