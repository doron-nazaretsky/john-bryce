#!/usr/bin/env bash
# Post-up init for the Spark lab. Pure docker orchestration — the real logic
# (downloading raw parquet, splitting to daily files, seeding the sandbox,
# converting notebooks) runs inside `spark-jupyter` against the `spark_data`
# named volume. Nothing is written to the student's host disk.
set -euo pipefail

echo "[spark-init] Waiting for Postgres..."
for _ in $(seq 1 30); do
  docker exec spark-postgres pg_isready -U spark -d taxi >/dev/null 2>&1 && break
  sleep 1
done

echo "[spark-init] Waiting for Redis..."
for _ in $(seq 1 30); do
  docker exec spark-redis redis-cli ping 2>/dev/null | grep -q PONG && break
  sleep 1
done

echo "[spark-init] Bootstrapping data (download + split + sandbox seed) inside spark-jupyter..."
docker exec spark-jupyter python /home/jovyan/work/scripts/init_data.py

echo "[spark-init] Converting notebooks (jupytext) inside spark-jupyter..."
docker exec spark-jupyter python /home/jovyan/work/scripts/post_up.py

cat <<EOF

==============================================================
 Spark lab is ready.
   Jupyter (driver):   http://localhost:8888
   Spark driver UI:    http://localhost:4040  (after a job runs)
   Spark master UI:    http://localhost:8080
   Postgres:           localhost:5432  (user=spark pass=spark db=taxi)
   Redis:              localhost:6379
   Producer:           make spark-producer-start / -status / -stop / -reset
==============================================================
EOF
