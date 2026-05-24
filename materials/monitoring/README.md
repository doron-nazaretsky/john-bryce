# Monitoring and Observability

A pipeline that runs is not a pipeline that works. This module teaches you how to **operate** a data pipeline, not just build one: how to know what it's doing in production, how to find out why it broke, and how to answer "is something wrong right now?" without guessing.

We use a small but realistic ETL — Kafka clicks → PySpark batch → Postgres upsert — wired to a complete observability stack (OpenTelemetry, Prometheus, Loki, Tempo, Grafana). You'll trigger three "interesting moments" and watch the symptoms appear simultaneously across metrics, logs, and traces.

## Prerequisites

- The [Spark batch ETL project](../projects/spark-etl/) — you should be comfortable with `spark-submit`, drivers/executors, and Kafka producers/consumers.
- **Docker Desktop with at least 8 GB of RAM** — the lab spins up 12 containers. The default 4 GB will OOM-kill services silently.
- A modern browser open to localhost ports (3001 Grafana, 8888 Jupyter, 3000 MyST docs).

## Learning Path

| Section | Topic | Duration |
|---|---|---|
| **01 - Introduction** | Why observability, the four pillars, our stack | ~45 min |
| **02 - Lab Tour** | Bring up the stack, orient yourself in Grafana, what the ETL does | ~30 min |
| **03 - Metrics** | Concepts, the metrics pipeline, reading dashboards, **Scenario A** | ~40 min |
| **04 - Logs** | Concepts, the logs pipeline, LogQL in Grafana, **Scenario B pt1** | ~30 min |
| **05 - Traces** | Concepts, the traces pipeline, cross-signal correlation, **Scenario B pt2** | ~30 min |
| **06 - Putting It Together** | **Scenario C** (worker kill), production patterns | ~30 min |
| **07 - Verification** | Instructor checklist run before each session (not student-facing) | n/a |
| **08 - Exercises** | Optional homework — add a log line, a manual span, a custom panel | ~30 min |

**Total: ~3.5 hours teaching + 0.5 hours exercises = 4 hours.**

## The Stack At A Glance

| Pillar | Tool | What it gives you |
|---|---|---|
| Instrumentation | OpenTelemetry Java agent + Python SDK | Zero-code spans on the JVM, one deliberate manual span in Python |
| Collection | OTel Collector (contrib) | One pipeline, three signals: receivers → processors → exporters |
| Metrics store | Prometheus | Numeric time series |
| Logs store | Loki | Label-indexed log streams (LogQL) |
| Traces store | Tempo | Span trees (TraceQL) |
| Visualization | Grafana | Dashboards + Explore + cross-signal correlation |

## The Three Scenarios

We trigger pre-built failures and watch them ripple through the dashboards:

- **A — Producer spike** (`producer rate 5x`): Kafka lag climbs, batch durations grow, write rate rises. Lands in the Metrics section.
- **B — Bad data** (`producer inject-bad 100`): a WARN line in Loki, dropped-records count in the ETL business dashboard, pivot from a log line to its trace via `batch_id`. Lands across Logs and Traces.
- **C — Worker dies** (`docker kill spark-worker-1`): executor count drops, batch duration spikes, all three signals tell the same story. Lands in Putting It Together.

## Important Convention — `batch_id`

Every ETL batch generates a unique `batch_id` (`b-20260520-173904-1c7cb6`). It shows up on:

- **Every log line** emitted by the ETL (Loki structured metadata field)
- **The manual `etl_batch` span** in Tempo (span attribute)
- **The Spark UI job description** (driver-side)

`batch_id` is the universal pivot for cross-signal investigation. When you find a problem in one signal, you can find the same batch in every other signal.

## Honest Framing — Trace Fragmentation

Spark serializes tasks across JVM boundaries, and OpenTelemetry context does **not** survive that boundary. This means our pipeline produces **two separate trace trees per batch**:

- `etl-driver / etl_batch` — one Python span per batch, carrying `batch_id`.
- `spark-driver / job-NNNN` — the auto-instrumented Spark internals (jobs, stages, executors).

They're not parent/child. That's the production reality of distributed compute, not a bug in our setup. The way real teams reconnect them is exactly what we do here: a shared attribute like `batch_id`. This is taught explicitly, not papered over.

## Out of Scope (V2 candidates)

- **OpenLineage** — column-level lineage is a complementary layer to tracing. We discuss it in [Production Patterns](06-putting-it-together/02-production-patterns.md) and decide after V1 whether to add it.
- **Distributed/HA mode** for Loki / Tempo / Prometheus — single-binary here, real prod uses microservices.
- **Sampling, exemplars, profiling (Pyroscope), real alerting** — mentioned in production patterns, not implemented.
- **Spark UI / History Server** — we funnel everything through OTel for the unified-stack story.
