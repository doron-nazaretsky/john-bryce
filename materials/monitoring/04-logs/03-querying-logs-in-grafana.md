# Querying Logs in Grafana

Open **Explore → Loki**. The query bar accepts LogQL — Loki's query language. LogQL is intentionally PromQL-flavored, so a lot translates.

## Anatomy of a LogQL query

```logql
{service_name="etl", level="WARNING"} |= "dropped" | batch_id = "b-20260520-173904-1c7cb6"
```

Three sections, evaluated left-to-right:

1. **Label selector** — `{service_name="etl"}` chooses the streams. Always required. Always cheap.
2. **Line filters** — `|=` (contains), `!=` (not contains), `|~` (regex match), `!~` (regex not match). Scans the selected streams' lines. Cost ∝ data scanned.
3. **Pipeline expressions** — `| json`, `| logfmt`, `| <field> = "..."`. Extract structured fields and filter by them.

The order matters because the first stage is the only one that's index-served. **Always start with a label selector tight enough to limit scope** before adding content filters.

## The five queries you'll actually use

### 1. All ETL logs

```logql
{service_name="etl"}
```

Default sort is newest-first; the most recent batch's lines appear at top.

### 2. Only warnings/errors

```logql
{service_name="etl"} | level=~"WARNING|ERROR"
```

`level` is structured metadata, so we filter via `|` pipe. Note: the structured metadata filter syntax uses `=` not `==`. Regex match with `=~`, regex not-match with `!~`.

### 3. A specific batch's log lines

```logql
{service_name="etl"} | batch_id = "b-20260520-173904-1c7cb6"
```

This is the "I have a `batch_id`, show me everything that happened in that batch" query. Use it constantly.

### 4. Bad records

```logql
{service_name="etl"} |= "dropped" |= "missing product_id"
```

Two `|=` line filters chained — both must match. We use this on the ETL Business dashboard's WARN panel.

### 5. Rate of failed batches (LogQL metric query)

```logql
sum(rate({service_name="etl"} |= "batch failed" [5m]))
```

LogQL can do arithmetic over log line counts — exactly the way PromQL handles counters. `rate(... [5m])` gives lines-per-second matched. Useful for alerts: "alert if batches are failing faster than 1 per 10 minutes".

## Live tail

In Explore → Loki, top-right has a **Live** button. Clicking it switches to streaming mode — new lines appear as they're ingested, the panel scrolls. Killer feature for "trigger the scenario in one terminal, watch the logs appear in the other".

Live tail uses Loki's tail websocket; works for any LogQL query. Limited to ~1000 most recent lines.

## Structured metadata vs labels — practical implications

When you click a log row in Explore, you see two tables:

- **Labels** — the stream identifiers. `service_name`, `service_instance_id`. Few, low-cardinality.
- **Structured metadata / Detected fields** — `batch_id`, `level`, `logger`, `log_file_name`, etc.

You can click any **value** in either to add a filter to the current query. `batch_id` next to a value of `b-...` → click → query becomes `{service_name="etl"} | batch_id = "b-..."`.

This is the simplest cross-batch investigation pattern: scroll the log feed, find an interesting batch, click its `batch_id`, narrow.

## The derived field — Loki → Tempo

In `datasources.yaml`, the Loki datasource has a derived field configured:

```yaml
derivedFields:
  - name: batch_id
    matcherRegex: 'batch_id=([A-Za-z0-9\-]+)'
    datasourceUid: tempo
    url: '${__value.raw}'
    urlDisplayLabel: 'View traces for batch'
    internalLink: true
```

Every time Grafana renders a log row, it runs this regex against the line content. When it matches (any line containing `batch_id=b-...`), it adds a button **"View traces for batch"** to the row. Clicking it opens Tempo with a TraceQL query for that batch_id.

Try it now:

1. Query `{service_name="etl"} |= "batch done"`.
2. Expand any result row.
3. Look at the bottom of the row — you should see `batch_id: b-...` with a button **"View traces for batch"** next to it.
4. Click → splits to Tempo on the right, showing the `etl_batch` span with that batch_id.

This is the wow moment of cross-signal correlation. We'll work it both ways in section 5.

## When LogQL is the wrong tool

LogQL is great for "show me events matching X". It's bad at:

- **Joins between log streams** — can't easily ask "show me ETL batches that happened while a Spark executor was missing".
- **Per-record latency / duration** — you can compute `rate()` of a phrase, but you can't easily extract durations from log lines unless you parse and unwrap, which is awkward.
- **Aggregations across long windows** — Loki performs okay at 1-hour LogQL aggregations but degrades at 7-day spans. For those, derive the data into Prometheus or push to an analytics warehouse.

The next pillar — traces — covers the per-record-duration case natively. That's section 5.

Now, scenario B part 1.
