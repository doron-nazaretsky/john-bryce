# The ETL Pipeline We're Observing

The lab is built around an intentionally small ETL — the domain logic fits on a napkin. The complexity is everywhere *around* the ETL: the producer, the cluster, the upsert mechanics, the watermark. That's where production observability earns its keep.

## What the pipeline does

```
   Click event producer            Kafka topic            PySpark Structured Streaming    Postgres
   (workspace, on-demand)          "clicks"               (spark-master, long-running)    aggregated_clicks
   ──────────────────────          ──────────────         ────────────────────────────    ─────────────
   ~100 events/sec baseline   ──→  4 partitions     ──→   readStream + watermark       →  upsert (REPLACE)
   `rate` multiplier knob          RF=2, ISR≥1            groupBy(window, product_id)     (product_id,
   `inject-bad` for malformed                             count(*)                        minute_window,
                                                          → foreachBatch upsert            click_count, …)
                                                            (REPLACE on conflict)          UNIQUE(prod, minute)
```

It's a single streaming query. Spark drives it: every ~60 seconds (`processingTime` trigger), the engine forms a *micro-batch* (epoch), reads whatever has arrived on `clicks` since the last commit, updates its in-memory state store, and hands a small DataFrame of *changed rows* to our `foreachBatch` sink. The sink upserts those rows into Postgres.

Each epoch:

1. **Read** new records from `clicks`. Spark tracks committed offsets in a **checkpoint directory** (`/var/lib/spark-checkpoints/clicks`) — we don't manage offsets in application code.
2. **Parse** JSON with a fixed schema. Records with a non-null `ts` but a missing `product_id` are bucketed under the placeholder `__BAD__` so they remain countable; records without a `ts` have no event-time and are filtered out before the watermark sees them.
3. **Window + aggregate** by `(tumbling 1-minute window on event_time, product_id)`, running `count(*)`. The watermark is **2 minutes** behind `max(event_time)`: late records that arrive within 2 minutes of an open window can still update its count; later than that, they're dropped and counted in `numRowsDroppedByWatermark`.
4. **Sink** the *changed rows* (output mode `update`) into Postgres via `INSERT … ON CONFLICT (product_id, minute_window) DO UPDATE SET click_count = EXCLUDED.click_count`. Because the streaming aggregate is the running total maintained by Spark's state store, this is a plain REPLACE — no addition, no double-count risk on replay.

That's it. ~200 lines of Python.

## The shape of an event

```json
{
  "event_id": "9c2e3a8f-...",
  "product_id": "P017",
  "user_id":    "U02431",
  "ts":         "2026-05-20T17:09:47.812345+00:00"
}
```

Twenty product IDs (`P001`–`P020`), five thousand user IDs. The producer rotates randomly through them at the configured rate.

`producer inject-bad N` produces `N` events with `product_id` omitted. These are valid JSON; they pass Kafka and the schema cast. The drop happens at the aggregation step: with the `__BAD__` placeholder, they're counted but never reach Postgres. Each epoch's foreachBatch emits a WARN log line `dropped N records missing product_id`. **The pipeline does not fail on bad data** — it just produces a smaller good-output. That's the realistic failure mode, and it's exactly what makes the logs+traces signal so important.

## The 12 containers, mapped to the pipeline

```
   ┌─ workspace ──┐    ┌─ kafka-1 ─┐    ┌─ spark-master ──┐    ┌─ postgres ─┐
   │              │    │           │    │ + Streaming ETL │    │            │
   │ producer CLI │───→│ kafka-2   │───→│ + spark-worker- │───→│ aggregated │
   │ spark CLI    │    │           │    │   1, -2         │    │ _clicks    │
   └──────────────┘    └───────────┘    └─────────────────┘    └────────────┘
          │                                       │                   │
          │                                       │                   │  (pg_stat_*
          ▼                                       ▼                   │   scrape)
                       (admin protocol         (OTLP push from        │
                        scrape from collector)  Java agent + Python)  │
                                       └──────────┬────────────────┬──┘
                                                  ▼                 ▼
                                          ┌─ otel-collector ──────────┐
                                          │ filelog: /var/log/etl/    │
                                          │ kafkametrics: kafka-{1,2} │
                                          │ postgresql: postgres      │
                                          │ otlp: 4317/4318           │
                                          └──┬────────┬──────────┬────┘
                                             ▼        ▼          ▼
                                          ┌─Prom─┐ ┌─Loki─┐ ┌─Tempo─┐
                                             ▲       ▲        ▲
                                             └───────┴─Grafana┘
```

## The CLIs you'll use

Two Click-based CLIs are installed on the workspace and on PATH:

```bash
# Producer — controlled via a JSON file in /tmp; daemon reads every tick.
producer start                    # spawn the long-running producer daemon
producer status                   # show rate_mult, pending_bad, totals
producer rate 5                   # 5x the baseline rate (= 500 events/sec)
producer rate 1                   # back to baseline (100 events/sec)
producer inject-bad 100           # one-shot: next tick sends 100 malformed
producer stop                     # SIGTERM the daemon

# Spark Structured Streaming ETL — controlled via docker exec into spark-master.
spark batch start                 # start the long-running streaming query
spark batch status                # daemon liveness + last micro-batch progress
spark batch stop                  # SIGTERM the spark-submit / driver JVM
spark cluster status              # master + workers from the master REST API
```

The CLI command group is still called `batch` (legacy naming kept to avoid surprises in the lessons), but it now controls a streaming query. Both CLIs write a tiny status file each tick so `status` is a file read, not an RPC.

## The `batch_id` convention

This is the single most important thing in this module. Every micro-batch (epoch) generates a `batch_id` derived from Spark's `epoch_id`:

```python
batch_id = f"e-{epoch_id}"
# e.g. e-42  — monotonic per query lifetime, resumed from the checkpoint on restart
```

It appears on:

- **Every log line emitted inside `foreachBatch`** — the Python JSON formatter attaches `batch_id` as a field, AND each message includes the inline form `batch_id=e-N` so the Loki derived-field regex (`batch_id=([A-Za-z0-9\-]+)`) renders a clickable chip.
- **The manual `etl_batch` Tempo span** — set as a span attribute, one span per epoch. Tempo TraceQL: `{ .batch_id = "e-42" }`.
- **Postgres column `last_batch_id`** — every row in `aggregated_clicks` records which epoch last touched it.

When you find a problem in any one signal, copy the `batch_id` and search any other signal by it. This is the pivot that turns three separate dashboards into one investigation.

**Why prefix with `e-`?** It makes legacy values (the previous lab used `b-YYYYMMDD-HHMMSS-...`) visually distinct in historical Loki/Tempo data, and the regex still matches both forms — old material continues to work.

## Why streaming instead of a manual batch loop

Earlier versions of this lab ran a `while True:` loop calling `spark.read.format("kafka")` with explicit `startingOffsets` / `endingOffsets`, committing offsets back to a Postgres `kafka_offsets` table in the same transaction as the upsert. That design was instructive but its symptoms leaked into the dashboards in ugly ways:

- Each batch spun up a fresh Kafka consumer with a random `client_id`. The OTel Prometheus exporter retained the dead-consumer time series forever. After a few batches you'd see 50+ lag series instead of 4 — visually noisy and pedagogically misleading.
- A whole "committed offsets" table in Postgres existed solely to do what Spark's checkpoint mechanism does natively.
- Aggregation used `ADD-on-conflict` (each batch contributed a *delta*) — correct, but it required a careful reasoning about replay safety that was easy to get wrong.

Structured Streaming removes all of that:

- **One long-lived consumer** for the query's lifetime → 4 stable lag series, one per partition.
- **Spark-managed checkpoint** for offsets → no Postgres bookkeeping.
- **Stateful aggregation** maintains the running count → REPLACE upsert is trivially idempotent.

The cost we pay: a new concept the student has to learn — the **watermark** — which decides when a window is "closed" and how much late data we tolerate. That's a more useful thing to teach than offset bookkeeping.

## What's deliberately *not* here

A few production things we explicitly skipped to keep the lab focused:

- **No schema registry**. JSON, fixed schema in the code. Real prod would use Avro+Schema Registry; the observability story is identical.
- **No stream-stream joins or sessionization**. Single windowed aggregation is enough to demonstrate watermarks; richer streaming patterns are out of scope.
- **No backpressure tuning**. Producer just keeps producing; lag will climb under Scenario A. Structured Streaming has rate-limit options (`maxOffsetsPerTrigger`) we don't exercise.

In the next section we get to the first signal: metrics.
