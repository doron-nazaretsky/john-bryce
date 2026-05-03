# Streaming Exercises

These exercises go beyond the in-class project. They're optional, can be done in any order, and are best done after Stage 3 of `streaming-clickstream` is working. All require the lab to be running (`make lab-streaming`).

For each exercise, write your code in a notebook or a small standalone script under your project's `notebooks/` or `scripts/` directory.

---

## Theory Exercises

### 1. Pick the right tool

For each of the following pipelines, decide whether you'd use **batch**, **near-real-time streaming**, or **direct sync HTTP**, and explain why in 1-2 sentences:

- (a) A nightly job that recomputes daily revenue per region from raw orders.
- (b) A button on a checkout page that asks "is this credit card valid?"
- (c) A homepage widget showing "trending articles in the last 5 minutes."
- (d) A weekly email summary of users' activity.
- (e) A fraud-detection screen that has to flag suspicious transactions before the user receives the goods.
- (f) A sync between an ERP system and a CRM, run every 4 hours.

### 2. Lateness budget

A team is debating the watermark threshold for an "errors per minute" dashboard. They have:
- Median lateness: 200ms
- P99 lateness: 4 seconds
- P99.9 lateness: 30 seconds

If the dashboard refreshes every 30 seconds, what watermark threshold would you pick? What does picking 1 second instead cost you? What does picking 5 minutes cost you?

### 3. Partitioning consequences

You have a topic `orders` with 12 partitions, and you produce records with `key = order_id`. The product team asks you to "process all orders for the same customer in order." What's wrong with the current setup, and what would you change?

### 4. Failure modes

For each of the following Kafka configurations, name a failure mode it allows:
- (a) `acks=1`, `replication.factor=3`, `min.insync.replicas=2`
- (b) `acks=all`, `replication.factor=3`, `min.insync.replicas=1`
- (c) `enable.auto.commit=true`, manual processing in the loop
- (d) `enable.idempotence=false`, `retries=10`

---

## Hands-On Exercises

The lab cluster has Kafka brokers `kafka-1:9092, kafka-2:9092, kafka-3:9092` and a Spark session inside `streaming-jupyter`. Use the `pageviews` topic from the project (or create a new topic — `kafka-topics.sh --create --topic <name> --partitions 6 --replication-factor 3 --bootstrap-server kafka-1:9092`).

### 5. Watch a rebalance

In one terminal, start two consumers in the same group:

```bash
docker exec -it streaming-jupyter python -c "
from kafka import KafkaConsumer
c = KafkaConsumer('pageviews', group_id='rebalance-demo',
                  bootstrap_servers='kafka-1:9092')
for r in c: print(r.partition, r.offset)
"
```

Run two of these in two terminals. Observe the partition assignment in each. Now `Ctrl+C` one of them. What happens to the other? How long did the rebalance take?

### 6. Kill a broker

With the project running (producer + windowed query), `docker stop kafka-2`. Use `kafka-topics.sh --describe` to inspect partition state:

```bash
docker exec kafka-1 kafka-topics.sh --describe --topic pageviews \
    --bootstrap-server kafka-1:9092
```

Which partitions changed leader? What did the producer do during the failover? What did the windowed query do?

`docker start kafka-2` and watch it rejoin and re-sync.

### 7. Write a top-N stream

Compute "top 5 pages every 1 minute" continuously. Hint: a windowed count followed by a per-window ranking. The tricky part is doing the ranking on a streaming DataFrame -- you'll likely need `foreachBatch`.

### 8. Sessionize per-user

Compute per-user sessions using `session_window` with a 5-minute inactivity gap. Output: `(user_id, session_start, session_end, page_count)`. Run the producer for a few minutes and inspect the output.

### 9. Build a "late-arrival reconciler"

This is a hard one. Set up your windowed aggregation with a 30-second watermark (intentionally tight). Produce some events with backdated timestamps (event_time = wall_clock - 5 minutes) and observe `numRowsDroppedByWatermark` growing.

Now write a *batch* job that reads the same Kafka topic from the beginning and recomputes the windowed counts correctly. Compare its output to the streaming output. The diff is your "lateness loss."

This is the **lambda architecture** in miniature: streaming for freshness, batch for correctness.

### 10. Implement at-most-once

Modify `pipeline/consumer.py` to be at-most-once: commit offsets *before* processing, so a crash mid-process loses records but never duplicates. Demonstrate the loss with a forced crash (`raise RuntimeError`) and show that on restart, the lost record is not redelivered.

---

## Stretch Exercises

### 11. Stream-stream join

Create two topics: `orders` (`order_id`, `user_id`, `amount`, `ts`) and `payments` (`order_id`, `status`, `ts`). Write a streaming query that joins them on `order_id` to produce `enriched_orders`. Use watermarks on both sides to bound state.

What happens if a payment arrives before its order? After the watermark? Document the behavior.

### 12. Compacted topic for state

Create a topic `user_profiles` with `cleanup.policy=compact`. Have a producer publish profile updates keyed by `user_id`. Then write a Spark streaming query that reads the topic from `earliest` and treats it as the current state of all profiles. Validate that compaction has dropped older versions.

### 13. Two-cluster mirroring (deep cut)

Spin up a second Kafka cluster (call it the "DR" cluster) in a separate compose file, and mirror the `pageviews` topic across using `kafka-mirror-maker.sh`. Validate that records produced to cluster A appear on cluster B with the same key partitioning.

This is a serious exercise. Don't attempt without comfort with the previous ones.

---

## Reflection Prompts

After completing some of these:

- What changed in your understanding of "real-time" between starting the module and finishing it?
- Which Kafka concept was the most surprising? Which Spark Streaming concept?
- For a system you've worked on (current job, side project, hypothetical), where would messaging fit naturally? Where would it be overkill?

---

[← Back: Streaming Module Home](../README.md)
