# Real-Time Streaming and Message Queues

This module covers two related topics that almost always appear together in modern data systems: **messaging architectures** (decoupling services with a broker in the middle) and **real-time stream processing** (computing answers continuously as data arrives, rather than in scheduled batches).

The tools we work with are **Apache Kafka** for the broker layer and **Spark Structured Streaming** for the processing layer -- but the goal is to learn the *concepts* through these tools, so what you take away transfers to RabbitMQ, Pulsar, Kinesis, Flink, and the next generation of whatever replaces them.

## Prerequisites

- The [Spark batch ETL project](../projects/spark-etl/) -- this module explicitly contrasts batch with streaming and assumes you've felt how a scheduler-driven pipeline behaves.
- Python 3.10+, Docker, basic SQL, comfort with Spark DataFrames.

The two core-concepts lessons that underpin this module ([Pub/Sub and Messaging](../core-concepts/07-application-patterns/02-pubsub-and-messaging.md) and [Synchronous vs Asynchronous I/O](../core-concepts/07-application-patterns/03-sync-vs-async-communication.md)) are taught **inside S1** -- no pre-reading required.

## Core Concepts Reference

This module references concepts from the **[Core Concepts library](../core-concepts/README.md)**. When a lesson links to a core concept, the recommended flow is:
1. Follow the link, read the generic theory.
2. Return to the streaming lesson to see *why this specific tool chose this concept*.
3. Compare with how you saw the same concept in the SQL/NoSQL/Spark courses.

| When you see... | The core concept is... |
|-----------------|----------------------|
| Pub/sub, fan-out, consumer groups, delivery guarantees, the coupling problem, sync RPC vs async messaging | [Pub/Sub and Messaging](../core-concepts/07-application-patterns/02-pubsub-and-messaging.md) |
| Blocking vs non-blocking I/O, event loops, `async`/`await` at code level | [Synchronous vs Asynchronous I/O](../core-concepts/07-application-patterns/03-sync-vs-async-communication.md) |
| Replication, leader/follower, ISR | [Replication Patterns](../core-concepts/05-replication-and-availability/01-replication-patterns.md) |
| Partitioning, partition key, scale-out | [Partitioning Strategies](../core-concepts/03-scaling/02-partitioning-strategies.md) |
| Append-only log, write-ahead log | [Write-Ahead Logs](../core-concepts/05-replication-and-availability/03-write-ahead-logs.md) |
| Quorum, `min.insync.replicas`, durability vs availability | [Quorum and Tunable Consistency](../core-concepts/04-distributed-systems/04-quorum-and-tunable-consistency.md) |

## Learning Path

| Module | Topics | Duration |
|--------|---------|----------|
| **01 - Introduction** | [From Messaging to Streaming](01-introduction/01-from-messaging-to-streaming.md), [Where This Shows Up](01-introduction/02-where-this-shows-up.md) | ~30 min |
| **02 - Kafka** | [Broker/Topic/Partition Model](02-kafka/01-broker-topic-partition-model.md), [Producers and Consumers](02-kafka/02-producers-and-consumers.md), [Consumer Groups & Rebalancing](02-kafka/03-consumer-groups-and-rebalancing.md), [Delivery Guarantees](02-kafka/04-delivery-guarantees.md), [Replication & ISR](02-kafka/05-replication-and-isr.md), [Multi-Node Deployment](02-kafka/06-multi-node-deployment.md), [Advanced Features Overview](02-kafka/07-advanced-features-overview.md) | ~3.5 hours |
| **03 - Streaming Processing** | [Real-Time vs Batch](03-streaming/01-realtime-vs-batch.md), [Streaming Mental Model](03-streaming/02-streaming-mental-model.md), [Structured Streaming Basics](03-streaming/03-structured-streaming-basics.md), [Checkpoints & Fault Tolerance](03-streaming/04-checkpoints-and-fault-tolerance.md), [Windowing](03-streaming/05-windowing.md), [Watermarks](03-streaming/06-watermarks.md), [Latency & Late Data](03-streaming/07-latency-and-late-data.md) | ~4 hours |
| **04 - Exercises** | [Streaming Exercises](04-exercises/01-streaming-exercises.md) | ~30 min |

**Total: 12 hours** (split across three sessions).

## Session Split

Each session follows the same rhythm: **2h theory → 0.5h exercise → 1h theory → 0.5h exercise**. Each theory block ends right where the next hands-on block begins -- no "we'll explain why later" gaps.

### S1 (4h) — Kafka basics: from messaging to a working round-trip

| Block | Content |
|---|---|
| **Theory 1 (2h)** | core-concepts: [Sync vs Async I/O](../core-concepts/07-application-patterns/03-sync-vs-async-communication.md) → [Pub/Sub and Messaging](../core-concepts/07-application-patterns/02-pubsub-and-messaging.md) → [01-Intro/From Messaging to Streaming](01-introduction/01-from-messaging-to-streaming.md) → [02-Kafka/Broker, Topic, Partition](02-kafka/01-broker-topic-partition-model.md) → [02-Kafka/Producers and Consumers](02-kafka/02-producers-and-consumers.md) (both sides — they're one chapter; Part A only needs the producer half) |
| **Hands-on A (0.5h)** | **Stage 1 Part A** — produce JSON pageviews keyed by `user_id` |
| **Theory 2 (1h)** | [01-Intro/Where This Shows Up](01-introduction/02-where-this-shows-up.md) (patterns recap) → [02-Kafka/Consumer Groups & Rebalancing](02-kafka/03-consumer-groups-and-rebalancing.md) (light treatment — fan-out/load-distribution; no commit semantics yet) |
| **Hands-on B (0.5h)** | **Stage 1 Part B** — consume with a `group_id`, return N events |

### S2 (4h) — Durability story: from Kafka acks to Spark checkpoints

The arc here is one coherent narrative — *"commit after the sink confirms"* — told from both ends. We finish the Kafka durability story first (closing the loop opened by Stage 1's auto-commit), then pivot once into Spark and stay there.

| Block | Content |
|---|---|
| **Theory 1 (2h)** | **Kafka durability (~45 min, taught as one unit):** [02-Kafka/Delivery Guarantees](02-kafka/04-delivery-guarantees.md) (the "remember Stage 1's auto-commit?" payoff — skim the Kafka-transactions deep-dive; it's not load-bearing) → [02-Kafka/Replication & ISR](02-kafka/05-replication-and-isr.md) (what `acks=all` actually buys you). **Spark intro (~75 min):** [03-Streaming/Real-Time vs Batch](03-streaming/01-realtime-vs-batch.md) → [03-Streaming/Streaming Mental Model](03-streaming/02-streaming-mental-model.md) → [03-Streaming/Structured Streaming Basics](03-streaming/03-structured-streaming-basics.md) (bulk of time goes here — it's the chapter Part A depends on). |
| **Hands-on A (0.5h)** | **Stage 2 Part A** — Spark `readStream` from Kafka, parse JSON, parquet sink |
| **Theory 2 (1h)** | [03-Streaming/Checkpoints & Fault Tolerance](03-streaming/04-checkpoints-and-fault-tolerance.md) — closes the durability arc: Kafka commits offsets, Spark commits the checkpoint, both *after* the sink confirms |
| **Hands-on B (0.5h)** | **Stage 2 Part B** — verify restart-from-checkpoint (no duplicates, no losses) |

### S3 (4h) — Windowed analytics over time

| Block | Content |
|---|---|
| **Theory 1 (2h)** | [03-Streaming/Windowing](03-streaming/05-windowing.md) — full 2h on event-time, tumbling vs sliding, window state; the actual prereq for the hands-on |
| **Hands-on A (0.5h)** | **Stage 3 Part A** — tumbling windowed count |
| **Theory 2 (1h)** | [03-Streaming/Watermarks](03-streaming/06-watermarks.md) + [Latency & Late Data](03-streaming/07-latency-and-late-data.md) — the conceptually hardest material; gets the full hour |
| **Hands-on B (0.5h)** | **Stage 3 Part B** — window + watermark + late-data handling |

The [02-Kafka/Multi-Node Deployment](02-kafka/06-multi-node-deployment.md) and [02-Kafka/Advanced Features Overview](02-kafka/07-advanced-features-overview.md) chapters are **optional reference material** — pull them in as Q&A buffer if a session finishes early, or point students at them as self-study. They are not on the critical path.

The [04 - Exercises](04-exercises/01-streaming-exercises.md) are optional, intended for after Stage 3.

## Lab Environment

```bash
make lab-streaming   # workspace + 3-broker Kafka (KRaft); Spark runs locally inside workspace
make down            # stop the lab
```

Once running:

| URL | What |
|---|---|
| <http://localhost:3000> | MyST docs — these lessons rendered |
| <http://localhost:8888> | JupyterLab (workspace) — write notebooks here; Spark runs in-process |
| <http://localhost:4040> | Spark UI (only while a streaming query runs) — watermark, micro-batches, query progress |
| <http://localhost:18080> | Kafka UI (Kafbat) — browse topics, partitions, messages, consumer-group lag |
| `localhost:19092, 19093, 19094` | Kafka bootstrap servers (from the host) |
| `kafka-1:9092, kafka-2:9092, kafka-3:9092` | Kafka bootstrap servers (in-cluster, from any container on the lab network) |

PySpark 4.0.0 and `kafka-python` are pre-installed in the workspace. SparkSessions in this module run in **local mode** (driver + executor in the same JVM) — the focus here is stream semantics, not cluster ops. The earlier Spark batch ETL module is where you saw the standalone cluster setup.

## Hands-on Project

The session exercises evolve a single scaffolded project across all three sessions: **streaming-clickstream**, a synthetic pageview pipeline that produces events into Kafka and processes them with Spark Structured Streaming. Scaffold it with:

```bash
make new-project ARGS="--scaffold streaming-clickstream"
```

Each session does one stage; each stage has Part A (after the first theory block) and Part B (after the second).

## Tools Used

| Tool | Purpose |
|---|---|
| **Apache Kafka (KRaft mode)** | Broker — 3 nodes for the lab, exercises use plain Kafka APIs |
| **kafka-python** | Producer/consumer client for Stage 1 |
| **PySpark Structured Streaming** | Streaming processing for Stages 2 and 3 |
| **`spark-sql-kafka` connector** | Spark's Kafka source/sink |
| **kafka-console-producer / consumer** | Quick CLI debugging |

---

**Ready to begin?** Start with [01 - From Messaging to Streaming](01-introduction/01-from-messaging-to-streaming.md).
