# The Metrics Pipeline

Concrete walkthrough of how metrics flow from "happened in the JVM" to "rendered in Grafana", with the actual configuration files open.

## Three sources feed the collector

### 1. The OTel Java agent on the Spark JVMs (push)

In `compose.yml`, every Spark JVM — driver, executors, master, workers — gets the agent attached via `SPARK_DAEMON_JAVA_OPTS` (for master/worker daemons) or via `--conf spark.driver.extraJavaOptions` / `spark.executor.extraJavaOptions` (for spark-submit).

```
-javaagent:/opt/otel-jars/opentelemetry-javaagent.jar
-Dotel.exporter.otlp.protocol=http/protobuf
-Dotel.exporter.otlp.endpoint=http://otel-collector:4318
-Dotel.service.name=spark-driver        # distinct per role
-Dotel.metric.export.interval=15000
-Dotel.instrumentation.<unused-libs>.enabled=false
```

The `-Dotel.metric.export.interval` pushes the agent's collected metrics every 15 seconds. The `-Dotel.instrumentation.*.enabled=false` flags disable instrumentation modules we don't use (Cassandra, MongoDB, AWS SDK, etc) — cuts boot time and avoids span noise. We keep on: kafka client, jdbc, jetty/servlet (Spark UI HTTP), runtime-telemetry (JVM stats).

### 2. The `kafkametrics` receiver (pull)

The collector's `kafkametrics` receiver speaks the Kafka admin protocol — same protocol Kafka clients use to fetch broker metadata, topic configs, and consumer group state. No JMX, no Java in the collector itself.

`config/otel-collector.yaml`:

```yaml
receivers:
  kafkametrics:
    brokers: [kafka-1:9092, kafka-2:9092]
    protocol_version: 3.7.0
    scrapers: [brokers, topics, consumers]
    collection_interval: 30s
```

Every 30 seconds the collector connects to the brokers, asks them about the world, and emits metrics like `kafka_topic_partitions`, `kafka_partition_current_offset_ratio`, `kafka_consumer_records_lag` for each consumer group.

### 3. The `postgresql` receiver (pull)

Same idea, postgres-specific. Reads `pg_stat_database`, `pg_stat_user_tables`, etc — Postgres's built-in statistics views.

```yaml
postgresql:
  endpoint: postgres:5432
  username: app
  password: app
  databases: [clicks]
  collection_interval: 30s
```

Outputs `postgresql_commits_total`, `postgresql_rollbacks_total`, `postgresql_db_size_bytes`, `postgresql_table_size_bytes`, `postgresql_rows{state=live}`, `postgresql_operations_total{operation=ins|upd|del}`.

## The collector pipeline

```yaml
service:
  pipelines:
    metrics:
      receivers:  [otlp, kafkametrics, postgresql]
      processors: [resource/lab, batch]
      exporters:  [prometheus]
```

- **otlp** receiver — accepts metrics pushed from Spark JVMs (and anything else speaking OTLP).
- **resource/lab** processor — adds the constant resource attribute `lab=monitoring` to everything. Useful when multiple labs share infrastructure.
- **batch** processor — buffers up to 1024 records or 5 seconds, whichever first. Reduces the number of HTTP requests / Prom scrapes.
- **prometheus** exporter — exposes `:8889/metrics` for Prometheus to scrape.

The `resource_to_telemetry_conversion: enabled: true` on the prometheus exporter is critical — without it, resource attributes (like `service.name=spark-driver`) wouldn't become Prometheus labels and you'd lose the ability to filter.

## Why we use the contrib distribution

The collector image is `otel/opentelemetry-collector-contrib:0.115.1`, not core. The receivers `kafkametrics`, `postgresql`, `filelog` (we'll use it in section 4) are contrib-only. If we used the core image:

```
Error: unknown receiver type "kafkametrics" for id "kafkametrics"
```

…and the collector would refuse to start. We documented this in `01-introduction/03-stack-tour.md`; it's also the second item in the plan's non-drift list.

## Prometheus config (one line of YAML)

```yaml
scrape_configs:
  - job_name: 'otel-collector'
    scrape_interval: 15s
    static_configs:
      - targets: ['otel-collector:8889']
```

Prometheus has exactly one scrape target: the collector. Everything we have ever instrumented or scraped flows through that one endpoint. **Prometheus does not talk to Kafka, Postgres, or Spark directly.** This is the central principle of using a collector — only one thing needs to know about your storage backend.

You can verify it's working:

```
http://localhost:9090/api/v1/targets
```

Should show one target, status `up`, label `job=otel-collector`.

## What metrics are actually flowing

Quick sanity:

```bash
curl -s 'http://localhost:9090/api/v1/label/__name__/values' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d["data"]))'
```

You'll see ~400 metric names. The interesting families:

- `jvm_*` — from the Java agent on every Spark JVM (~50 metrics × 5 JVMs).
- `kafka_consumer_*` — from the Java agent (kafka client instrumented).
- `kafka_*` (broker, topic, partition) — from the kafkametrics receiver.
- `postgresql_*` — from the postgresql receiver.

That's about ~400 series at our cardinality. Production scales this by 10–100x and Prometheus handles it fine; we just need a few series for the lab to be vivid.

Next: how to read these in the dashboards we shipped.
