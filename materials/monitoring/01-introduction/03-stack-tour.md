# Our Stack — A Concrete Tour

Now we name each box in the four-pillars diagram. Everything below is what runs when you type `make lab-monitoring`.

## The 12 containers

| # | Container | Role | Pillar |
|---|---|---|---|
| 1 | `workspace` | Your shell + MyST docs + Jupyter + CLIs (`producer`, `spark`) | client |
| 2 | `kafka-1`, `kafka-2` | 2-broker KRaft cluster, topic `clicks` (4 partitions, RF=2) | source |
| 3 | `spark-master` | Spark master + the long-running ETL daemon (driver) | compute |
| 4 | `spark-worker-1`, `spark-worker-2` | Spark executors | compute |
| 5 | `postgres` | Sink — table `aggregated_clicks (product_id, minute_window, click_count, …)` | sink |
| 6 | `otel-collector` | Single central collector, contrib distribution | pillar 2 |
| 7 | `prometheus` | Metrics TSDB (6h retention) | pillar 3 |
| 8 | `loki` | Logs (single-binary, filesystem) | pillar 3 |
| 9 | `tempo` | Traces (single-binary, filesystem) | pillar 3 |
| 10 | `grafana` | Visualization (anonymous role = Admin for the lab) | pillar 4 |

## How signals flow

```{mermaid}
flowchart LR
    ETL["ETL daemon (Python)<br/>manual etl_batch span"]
    SPARK["Spark JVMs (driver + executors)<br/>OTel Java agent:<br/>job/stage spans, JVM metrics,<br/>JDBC, Kafka"]
    KAFKA["Kafka brokers<br/>(admin API)"]
    PG["Postgres<br/>(pg_stat_*)"]
    COL["OTel Collector"]
    TEMPO[(Tempo)]
    LOKI[(Loki)]
    PROM[(Prometheus)]

    ETL -- "OTLP HTTP" --> COL
    SPARK -- "OTLP" --> COL
    SPARK -- "batch logs<br/>(filelog receiver)" --> COL
    KAFKA -- "kafkametrics scrape" --> COL
    PG -- "postgresql scrape" --> COL

    COL --> TEMPO
    COL --> LOKI
    COL --> PROM
```

Every arrow is one of: an OTLP push from a JVM agent, a scrape pull by the collector, or a file-tail by the collector. The collector is the only thing that talks to the storage backends.

## What each backend is good at

**Prometheus** — a time-series database built for numeric metrics with labels. It pulls (scrapes) from endpoints rather than receiving pushes, so the OTel Collector exposes a scrape endpoint and Prometheus reads from it. Queried with PromQL: rates, aggregations, alerting rules.

**Loki** — a log store that indexes only a small set of **labels** (e.g. `service_name=etl`), not the log content. That makes it cheap to keep long retention on modest disks. Querying log content is a scan over the matching label streams (LogQL `|=` and `|~`). Loki 3.x also supports **structured metadata** fields like `batch_id`, queryable as `{service_name="etl"} | batch_id="..."` without exploding label cardinality.

**Tempo** — a trace store with minimal indexing. Best at "show me this exact request": look up directly by `trace_id`, or run TraceQL searches like `{ .batch_id != "" }` over recent spans. Per-trace investigation is fast and cheap.

**Grafana** — the visualization layer: dashboards, Explore (ad-hoc queries), and the cross-signal correlation we'll set up in Section 5. We deliberately give it admin-equivalent anonymous access for the lab — no one wants to type a password during a demo.

## The OpenTelemetry pieces — naming gets confusing

The OpenTelemetry project ships several distinct things and people conflate them constantly:

- **OTel API / SDK** — language libraries (Java, Python, Go, …) for creating signals from your code. The SDK is what your application links against.
- **OTel auto-instrumentation agents** — drop-in agents that bytecode-rewrite known libraries. `opentelemetry-javaagent.jar` for JVM, `opentelemetry-instrument` for Python, etc.
- **OTel Collector** — a separate daemon written in Go. Receives signals, transforms, exports.
- **OTLP (the protocol)** — the wire format. gRPC on :4317 or HTTP/protobuf on :4318. All of the above speak it.

Our pipeline uses **the agent on the Spark JVM** (zero-code, gives us job/stage spans + JVM metrics + Kafka/JDBC instrumentation), **the SDK in Python** (one deliberate `etl_batch` span carrying `batch_id`), and **the collector** in the middle.

Don't confuse the OTel SDK with the OTel Collector. The SDK runs *inside* your app; the Collector is a sidecar. They both speak OTLP — that's how they're connected.

## A useful tool table

| Tool | What you'll use it for in this module |
|---|---|
| `producer rate <mult>` | Multiplies the Kafka click producer's rate. Used in Scenario A. |
| `producer inject-bad <n>` | One-shot: emit N malformed records (no `product_id`). Used in Scenario B. |
| `spark batch start \| stop \| status` | Control the long-running ETL daemon inside spark-master. |
| `docker kill spark-worker-1` | Used in Scenario C. |
| Grafana http://localhost:3001 | Dashboards (5), Explore, correlation jumps. |
| Prometheus http://localhost:9090 | Direct PromQL when you want to verify the source of truth. |

That's the stack. Next we bring it up.
