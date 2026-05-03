# The Streaming Mental Model

Before we touch the Spark Structured Streaming API, we need a few concepts straight in our heads. Streaming code is not just "batch code that runs more often." There are five ideas that, once internalized, make every streaming API click. Get them wrong and the API will feel arbitrary.

The five: **unbounded data**, **event time vs processing time**, **state**, **lateness**, and **completeness**.

---

## 1. Unbounded Data

In batch, your input is a finite set: a file, a table, a query result. You scan it from start to end, you compute, you stop.

In streaming, your input never ends. There's always potentially another record -- now, in five seconds, in five hours.

```
Batch input:        [r0, r1, r2, ..., r999]                          ← finite
Streaming input:    r0, r1, r2, r3, ... (continues forever) ...      ← unbounded
```

Most operations that are trivial on bounded data are tricky on unbounded data:

| Bounded | Unbounded |
|---|---|
| `count(*)` returns once, when scan completes | What's "the count"? At time T, it's some value. At T+1, it's larger. There's no single answer. |
| `select max(x)` returns once | The max grows over time. Each new record may increase it. |
| `order by ts` sorts the whole result | You can't sort the whole stream — the whole stream doesn't end. |

The general fix is to **introduce time** as a structuring dimension. We don't ask "how many pageviews?" -- we ask "how many pageviews in this 1-minute window?" Now the question is bounded again, even though the input isn't.

---

## 2. Event Time vs Processing Time

Two clocks in any streaming system:

- **Event time:** when the event actually happened in the world. The user clicked at 12:00:05.123.
- **Processing time:** when the system observed it. The record arrived at the stream processor at 12:00:07.500.

Event time and processing time **diverge for every record**, by varying amounts:

```
event:           click @ 12:00:05.123  (in the world)
producer ack:    12:00:05.130           (kafka-1 wrote it)
broker arrival:  12:00:05.150           (consumer fetched it)
processed:       12:00:07.500           (stream processor saw it)
                                        ↑
                                    processing time
```

The difference -- ~2.4 seconds in this case -- comes from network, queueing, scheduling, garbage collection, retries.

**Why this matters:** if you want to ask "how many pageviews happened between 12:00 and 12:01?", you mean event time. If you ask "how many pageviews did we process between 12:00 and 12:01?", you mean processing time.

Almost always you want event time. Processing time is what's easy; event time is what's correct.

The events themselves carry their event-time as a field (in the project: `ts` on each pageview). Processing time is whatever the cluster's wall clock says when the record is read.

---

## 3. State

A stateless transformation -- "convert each record to uppercase" -- needs no memory. Each record is processed in isolation.

A stateful operation needs memory across records:

```
input:  click(/home), click(/home), click(/about), click(/home), ...
output: count: { /home: 3, /about: 1 }
```

You can't compute "count by page" without remembering counts seen so far. The processor maintains state -- a small in-memory map -- and updates it on each record.

In batch, state is implicit (the whole partition is in memory during the shuffle). In streaming, state is **explicit and long-lived**:

- It must survive across micro-batches (or however the engine schedules work).
- It must survive crashes -- so it's checkpointed.
- It must not grow forever -- so it must be bounded somehow (windowing, eviction, watermarks).

Most of the engineering work in streaming is about state management. Stateless transformations work the same as in batch; stateful ones require new tools.

---

## 4. Lateness

Now the hard one. In a perfect world, records arrive in the same order they were generated. In the real world, they don't:

- A mobile client lost network for 30 seconds, buffered events, and sent them later.
- A producer with `acks=all` and a slow follower took 500ms to confirm.
- The broker's partition leader changed; some records that were in flight arrived after the new leader's first writes.
- A consumer crashed and replayed from an earlier offset; the records were "old" by the time you got them.

A record's event time can be anywhere in the past. The gap between "now" (processing time) and the record's event time is its **lateness**.

```
processing time NOW: 12:05:00
record arrives:      event_time = 12:00:23  (lateness = 4m37s)
```

The system has to decide: do we *include* this record in the 12:00–12:01 window we may have already emitted? Do we re-emit the window with the new value? Do we drop the record?

The answer is: it depends on **how late is too late**, which is the [watermark](05-watermarks-and-late-data.md). For now: every streaming system needs a policy for lateness, and that policy is a first-class part of the design.

---

## 5. Completeness

Closely related to lateness, and the deepest mental shift from batch:

> **In streaming, you almost never know when you've seen everything for a given period.**

In batch, "the day's data" is a closed set after the day ends and the file is delivered. In streaming, "the data for the 12:00 minute" is open until... when, exactly? Until you decide it is. There might still be a record arriving 5 minutes late. Or 5 hours.

The implication is that **streaming results are usually approximations that converge**. Right at 12:01:00 you can emit "23 pageviews in the 12:00 minute, based on what I've seen so far." A minute later a late record arrives and the answer is now 24. Then the answer settles.

Streaming engines support this with three output modes:

- **Append:** emit only when you're sure -- when the watermark guarantees no more updates will come. The result for a window comes out once.
- **Update:** emit every time a row's value changes. The same window may be emitted multiple times, with the latest count.
- **Complete:** emit the entire result table on every trigger. Expensive, only safe for small results.

The right choice depends on what consumes the output. We'll come back to this in [Structured Streaming Basics](03-structured-streaming-basics.md).

---

## The Mental Shift

Putting it all together, here's the shift from batch thinking to streaming thinking:

| Batch | Streaming |
|---|---|
| Input is a finite dataset | Input is an unbounded stream |
| Time is implicit (the data has whatever time the data has) | Time is explicit (you choose event time vs processing time, you reason about lag) |
| State is per-job, ephemeral | State is long-lived, must be checkpointed |
| Records are in order (or you sort them) | Records can be late or out of order — you handle it |
| The answer is computed once per run | The answer is approximate and converges over time |

If you can answer all five of these for a given pipeline, you have enough to write the streaming code. If you can't, you'll write code that *works* on test data and *breaks* in production -- because production has lateness, has out-of-order events, and never lets you assume the dataset is closed.

---

## Where We Go Next

The next chapter introduces Spark Structured Streaming with these concepts in mind. You'll see how each of the five ideas above maps to specific API decisions:

- Unbounded data → reading from a streaming source (Kafka), starting a long-running query.
- Event time → the `withWatermark` API and time-based group-by.
- State → automatically managed by the engine, but bounded by watermarks.
- Lateness → `withWatermark` again, plus output mode choice.
- Completeness → `outputMode("append" | "update" | "complete")`.

The API will feel arbitrary if you skip the mental model and dense if you've internalized it. Take a moment with the five concepts before moving on.

---

[← Previous: Real-Time vs Batch](01-realtime-vs-batch.md) | [Next: Structured Streaming Basics →](03-structured-streaming-basics.md)
