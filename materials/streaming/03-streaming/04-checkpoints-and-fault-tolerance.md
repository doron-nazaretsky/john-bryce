---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---
# Checkpoints and Fault Tolerance

A streaming query runs for days, weeks, months. During that time it builds up state -- offsets it has consumed, aggregates it has computed, windows it has open. When the query restarts -- because the cluster was upgraded, the driver crashed, the deploy rolled out -- all that state has to come back. Otherwise the query would either lose work (silently re-emitting) or duplicate work (re-reading from offset 0).

The mechanism is the **checkpoint**: a directory on durable storage where the engine continuously persists everything needed to resume.

---

## What's in a Checkpoint

A Spark Structured Streaming checkpoint contains:

- **Source offsets:** for every input source, the offsets that have been processed (not just *read* — fully *processed and committed to the sink*). For Kafka, this is `(topic, partition) → offset`.
- **State store:** for stateful operators (windows, dedup, joins), the in-memory state is periodically snapshotted to disk and incremental updates are logged.
- **Metadata:** schemas, query plan, configuration. Enough that Spark can verify the restarted query is "the same query" as before.

The checkpoint is updated **once per micro-batch**, after the sink confirms the write. This is what gives Spark its end-to-end guarantee: a record's offset is only committed *after* its output has landed.

```python
query = events.writeStream \
    .format("parquet") \
    .option("path", "/output/...") \
    .option("checkpointLocation", "/checkpoints/...")    # ← this
    .start()
```

If `checkpointLocation` is missing, Spark refuses to start a stateful query and warns even on stateless ones. **Always set it.**

### When does Spark checkpoint?

Checkpointing is automatic and tied to the micro-batch lifecycle — you don't trigger it manually:

- **Offsets and commit metadata:** written every micro-batch. Offsets are persisted to `offsets/<batchId>` *before* the batch runs (so Spark knows what it's about to process), and a marker is written to `commits/<batchId>` *after* the sink confirms the write.
- **State store snapshots:** for stateful queries, deltas are written every batch, and a full snapshot is taken periodically (default: every 10 batches, controlled by `spark.sql.streaming.stateStore.minDeltasForSnapshot`). Snapshots speed up restart; deltas keep recovery correct between them.

There's no time-based interval — cadence is driven entirely by batch boundaries, which in turn depend on your trigger (default: as fast as possible; or `trigger(processingTime="10 seconds")`, etc.).

Here's a tiny streaming query with an explicit checkpoint location. After it runs, we can inspect the checkpoint directory on disk and see Spark's bookkeeping (offsets, commits, metadata) take shape.

```{code-cell} python
import os, time, shutil, uuid
from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .appName("checkpoint-demo")
    .master("local[2]")
    .config("spark.sql.shuffle.partitions", "2")
    .getOrCreate())

ckpt = f"/tmp/streaming-ckpt-{uuid.uuid4().hex[:8]}"
shutil.rmtree(ckpt, ignore_errors=True)

stream = (spark.readStream.format("rate").option("rowsPerSecond", 3).load())

query = (stream.writeStream
    .format("memory")
    .queryName("ckpt_demo")
    .option("checkpointLocation", ckpt)
    .outputMode("append")
    .start())

time.sleep(8)
last = query.lastProgress
query.stop()

print("batchId committed:", last.get("batchId"))
print("source offsets:", last["sources"][0].get("endOffset"))
print(f"\ncheckpoint contents at {ckpt}:")
for root, dirs, files in os.walk(ckpt):
    for f in files:
        rel = os.path.relpath(os.path.join(root, f), ckpt)
        print(f"  {rel}")

shutil.rmtree(ckpt, ignore_errors=True)
```

You'll typically see `offsets/`, `commits/`, `sources/`, and `metadata` -- the building blocks Spark uses on restart to resume exactly where it left off.

---

## What "Fault Tolerance" Actually Means

When the query restarts:

1. Spark reads the checkpoint, finds the last committed offsets and the most recent state snapshot.
2. It rebuilds in-memory state from the snapshot (plus any incremental log entries since the snapshot).
3. It resumes consuming from the committed offsets.

The result: from the consumer's perspective, the restart is **transparent** -- as long as the records between the last commit and the crash are still in Kafka (which they are, because Kafka has retention), the query reads them again, processes them, and the sink either sees the duplicate writes or absorbs them, depending on how the sink works.

That last clause is the key to understanding the guarantee:

- **At-least-once into the sink** is what Spark gives you natively. Records may be re-processed and re-written after a crash.
- **Exactly-once into the sink** is possible **only if the sink is idempotent or transactional**. Examples that work: parquet output (each batch writes a new directory; Spark renames atomically on commit), Kafka output (Spark uses Kafka transactions). Examples that don't, by default: a JDBC sink with `INSERT` (you'll get duplicate rows on restart-after-crash).

The sink is where exactly-once is enforced or lost. Spark's contract is "I'll give the sink each record at least once and tell you when it's safe to commit;" the sink has to make that work.

---

## The Atomic-Commit Trick

Why does parquet "just work" for exactly-once? Because Spark uses a two-phase commit:

1. Each task writes its output to a **temporary subdirectory** during the micro-batch.
2. After all tasks succeed, the driver atomically renames the temp directory to the final batch directory and updates the checkpoint.
3. If anything fails before the rename, the temp data is orphaned (and cleanup is automatic) and the checkpoint is **not** updated -- next run will re-process the same records.

So either: temp written + rename + checkpoint advanced (success), or temp orphaned + checkpoint not advanced (failure, retried). There's no in-between where data is partially visible.

For a custom sink (`foreachBatch`), you have to design this yourself. The micro-batch ID is passed to your code, and you can use it for idempotent dedup:

```python
def write_to_postgres(batch_df, batch_id):
    batch_df.write \
      .mode("ignore") \
      .jdbc(url, table=f"output_b{batch_id}", ...)   # batch_id in the table name
    # or insert a row in a metadata table marking this batch as written
```

---

## What Matters Most Here: Source Offsets (and Two Guarantees Around Them)

For our Stage 2 query — a stateless ingest from Kafka to parquet — the "no duplicates, no losses on restart" property rests on three things working together. Only one of them is something you configure; the other two are guarantees Spark and the parquet sink give you for free. It's worth knowing all three, because if any one of them broke, the property would break with it.

**1. Source offsets in the checkpoint *(the part you configure)*.**
The checkpoint records, per Kafka `(topic, partition)`, the last offset Spark has fully processed. On restart, Spark reads that offset and tells the Kafka source: "resume from here." This is what `startingOffsets="earliest"` being *ignored on the second run* actually means — Spark uses the committed offset instead of the source's default. **This is the piece your `checkpointLocation` option turns on.** Without it, a restart re-reads from `earliest` and double-writes every record.

**2. Commit ordering: offsets are written *after* the sink confirms the write *(Spark's guarantee)*.**
Within each micro-batch, Spark writes to parquet first, waits for the rename to succeed, *then* advances the offsets in the checkpoint. So if the driver crashes mid-batch, one of two things is true: either the parquet write completed and the offset was advanced (clean), or the parquet write didn't complete and the offset wasn't advanced (so the next run reprocesses that batch — which is safe *because of #3*).

**3. Atomic rename in the parquet sink *(the sink's guarantee)*.**
A micro-batch is either fully visible in the output directory or not at all. There's no half-written file partially showing rows. So when #2 says "re-run the batch on restart," that re-run can't observe garbage left behind by the failed attempt.

Strip out any one of these and the property breaks: no offsets and you re-read from the start; wrong commit order and you'd commit offsets for data that never made it to the sink (losses); non-atomic sink and a crashed batch leaves visible duplicates. Together they give you exactly-once *visible output* on top of at-least-once processing.

Everything else in the checkpoint (query metadata, state stores, etc.) is bookkeeping or only matters for stateful operators — which we're about to meet.

---

## The State Store (Teaser)

> The rest of this section is a forward-look at things you haven't met yet -- **windowing** and **watermarks** are the next two chapters. You don't need this for Stage 2; come back to it once you've worked through Stage 3.

For stateful operators, the engine uses a **state store** -- by default, a key-value store backed by RocksDB (since Spark 3.2) or by HDFS (older default). It lives next to the checkpoint.

The state store remembers things like:

- Open windowed aggregates: `(window_start, page) → count` *(see [Windowing](05-windowing.md))*
- Watermark high-water mark *(see [Watermarks](06-watermarks.md))*
- Dedup tables (for `dropDuplicates`)
- Stream-stream join state

Each micro-batch:

1. Reads the relevant keys from the state store.
2. Updates them based on incoming records.
3. Writes the new values back.
4. Periodically snapshots and logs deltas so restart is fast.

If you ever see Spark's metric `numStateRows`, that's how many keys you've got in the state store. Track it.

---

## Recovery: What You Should Verify

For Stage 2B of the project, you'll write a query that:

1. Reads pageviews from Kafka.
2. Writes parquet to disk.
3. Has a checkpoint directory.

The verification is:

```bash
# 1. Start the query, let it run for 30s, check parquet has rows.
docker exec streaming-jupyter python -m pipeline.ingest_job &
sleep 30
ls /data/output/pageviews   # should have files
# 2. Kill it.
kill %1
# 3. Restart it.
docker exec streaming-jupyter python -m pipeline.ingest_job &
sleep 30
# 4. Confirm: no record was processed twice (parquet rows match the producer's count exactly).
```

The checkpoint is what makes step 4 possible. Without it, the second run would start from the beginning and double-write.

---

## Common Checkpoint Pitfalls

Things that go wrong if you don't think about them:

### Changing the query

Spark fingerprints the query plan into the checkpoint. If you change the query (add a filter, change a column type, change watermark threshold), the restart can fail with an "unsupported change" error.

A safe rule of thumb: **changing the query means starting a fresh checkpoint** (and accepting whatever reprocessing that entails). For minor changes (parameters, sink path), Spark is sometimes flexible -- but don't rely on it.

### Sharing a checkpoint between queries

Each query needs its own `checkpointLocation`. If two queries write to the same one, they corrupt each other's state. Pick directories like `/checkpoints/<query-name>` and never share.

### Putting the checkpoint on ephemeral storage

The checkpoint must outlive the driver. If you put it in a Kubernetes pod's local filesystem, it dies with the pod. Use a durable mount: HDFS, S3, GCS, an attached EBS volume.

For the project we use a path inside a Docker volume, which persists across container restarts.

### Old checkpoint with retention-expired data

If your query was offline for two weeks and Kafka retention is one week, the offsets in the checkpoint may be older than what's still in Kafka. The query will fail with `OffsetOutOfRange`. Recovery options: reset to the earliest available offset (re-process whatever's there), or accept the gap.

---

## Putting It All Together: The End-to-End Story

Combining the last three chapters, the full streaming-with-Kafka guarantee chain is:

1. **Producer:** idempotent producer (`acks=all`, default in modern Kafka) — exactly-once write to the partition log.
2. **Consumer (Spark):** offsets committed *after* sink writes succeed — at-least-once delivery into the processing logic.
3. **Stateful operations:** state stored in checkpoint, restored on restart — no loss of in-flight aggregates.
4. **Sink:** if idempotent (parquet, Kafka with transactions, JDBC with upserts), the writes are exactly-once visible.

Each link of the chain has to hold for end-to-end exactly-once. Skip the producer's idempotence and you can have duplicates in the topic. Skip the checkpoint and a crash drops state. Skip the sink's idempotence and you have duplicates in the warehouse.

In the project, every link holds: idempotent producer (default), Spark with checkpointing, parquet sink (atomic rename). The result is a pipeline you can crash and restart with no data loss and no duplication.

---

[← Previous: Structured Streaming Basics](03-structured-streaming-basics.md) | [Next: Windowing →](05-windowing.md)
