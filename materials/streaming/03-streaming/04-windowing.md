# Windowing

Most interesting streaming queries ask "what happened in *this period of time*?" rather than "how many total ever?" Windowing is how we bound an unbounded stream into finite chunks of event time so we can answer those questions.

This chapter covers the three window shapes -- **tumbling**, **sliding**, **session** -- and what each one is good for.

---

## Why Windows?

A streaming query like `SELECT page, count(*) FROM pageviews GROUP BY page` runs forever. Its result grows unboundedly. After a year of traffic, "page=/home count=2,184,029" is true but useless: it tells you nothing about *when* the views happened.

Windows split the stream by event time:

```
SELECT
  window(ts, "1 minute") AS w,
  page,
  count(*) AS views
FROM pageviews
GROUP BY w, page
```

Now the result is `(window, page) → count`. Each row scopes its count to one minute of event time. The result still grows over time -- one row per (page, minute) -- but the grouping is bounded per minute.

In Spark Structured Streaming:

```python
from pyspark.sql.functions import window, col

windowed = events.groupBy(
    window(col("ts"), "1 minute"),
    col("page"),
).count()
```

`window` is a function that, given a timestamp column, returns a struct `{start, end}`. Group by it (along with whatever business keys you care about) and you have a windowed aggregation.

---

## Tumbling Windows

Tumbling windows are **fixed-size, non-overlapping** chunks of time:

```
events:    .  . ..   .   ...    . . .  ..    .
                            event time →

windows:  |---- W0 ----|---- W1 ----|---- W2 ----|
            10:00         10:01         10:02
```

Each event belongs to exactly one window. Tumbling windows are the default: `window(ts, "1 minute")` is tumbling with a 1-minute size.

**Use cases:** "pageviews per minute," "errors per hour," any "count per period" dashboard. The simplest and most common shape.

In SQL terms, the equivalent batch query would be `GROUP BY date_trunc('minute', ts)` -- bucketing by truncated time. Tumbling windows are the streaming version of that.

---

## Sliding Windows

Sliding windows are **fixed-size with overlap**:

```
events:   .  . ..   .   ...    . . .  ..
                            event time →

windows:  |---- W0 ----|
                |---- W1 ----|
                      |---- W2 ----|
                            |---- W3 ----|
```

You specify both *size* and *slide* (how much each new window advances). With size=1m and slide=15s, you get a new window every 15 seconds, each spanning the most recent 1 minute. Each event belongs to multiple windows.

```python
windowed = events.groupBy(
    window(col("ts"), "1 minute", "15 seconds"),
    col("page"),
).count()
```

**Use cases:** rolling moving averages, "errors in the last 5 minutes" updated every 30 seconds, smooth dashboards where you don't want a discontinuity at every minute boundary.

**Cost:** more state. With size/slide ratio = 4, the engine is maintaining 4x the windows simultaneously. Slide values close to size are expensive. Slide=size makes a sliding window equivalent to a tumbling one.

---

## Session Windows

Session windows are **dynamic, gap-defined**. There's no fixed size -- a session opens when activity starts, extends as long as events keep arriving close enough together, and closes when there's a gap of inactivity.

```
events:   .. ..  .  ........              ..  ...    .
                              event time →

sessions: |--- S1 ---|       |--- S2 ---|     |- S3 -|
                              (gap > 5min closes S1)
```

```python
from pyspark.sql.functions import session_window, col

sessions = events.groupBy(
    session_window(col("ts"), "5 minutes"),    # 5-min inactivity gap
    col("user_id"),
).count()
```

Each session is one user's burst of activity, bounded by 5 minutes of silence on either side. Sessions are *per group key* -- each user has their own concurrent sessions.

**Use cases:** user session reconstruction (session length, pages per session), bursts of related events (a deploy run, a checkout flow), anything where the "natural unit" is "activity until quiet."

Session windows are stateful in a more complex way -- the engine has to merge windows when a late event bridges two previously-separate sessions. Spark handles this for you, but the state cost can be significant.

---

## Picking the Right Window

| Question | Window |
|---|---|
| "Per-minute count for a dashboard" | Tumbling, 1 min |
| "Rolling 5-minute average updated every 30 seconds" | Sliding, size=5m, slide=30s |
| "How many pages did the user view per visit?" | Session, gap=30 min |
| "Top items per hour" | Tumbling, 1 hour |
| "Detect spikes (vs the last 10 minutes)" | Sliding, size=10m, slide=1m |

If unsure between tumbling and sliding, start tumbling. It's simpler, cheaper, and almost always good enough.

---

## What "Window" Actually Looks Like

The `window()` function returns a struct. After `groupBy(window(...))`, your result has a column called `window` with `start` and `end` subfields:

```
+------------------------------------------+--------+-------+
| window                                   | page   | count |
+------------------------------------------+--------+-------+
| {2026-05-03 10:00, 2026-05-03 10:01}     | /home  | 23    |
| {2026-05-03 10:00, 2026-05-03 10:01}     | /about | 7     |
| {2026-05-03 10:01, 2026-05-03 10:02}     | /home  | 19    |
+------------------------------------------+--------+-------+
```

Use `.select(col("window.start"), col("window.end"), ...)` to flatten if you want simpler output columns.

---

## Window Boundaries

Spark anchors windows to the **Unix epoch**, not to "the time the query started." A 1-minute tumbling window covers `[10:00:00, 10:01:00)`, then `[10:01:00, 10:02:00)`, regardless of when the query was launched. This makes results consistent across query restarts and across multiple parallel partitions.

Inclusive on the start, exclusive on the end. An event at exactly `10:01:00.000` belongs to the second window, not the first. Tracker for this is in the docs as `window(ts, slideDuration, startTime)` if you ever need to shift the boundaries (rare).

---

## Windowing Without Watermarks Doesn't Work in Append Mode

A windowed aggregation is *stateful*: the engine must hold the count for each open window in memory until it's sure no more records can land in that window. Without a way to declare "the window is closed," that state grows forever.

The mechanism is **watermarks** -- the next chapter. Briefly: a watermark is a promise that "no record with event time earlier than X will arrive after this point." Once a window's end is below the watermark, the engine can finalize and emit it (in append mode) and free the state.

Without a watermark, append mode for a windowed aggregation is *forbidden* -- Spark will refuse to start the query. Update or complete mode work without a watermark, but state grows unbounded, which is its own problem.

> The next chapter dives into watermarks; we'll come back and finish the picture.

---

## A Practical Stage-3 Sketch

For the project's Stage 3, the goal is "pageviews per page per minute, emitted as 1-minute windows close." That's:

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

`withWatermark("ts", "2 minutes")` is what makes append-mode windowed aggregation legal. Once the highest event time seen is `T`, the engine considers `T - 2 minutes` to be the watermark; any window ending before that is finalized.

We'll fill out exactly what those 2 minutes mean next.

---

[← Previous: Structured Streaming Basics](03-structured-streaming-basics.md) | [Next: Watermarks and Late Data →](05-watermarks-and-late-data.md)
