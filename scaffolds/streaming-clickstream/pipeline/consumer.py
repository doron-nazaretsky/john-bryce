"""Stage 1B — Consumer.

Implement ``run_consumer`` so it reads up to ``max_records`` messages from the
pageviews topic using a consumer in the given group, deserializes them as JSON
dicts, and returns them as a list. Commit offsets after processing each
record (at-least-once delivery).
"""
from __future__ import annotations


def run_consumer(group_id: str, max_records: int) -> list[dict]:
    """Consume up to ``max_records`` events as a member of ``group_id``.

    Args:
        group_id: Consumer-group identifier. Two callers with the same
            ``group_id`` share the workload (point-to-point); two callers
            with different ``group_id``s each see all records (fan-out).
        max_records: Stop after consuming this many records. Useful so the
            test can deterministically assert on counts.

    Behavior:
        * Bootstrap from ``pipeline.config.KAFKA_BOOTSTRAP_SERVERS``.
        * Topic is ``pipeline.config.PAGEVIEWS_TOPIC``.
        * ``auto_offset_reset="earliest"`` so you read the test's seeded events.
        * ``enable_auto_commit=False`` — commit manually after processing
          each record (at-least-once).
        * Deserialize each record's value (bytes) as JSON.
        * Return the list of decoded events in the order they were consumed.

    Raise NotImplementedError until you've implemented the function.
    """
    raise NotImplementedError("Stage 1B: implement pipeline.consumer.run_consumer")
