# Orienting Yourself in Grafana

Open <http://localhost:3001>. No login — the lab runs Grafana with anonymous Admin access so you can read, edit, and build panels without typing a password.

You'll spend essentially the entire module in two places: **Dashboards** (the five pre-provisioned views below) and **Explore** (the ad-hoc query bench). Everything else in the sidebar is irrelevant to us.

## The five dashboards

Open **Dashboards** from the left sidebar. They're prefixed with numbers because that number is also the **investigation order**:

| # | Dashboard | What it's for | When you open it |
|---|---|---|---|
| 00 | **Overview** | One-screen pulse: producer rate, consumer lag, Postgres write rate, last-epoch status, throughput timeseries, WARN counters. | First. Always. |
| 10 | **Kafka** | Brokers, partitions, per-partition production rate, per-partition consumer lag, fetch latency. | Throughput or lag looks off. |
| 20 | **Spark** | Driver + executor heap, GC time, CPU, thread count, live executor count. | Compute side looks unhealthy or you suspect a worker died. |
| 30 | **Postgres** | Row count, write rate by operation, commits vs rollbacks, cache hit ratio, DB size. | Writes drop or you need to validate what actually landed in the sink. |
| 40 | **ETL Business** | Domain-level: epochs succeeded/failed, schema-drop counters, full log stream with `batch_id` chips. | You suspect a *data* problem, not an infra problem. |

Click into **00 · Overview** now. Notice three things:

1. **Four stat tiles across the top** — these are your at-a-glance health check. Their colors (green / yellow / red) are the same vocabulary the rest of the dashboards use.
2. **A throughput timeseries** — `produced → consumed → written`. The three lines should track each other; divergence means a stage is falling behind.
3. **Dashboard links at the top of the page** — `ETL Business`, `Kafka`, `Spark`, `Postgres`. These are the navigation jumps you'll use during a real investigation.

## The investigation pattern

The dashboards encode a workflow, not just a list:

```{mermaid}
flowchart TD
    O["00 · Overview<br/>(always start here)"]
    O -- "throughput shifted" --> K["10 · Kafka"]
    O -- "epoch failed" --> E["40 · ETL Business"]
    O -- "write rate dropped" --> P["30 · Postgres"]
    O -- "heap or executor count" --> S["20 · Spark"]
```

This is the production model — sometimes called the **RED method** (Rate, Errors, Duration) or **USE method** (Utilization, Saturation, Errors). Overview tells you which system is in trouble; the system dashboard tells you which component within it; Explore tells you which exact record or epoch.

## Explore — the ad-hoc query bench

Click **Explore** in the sidebar. At the top there's a datasource picker with three options:

- **Prometheus** — numeric metrics, PromQL syntax. Anything with a `rate()`, `sum()`, or `histogram_quantile()`.
- **Loki** — log lines, LogQL syntax. Anything where you want to read *what actually happened*.
- **Tempo** — traces, TraceQL syntax. Anything where you want a *duration* or a *span tree*.

Three Explore features you will use this module:

- **Split view** (top-right). Opens a second panel beside the first. The most common shape: Loki on the left, Tempo on the right, pivoting between them by `batch_id`.
- **The time picker** (top-right). Defaults to "last 1 hour". When you're chasing a specific event, tighten this — looking at the wrong window is the most common cause of an empty result.
- **Cmd/Ctrl-Enter** to run a query without leaving the keyboard.

## The cross-signal links you'll use

The Loki and Tempo datasources are pre-wired to recognize the `batch_id` identifier:

- In a Loki result row, expand it — there's a `batch_id` chip with a **"View traces for batch"** button next to it. Click it, Tempo opens with that batch's `etl_batch` span.
- In a Tempo span, top-right of the detail panel has **"Logs for this span"**. Click it, Loki opens filtered to that batch.

You don't have to configure this; it's already provisioned. We'll use it constantly in the failure narratives — open the page once when you get there and the mechanism will make sense by example.

## Dashboards are editable but won't survive a restart

Anonymous Admin means you can edit any panel inline (`...` menu → Edit). That's by design for the lab — go ahead and tweak queries to learn. The dashboards are provisioned from files on disk, though, so anything you change is overwritten on the next Grafana restart. To make a change stick, edit the JSON in `labs/monitoring/config/grafana/dashboards/`.

That's enough orientation. Next we look at the ETL itself — the thing all these panels are watching.
