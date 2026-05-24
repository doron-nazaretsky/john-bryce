# The Logs Pipeline

Concrete walkthrough of how a log line goes from `_root.info(...)` in `etl_daemon.py` to a queryable row in Loki.

## Source — Python JSON formatter

```python
class _JsonLineFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "batch_id": getattr(record, "batch_id", "-"),
        })
```

Two handlers: a `FileHandler` writes to `/var/log/etl/etl.log`, a `StreamHandler` writes to stdout. Both with the same formatter.

The `batch_id` field comes from a `LoggerAdapter` — at the start of each batch:

```python
def _log(batch_id: str) -> logging.LoggerAdapter:
    return logging.LoggerAdapter(_root, {"batch_id": batch_id})

log = _log(batch_id)
log.info(f"batch start batch_id={batch_id}")
```

Two important details:

- We embed `batch_id` in both the structured field AND the message text. The text form (`"batch start batch_id=b-..."`) is what Grafana's Loki **derived field** regex matches on, enabling the Loki → Tempo jump. The structured field becomes a Loki structured-metadata field for direct filtering.
- The `ts` field is ISO 8601 with timezone. The OTel filelog operator parses this as the canonical timestamp; without it, Loki would use the file-tail time, which lags by 1–5 seconds in practice.

## Transport — shared volume

The ETL daemon runs inside the `spark-master` container. The collector runs in `otel-collector`. They share the named volume `etl-logs` mounted at `/var/log/etl/` in both. The collector tails the file directly — no network, no protocol.

```yaml
# compose.yml, spark-master service
volumes:
  - etl-logs:/var/log/etl

# compose.yml, otel-collector service
volumes:
  - etl-logs:/var/log/etl:ro
```

This pattern (file-tail via shared volume) is the simplest path for any application that already writes logs to disk. Alternatives: OTLP-push from the Python SDK (heavier), syslog (deprecated), Fluentd / Vector sidecar (more complexity).

## The OTel filelog receiver

```yaml
receivers:
  filelog:
    include: [/var/log/etl/etl.log]
    start_at: beginning
    operators:
      - type: json_parser
        timestamp:
          parse_from: attributes.ts
          layout_type: gotime
          layout: "2006-01-02T15:04:05.999999999Z07:00"
        severity:
          parse_from: attributes.level
      - type: move
        from: attributes.batch_id
        to: resource["batch_id"]
      - type: move
        from: attributes.logger
        to: resource["logger"]
      - type: move
        from: attributes.msg
        to: body
```

Walking through the operators:

1. **json_parser** — parses each line as JSON, hoists fields into OTel attributes. Sets the OTel timestamp from the `ts` field (rather than wall-clock) and the OTel severity from `level`.
2. **move** ops promote `batch_id` and `logger` to **resource attributes** — these end up as Loki labels and structured metadata.
3. **move** for `msg → body` makes the log line "value" be just the message text, not the full JSON. Cleaner Explore UI.

The `layout_type: gotime` parser is the one that took several iterations to get right — Python's `datetime.isoformat()` emits `+00:00` for UTC, which Go's standard timestamp parser accepts but Python's `strptime` doesn't. We document this exact pitfall in the file. Pin the Go format string carefully.

## The pipeline

```yaml
service:
  pipelines:
    logs/etl:
      receivers:  [filelog]
      processors: [resource/etl_service, resource/lab, batch]
      exporters:  [otlphttp/loki]

    logs/otlp:
      receivers:  [otlp]
      processors: [resource/lab, batch]
      exporters:  [otlphttp/loki]
```

Two pipelines: one for the ETL file, one for OTLP-pushed logs (currently unused — the Java agent on Spark JVMs doesn't push logs by default).

`resource/etl_service` adds `service.name=etl` to the ETL pipeline since file-tail doesn't include a service name. The other resource processor stamps `lab=monitoring` on everything.

The `otlphttp/loki` exporter posts batches to `http://loki:3100/otlp`. Loki 3.x speaks OTLP natively — no need for a translation layer. Resource attributes that match Loki's allow-list become labels; the rest become structured metadata.

```yaml
exporters:
  otlphttp/loki:
    endpoint: http://loki:3100/otlp
```

By default, Loki only promotes a tiny allow-list to labels (`service_name`, `service_namespace`, `service_instance_id`). Everything else — including `batch_id`, `logger`, `level` — becomes structured metadata. That's exactly what we want for `batch_id` (high cardinality), and it's also what we want for `level` (only 5 values, but Loki's default behavior is fine).

## What labels exist in Loki

Run a label list against Loki:

```bash
docker exec grafana wget -qO- 'http://loki:3100/loki/api/v1/labels' | python3 -m json.tool
```

You'll see just `service_name` and `service_instance_id`. Everything else (`batch_id`, `level`, `logger`) lives as structured metadata — queryable but not indexed as labels.

```bash
docker exec grafana wget -qO- 'http://loki:3100/loki/api/v1/label/service_name/values' | python3 -m json.tool
# {"status":"success","data":["etl","spark-driver","spark-executor","spark-master","spark-worker"]}
```

## Two paths that don't exist (but you might wonder about)

- **Logs from the Spark JVMs via the Java agent**. The agent has a logs SDK that can push log records over OTLP, but enabling it requires JVM args we don't set. Spark's own log4j output goes to the container stdout, which we *could* capture via stdout/docker-driver and ship — but we don't. Why? Spark logs are extremely verbose at INFO; routing them via OTel would 10× our log volume for very little teaching value. For Scenario C we'll lean on the Spark UI and trace data instead.
- **Direct Python OTLP log push**. Equivalent effort to filelog + shared volume, with the downside of coupling the application to the collector's lifecycle. We chose file-tail for the lab — closer to how real legacy apps get logged.

Next: how to query this in Grafana.
