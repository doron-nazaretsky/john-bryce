#!/usr/bin/env bash
# Post-up init for the Spark lab.
# Creates Postgres schema for Exercise B and the Mongo db/collection for Exercise C.
# Idempotent: safe to re-run.
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[spark-init] Populating spark_data volume (one-time copy of raw parquet + zones.csv)..."
# Populate the named volume from host ./data/ exactly once. Subsequent runs skip the
# copy if the marker file is present. docker cp streams via tar — no bind-mount
# perf penalty on Windows/Mac. After this, all Spark I/O happens on Docker-VM disk.
if ! docker exec spark-jupyter test -f /home/jovyan/work/data/.populated; then
  if [ ! -d "$LAB_DIR/data/raw" ] || [ -z "$(ls -A "$LAB_DIR/data/raw" 2>/dev/null)" ]; then
    echo "ERROR: $LAB_DIR/data/raw is empty. Run 'make data-spark' first." >&2
    exit 1
  fi
  # Fresh named volumes come up root-owned; chown to jovyan so the rest runs unprivileged.
  docker exec -u root spark-jupyter bash -c 'mkdir -p /home/jovyan/work/data/raw && chown -R jovyan:users /home/jovyan/work/data'
  docker cp "$LAB_DIR/data/raw/." spark-jupyter:/home/jovyan/work/data/raw/
  [ -f "$LAB_DIR/data/zones.csv" ] && \
    docker cp "$LAB_DIR/data/zones.csv" spark-jupyter:/home/jovyan/work/data/zones.csv
  docker exec -u root spark-jupyter bash -c 'chown -R jovyan:users /home/jovyan/work/data'
  docker exec spark-jupyter bash -c 'touch /home/jovyan/work/data/.populated'
  echo "[spark-init] Volume populated with raw parquet + zones.csv."
else
  echo "[spark-init] spark_data volume already populated; skipping copy."
fi

# Always (re)build tier symlink directories. Cheap (ln -s), idempotent, and lets us
# change tier composition (e.g. small = 2 files for better parallelism) without
# requiring students to drop the named volume.
echo "[spark-init] (Re)building tier symlinks: small, medium, large..."
docker exec spark-jupyter bash -c '
  set -e
  cd /home/jovyan/work/data
  build_tier() { local t="$1"; shift; rm -rf "$t"; mkdir "$t"; for m in "$@"; do ln -s "../raw/yellow_tripdata_2019-${m}.parquet" "$t/"; done; }
  build_tier small  01 02
  build_tier medium 01 02 03 04
  build_tier large  01 02 03 04 05 06 07 08 09 10 11 12
'

echo "[spark-init] Generating .ipynb from MyST .md sources via jupytext..."
# Source of truth is notebooks/*.md (readable, diffable, AI-editable).
# The .ipynb files are build artifacts — regenerated on every lab-up, gitignored.
docker exec -i spark-jupyter bash -c '
  set -e
  cd /home/jovyan/work/notebooks
  for md in *.md; do
    ipynb="${md%.md}.ipynb"
    if [ ! -f "$ipynb" ] || [ "$md" -nt "$ipynb" ]; then
      jupytext --quiet --to ipynb "$md"
    fi
  done
'

echo "[spark-init] Waiting for Postgres to be ready..."
for i in $(seq 1 30); do
  if docker exec spark-postgres pg_isready -U spark -d taxi >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[spark-init] Creating Postgres schema (zone_daily_stats, hourly_demand)..."
docker exec -i spark-postgres psql -U spark -d taxi <<'SQL'
CREATE TABLE IF NOT EXISTS zone_daily_stats (
    zone_id       INT      NOT NULL,
    stat_date     DATE     NOT NULL,
    trip_count    BIGINT   NOT NULL,
    total_revenue NUMERIC(14,2) NOT NULL,
    avg_tip_pct   NUMERIC(6,3),
    PRIMARY KEY (zone_id, stat_date)
);

CREATE TABLE IF NOT EXISTS hourly_demand (
    zone_id INT    NOT NULL,
    hour    INT    NOT NULL CHECK (hour BETWEEN 0 AND 23),
    trips   BIGINT NOT NULL,
    PRIMARY KEY (zone_id, hour)
);
SQL

echo "[spark-init] Waiting for MongoDB to be ready..."
for i in $(seq 1 30); do
  if docker exec spark-mongo mongosh --quiet --eval "db.adminCommand('ping').ok" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[spark-init] Creating MongoDB taxi.zone_profiles collection..."
docker exec -i spark-mongo mongosh --quiet <<'JS'
const db = db.getSiblingDB('taxi');
if (!db.getCollectionNames().includes('zone_profiles')) {
  db.createCollection('zone_profiles');
}
JS

cat <<EOF

==============================================================
 Spark lab is ready.
   Jupyter (driver):   http://localhost:8888
   Spark driver UI:    http://localhost:4040  (after a job runs)
   Spark master UI:    http://localhost:8080
   Postgres:           localhost:5432  (user=spark pass=spark db=taxi)
   MongoDB:            localhost:27017 (db=taxi coll=zone_profiles)
   Base workspace:     http://localhost:8889  (MyST docs on :3000)
==============================================================
EOF
