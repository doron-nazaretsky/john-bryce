---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---
# Watermarks

Late data is a fact, not an exception. A record can arrive 30 seconds after the event happened, or 5 minutes, or an hour. Without some explicit rule about how late is too late, a streaming aggregation has to keep its state forever, "just in case." That's not feasible.

A **watermark** is the rule. It's a per-query promise that says: *"I won't accept any record with event time earlier than this anymore."* Once a window's end is past the watermark, the engine can finalize it and free the state.

This chapter explains how the watermark *mechanism* works in Spark Structured Streaming — what it is, how it moves, what it doesn't do, and how it binds to a query. The next chapter, [Latency and Late Data](07-latency-and-late-data.md), covers how you *tune* it: choosing a threshold, the latency it costs you, and what happens to records that miss it.

---

## What a Watermark Actually Is

At any moment, the engine knows the **maximum event time** seen across all input partitions so far. Call that `max_ts`.

The watermark is `max_ts - threshold`, where `threshold` is the lateness tolerance you declared:

```python
# withWatermark has no SQL syntax — it stays on the DataFrame. After this,
# you can registerTempView and write the rest of the query in SQL.
events.withWatermark("ts", "2 minutes")
# watermark = max(event_time seen) - 2 minutes
```

Concretely: if the highest event time we've observed is `12:05:30`, and we declared a 2-minute threshold, the watermark is `12:03:30`. Any window whose end is before `12:03:30` is "closed" and won't be updated. Records arriving with event time before `12:03:30` are considered too late and dropped.

### Example

To make this concrete, here is a single stream of six records (1-minute windows, `threshold = 2 minutes`). We start with the raw data, then look at it through different lenses.

Two timestamps appear in the data and they are **independent**: `event_time` is when the event *happened* (carried in the record), `arrival_time` is when Spark *received* it. The watermark is computed from `event_time` only — `arrival_time` is shown purely to make the order records reach the engine visible.

**The data — a step-by-step trace.** Each row is one record arriving, with `max_ts` and the derived watermark after it:

| # | arrival_time | event_time | record | max_ts | watermark (`max_ts−2m`) | decision |
|---|---|---|---|---|---|---|
| 1 | 12:00:31 | 12:00:30 | /home | 12:00:30 | 11:58:30 | accept → window `[12:00, 12:01)`, count=1 |
| 2 | 12:00:46 | 12:00:45 | /home | 12:00:45 | 11:58:45 | accept → window `[12:00, 12:01)`, count=2 |
| 3 | 12:01:11 | 12:01:10 | /about | 12:01:10 | 11:59:10 | accept → window `[12:01, 12:02)`, count=1 |
| 4 | 12:01:20 | 12:00:50 | /home | 12:01:10 | 11:59:10 | accept (out of order) — `12:00:50 ≥ 11:59:10` → `[12:00, 12:01)`, count=3 |
| 5 | 12:03:31 | 12:03:30 | /home | 12:03:30 | 12:01:30 | accept → `[12:03, 12:04)`; **closes** `[12:00, 12:01)` (end `12:01:00 < 12:01:30`) → emits `(/home, 3)` |
| 6 | 12:03:45 | 12:00:55 | /home | 12:03:30 | 12:01:30 | **DROP** — `12:00:55 < 12:01:30`; window already closed; `numRowsDroppedByWatermark++` |

**Lens 1 — the event-time number line.** The watermark is a point on the event-time axis that *trails* the maximum event time seen by exactly `threshold`. It is not on a wall-clock axis. This snapshot is the state right after record 5 (`event_time 12:03:30`) arrives:

```
                      threshold = 2 min
                       ◄─────────────►
event-time ─┬──────┬──────┬──────┬──────┬───────►
          12:00  12:01  12:02  12:03  12:04
                       ▲             ▲
                   watermark      max_ts
                   12:01:30      12:03:30

  left of watermark  → TOO LATE: dropped (windows here are closed)
  right of watermark → accepted into its window
```

Anything to the left of the watermark is sealed off; anything to the right is still open for business. As `max_ts` moves right (driven only by data), the whole `◄─►` bracket drags right with it.

**Lens 2 — the per-record decision.** What the engine does each time a record shows up:

```
        record arrives (carries event_time)
                     │
                     ▼
        event_time > max_ts ? ──yes──► max_ts = event_time
                     │ no                recompute watermark
                     │                   = max_ts − threshold
                     ◄───────────────────────────┘
                     ▼
        event_time < watermark ?
            │                 │
          yes                 no
            ▼                 ▼
          DROP          route into its window,
   numRowsDroppedByWatermark++   update state
                              │
                              ▼
                  any window with end ≤ watermark?
                      → finalize & emit it, free its state
```

Note the watermark used to judge a record is the one *in effect when the record is processed* — a record can raise `max_ts` and thereby raise the bar for the records after it, but not retroactively. (The exact timing is one micro-batch coarser than "per record" — see [The Watermark Lags by One Micro-Batch](#the-watermark-lags-by-one-micro-batch) below.)

Read the table against the two lenses: each row is the number line (Lens 1) sampled at one step, and each `decision` cell is one pass through the flowchart (Lens 2). Two things stand out:

- **Record 4** arrives 30s after its event time (out of order) but is still accepted — its *event time* sits above the watermark. Arrival lateness is irrelevant.
- **Record 5** is the pivot: it pushes `max_ts` forward, which drags the watermark past `12:01:00`, sealing the first window. That is what turns the otherwise-harmless **record 6** into a drop — it arrives only 14s after record 5 in wall-clock terms, but its event time is 3 minutes in the past. The watermark cares about event time, not arrival time.

One thing to internalize above all: **the watermark is driven by the data**, not the wall clock. If no data flows for an hour, the watermark doesn't advance. (The other half — that the threshold is a latency/correctness trade-off — is the subject of the [next chapter](07-latency-and-late-data.md).)

---

## The Watermark Doesn't Wait for Wall Clock

A subtle behavior: if no data flows, the watermark doesn't advance. A window whose end is not yet past the watermark **does not emit** -- even if real-world time has long since passed the window's end.

This is correct semantically (if there's no data, you can't know whether late data might still come), but operationally surprising. It's also why test fixtures often have to send a "later" event to "push the watermark forward" and force earlier windows to emit.

You'll see this in Stage 3 of the project: a test that produces a window's worth of events, then produces a *later* event, then checks the earlier window's result. The later event is what advances the watermark and triggers emission.

---

## The Watermark Lags by One Micro-Batch

The Lens 2 flowchart says "recompute the watermark, then judge the next record against it." That's the right mental model but a deliberate simplification. In reality Spark advances the watermark **at micro-batch boundaries, not per record**, and the watermark *applied during* batch N is the one *computed at the end of* batch N−1.

Concretely: within a batch, Spark observes the rows and tracks the max event time, but only at the *end* of the batch does it update the watermark to `max_ts − threshold`. That new value governs the *next* batch. So a record is always judged against the watermark as of the previous batch — there is effectively one extra batch of grace.

Why it matters: a record your hand-calculation says should be dropped can survive one more batch because the watermark hadn't caught up yet. When you reason precisely — debugging why a late record was *not* dropped, or writing a test that asserts on drops — use "watermark from the end of the previous batch," not "watermark recomputed instantly." The inline `(watermark = …)` annotations in the trace above are the simplified per-record view; the batch-boundary rule is the exact one.

---

## Event-Time Skew Across Sources and Partitions

The watermark is the **max event time across all input partitions**, minus the threshold. "Max across all partitions" has an operational edge that bites in production.

Consider Kafka with multiple partitions. If one partition races ahead — its events carry newer event times — while another lags (a slow consumer, a rebalance, an under-provisioned broker), the fast partition drags `max_ts`, and therefore the watermark, forward. The lagging partition's events, which are perfectly normal and not actually late, now arrive *behind* a watermark that a different partition pushed ahead. They get dropped as "late" even though nothing is wrong with them.

The dual problem is an **idle partition**: one that receives no data contributes no event times, so it can't hold the watermark back — the watermark advances on the strength of the active partitions, and data that later shows up on the idle one may already be too late.

This is why "the watermark is global" (see [What `withWatermark` Doesn't Do](#what-withwatermark-doesnt-do)) is not just a per-key caveat — it's a per-*partition* one. Mitigations: keep consumer lag low and monitor it, provision so no partition starves, and size the threshold with partition skew in mind, not just per-record lateness. Spark deliberately keeps the watermark a single global value, so uneven sources are something you design around — not something the engine smooths over for you.

---

## What `withWatermark` Doesn't Do

Common misconceptions:

- **It's not a wall-clock timeout.** A watermark is purely event-time based.
- **It's not retroactive.** Setting the threshold doesn't recover already-dropped records.
- **It's not per-key.** The watermark is global per query — there's one max event time across all groups. If one group has a much faster clock than others, slow groups can have their windows closed prematurely.
- **It's not free.** The engine has to track per-window state until the watermark passes. Bigger threshold = more state. Watch memory.

---

## How a Watermark Binds to a Query

"Global per query" raises a fair question: at what granularity is a watermark configured, and how is one attached to a particular query? The watermark is **not** a session setting you change before launching a query — it is a *transformation in the query's logical plan*. The concepts below pin down the binding model.

### One watermark per query, not per key

Within a single streaming query there is exactly one watermark value at any instant: `max(event_time across all partitions and all groups) − threshold`. It is not per-group. If `/home` events run on a faster clock than `/about` events, the single shared watermark is driven by whichever group is ahead — and that can close the slower group's windows prematurely. This is what "global per query" means: global in *scope within one query*, not a global config shared across queries.

### You bind a watermark by attaching it to the DataFrame

`withWatermark` is a transformation, so it becomes a node in the logical plan of whatever query consumes that DataFrame. The query a watermark belongs to is decided purely by lineage — which DataFrame you called it on, and which `writeStream.start()` consumed that DataFrame.

```python
# Each query gets its own watermark on the DataFrame, then its own view + SQL.
df.withWatermark("ts", "2 minutes").createOrReplaceTempView("events_q1")   # ← part of q1's plan
df.withWatermark("ts", "30 seconds").createOrReplaceTempView("events_q2")  # ← independent, part of q2's plan

q1 = (spark.sql("""
        SELECT window(ts, '1 minute') AS w, count(*) AS c
        FROM events_q1 GROUP BY window(ts, '1 minute')
      """)
      .writeStream.format("console").start())

q2 = (spark.sql("""
        SELECT window(ts, '10 seconds') AS w, count(*) AS c
        FROM events_q2 GROUP BY window(ts, '10 seconds')
      """)
      .writeStream.format("console").start())
```

`q1` and `q2` run concurrently from the same source `df` with completely independent watermarks (2 minutes and 30 seconds). There is no `spark.conf` knob for the threshold; you "modify it per query" simply by attaching a different `withWatermark` to each DataFrame.

### The threshold is fixed at query start

A query's watermark threshold is captured into its plan (and its checkpoint) when `.start()` is called. To change it you must `.stop()` and restart the query. Changing the watermark threshold is also one of the checkpoint-incompatible changes from the [Checkpoints](04-checkpoints-and-fault-tolerance.md) chapter, so it generally requires a fresh checkpoint — you cannot retune a running query in place.

### Multiple watermarks in one query

A query can carry more than one watermark — e.g. a stream–stream join with `withWatermark` on each side. Spark collapses them into one effective watermark using `spark.sql.streaming.multipleWatermarkPolicy`, default `min` (the slowest input governs eviction), settable to `max`. If no `withWatermark` appears in the lineage at all, the query has no watermark and stateful operators never evict by event time — the unbounded-state situation discussed in the [next chapter](07-latency-and-late-data.md).

---

## A Live Watermark Demo

A `rate` source's `timestamp` column doubles as the event time. We declare a 2-second watermark and aggregate by 5-second windows. After running for a few seconds, we inspect the query's progress to see the watermark Spark has chosen.

```{code-cell} python
import time, json
from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .appName("watermark-demo")
    .master("local[2]")
    .config("spark.sql.shuffle.partitions", "2")
    .getOrCreate())

stream = (spark.readStream
    .format("rate")
    .option("rowsPerSecond", 5)
    .load())

# withWatermark has no SQL syntax — declare it on the DataFrame, then register
# the resulting (still-streaming) view and express the aggregation in SQL.
stream.withWatermark("timestamp", "2 seconds").createOrReplaceTempView("rate_stream")

windowed = spark.sql("""
    SELECT window(timestamp, '5 seconds') AS window, count(*) AS count
    FROM rate_stream
    GROUP BY window(timestamp, '5 seconds')
""")

query = (windowed.writeStream
    .format("memory")
    .queryName("wm_demo")
    .outputMode("update")          # update mode shows running counts as windows fill (append would wait for them to close past the watermark)
    .start())

time.sleep(15)
progress = query.lastProgress
query.stop()

print("event-time watermark Spark picked:", progress["eventTime"].get("watermark"))
print("max event-time seen so far:        ", progress["eventTime"].get("max"))
spark.sql("SELECT window.start, window.end, count FROM wm_demo ORDER BY window.start").show(truncate=False)
```

---

[← Previous: Windowing](05-windowing.md) | [Next: Latency and Late Data →](07-latency-and-late-data.md)
