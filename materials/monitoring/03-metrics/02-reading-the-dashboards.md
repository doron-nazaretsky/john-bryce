# Reading the Metrics Dashboards

Open Grafana, open dashboard **00 Overview**, leave it on a 30-second window.

This page is a tour of the four metrics-focused dashboards (Overview, Kafka, Spark, Postgres) and what each panel actually tells you. The logs-driven `40 ETL Business` dashboard is covered in the logs section. The investigation pattern (Overview → system → Explore) is in [*Grafana orientation*](../02-lab-tour/03-grafana-orientation.md); this page is panel-by-panel detail.

## 00 Overview — the first place you look

Four stat panels across the top, then a throughput timeseries and a recent-batches log stream.

| Stat | Meaning | Color logic |
|---|---|---|
| **Last batch** | Most recent batch status (OK / FAILED) | Green=INFO, red=ERROR (background) |
| **Producer rate** | Events/sec being consumed from Kafka (proxy for produce rate when caught up) | Blue area, no thresholds |
| **Consumer lag** | Max lag across all partitions | Green<5k, yellow 5k–50k, red>50k |
| **Postgres write rate** | Upserts/sec on `aggregated_clicks` | Blue area, no thresholds |

The throughput panel below shows `consumed/sec` vs `rows written/sec`. **Divergence = a problem.** Consumed rate climbing while rows-written stays flat = Spark is consuming but not making it to Postgres.

Then there's an Ok/Failed split, a Dropped count, and the log stream.

## 10 Kafka

Single most important panel: **Consumer lag (per partition)**. Three readings:

- **All lines climb together** = throughput problem on the *consumer* (Spark) side. Spark reads all partitions per batch; if it's slower than the producer, lag accumulates on all four.
- **One line spikes, others flat** = broker partition issue, hot key, or stuck consumer assignment. Rare in our lab (4 partitions, no key, even distribution).
- **All flat ≈ 0** = healthy.

The bar gauge on the right shows the same data as a snapshot — useful for "right now, which partition is worst?"

**Production rate** is the *derivative* of `kafka_partition_current_offset_ratio` — how fast new offsets are appearing per partition. Flat = producer not producing; spiking = overproduction.

**Fetch latency** is broker-side time per fetch. Spikes = broker pressure or network. Should always be < 100ms in our lab.

### Why `consumer_records_lag` not `consumer_group_lag`

The lag we have (`kafka_consumer_records_lag`) is emitted by the **Spark consumer itself** via the Java agent's Kafka instrumentation — per client, per partition, what *this Spark batch* sees. Spark's reads don't commit to a consumer group in the usual way (offsets are managed in checkpoint), so there's no collector-side group lag. The agent-emitted client-side lag is what you have, and it's perfect for the lab.

## 20 Spark

Four stats: live executors, driver heap %, driver GC time/min, driver CPU.

Headline panels:

- **JVM heap by service/host** — one line per JVM. Driver should sit flat between batches. Executors should spike during each batch and dip between.
- **GC time / sec** by service — sustained > 0.1 s/s = JVM in trouble. Spikes during a batch are normal; *steady-state* high GC means the JVM is starved.
- **CPU utilization** by service — same shape pattern as heap: executors spike during batches.
- **Thread count** — sudden drops mean an executor died. Steady growth means a thread leak (rare in Spark).

### What you *won't* see here

There is no panel for "Spark job duration" or "stage time". Spark doesn't emit metrics for job durations as Prometheus counters/gauges — those live in **traces**, where each job is a span. We see them in section 5.

This is a real teaching point: **not every operational signal naturally fits all three signal types**. Job duration is per-job → that's spans territory. Forcing it into Prom histograms would require manual instrumentation. Traces own this question instead.

## 30 Postgres

Four stats: row count, write rate (ins+upd/sec), commits/sec, db size.

The headline panel is **Write operations / sec** — a stacked bar chart split by operation (ins, upd, del). For an upsert workload like ours, you'll see both `ins` and `upd` on each batch, roughly evenly (depends on whether the minute window is new or being updated).

**Rows over time** is the cumulative `aggregated_clicks` row count. Should climb monotonically.

**Commits vs rollbacks** — green commits near the write rate; red rollbacks should be 0. Any non-zero rollback rate = something failing transactions.

**Cache hit ratio** = `1 - disk_reads / total_reads`. Should be > 0.99 for our small dataset. If it drops, your working set is no longer fitting in Postgres's shared buffers.

### The schema-qualified label gotcha

The `postgresql` receiver labels tables with their schema qualifier: `postgresql_table_name="public.aggregated_clicks"`, not `"aggregated_clicks"`. If you write your own panels: include the schema.

## A quick PromQL primer

Open **Explore → Prometheus**. The four most useful operations:

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

We'll exercise these dashboards on real failures in section 6. Next: logs.
