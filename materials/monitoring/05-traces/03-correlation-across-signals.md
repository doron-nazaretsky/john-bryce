# Correlation Across Signals — The Wow Moment

This is the page the whole module has been building toward. By the end of this lesson you'll know how to take *any* symptom in *any* signal and follow the same `batch_id` to all the others.

## Set-up — open the right things

Open two browser tabs:

- **Tab 1**: Grafana → Explore → Loki, with `{service_name="etl"}` running.
- **Tab 2**: Grafana → Explore → Tempo, with Search filter `Service Name = etl-driver`.

If you don't have recent traffic, fire an epoch:

```bash
docker exec workspace producer start
docker exec workspace spark batch start
sleep 90  # let one micro-batch complete
```

## Direction 1 — Loki → Tempo (the derived field)

In Tab 1 (Loki), find a log line containing the substring `batch_id=...`. The streaming daemon emits several per epoch: "epoch start", "epoch done", "streaming progress", and any WARN like "dropped … records missing product_id".

Expand the row. You should see a **batch_id** field at the bottom with a value like `e-42` and a button next to it: **"View traces for batch"**.

How this works:

```yaml
# config/grafana/provisioning/datasources/datasources.yaml
derivedFields:
  - name: batch_id
    matcherRegex: 'batch_id=([A-Za-z0-9\-]+)'
    datasourceUid: tempo
    url: '${__value.raw}'
    urlDisplayLabel: 'View traces for batch'
    internalLink: true
```

Grafana scans every rendered log line against `matcherRegex`. When it matches, it extracts the capture group and renders a button that opens an *internal link* to the Tempo datasource, passing the captured value.

Tempo's UI receives the value as a TraceQL query. Since the captured value is just `e-...`, Tempo interprets it as a trace_id (which fails — it's not a hex string) AND offers a TraceQL search fallback. The TraceQL search for `{ .batch_id = "e-..." }` succeeds and returns our `etl_batch` span.

Click the button. Tab 2 splits to show:

- **Top**: trace search result, with one trace matching.
- **Click the trace**: the span tree opens. `etl_batch`, attributes show `batch_id = e-...`.

You navigated from "a log line tells me something happened in epoch X" to "here's the trace of epoch X" in **two clicks**.

## Direction 2 — Tempo → Loki (the tracesToLogsV2 link)

In Tab 2, open the same `etl_batch` span. Top-right of the span detail panel: **"Logs for this span"** button.

How this works:

```yaml
# Tempo datasource jsonData
tracesToLogsV2:
  datasourceUid: loki
  spanStartTimeShift: '-30s'
  spanEndTimeShift: '30s'
  tags:
    - key: 'batch_id'
      value: 'batch_id'
  filterByTraceID: false
  filterBySpanID: false
  customQuery: true
  query: '{service_name=~".+"} | batch_id=`${__tags.batch_id}`'
```

When the user clicks "Logs for this span", Grafana extracts the `batch_id` attribute from the open span, substitutes it into the query template, and opens Loki with:

```logql
{service_name=~".+"} | batch_id=`e-...`
```

This filters to that exact epoch's log lines, regardless of `service_name`. You see "epoch start" → some intermediate INFOs → "epoch done" → "streaming progress", in time order.

Click. You've navigated from "trace shows what happened in this epoch" to "here's every log line that happened in that epoch" in **one click**.

## Why `batch_id` and not `trace_id`?

The canonical OpenTelemetry pivot is `trace_id` — log lines emitted inside a span are tagged with the span's trace_id by `LoggingInstrumentor`. In a simple Python service that works perfectly.

In our pipeline it doesn't, because:

- The `etl_batch` Python span lives in process A.
- The Spark job/stage spans live in process B (the JVM).
- They're different trace_ids by definition.
- Python log lines would get the etl_batch trace_id. JVM logs (which we don't ship to Loki anyway, but if we did) would get a different one.

`batch_id`, in contrast, is a single value we control. We attach it to every Python log line emitted inside `foreachBatch` (the JSON formatter), to the Python span (`etl_batch.batch_id`), and to Postgres rows (`last_batch_id`). It's the **business identifier** that survives every process boundary.

This is the production lesson: in a distributed pipeline, define one or two **business-level identifiers** (batch_id, job_run_id, deployment_version) and attach them to every signal everywhere. Trace_id is great for HTTP request flows; for batch ETL, business identifiers are king.

## Tempo TraceQL — the four queries you'll use

Open Explore → Tempo → query type **TraceQL**.

```traceql
# All spans tagged with any batch_id
{ .batch_id != "" }

# Slow batches
{ resource.service.name = "etl-driver" && duration > 10s }

# Failed batches (status set to ERROR in our Python code on exception)
{ resource.service.name = "etl-driver" && status = error }

# Specific epoch
{ .batch_id = "e-42" }
```

These are the queries you'd save into a team Tempo collection. With them, "show me the 10 slowest batches today" is one query, not a complex log-derived aggregation.

## The bigger pattern

The mechanism Grafana provides is general: any **derived field** (Loki side) or any **trace-to-logs config** (Tempo side) lets you link signals by *whatever string identifier you choose*. We picked `batch_id`. Production teams pick:

- `job_run_id` (orchestrator-level — Airflow / Dagster run IDs)
- `deployment_version` (which commit was this from)
- `tenant_id` (multi-tenant pipelines)
- `dataset_id` (especially with column-level lineage à la OpenLineage)

Pick the identifiers that match how you think about *your* failures. Tag everything with them. The wow moment is then mechanical.

Section 5 wraps with the second half of Scenario B, where we'll actually walk Direction 1 (Loki → Tempo) live.
