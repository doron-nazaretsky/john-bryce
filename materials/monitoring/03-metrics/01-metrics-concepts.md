# Metrics — Concepts

Metrics are numeric values, sampled at regular intervals, indexed by a set of labels. They answer questions of the form "what does this number look like over time, broken down by these dimensions?"

Almost every operational question — "is the system healthy", "is throughput dropping", "are tail latencies climbing" — can be expressed as a query against metrics. That's why metrics are the bedrock signal of observability.

## The three (and a half) metric types

Almost every metrics system uses these primitives. Names vary slightly; semantics don't.

**Counter** — monotonically increasing. Number of events that have happened since the process started. `kafka_consumer_records_consumed_total`. You almost never look at the raw value; you look at `rate(counter[1m])` — the per-second rate of increase. A counter reset (process restart) shows up as a sudden drop and is handled automatically by `rate()` / `increase()`.

**Gauge** — value that can go up or down. Current heap usage, current queue depth, current number of live executors. `jvm_memory_used_bytes`. You read it directly; `rate()` of a gauge is nonsense.

**Histogram** — distribution of observations bucketed into ranges. The classic use is request durations: how many requests took 0–10ms, 10–100ms, 100ms–1s. Lets you compute percentiles (`histogram_quantile(0.99, ...)`). The cost is cardinality: each bucket is its own time series. Pre-2025 Prometheus histograms are heavy; the newer *native histograms* fix this, but most ecosystems are still on classic.

**Summary** — like a histogram but computes percentiles *client-side* per process. Can't be aggregated across instances. Less useful than histograms; mostly legacy.

For the lab we use mostly counters (consumer records, postgres operations, commits) and gauges (heap, executor count, lag).

## Cardinality — the only metric-side concept that can ruin your day

A time series is defined by its **set of label key/value pairs**. `kafka_consumer_records_lag{topic="clicks",partition="3",client_id="..."}` is one series. Change any label value and it's a different series.

Series count = product of distinct values across all labels. If you have:

- 20 services × 5 endpoints × 10 status codes × 1000 customer_ids = **1,000,000 time series for one metric**.

A million series is enough to crash a modest Prometheus. The cardinality bombs are almost always:

- **User IDs / session IDs / request IDs** as labels. Never.
- **High-resolution timestamps** as labels. Same.
- **URL paths with embedded IDs** (`/users/42/orders/9117`). Strip the IDs before tagging.
- **Free-text fields** (error messages, user agents). Use logs for these.

Rule of thumb: any label value should come from a fixed-size enumeration (status codes, HTTP methods, service names, partition numbers). When you're tempted to add a high-cardinality label, you're reaching for logs or traces, not metrics.

In this lab, `batch_id` is a perfect example of what *not* to put on a metric — every epoch is a new value, unbounded growth over time. `batch_id` lives in logs and traces only.

## Scrape vs push — the OTel Collector adjudicates

Two opposing collection models:

**Pull / scrape**: the storage backend periodically hits an HTTP endpoint exposed by the application or sidecar and reads the current state. This is Prometheus's native model. Good for long-lived services with stable endpoints. Bad for short-lived jobs, things behind NAT.

**Push**: the application sends metrics to a collector or backend at intervals. OTLP-push, statsd, CloudWatch. Good for short-lived jobs, batched workloads. Bad for lossy networks.

OpenTelemetry's design is **push from the SDK or agent → push to the collector → collector adapts**. The collector exposes a Prometheus-scrape endpoint; Prometheus pulls from it. You get push semantics from your workload and pull semantics for Prometheus, with the collector absorbing the impedance mismatch.

In our lab:

```
   Spark JVMs ──OTLP push──→ OTel Collector ──Prometheus scrape──→ Prometheus
   (Java agent)
```

## OTLP vs Prometheus exposition format

Both are wire formats. OTLP is gRPC- or HTTP/protobuf-based and OpenTelemetry-native. Prometheus exposition is plain text over HTTP:

```
# HELP kafka_consumer_records_lag ...
# TYPE kafka_consumer_records_lag gauge
kafka_consumer_records_lag{topic="clicks",partition="0"} 1234
```

Prometheus scrapes the latter. The OTel Collector translates OTLP-in → Prometheus-format-out via its `prometheus` exporter. Things to remember about the translation:

- Counters get the `_total` suffix added (Prometheus convention).
- Resource attributes from OTel become Prometheus labels via `resource_to_telemetry_conversion`. That's how `service.name=spark-driver` ends up as a Prom label.

## In our lab — where the metrics come from

Three sources feed the collector (see [*The four pillars and our stack*](../01-foundations/02-pillars-and-stack.md) for the full topology):

- **OTel Java agent** on every Spark JVM — JVM heap/GC/CPU, Kafka client lag and fetch latency, JDBC spans, etc. Pushed over OTLP every 15 seconds.
- **`kafkametrics` receiver** in the collector — speaks the Kafka admin protocol, scrapes brokers every 30 seconds. Gives us `kafka_brokers`, `kafka_topic_partitions`, `kafka_partition_current_offset_ratio`.
- **`postgresql` receiver** in the collector — reads `pg_stat_*` views every 30 seconds. Gives us `postgresql_commits_total`, `postgresql_operations_total{operation=ins|upd|del}`, `postgresql_db_size_bytes`, etc.

The collector pipeline then exposes all of these at `:8889/metrics`, and Prometheus is configured with exactly one scrape target — the collector. **Prometheus does not talk to Kafka, Postgres, or Spark directly.** That's the central principle of using a collector: only one thing knows about your storage backend.

Quick sanity:

```bash
curl -s 'http://localhost:9090/api/v1/label/__name__/values' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d["data"]))'
```

You'll see ~400 metric names. Enough to investigate any infrastructure-level issue without writing a single `metric.inc()`.

Next: how to read these metrics in the four dashboards we shipped.
