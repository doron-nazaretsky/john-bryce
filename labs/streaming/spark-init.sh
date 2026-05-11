#!/usr/bin/env bash
# Streaming-lab spark sidecar: runs the Jupyter server that hosts the Spark
# driver/executor (local[*] mode). MyST docs in the `workspace` container
# connect here via http://localhost:8888 from the user's browser. Token defaults
# to `local-dev` to match myst.yml.
set -e

# Spark 4.0's ArtifactManager creates `./artifacts/spark-<uuid>/` on the first
# SparkSession in cwd. When MyST/thebe starts the kernel, Jupyter sets cwd to
# the source MD's directory (e.g. materials/streaming/03-streaming/), which is
# inside MyST's watched tree — the new dir would trigger a full site rebuild
# mid-run and reload the page. Force it out to /tmp via a spark-defaults.conf
# pointed at by SPARK_CONF_DIR.
mkdir -p /tmp/spark-conf /tmp/spark-artifacts /tmp/spark-local
cat > /tmp/spark-conf/spark-defaults.conf <<'EOF'
spark.driver.artifact.localDir /tmp/spark-artifacts
spark.local.dir                /tmp/spark-local
EOF

# Silence Spark's stderr noise so each code-cell shows only the meaningful
# output (DataFrame.show, prints, schemas). Without our own log4j2.properties
# Spark falls back to its bundled defaults (root=INFO) and additionally prints
# "Using Spark's default log4j profile / Setting default log level to WARN"
# straight to stderr. Setting root=ERROR here suppresses NativeCodeLoader,
# ResolveWriteToStream, DAGScheduler, ProcessingTimeExecutor, etc. — keep
# real errors so genuine failures still surface in the cell output.
cat > /tmp/spark-conf/log4j2.properties <<'EOF'
# Status of log4j2's own bootstrap — suppress its startup chatter too.
status = error
name = SparkOverrides

rootLogger.level = error
rootLogger.appenderRef.stdout.ref = console

appender.console.type = Console
appender.console.name = console
appender.console.target = SYSTEM_ERR
appender.console.layout.type = PatternLayout
appender.console.layout.pattern = %d{HH:mm:ss} %-5p %c{1}: %m%n%ex

# Spark's Logging trait prints "Setting default log level to ..." iff it
# detects that log4j2 is still at bundled defaults (isLog4j2DefaultsLoaded
# returns true when no named logger has been overridden). Declaring explicit
# loggers below proves the config is user-provided so Spark stays quiet.
logger.spark.name = org.apache.spark
logger.spark.level = error
logger.sparksql.name = org.apache.spark.sql
logger.sparksql.level = error
logger.streaming.name = org.apache.spark.sql.execution.streaming
logger.streaming.level = error
logger.repl.name = org.apache.spark.repl.Main
logger.repl.level = error
EOF

export SPARK_CONF_DIR=/tmp/spark-conf

exec jupyter server --no-browser --ip=0.0.0.0 --port=8888 \
  --IdentityProvider.token="${JUPYTER_TOKEN:-local-dev}" \
  --ServerApp.allow_origin="http://localhost:3000" \
  --ServerApp.allow_credentials=True \
  --ServerApp.allow_remote_access=True \
  --allow-root
