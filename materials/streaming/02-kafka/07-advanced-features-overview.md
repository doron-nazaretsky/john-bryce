---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---
# Advanced Features Overview

Kafka has grown beyond "broker, topic, partition." A handful of features built on the core model show up so often in real systems that you should know they exist, what problem each solves, and roughly how it does it. We won't use most of them in the project, but you'll meet them in production.

This is a tour, not a deep dive.

---

## 1. Log Compaction

Standard topic retention is time- or size-based: drop records older than 7 days, or keep at most 100 GB per partition. Compaction is a third option, suited to a different use case.

**Problem:** you want to use a topic as a key-value snapshot of current state. "What's the latest profile for user-42?" should be answerable by reading the topic, even if user-42 has had a million updates over the years.

**How it works:** Kafka's compactor periodically scans the log and keeps only the **most recent** record for each key. Older records with the same key are dropped.

```
Before compaction:
  (user-42, name="Alice")
  (user-42, name="Alicia")
  (user-99, name="Bob")
  (user-42, name="Alicia M.")
  (user-99, name="Robert")

After compaction:
  (user-42, name="Alicia M.")
  (user-99, name="Robert")
```

**Use cases:** Kafka Streams' state stores, the `__consumer_offsets` internal topic itself, slowly-changing dimensions in event-driven architectures, configuration distribution.

A quirk: a `null` value is treated as a **tombstone** -- once compacted, it deletes the key. This is how you remove records from a compacted topic.

You enable compaction with `cleanup.policy=compact` on the topic.

We can create a compacted topic and produce two records under the same key — the second one is the "current" value.

**Step 1 — create the compacted topic.**

```{code-cell} python
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, UnknownTopicOrPartitionError
import time

BOOTSTRAP = "kafka-1:9092,kafka-2:9092,kafka-3:9092"
TOPIC = "demo-compacted-topic"

admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP)
try:
    admin.delete_topics([TOPIC]); time.sleep(1)   # idempotent: re-runs start clean
except UnknownTopicOrPartitionError:
    pass
admin.create_topics([NewTopic(
    name=TOPIC, num_partitions=1, replication_factor=3,
    topic_configs={"cleanup.policy": "compact", "min.cleanable.dirty.ratio": "0.01"},
)])
print(f"topic {TOPIC!r} created with cleanup.policy=compact")
```

**Step 2 — verify the topic config.**

```{code-cell} python
from kafka.admin import ConfigResource, ConfigResourceType

configs = admin.describe_configs([ConfigResource(ConfigResourceType.TOPIC, TOPIC)])
for cfg in configs:
    for entry in cfg.resources[0][4]:
        if entry[0] == "cleanup.policy":
            print(f"cleanup.policy = {entry[1]}")
```

**Step 3 — produce two values under the same key.** Only the last one will survive compaction.

```{code-cell} python
from kafka import KafkaProducer

producer = KafkaProducer(bootstrap_servers=BOOTSTRAP)
producer.send(TOPIC, key=b"user-42", value=b'{"name":"Alice"}')
producer.send(TOPIC, key=b"user-42", value=b'{"name":"Alicia M."}')
producer.flush()
producer.close()
print("produced 2 records under key 'user-42'")
```

**Step 4 — read back what's in the log right now.** Compaction is asynchronous, so for a brand-new topic both records are still there. Explicit `poll()` so the read step is visible; `group_id=None` means no offsets are tracked.

```{code-cell} python
from kafka import KafkaConsumer
import time

consumer = KafkaConsumer(TOPIC, bootstrap_servers=BOOTSTRAP,
                         auto_offset_reset="earliest",
                         enable_auto_commit=False,
                         group_id=None)
deadline = time.time() + 10
got_any = False
while time.time() < deadline:
    batch = consumer.poll(timeout_ms=1000)
    if batch:
        got_any = True
        for records in batch.values():
            for r in records:
                print(f"offset={r.offset} key={r.key} value={r.value}")
    elif got_any:
        break
```

**Step 5 — clean up.**

```{code-cell} python
consumer.close()
admin.delete_topics([TOPIC])
admin.close()
print(f"closed consumer and deleted topic {TOPIC!r}")
```

---

## 2. Kafka Transactions

We mentioned these in [Delivery Guarantees](04-delivery-guarantees.md). They wrap a consume-process-produce cycle in an all-or-nothing unit so:

- Either every output record is visible *and* the input offsets advance, or
- None of it is visible and we'll re-process the inputs next time.

**Use case:** stream processors that read from one topic, transform, and write to another -- where exactly-once semantics across that loop matter.

**How it works:** the producer is given a `transactional.id` and uses `beginTransaction` / `commitTransaction` calls. Output records are tagged with the transaction. Consumers reading with `isolation.level=read_committed` skip records from in-flight or aborted transactions. Offset commits become part of the transaction.

**Caveat:** transactions live inside Kafka. If your consumer writes to Postgres or S3 instead of another Kafka topic, exactly-once across that boundary requires *additional* mechanism -- idempotent writes, transactional outboxes, or sink-side dedup.

Spark Structured Streaming uses transactions automatically when writing to Kafka. You don't write the API calls yourself.

---

## 3. Schema Registry

Kafka stores raw bytes -- it has no built-in concept of schemas. That's a feature in some contexts (flexibility, no central authority required) and a problem in others (no enforcement that producers and consumers agree on the structure of records).

**Schema Registry** is a separate service (Confluent's most prominent open-source contribution) that holds the schema for each topic and validates that:

- Producers serialize against a known, registered schema.
- Schemas evolve in compatible ways (e.g., new optional fields, no removal of required fields).
- Consumers can fetch the schema by ID and deserialize correctly even years after the fact.

Records carry a small "schema ID" in their bytes; producers and consumers fetch the actual schema definition from the registry.

**Common formats:** Avro (the original), Protobuf, JSON Schema.

**Why this matters:** without a registry, schema agreement is informal -- a comment in a wiki, a chat in Slack, an old version of a producer that nobody updated. With a registry, the contract is enforced and evolution is auditable.

The project uses plain JSON without a registry (per the course's no-extra-deps rule), but in production you would use one. We will not introduce one in the course.

---

## 4. Kafka Connect

Most data ends up in Kafka because something else *put* it there, and most data leaves Kafka because something else *pulls* it out. The "something else" is usually a database, a cloud storage bucket, a search index, or a third-party API.

Writing the integration code each time is repetitive. **Kafka Connect** is a framework for declaring those integrations as configuration:

```yaml
name: postgres-to-kafka
connector.class: io.debezium.connector.postgresql.PostgresConnector
database.hostname: db.internal
database.user: replicator
table.include.list: public.users,public.orders
topic.prefix: ecommerce
```

Connectors come in two flavors:

- **Source connectors** -- pull data from somewhere and produce to Kafka. Common: Debezium (CDC from databases), JDBC source, MQTT, file system.
- **Sink connectors** -- consume from Kafka and write somewhere. Common: JDBC sink, S3, Elasticsearch, BigQuery, Snowflake.

Connect runs as its own service (a worker, or a fleet of workers) on top of a Kafka cluster. The configuration of each connector is itself stored in a Kafka topic (config.storage.topic), and progress is tracked in Kafka -- the framework eats its own dog food.

In production, **CDC via Debezium** is one of the most important Connect use cases: streaming every change in a relational database into a Kafka topic so downstream systems can react in real time without polling.

We don't use Connect in the project, but recognize it when you see "connector" mentioned in production architectures.

---

## 5. Kafka Streams (and ksqlDB)

Kafka itself ships with a Java client library, **Kafka Streams**, for writing stream-processing applications that read and write Kafka topics. It's a competitor to Spark Structured Streaming and Apache Flink for the in-Kafka stream-processing niche.

**ksqlDB** is built on top of Kafka Streams: it lets you write stream queries in SQL.

```sql
CREATE STREAM pageviews_per_minute AS
  SELECT page, COUNT(*) AS views
  FROM pageviews
  WINDOW TUMBLING (SIZE 1 MINUTE)
  GROUP BY page
  EMIT CHANGES;
```

We use Spark Structured Streaming in this course because the previous course used Spark batch and we're building on that. In a Kafka-native stack, Kafka Streams or ksqlDB might be the right choice instead. The semantics overlap heavily; the picking criteria are mostly ecosystem fit (Java vs Python, existing Spark expertise, etc.).

---

## Where We Go Next

The Kafka half of this module ends here. Now we shift to the *processing* side: **Spark Structured Streaming**. The next chapter contrasts batch vs streaming, using your spark-etl experience as the starting point.

---

[← Previous: Multi-Node Deployment](06-multi-node-deployment.md) | [Next: Real-Time vs Batch →](../03-streaming/01-realtime-vs-batch.md)
