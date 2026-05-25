# Traces — Concepts

A trace is the story of a single operation across many components. It's the "I called the API, it called five services, here's the timing tree" view.

If metrics tell you what's happening in the aggregate and logs tell you what's happening to individual events, **traces tell you what's happening to a single causal flow**. That's the third axis observability needs.

## Spans, trace_id, parent/child

```
trace_id = c4f8...                       Trace
├─ span "handle_request"                 Root span (no parent)
│    span_id = a1b2, parent = null
│    └─ span "load_user"                 Child span
│         span_id = c3d4, parent = a1b2
│         └─ span "db_query"             Grandchild
│              span_id = e5f6, parent = c3d4
└─ ...
```

Every span has:

- A unique **span_id** (random).
- A **trace_id** shared with all spans in the same operation.
- An optional **parent_span_id** linking it into the tree.
- A **start_time** and **duration**.
- A **name** (`db_query`) and **service.name** (which component created it).
- A bag of **attributes** (key/value, like span "tags").

Looking up a trace is "give me all spans with trace_id = c4f8...". Tempo's storage is optimised for exactly that.

## Why parent/child matters

The tree structure is what makes traces *useful*. Without it, you have a flat list of timings — same as just having durations as a metric. With it:

- **Latency attribution**: span "handle_request" took 800ms; its child "db_query" took 700ms. The DB is the bottleneck.
- **Critical path**: which child overlapped/blocked which sibling. Visible in the timeline view.
- **Error propagation**: child errored, parent rolled up. You can find the *source* of an error chain.

In a microservices request flow, parent/child is propagated via HTTP headers (`traceparent`, `tracestate`). When service A calls service B over HTTP, A injects the header, B's auto-instrumentation reads it, B creates a child span. That's the entire mechanism.

## Trace fragmentation in distributed compute — the honest part

Spark — and basically every distributed compute framework — does **not** propagate OTel context across the task serialization boundary. When the driver schedules a task on an executor:

1. The driver has a span active.
2. The driver serializes the task closure and sends it to the executor.
3. The executor deserializes and runs the closure.
4. The executor's auto-instrumentation creates its own spans — but with a fresh `trace_id`, no parent.

Even within the driver process, our lab has two separate runtimes — the Python ETL daemon and the JVM — and **OTel context is a thread-local in each runtime; Py4J doesn't bridge it**. So our pipeline produces two trace trees per epoch:

- `etl-driver / etl_batch` — one Python span per epoch, carrying `batch_id`.
- `spark-driver / job-NNNN` — auto-instrumented Spark internals (jobs, stages).

They are *siblings in time* but not parent/child in OTel.

**This is production reality, not a bug.** Every team running observability on Spark hits this. The standard workaround is exactly what we do here: tag every span with a shared business attribute (`batch_id`) that you can pivot on. You give up "single trace tree spans the whole pipeline" and gain "easy filter by batch across all spans". That pivot mechanism is the subject of the next page.

> Instructor talking point: every observability tool documentation promises seamless distributed tracing. In data engineering with Spark, that promise has a footnote you only see in production. We're showing you the footnote up front.

## Manual vs auto instrumentation — cost vs business semantics

Two trace sources in this lab, both useful:

- **Auto** (OTel Java agent on the Spark JVMs): produces spans for every Spark job and Kafka client operation. Zero code on our part. Detailed but generic — these are "what Spark did".
- **Manual** (`etl_batch` span via OTel Python SDK): one span per epoch, with the `batch_id` attribute. ~15 lines of setup, 3 lines per epoch. Sparse but exactly the boundary we care about — this is "what *our pipeline* did".

The combination is the lesson. Auto gives you depth (sub-job timing, executor identities). Manual gives you the *business semantics* — the boundary that matters to humans, with the attributes you'd actually query on.

You almost always need both. Auto-only and you can't navigate by business identifier. Manual-only and you lose system-level depth.

## Sampling (mentioned, not used)

In production, traces are expensive — one span per HTTP call, one trace per request, at thousands of requests per second, your trace storage bill explodes. Two strategies:

- **Head-based sampling**: at trace start, flip a coin. Cheap; loses interesting traces randomly.
- **Tail-based sampling**: record every span, then at trace end decide whether to keep based on duration or error status. More expensive but keeps the good stuff.

The OTel Collector contrib has a `tail_sampling` processor. Production teams set it up early. Our lab runs with no sampling — trace volume is tiny (one `etl_batch` span per ~10 seconds). See [*What we didn't show*](../06-failure-narratives/04-what-we-didnt-show.md) for when to add it.

## In our lab — where the spans come from

Two sources push spans into the collector over OTLP, which forwards them to Tempo:

- The **OTel Java agent** on every Spark JVM emits HTTP, JDBC, Kafka-client, and (via the spot SparkListener) Spark job/stage spans. We disable unused instrumentation modules (mongo, cassandra, redis, …) via `-Dotel.instrumentation.<name>.enabled=false` to cut boot time and span noise.
- The **OTel Python SDK** in the ETL daemon emits a single `etl_batch` span per epoch with `batch_id` as an attribute.

The collector's traces pipeline is trivial: `receivers: [otlp] → processors: [batch] → exporters: [otlp/tempo]`. No sampling, no transformation beyond the standard resource attributes.

Next: how to navigate between signals using `batch_id`.
