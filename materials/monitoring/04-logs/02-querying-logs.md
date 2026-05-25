# Querying Logs in Grafana

Open **Explore → Loki**. The query bar accepts LogQL — Loki's query language. LogQL is intentionally PromQL-flavored, so a lot translates.

## Anatomy of a LogQL query

```logql
{service_name="etl", level="WARNING"} |= "dropped" | batch_id = "e-42"
```

Three sections, evaluated left-to-right:

1. **Label selector** — `{service_name="etl"}` chooses the streams. Always required. Always cheap.
2. **Line filters** — `|=` (contains), `!=` (not contains), `|~` (regex), `!~` (regex not match). Scans the selected streams' lines. Cost ∝ data scanned.
3. **Pipeline expressions** — `| json`, `| logfmt`, `| <field> = "..."`. Extract structured fields and filter by them.

The first stage is the only one that's index-served. **Always start with a label selector tight enough to limit scope** before adding content filters.

## The five queries you'll actually use

### 1. All ETL logs

```logql
{service_name="etl"}
```

Default sort is newest-first; the most recent epoch's lines appear at top.

### 2. Only warnings/errors

```logql
{service_name="etl"} | level=~"WARNING|ERROR"
```

`level` is structured metadata, so we filter via `|` pipe. The structured-metadata filter syntax uses `=` not `==`. Regex match with `=~`, regex not-match with `!~`.

### 3. A specific epoch's log lines

```logql
{service_name="etl"} | batch_id = "e-42"
```

The "I have a `batch_id`, show me everything that happened in that epoch" query. Use constantly.

### 4. Bad records

```logql
{service_name="etl"} |= "dropped" |= "missing product_id"
```

Two `|=` line filters chained — both must match. Used on the ETL Business dashboard's WARN panel.

### 5. Rate of failed epochs (LogQL metric query)

```logql
sum(rate({service_name="etl"} |= "epoch failed" [5m]))
```

LogQL can do arithmetic over log line counts — exactly the way PromQL handles counters. Useful for alerts: "alert if epochs are failing faster than 1 per 10 minutes".

## Live tail

In Explore → Loki, top-right has a **Live** button. New lines appear as they're ingested. The killer feature for "trigger the scenario in one terminal, watch the logs appear in the other". Use it when you run Scenario A in section 6.

Live tail uses Loki's tail websocket; works for any LogQL query. Limited to ~1000 most recent lines.

## Structured metadata vs labels — practical implications

When you click a log row in Explore, you see two tables:

- **Labels** — the stream identifiers. `service_name`, `service_instance_id`. Few, low-cardinality.
- **Structured metadata / Detected fields** — `batch_id`, `level`, `logger`, `log_file_name`, etc.

Click any **value** in either to add a filter. `batch_id` next to a value of `e-42` → click → query becomes `{service_name="etl"} | batch_id = "e-42"`. Simplest cross-epoch investigation pattern: scroll the feed, find an interesting epoch, click its `batch_id`, narrow.

## The derived field — Loki → Tempo, in one click

Every log line emitted by our ETL daemon contains the substring `batch_id=e-N`. The Loki datasource has a **derived field** configured that renders a button next to the matched text:

```yaml
derivedFields:
  - name: batch_id
    matcherRegex: 'batch_id=([A-Za-z0-9\-]+)'
    datasourceUid: tempo
    urlDisplayLabel: 'View traces for batch'
```

Try it:

1. Query `{service_name="etl"} |= "epoch done"`.
2. Expand any result row.
3. At the bottom you see `batch_id: e-...` with a button **View traces for batch**.
4. Click → Tempo opens with the matching `etl_batch` span.

This is the cross-signal correlation pivot. The full mechanism in both directions is in section 5.

## When LogQL is the wrong tool

LogQL is great for "show me events matching X". It's bad at:

- **Joins between log streams** — can't easily ask "show me ETL batches that happened while a Spark executor was missing".
- **Per-record latency / duration** — `rate()` of a phrase works, but extracting durations from log lines requires parsing and unwrap operations.
- **Aggregations across long windows** — Loki performs okay at 1-hour aggregations but degrades at 7-day spans.

The next signal — traces — covers per-record-duration natively.
