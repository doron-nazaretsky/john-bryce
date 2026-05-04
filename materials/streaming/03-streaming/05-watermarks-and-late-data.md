---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---
# Watermarks and Late Data

Late data is a fact, not an exception. A record can arrive 30 seconds after the event happened, or 5 minutes, or an hour. Without some explicit rule about how late is too late, a streaming aggregation has to keep its state forever, "just in case." That's not feasible.

A **watermark** is the rule. It's a per-query promise that says: *"I won't accept any record with event time earlier than this anymore."* Once a window's end is past the watermark, the engine can finalize it and free the state.

This chapter explains how watermarks work in Spark Structured Streaming, what choosing a watermark threshold means in practice, and how late events are handled.

---

## What a Watermark Actually Is

At any moment, the engine knows the **maximum event time** seen across all input partitions so far. Call that `max_ts`.

The watermark is `max_ts - threshold`, where `threshold` is the lateness tolerance you declared:

```python
events.withWatermark("ts", "2 minutes")
# watermark = max(event_time seen) - 2 minutes
```

Concretely: if the highest event time we've observed is `12:05:30`, and we declared a 2-minute threshold, the watermark is `12:03:30`. Any window whose end is before `12:03:30` is "closed" and won't be updated. Records arriving with event time before `12:03:30` are considered too late and dropped.

Two things to internalize:

1. **The watermark is driven by the data**, not the wall clock. If no data flows for an hour, the watermark doesn't advance.
2. **The threshold is a trade-off**: bigger threshold → tolerate later events, but emit results later and hold state longer. Smaller threshold → emit fast, but drop more late records.

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

## Concrete Example

Records flowing into a 1-minute windowed query:

```
event_time              record       what happens
12:00:30                "/home"      window [12:00, 12:01) state: count=1
12:00:45                "/home"      window [12:00, 12:01) state: count=2
12:01:10                "/about"     window [12:01, 12:02) state: count=1
                                     (max_ts = 12:01:10, watermark = 11:59:10)
12:00:50  (late!)       "/home"      window [12:00, 12:01) state: count=3
                                     (still inside watermark, accepted)
12:03:30                "/home"      window [12:03, 12:04) state: count=1
                                     (max_ts = 12:03:30, watermark = 12:01:30)
                                     Window [12:00, 12:01) is now closed
                                     (end = 12:01:00 < watermark 12:01:30)
                                     ENGINE EMITS: ([12:00, 12:01), "/home", 3)
                                                   ([12:00, 12:01), "/about", 0)
                                                       (no /about records in that window)
                                     Wait — [12:00, 12:01) only had /home records,
                                     so it emits one row: "/home"=3
12:00:55  (very late!)  "/home"      window [12:00, 12:01) is closed
                                     event_time 12:00:55 < watermark 12:01:30
                                     RECORD DROPPED
                                     numRowsDroppedByWatermark += 1
```

Trace this through carefully. The mechanic is: **the watermark advances as the max event time advances; when a window's end falls below the watermark, the window finalizes and emits**.

A live demo: a `rate` source's `timestamp` column doubles as the event time. We declare a 2-second watermark and aggregate by 5-second windows. After running for a few seconds, we inspect the query's progress to see the watermark Spark has chosen.

```{code-cell} python
import time, json
from pyspark.sql import SparkSession
from pyspark.sql.functions import window, col

spark = (SparkSession.builder
    .appName("watermark-demo")
    .master("local[2]")
    .config("spark.sql.shuffle.partitions", "2")
    .getOrCreate())
spark.sparkContext.setLogLevel("WARN")

stream = (spark.readStream
    .format("rate")
    .option("rowsPerSecond", 5)
    .load())

windowed = (stream
    .withWatermark("timestamp", "2 seconds")
    .groupBy(window(col("timestamp"), "5 seconds"))
    .count())

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

## The Watermark Doesn't Wait for Wall Clock

A subtle behavior: if no data flows, the watermark doesn't advance. A window whose end is not yet past the watermark **does not emit** -- even if real-world time has long since passed the window's end.

This is correct semantically (if there's no data, you can't know whether late data might still come), but operationally surprising. It's also why test fixtures often have to send a "later" event to "push the watermark forward" and force earlier windows to emit.

You'll see this in Stage 3 of the project: a test that produces a window's worth of events, then produces a *later* event, then checks the earlier window's result. The later event is what advances the watermark and triggers emission.

---

## What `withWatermark` Doesn't Do

Common misconceptions:

- **It's not a wall-clock timeout.** A watermark is purely event-time based.
- **It's not retroactive.** Setting the threshold doesn't recover already-dropped records.
- **It's not per-key.** The watermark is global per query — there's one max event time across all groups. If one group has a much faster clock than others, slow groups can have their windows closed prematurely.
- **It's not free.** The engine has to track per-window state until the watermark passes. Bigger threshold = more state. Watch memory.

---

## Practical Recipes

### "Pageviews per page per minute, emit when window closes":

```python
windowed = events \
    .withWatermark("ts", "2 minutes") \
    .groupBy(window(col("ts"), "1 minute"), col("page")) \
    .count()

query = windowed.writeStream \
    .format("parquet") \
    .option("path", "/output/windowed") \
    .option("checkpointLocation", "/checkpoints/windowed") \
    .outputMode("append") \
    .trigger(processingTime="10 seconds") \
    .start()
```

### "Pageviews per page, always show the latest count" (rolling, no windows):

```python
counts = events.groupBy(col("page")).count()
# No watermark, no window — but state grows with cardinality of `page`
query = counts.writeStream.outputMode("complete").format("console").start()
```

### "Top pages in the last 5 minutes" (sliding, update mode):

```python
top = events \
    .withWatermark("ts", "1 minute") \
    .groupBy(window(col("ts"), "5 minutes", "30 seconds"), col("page")) \
    .count()

query = top.writeStream.outputMode("update").format("console").start()
```

---

> **Hands-on now — Stage 3 Part B.** Switch to `streaming-clickstream/stages/03-windowed-counts/lesson.md` and complete **Part B (window + watermark + late-data handling)**. Run `pytest tests/test_stage3.py -v` -- both parts should be green. That closes Session 3 and the project.

---

[← Previous: Windowing](04-windowing.md) | [Next: Checkpoints and Fault Tolerance →](06-checkpoints-and-fault-tolerance.md)
