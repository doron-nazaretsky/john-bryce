# Production Patterns — What We Didn't Show

The lab is small on purpose. Real production observability adds a few capabilities we mentioned but skipped. This page is a tour of what to learn next.

## SparkListener-based tracing is what real teams use

What we did with spot is the production-correct pattern. Big companies running Spark at scale (Databricks, Netflix, Uber) all use SparkListener-based observability — either off-the-shelf packages, custom listeners, or vendor integrations that work the same way under the hood.

The reason: Spark's `extraListeners` config is the official extension point. Adding a SparkListener doesn't fork Spark, doesn't require Databricks-specific runtime knowledge, and works equally on EMR, GKE, and on-prem.

If your team owns Spark observability, contribute to spot, or fork it. The listener pattern is stable; the implementation is small (~200 lines of Scala).

## OpenLineage — deferred to V2

`OpenLineage` is a sister project to OpenTelemetry. It's about **column-level lineage**: when batch B writes column `aggregated_clicks.click_count`, which input columns from which producer tables/topics flowed into it, and at which transform stage?

OTel traces tell you the *operational* story ("the batch ran, took 17s"). OpenLineage tells you the *data* story ("this column was computed from these inputs by this query"). They're complementary, not competing.

Why we deferred: setup needs a separate sidecar (Marquez or a hosted equivalent), a Spark integration jar, plus mental load on top of OTel. The plan's V2 evaluation criterion is: "after running V1 in class, decide whether students asked enough lineage questions to justify the extra container."

If you're doing this in your team:

- Add the OpenLineage Spark listener jar (separate from spot).
- Run a Marquez container, point the listener at it.
- You get a UI of "table X was last written by job Y from inputs A, B, C".
- The pattern combines cleanly with the OTel pattern: `batch_id` carries through both.

## Orchestrator-level tracing — the layer above

In real life Spark batches don't trigger themselves; an orchestrator (Airflow, Dagster, Prefect) schedules them. The orchestrator has its own observability layer:

- **Airflow**: scheduler + worker logs, task state UI, DAG-run dashboards.
- **Dagster**: built-in opentelemetry-instrumentation; spans for `op` and `asset` execution.
- **Prefect**: similar, with telemetry hooks.

You want trace context to propagate **from orchestrator → Spark job**. Concretely: the orchestrator generates a trace_id, passes it as an env var to the Spark submission, the listener picks it up and uses it as its application-span parent.

This gives you "the orchestrator scheduled this DAG run; one of its tasks ran this Spark job; here's the full timeline". Same `trace_id` from top to bottom. spot doesn't do this out of the box (orchestrator integration code is per-orchestrator); it's a one-evening project.

## Spark UI / History Server

We deliberately route everything through OTel for the unified-stack story. Real teams *also* run the Spark History Server — a Spark-native UI for job history, stage-by-stage timings, DAG visualization, SQL plan view.

The OTel data + Tempo gives you a subset of what the Spark UI offers, in a Grafana-native way. The Spark UI gives you Spark-specific depth: shuffle write/read bytes, GC events per task, executor logs, SQL physical plan annotations.

In production you run both. The Spark UI for deep-debug-this-one-job, the OTel/Grafana stack for cross-system / cross-time investigation.

## Sampling at scale

Our lab has 1 micro-batch per minute = 1 etl_batch trace + a handful of Spark job traces per minute = ~thousands of traces per day. Tempo eats this for breakfast.

Real Spark workloads: a single micro-batch can produce hundreds of Spark jobs, each with dozens of stages, each with thousands of tasks. The trace volume in a busy pipeline = millions of spans per hour. Tempo (and your bill) won't survive.

Production sampling strategies:

- **Head-based**: at trace start, sample 1% of traces. Cheap, simple. Loses interesting traces randomly.
- **Tail-based**: collect everything in a short buffer, decide at trace-end whether to keep. Always keep errors, always keep slow traces, sample the rest. Better signal-to-noise; needs the OTel `tail_sampling` processor in the collector.
- **Exemplars**: keep aggregate metrics, but link out to a handful of representative traces. Lets you go from "p99 latency spiked" to "here's an actual slow trace from that minute".

If you scale this lab to production: turn on tail sampling, set rules that always keep `error = true` and `duration > p99`.

## Real alerting (Alertmanager)

We have no alert rules in the lab. Production alerts are usually:

- **Symptom-based (the right kind)**: "consumer lag > 5 minutes worth of expected throughput" or "batch failure rate > 1 per 30 minutes". These align with what users notice.
- **Cause-based (the wrong kind)**: "JVM heap > 80%" — fires constantly, ignored. Cause alerts are for dashboards, not pages.

Wiring: Prometheus has Alertmanager. Define alert rules in YAML, route to Slack/PagerDuty/email. Grafana 11 also has its own alerting that overlaps; pick one to avoid double-paging.

A real DE team's alert list is typically short — 5 to 15 named alerts per critical pipeline. If you have 100 alerts, you have 100 false alarms.

## Profiling — the fourth signal that almost exists

Beyond metrics/logs/traces, there's a fourth signal worth knowing about: **continuous profiling**. Tools like Grafana Pyroscope sample CPU and memory profiles continuously, similar to how perf works but at lower overhead. You get "what code was running when this batch slowed down" at flame-graph fidelity.

Out of scope here; mentioned because it's the next thing senior DE teams add after they have metrics/logs/traces nailed. Pyroscope integrates with the same Grafana stack we're using.

## What to read next

- The OpenTelemetry Collector docs — receivers, processors, exporters list. https://opentelemetry.io/docs/collector/
- The Tempo TraceQL spec — for serious investigation queries.
- The OpenLineage spec — to understand the lineage layer.
- Real-world Spark observability post-mortems on the engineering blogs of Databricks / Netflix / Uber.
- The book *Distributed Tracing in Practice* (Parker et al.) — covers the why and how of cross-system trace context.

Section 7 is the instructor's pre-class verification checklist. Section 8 is optional homework.
