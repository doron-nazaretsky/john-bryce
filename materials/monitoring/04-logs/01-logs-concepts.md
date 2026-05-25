# Logs — Concepts

Before anything else: **don't reach for logs when you wanted metrics.** This is the single most common DE observability sin. Engineers see a problem, default to grepping logs to count events ("how many WARNs in the last hour?"), and end up reinventing aggregation in shell pipelines.

If you're computing a number, you wanted a counter. If you're computing a distribution, you wanted a histogram. Logs are for *the specific event* — what happened to *this* record, *this* user, *this* batch. Section 6 makes this concrete: Scenario A is metrics-led because it's about rates; Scenario B is logs-led because it's about *which records* got dropped.

With that out of the way:

## What logs actually are

Logs are individual events, emitted at the time they happen, in a form a human can read. They are the oldest signal and the most expressive: anything that has happened in your code can in principle become a log line.

The trade-off is volume and cost. A million events per minute that each emit one INFO log = 60 million log lines an hour. Storing them, indexing them, and querying them is non-trivial. The way modern log systems make this work is by **indexing labels, not content**.

## Structured vs unstructured

```
# Unstructured (plain text)
2026-05-20 17:33:04 INFO Started batch processing for product P017

# Structured (JSON)
{"ts":"2026-05-20T17:33:04Z","level":"INFO","msg":"epoch start",
 "batch_id":"e-42","product":"P017"}
```

The structured form looks uglier but is hugely more powerful: every field is queryable. Asking "which epochs mentioned product P017" becomes a key lookup, not a regex over text. **Always emit structured logs in production**. The cost is trivial (one import + a custom formatter); the benefit is everything.

Our ETL daemon uses a custom JSON formatter. Every log line is one JSON object with `ts`, `level`, `logger`, `msg`, and `batch_id`.

## Log levels

The five-level scheme everyone has seen — but worth re-stating because most production noise comes from sloppy use:

- **DEBUG** — for developers; off in production.
- **INFO** — normal state-change events ("epoch start", "upserted 320 rows"). Should describe what *just happened*, not announce it ahead of time.
- **WARN** — something is off but recoverable. The ETL drops 100 bad records → WARN.
- **ERROR** — operation failed and the caller couldn't fix it. The batch crashed → ERROR.
- **FATAL/CRITICAL** — the process can't continue. Reserved.

The single biggest production logging sin: making everything INFO. If everything is INFO, nothing is interesting. The point of levels is to enable cheap visual scanning ("show me only WARN+ for the last hour").

## Label-indexed storage (Loki)

Loki's design: index a small set of labels per log stream; **don't index the content**. The stream `{service_name="etl", level="INFO"}` is one logical bucket. To find a specific log line, Loki:

1. Looks up the stream by label match (cheap).
2. Scans the chunks of that stream for content matching your filter (cost proportional to scanned bytes).

The cardinality lesson from [*Metrics concepts*](../03-metrics/01-metrics-concepts.md) applies here too — `user_id`, `request_id`, `batch_id` as *labels* would create one stream per value and Loki performance crashes. The modern answer is **structured metadata** (Loki 3.x): stored per-line, queryable as `| field="..."`, no stream explosion.

In our lab, `service_name` is a stream label (5 distinct values: etl, spark-driver, spark-executor, spark-master, spark-worker). `batch_id` is a structured metadata field (unbounded values, but doesn't fragment streams).

This is the practical, modern way to do logs at scale. Splunk, Datadog, ELK each have their own variation but the cardinality lesson is universal.

## Log ↔ trace correlation, briefly

Two log lines emitted within the same span can be correlated if you include `trace_id` and `span_id` in the log line. OpenTelemetry's `LoggingInstrumentor` (Python) does this automatically.

**Important caveat for this lab**: our Python ETL emits only one manual span (`etl_batch`), and we don't enable `LoggingInstrumentor`. The cross-signal pivot is by **`batch_id`** — a *business identifier* — which is just as expressive and works across the JVM↔Python boundary where `trace_id` wouldn't. The full mechanism lives in section 5.

## In our lab — how a log line gets to Loki

The plumbing in ~50 words:

1. The Python ETL daemon writes JSON lines to `/var/log/etl/etl.log` via a custom formatter.
2. The OTel Collector's `filelog` receiver tails that file (shared volume `etl-logs` mounted into both `spark-master` and `otel-collector`). A `json_parser` operator hoists fields, a `move` operator promotes `batch_id` to a structured-metadata field.
3. The collector exports to Loki over OTLP-HTTP (`http://loki:3100/otlp`). Loki promotes `service_name` to a label and keeps everything else as structured metadata.

Spark JVM logs are *not* shipped to Loki — they're verbose at INFO and would 10× our log volume for little teaching value. Scenario C leans on metrics + traces instead.

Next: how to query this in Grafana.
