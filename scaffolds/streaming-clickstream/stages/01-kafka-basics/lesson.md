---
kernelspec:
  name: python3
  language: python
  display_name: Python 3
---

# Stage 1 — Kafka Basics

## The Situation

The website emits pageview events. We need to (a) get them into Kafka and
(b) read them back out. That's the smallest end-to-end Kafka loop, and it's
where every messaging architecture begins. By the end of this stage you'll
have written both a producer and a consumer using `kafka-python` and seen
the round trip work against the 3-broker lab cluster.

The two pieces are independent — producer doesn't know about consumer,
consumer doesn't know about producer — and that's the whole point of the
broker-in-the-middle pattern.

## Design Considerations

Before you start implementing, think through:

- The producer needs a *partition key*. With a 6-partition topic and a key
  hashed to one of those partitions, what does that give you about
  per-key ordering? About load distribution?
- The consumer commits its progress. If you commit *before* processing,
  what's the failure mode? After processing? What's the difference?
- The consumer is a member of a group. What does the group give you here?
  And why does the test assert that re-consuming with the same group
  returns nothing?

## Part A — Producer (~30 min, first exercise block)

Open `pipeline/producer.py` and implement:

```python
def send_event(event: dict) -> None:
    ...
```

Requirements:

- Serialize the event as JSON.
- Send to the topic named in `config.PAGEVIEWS_TOPIC`.
- Use `event["user_id"]` as the partition key (so events for one user stay
  ordered).
- Use `acks="all"` for durability.

You can keep a single module-level `KafkaProducer` and reuse it across
calls — that's how production code does it. Lazy-init it on first call.

**Acceptance:**

```bash
docker exec project-streaming-jupyter pytest /home/jovyan/work/tests/test_stage1.py::test_part_a -v
```

Expected output: one passing test that produces 5 events and verifies them
via an independent consumer. The test specifically checks that records are
keyed by `user_id`.

## Part B — Consumer (~30 min, second exercise block)

Open `pipeline/consumer.py` and implement:

```python
def run_consumer(group_id: str, max_records: int) -> list[dict]:
    ...
```

Requirements:

- Use `group_id` as the consumer group (the test passes a unique one each
  time).
- `auto_offset_reset="earliest"` so a brand-new group reads the seeded test
  events from offset 0.
- `enable_auto_commit=False`. After processing each record, **call
  `consumer.commit()` manually**.
- Stop after `max_records` records.
- Return the deserialized JSON values in a list.

**Acceptance:**

```bash
docker exec project-streaming-jupyter pytest /home/jovyan/work/tests/test_stage1.py::test_part_b -v
```

The test checks two things:
1. You consumed exactly the events the producer sent.
2. **Re-consuming with the same `group_id` returns zero events.** This is
   the offset-commit assertion — your manual commit must be working.

If your consumer is correct but `test_part_b` fails on the second
re-consume, you committed *after the timeout* but never actually persisted
the commit. Make sure you call `consumer.commit()` before returning.

## Definition of Done

- `pytest tests/test_stage1.py -v` is fully green (both `test_part_a` and
  `test_part_b`).
- You can describe, in one sentence each:
  - Why the producer keys by `user_id`.
  - What the consumer's `group_id` does.
  - Why `enable_auto_commit=False` matters for at-least-once delivery.

## Before You Move On

- Run `make events-start` and let the producer run for 10 seconds. Then
  open a second terminal and run a quick consumer (`docker exec
  project-streaming-jupyter python -c "..."`) — does your consumer keep up with
  the producer?
- What would happen if you started two consumers with the same `group_id`
  against the live producer? With different `group_id`s? Predict, then try
  it.
- Stop one of the brokers (`docker stop project-kafka-2`). Does the producer keep
  working? Does the consumer? Why? (You'll come back to this in Stage 2's
  Theory B block.)

---

[Next: Stage 2 — Spark Ingest →](../02-spark-ingest/lesson.md)
