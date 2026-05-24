# Scenario B Part 2 — Cross-Signal Investigation

We pick up Scenario B from the logs side and finish it from the traces side. By the end you'll have followed a single `batch_id` from a WARN line in Loki, to its trace in Tempo, to the per-job Spark spans, back to logs filtered to that batch — using nothing but mouse clicks.

## Setup

Producer + daemon running. If you ran Scenario B Part 1 a few minutes ago, you should still have the dropped-records WARN line visible in Loki. If not, retrigger:

```bash
docker exec workspace producer inject-bad 100
sleep 70  # let the batch process it
```

## Step 1 — Find the WARN in Loki

Open **Explore → Loki**:

```logql
{service_name="etl"} |= "dropped" |= "missing"
```

Pick the most recent match. Click to expand the row. Note the `batch_id` value at the bottom — say it's `e-42`.

You can also see the structured metadata block exposes `level=WARNING`, `logger=etl`.

## Step 2 — Pivot to Tempo via the derived field

In the expanded row, near the bottom: a button labeled **"View traces for batch"**. Click it.

Grafana opens a split view. The right pane is Tempo, with a TraceQL search returning the `etl_batch` span for that exact `batch_id`. Click the trace.

You see the timeline: one span, sub-second to a few seconds, the `batch_id` attribute matches what you came from.

## Step 3 — Find the Spark-side trace

The `etl_batch` (etl-driver) span doesn't have child spans — it's the deliberate single Python span around the foreachBatch upsert. To see the Spark-internal view of *this* epoch, switch the Tempo query to search by service `spark-driver` and filter by approximate time of the etl_batch span. Or use TraceQL:

```traceql
{ resource.service.name = "spark-driver" }
```

Look for traces whose start time is roughly within the etl_batch's time window. There will typically be a few Spark jobs per micro-batch (Kafka source consume, state-store read, the windowed aggregation, the foreachBatch driver collect). Each is its own trace tree, each with its own stage spans.

This is the trace fragmentation we talked about — two views of the same batch, in separate trace trees, linked by *time* and *the batch_id we know from logs*.

In a richer setup you'd also see executor-side spans (Kafka client spans, JDBC spans). In our lab those are quiet because the postgres write goes through psycopg on the driver, not JDBC on executors.

## Step 4 — Jump back to logs from a span

In any of the Spark spans you opened in step 3, click "Logs for this span" (top-right of the span panel). Tempo's `tracesToLogsV2` config substitutes the etl_batch's `batch_id` into a LogQL query and opens Loki with:

```logql
{service_name=~".+"} | batch_id=`e-42`
```

You see every ETL log line for that epoch. Note the time-ordered story:

```
17:11:02  INFO    epoch start batch_id=e-42 input_rows=5060 good=20 bad=1  (start; 20 good product/window rows changed plus the bad bucket)
17:11:04  WARNING dropped 100 records missing product_id ...               (the smoking gun)
17:11:05  INFO    epoch done batch_id=e-42 rows_written=20 bad=1           (the summary; bad rows are skipped from postgres)
17:11:05  INFO    streaming progress batch_id=e-42 input_rows=5060 dropped_by_watermark=0
```

You investigated bad-data symptoms from three angles in under 30 seconds:

- **Metrics** (postgres write rate slightly lower → 40 ETL Business dashboard)
- **Logs** (the WARN itself, and the explicit "total=X bad=Y" summary)
- **Traces** (the epoch duration was normal — schema cast is cheap — so it was a soft failure, not a perf problem)

## What this would look like without observability

The same problem in a typical "we ship to Splunk and hope" setup:

- The pipeline succeeds. Postgres row counts are slightly lower than expected.
- Three days later, a downstream report flags a 0.7% drop in click counts.
- Someone digs into the SQL warehouse, traces back through the pipeline manually, eventually finds the batch with the drop.
- No idea *why* the records were dropped — there's no trace of the schema cast failure.
- Maybe-fix: add a row-count alarm. Doesn't catch the next variant.

With our pattern: ten seconds, three clicks, you have the batch_id, the WARN text, the count, the timing, and the database evidence — enough to file a ticket with the upstream producer team that includes the exact records' offset range.

## Where the wow comes from

Not from any individual tool. Loki, Tempo, Prometheus, Grafana — each on its own is just a database with a query language. The wow is in:

1. Picking **business identifiers** that survive every process boundary in your pipeline.
2. Tagging those identifiers onto **every signal everywhere** — log fields, span attributes, table columns.
3. Pre-configuring **navigation links** in your viz tool so the pivot is one click, not a copy-paste.

You can replicate this with Datadog, Honeycomb, New Relic, or even with stdout-and-grep if you're disciplined about the identifiers. The mechanism above is just one concrete instance of the pattern.

## Mini-exercise (for the gap before next section)

Without using the dashboards — only Explore — answer:

1. How many distinct batches succeeded in the last 15 minutes? (Loki, LogQL aggregation)
2. What's the duration of the slowest batch in the last hour? (Tempo, TraceQL with `duration` filter)
3. Did any batch with dropped records have an unusually long duration? (Loki to find batch_ids with WARN, then Tempo for each)

You're now equipped for the final scenario, where all three signals tell one coherent story about a different kind of failure.
