---
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---
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

In Spark Structured Streaming (SQL form, assuming `events` is registered as a temp view):

```python
events.createOrReplaceTempView("events")

windowed = spark.sql("""
    SELECT window(ts, '1 minute') AS w, page, count(*) AS views
    FROM events
    GROUP BY window(ts, '1 minute'), page
""")
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

Let's run a 5-second tumbling window over a `rate` stream. We use `rate` (rather than Kafka) because it's trivial to seed and produces a clean, predictable timestamp column.

```{code-cell} python
import time
from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .appName("windowing-demo")
    .master("local[2]")
    .config("spark.sql.shuffle.partitions", "2")
    .getOrCreate())

stream = (spark.readStream
    .format("rate")
    .option("rowsPerSecond", 5)
    .load())

# Register the streaming DataFrame as a temp view so we can query it with SQL.
stream.createOrReplaceTempView("rate_stream")

# 5-second tumbling windows, count rows per window — expressed in Spark SQL.
windowed = spark.sql("""
    SELECT window(timestamp, '5 seconds') AS window, count(*) AS count
    FROM rate_stream
    GROUP BY window(timestamp, '5 seconds')
""")

query = (windowed.writeStream
    .format("memory")
    .queryName("tumbling_demo")
    .outputMode("update")
    .start())

time.sleep(15)
query.stop()

spark.sql("SELECT window.start, window.end, count FROM tumbling_demo ORDER BY window.start").show(truncate=False)
```

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
windowed = spark.sql("""
    SELECT window(ts, '1 minute', '15 seconds') AS w, page, count(*) AS views
    FROM events
    GROUP BY window(ts, '1 minute', '15 seconds'), page
""")
```

**Use cases:** rolling moving averages, "errors in the last 5 minutes" updated every 30 seconds, smooth dashboards where you don't want a discontinuity at every minute boundary.

**Cost:** more state. Each event belongs to `ceil(size / slide)` windows, so the engine carries that many open windows at any moment. With `size=1m, slide=15s` (ratio 4), every event is in 4 windows. With `size=1m, slide=1s` (ratio 60), every event is in 60. Slide values *much smaller* than size are the expensive end; slide values *close to* size are the cheap end, and `slide = size` reduces to tumbling (ratio 1).

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
sessions = spark.sql("""
    SELECT session_window(ts, '5 minutes') AS s, user_id, count(*) AS events
    FROM events
    GROUP BY session_window(ts, '5 minutes'), user_id
""")
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

> **Hands-on now — Stage 3 Part A.** Switch to `streaming-clickstream/stages/03-windowed-counts/lesson.md` and complete **Part A**. Come back here once Part A's acceptance test is green.

---

[← Previous: Checkpoints and Fault Tolerance](04-checkpoints-and-fault-tolerance.md) | [Next: Watermarks →](06-watermarks.md)
