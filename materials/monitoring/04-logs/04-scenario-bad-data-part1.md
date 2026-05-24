# Scenario B Part 1 — Bad Data (Logs)

Upstream emits malformed records. The pipeline doesn't crash; it drops them and logs a warning. Without observability, you'd notice days later when downstream KPIs are off. With logs done properly, you see it within seconds.

## The setup

Producer + ETL daemon running. Tabs open: **Explore → Loki** (left half) and **40 ETL Business** dashboard (right half).

In Loki Explore, set this query and click **Live**:

```logql
{service_name="etl"} | level=~"WARNING|ERROR"
```

Empty stream right now — no warnings in steady state.

## Trigger

```bash
docker exec workspace producer inject-bad 100
```

This sets a one-shot counter in the producer's control file. On its next tick (within 1 second), the producer emits 100 events with no `product_id`, then decrements the counter back to 0.

## Watch for the WARN line

Within ~60 seconds the next streaming epoch fires. Spark reads the 100 malformed events along with the rest, parses them (they're valid JSON), runs the schema cast (`product_id` becomes NULL), and the windowed aggregation buckets them under the placeholder `__BAD__`. The foreachBatch sink detects the `__BAD__` rows, emits a WARN with the count, and skips writing them to Postgres:

```
{"ts":"2026-05-20T17:43:10.412Z","level":"WARNING","logger":"etl",
 "msg":"dropped 100 records missing product_id (running total across 1 open window(s))",
 "batch_id":"e-42"}
```

A subtle semantic difference from the legacy batch design: the count is a **running total** for any currently-open window touched by this epoch, not a per-epoch delta. If the producer injects bad records over several minutes, the same window's `__BAD__` bucket grows and the WARN's number grows with it. That's a property of stateful streaming with update output mode — the sink sees the current state, not the delta.

Your live-tail panel pops it. Your 40 ETL Business dashboard's "Records dropped / sec" panel shows a spike.

The headline number on Overview's "Dropped records (30m)" stat goes from 0 to 100 with a yellow background.

## Investigating the way you would in prod

You're the on-call. Someone in #data-quality asks "did anything weird happen with clicks today?". Procedure:

**Step 1**: open Overview, glance at the dropped-records stat. Non-zero? Go to step 2.

**Step 2**: open 40 ETL Business, find the "Records dropped / sec" panel. Identify when the spike was.

**Step 3**: in the dashboard's logs panel below, find a WARN line around that time. Note its `batch_id`.

**Step 4**: copy the batch_id, open Explore → Loki:

```logql
{service_name="etl"} | batch_id = "e-..."
```

You now see exactly what happened in that one epoch — start time, the WARN itself, the rows written, the done line. You can answer "did that epoch produce *any* output", "how many bad records vs good", "did the epoch fail or just degrade".

This investigation took 4 clicks. Without observability, it's reading a SQL aggregate output and reverse-engineering.

## Why the pipeline didn't fail

This is the crucial pedagogical point of Scenario B: **soft failures are the dangerous ones**.

```python
# In the streaming query, null product_ids are coalesced to a placeholder
# so they survive the aggregation as a counted bucket.
windowed = (
    parsed.withWatermark("event_time", "2 minutes")
          .groupBy(
              F.window("event_time", "1 minute"),
              F.coalesce(F.col("product_id"), F.lit("__BAD__")).alias("product_id"),
          )
          .agg(F.count(F.lit(1)).alias("click_count"))
)

# In foreachBatch we split the __BAD__ bucket out and log its count;
# only the good rows are upserted to Postgres.
bad_rows = [r for r in rows if r["product_id"] == "__BAD__"]
good_rows = [r for r in rows if r["product_id"] != "__BAD__"]
if bad_rows:
    log.warning(f"dropped {sum(r['click_count'] for r in bad_rows)} records missing product_id ...")
```

The pipeline counts the bad records, emits a WARN, drops them, continues. From the operator's outside view: the batch succeeded. Postgres got fewer rows but no exception was raised. Without the WARN, nothing surfaces the issue.

This is exactly how real pipelines lose money: a single field schema change at the producer that the ETL silently tolerates, downstream tables looking subtly wrong for days.

The lesson: **for every silent failure mode, emit a WARN with enough context to investigate later.** "Enough context" = a stable identifier (batch_id), the count, and enough description that someone reading it in a year will understand what was dropped and why.

## A check on the data side

You can verify Postgres reflects the drop:

```bash
docker exec postgres psql -U app -d clicks -c \
  "SELECT minute_window, sum(click_count) FROM aggregated_clicks
   WHERE last_batch_id = 'e-...'  -- paste your batch_id
   GROUP BY minute_window;"
```

Sum should be ~100 lower than what the producer emitted for that minute. Postgres knows it doesn't have those records. Anyone querying `aggregated_clicks` would not know — they'd just see slightly lower numbers.

`last_batch_id` is exactly the kind of column you want on every materialised table in production. It's the "I have a row, who put it here, and when" link to your pipeline's observability.

## What we haven't done yet

So far, this scenario lives entirely in **logs**. We have one WARN line that tells us *what* happened in *which* batch. But we don't have:

- The *duration* of the affected batch — was it slower because of the bad data? (Answer: no — schema cast is cheap. But to prove it we need traces.)
- Whether the bad-data batch had a different downstream timing pattern (e.g., postgres write took longer because the agg result was slightly different shape).
- Whether *upstream* tools — the Kafka producer, the broker — saw the bad records as anomalous.

The first two are trace questions. The third is metric, partially.

Section 5 picks up the same scenario but from the traces side, then connects them.
