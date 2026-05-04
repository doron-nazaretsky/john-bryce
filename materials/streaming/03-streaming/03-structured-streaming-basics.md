---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---
# Structured Streaming Basics

Spark's streaming API is **Structured Streaming**: the same DataFrame and SQL APIs you already know, applied to an unbounded input. The trick is: the DataFrame represents the *whole infinite stream*, not a fixed snapshot. Spark turns each query into a long-running job that incrementally maintains the result.

This chapter is the API tour: read source, transform, write sink, start the query.

---

## The Core Idea: Unbounded Tables

Imagine a table that grows over time. Each new record is a new row appended at the bottom. Now write a query against it: `SELECT page, count(*) FROM pageviews GROUP BY page`. In batch, this returns once. In Structured Streaming, this query is *always running* and maintains the result as new rows arrive.

```
pageviews (unbounded):                     query result (continuously maintained):
  page="/home", ts=10:00:01                   page="/home"  count=3
  page="/about", ts=10:00:02                  page="/about" count=1
  page="/home", ts=10:00:03                   ...
  page="/home", ts=10:00:05
  ...                                         (updates whenever input changes)
```

That's the whole API model: **DataFrames over unbounded tables, queries that maintain results forever**. Everything else is which source you read, which sink you write, and how triggers and output modes shape the emission.

---

## Reading from Kafka

Spark ships a Kafka source -- the `spark-sql-kafka` connector -- that reads a topic as a streaming DataFrame:

```{code-cell} python
from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .appName("pageview-ingest")
    .master("local[2]")
    .config("spark.sql.shuffle.partitions", "2")
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.0")
    .getOrCreate())

stream = (spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "kafka-1:9092,kafka-2:9092,kafka-3:9092")
    .option("subscribe", "pageviews")
    .option("startingOffsets", "earliest")
    .load())

stream.printSchema()
```

`stream` is a streaming DataFrame. Its schema is fixed: `key`, `value`, `topic`, `partition`, `offset`, `timestamp`, `timestampType`. The `value` column is bytes -- you have to deserialize.

```{code-cell} python
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import StructType, StructField, StringType, TimestampType

schema = StructType([
    StructField("user_id", StringType()),
    StructField("page", StringType()),
    StructField("ts", TimestampType()),
])

events = stream.select(
    from_json(col("value").cast("string"), schema).alias("event")
).select("event.*")

events.printSchema()
```

Now `events` has columns `user_id`, `page`, `ts`. From here it behaves like any DataFrame -- `select`, `filter`, `groupBy`, joins. The difference is it's unbounded.

`startingOffsets`:

- `earliest`: read from the beginning. Good for first-time setup or full backfills.
- `latest`: read only new records (after the query started). Good when you don't care about history.

After the first run, **the checkpoint** owns the consumed offsets and `startingOffsets` is ignored. You only set it for the first run.

---

## The Trigger: How Often Does the Engine Look?

Structured Streaming is, under the hood, a sequence of micro-batches. The engine periodically:

1. Asks the source for any new records since the last batch.
2. Runs the query against those records (incrementally maintaining state).
3. Writes the output.

The **trigger** controls how often this loop fires:

```python
query.writeStream.trigger(processingTime="10 seconds")
```

Common choices:

- **Default** (no trigger configured): fire as soon as the previous batch finishes. Latency-optimal.
- **`processingTime="N seconds"`** (the most common): fire every N seconds. More predictable resource use.
- **`once=True`**: fire once, process whatever's available, exit. Useful for batch-style "catch up" runs.
- **`availableNow=True`** (modern replacement for `once`): fire as many micro-batches as needed to drain the source, then exit.

For the project we'll use `processingTime="10 seconds"` -- a 10-second cadence. Each batch processes ~10 seconds of events.

> A note: there's also a "continuous processing" mode for sub-millisecond latency, but it's experimental and lacks most stateful operations. Don't use it.

---

## Writing to Sinks

The sink is where the result goes. The most common ones:

- **`console`** -- prints to stdout. For development and debugging only.
- **`parquet` / `json` / `csv`** -- writes files to a directory.
- **`kafka`** -- writes records back to a Kafka topic. Used for stream-to-stream pipelines.
- **`memory`** -- writes to an in-memory table queryable from the same Spark session. For tests.
- **`foreachBatch`** -- gives you the micro-batch as a regular DataFrame and lets you write it however you want (JDBC, S3 with custom logic, etc.).

A Kafka-to-parquet pipeline:

```python
query = events.writeStream \
    .format("parquet") \
    .option("path", "/output/pageviews") \
    .option("checkpointLocation", "/checkpoints/pageviews") \
    .trigger(processingTime="10 seconds") \
    .outputMode("append") \
    .start()

query.awaitTermination()
```

Three things here are non-negotiable:

- **`path`** is the output directory. Each micro-batch writes new parquet files.
- **`checkpointLocation`** is where Spark stores its state and committed offsets. Without it, recovery is impossible. Always set it.
- **`outputMode`** dictates emission semantics (next section).

---

## Output Modes

Earlier we said streaming results converge over time and the engine offers three output modes. They are:

### Append (default for stateless queries)

> "Only emit rows that won't change again."

For an `events` stream with no grouping, every row is final the moment it's written -- so append fits naturally.

For a *grouped* query like `groupBy(page).count()`, append needs a watermark to know when a group's count won't change anymore (because no more late records can arrive for that group). Without a watermark, the engine refuses, because every existing row could change forever.

### Update

> "Emit any row that changed in this batch."

Run a count query in update mode and you'll see `(/home, 3)` after the first batch, `(/home, 5)` after the next, etc. Same key, different value. The sink must support upserts or you'll have duplicates.

Most useful for sinks like a real-time database that supports upsert by key.

### Complete

> "Emit the entire result table on every trigger."

Only viable when the result is small. Useful for dashboards reading from a `console` or `memory` sink.

The streaming-clickstream project uses both **append** (Stage 2: writing raw events to parquet) and **update** with watermark (Stage 3: windowed counts).

---

## A Complete Minimal Pipeline

Putting it together, the smallest end-to-end query:

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, TimestampType

spark = (SparkSession.builder
    .appName("pageview-ingest")
    .master("local[2]")
    .config("spark.sql.shuffle.partitions", "2")
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.0")
    .getOrCreate())

schema = StructType([
    StructField("user_id", StringType()),
    StructField("page", StringType()),
    StructField("ts", TimestampType()),
])

raw = (spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "kafka-1:9092,kafka-2:9092,kafka-3:9092")
    .option("subscribe", "pageviews")
    .option("startingOffsets", "latest")
    .load())

events = raw.select(from_json(col("value").cast("string"), schema).alias("e")).select("e.*")

query = (events.writeStream
    .format("parquet")
    .option("path", "/data/pageviews")
    .option("checkpointLocation", "/checkpoints/pageviews-ingest")
    .trigger(processingTime="10 seconds")
    .outputMode("append")
    .start())

query.awaitTermination()
```

Run it. It runs forever. Every 10 seconds, it reads any new records from Kafka, parses them, and writes them as parquet files. The checkpoint tracks where it left off, so a restart resumes from the right offset.

This is essentially Stage 2 Part B of the project.

---

## What's Coming Next

So far the queries have been stateless -- each record turns into one output row. The interesting streaming queries are *stateful*:

- "Count pageviews per page per minute."
- "Find the top 10 pages every 5 minutes."
- "Detect users who visited 5 different pages in 30 seconds."

Those need windowing and watermarks. Next two chapters.

---

[← Previous: Streaming Mental Model](02-streaming-mental-model.md) | [Next: Windowing →](04-windowing.md)
