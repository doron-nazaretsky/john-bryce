# Reading the Dashboards

Open Grafana, open dashboard **00 Overview**, leave it on a 30-second window.

This page is a tour of the four metrics-focused dashboards (Kafka, Spark, Postgres, Overview) and what each panel actually tells you. Section 4 covers the logs-driven 40 ETL Business dashboard.

## 00 Overview — the first place you look

Four stat panels across the top, then a throughput timeseries and a recent-batches log stream.

| Stat | Meaning | Color logic |
|---|---|---|
| **Last batch** | Most recent batch status (OK / FAILED) | Green=INFO, red=ERROR (background) |
| **Producer rate** | Events/sec being consumed from Kafka (proxy for produce rate when caught up) | Blue area, no thresholds |
| **Consumer lag** | Max lag across all partitions | Green<5k, yellow 5k–50k, red>50k |
| **Postgres write rate** | Upserts/sec on `aggregated_clicks` | Blue area, no thresholds |

The throughput panel below shows `consumed/sec` vs `rows written/sec`. **Divergence = a problem.** Consumed rate climbs while rows-written stays flat = Spark is consuming but not making it to Postgres.

Then there's an Ok/Failed split, a Dropped count, and the log stream.

### When to leave Overview

Use the dashboard navigation links (top-right of the page) to jump to the specific system. Or use the rule of thumb from section 2:

- Consumer lag red → **10 Kafka**
- Last batch red → **40 ETL Business**
- Postgres write rate dropped → **30 Postgres**
- Nothing obviously wrong but you suspect compute → **20 Spark**

## 10 Kafka

Single most important panel: **Consumer lag (per partition)**. Lines are individual partitions. Three readings:

- **All lines climb together** = throughput problem on the *consumer* (Spark) side. The producer is faster than the consumer; the lag accumulates on all partitions because Spark reads all of them in each batch.
- **One line spikes, others flat** = broker partition issue, hot key, or a stuck consumer assignment. Rare in our lab (4 partitions, no key, even distribution).
- **All flat ≈ 0** = healthy.

The bar gauge on the right shows the same data as a snapshot — useful when you want to see "right now, which partition is worst?"

The "Production rate" panel is the *derivative* of `kafka_partition_current_offset_ratio` — how fast new offsets are appearing in each partition. If it's flat, the producer isn't producing. If it's spiking, the producer is overproducing.

"Fetch latency" is broker-side time spent on each fetch. Spikes here = broker pressure or network. In our lab it should always be < 100ms.

### Why "consumer_records_lag" not "consumer_group_lag"

The lag metric we have (`kafka_consumer_records_lag`) is emitted by the **Spark consumer itself** via the Java agent's Kafka instrumentation — it's per client, per partition, what *this specific Spark batch* sees. There's no separate consumer group lag pulled by the collector because Spark's batch reads don't commit to a consumer group in the usual way (it manages offsets in checkpoint). The agent-emitted client-side lag is what you have, and it's perfect for the lab.

## 20 Spark

Four stats: live executors, driver heap %, driver GC time/min, driver CPU.

Headline panels:

- **JVM heap by service/host** — one line per JVM. Driver should sit flat between batches. Executors should spike during each batch and dip between them.
- **GC time / sec** by service — sustained > 0.1 s/s = JVM in trouble. Spikes during a batch are normal; *steady-state* high GC means the JVM is starved.
- **CPU utilization** by service — same shape pattern as heap: executors spike during batches.
- **Thread count** — sudden drops mean an executor died. Steady growth means a thread leak (rare in Spark).

### What you *won't* see here

There is no panel for "Spark job duration" or "stage time". The reason: Spark itself doesn't emit metrics for job durations as Prometheus counters/gauges. Those live in **traces**, where each job is a span. We'll see that in section 5.

This is a real teaching point: **not every operational signal naturally fits all three signal types**. Job duration is fundamentally per-job → that's spans territory. Trying to force a "p99 job duration" panel via metrics histograms would require manual instrumentation in spot or a similar listener; ours doesn't do it. Instead, traces own this question.

## 30 Postgres

Four stats: row count, write rate (ins+upd/sec), commits/sec, db size.

The headline panel is **Write operations / sec** — a stacked bar chart split by operation (ins, upd, del). For an upsert workload like ours, you'll see both `ins` and `upd` on each batch, in roughly even amounts (depends on whether the minute window is new or being updated).

**Rows over time** is the cumulative `aggregated_clicks` row count. Should climb monotonically.

**Commits vs rollbacks** — green commits should be near the write rate; red rollbacks should be 0. Any non-zero rollback rate = something is failing transactions.

**Cache hit ratio** = `1 - disk_reads / total_reads`. Should be > 0.99 for our small dataset. If it drops, your working set is no longer fitting in Postgres's shared buffers.

### The schema-qualified label gotcha

The `postgresql` receiver labels tables with their schema qualifier: `postgresql_table_name="public.aggregated_clicks"`, not just `"aggregated_clicks"`. The first version of these dashboards used the unqualified name and showed "No Data" — caught during the step-5 verification rubric. If you write your own panels: include the schema.

## A quick PromQL primer

Open **Explore → Prometheus**. The PromQL syntax for the four most useful operations:

```promql
# Pick a series by labels
kafka_consumer_records_lag{topic="clicks"}

# Rate of a counter (always wrap counters in rate())
rate(kafka_consumer_records_consumed_total[1m])

# Aggregate (drop labels)
sum by (service_name) (jvm_memory_used_bytes{jvm_memory_type="heap"})

# Math between metrics
1 - sum(rate(postgresql_blocks_read_total{source="disk"}[2m]))
    / sum(rate(postgresql_blocks_read_total[2m]))
```

The four PromQL functions to remember are `rate()`, `sum()`, `avg()`, and `histogram_quantile()`. Almost any panel you'll see in the wild is one of those wrapping a metric name with label filters.

Now, the first scenario.
