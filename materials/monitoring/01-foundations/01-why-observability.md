# Why Observability

A data pipeline that "ran" is not the same as one that "worked". In a multi-step distributed system, hundreds of things can go silently wrong: a Kafka broker drops connections, an executor OOMs and silently retries on another node, a schema change makes 30% of records get dropped at parse time, a Postgres index page split makes upserts 10× slower. None of these show up as a process exit code of 1. The job *succeeded* — it just delivered the wrong answer, late, with no warning.

This is the core problem **observability** solves: how do you understand the *internal* state of a running system from *outside*, after the fact, without redeploying with extra `print` statements?

## Monitoring vs observability

These words are often used interchangeably. The practical distinction:

- **Monitoring** is the dashboards and alerts you set up *ahead of time* for failures you can predict. CPU > 80%. Queue depth > 100k. Job runtime > 5 minutes. You're checking known thresholds for known questions.
- **Observability** is your ability to ask *new* questions after the fact about behaviours you didn't predict. "Why was this specific batch 4× slower than usual?" "Which records were dropped between 14:32 and 14:34?" "Did the slow-down start before or after we deployed the new aggregation logic?"

If your only tool is a dashboard, you can only see the things someone thought to put on the dashboard. Observability is what lets you investigate the question you didn't know you'd need to ask.

## Why this matters more in data engineering

In a typical web backend, a failed request is loud: someone refreshes the page, sees a 500, files a ticket. The feedback loop is minutes.

Data pipelines don't have that property. Most pipeline failures are:

- **Silent**: the job exits 0, dashboards stay green, but downstream tables have wrong numbers. No one notices until a finance analyst spots a weird KPI four days later.
- **Slow-burning**: a partition skew that makes one task take 8× longer slowly degrades throughput, but no single batch crosses an alert threshold.
- **Multi-hop**: the symptom appears in Postgres ("row count too low"), but the cause is in Kafka three systems away ("one partition's offsets are stuck").
- **Schema-related**: a producer adds a new field, downstream parsers tolerate it, but a transform 20 minutes later drops every row.

The first principle of DE observability: **trust no aggregate.** A KPI looking right means nothing if you can't drop into the underlying signals and verify each step on the pipeline produced the volume and shape you expected.

## Whose job is the stack itself?

In most companies you join, **you will not set this up.** A platform / SRE / DevOps team operates the observability stack — collector, Prometheus, Loki, Tempo, Grafana — as shared infrastructure, the same way they operate Kubernetes or the artifact registry. From a data engineer's seat, the stack is *given*: there is a Grafana URL, there is a collector endpoint, there are agreed-on conventions for labels and trace export.

Your job, as a DE, is the other half:

- **Pick the right business identifiers** (`batch_id`, `run_id`, `dataset_id`) and attach them to every signal your pipeline emits.
- **Decide what to instrument manually** in your application code — usually one or two business-meaningful spans, the one or two domain-meaningful log fields, the metric you'd want on a dashboard one day.
- **Read the dashboards** when something is off, follow the cross-signal pivots to the root cause, and write the incident note.

That split is why this module spends a little time on "what the stack is and how it's wired" and most of it on "how to operate it as the DE consumer".

## What the rest of this module gives you

By the end you will be able to:

1. Recognise the four pillars of an observability stack when you encounter a new tool (today OTel + Grafana, tomorrow Datadog or Honeycomb).
2. Operate a working stack — query LogQL, read PromQL panels, navigate a trace tree, jump between signals on a shared attribute.
3. Diagnose three classes of failure end-to-end — producer overload, bad upstream data, infrastructure loss — using only the dashboards and the Explore view.
4. Speak the language. When the SRE team says "what's the p99 of your batch duration broken down by stage", you will know that this is a span-level query and that it requires the right instrumentation on the right component.

Next: the four pillars of the stack, with concrete tool names attached.
