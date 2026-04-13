# Spark Lab — NYC Taxi Analytics Platform

Hands-on 4-hour Spark session: write real SparkSQL against NYC TLC Yellow Taxi 2019 data, observe parallelism in the Spark UI, and build a mini ETL pipeline that lands aggregates in Postgres and document profiles in MongoDB.

## Why this lab is different

Most labs in this repo are MyST lessons rendered on port 3000 with executable cells against the shared Jupyter on :8888. **The Spark lab is deliberately an exception.** Students work directly in `.ipynb` notebooks inside a dedicated driver container (`spark-jupyter`) so:

- They write code, not just run it.
- The driver lives next to the executors with the right JARs on its classpath.
- The Spark Driver UI on :4040 is a first-class teaching surface tied to that driver.

The base `workspace` container still runs (its Jupyter is moved to host port **8889**) so MyST docs on :3000 remain available for reference.

## Prerequisites

- Docker Desktop with at least **6 GB** allocated (8 GB is comfortable).
- Repo cloned to a path **without spaces** (Windows Docker Desktop bind-mount edge case).
- ~3 GB of free disk for the TLC parquet files.

## One-time setup (pre-class)

```bash
make data-spark      # downloads 12 monthly parquet files + zone lookup,
                     # writes data/CHECKSUMS.txt, builds tiered slices
                     # under data/{small,medium,large}/. Slow first run.
```

`data-spark` requires `lab-spark` to be running (it shells into `spark-jupyter` to build the tiers). Sequence on a fresh machine:

```bash
make lab-spark       # bring everything up
make data-spark      # download + tier
```

After tiers exist on disk you can `make reset` and re-`make lab-spark` freely without re-downloading.

## Running the lab

```bash
make lab-spark
```

Brings up six containers and runs `init.sh` to create the Postgres schema and Mongo collection.

| URL | What |
|---|---|
| <http://localhost:8888> | JupyterLab (the Spark driver) — open this for the lesson |
| <http://localhost:4040> | Spark Driver UI (only while a SparkSession is alive) |
| <http://localhost:8080> | Spark Master UI — workers, cores, application history |
| <http://localhost:3000> | MyST docs (base workspace) |
| <http://localhost:8889> | Base workspace Jupyter (rarely needed) |
| `localhost:5432` | Postgres — `spark` / `spark` / db `taxi` |
| `localhost:27017` | MongoDB — db `taxi`, collection `zone_profiles` |

## Notebook order

1. `notebooks/00-warmup.ipynb` — connect, UI tour, narrow vs wide.
2. `notebooks/01-exercise-a.ipynb` — exploratory SparkSQL → partitioned parquet.
3. `notebooks/02-exercise-b.ipynb` — aggregates → Postgres (the JDBC parallel-write moment).
4. `notebooks/03-exercise-c.ipynb` — nested zone profile docs → MongoDB.
5. `notebooks/04-exercise-d.ipynb` — *the mystery slow query* (in-session stretch task).
6. `notebooks/instructor-skew-demo.ipynb` — instructor companion for D.
7. `notebooks/instructor-spark-submit.ipynb` — instructor walkthrough of `spark-submit`.
8. `notebooks/bonus-cache.ipynb` — homework / fast-finisher.

Each exercise is independent — A / B / C all read from the shared `data/` tiers, none depend on the previous notebook's output.

## Validators

`helpers.validators` exposes one validator per exercise:

```python
from helpers import validate_exercise_a, validate_exercise_b, validate_exercise_c, validate_exercise_d
```

Property checks (row counts, column shapes, non-null grouping keys, plausible numeric ranges) — not exact-value checks.

## Troubleshooting

- **Driver UI 4040 returns nothing** — only available while a `SparkSession` is open. Run a notebook cell that builds one.
- **`spark-jupyter` exits or restarts** — usually OOM. Confirm the driver memory in the SparkSession builder is `1g` (default in the notebooks) and Docker Desktop has at least 6 GB.
- **`Connection refused` to Postgres / Mongo** — they are reachable from inside the cluster as `spark-postgres` / `spark-mongo` (service names), not `localhost`. From the host use `localhost:5432` / `localhost:27017`.
- **Parquet read fails: file not found** — paths in notebooks are relative to `/home/jovyan/work` inside the container. Run `make data-spark` first.
- **Skew query won't show skew** — Exercise D pins `spark.sql.adaptive.enabled=false`. Don't reuse a SparkSession from another notebook that left AQE on.

## Version pins

See comments in `Dockerfile.jupyter` for why each version is what it is. Summary:

| Component | Version |
|---|---|
| Spark | 3.5.1 (Bitnami) |
| Python (driver + executors) | 3.11 |
| Postgres JDBC | 42.7.3 |
| Mongo Spark Connector | `_2.12:10.4.1` |
| Postgres server | `postgres:16-alpine` |
| MongoDB server | `mongo:7` |
