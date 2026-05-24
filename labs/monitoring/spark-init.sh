#!/usr/bin/env bash
# Spark sidecar entrypoint (master or worker).
#
# The bitnamilegacy/spark:3.5 image's default entrypoint is /opt/bitnami/scripts/spark/run.sh,
# which reads SPARK_MODE and starts the matching daemon. We wrap it to do two
# things first that aren't in the image:
#
#   1. Install Python OTel SDK + instrumentation packages so the PySpark driver
#      (which we spark-submit into this container) can do its single manual
#      etl_batch span + LoggingInstrumentor enrichment. Plan forbids a custom
#      Spark Dockerfile, so install-at-startup is the alternative.
#
#   2. Configure spark-defaults.conf with the artifact-redirect to /tmp
#      (mirroring the streaming lab's spark-init.sh) so PySpark's
#      ArtifactManager doesn't dump UUIDs into the mounted /workspace tree.
#
# After that, exec the original bitnami entrypoint with whatever args the
# compose command line gave us (we ignore $1=master|worker, the image reads
# SPARK_MODE from env).

set -e

ROLE="${1:-master}"
echo "[spark-init] role=${ROLE}"

# ── Python deps for the driver + executors ──────────────────────────────────
# - psycopg          : per-partition Postgres upsert (executors + driver)
# - opentelemetry-*  : driver-only, used to emit ONE manual span per batch
#                      tagged with batch_id. This is the universal cross-
#                      signal pivot: spot's job/stage spans don't carry
#                      batch_id (verified during step-5 verification), and
#                      the long-running daemon can't bake it into the JVM
#                      resource attrs. The manual span fills that gap.
python3 -m pip install --quiet --root-user-action=ignore \
  'psycopg[binary]>=3.1,<4' \
  'opentelemetry-api>=1.27,<2' \
  'opentelemetry-sdk>=1.27,<2' \
  'opentelemetry-exporter-otlp-proto-http>=1.27,<2' \
  'opentelemetry-instrumentation-logging>=0.48b0,<1' \
  || echo "[spark-init] WARN: pip install failed (will retry on next batch)"

# ── spark-defaults.conf — artifact redirect to /tmp ──────────────────────────
# Same rationale as labs/streaming/spark-init.sh: Spark's ArtifactManager
# creates ./artifacts/spark-<uuid>/ in cwd. cwd is /workspace (mounted), and
# /workspace is watched by MyST in the workspace container; new dirs trigger
# a MyST rebuild. Force out to /tmp.
# Structured-streaming checkpoint dir is shared between driver (master) and
# executors (workers). The bitnami entrypoint switches to user `spark` before
# starting the JVM, so the root-owned named-volume mount is unwritable for the
# state-store mkdir from executors. Chmod here while we still run as root.
if [ -d /var/lib/spark-checkpoints ]; then
  chmod 0777 /var/lib/spark-checkpoints
fi

mkdir -p /tmp/spark-conf /tmp/spark-artifacts /tmp/spark-local
cat > /tmp/spark-conf/spark-defaults.conf <<'EOF'
spark.driver.artifact.localDir /tmp/spark-artifacts
spark.local.dir                /tmp/spark-local
EOF
export SPARK_CONF_DIR=/tmp/spark-conf

# ── Hand off to bitnami's entrypoint ─────────────────────────────────────────
# /opt/bitnami/scripts/spark/run.sh reads SPARK_MODE and starts the matching
# daemon (master or worker). SPARK_DAEMON_JAVA_OPTS already carries the OTel
# java agent attachment from compose.yml.
exec /opt/bitnami/scripts/spark/entrypoint.sh /opt/bitnami/scripts/spark/run.sh
