#!/usr/bin/env bash
# Download NYC TLC Yellow Taxi 2019 parquet (12 months) + zone lookup CSV,
# write SHA256 checksums, then build tiered slices (small / medium / large)
# inside the spark-jupyter container.
#
# Run once as pre-class homework: `make data-spark`. Slow on first run (~2-3 GB).
set -euo pipefail

LAB_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$LAB_DIR/data"
RAW_DIR="$DATA_DIR/raw"
mkdir -p "$RAW_DIR"

BASE_URL="https://d37ci6vzurychx.cloudfront.net"

human_size() {
  # Portable human-readable byte size (MacOS/BSD + GNU).
  local bytes=$1
  awk -v b="$bytes" 'BEGIN{
    split("B KB MB GB TB", u); s=1;
    while (b>=1024 && s<5){ b=b/1024; s++ }
    printf (s==1 ? "%d %s" : "%.1f %s"), b, u[s]
  }'
}

file_bytes() {
  # stat flag differs between GNU and BSD.
  stat -c%s "$1" 2>/dev/null || stat -f%z "$1"
}

echo "[data-spark] Downloading 12 months of Yellow Taxi 2019 parquet to $RAW_DIR ..."
total_files=12
idx=0
for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  idx=$((idx+1))
  f="yellow_tripdata_2019-${m}.parquet"
  if [ -f "$RAW_DIR/$f" ]; then
    size=$(human_size "$(file_bytes "$RAW_DIR/$f")")
    printf "  [%2d/%d] %s (cached, %s)\n" "$idx" "$total_files" "$f" "$size"
  else
    printf "  [%2d/%d] %s ... " "$idx" "$total_files" "$f"
    # -# gives a progress bar; redirect so bar appears on its own line below the prefix
    echo
    curl -fL --progress-bar -o "$RAW_DIR/$f" "$BASE_URL/trip-data/$f"
    size=$(human_size "$(file_bytes "$RAW_DIR/$f")")
    printf "         downloaded %s\n" "$size"
  fi
done

total_raw=$(du -sh "$RAW_DIR" 2>/dev/null | awk '{print $1}')
echo "[data-spark] Raw parquet total: ${total_raw:-unknown}"

echo "[data-spark] Downloading taxi zone lookup..."
if [ -f "$DATA_DIR/zones.csv" ]; then
  echo "  - zones.csv (cached, $(human_size "$(file_bytes "$DATA_DIR/zones.csv")"))"
else
  curl -fL --progress-bar -o "$DATA_DIR/zones.csv" "$BASE_URL/misc/taxi_zone_lookup.csv"
  echo "  - zones.csv ($(human_size "$(file_bytes "$DATA_DIR/zones.csv")"))"
fi

echo "[data-spark] Writing SHA256 checksums to CHECKSUMS.txt..."
(
  cd "$DATA_DIR"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum raw/*.parquet zones.csv > CHECKSUMS.txt
  else
    shasum -a 256 raw/*.parquet zones.csv > CHECKSUMS.txt
  fi
)

echo "[data-spark] Raw parquet + zones.csv ready on host. Tiered slices (small/medium/large)"
echo "[data-spark] are built inside the spark_data Docker volume by lab-spark's init.sh"
echo "[data-spark] (avoids slow Windows/Mac bind-mount reads during Spark jobs)."

grand_total=$(du -sh "$DATA_DIR" 2>/dev/null | awk '{print $1}')
echo "[data-spark] Done. Host data footprint: ${grand_total:-unknown}"
echo "[data-spark] Next: run 'make lab-spark' — raw parquet will be copied into the"
echo "              spark_data volume once, and small/medium/large tiers built inside it."
