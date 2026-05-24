# Exercises (Optional Homework)

These are short — 15-45 minutes each — and meant to make the patterns stick. Pick one or do all four.

## Exercise 1 — Add a business log line

In `labs/monitoring/etl/etl_daemon.py`, the ETL currently logs `batch start`, `dropped N records`, `upserting N rows`, `batch done`. Add one more business-relevant log line.

Suggested target: **log the top product by clicks for each batch**.

Hint: after the aggregation step, you have an `agg_df` (Spark DataFrame). Compute `agg_df.orderBy(F.desc("click_count")).limit(1).collect()[0]` once per batch and log it:

```python
top = agg_df.orderBy(F.desc("click_count")).limit(1).collect()
if top:
    log.info(f"top product batch_id={batch_id} product_id={top[0]['product_id']} count={top[0]['click_count']}")
```

Restart the daemon (`spark batch stop && spark batch start`). After the next epoch:

1. Find your new log line in Loki: `{service_name="etl"} |= "top product"`.
2. Use the derived field to pivot to the trace for that epoch.
3. Confirm the same `batch_id` appears on both signals.

**Bonus**: turn the top product into a Loki structured-metadata-derived metric — `sum by (product) (count_over_time({service_name="etl"} |= "top product" | regexp "product_id=(?P<product>P[0-9]+)" [1h]))`. You now have a "which products are most active per hour" panel without changing any Prometheus config.

## Exercise 2 — Add a manual span

Right now the only Python span is `etl_batch`. Add a child span for one operation inside the micro-batch — for example, the postgres upsert.

In `upsert_to_pg`, wrap the `executemany` call:

```python
with _tracer.start_as_current_span("postgres_upsert", attributes={"rows": len(good_rows)}):
    cur.executemany("INSERT INTO aggregated_clicks ...", [...])
```

After the next epoch, in Tempo:

1. Find the etl_batch span as before.
2. Click into it — you should now see a child span `postgres_upsert` with the `rows` attribute.
3. Click "Logs for this span" — does it filter to only the upsert-time logs, or to the whole epoch? (Answer: the whole epoch, because our tracesToLogsV2 link is keyed on `batch_id` which is on the parent, and the child inherits.)

**Bonus**: add a span around the `df.collect()` to time how long the driver-side materialization takes. Now you have a trace that breaks down the epoch into "collect from state store", "upsert" — the same structure you'd build manually in any production pipeline.

## Exercise 3 — Build a custom Grafana panel

Pick a question we don't have a panel for, and answer it with a single panel.

Suggestions (pick one):

- **Average batch duration over the last hour** — Tempo has this data as span durations. Use Tempo's metrics-from-traces (Grafana 11+ supports TraceQL aggregations) or compute via a synthetic log-derived metric.
- **Dropped-record ratio** — `dropped / total`, derived from the "batch done total=X bad=Y" log line via LogQL `regexp` and `unwrap`. Plot as percentage over time.
- **Postgres write rate compared to Kafka consume rate** — already on Overview, but make a richer version: show the ratio, alert visually when consumed/written drifts > 10%.

Save the panel to a new dashboard `50 · My Investigations`. Use the same color palette (`semi-dark-*`) for consistency.

## Exercise 4 — Find a real failure

Cause a failure that isn't one of the three scripted scenarios. Diagnose it using only the observability tools.

Suggestions:

1. `docker exec spark-master bash -c "echo > /tmp/bad-conf"` and add `/tmp/bad-conf` to the spark-submit `--conf` list (you'd need to edit `start_daemon.sh`). The next start will fail.
2. `docker exec postgres psql -U app -d clicks -c "DROP TABLE aggregated_clicks"` — every batch will start failing with a SQL error.
3. `docker exec workspace producer rate 100` for a few minutes, then turn it off. Watch the recovery shape.

For each: write a 5-line incident note: when it started (timestamps from which dashboard), what the symptom was, which signals you used to localize the cause, and what the root cause was.

This is what an actual on-call ticket looks like. The point: with this stack, the incident note writes itself from the screenshots you take during diagnosis.

## Submission

These aren't graded; they're for your own reps. If you do exercise 4, share your incident note in #data-eng-monitoring — others learn from your patterns.
