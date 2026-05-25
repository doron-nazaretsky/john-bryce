# Cross-Signal Correlation — The Wow Moment

This is what the whole module has been building toward. By the end of this page you'll know how to take *any* symptom in *any* signal and follow the same `batch_id` to all the others.

## Set up two browser tabs

- **Tab 1**: Grafana → Explore → Loki, with `{service_name="etl"}` running.
- **Tab 2**: Grafana → Explore → Tempo, with Search filter `Service Name = etl-driver`.

If you don't have recent traffic, fire some epochs:

```bash
docker exec workspace producer start
docker exec workspace spark batch start
sleep 30  # let a few epochs complete
```

## Direction 1 — Loki → Tempo (the derived field)

In Tab 1 (Loki), find a log line containing `batch_id=...`. The streaming daemon emits several per epoch: "epoch start", "epoch done", "streaming progress", and WARNs like "dropped … records missing product_id".

Expand the row. At the bottom you see a **batch_id** field with a value like `e-42` and a button: **View traces for batch**.

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

Grafana scans every rendered log line against the regex. When it matches, it extracts the capture group and renders a button that opens an internal link to the Tempo datasource, passing the captured value. Tempo offers a TraceQL search fallback: `{ .batch_id = "e-..." }` succeeds and returns our `etl_batch` span.

Click the button. Tab 2 splits to show the matching trace. **Two clicks** from "a log line says something happened" to "here's the trace of that epoch".

## Direction 2 — Tempo → Loki (`tracesToLogsV2`)

In Tab 2, open the same `etl_batch` span. Top-right of the span detail panel: **Logs for this span** button.

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
  customQuery: true
  query: '{service_name=~".+"} | batch_id=`${__tags.batch_id}`'
```

Grafana extracts the `batch_id` attribute from the open span, substitutes it into the query template, and opens Loki with:

```logql
{service_name=~".+"} | batch_id=`e-...`
```

This filters to that exact epoch's log lines, regardless of `service_name`. You see "epoch start" → intermediate INFOs → "epoch done" → "streaming progress", in time order. **One click** from "trace shows what happened" to "here's every log line for it".

## Why `batch_id` and not `trace_id`

In a simple Python service, `trace_id` works perfectly as the cross-signal pivot — log lines emitted inside a span are tagged with the span's `trace_id` by `LoggingInstrumentor`. In our pipeline it doesn't, for the reason [*Traces concepts*](01-traces-concepts.md) covered: the `etl_batch` Python span and the Spark JVM spans live in different processes with different `trace_id`s by definition.

`batch_id`, in contrast, is a single value we control. We attach it to every Python log line, to the Python span, and to Postgres rows. It's the **business identifier** that survives every process boundary.

The production lesson: define one or two **business-level identifiers** (batch_id, job_run_id, deployment_version) and attach them to every signal everywhere. `trace_id` is great for HTTP request flows; for batch ETL, business identifiers are king.

## TraceQL — four queries you'll use

Open Explore → Tempo → query type **TraceQL**.

```traceql
# All spans tagged with any batch_id
{ .batch_id != "" }

# Slow epochs
{ resource.service.name = "etl-driver" && duration > 10s }

# Failed epochs (status set to ERROR in our Python code on exception)
{ resource.service.name = "etl-driver" && status = error }

# Specific epoch
{ .batch_id = "e-42" }
```

With these, "show me the 10 slowest epochs today" is one query, not a complex log-derived aggregation.

## A note on the Spark-internal trace tree

The Java agent's spot SparkListener emits an `application` → `job-NNNN` → stage span tree on every Spark job. It's `service.name=spark-driver` in Tempo Search. It has Spark-internal attributes (stageIds, spark.job.time) but **does not carry `batch_id`** — that's why our pivot uses the `etl_batch` span instead. For Scenario C-style "did the cluster do something weird" investigations the Spark tree is useful; we don't pivot on it in the lab. See [*What we didn't show*](../06-failure-narratives/04-what-we-didnt-show.md) for the SparkListener-based observability patterns real teams use.

## The bigger pattern

The mechanism Grafana provides is general: any **derived field** (Loki side) or any **trace-to-logs config** (Tempo side) lets you link signals by *whatever string identifier you choose*. We picked `batch_id`. Production teams pick:

- `job_run_id` (orchestrator-level — Airflow / Dagster run IDs)
- `deployment_version` (which commit was this from)
- `tenant_id` (multi-tenant pipelines)
- `dataset_id` (especially with column-level lineage)

Pick the identifiers that match how you think about *your* failures. Tag everything with them. The wow moment is then mechanical.

Section 6 puts all three pillars to work: three real failures, walked as narratives.
