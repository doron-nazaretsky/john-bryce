# Bring Up The Lab

This is the one place you'll touch the command line for setup. After this, everything happens inside Grafana and the workspace CLIs.

## Prereq — bump Docker Desktop to 8 GB

Docker Desktop on Mac and Windows ships with a 4 GB memory ceiling. **The lab needs ~7.6 GB.** Without the bump, services will OOM-kill silently (Spark workers tend to go first), and you'll spend an hour debugging phantom failures.

```
Docker Desktop → Settings → Resources → Memory → 8 GB → Apply & Restart
```

On Linux there is no such ceiling — Docker uses the host directly. Just make sure you have 8 GB free.

## Bring it up

From the repository root:

```bash
make lab-monitoring
```

This runs:

```
docker compose -f labs/base/compose.yml -f labs/monitoring/compose.yml up -d --build
```

First boot takes ~4 minutes — Docker pulls images, the jar-prep init container builds the spot SparkListener from source, the Kafka cluster forms, healthchecks settle. Subsequent boots are ~30 seconds.

## What "healthy" looks like

```bash
docker compose -f labs/base/compose.yml -f labs/monitoring/compose.yml ps
```

You should see 10 containers, all with status `Up ... (healthy)`. If any are `restarting` or `unhealthy`:

| Service | Healthy when | Common cause if not |
|---|---|---|
| kafka-1 / kafka-2 | KRaft quorum formed | Not enough memory — bump Docker to 8 GB |
| spark-master | port 8080 responds | jar-prep container hasn't finished — wait |
| spark-worker-* | registered with master | Master not healthy yet — wait |
| otel-collector | port 13133 responds | Collector won't start — almost always a YAML typo |
| prometheus / loki / tempo | `/ready` returns 200 | Disk full or healthcheck timing |
| grafana | `/api/health` returns 200 | Provisioning files have a YAML error |

## URLs

| URL | What it is |
|---|---|
| http://localhost:3000 | MyST documentation (this site) |
| http://localhost:8888 | JupyterLab — open notebooks under `notebooks/` |
| http://localhost:3001 | **Grafana** — where you live for the rest of the lab. No login needed. |
| http://localhost:9090 | Prometheus — useful for direct PromQL verification |
| http://localhost:8080 | Spark master UI |

If you're already signed in to a Grafana from a different lab, force a hard refresh (Cmd-Shift-R) once when you first open localhost:3001.

## Smoke test — is everything talking?

```bash
docker exec workspace producer start          # start the click event producer
docker exec workspace spark batch start       # start the long-running streaming ETL
sleep 30
docker exec workspace spark batch status      # should show daemon=running + last batch OK
```

Verify rows landed:

```bash
docker exec postgres psql -U app -d clicks -c \
  "SELECT count(*), max(updated_at) FROM aggregated_clicks"
```

Within 60–90 seconds you should see > 0 rows. If you do, every part of the pipeline is connected — Kafka → Spark → Postgres, plus OTel pulling metrics from all three.

## Tearing down

```bash
make down
```

Stops and removes the containers but keeps named volumes (Kafka topics, Postgres tables, Tempo/Loki data, the built spot jar). To wipe volumes too, `docker volume ls | grep monitoring` and remove them with `docker volume rm`.

Next: the ETL pipeline you just brought up.
