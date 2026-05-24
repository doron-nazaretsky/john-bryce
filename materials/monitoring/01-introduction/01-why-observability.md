# Why Observability

A data pipeline that "ran" is not the same as one that "worked". In a multi-step distributed system, hundreds of things can go silently wrong: a Kafka broker drops connections, an executor OOMs and silently retries on another node, a schema change makes 30% of records get dropped at parse time, a Postgres index page split makes upserts 10× slower. None of these show up as a process exit code of 1. The job *succeeded* — it just delivered the wrong answer, late, with no warning.

This is the core problem **observability** solves: how do you understand the *internal* state of a running system from *outside*, after the fact, without redeploying with extra `print` statements?

## Monitoring vs Observability — a useful distinction

These words are often used interchangeably. The practical distinction:

- **Monitoring** is the dashboards and alerts you set up *ahead of time* for failures you can predict. CPU > 80%. Queue depth > 100k. Job runtime > 5 minutes. You're checking known thresholds for known questions.
- **Observability** is your ability to ask *new* questions after the fact about behaviours you didn't predict. "Why was this specific batch 4× slower than usual?" "Which records were dropped between 14:32 and 14:34?" "Did the slow-down start before or after we deployed the new aggregation logic?"

If your only tool is a dashboard, you can only see the things someone thought to put on the dashboard. Observability is what lets you investigate the question you didn't know you'd need to ask.

The textbook formulation: observability requires three signals — **metrics** (what aggregate behaviour looks like), **logs** (what individual events happened), and **traces** (how a single request flowed through the system). The four-pillars view in the next lesson extends this with the instrumentation, collection, and storage that make the signals possible at all.

## Why this matters more in data engineering

In a typical web backend, a failed request is loud: someone refreshes the page, sees a 500, files a ticket. The feedback loop is hours, sometimes minutes.

Data pipelines don't have that property. Most pipeline failures are:

- **Silent**: the job exits 0, dashboards stay green, but downstream tables have wrong numbers. No one notices until a finance analyst spots a weird KPI four days later.
- **Slow-burning**: a partition skew that makes one task take 8× longer slowly degrades throughput, but no single batch crosses an alert threshold.
- **Multi-hop**: the symptom appears in Postgres ("row count too low"), but the cause is in Kafka three systems away ("one partition's offsets are stuck").
- **Schema-related**: a producer adds a new field, downstream parsers tolerate it, but a transform 20 minutes later drops every row.

The first principle of DE observability: **trust no aggregate.** A KPI looking right means nothing if you can't drop into the underlying signals and verify each step on the pipeline produced the volume and shape you expected.

## What the rest of this module gives you

By the end of the next 4 hours you will be able to:

1. Read the four pillars of an observability stack and recognise them when you encounter a new tool (today OTel + Grafana, tomorrow Datadog or Honeycomb).
2. Operate a working observability stack — query LogQL, read PromQL panels, navigate a trace tree, jump between signals on a shared attribute.
3. Diagnose three classes of failure end-to-end — producer overload, bad upstream data, infrastructure loss — using only the dashboards and the Explore view.
4. Speak the language. When the SRE team says "what's the p99 of your batch duration broken down by stage", you will know that this is a span-level query and that it requires the right instrumentation on the right component.

We will spend most of our time *using* the stack, not configuring it. The lab comes up pre-wired. The point is the way of seeing the system, not the YAML.
