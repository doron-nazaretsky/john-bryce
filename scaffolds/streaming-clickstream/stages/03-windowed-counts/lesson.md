---
kernelspec:
  name: python3
  language: python
  display_name: Python 3
---

# Stage 3 — Windowed Counts

## The Situation

The dashboard team wants "pageviews per page in the last minute," updated
continuously. That's a windowed aggregation over an unbounded stream — the
classic streaming-analytics shape. We build it once, with a watermark, in
`pipeline/windowed_job.py::windowed_counts`.

Like Stage 2, you'll evolve the same function across two parts. The
challenge here is conceptual, not mechanical: windowing without watermarks
holds state forever, watermarks change emission timing in subtle ways, and
"how do we know a window is finished?" is the streaming question we
discussed in lecture.

## Design Considerations

- A 1-minute tumbling window over event-time vs over processing-time —
  which one does the dashboard actually want?
- A watermark of 2 minutes means: how late can a record be before it's
  dropped? How long does state for one window stay in memory?
- `outputMode("append")` requires a watermark on a windowed aggregation.
  Why? What happens if you try without one?
- The watermark advances based on the *max event time seen*, not on wall
  clock. What does that mean for the test fixture?

## Part A — Tumbling window count (~30 min)

Open `pipeline/windowed_job.py` and implement `windowed_counts`. For Part A
the requirements are:

1. Read pageviews from Kafka (`startingOffsets="earliest"`), parse the JSON
   value with the schema from Stage 2.
2. **`withWatermark("ts", "2 minutes")`** — apply this *before* the
   `groupBy`. (Required for `append` mode.)
3. `groupBy(window(col("ts"), "1 minute"), col("page")).count()`.
4. Project the window struct's fields out as flat columns:
   ```python
   .select(
       col("window.start").alias("window_start"),
       col("window.end").alias("window_end"),
       col("page"),
       col("count"),
   )
   ```
5. Write to parquet at `output_path`, checkpoint at `checkpoint_path`,
   `outputMode("append")`, trigger every `5 seconds`.
6. Return the `StreamingQuery`.

**Acceptance:**

```bash
docker exec project-streaming-jupyter pytest /home/jovyan/work/tests/test_stage3.py::test_part_a -v
```

The test produces 6 events in a single 1-minute window plus 1 "pusher"
event 5 minutes later (to advance the watermark past the first window so
the engine emits it). It then waits up to 2 minutes for parquet rows
showing the per-page counts.

If your query never emits, **the watermark hasn't advanced past the
windows you expect to see**. Check that the pusher's event-time is well
beyond the windows you care about, and that your `withWatermark` is on the
right column.

## Part B — Late-data tolerance (~30 min)

Already done — the schema in Part A includes the watermark. Part B's test
verifies the *behavior* of the watermark: a near-late event (well within
the 2-minute threshold) must update its window's count.

Concretely, the test produces:

1. Four `/home` events at 10:00:00–10:00:15 (early).
2. A pusher at 10:05:00 (advances watermark to 10:03:00).
3. A "near-late" `/home` event at 10:00:08 (event-time before some windows
   already seen, but still inside the 2-minute watermark tolerance).

The first window `[10:00, 10:01)` should ultimately have `/home` count ≥ 4
in the output (4 early + 1 near-late).

If your Part A passed but Part B fails, you may have set `withWatermark`
*after* the `groupBy` (no-op) or used a too-tight threshold (you'd drop the
near-late). Re-check the order of operations.

**Acceptance:**

```bash
docker exec project-streaming-jupyter pytest /home/jovyan/work/tests/test_stage3.py::test_part_b -v
```

## Definition of Done

- Both `test_part_a` and `test_part_b` pass.
- You can articulate, in 1-2 sentences:
  - Why a watermark is required for append mode on a windowed aggregation.
  - What happens when the watermark advances past a window's end.
  - Why we needed a "pusher" event in the test.

## Before You Move On

- Run `make events-start` and `make run-windowed` together. Watch parquet
  windows accumulate under `data/windowed/`. They appear roughly 2 minutes
  after each window's end (your watermark threshold).
- The live producer emits ~10% of events with backdated timestamps (30s –
  2m late). Some of these are within the watermark, some aren't. Use
  `query.lastProgress["stateOperators"]` to see how many were dropped.
- (Stretch) Modify the function to also write to a Kafka topic
  `windowed-counts` instead of parquet. What output mode and key choice
  make sense?

---

[← Stage 2 — Spark Ingest](../02-spark-ingest/lesson.md) | [Project README](../../README.md)
