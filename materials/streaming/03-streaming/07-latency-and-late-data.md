# Latency and Late Data

The [previous chapter](06-watermarks.md) covered the watermark *mechanism* — what it is and how it moves. This chapter is about the part you actually operate: the threshold is a tuning knob, and turning it trades latency against correctness against memory. Here we make those trade-offs explicit, quantify the latency a watermark costs you, and follow what happens to the records that miss it.

---

## One Knob, Three Jobs

The watermark threshold looks like a single tuning number, but in Spark it controls **three things at once**, and you cannot set them independently:

1. **Emission delay** — how long a window waits after its end before it's finalized and emitted (in append mode). Window `[12:00, 12:01)` isn't emitted until the watermark passes `12:01`, i.e. roughly `threshold` after the window closed in event time.
2. **Late-data tolerance** — how out-of-order a record may be and still be accepted. Anything older than `max_ts − threshold` is dropped.
3. **State retention** — how long the engine keeps a window's state in memory before it can free it.

These are conceptually independent concerns, and Spark lets you decouple exactly **one** of them — emission delay — through output mode:

- In **append** mode, emission is tied to the threshold: a window emits once, only after the watermark passes its end, so result latency ≈ `threshold`.
- In **update** mode, the window is re-emitted every trigger as it changes. You *do* get fast emission while a large threshold still keeps the window open for late data — so "emit fast **and** tolerate late data" is achievable. The price is that downstream sees intermediate, **revisable** values rather than one final answer (the sink must handle upserts/idempotency).

What you **cannot** separate, in any output mode, is **late-data tolerance from state retention**. Both *are* `threshold`. To accept events up to an hour late, the engine must hold an hour of window state in memory — there is no way to say "tolerate 1h of lateness but keep only 1min of state." That is the real, inescapable coupling, and it's why "picking the threshold" is always a memory decision as much as a correctness one.

This is also the precise difference from Flink, whose `allowedLateness` is *separate* from the watermark: Flink fires a clean on-time result at the watermark and *then* keeps an independently-sized retention window for late corrections. Spark offers no such split — append gives one clean-but-late firing, update gives many fast-but-revisable firings, and in neither case can "how late I tolerate" be sized independently of "how much state I hold."

---

## Picking the Threshold

There's no universal right answer. The threshold should be **just barely longer than your typical lateness**, plus a margin.

A useful exercise: instrument your producer or broker to measure `(processing_time - event_time)` and look at the distribution. If 99% of events arrive within 30 seconds of the event time, a 1-minute watermark catches them with margin. If your mobile clients can be offline for 5 minutes and replay events on reconnect, you need a longer threshold.

For the lab and project: 2 minutes is generous. Real production values are usually 10s to 5 minutes.

| Tolerance | Implication |
|---|---|
| 10 seconds | Tight latency, drops anything late. Fine for "live now" dashboards. |
| 1 minute | Reasonable middle ground. Most real systems pick something here. |
| 10 minutes | Late data is a real concern. Watch state size. |
| 1 hour+ | Probably the wrong tool — consider periodic batch reconciliation instead. |

---

## The End-to-End Latency Budget

"Bigger threshold → emit later" is qualitative. Here is the actual decomposition. For an **append-mode** windowed aggregation, the wall-clock delay between an event happening and its window's result being visible downstream is the sum of:

```
result_latency ≈ (window.end − event_time)     # wait for the window to fill
               + threshold                      # wait for the watermark to pass window.end
               + (up to one trigger interval)   # watermark only advances at batch boundaries
               + batch processing time           # the compute itself
               + sink commit time                # write + checkpoint
```

Walk through it with a `1-minute` window, `threshold = 2 min`, `trigger = 10 s`:

- An event at `12:00:10` lands in window `[12:00, 12:01)`. It must first wait until event time reaches `12:01` for the window to even be complete — up to ~50s for this event.
- The window can't *emit* until the watermark passes `12:01`, which needs `max_ts ≥ 12:03` — another `2 min` of **event-time** progress (driven by data, not the wall clock; see [The Watermark Doesn't Wait for Wall Clock](06-watermarks.md#the-watermark-doesnt-wait-for-wall-clock)).
- The watermark only re-evaluates at a micro-batch boundary, so add up to one `trigger` interval (~10s; see [The Watermark Lags by One Micro-Batch](06-watermarks.md#the-watermark-lags-by-one-micro-batch)).
- Then the batch computes and the sink commits (typically sub-second to seconds).

So for a freshly-arrived event the *dominant* term is `threshold` plus the partial-window wait — the threshold is usually the single biggest contributor to end-to-end latency, which is exactly why it's the number you tune. Two consequences:

- **Append mode pays the full budget.** The result is correct-once and clean, but you wait `~threshold` for it.
- **Update mode trades the budget for churn.** It emits the running value every trigger (latency ≈ one trigger interval) and *revises* it as more data arrives — so you see results `threshold`-sooner, but the sink must tolerate being overwritten (idempotent/upsert), and downstream sees intermediate values. This is the latency lever you actually pull when `threshold`-scale delay is unacceptable.

If you have a latency SLA, budget backwards from it: the threshold you can afford is roughly `SLA − partial_window_wait − trigger − processing`. If that leaves no room for a threshold large enough to catch your real lateness, append mode can't meet the SLA and you must move to update mode plus downstream reconciliation.

---

## What Late Data Means in Each Output Mode

The interaction between watermarks and output modes is what trips people up. Three combinations matter:

### Append + Watermark (most common for windowed aggregations)

The window is held until its `end < watermark`. Once that's true, the window's row is emitted **once**, and any later record for that window is **dropped**.

This is what you want for "build a permanent record of windowed counts." It's also why append mode without a watermark on a windowed aggregation is forbidden — there'd be no point at which the engine could safely emit.

### Update + Watermark

The window is updated and re-emitted every time it changes. Late records that fall within the watermark cause an update; later records (past the watermark) are dropped. The downstream sink sees the latest value.

Use this for sinks that support upserts (a database with a primary key, a Kafka topic where consumers respect the latest value per key).

### Complete (no watermark needed)

The full result table is emitted every trigger. State grows with the cardinality of the result, so this only works for small queries (small number of distinct keys).

---

## Where Late Records Go

Records that arrive past the watermark are dropped — silently by default. You can monitor this:

```python
query = ...
print(query.lastProgress["stateOperators"][0]["numRowsDroppedByWatermark"])
```

That number is one of the most important streaming metrics. If it's growing, your threshold is too tight or your data has more lateness than you assumed.

In production, you typically:

1. Set a watermark generous enough to catch most late records.
2. Monitor `numRowsDroppedByWatermark`.
3. Run a *separate* periodic batch reconciliation job that catches the truly-late tail and corrects the result. This is the **"lambda architecture"** pattern: streaming for freshness, batch for correctness.

---

## Aggregation State: What's Stored, and When It's Freed

A windowed aggregation and a plain `GROUP BY` look almost identical in code, but they differ in one property that decides whether a query can run forever: *what state the engine holds, and whether anything ever removes it*. The concepts below build that picture one step at a time.

### The engine stores aggregates, not records

A streaming aggregation does **not** retain the input rows. It keeps one state entry per grouping key, holding only the running aggregate for that key.

```python
counts = spark.sql("SELECT page, count(*) AS views FROM events GROUP BY page")
```

The state here is the map `page → running_count`. A billion pageviews across 50 distinct pages is **50 state entries**, not a billion. Adding more events to an existing key just mutates that key's number; it does not add state.

### State scales with key cardinality, not event volume

Because state is one entry per key, its size is governed entirely by how many *distinct keys* exist — never by how many events flow through.

- **Bounded key** — `GROUP BY page` where pages are a small fixed set. State plateaus (≈50 entries) and stays flat no matter how long the query runs. Safe forever.
- **Unbounded key** — `GROUP BY user_id` (or `session_id`, or a URL with query strings). New keys keep appearing and nothing removes the old ones, so state grows without limit.

```python
# Bounded: a few dozen pages → safe
spark.sql("SELECT page    AS k, count(*) FROM events GROUP BY page")
# Unbounded: a new key per user, forever → state grows without limit
spark.sql("SELECT user_id AS k, count(*) FROM events GROUP BY user_id")
```

The failure mode is about key cardinality, not record count — a low-traffic stream with unbounded keys still blows up; a high-traffic stream with bounded keys does not.

### A watermark only frees state that can be *closed*

It is tempting to think `withWatermark` would bound the unbounded case. It does not, and adding it to a non-windowed aggregation has no effect.

```python
# This watermark is inert: there is no window for it to close.
events.withWatermark("ts", "10 minutes").createOrReplaceTempView("events")
spark.sql("SELECT user_id, count(*) FROM events GROUP BY user_id")
```

A watermark frees state by *finalizing windows*: when a window's `end` falls below the watermark, that window can never receive another record, so the engine emits it and evicts its state. A plain `GROUP BY user_id` has no window — there is no `end` to ever fall past the watermark, and a late record for any key must still be allowed to update that key's running count. The engine can therefore never declare a key "done," so it can never evict one.

### `complete` output mode pins every key forever

Output mode interacts with this. `complete` mode re-emits the *entire* result table every trigger, so by construction the engine must retain every key for the life of the query — even bounded-key aggregations keep all their keys (which is fine when that set is small).

```python
# Must hold every key forever — only acceptable when the key set is small.
counts.writeStream.outputMode("complete").format("console").start()
```

### Window + watermark is what makes state bounded

To bound an otherwise-unbounded aggregation, scope it to an event-time window and declare a watermark. Each key's state now belongs to a specific window; once that window's `end` passes the watermark, the window finalizes and *all* its per-key state is freed.

```python
events.withWatermark("ts", "2 minutes").createOrReplaceTempView("events")

windowed = spark.sql("""
    SELECT window(ts, '1 hour') AS w, user_id, count(*) AS views
    FROM events
    GROUP BY window(ts, '1 hour'), user_id
""")

query = (windowed.writeStream
    .format("parquet")
    .option("path", "/output/windowed")
    .option("checkpointLocation", "/checkpoints/windowed")
    .outputMode("append")
    .start())
```

Even though `user_id` is unbounded, state stays bounded: at any moment only the windows still within the watermark are live, and everything older has been emitted and discarded. This is the whole reason the windowed patterns in these chapters always pair `withWatermark` with `window(...)` — the window gives the watermark something to close, and closing is what frees the state.

---

> **Hands-on now — Stage 3 Part B.** Switch to `streaming-clickstream/stages/03-windowed-counts/lesson.md` and complete **Part B (window + watermark + late-data handling)**. Run `pytest tests/test_stage3.py -v` -- both parts should be green. That closes Session 3 and the project.

---

[← Previous: Watermarks](06-watermarks.md) | [Next: Streaming Exercises →](../04-exercises/01-streaming-exercises.md)
