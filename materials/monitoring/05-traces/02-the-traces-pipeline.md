# The Traces Pipeline

How spans flow from "happened in code" to "rendered as a trace in Grafana", for both the auto and manual sources.

## Source 1 — the OTel Java agent (Spark JVMs)

Same agent that gives us metrics in section 3 also produces spans. The Java agent emits:

- **HTTP spans** for any inbound HTTP request (Spark UI on Jetty).
- **Kafka client spans** for produce/consume operations.
- **JDBC spans** for SQL queries (we don't use Spark JDBC for our writes — psycopg in the driver-side `foreachBatch` does — so this is mostly idle).
- **Runtime spans** are off by default.

These spans alone don't tell the full Spark story — they're component-level, not job-level. To get *job/stage* spans we need a SparkListener that integrates with Spark's lifecycle hooks.

## Source 2 — the spot SparkListener

The plan calls out `com.xebia.data.spot.TelemetrySparkListener` (Apache 2.0; renamed from `io.godatadriven` after Xebia's acquisition). It's a SparkListener that subscribes to Spark's internal events (`SparkListenerApplicationStart`, `SparkListenerJobStart`, etc) and creates corresponding OTel spans.

Config:

```
--jars /opt/otel-jars/spot-complete.jar
--conf spark.extraListeners=com.xebia.data.spot.TelemetrySparkListener
```

Output is a span tree per Spark job:

```
application span (one per spark-submit)
└─ job-NNNN span (one per Spark job)
   └─ stage span (one per Spark stage)
```

Span attributes are minimal: `stageIds`, `spark.job.time`. **It does NOT propagate `setJobDescription` or `setLocalProperty` to span attributes** — verified by reading the source during step-5 verification. If you want a custom attribute (like `batch_id`) on those spans, you'd need to fork spot or run a separate listener. We don't; that's why the manual `etl_batch` span exists.

The spot project status is documented as "early development" in its README. Our lab pins a specific Git SHA; we built the jar from source via the jar-prep init container (no Maven Central artifact existed at the time of writing).

## Source 3 — the manual `etl_batch` span (Python)

From `etl_daemon.py`:

```python
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

_provider = TracerProvider(resource=Resource.create({"service.name": "etl-driver"}))
_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4318/v1/traces"))
)
trace.set_tracer_provider(_provider)
_tracer = trace.get_tracer("etl")

# Inside the foreachBatch sink, once per micro-batch (epoch):
with _tracer.start_as_current_span(
    "etl_batch",
    attributes={"batch_id": batch_id, "etl.kafka.topic": CLICKS_TOPIC,
                "etl.epoch_id": int(epoch_id)},
) as span:
    upsert_rows_into_postgres(df, batch_id)
    span.set_attribute("etl.rows_written", len(good_rows))
```

Twelve lines of setup, three lines per epoch. The cost.

This produces a single span per epoch, `service.name=etl-driver`, with `batch_id` (= `f"e-{epoch_id}"`) as a span attribute. Tempo TraceQL can search:

```
{ resource.service.name = "etl-driver" }
{ .batch_id = "e-42" }
{ .batch_id != "" && duration > 10s }
```

The third query is the analyst's dream — "show me slow epochs with their batch_id, sorted by duration".

## Why we have **two trace trees** and not one

Earlier we said this would happen. Concretely:

- **Trace tree 1**: `etl-driver` / `etl_batch`. Lives in the Python process. Has `batch_id`. One root, no children, sub-second-to-a-few-seconds duration (just the foreachBatch upsert work).
- **Trace tree 2**: `spark-driver` / `application` / `job-00001` / stages. Lives in the JVM. Has spot's spark-specific attributes. Multiple jobs per epoch (Spark's microbatch planning + state-store read + Kafka source consume).

They are siblings in time but not parent/child in OTel. The Python span and the JVM spans both run inside `spark-master`, but they're separate processes (PySpark Python ↔ JVM via Py4J). OTel context is a thread-local in each runtime; Py4J doesn't bridge it.

In real production this is the norm. The cross-tree pivot is via the shared `batch_id` attribute, which the next section explains.

## Wire — the trace pipeline in the collector

```yaml
service:
  pipelines:
    traces:
      receivers:  [otlp]
      processors: [resource/lab, batch]
      exporters:  [otlp/tempo]

exporters:
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true
```

Simple: accept OTLP (gRPC or HTTP) from any client, batch, push to Tempo over OTLP-gRPC. No transformation beyond the `lab=monitoring` resource attribute.

Tempo's storage is filesystem (single-binary mode). For the lab that's fine; for production you'd use S3 / GCS / Azure Blob.

## Verifying traces are arriving

```bash
# From the host (no tempo port exposed) — proxy via Grafana:
curl -s -u admin:admin \
  'http://localhost:3001/api/datasources/proxy/uid/tempo/api/search?q=%7B%20.batch_id%21%3D%22%22%20%7D&limit=3' \
  | python3 -m json.tool | head -20
```

Should return JSON with at least one trace, `rootServiceName: etl-driver`, `rootTraceName: etl_batch`.

If empty: most likely the daemon hasn't run a full batch since startup. `spark batch status` should show at least one "ok" state.

## The trace tree as a debugging tool

Open **Explore → Tempo**, set query type to **Search**, filter by **Service Name = etl-driver**. You'll get a list of traces (most recent first). Click one. The middle pane is a timeline:

```
[==================== etl_batch (17s) ====================]
  attributes:
    batch_id = e-42
    etl.kafka.topic = clicks
    etl.rc = 0
    service.name = etl-driver
```

For our lab, `etl_batch` is a flat span — no children, since we didn't wire context propagation to the JVM (intentional simplification). The full Spark job tree lives in the *separate* `spark-driver` trace, which you can find by switching to the **Search → Service Name = spark-driver** view.

Side by side, two traces from the same epoch tell you:

- `etl_batch` (etl-driver): the wall-clock time of the Postgres upsert inside foreachBatch.
- `application/job-NNNN` (spark-driver): the JVM-side breakdown — Kafka source read, state-store read+write, shuffle, several stages each with their timings.

In the next page we make this navigable: from a single log line in Loki, jump to the matching trace. From the trace, jump back to logs.
