# From Messaging to Streaming

Messaging answers the question *how should two services communicate when the caller doesn't need the result right now?* Streaming answers a different but related question: *given a continuous flow of events, how do we keep a result up to date without re-running batch jobs every time?*

The two topics share infrastructure -- both lean on a broker -- but the demands streaming places on that broker are stricter than the demands of plain messaging. This module is about those demands and the tools (Apache Kafka, Spark Structured Streaming) that meet them.

> **Prerequisite:** This page assumes you have read [Pub/Sub and Messaging](../../core-concepts/07-application-patterns/02-pubsub-and-messaging.md) -- the coupling problem, broker topologies, delivery guarantees, persistence. We will not re-derive any of that here. The rest of this lesson is about what changes once the messages stop being one-off notifications and become a continuous, high-volume stream that you compute over.

---

## What Streaming Adds to Messaging

A "send an order-confirmation email" message and "every page-view on the site" are both messages. But the second one has properties the first doesn't:

- **Volume.** Order events arrive at the rate users place orders -- maybe a few per second. Page-view events arrive at the rate users browse -- thousands per second on a busy site. The infrastructure needs to scale horizontally without falling over.
- **Continuity.** Order events arrive in bursts and are independently meaningful. Page-view events form a continuous stream that you summarise -- "page-views per minute per URL" only makes sense as an aggregate over time.
- **Replayability.** When a new analytics team joins, they want to compute *historical* metrics from the same stream the live dashboard reads. The broker has to let a brand-new consumer start from the beginning, not just from "now."
- **Ordering inside a key.** "User 42's events" need to be processed in the order they happened -- otherwise you get nonsense like "checkout before add-to-cart." But there is no need to globally order events across all users.
- **Long retention.** Order-confirmation emails can be deleted after delivery. The page-view stream is kept for days or weeks, as the source of truth that downstream views are derived from.

These five demands are what separate "a message broker" from "a streaming platform." A traditional broker like RabbitMQ can do messaging, but isn't built around durable replay or partitioned ordering at high volume. Kafka and similar systems were designed from day one to do exactly that.

---

## The Three Properties That Make Streaming Possible

Three architectural choices, taken together, are what turn a broker into a platform you can build a streaming pipeline on top of.

### 1. Durable, Replayable Log

The broker stores messages on disk in append-only logs and keeps them for a configurable retention period -- not just until they're acknowledged. A consumer maintains a cursor (an *offset*) into the log and can rewind to any earlier point. New consumers can start from offset zero and process all of history.

This is what makes "spin up a new analytics job and have it backfill from last Monday" trivial. The job subscribes with `auto_offset_reset=earliest`, reads its way forward, and catches up to the live tail. No special bulk-export pipeline; the broker *is* the export.

> **Core Concept:** This is the same idea as a [Write-Ahead Log](../../core-concepts/05-replication-and-availability/03-write-ahead-logs.md) used by databases for durability and replication, applied at the broker level. Kafka in particular *is* a distributed WAL -- the log is the data, not just a recovery aid.

### 2. Partitioning for Horizontal Scale

A single log on a single machine has a throughput ceiling. Streaming platforms split each topic into **partitions** -- separate logs that can live on different machines. Producers shard messages across partitions (usually by hashing a key), and consumers read partitions in parallel.

The trade-off is that *global ordering* across the whole topic is given up. What's preserved is **per-partition ordering**: messages with the same key always land on the same partition and are read in order. For most streaming workloads, per-key ordering is what you actually want -- "this user's events in order" matters, "this user's event before some other user's event" usually doesn't.

> **Core Concept:** [Partitioning Strategies](../../core-concepts/03-scaling/02-partitioning-strategies.md) covers the generic tools for splitting data across nodes. The streaming version is the same idea applied to an event log instead of a table.

### 3. Consumer Groups for Parallel Processing

Once data is partitioned, processing has to be partitioned too. Streaming brokers have a built-in primitive for this: a **consumer group** is a set of consumer instances that cooperate to read a topic, with each partition assigned to exactly one consumer in the group at a time. Add a consumer to the group → some partitions move to it. Remove one → its partitions move elsewhere.

This gives you both topologies from the messaging chapter at once, on the same topic, with no special configuration: each *group* sees every record (fan-out between groups), inside a group records are split (queue inside each group). The same primitive does both.

---

## Why "Real-Time" Now Means Something Specific

With these three properties in place, processing changes shape. The classic batch model -- "run a job at 2am that reads yesterday's files and writes today's report" -- becomes a special case of a more general model: continuous queries over an unbounded stream, with results that update as new data arrives.

That's what *real-time* means in this module. Not microsecond control-system latency, but **sub-second to a few seconds** end-to-end: an event happens, and a result reflecting that event appears downstream a moment later, not the next morning. The contrast is sharp:

```
Batch (spark-etl):   file lands at 12:00:05  →  results visible at 12:01:00  (~1 minute)
Streaming:           event happens at 12:00:05  →  result visible at 12:00:05.5  (~500 ms)
```

That gap -- a hundred-fold reduction in end-to-end latency -- is the whole reason this stack exists. We'll come back to it in [Real-Time vs Batch](../03-streaming/01-realtime-vs-batch.md), once we have the Kafka concepts in place to discuss it concretely.

---

## What This Module Will Cover

The rest of the module follows the same shape as the demands above:

1. **Kafka** -- the broker that makes the three properties (durable log, partitioning, consumer groups) concrete. We will learn the generic concepts through Kafka so they transfer to Pulsar, Kinesis, and the rest.
2. **Spark Structured Streaming** -- the processing layer on top of Kafka. Continuous queries, windowing, watermarks, checkpoints. The same DataFrame API you know from batch, applied to an unbounded input.
3. **A scaffolded clickstream project** -- producer → consumer → Spark job → windowed aggregation, built incrementally across the three sessions.

The next lesson zooms out and looks at the **kinds of systems** these tools tend to show up in -- not just analytics pipelines, but also event-driven services, audit logs, and async RPC -- so you have a feel for which problems streaming solves and which it doesn't, before we open up Kafka itself.

---

[Next: Where This Shows Up →](02-where-this-shows-up.md)
