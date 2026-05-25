# What We Didn't Show

The lab is small on purpose. Real production observability adds capabilities we either skipped or only mentioned. This is an honest map — for each topic, what it is, when you'd reach for it, and what to read next. No tutorials.

## Real alerting (Alertmanager / Grafana alerting)

Our lab has no alert rules. In production you wire alert *rules* in Prometheus (or Grafana 11's alerting layer) → route via **Alertmanager** to Slack / PagerDuty / email.

The taste rule that matters more than the tooling:

- **Symptom-based alerts (right)**: "consumer lag > 5 minutes worth of expected throughput", "epoch failure rate > 1 per 30 minutes". Align with what users notice.
- **Cause-based alerts (wrong)**: "JVM heap > 80%". Fires constantly, gets ignored.

A real DE team's alert list is short — 5 to 15 named alerts per critical pipeline. If you have 100 alerts, you have 100 false alarms.

## Trace sampling at scale

[*Traces concepts*](../05-traces/01-traces-concepts.md) mentioned the two strategies. The mechanics:

- **Head-based**: at trace start, sample 1%. Cheap and simple; loses interesting traces randomly.
- **Tail-based**: buffer everything in the collector, decide at trace end whether to keep based on duration and error status. The OTel Collector contrib has a `tail_sampling` processor. Always keep `error=true`, always keep `duration > p99`, sample the rest.
- **Exemplars**: keep aggregate metrics, but link out to a handful of representative traces per bucket — lets you go from "p99 spiked" to "here's an actual slow trace from that minute".

Our lab produces a handful of spans per epoch; in a busy real pipeline you can hit millions of spans per hour. Turn on tail sampling before that bill arrives.

## SparkListener-based tracing — what real teams use

[*Cross-signal correlation*](../05-traces/02-cross-signal-correlation.md) noted the spot SparkListener as the source of our `application` / `job-NNNN` spans. The pattern is the production-correct one: every team running Spark observability at scale uses SparkListener-based hooks — off-the-shelf packages, custom listeners, or vendor integrations that work the same way under the hood.

The reason: Spark's `extraListeners` config is the official extension point. Adding a SparkListener doesn't fork Spark, doesn't require Databricks-specific runtime knowledge, and works equally on EMR, GKE, and on-prem.

If your team owns Spark observability, contribute to spot or fork it. The listener pattern is stable; the implementation is small (~200 lines of Scala). What you typically add: propagating `setJobDescription` / `setLocalProperty` values as span attributes (so your `batch_id` appears on the Spark-internal spans too), and bridging context from an orchestrator (next item).

## Orchestrator-level tracing — the layer above

In real life Spark jobs don't trigger themselves; an orchestrator (Airflow, Dagster, Prefect) schedules them. Each has its own observability layer:

- **Airflow**: scheduler + worker logs, task state UI, DAG-run dashboards.
- **Dagster**: built-in OpenTelemetry instrumentation; spans for `op` and `asset` execution.
- **Prefect**: telemetry hooks.

The win is propagating trace context **from orchestrator → Spark job**. Concretely: the orchestrator generates a `trace_id`, passes it as an env var to the Spark submission, your SparkListener picks it up and uses it as the parent of its application span. You get "the orchestrator scheduled this DAG run; one of its tasks ran this Spark job; here's the full timeline" — same `trace_id` from top to bottom. Spot doesn't do this out of the box; it's a one-evening project per orchestrator.

## Spark UI / History Server

We deliberately route everything through OTel for the unified-stack story. Real teams *also* run the Spark History Server — a Spark-native UI for job history, stage-by-stage timings, DAG visualization, SQL plan view.

The OTel data + Tempo gives you a subset of what the Spark UI offers, in a Grafana-native way. The Spark UI gives you Spark-specific depth: shuffle write/read bytes, GC events per task, executor logs, SQL physical plan annotations.

In production you run both. Spark UI for deep-debug-this-one-job; OTel/Grafana for cross-system / cross-time investigation.

## Continuous profiling — the fourth signal

Beyond metrics/logs/traces, there's a fourth signal worth knowing about: **continuous profiling**. Tools like **Grafana Pyroscope** sample CPU and memory profiles continuously, similar to `perf` but at lower overhead. You get "what code was running when this epoch slowed down" at flame-graph fidelity.

Out of scope here; mentioned because it's the next thing senior DE teams add after metrics/logs/traces are nailed. Pyroscope integrates with the same Grafana stack you've been using.

## OpenLineage — column-level lineage

OpenLineage is a sister project to OpenTelemetry. It's about **column-level lineage**: when epoch X writes `aggregated_clicks.click_count`, which input columns from which producer tables/topics flowed in, and at which transform stage?

OTel traces tell you the *operational* story ("the epoch ran, took 17s"). OpenLineage tells you the *data* story ("this column was computed from these inputs by this query"). Complementary, not competing.

Setup needs a separate sidecar (Marquez or hosted equivalent), a Spark integration jar, and mental load on top of OTel. The pattern combines cleanly with what you've learned: `batch_id` carries through both.

## Where to go next

- **The OpenTelemetry Collector docs** — receivers, processors, exporters list. https://opentelemetry.io/docs/collector/
- **The Tempo TraceQL spec** — for serious investigation queries.
- **The OpenLineage spec** — to understand the lineage layer.
- **Engineering blog post-mortems** from Databricks, Netflix, Uber on real Spark observability.
- **Distributed Tracing in Practice** (Parker et al.) — the why and how of cross-system trace context.

That's the module. You now know enough to walk into any team where the platform is already provisioned and operate it.
