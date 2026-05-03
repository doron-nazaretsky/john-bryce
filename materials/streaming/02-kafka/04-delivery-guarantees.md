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

---

## Kafka Transactions: The Second Half

Idempotent producer fixes the producer side. But what about the consume-process-produce pattern, where a stream processor reads from one topic, computes, writes to another, and updates the offsets? Three operations, all of which need to atomically succeed or fail together for exactly-once across them.

Kafka **transactions** wrap exactly that pattern. The producer opens a transaction, writes outputs, commits the input offsets *as part of the transaction*, and commits. Consumers reading the output topic with `isolation.level=read_committed` only see records from committed transactions.

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

Spark Structured Streaming uses this internally when you write to Kafka with `outputMode("append")` and a checkpoint, giving you end-to-end exactly-once **as long as your sink is also transactional or idempotent**.

This is a high-level mention -- you won't write transaction code by hand in the project. What matters is: **exactly-once is real in Kafka, but only for Kafka-to-Kafka pipelines and only inside the boundaries of a single producer**.

---

## What "Exactly-Once" Doesn't Mean

It does **not** mean:

- **Exactly-once across systems.** If your consumer reads from Kafka and writes to Postgres, "exactly-once" requires the Postgres write and the Kafka offset commit to be atomic. They aren't, by default. You need either a transactional outbox pattern, a sink that reads offsets back, or idempotent writes (with dedup keys in Postgres).
- **Exactly-once across multiple producers.** Idempotence is per-producer. Two producers sending the same business event will produce two records.
- **Exactly-once observation.** Two independent consumers reading the same topic each see every record. Kafka transactions give exactly-once *processing* in the consume-process-produce loop, not exactly-once *consumption*.

The correct mental model: aim for **at-least-once delivery + idempotent consumers**. Use exactly-once Kafka transactions only when the whole pipeline lives inside Kafka.

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

[← Previous: Consumer Groups and Rebalancing](03-consumer-groups-and-rebalancing.md) | [Next: Replication and ISR →](05-replication-and-isr.md)
