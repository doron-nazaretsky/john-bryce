# Real-Time vs Batch Processing

You've already built a batch pipeline -- the [spark-etl project](../../projects/spark-etl/). It runs on a scheduler, picks up new files every minute, and produces results that lag the world by ~1 minute. That's batch. This chapter answers: when is that not enough, and what does the alternative actually look like?

---

## Recap: The Batch Model You Built

In the spark-etl project, the world worked like this:

```
producer drops 1 file every 10s →  data/landing/
                                       ↓
        scheduler fires run_etl every 60s
                                       ↓
                    run_etl reads new files, computes
                                       ↓
                       writes to analyst store + serving store
```

A scheduler decides *when* to compute. Each tick processes a finite chunk of input that has accumulated since the last tick. Between ticks, the system is idle.

This pattern has a lot going for it:

- **Simple.** Each tick is an isolated unit -- read input, compute, write output, done.
- **Easy to test.** You can run a single tick deterministically with a known input file.
- **Easy to recover.** If a tick fails, retry it. The tick is the unit of work.
- **Resource-efficient when input is predictable.** Spin up the cluster, run the work, tear down (or scale down).

It also has a clear cost: **data is stale by up to one tick**. The user clicked at 12:00:05; the result is in the analyst store at 12:01:00. The "freshness" of the answer is bounded below by your tick interval.

For most analytics, that's fine. For some, it isn't.

---

## When Batch Stops Being Enough

Three patterns push you off batch:

### 1. Human-perceptible latency requirements

A trader's dashboard updating every 5 seconds. A fraud-detection screen flagging a transaction within a second of it happening. An anomaly-detection alarm firing 30 seconds after the metric goes off.

For these, "wait a minute and rerun" is not a usable answer. Batch with a smaller tick interval helps -- but a 1-second batch still has 1 second of staleness, plus the JVM cold-start of each spark-submit. At some point you cross a line where the *batch overhead* dominates and switching to streaming pays back.

### 2. Continuously-derived state

A pipeline whose output is itself a stream consumed by other systems. "Every order produces a row in `enriched_orders`." If the downstream system wants enriched orders as soon as they happen, you can't afford the batch's wait-and-tick cycle.

### 3. State that spans events

"How many distinct users visited the homepage in the last 5 minutes?" In batch you can compute this once per tick -- but you have to reconcile across batches. In streaming, you maintain the state continuously and emit a fresh answer whenever it changes.

---

## The Streaming Model

Streaming flips the picture. Instead of "process a chunk every N seconds," it's "process every record as it arrives, continuously."

```
producer publishes events  →  Kafka topic (continuous flow)
                                 ↓
            stream processor reads, transforms, emits
                                 ↓
                      sink updates continuously
```

The stream processor is **always running**. It reads as fast as records arrive, holds state in memory as needed, and emits results as soon as they're ready.

A few important consequences:

- **Latency floor is the broker + processing time.** End-to-end latency drops from "tick interval + processing time" to "processing time alone" -- typically sub-second.
- **No notion of "the dataset ends."** Your code has to deal with input that never stops.
- **State is now part of the computation.** "What was the running count?" requires the processor to remember.
- **Failure handling looks different.** No retry-the-tick. Crashes are recovered by restoring state from a checkpoint and replaying from a known offset.

That last point is what makes streaming subtle. We'll spend the rest of this chapter on it.

---

## The Spectrum, Not Two Boxes

It's tempting to call batch and streaming opposites, but they're points on a spectrum:

```
Real batch     Micro-batch      Continuous streaming   Hard real-time
(hourly,       (60s, 30s, 10s)  (Spark Structured     (microseconds,
 daily)                          Streaming, Flink)     embedded systems)

  ←-- minutes --→  ←-- seconds --→  ←-- ms --→  ←-- µs --→
```

- **Real batch:** big chunks at long intervals. Cheap, simple, stale.
- **Micro-batch (small batch):** very short intervals -- 30 seconds, 10 seconds, 1 second. Looks streaming-y from the outside but each tick is still a finite job.
- **Continuous streaming:** the engine holds open state and emits as records arrive. Spark Structured Streaming is technically micro-batch under the hood (default ~100ms triggers), but the API and semantics are streaming.
- **Hard real-time:** deterministic latency in microseconds. Not Kafka, not Spark, not what we're building.

For the rest of this course "streaming" means the second-and-third points: latencies in the sub-second to a few seconds range. That's what the tools we use are good at.

---

## Why You Wouldn't Always Pick Streaming

Streaming is harder. Specifically:

- **State must be managed.** A long-running query holds aggregates, joins, dedup tables in memory. You have to budget that memory and decide when state can be evicted.
- **Late and out-of-order data is a fact, not an exception.** A record arriving 30 seconds late is normal. Your code has to handle it explicitly. (See [Watermarks](05-watermarks-and-late-data.md).)
- **Failure recovery requires checkpoints.** A streaming query that's been running for a week has aggregated a week of state -- you can't afford to lose it. That state must be persisted somewhere.
- **Operational complexity.** The cluster is *always running*. Resource sizing, deployment, observability, and on-call all become "running a 24/7 service" rather than "running a job."
- **Backpressure matters.** If the consumer can't keep up with the producer, the broker absorbs it -- but if the gap keeps growing, you eventually fall over.

Most pipelines that *could* be streaming are better off as batch. The right question is "do we actually need sub-second latency, or are we just choosing streaming because it's modern?"

A useful heuristic: **if the user-visible result tolerates 5+ minutes of staleness, batch is probably the right answer.**

---

## What We're Going to Build

In Stages 2 and 3 of the project we'll write streaming jobs:

- A **continuous ingester** that reads pageview events from Kafka and writes them to parquet files. (Stage 2.)
- A **windowed aggregation** that maintains "pageviews per page per 1-minute window" and emits results as windows close. (Stage 3.)

Both will use Spark Structured Streaming -- the next chapter is the mental model that makes its API make sense.

> **Compare with what you built before:** in spark-etl you had a 60-second scheduler. In Stage 3 here, the same kind of "pageviews per minute" answer becomes a *long-running query* that updates continuously. The tick interval becomes (effectively) the trigger interval -- but state is preserved across triggers, and late data is handled at the engine level rather than by you.

---

[← Previous: Advanced Features Overview](../02-kafka/07-advanced-features-overview.md) | [Next: Streaming Mental Model →](02-streaming-mental-model.md)
