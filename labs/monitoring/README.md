# Monitoring & Observability Lab

Full observability stack — OpenTelemetry Collector (contrib), Prometheus, Loki, Grafana Tempo, Grafana — wrapped around a small but realistic data pipeline: a 2-broker Kafka cluster, a 3-node Spark cluster (1 master + 2 workers), and Postgres as the sink. A PySpark batch ETL runs every minute, reads e-commerce click events from Kafka, aggregates them with Spark SQL, and upserts the results into Postgres. The whole pipeline is monitored by the same OTel-centric stack so students can experience cross-signal navigation (trace → logs → metrics) in Grafana.

## Usage

```bash
make lab-monitoring   # bring up all 12 services
make down             # stop the lab
```

**Prereqs:** Docker Desktop with at least **8 GB RAM** allocated (the default 4 GB will OOM). Mac/Windows users: Docker Desktop → Settings → Resources → Memory.

## Container Map

| Service | Image | Role | Mem |
|---|---|---|---:|
| workspace | base (LAB=monitoring) | MyST docs, Jupyter, producer CLI, spark CLI, batch loop | 700m |
| jars-init | curlimages/curl | One-shot: download OTel agent + spot listener jars | — |
| otel-collector | otel/opentelemetry-collector-contrib | Central collection point for all three signals | 400m |
| prometheus | prom/prometheus | Metrics TSDB | 400m |
| loki | grafana/loki | Logs store | 400m |
| tempo | grafana/tempo | Traces store | 400m |
| grafana | grafana/grafana | Viz with pre-provisioned dashboards | 400m |
| spark-master | bitnamilegacy/spark:3.5 | Cluster manager + ETL driver host | 700m |
| spark-worker-1 | bitnamilegacy/spark:3.5 | Executor host | 1500m |
| spark-worker-2 | bitnamilegacy/spark:3.5 | Executor host | 1500m |
| kafka-1 | bitnamilegacy/kafka:3.7.0 | Broker + controller (KRaft) | 400m |
| kafka-2 | bitnamilegacy/kafka:3.7.0 | Broker + controller (KRaft) | 400m |
| postgres | postgres:16-alpine | Sink table | 400m |
| **total** | | | **~7.6 GB** |

## URLs

| URL | What |
|---|---|
| <http://localhost:3000> | MyST docs (the monitoring lesson) |
| <http://localhost:8888> | JupyterLab on the workspace |
| <http://localhost:3001> | Grafana (admin / admin) |
| <http://localhost:9090> | Prometheus |
| <http://localhost:8080> | Spark master UI |
| <http://localhost:8081> | Spark worker 1 UI |
| <http://localhost:8082> | Spark worker 2 UI |
| `localhost:5432` | Postgres (user `app`, password `app`, db `clicks`) |
| `localhost:19092, 19093` | Kafka bootstrap (from host) |

## Spark Version Caveat

This lab pins **Spark 3.5** (not 4.0 as in the streaming lab). Reason: the `com.xebia.data.spot` `TelemetrySparkListener`, which we use to emit driver-side job/stage spans, supports Spark 3.3–3.5 only. The spot project's README explicitly notes "early development" status; we pin both spot and OTel agent versions in `compose.yml` (jars-init service) so behavior is reproducible across student machines.

## Status

In active development per `/Users/doronnazaretsky/.claude/plans/snappy-bubbling-garden.md`. Step-1 of that plan (this commit): all 12 services come up healthy. Step 2 adds the ETL + producer + CLIs. Step 3 wires the OTel collector pipelines. Step 4 ships the Grafana provisioning + dashboards.
