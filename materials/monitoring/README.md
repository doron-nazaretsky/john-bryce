# Monitoring and Observability

A pipeline that runs is not a pipeline that works. This module teaches you how to **operate** a data pipeline, not just build one: how to know what it's doing in production, how to find out why it broke, and how to answer "is something wrong right now?" without guessing.

We use a small but realistic ETL — Kafka clicks → PySpark Structured Streaming → Postgres upsert — wired to a complete observability stack (OpenTelemetry, Prometheus, Loki, Tempo, Grafana). You'll trigger three failures and watch the symptoms appear simultaneously across metrics, logs, and traces.

## Prerequisites

- The [Spark batch ETL project](../projects/spark-etl/) — comfortable with `spark-submit`, drivers/executors, and Kafka producers/consumers.
- **Docker Desktop with at least 8 GB of RAM** — the lab spins up 10 containers. The default 4 GB will silently OOM-kill services.
- A modern browser open to localhost ports (3001 Grafana, 8888 Jupyter, 3000 MyST docs).

## Learning path

| Section | Topic | Duration |
|---|---|---|
| **01 — Foundations** | Why observability, the four pillars, our concrete stack | ~30 min |
| **02 — Lab Tour** | Bring up the stack, the ETL we're observing, orienting yourself in Grafana | ~30 min |
| **03 — Metrics** | Concepts (counters, gauges, cardinality), reading the four metrics dashboards | ~30 min |
| **04 — Logs** | Concepts (structured logs, label-indexed storage), querying with LogQL | ~30 min |
| **05 — Traces** | Concepts (spans, fragmentation), cross-signal correlation via `batch_id` | ~30 min |
| **06 — Failure Narratives** | Three end-to-end investigations + what we didn't show | ~45 min |

**Total: ~3.5 hours.**

## A note on roles

In real companies a platform / SRE / DevOps team owns the stack itself — collector, Prometheus, Loki, Tempo, Grafana — and operates it for everyone. As a data engineer you'll *consume* it: instrument your pipeline, attach the right business identifiers, read the dashboards, follow the cross-signal pivots. This module spends a little time on how the stack is wired so the abstractions don't feel magical, but most of it is about operating an already-provisioned stack — the situation you'll actually be in.

Next: why observability is a different problem in data engineering than in a web backend.
