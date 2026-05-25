#!/usr/bin/env bash
# Boots the long-running ETL daemon inside spark-master.
#
# Invoked by `spark batch start` (workspace CLI) via:
#   docker exec -d spark-master bash /workspace/labs/monitoring/etl/start_daemon.sh
#
# Writes its own pid to ${PID_FILE} so `spark batch stop` can SIGTERM it
# cleanly. spark-submit is called in client mode; the spark-submit process IS
# the driver, so killing it terminates the daemon and releases the cluster.
set -u

PID_FILE="${PID_FILE:-/var/log/etl/spark-batch-daemon.pid}"
# Structured-streaming knobs — the daemon reads these from env. The checkpoint
# dir is on its own volume (NOT under /var/log/etl, which the OTel filelog
# receiver tails — binary checkpoint files would confuse it).
CHECKPOINT_DIR="${CHECKPOINT_DIR:-/var/lib/spark-checkpoints/clicks}"
WATERMARK_DELAY="${WATERMARK_DELAY:-30 seconds}"
WINDOW_SIZE="${WINDOW_SIZE:-30 seconds}"
TRIGGER_INTERVAL="${TRIGGER_INTERVAL:-10 seconds}"
export CHECKPOINT_DIR WATERMARK_DELAY WINDOW_SIZE TRIGGER_INTERVAL
# spark-submit runs as root inside spark-master, but the JVM executors on
# worker containers run as user `spark`. Make the checkpoint tree writable
# for both so the state-store can mkdir from any role.
mkdir -p "${CHECKPOINT_DIR}"
chmod -R 0777 "$(dirname "${CHECKPOINT_DIR}")"

OTEL_AGENT="/opt/otel-jars/opentelemetry-javaagent.jar"
SPOT_JAR="/opt/otel-jars/spot-complete.jar"
COLLECTOR="${OTEL_COLLECTOR_HTTP:-http://otel-collector:4318}"

# ── OTel agent tuning ──────────────────────────────────────────────────────
# Disable instrumentation modules we definitely don't use. Cuts boot-time
# bytecode rewriting and runtime span volume substantially. We keep:
#   * kafka          — the data source
#   * jdbc           — postgres writes (when spark uses the JDBC source)
#   * jetty/servlet  — Spark UI HTTP
#   * runtime-telemetry — JVM memory/GC/thread metrics
DISABLES=" \
  -Dotel.instrumentation.mongo.enabled=false \
  -Dotel.instrumentation.cassandra.enabled=false \
  -Dotel.instrumentation.elasticsearch.enabled=false \
  -Dotel.instrumentation.redis.enabled=false \
  -Dotel.instrumentation.lettuce.enabled=false \
  -Dotel.instrumentation.jedis.enabled=false \
  -Dotel.instrumentation.aws-sdk.enabled=false \
  -Dotel.instrumentation.akka-actor.enabled=false \
  -Dotel.instrumentation.akka-http.enabled=false \
  -Dotel.instrumentation.play-mvc.enabled=false \
  -Dotel.instrumentation.vertx.enabled=false \
  -Dotel.instrumentation.netty.enabled=false \
  -Dotel.instrumentation.spring-webmvc.enabled=false \
  -Dotel.instrumentation.spring-webflux.enabled=false \
  -Dotel.instrumentation.grpc.enabled=false \
  -Dotel.instrumentation.couchbase.enabled=false \
  -Dotel.instrumentation.hibernate.enabled=false \
"

DRIVER_OPTS="-javaagent:${OTEL_AGENT} -Dotel.exporter.otlp.protocol=http/protobuf -Dotel.exporter.otlp.endpoint=${COLLECTOR} -Dotel.service.name=spark-driver -Dotel.metric.export.interval=15000${DISABLES}"
EXECUTOR_OPTS="-javaagent:${OTEL_AGENT} -Dotel.exporter.otlp.protocol=http/protobuf -Dotel.exporter.otlp.endpoint=${COLLECTOR} -Dotel.service.name=spark-executor -Dotel.metric.export.interval=15000${DISABLES}"

mkdir -p /var/log/etl
echo $$ > "${PID_FILE}"

exec /opt/bitnami/spark/bin/spark-submit \
  --master "spark://spark-master:7077" \
  --deploy-mode client \
  --name "etl-daemon" \
  --packages "org.postgresql:postgresql:42.7.4,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0" \
  --jars "${SPOT_JAR}" \
  --conf "spark.jars.ivy=/tmp/.ivy2" \
  --conf "spark.extraListeners=com.xebia.data.spot.TelemetrySparkListener" \
  --conf "spark.driver.extraJavaOptions=${DRIVER_OPTS}" \
  --conf "spark.executor.extraJavaOptions=${EXECUTOR_OPTS}" \
  --conf "spark.driver.artifact.localDir=/tmp/spark-artifacts" \
  --conf "spark.local.dir=/tmp/spark-local" \
  /workspace/labs/monitoring/etl/etl_daemon.py
