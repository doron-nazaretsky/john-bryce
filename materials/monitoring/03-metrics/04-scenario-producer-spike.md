# Scenario A — Producer Spike (Metrics)

A producer suddenly emits more events. Lag climbs, batches take longer, the sink scrambles. The whole story tells itself through metrics; we use this scenario to internalize the metric-side mental model.

## The setup

You should already have:

- `producer status` showing `running=true` with `rate_mult=1.0` (baseline 100 events/sec).
- `spark batch status` showing `daemon=running` and a recent successful batch.

If not:

```bash
docker exec workspace producer start
docker exec workspace spark batch start --interval 60
```

Open **00 Overview** and the **10 Kafka** dashboard in two browser tabs. Set both to refresh every 10 seconds, time window "last 30 minutes".

## Trigger

In your terminal:

```bash
docker exec workspace producer rate 5
```

This multiplies the baseline rate by 5. The producer is now emitting ~500 events/sec instead of ~100.

Note what you *expect*:

1. Production rate panel (10 Kafka) should jump immediately to ~5× its previous value.
2. Consumer lag should start climbing — the producer is faster than the consumer (Spark only reads on its batch cadence).
3. Each batch should take longer to process (more records to chew through).
4. Postgres write rate should climb proportionally — more unique `(product, minute)` keys, more upserts.

## Watch the signals appear

**Within 5 seconds** — production rate panel on 10 Kafka jumps. The OTel collector polls Kafka every 30s but we get OTel Java agent metrics every 15s, so this shows up fast.

**Within 30 seconds** — consumer lag starts climbing on the per-partition graph. All four partitions rise together (the producer round-robins across them). The "Max lag" stat panel on Overview turns from green to yellow to red as it crosses the 5k and 50k thresholds.

**Within 60 seconds** — the next Spark batch runs. You'll see it on **20 Spark**: executor CPU spikes, executor heap usage climbs higher than baseline batches, then drops back. On Overview the rows-written panel climbs.

**Steady state** — if you leave it at 5x for several minutes, you should see consumer lag stabilize at a new equilibrium (the consumer is still keeping up, just with a permanent ~minute of buffered records).

## What this teaches

**Lag is the leading indicator.** It rose seconds after the rate change, way before anything else looked unusual. This is the production playbook: lag panels are the first thing on-call sees.

**Throughput divergence reveals where the bottleneck is.** Look at the Overview throughput panel — produced rate jumps to 500, consumed rate stays at ~100 until the next batch, then spikes during the batch (it processes 60 seconds × 500 = 30k records in 2 seconds). Postgres write rate follows. Each system's rate is shaped by *its* processing cadence.

**Per-partition vs aggregate matters.** If all four partition lines climb together, the problem is on the consumer side. If only one climbs, look at the broker. Same rule scales to 100 partitions.

## Recovery

```bash
docker exec workspace producer rate 1
```

Lag will drain over the next 2–3 batches. The shape:

- Production rate drops back to baseline immediately.
- Consumer lag plateaus (no new records arriving), then drops sharply each time Spark batch fires (each batch consumes the backlog).
- After ~3 batches, lag returns to near-zero.

## What to look at later (when the lab session is done)

Click any of the lag spikes in **Explore → Prometheus** to drill in:

```promql
# Which partition was the worst at that moment?
topk(1, kafka_consumer_records_lag{topic="clicks"})

# How long did the lag stay above 10k?
kafka_consumer_records_lag_max > 10000

# At which batch durations did lag drain?
# (Can't do this purely in PromQL — that's a job for traces, section 5.)
```

The third query is the natural lead-in to traces. We have metrics for the lag itself, but we don't have a metric for "how long did batch X take?" That belongs to the **traces** signal, and we'll answer that exact question in section 5 via Tempo.

## A note on cardinality

The lag metric is labelled per-partition: `kafka_consumer_records_lag{topic="clicks",partition="0",client_id="..."}`. We have 4 partitions × 1 client_id × 1 topic = 4 series. Healthy.

If you instrumented per-event metrics — say, `events_processed_total{user_id="..."}` — you'd be at 5000 series for one metric and growing. That's exactly the cardinality bomb from the concepts page. The right answer for "what happened to user X" is **logs** — section 4.
