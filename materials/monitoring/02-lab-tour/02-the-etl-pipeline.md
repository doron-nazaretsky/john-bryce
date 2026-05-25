# The ETL Pipeline We're Observing

The lab is built around an intentionally small ETL — the domain logic fits on a napkin. The complexity is everywhere *around* it: the producer, the cluster, the upsert mechanics, the watermark. That's where production observability earns its keep.

## What the pipeline does

```{mermaid}
flowchart LR
    P["<b>Click event producer</b><br/>(workspace, on-demand)<br/>~100 events/sec baseline<br/><code>rate</code> multiplier knob<br/><code>inject-bad</code> for malformed"]
    K["<b>Kafka topic</b> <code>clicks</code><br/>4 partitions<br/>RF=2, ISR≥1"]
    S["<b>PySpark Structured Streaming</b><br/>(spark-master, long-running)<br/>readStream + watermark<br/>groupBy(window, product_id)<br/>count(*)<br/>→ foreachBatch upsert<br/>(REPLACE on conflict)"]
    DB["<b>Postgres</b> <code>aggregated_clicks</code><br/>upsert (REPLACE)<br/>(product_id, minute_window,<br/>click_count, …)<br/>UNIQUE(prod, minute)"]
    P --> K --> S --> DB
```

It's a single streaming query. Spark drives it: every 10 seconds (`processingTime` trigger), the engine forms a *micro-batch* (Spark calls it an **epoch**), reads whatever has arrived on `clicks` since the last commit, updates its in-memory state store, and hands a small DataFrame of *changed rows* to our `foreachBatch` sink. The sink upserts those rows into Postgres.

Each epoch:

1. **Read** new records from `clicks`. Spark tracks committed offsets in a **checkpoint directory** (`/var/lib/spark-checkpoints/clicks`) — we don't manage offsets in application code.
2. **Parse** JSON with a fixed schema.
3. **Window + aggregate** by `(tumbling 30-second window on event_time, product_id)`, running `count(*)`. The **watermark** is 30 seconds behind `max(event_time)`: late records arriving within the watermark can still update an open window's count; later than that, they're dropped and counted in `numRowsDroppedByWatermark`. (For the watermark *concept* itself, see [`materials/streaming/03-streaming/06-watermarks.md`](../../streaming/03-streaming/06-watermarks.md); this page only states our setting.)
4. **Sink** the *changed rows* (output mode `update`) into Postgres via `INSERT … ON CONFLICT (product_id, minute_window) DO UPDATE SET click_count = EXCLUDED.click_count`. Because the streaming aggregate is the running total maintained by Spark's state store, this is a plain REPLACE — no addition, no double-count risk on replay.

~200 lines of Python.

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

## The `__BAD__` placeholder — silent bad data, made countable

`producer inject-bad N` emits `N` events with `product_id` omitted. They're valid JSON; they pass Kafka and the schema cast. Inside Spark, `coalesce(product_id, "__BAD__")` buckets them under the literal placeholder `__BAD__` so they remain countable in the aggregation. The `foreachBatch` sink intercepts those rows, counts them, logs a WARN `dropped N records missing product_id`, and drops them before the upsert.

**The pipeline does not fail on bad data** — it produces a smaller good-output. That's the realistic failure mode, and it's exactly what makes logs + traces the right signals for Scenario B.

## The `batch_id` convention — the most important thing in this module

Every epoch generates a `batch_id` derived from Spark's `epoch_id`:

```python
batch_id = f"e-{epoch_id}"
# e.g. e-42  — monotonic per query lifetime, resumed from the checkpoint on restart
```

It appears on:

- **Every log line emitted inside `foreachBatch`** — the Python JSON formatter attaches `batch_id` as a structured-metadata field, AND each message embeds the inline form `batch_id=e-N` so the Loki derived-field regex (`batch_id=([A-Za-z0-9\-]+)`) renders a clickable chip.
- **The manual `etl_batch` Tempo span** — set as a span attribute, one span per epoch. TraceQL: `{ .batch_id = "e-42" }`.
- **Postgres column `last_batch_id`** — every row in `aggregated_clicks` records which epoch last touched it.

When you find a problem in any one signal, copy the `batch_id` and search any other signal by it. **This is the pivot that turns three separate dashboards into one investigation.** The full cross-signal navigation mechanism is the subject of section 5.

## The CLIs you'll use

Two Click-based CLIs are installed on the workspace and on PATH.

```bash
# Producer — controlled via a JSON file in /tmp; daemon reads every tick.
producer start                    # spawn the long-running producer daemon
producer status                   # show rate_mult, pending_bad, totals
producer rate 5                   # 5x the baseline rate (= 500 events/sec)
producer rate 1                   # back to baseline (100 events/sec)
producer inject-bad 100           # one-shot: next tick sends 100 malformed
producer stop                     # SIGTERM the daemon

# Spark streaming ETL — controlled via docker exec into spark-master.
spark batch start                 # start the long-running streaming query
spark batch status                # daemon liveness + last micro-batch progress
spark batch stop                  # SIGTERM the spark-submit / driver JVM
spark cluster status              # master + workers from the master REST API
```

The CLI command group is still called `batch` (legacy naming) but it controls a streaming query.

You'll use `producer rate`, `producer inject-bad`, and `docker kill spark-worker-1` to trigger the three failure scenarios in section 6.

Next: orienting yourself in Grafana.
