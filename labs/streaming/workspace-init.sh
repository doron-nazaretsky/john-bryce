#!/usr/bin/env bash
# Streaming-lab override: workspace runs MyST docs only. The Jupyter kernel that
# executes the lesson's `{code-cell}` blocks lives in the `spark` sidecar — see
# labs/streaming/spark-init.sh. Splitting them keeps Spark's JVM memory budget
# isolated from the Node-based MyST server.
set -e

myst clean --all --yes
HOST=0.0.0.0 exec myst start --keep-host --port 3000 --server-port 3100
