# Scenario C — A Worker Dies (Integrated)

The infrastructure breaks. Specifically: someone (you) kills a Spark worker mid-batch. All three signals tell a piece of the story, and only by reading all three do you understand what happened.

This scenario is the integration test of everything in the previous five sections.

## Setup

```bash
docker exec workspace producer start
docker exec workspace producer rate 3   # 300/sec — gives Spark visible work per batch
docker exec workspace spark batch start
sleep 90  # let two healthy batches go by first
```

Open three dashboards (split window or three tabs):

- **00 Overview** — for the global pulse
- **20 Spark** — for the JVM-level damage
- **40 ETL Business** — for batch outcomes

And **Explore → Loki** with `{service_name="etl"}` running.

## Trigger

Kill one of the two Spark workers:

```bash
docker kill spark-worker-1
```

We don't restart it yet. We let the pipeline absorb the failure.

## Observe each signal

### Metrics — 20 Spark dashboard

Within 10 seconds:

- **Live executors** stat drops from 2 to 1 (background turns yellow).
- **JVM heap by service/host** loses the line for spark-worker-1.
- **Thread count** for spark-worker-1 vanishes from the legend.

The signals are immediate and structural — a host disappeared.

### Logs — 40 ETL Business + Loki Explore

Wait for the next epoch (within 60 seconds). Two outcomes are possible:

**Outcome A — epoch in flight when worker died.** Tasks on the dead worker fail; Spark's task scheduler detects the lost executor, reschedules onto the remaining worker, and retries. The streaming engine also has its own safety net: the failed micro-batch is retried from the checkpoint with the same `epoch_id`. The epoch usually completes, just slower than usual. Expected log:

```
INFO  epoch start batch_id=e-... input_rows=11420
INFO  epoch done batch_id=e-... rows_written=312 bad=0
INFO  streaming progress batch_id=e-... input_rows=11420 dropped_by_watermark=0
```

The duration of this epoch is markedly higher than baseline — visible in Tempo (next step) and also as a glitch in Postgres write rate (the foreachBatch upsert lands all at once at the end of a longer micro-batch).

**Outcome B — epoch fired after worker died.** Spark schedules everything on the remaining worker. Half the parallelism, twice the time. Same successful outcome, just visibly slower.

A subtlety worth noting: with Structured Streaming, **replay safety is automatic**. If the driver itself were killed mid-foreachBatch (not the worker), the next start would resume from the checkpoint and replay the same `epoch_id` with the same state-store-derived data. The REPLACE upsert is idempotent, so the data stays correct. This is a stronger guarantee than the old batch design provided.

In neither case do you see an ERROR log. The pipeline self-healed. This is what makes the failure mode insidious — without observability you might never notice.

### Traces — Tempo

Open Tempo, search for recent `etl-driver / etl_batch` traces:

```traceql
{ resource.service.name = "etl-driver" }
```

Compare the most recent two epochs:

- The one that ran with 2 workers: short duration.
- The one that ran with 1 worker: noticeably longer duration (the foreachBatch waits on the slower micro-batch).

Click the etl_batch trace. The span is otherwise identical — same attributes, same status. The duration is the only difference.

Switch to TraceQL `{ resource.service.name = "spark-driver" }` and find a job from this epoch. The stages took longer; if you'd had executor-side spans, you'd see retries here too. With our setup, the job-level duration is the visible signal.

## What this teaches

This scenario is *integration*: each pillar shows a different facet, and only together do they explain the event.

| Signal | What it tells you |
|---|---|
| Metrics | An executor disappeared. (The structural change.) |
| Logs | The pipeline self-healed. (No ERROR.) |
| Traces | The healed batches were slower. (The quantitative cost.) |

If you only had metrics, you'd know a worker died but not whether anyone noticed. If you only had logs, you'd see no errors and assume nothing happened. If you only had traces, you'd see slower epochs and not know why. **Three signals together = the story**.

## Recovery

```bash
docker start spark-worker-1
```

Within ~30 seconds, Spark master accepts the rejoining worker; the next epoch sees 2 executors again; everything returns to baseline.

Verify in:

- **20 Spark** — executor count back to 2, two heap lines visible.
- **Tempo** — next batch duration returns to ~2s.

## Variations to demo (or assign as exercise)

1. **Kill the spark-master.** Pipeline halts hard — batches fail to schedule. ERROR logs flow. Restart restores. The signal: `daemon=running` but `batch failed` count climbs.

2. **Kill kafka-1.** Producer + consumer should keep working via kafka-2 (replication factor 2). Kafka admin metrics show 1 broker; per-partition lag may briefly spike during the broker switch.

3. **`docker pause spark-worker-1` instead of `kill`.** Subtler: worker doesn't disappear, just stops heartbeating. Spark UI shows the worker as "dead" eventually but takes longer. Tasks on the paused worker hang until Spark gives up. Different failure mode, different signal pattern.

Each variation produces a unique signature across the three signals. Real on-call experience is recognizing these signatures.

## The takeaway slide

The lesson's central promise — **unified observability across a multi-system DE pipeline** — holds when:

- Every component is instrumented (auto where possible, manual where needed).
- One collector ingests everything (you don't run a separate pipeline per signal).
- One viz layer correlates across signals (one tab to debug from).
- A business identifier (`batch_id`) ties everything together.

If any of those four is missing, you have monitoring, not observability.

Section 6 part 2: what we *didn't* show you that exists in production.
