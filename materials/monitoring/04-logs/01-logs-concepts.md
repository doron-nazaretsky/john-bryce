# Logs — Concepts

Logs are individual events, emitted at the time they happen, in a form a human can read. They are the oldest signal and the most expressive: anything that has happened in your code can in principle become a log line.

The trade-off is volume and cost. A million events per minute that each emit one INFO log = 60 million log lines an hour. Storing them, indexing them, and querying them is non-trivial. The way modern log systems make this work is by **indexing labels, not content**.

## Structured vs unstructured

```
# Unstructured (plain text)
2026-05-20 17:33:04 INFO Started batch processing for product P017

# Structured (JSON)
{"ts":"2026-05-20T17:33:04Z","level":"INFO","msg":"batch start",
 "batch_id":"b-20260520-173304-abc","product":"P017"}
```

The structured form looks uglier but is hugely more powerful: every field is queryable. Asking "which batches mentioned product P017" becomes a key lookup, not a regex over text. **Always emit structured logs in production**. The cost is trivial (one extra import + a custom formatter); the benefit is everything.

Our ETL daemon uses a custom JSON formatter (`_JsonLineFormatter` in `etl_daemon.py`). Every log line is one JSON object with `ts`, `level`, `logger`, `msg`, and `batch_id`.

## Log levels

The five-level scheme everyone has seen — but worth re-stating because most production noise comes from sloppy use:

- **DEBUG** — for developers; off in production.
- **INFO** — normal state-change events ("batch start", "upserted 320 rows"). Should describe what *just happened*, not announce it ahead of time.
- **WARN** — something is off but recoverable. The ETL drops 100 bad records → that's a WARN.
- **ERROR** — operation failed and the caller couldn't fix it. The batch crashed → ERROR.
- **FATAL/CRITICAL** — the process can't continue. Reserved.

The single biggest production logging sin: making everything INFO. If everything is INFO, nothing is interesting. The point of levels is to enable cheap visual scanning ("show me only WARN+ for the last hour").

## Why label-indexed storage matters (Loki)

Loki's design: index a small set of labels per log stream; **don't index the content**. The "stream" `{service_name="etl", level="INFO"}` is one logical bucket. To find a specific log line, Loki:

1. Looks up the stream by label match (cheap).
2. Scans the chunks of that stream for content matching your filter (cost proportional to scanned bytes).

The implications:

- **Few, low-cardinality labels** = cheap storage, fast queries. `service_name`, `level`, `lab` — all fine.
- **High-cardinality fields as labels** = explosion. `user_id`, `request_id`, `batch_id` — these would create one stream per value. Loki will accept it but performance crashes.
- **High-cardinality fields as structured metadata** (Loki 3.x feature) = the right balance. Stored per-line, queryable as `| field="..."`, no stream explosion.

In our lab, `service_name` is a stream label (5 distinct values: etl, spark-driver, spark-executor, spark-master, spark-worker). `batch_id` is a structured metadata field (unbounded values, but doesn't fragment streams). The collector's `filelog` operator pipeline is what makes that distinction.

This is the practical, modern way to do logs at scale. Splunk, Datadog, ELK each have their own variation but the cardinality lesson is universal.

## Log ↔ trace correlation

Two log lines emitted within the same span (= same logical operation) can be correlated if you include the trace_id and span_id in the log line.

OpenTelemetry's `LoggingInstrumentor` (Python) and equivalents in other languages do this automatically: hook the logging library so every log record gets the current trace_id/span_id attached. If your log lines have these, you can:

- See "all logs from this trace" — open a span in Tempo, jump to Loki filtered by trace_id.
- See "the trace this log line belongs to" — open a log line in Loki, click the trace_id to jump to Tempo.

**Important caveat for this lab**: our Python ETL emits **only one manual span** (`etl_batch`), and we don't enable `LoggingInstrumentor` (which would inject trace_id/span_id into every log record). The lab's cross-signal pivot is instead by `batch_id` — a *business identifier* — which is just as expressive and works across the JVM↔Python boundary where trace_id wouldn't.

That decision is honest and pedagogical: in real production you'd use BOTH (trace_id for per-request correlation, batch_id for per-batch correlation). Here we lean on `batch_id` because it works for the universal case.

## Don't reach for logs when you wanted metrics

This is the most common sin in DE observability. Engineers see a problem, default to grepping logs to count events ("how many WARNs in the last hour?"), and end up reinventing aggregation in shell pipelines.

If you're computing a number, you wanted a counter. If you're computing a distribution, you wanted a histogram. Logs are for *the specific event* — what happened to *this* record, *this* user, *this* batch.

The lab will reinforce this by example: Scenario A is metrics-led because it's about rates. Scenario B is logs-led because it's about *which records* got dropped.

Next: how the logs pipeline is wired.
