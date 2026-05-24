# The Four Pillars

Every observability stack — whether it's OpenTelemetry + Grafana, Datadog, New Relic, or a homegrown ELK setup — does the same four things in the same order. The vendors and the wire formats change; the architecture doesn't.

```
   1. Instrumentation       2. Collection         3. Storage         4. Analytics
   (Generation)             (Ingestion)           (Backends)         (Visualization)
   ─────────────────        ──────────────        ──────────────     ─────────────
   produces signals    →    receives, batches  →  persists with    → queries +
   from your code           transforms, fans       indexes optimised  dashboards +
   and runtime              out to backends        per signal type    correlation
```

If you can name where a tool sits in this picture, you can reason about its trade-offs and its failure modes.

## Pillar 1 — Instrumentation (signal generation)

This is where signals are *born*. Three categories:

- **Manual**: you write `metric.inc()` or `tracer.start_span(...)` in your code. Expressive (you can attach any attribute you want), but expensive: every framework boundary needs a developer to do it.
- **Automatic (zero-code)**: an agent — typically attached as a JVM `-javaagent` or a Python `instrument` wrapper — bytecode-rewrites known libraries (JDBC, Kafka client, gRPC, HTTP frameworks) to emit signals without code changes. This is how 90% of production trace data gets generated.
- **Receiver-side (a.k.a. pull)**: the *collector* runs probes against the system itself — Postgres `pg_stat_*`, Kafka admin protocol, JMX endpoints. No code in the target system at all.

A real pipeline uses all three. The skill is knowing which one to reach for: a manual span for the business-critical boundary, auto-instrumentation for the library noise, receiver-side for things you don't run (managed Kafka, managed Postgres).

## Pillar 2 — Collection (ingestion + transformation)

Signals from instrumentation are noisy, low-level, and not pointed at any particular backend. Between the workload and the storage layer sits a **collector** — a daemon whose job is to:

- **Receive** signals over whatever protocol the source emits (OTLP gRPC, OTLP HTTP, Prometheus scrape, syslog, plain TCP).
- **Process** them — batch for throughput, drop noisy attributes, enrich with environment tags, sample traces to control volume.
- **Export** to one or more storage backends, each in its native protocol.

The collector is the *only* thing your application talks to. This decoupling is the whole point: you can swap Prometheus for VictoriaMetrics, or Loki for Splunk, without touching a single line of application code. Add a new backend? Add an exporter.

The OpenTelemetry Collector is the dominant open-source implementation. It comes in two distributions: **core** (a small, vendor-neutral set of receivers/exporters) and **contrib** (everything else). Receivers like JMX, PostgreSQL, MySQL, Kafka admin, and the `filelog` receiver are contrib-only. **We use contrib because we need filelog + kafkametrics + postgresql receivers.** Pick wrong and your collector silently fails to start.

## Pillar 3 — Storage backends

Different signal types need fundamentally different storage. You don't store JSON log lines the way you store time-series numbers.

| Signal | Storage shape | Why it matters |
|---|---|---|
| **Metrics** | Numeric value + label set, indexed by time. Compressed time-series database. | Cheap to keep at high cardinality across long windows. Slow when you need a single record. |
| **Logs** | Variable-length text, indexed by labels (not full text), grouped into streams. | Cheap to write at huge volume. Querying by content (regex) costs proportional to data scanned — you live or die by your label design. |
| **Traces** | Span trees keyed by trace_id. Each span is small but trace lookups are random reads. | Optimised for "show me this specific request"; aggregations across millions of traces are expensive. |

Our stack uses **Prometheus** (metrics), **Loki** (logs), and **Tempo** (traces). Prometheus is a CNCF graduated project (originally from SoundCloud); Loki and Tempo are Grafana Labs open-source projects designed to interoperate with it. That alignment is *not* a coincidence — picking backends from the same ecosystem makes the cross-signal correlation (the wow moment in pillar 4) much smoother.

In production you often see specialised commercial variants — Mimir, Datadog metrics, Splunk, Honeycomb — but the *shape* of the data is the same.

## Pillar 4 — Analytics + Visualization

Storage by itself doesn't help anyone. The fourth pillar is where humans interact with the signals: dashboards, ad-hoc queries, alerts, and — the most important capability in modern observability — **cross-signal correlation**.

This is where Grafana earns its keep. Three modes you'll use:

- **Dashboards** — curated, persistent views of pre-decided panels. The "monitoring" sense from the previous lesson.
- **Explore** — ad-hoc query of any datasource. The "observability" sense: ask a new question.
- **Correlation** — click a `trace_id` in a log line, land on the matching trace in Tempo. Open a span, jump to the logs from that batch. This is the experience that turns three signals into one investigation.

When we say "the four pillars work together", what we really mean is: the whole stack exists to make the fourth pillar fast. Everything upstream is in service of giving the human investigator one tab to debug from.

## A picture of our stack

```
 ┌─────────────────┐   ┌──────────────────┐   ┌─────────────┐   ┌──────────┐
 │  Spark JVMs +   │   │                  │   │ Prometheus  │   │          │
 │  Python ETL     │──→│ OTel Collector   │──→│ Loki        │←──│ Grafana  │
 │  Kafka, PG      │   │ (contrib)        │   │ Tempo       │   │          │
 └─────────────────┘   └──────────────────┘   └─────────────┘   └──────────┘
       Pillar 1              Pillar 2             Pillar 3         Pillar 4
   instrumentation          collection            storage         analytics
```

In the next lesson we'll put concrete tool names on each box and walk through which of our 12 containers belongs where.
