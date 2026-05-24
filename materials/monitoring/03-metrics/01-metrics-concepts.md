# Metrics — Concepts

Metrics are numeric values, sampled at regular intervals, indexed by a set of labels. They answer questions of the form "what does this number look like over time, broken down by these dimensions?"

This sounds simple. It is. The trick is that almost every operational question — "is the system healthy", "is throughput dropping", "are tail latencies climbing" — can be expressed as a query against metrics. That's why metrics are the bedrock signal of observability.

## The three (and a half) metric types

Almost every metrics system uses these primitives. Names vary slightly; semantics don't.

**Counter** — monotonically increasing. Number of events that have happened since the process started. `kafka_consumer_records_consumed_total`. You almost never look at the raw value; you look at `rate(counter[1m])` — the per-second rate of increase. A counter reset (process restart) shows up as a sudden drop and is handled automatically by `rate()` / `increase()`.

**Gauge** — value that can go up or down. Current heap usage, current queue depth, current number of live executors. `jvm_memory_used_bytes`. You read it directly; `rate()` of a gauge is nonsense.

**Histogram** — distribution of observations bucketed into ranges. The classic use is request durations: how many requests took 0–10ms, 10–100ms, 100ms–1s. Lets you compute percentiles (`histogram_quantile(0.99, ...)`). The cost is cardinality: each bucket is its own time series. Pre-2025 Prometheus histograms are very heavy; the newer *native histograms* fix this, but most ecosystems are still on classic.

**Summary** — like a histogram but computes percentiles *client-side* per process. Can't be aggregated across instances. Less useful than histograms; mostly legacy.

For the lab we'll use mostly counters (consumer records, postgres operations, commits) and gauges (heap, executor count, lag).

## Cardinality — the only metric-side concept that can ruin your day

A time series is defined by its **set of label key/value pairs**. `kafka_consumer_records_lag{topic="clicks",partition="3",client_id="..."}` is one series. Change any label value and it's a different series.

Series count = product of distinct values across all labels. If you have:

- 20 services × 5 endpoints × 10 status codes × 1000 customer_ids = **1,000,000 time series for one metric**.

A million series is enough to crash a modest Prometheus. The cardinality bombs are almost always:

- **User IDs / session IDs / request IDs** as labels. NEVER do this.
- **High-resolution timestamps** as labels. Same.
- **URL paths with embedded IDs**, like `/users/42/orders/9117`. Strip the IDs before tagging.
- **Free-text fields** (error messages, user agents). Use logs for these.

Rule of thumb: any label value should come from a fixed-size enumeration (status codes, HTTP methods, service names, partition numbers). When you're tempted to add a high-cardinality label, you're really reaching for logs or traces, not metrics.

In this lab, `batch_id` is a perfect example of what *not* to put on a metric — every batch is a new value, unbounded growth over time. We use `batch_id` only in logs and traces.

## Scrape vs push (the OTel collector adjudicates)

Two opposing collection models:

**Pull / scrape**: the storage backend periodically hits an HTTP endpoint exposed by the application or by a sidecar and reads the current state. This is Prometheus's native model. Good for: long-lived services with stable endpoints. Bad for: short-lived jobs, things behind NAT.

**Push**: the application sends metrics to a collector or backend at intervals. OTLP-push, statsd, CloudWatch. Good for: short-lived jobs, batched workloads, mobile clients. Bad for: lossy networks, slow collectors (backpressure).

OpenTelemetry's design is **push from the SDK or agent → push to the collector → Collector adapts**. The collector exposes a Prometheus-scrape endpoint on its `prometheus` exporter — Prometheus then *pulls* from the collector. You get push semantics from your workload and pull semantics for Prometheus, with the collector absorbing the impedance mismatch.

In our lab:

```
   Spark JVMs ──OTLP push──→ OTel Collector ──Prometheus scrape──→ Prometheus
   (agent)
```

## OTLP vs Prometheus exposition format

Both are wire formats for metrics. OTLP is gRPC- or HTTP/protobuf-based and the OpenTelemetry-native format. Prometheus exposition is plain text over HTTP, looking like:

```
# HELP kafka_consumer_records_lag ...
# TYPE kafka_consumer_records_lag gauge
kafka_consumer_records_lag{topic="clicks",partition="0"} 1234
kafka_consumer_records_lag{topic="clicks",partition="1"} 8732
```

Prometheus scrapes the latter. The OTel Collector translates OTLP-in → Prometheus-format-out via its `prometheus` exporter, which exposes the result at `:8889/metrics`. That's the URL Prometheus is configured to scrape in `config/prometheus.yaml`.

You usually don't care about the format choice. You care that:

- Counters in OTLP get the `_total` suffix added when exposed as Prometheus (Prometheus convention).
- Resource attributes from OTel become Prometheus labels via the `resource_to_telemetry_conversion` setting on the exporter. That's how `service.name=spark-driver` ends up as a Prom label.

## What our metrics pipeline gives us, concretely

Without writing a line of metrics code, the agent on the Spark JVMs gives us:

- `jvm_memory_used_bytes{jvm_memory_type=heap,service_name=spark-driver,...}` — heap usage by JVM
- `jvm_gc_duration_seconds_*` — GC pause distributions
- `jvm_cpu_recent_utilization_ratio` — process CPU
- `kafka_consumer_records_lag*`, `kafka_consumer_records_consumed_total` — auto-instrumented Kafka client
- `kafka_consumer_fetch_latency_*` — fetch RTT

The collector's pull-mode receivers give us:

- `kafka_brokers`, `kafka_topic_partitions`, `kafka_partition_current_offset_ratio` — from the kafkametrics receiver (Kafka admin protocol)
- `postgresql_commits_total`, `postgresql_rollbacks_total`, `postgresql_rows{state=live}`, `postgresql_operations_total` — from the postgresql receiver (`pg_stat_*` views)

That's enough metrics to investigate any infrastructure-level issue without writing a single `metric.inc()`. The next page walks through how the OTel collector ties this together.
