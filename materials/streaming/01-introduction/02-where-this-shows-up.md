# Where Messaging and Streaming Show Up

The previous lesson argued for the streaming-shaped broker in the abstract. This one shows where you actually meet it in real systems -- both the obvious places and the ones that surprise people. Knowing the patterns by name makes it easier to recognise which of them fits a problem you're handed.

---

## The Five Patterns You'll See Repeatedly

### 1. Event Notifications (Pub/Sub)

> "Something happened. Whoever cares, react."

The checkout example from the messaging chapter. One producer, many independent consumers, each doing their own thing with the event. Fan-out topology.

**Real systems:** order-placed events triggering email + warehouse + analytics + fraud, GitHub webhooks (`push`, `pull_request`) triggering CI + chat notifications + downstream mirrors, Stripe `payment.succeeded` events triggering receipt emails and accounting updates.

> **Core Concept:** Fan-out / pub/sub topology -- see [Pub/Sub and Messaging](../../core-concepts/07-application-patterns/02-pubsub-and-messaging.md).

---

### 2. Work Queues

> "Here's a job. Some worker, do it."

One producer, one logical consumer (a pool of workers competing for jobs). Point-to-point topology. The queue exists to **smooth load** -- the producer can submit jobs faster than any single worker can process, and the queue absorbs the burst.

**Real systems:** image-resizing pipelines (upload → queue → resize workers), video transcoding, bulk-email sending, web scraping, batch report generation, Celery / Sidekiq / Resque task queues.

A specific subtype: **job scheduling**. Cron writes a "run job X" message to a queue; workers pick it up. Decoupling the *trigger* (cron, time) from the *work* (the heavy task) is what lets the work be retried, scaled, and observed without changing the trigger.

---

### 3. Stream Processing Pipelines

> "Process every event continuously, derive a result that's always up-to-date."

A producer publishes a high-volume stream (clicks, sensor readings, log lines, trades). A consumer reads continuously, computes some aggregation or transformation, and writes out a derived stream or table.

**Real systems:** real-time analytics dashboards (page-views per minute, errors per service), fraud detection (every transaction is scored as it happens), monitoring/alerting (metrics → derived alarms), recommendation systems updating user features in real time.

This is what the second half of this module is about. Kafka is the producer side, Spark Structured Streaming is the consumer side.

---

### 4. Log Aggregation and Audit

> "Append everything that ever happened to a durable, ordered log."

The broker is treated as the *system of record*. The log of events is the truth; everything else is a derived view that can be rebuilt by replaying the log.

**Real systems:** event sourcing (Kafka as the source of truth, materialized views in Postgres / Elasticsearch / Cassandra), audit trails for regulated industries, system logs aggregated for SIEM (Splunk, Elastic, Datadog).

This pattern requires the broker to *persist* messages and let consumers replay from any point. Not all messaging systems can do this -- it's a property of log-structured brokers like Kafka. The "durable, replayable log" property from the previous lesson is exactly what makes this pattern work.

---

### 5. Service-to-Service Async RPC

> "Call this service, but don't wait. The reply will come later on a reply queue."

This is the rarest pattern and the most often misused. The caller publishes a request, includes a correlation ID, and listens on a reply topic for the response. The callee processes the request and publishes the reply.

**Real systems:** request/reply over RabbitMQ, Apache Pulsar, or AWS SQS for slow backend calls (e.g. expensive ML inference) where the caller has nothing else to do but wait.

> **Warning:** if you find yourself building this, ask whether a direct sync HTTP call wouldn't be simpler. The decision rule from the messaging chapter applies: if the caller is just going to block waiting for the reply anyway, the broker is adding hops, not removing coupling. Async RPC is right when there's a specific reason -- usually load-leveling against a slow backend with bursty demand -- not as a default.

---

## When Messaging Is the Wrong Tool

Some architectural mistakes are easier to make than to explain in retrospect. Watch for these:

- **Using a queue for a database.** "We need to store the last value seen per user" -- that's a database. Messaging is about events flowing through, not state living in.
- **Using messaging to avoid learning HTTP.** Two services that own each other's lifecycles, deployed together, on the same network -- a function call or HTTP call is fine. Don't add a broker as a status symbol.
- **Using messaging to avoid thinking about consistency.** "We'll just publish an event and let things sort themselves out" doesn't fix anything if the consumers all need to agree on the same view of the world. You've made consistency *harder*, not easier.
- **Using messaging without idempotent consumers.** The moment delivery is async, "at least once" is the only reasonable guarantee, which means consumers must be safe to call twice. If they aren't, you have a duplicate-orders bug waiting to happen.

---

## What Counts as "Real-Time"?

The word "real-time" gets used three different ways in industry. Pin them down before deciding what tool fits:

| Term | Latency budget | Example |
|---|---|---|
| **Hard real-time** | microseconds, deterministic | Aircraft control, anti-lock brakes (not a streaming-system problem) |
| **Near-real-time** | sub-second to a few seconds | Fraud scoring, live dashboards, alerting |
| **Soft real-time** | tens of seconds to minutes | "Refresh the homepage rankings every 30s" |

Streaming tools (Kafka + Spark, Kafka + Flink) target **near-real-time** -- sub-second to a few seconds end-to-end. They are not for hard real-time, and they are overkill for soft real-time, which a periodic batch job handles fine.

We'll come back to this in [Real-Time vs Batch](../03-streaming/01-realtime-vs-batch.md) once the Kafka and Spark Streaming concepts are in place.

---

## What's Next

The next chapter introduces Apache Kafka. We'll learn the broker through its concepts (broker, topic, partition, producer, consumer, group) but stay aware that the same vocabulary -- with small variations -- applies to every modern broker.

---

[← Previous: From Messaging to Streaming](01-from-messaging-to-streaming.md) | [Next: Broker, Topic, Partition Model →](../02-kafka/01-broker-topic-partition-model.md)
