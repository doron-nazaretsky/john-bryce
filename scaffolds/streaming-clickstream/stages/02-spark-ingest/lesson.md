---
kernelspec:
  name: python3
  language: python
  display_name: Python 3
---

# Stage 2 — Spark Ingest

## The Situation

We have events in Kafka. Now we want them on disk in a queryable format —
parquet — so analysts can run batch queries over history. The naive approach
is "spin up a job every minute and read whatever's new" (the spark-etl
approach). We're going to do better: a *long-running streaming query* that
reads continuously and writes incrementally.

This stage is one function — `build_stream` in `pipeline/ingest_job.py` —
that you'll evolve across the two parts. Part A builds the query and gets
events flowing to parquet. Part B comes *after* the checkpoints theory
lesson and verifies that the same query can be killed and restarted
without duplicating or losing rows.

## Design Considerations (for Part A)

- The query runs forever. There's no "next tick" to retry on failure —
  the engine itself has to come back up and resume. For now, just notice
  that's the shape of the problem; we'll see how Spark solves it in
  Theory 2.
- `outputMode("append")` is fine for *un-aggregated* events. Why? When does
  it not work?
- The writer needs a `checkpointLocation`. Treat it as a required path
  Spark needs — the next theory chapter unpacks what's actually in it.

## Part A — Read from Kafka, parse, write parquet (~30 min)

Open `pipeline/ingest_job.py` and implement `build_stream`. The function
should:

1. `spark.readStream.format("kafka")` from `kafka_conf.bootstrap_servers`,
   subscribing to `kafka_conf.topic`.
2. `option("startingOffsets", "earliest")` so a brand-new query reads the
   seeded test events.
3. Parse the `value` column (bytes) as JSON with the schema:
   ```
   user_id      string
   session_id   string
   page         string
   referrer     string
   ts           timestamp
   ```
   (Hint: `from_json(col("value").cast("string"), schema)`.)
4. Write to parquet at `sink_conf.output_path` with checkpoint at
   `sink_conf.checkpoint_path`, `outputMode("append")`, trigger every
   `5 seconds`.
5. Return the `StreamingQuery`.

**Acceptance:**

```bash
docker exec project-streaming-jupyter pytest /home/jovyan/work/tests/test_stage2.py::test_part_a -v
```

The test produces 20 events, starts your query, waits up to 90 seconds for
20 parquet rows to appear, and verifies the schema and content.

## Part B — Verify restart-from-checkpoint (~30 min)

> You should have just finished the **Checkpoints and Fault Tolerance**
> theory lesson. Part B is where that theory lands: we kill the query
> mid-stream, restart it, and watch the checkpoint do its job.

The test for Part B does something Part A's test doesn't: it stops the
query, produces *more* events, restarts the query, and asserts that exactly
the right number of rows ended up on disk — no duplicates from
re-processing the first batch, no losses.

For this to pass, the same `build_stream` must:

- Always pass `checkpointLocation` to the writer (you already did this in
  Part A — but verify it's correct). The checkpoint is what tells the
  restarted query *where in Kafka it had reached*; without it, the second
  run starts from `startingOffsets` again and double-writes everything.
- Use a deterministic `output_path`. Spark's parquet sink uses an atomic
  rename per micro-batch, so output files from successive runs accumulate
  cleanly in the same directory.
- Use `startingOffsets="earliest"` (the option is **ignored** when a
  checkpoint exists — Spark uses the committed offsets instead). This is
  the concrete payoff of "commit after the sink confirms": on restart,
  Spark trusts its own committed offsets, not the source's defaults.

If your Part A passes but Part B fails with too many rows, your
`startingOffsets` is being respected on the second run — check that
`checkpointLocation` actually points at a stable directory.

If Part B fails with too few rows, the checkpoint *is* being honored, but
some of the second batch isn't making it through. Increase the timeout in
the test (last resort) or check that the trigger is firing in time.

**Acceptance:**

```bash
docker exec project-streaming-jupyter pytest /home/jovyan/work/tests/test_stage2.py::test_part_b -v
```

## Definition of Done

- Both `test_part_a` and `test_part_b` pass.
- You can describe what the checkpoint contains (offsets, query metadata,
  state — even if state is empty for this query).
- You understand why parquet is exactly-once *for this query*: atomic
  rename + checkpoint advanced after the rename.

## Before You Move On

- Run `make events-start` in one terminal and `make run-ingest` in another.
  Watch parquet files appear under `data/ingested/`. Stop the ingest with
  `Ctrl+C`, restart it. Did you get duplicate rows?
- What would happen if you deleted the checkpoint directory and re-ran the
  query? (Hint: `auto_offset_reset` on Kafka — what does it do for a brand-
  new consumer group?)
- The stage 3 query is *stateful* (it holds open windows in memory). What
  do you predict the checkpoint will contain that this stage's didn't?

---

[← Stage 1 — Kafka Basics](../01-kafka-basics/lesson.md) | [Next: Stage 3 — Windowed Counts →](../03-windowed-counts/lesson.md)
