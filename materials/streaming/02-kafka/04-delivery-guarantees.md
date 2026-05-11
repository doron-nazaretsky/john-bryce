---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---
# Delivery Guarantees

Every messaging system has to answer one question: **what does it promise about whether your message arrives?** The answer is one of three classic levels -- at-most-once, at-least-once, exactly-once -- and the rest of the system follows from which one you pick.

This chapter looks at the three levels generically, then shows what each requires from Kafka producers and consumers.

> **Core Concept:** For the cross-tool theory of delivery guarantees and idempotent consumers, see the "Delivery Guarantees" section of [Pub/Sub and Messaging Patterns](../../core-concepts/07-application-patterns/02-pubsub-and-messaging.md).

---

## The Three Levels (Generic)

| Level | What can happen | Use when |
|---|---|---|
| **At-most-once** | Messages can be **lost**, never duplicated | Loss is cheaper than duplication; metrics, telemetry samples |
| **At-least-once** | Messages can be **duplicated**, never lost | Duplication is cheaper than loss; most business pipelines |
| **Exactly-once** | No loss, no duplicates | Money, inventory, anything where double-processing is dangerous |

The names are precise: **at-most-once** means "0 or 1 delivery" (so loss is the failure mode). **At-least-once** means "1 or more deliveries" (so duplicates are the failure mode). **Exactly-once** means "exactly 1" -- no failure mode.

In practice, **at-least-once with idempotent consumers** is the most common real-world configuration. True exactly-once is achievable in Kafka in specific narrow scenarios, but it's expensive and brittle outside them.

---

## Failure Points in a Kafka Round-Trip

To see where each guarantee bites, look at where things can go wrong:

```
[Producer] --1--> [Broker] --2--> [Consumer]
                                    |
                                    3
                                    v
                              [Side Effect]
                                    |
                                    4
                                    v
                                [Commit]
```

Failure modes:

- **(1) Producer to broker:** producer crashes mid-send; network drops the request; broker crashes before writing.
- **(2) Broker to consumer:** consumer crashes after receiving but before processing.
- **(3) Side effect:** consumer wrote to its database / called an API, then crashed before committing the offset.
- **(4) Commit:** consumer committed before processing finished, then crashed.

The level you pick determines which combinations of (1)-(4) cause loss vs duplication.

---

## At-Most-Once

**Producer side:** send and don't retry. If the send fails, drop the record.

**Consumer side:** commit the offset *before* processing.

```
poll → commit → process
```

If processing crashes, the offset is already committed -- the consumer restarts from the next record, and the in-flight one is lost. No duplicates, but you can lose records.

In Kafka, this is achieved via `enable_auto_commit=True` with the default 5-second interval (and accepting that records consumed but not yet processed may be lost on a crash). Or by manually committing first, then processing.

**Use cases:** raw metrics streams, samples for dashboards, debug telemetry. Anything where one missing data point doesn't matter.

---

## At-Least-Once

**Producer side:** retry on failure. If unsure whether a record made it (timeout, network blip), send it again. May result in duplicates on the broker.

**Consumer side:** process the record, *then* commit.

```
poll → process → commit
```

If processing succeeds and the commit succeeds, all good. If processing succeeds but the consumer crashes before committing, the next consumer reads the same record again -- it's processed twice. **No loss, possible duplicates.**

This is the default safe setting and the one we'll use in the project.

### The Idempotency Requirement

At-least-once forces a property on your consumer: **processing the same record twice must be safe.** Two common ways to achieve that:

1. **Natural idempotency:** the operation is the same regardless of how many times you do it. Example: `UPDATE pages SET last_seen_at = '2026-05-03T10:00:00Z' WHERE page_id = '/x'`. Running it twice gives the same result.
2. **Dedup keys:** record an identifier in your sink and check for it before re-processing. Example: insert into a table with a unique constraint on `(event_id)`. The second insert fails harmlessly.

Pipelines that ignore this property end up with double-counted revenue, double-sent emails, etc. -- bugs that don't show up in test, only in incidents.

> See the discussion in the [spark-etl project](../../projects/spark-etl/) of incrementality vs idempotency -- the same distinction matters here.

---

## Producer Idempotence: The First Half of Exactly-Once

Even at-least-once at the consumer can be ruined if the producer sends duplicates that the broker happily appends. Suppose:

1. Producer sends record X, broker writes it, sends ACK.
2. ACK is lost in transit.
3. Producer times out, retries.
4. Broker writes X **again** -- now there are two copies in the log.

Kafka's **idempotent producer** fixes this. With `enable.idempotence=true` (default since Kafka 3.0), each producer instance gets a Producer ID and assigns each record a sequence number. The broker tracks the highest sequence per `(producer_id, partition)` and rejects duplicates.

This guarantees **at-most-once write per producer-partition** at the storage level, which combined with retries gives **exactly-once write**: every record makes it, exactly one copy.

Cost: small CPU and metadata overhead, well worth it. **Turn it on.** It's now the default in Kafka.

Here's a producer wired up for the strong-durability story (`acks=all` + idempotence) plus a manual-commit consumer that processes *then* commits — the at-least-once recipe end to end.

**Step 1 — create the topic.**

```{code-cell} python
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

BOOTSTRAP = "kafka-1:9092,kafka-2:9092,kafka-3:9092"
TOPIC = "demo-delivery-guarantees"

admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP)
try:
    admin.create_topics([NewTopic(name=TOPIC, num_partitions=1, replication_factor=3)])
except TopicAlreadyExistsError:
    pass
print(f"topic {TOPIC!r} ready")
```

**Step 2 — strong-durability producer:** every write waits for full ISR ack and is idempotent on retries.

```{code-cell} python
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP,
    acks="all",
    enable_idempotence=True,
    retries=5,
)
for i in range(5):
    md = producer.send(TOPIC, key=f"order-{i}".encode(),
                       value=f"amount={i*10}".encode()).get(timeout=10)
    print(f"acked: partition={md.partition} offset={md.offset}")
producer.flush()
producer.close()
```

**Step 3 — at-least-once consumer: process *then* commit.** Manual commit after each batch, explicit `poll()` so the network calls are visible.

```{code-cell} python
from kafka import KafkaConsumer
import time

consumer = KafkaConsumer(
    TOPIC, bootstrap_servers=BOOTSTRAP,
    group_id="demo-delivery-grp",
    auto_offset_reset="earliest",
    enable_auto_commit=False,
)
deadline = time.time() + 10
got_any = False
while time.time() < deadline:
    batch = consumer.poll(timeout_ms=1000)
    if batch:
        got_any = True
        for records in batch.values():
            for r in records:
                print(f"processed key={r.key} value={r.value}")
        consumer.commit()    # only after successful processing
    elif got_any:
        break
```

**Step 4 — clean up.**

```{code-cell} python
consumer.close()
admin.delete_topics([TOPIC])
admin.close()
print(f"closed consumer and deleted topic {TOPIC!r}")
```

---

## Kafka Transactions: Exactly-Once, but Only Kafka-to-Kafka

Idempotent producer fixes the producer→broker side. The harder question is: can a consumer guarantee that each record is *processed* exactly once? The answer Kafka gives is precise and narrow: **yes, but only when the processing step's only side effect is writing back to Kafka.**

### The shape Kafka transactions cover

Kafka's exactly-once feature is built for one specific pipeline shape — the **consume-process-produce loop**:

```
read from input topic → process → write to output topic (+ commit input offsets)
```

Three things have to happen together for this to be exactly-once:

1. The output records appear in the destination topic.
2. The input offsets advance, so the same records aren't re-read.
3. If anything fails, *none* of the above takes effect.

Kafka can pull this off because **all three side effects live inside Kafka itself**. Consumer offsets aren't stored externally — they're written to an internal Kafka topic called `__consumer_offsets`. So the output writes, the offset commit, and the transaction marker are all just records in Kafka logs, and the broker can wrap them in one atomic transaction.

```python
# pseudocode — exact API depends on client
producer.init_transactions()
while True:
    records = consumer.poll()
    producer.begin_transaction()
    for r in records:
        result = process(r)
        producer.send("output_topic", result)
    producer.send_offsets_to_transaction(consumer.offsets(), consumer.group_id)
    producer.commit_transaction()
```

Downstream consumers reading the output topic with `isolation.level=read_committed` only see records from transactions that committed. If the processor crashes mid-transaction, the broker aborts it: the output records are filtered out, the offset commit never takes effect, and a new processor instance re-reads the same input and redoes the work. The redo is safe precisely because the previous attempt's output was discarded.

Spark Structured Streaming uses this machinery internally when you `writeStream` to Kafka with a checkpoint, which is why Kafka-to-Kafka Spark pipelines can claim end-to-end exactly-once.

### Why exactly-once dies the moment you leave Kafka

Now consider the much more common shape — a consumer that reads from Kafka and writes *somewhere else*: Postgres, S3, Elasticsearch, Stripe, an email provider, a Redis counter. Call this **consume-process-commit**:

```
read from Kafka → do external side effect → commit Kafka offset
```

You now have **two independent systems** that need to agree on what happened: the external sink, and Kafka's offset store. There is no distributed transaction between them — Kafka cannot roll back a Postgres insert, and Postgres cannot roll back a Kafka offset commit. Whichever order you pick, one failure mode is unavoidable:

- **Process, then commit** (at-least-once): the external write succeeds, the consumer crashes before `commit()` lands, the next poll re-delivers the record → **duplicate**.
- **Commit, then process** (at-most-once): the commit succeeds, processing crashes → **lost record**.

There is no third option Kafka can offer here, because Kafka only controls one of the two systems. This isn't a missing feature waiting to be built — it's a fundamental limit of distributed systems without a shared transaction coordinator. Kafka transactions work for Kafka-to-Kafka because Kafka *is* the shared coordinator. Once a non-Kafka system is in the picture, that's gone.

### What "effectively exactly-once" looks like in practice

Real pipelines don't give up on exactly-once semantics — they just stop expecting Kafka to provide them. They run **at-least-once delivery** and make the *processing step* idempotent, so a duplicate delivery has no observable effect. The common patterns:

1. **Dedup key in the sink.** Write `(event_id, ...)` to Postgres with `event_id` as a unique constraint. A duplicate insert fails harmlessly. The event needs a stable ID — `(topic, partition, offset)` works as a fallback when nothing better exists.
2. **Natural idempotency.** `UPDATE pages SET last_seen_at = '2026-05-03T10:00Z' WHERE id = 'x'` produces the same final state no matter how many times it runs. Upserts (`INSERT ... ON CONFLICT DO UPDATE`) fall in the same category.
3. **Transactional outbox.** Inside a single Postgres transaction, do both the business write *and* insert a row recording "I processed offset N for partition P." On startup, the consumer reads its last-processed offset from Postgres and `seek()`s there, ignoring `__consumer_offsets` entirely. Postgres is now the source of truth for "what have I processed," so the two systems can't diverge. This is the canonical fix when you genuinely need exactly-once external writes.
4. **Sink owns the offsets.** Some sinks (Iceberg/Delta with checkpointing, Spark Structured Streaming with a checkpoint directory) record input offsets atomically alongside the output. Same idea as the outbox, baked into the framework.

### What "exactly-once" does *not* mean

Even within Kafka, the term is narrower than it sounds:

- **Not across systems.** Anything outside Kafka is your problem to make idempotent.
- **Not across multiple producers.** Idempotence is keyed on Producer ID. Two producers emitting the same business event produce two records — Kafka has no way to know they're "the same."
- **Not exactly-once *consumption*.** Two consumer groups reading the same topic each see every record. Transactions give exactly-once *processing* inside one consume-process-produce loop, not exactly-once *delivery* to every reader.

### The mental model

Kafka can guarantee that **its own internal state — output topic plus offsets — moves atomically**. The moment your side effect leaves Kafka, that guarantee evaporates, and the responsibility moves to you: either make the side effect idempotent, or make the external system the place where offsets are committed.

That is why the practical recommendation, for everything except pure Kafka-to-Kafka stream processing, is always the same: **at-least-once delivery + idempotent consumers**. Reach for Kafka transactions only when the whole pipeline lives inside Kafka.

---

## How Each Guarantee Is Achieved (Kafka Settings)

| Guarantee | Producer | Consumer |
|---|---|---|
| At-most-once | `acks=1`, no retries | `enable.auto.commit=true` (or commit before processing) |
| At-least-once | `acks=all`, retries enabled, idempotence on | Manual commit *after* processing |
| Exactly-once (Kafka-only pipeline) | Transactional producer (`transactional.id` set), idempotence on | `isolation.level=read_committed`; offsets committed inside the transaction |

For the project we use **at-least-once with idempotent producer**, which is the default safe configuration in modern Kafka.

---

## A Decision Checklist

For each pipeline, ask:

1. **What's the cost of losing a record?** If non-zero, you need at-least-once or stronger.
2. **What's the cost of processing twice?** If non-zero, you need either exactly-once or idempotent processing.
3. **Does the pipeline cross system boundaries?** If yes, exactly-once is hard -- design for at-least-once + idempotency.
4. **Is the work going into a sink that supports upserts or unique constraints?** If yes, you have natural idempotency essentially for free.

---

> **Hands-on now — Stage 2 Part A.** Switch to `streaming-clickstream/stages/02-spark-ingest/lesson.md` and complete **Part A (Spark `readStream` from Kafka, console sink)**. Come back here once Part A's acceptance test is green.

---

[← Previous: Consumer Groups and Rebalancing](03-consumer-groups-and-rebalancing.md) | [Next: Replication and ISR →](05-replication-and-isr.md)
