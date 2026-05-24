# Traces — Concepts

A trace is the story of a single operation across many components. It's the "I called the API, it called five services, here's the timing tree" view.

If metrics tell you what's happening in the aggregate and logs tell you what's happening to individual events, **traces tell you what's happening to a single causal flow**. That's the third axis that observability needs.

## Spans, trace_id, parent/child

```
trace_id = c4f8...                       Trace
├─ span "handle_request"                  Root span (no parent)
│    span_id = a1b2, parent = null
│    └─ span "load_user"                  Child span
│         span_id = c3d4, parent = a1b2
│         └─ span "db_query"              Grandchild
│              span_id = e5f6, parent = c3d4
└─ ...
```

Every span has:

- A unique **span_id** (random).
- A **trace_id** shared with all siblings/ancestors in the same operation.
- An optional **parent_span_id** linking it into the tree.
- A **start_time** and **duration**.
- A **name** (`db_query`) and **service.name** (which component created it).
- A bag of **attributes** (key/value, like span "tags").

Looking up a trace is "give me all spans with trace_id = c4f8...". Tempo's storage is optimised for exactly that.

## Why parent/child matters

The tree structure is what makes traces *useful*. Without it, you have a flat list of timings — same as just having durations as a metric. With it:

- **Latency attribution**: span "handle_request" took 800ms; its child "db_query" took 700ms. The DB is the bottleneck.
- **Critical path**: which child span overlapped/blocked which sibling. Visible in the timeline view.
- **Error propagation**: child span errored, parent rolled up the error. You can find the *source* of an error chain.

In a microservices request flow, parent/child is propagated via HTTP headers (`traceparent`, `tracestate`). When service A calls service B over HTTP, A injects the header, B's auto-instrumentation reads it, B creates a child span. That's the entire mechanism.

## Trace fragmentation in distributed compute (the honest part)

Spark — and basically every distributed compute framework — does **not** propagate OTel context across the task serialization boundary. When the driver schedules a task on an executor:

1. The driver has a span (`job-00001`) active.
2. The driver serializes the task closure and sends it to the executor.
3. The executor deserializes, runs the closure.
4. The executor's auto-instrumentation creates its own spans — but they have a fresh `trace_id`, no parent.

So in this lab, the driver-side `job-00001` spans (from spot) and any executor-side spans (currently none, but in principle JDBC writes from an executor would generate spans) are **NOT** in the same trace.

**This is production reality, not a bug.** Every team running observability on Spark hits this. The standard workaround is exactly what we do here: tag every span with a shared business attribute (`batch_id`) that you can pivot on. You give up "single trace tree spans the whole pipeline" and gain "easy filter by batch across all spans".

The instructor talking point: "every observability tool documentation promises seamless distributed tracing. In data engineering with Spark, that promise has a footnote you only see in production. We're showing you the footnote up front."

## Sampling (mentioned, not used)

In production, traces are expensive — one span per HTTP call, one trace per request, at thousands of requests per second, your trace storage bill explodes. Solutions:

- **Head-based sampling**: at trace start, flip a coin to decide whether to record. Cheap but loses interesting traces (errors are usually rare and randomly sampled out).
- **Tail-based sampling**: record every span, then at trace end (or after a buffer window) decide whether to keep based on duration / error status. More expensive but keeps the good stuff.

The OTel Collector contrib has a `tail_sampling` processor. Production teams set it up early. The lab runs with no sampling — our trace volume is laughably small (one `etl_batch` span per minute), and Tempo accepts everything.

If you're applying this in real production: sample your trace data. 1% head-based + a tail processor that catches errors and slow traces is a reasonable starting point.

## Manual vs auto instrumentation (again, in trace context)

Two trace trees in this lab, both useful:

- **Auto** (spot listener + Java agent): produces 5–10 spans per Spark job, with timing for each stage. Zero code on our part. Detailed but generic — these are "what Spark did".
- **Manual** (`etl_batch` span via OTel Python SDK): one span per batch, with the `batch_id` attribute. One Python file change to add the with-block. Sparse but exactly the boundary we care about — this is "what *our pipeline* did".

The combination is the lesson. Auto gives you depth (sub-job timing, executor identities, GC pause events). Manual gives you the *business semantics* — the boundary that matters to humans, with the attributes you'd actually query on.

You almost always need both in real pipelines. Auto-only and you can't navigate by business identifier. Manual-only and you lose all the system-level depth.

## Sampling out the agent's chatter

The Java agent, left to its defaults, will produce spans for Jetty HTTP requests (Spark UI), JDBC calls, Kafka client operations, and more. We disable instrumentation modules we don't use via `-Dotel.instrumentation.<name>.enabled=false`:

```
mongo, cassandra, elasticsearch, redis, lettuce, jedis, aws-sdk,
akka-actor, akka-http, play-mvc, vertx, netty, spring-webmvc,
spring-webflux, grpc, couchbase, hibernate
```

Cuts JVM boot time meaningfully (no bytecode rewriting for unused libs) and trace volume. We keep on: kafka, jdbc, jetty/servlet, runtime-telemetry. These are the only ones the workload uses.

Next: how the trace pipeline is wired in our specific lab.
