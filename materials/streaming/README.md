# Real-Time Streaming and Message Queues

This module covers two related topics that almost always appear together in modern data systems: **messaging architectures** (decoupling services with a broker in the middle) and **real-time stream processing** (computing answers continuously as data arrives, rather than in scheduled batches).

The tools we work with are **Apache Kafka** for the broker layer and **Spark Structured Streaming** for the processing layer -- but the goal is to learn the *concepts* through these tools, so what you take away transfers to RabbitMQ, Pulsar, Kinesis, Flink, and the next generation of whatever replaces them.

## Prerequisites

- The [Spark batch ETL project](../projects/spark-etl/) -- this module explicitly contrasts batch with streaming and assumes you've felt how a scheduler-driven pipeline behaves.
- [Pub/Sub and Messaging](../core-concepts/07-application-patterns/02-pubsub-and-messaging.md) -- the coupling problem, broker, topologies, delivery guarantees. The streaming module assumes you've read this.
- [Synchronous vs Asynchronous I/O](../core-concepts/07-application-patterns/03-sync-vs-async-communication.md) -- the code-level cousin of the same idea. Optional but useful background.
- Python 3.10+, Docker, basic SQL, comfort with Spark DataFrames.

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
| **03 - Streaming Processing** | [Real-Time vs Batch](03-streaming/01-realtime-vs-batch.md), [Streaming Mental Model](03-streaming/02-streaming-mental-model.md), [Structured Streaming Basics](03-streaming/03-structured-streaming-basics.md), [Windowing](03-streaming/04-windowing.md), [Watermarks & Late Data](03-streaming/05-watermarks-and-late-data.md), [Checkpoints & Fault Tolerance](03-streaming/06-checkpoints-and-fault-tolerance.md) | ~4 hours |
| **04 - Exercises** | [Streaming Exercises](04-exercises/01-streaming-exercises.md) | ~30 min |

**Total: 12 hours** (split across three sessions).

## Session Split

| Session | Focus | Theory | Hands-on |
|---|---|---|---|
| **S1 (4h)** | Kafka basics — messaging problem, broker model, consumer groups | 3h | Project Stage 1 (Parts A + B) — producer + consumer |
| **S2 (4h)** | Delivery guarantees, multi-node, real-time vs batch, Structured Streaming basics | 3h | Project Stage 2 (Parts A + B) — Spark reads Kafka, parquet sink |
| **S3 (4h)** | Windowing, watermarks, checkpoints | 3h | Project Stage 3 (Parts A + B) — windowed counts + late data |

Each session follows the same rhythm: **2h theory → 0.5h exercise → 1h theory → 0.5h exercise**.

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
