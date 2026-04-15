# Spark Lab — Instructor Notes

Student-facing docs deliberately avoid naming storage technologies. The
picks (Postgres for the analyst store, Redis for the serving store, the
file-tracking strategy, etc.) emerge from class discussion and are captured
in `class-discussion-points.md` — which is **git-ignored during the class**
and **committed after the class ends** so students can reference what was
decided.

This file is for you: what the lab is actually testing, how the harness works,
and what to watch for when students get stuck.

---

## What Each Stage Is Really About

| Stage | Surface problem | Underlying teaching point |
|---|---|---|
| 01 Exploration | "look at the data" | Confront the two wildly different scales: landing-side throughput (≈1.8M rows/min) vs analyst-grain ceiling (≈2.3M rows/year). Sets up why Spark earns its keep only on the landing side. |
| 02 Incremental ingest | "don't double-process files" | File-tracking strategies: ingest-log table vs bucket isolation (`landing/→in_process/→archive/\|errors/`). Atomicity of rename vs DB write. Single-writer invariant. |
| 03 Analyst store + idempotency | "writes converge under retry" | Separate incrementality (don't reprocess) from idempotency (writes are replay-safe). Teach delete-insert-at-batch-grain vs UPSERT. |
| 04 Backend serving | "ms budget, not index-tuning" | Hot store for pre-computed, very-low-cardinality answers. Consistency with the analyst store. |
| 05 Bonus | "maintain the hot answer directly" | Additivity ≠ idempotency. Requires an explicit dedupe guard. |

---

## Per-Stage Student Deliverables

| Stage | Student edits | Test command |
|---|---|---|
| 01 | `notebooks/00-exploration.ipynb` (just to explore) | none |
| 02 | `pipeline/etl.py::run_etl` | `pytest tests/test_stage2_incrementality.py` |
| 03 | `pipeline/etl.py::run_etl`, `pipeline/serving.py::total_revenue` | `pytest tests/test_stage3_idempotency.py` |
| 04 | `pipeline/serving.py::avg_revenue` (and likely `run_etl` too) | `pytest tests/test_stage4_latency.py` |
| 05 | Same files, open-ended | same as 04 |

Only two files are edited across the whole project:
`pipeline/etl.py` and `pipeline/serving.py`.

---

## How the Tests Work

- **Session-scoped `SparkSession`**: one per pytest run, `local[2]` master.
  Fast, and avoids the cost of talking to the standalone cluster in tests.
  (The scheduler still uses `spark-submit` against the cluster for the live
  lab run — tests are intentionally simpler.)
- **`connections` fixture**: wipes the Postgres `public` schema (drops +
  recreates) and `FLUSHDB`s Redis before each test, so student schemas don't
  leak between tests. The harness does not know or care what the student
  created — it just reaches in and resets.
- **Landing dir per test**: a fresh tmp dir, seeded with hand-built parquet
  fixtures via `helpers.test_utils.write_day_fixture`.
- **Latency helper**: `median_latency(fn, trials=N, warmup=1)` — one warmup
  call, then median over N trials. Survives the noisy first call (JIT, pool
  warmup, connection setup).

Running tests:

```bash
make test-spark
# or granular:
docker exec spark-jupyter pytest tests/ -v
```

---

## The Scheduler and `spark-submit`

`pipeline/scheduler.py` is the shape we want students to see — spark-submit
per tick, not a long-running driver. JVM cold-start (~5-10s) is acceptable
inside a 60s window and is the realistic production mode.

Single-writer is enforced by a pidfile lock; if a tick fires while the
previous submit is still running, the tick is skipped rather than stacked.
In production this would be Airflow sensors / K8s `concurrencyPolicy=Forbid`
/ a cluster queue — talk to that during the single-writer discussion.

To see it live:

```bash
docker exec -it spark-jupyter python -m pipeline.scheduler
```

Let it run for 3 minutes. Each tick should pick up ~6 new files.

---

## Common Student Issues

| Symptom | Likely cause |
|---|---|
| Stage 2 test passes but stage 3 fails | Student has file-dedup but not write-idempotency. Steer toward delete-insert-by-batch or UPSERT. |
| Stage 3 `total_revenue` is 2× expected on second run | Same thing, louder. |
| Stage 4 latency failure at ~200ms | Student is computing `avg_revenue` from the analyst store every call. Talk about cardinality (24 rows), serving-store shape. |
| Tests flake on latency | Laptop under load. Re-run. If chronic, raise the budget in `test_stage4_latency.py`. |
| `NotImplementedError` at import time | They haven't started the stage yet (expected). |
| Data missing in landing | `spark-producer` exited (ran out of files) or `data/days/` is empty. Check `docker logs spark-producer`. |

---

## When to Commit `class-discussion-points.md`

The file is in `.gitignore`. After the class concludes and the decisions are
real, remove the entry from `.gitignore` and commit. Students who come back
to the repo later will then see the rationale behind every choice.
