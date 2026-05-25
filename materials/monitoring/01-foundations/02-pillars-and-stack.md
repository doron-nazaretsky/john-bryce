# The Four Pillars (and Our Stack)

Every observability stack — OpenTelemetry + Grafana, Datadog, New Relic, a homegrown ELK setup — does the same four things in the same order. The vendors and the wire formats change; the architecture doesn't. This page names each pillar in the abstract, then names the boxes in *our* stack concretely.

## The four pillars

```{mermaid}
flowchart LR
    P1["1 · Instrumentation<br/>(Generation)<br/><br/>produces signals<br/>from your code<br/>and runtime"]
    P2["2 · Collection<br/>(Ingestion)<br/><br/>receives, batches,<br/>transforms, fans out<br/>to backends"]
    P3["3 · Storage<br/>(Backends)<br/><br/>persists with<br/>indexes optimised<br/>per signal type"]
    P4["4 · Analytics<br/>(Visualization)<br/><br/>queries +<br/>dashboards +<br/>correlation"]
    P1 --> P2 --> P3 --> P4
```

If you can name where a tool sits in this picture, you can reason about its trade-offs and its failure modes.

### Pillar 1 — Instrumentation (signal generation)

Where signals are *born*. Three categories:

- **Manual**: you write `metric.inc()` or `tracer.start_span(...)` in your code. Expressive (any attribute you want), but expensive: every framework boundary needs a developer.
- **Automatic (zero-code)**: an agent — typically attached as a JVM `-javaagent` or a Python `instrument` wrapper — bytecode-rewrites known libraries (JDBC, Kafka client, HTTP frameworks) to emit signals without code changes. How 90% of production trace data gets generated.
- **Receiver-side (pull)**: the *collector* runs probes against the system itself — Postgres `pg_stat_*`, Kafka admin protocol, JMX endpoints. No code in the target system at all.

A real pipeline uses all three. The skill is knowing which to reach for: a manual span for the business-critical boundary, auto-instrumentation for the library noise, receiver-side for things you don't run (managed Kafka, managed Postgres).

### Pillar 2 — Collection (ingestion + transformation)

Signals from instrumentation are noisy, low-level, and not pointed at any particular backend. Between the workload and the storage layer sits a **collector** — a daemon whose job is to:

- **Receive** signals over whatever protocol the source emits (OTLP gRPC, OTLP HTTP, Prometheus scrape, file tail).
- **Process** them — batch for throughput, drop noisy attributes, enrich with environment tags, sample traces to control volume.
- **Export** to one or more storage backends, each in its native protocol.

The collector is the *only* thing your application talks to. This decoupling is the whole point: you can swap Prometheus for VictoriaMetrics, or Loki for Splunk, without touching application code.

The OpenTelemetry Collector is the dominant open-source implementation. It comes in two distributions: **core** (small, vendor-neutral) and **contrib** (everything else, including receivers like `kafkametrics`, `postgresql`, `filelog`). Our lab uses contrib — pick the wrong one and your collector silently fails to start.

### Pillar 3 — Storage backends

Different signal types need fundamentally different storage. You don't store JSON log lines the way you store time-series numbers.

| Signal | Storage shape | Why it matters |
|---|---|---|
| **Metrics** | Numeric value + label set, indexed by time. Compressed TSDB. | Cheap to keep at high cardinality across long windows. Slow when you need a single record. |
| **Logs** | Variable-length text, indexed by labels (not full text), grouped into streams. | Cheap to write at huge volume. Querying by content scans proportional to data — you live or die by your label design. |
| **Traces** | Span trees keyed by trace_id. Optimised for "show me this specific request". | Per-trace lookup is fast; aggregations across millions of traces are expensive. |

Our stack uses **Prometheus** (metrics), **Loki** (logs), and **Tempo** (traces). All three are designed to interoperate via Grafana — that alignment is what makes the cross-signal correlation in pillar 4 work cleanly. In production you often see specialised commercial variants (Mimir, Datadog metrics, Splunk, Honeycomb), but the *shape* of the data is the same.

### Pillar 4 — Analytics + Visualization

Where humans interact with the signals: dashboards, ad-hoc queries, alerts, and — the most important capability in modern observability — **cross-signal correlation**.

Three modes you'll use:

- **Dashboards** — curated, persistent views of pre-decided panels. The "monitoring" sense from the previous page.
- **Explore** — ad-hoc query of any datasource. The "observability" sense: ask a new question.
- **Correlation** — click a `batch_id` in a log line, land on the matching trace in Tempo. Open a span, jump to the logs from that batch. This is what turns three signals into one investigation.

Everything upstream is in service of making the fourth pillar fast.

## Our stack — concrete

```{mermaid}
flowchart LR
    SRC["Spark JVMs +<br/>Python ETL<br/>Kafka, Postgres<br/><br/><i>Pillar 1 · instrumentation</i>"]
    COL["OTel Collector<br/>(contrib)<br/><br/><i>Pillar 2 · collection</i>"]
    STORE[("Prometheus<br/>Loki<br/>Tempo<br/><br/><i>Pillar 3 · storage</i>")]
    GRAF["Grafana<br/><br/><i>Pillar 4 · analytics</i>"]
    SRC --> COL --> STORE
    STORE --> GRAF
```

## The 10 containers

When you run `make lab-monitoring`, this is what comes up.

| # | Container | Role | Pillar |
|---|---|---|---|
| 1 | `workspace` | Your shell + MyST docs + Jupyter + CLIs (`producer`, `spark`) | client |
| 2 | `kafka-1`, `kafka-2` | 2-broker KRaft cluster, topic `clicks` (4 partitions, RF=2) | source |
| 3 | `spark-master` | Spark master + long-running streaming ETL daemon (driver) | compute |
| 4 | `spark-worker-1`, `spark-worker-2` | Spark executors | compute |
| 5 | `postgres` | Sink — `aggregated_clicks (product_id, minute_window, click_count, …)` | sink |
| 6 | `otel-collector` | Single central collector, contrib distribution | pillar 2 |
| 7 | `prometheus` | Metrics TSDB (6h retention) | pillar 3 |
| 8 | `loki` | Logs (single-binary, filesystem) | pillar 3 |
| 9 | `tempo` | Traces (single-binary, filesystem) | pillar 3 |
| 10 | `grafana` | Visualization (anonymous role = Admin for the lab) | pillar 4 |

Every signal arrow is one of: an OTLP push from a JVM or Python SDK, a scrape pull by the collector, or a file tail by the collector. The collector is the only thing that talks to the storage backends — that's the central principle of using one.

## OTel naming, untangled

The OpenTelemetry project ships several distinct things, and people conflate them constantly:

- **OTel SDK / API** — language libraries (Java, Python, Go, …). Runs *inside* your application.
- **OTel auto-instrumentation agents** — drop-in agents that bytecode-rewrite known libraries (`opentelemetry-javaagent.jar` for JVM, `opentelemetry-instrument` for Python).
- **OTel Collector** — a separate daemon written in Go. Receives signals, transforms, exports. Runs as a sidecar.
- **OTLP** — the wire format. gRPC on `:4317`, HTTP/protobuf on `:4318`. All of the above speak it.

Our pipeline uses **the Java agent on the Spark JVMs** (zero-code; gives us job/stage spans, JVM metrics, Kafka/JDBC instrumentation), **the SDK in Python** (one deliberate `etl_batch` span carrying `batch_id`), and **the collector** in the middle.

The SDK runs *inside* your app; the Collector is a sidecar. They both speak OTLP — that's how they're connected.

Next: bringing the lab up.
