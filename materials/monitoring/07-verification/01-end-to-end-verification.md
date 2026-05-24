# End-to-End Verification (Instructor Checklist)

**This page is for the instructor, run before class. Do not ship to students during the lesson.**

The whole module rests on cross-signal correlation working end-to-end. If any step below fails, the wow moments don't land. Each item should take under 30 seconds; the entire checklist should run in under 5 minutes.

## Stack health

```bash
make lab-monitoring
docker compose -f labs/base/compose.yml -f labs/monitoring/compose.yml ps
```

- [ ] All 12 containers show `Up ... (healthy)`. The collector shows just `Up` (distroless, no shell-based healthcheck — that's expected).

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:9090/-/healthy
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3001/api/health
docker exec grafana wget -qO- http://loki:3100/ready
docker exec grafana wget -qO- http://tempo:3200/ready
```

- [ ] All return 200 / "ready".

## Data flow

```bash
docker exec workspace producer start
docker exec workspace spark batch start
sleep 90
docker exec workspace spark batch status
docker exec workspace producer status
docker exec postgres psql -U app -d clicks -tAc "SELECT count(*), max(updated_at) FROM aggregated_clicks"
```

- [ ] `spark batch status` shows `daemon=running` and `state=ok` with a recent batch_id.
- [ ] `producer status` shows `running=true` and `total_sent > 5000`.
- [ ] Postgres row count > 0.

## Signals reaching backends

```bash
# Prometheus — should have ~400 metric names
curl -s 'http://localhost:9090/api/v1/label/__name__/values' \
  | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["data"]))'

# Loki — should list etl + spark-* services
docker exec grafana wget -qO- 'http://loki:3100/loki/api/v1/label/service_name/values'

# Tempo — should have an etl_batch trace with batch_id
docker exec grafana wget -qO- 'http://tempo:3200/api/search?q=%7B%20.batch_id%21%3D%22%22%20%7D&limit=1' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('traces:', len(d.get('traces',[])))"
```

- [ ] Prom has ~400 metric names.
- [ ] Loki lists at minimum `etl` and `spark-driver`.
- [ ] Tempo returns ≥ 1 trace with batch_id.

## Grafana dashboards

In browser, http://localhost:3001/dashboards. Open each:

- [ ] **00 Overview** — Last batch stat is green (INFO), Producer rate > 0, Consumer lag green, Postgres write rate > 0, throughput timeseries has lines, log stream has entries.
- [ ] **10 Kafka** — Brokers alive = 2 (green), clicks partitions = 4, max lag green, per-partition timeseries has 4 lines.
- [ ] **20 Spark** — Live executors = 2 (green), driver heap < 70%, GC < 1s/min, executor heap timeseries has at least two host lines.
- [ ] **30 Postgres** — aggregated_clicks rows > 0, write rate > 0, commits/sec > 0, write-ops bar chart has bars.
- [ ] **40 ETL Business** — Batches succeeded > 0, batch outcomes bar chart has green bars, log stream populated.

Within 2 minutes of bring-up, all dashboards should be populated. If any panel says "No Data", read its query — the metric label names sometimes drift (e.g., `postgresql_table_name` is schema-qualified as `"public.aggregated_clicks"`).

## Cross-signal correlation

This is the **non-negotiable** part. If either direction fails the lesson doesn't land.

**Loki → Tempo:**

1. Explore → Loki → `{service_name="etl"} |= "batch done"`.
2. Expand the most recent row.
3. There's a button "View traces for batch" at the bottom.
4. Click → splits to Tempo with a trace search returning the matching `etl_batch` span.
5. Click the trace → the etl_batch span shows the same `batch_id` attribute.

- [ ] Loki → Tempo derived field renders and pivots correctly.

**Tempo → Loki:**

1. Open the `etl_batch` span from step 5 above.
2. Click "Logs for this span" (top-right of the span panel).
3. Loki opens with a query filter for that exact batch_id.
4. The log lines for that batch are visible.

- [ ] Tempo → Loki tracesToLogsV2 link works.

## Three scenarios

For each: trigger, observe the expected deltas (within 60–90 seconds), recover.

**Scenario A:** `docker exec workspace producer rate 5` → kafka lag rises, batch durations grow → `producer rate 1` → lag drains.

- [ ] Lag visibly rose and recovered.

**Scenario B:** `docker exec workspace producer inject-bad 100` → WARN line in Loki within next batch, drop count > 0 on 40 dashboard.

- [ ] WARN observed, dropped-count stat increments.

**Scenario C:** `docker kill spark-worker-1` → executor count drops to 1 within 30s → next batch takes longer (visible in Tempo) → `docker start spark-worker-1` → executor count returns to 2.

- [ ] Executor count dropped and recovered, slower batch visible in Tempo.

## What to clean up between sessions

Cleanest reset between groups (preserves built jars but clears all data):

```bash
docker compose -f labs/base/compose.yml -f labs/monitoring/compose.yml down
docker volume rm monitoring_kafka-1-data monitoring_kafka-2-data \
                 monitoring_postgres-data monitoring_loki-data \
                 monitoring_tempo-data monitoring_prometheus-data \
                 monitoring_etl-logs 2>/dev/null
make lab-monitoring
```

(Volume names depend on your Compose project name — `docker volume ls | grep monitoring` to confirm.)

A full image rebuild is rarely needed; only if Kafka or Postgres image versions changed.

## When something fails

The verification rubric above tells you *what* is broken, not *why*. The debugging recipe:

- **Container unhealthy**: `docker logs <container> --tail 50`. Look for the first error.
- **Metrics missing in Prometheus**: hit `/api/v1/label/__name__/values`. If kafka_* missing, the kafkametrics receiver isn't connecting (check OTel collector logs for "connection refused" — almost always Kafka still booting).
- **Logs missing in Loki**: check the OTel collector's filelog operator is finding `/var/log/etl/etl.log`. The volume mount `etl-logs` must be shared between spark-master and otel-collector.
- **Traces missing in Tempo**: check the OTel collector logs for OTLP receive errors. The Spark JVMs must be configured for `http/protobuf` on port 4318 (not gRPC 4317).
- **Cross-signal links not rendering**: hard refresh Grafana (Cmd-Shift-R). Provisioning sometimes races on a cold start.

Last: have the demo plan in your head. Each scenario has a recovery step; doing them in order without thinking is how you avoid awkward silences during class.
