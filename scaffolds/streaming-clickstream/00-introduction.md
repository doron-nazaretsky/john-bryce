# streaming-clickstream — Introduction

## Getting Started

```bash
make run                  # bring up the cluster (Kafka × 3, Spark master + 2 workers, Jupyter)
make events-start         # start the synthetic pageview producer (in project-streaming-jupyter)
make events-stop          # stop the producer
make events-status        # show event count and producer status
make test                 # run the stage tests
```

Once `make run` is up:

| URL | What |
|---|---|
| <http://localhost:18888> | JupyterLab — open notebooks here (token: `devtoken`) |
| <http://localhost:14040> | Spark Driver UI (only while a query runs) |
| <http://localhost:28080> | Kafka UI (Kafbat) — browse topics, partitions, messages, consumer-group lag |
| `localhost:29092,29093,29094` | Kafka brokers (from the host) |

> Spark runs in `local[*]` mode inside the Jupyter container — there is no
> separate Spark master/workers cluster. The teaching focus here is Kafka and
> Structured Streaming concepts, both of which work identically in local mode.

In-cluster, the brokers are reachable as `project-kafka-1:9092,project-kafka-2:9092,project-kafka-3:9092`.

---

## The Domain

A consumer-facing website emits **pageview** events as users browse:

```json
{
  "user_id": "user-00042",
  "session_id": "sess-91ad",
  "page": "/products/blue-widget",
  "referrer": "/products",
  "ts": "2026-05-03T10:00:00.123Z"
}
```

Events arrive constantly. They want to be:

1. **Ingested** into a durable store (parquet on disk) so analysts can look at history.
2. **Aggregated** in near-real-time as "pageviews per page per 1-minute window" so a dashboard can update every few seconds.

You're going to build the pipeline that does both.

A `scripts/event_generator.py` (provided) emits events at ~50 events/sec when
running in **live mode**, with realistic distributions (Zipf over pages, ~10%
of events with timestamps backdated by 30s–2m to simulate late arrivals). It
also has a **deterministic seed mode** the tests use.

---

## Why You Are Here

This is not a SQL exercise. This is also not a "wire two libraries together"
exercise. The interesting decisions are:

- A producer publishes faster than your consumer can process. What happens?
- The consumer crashes mid-batch. What happens to in-flight records?
- A late event arrives 30 seconds after a window has already closed. What
  happens to the count?
- You restart the windowed query. Do you get duplicate windows? Missing windows?

Each of these has a tool answer (Kafka offsets, Spark checkpoints, watermarks)
*and* a design answer (what guarantee did we commit to? what did we tell the
dashboard team?). We'll separate the two in class.

---

## How the Project Works

Three stages, each with two parts (Part A and Part B). Each part has a test.

```python
# Stage 1A — pipeline/producer.py
def send_event(event: dict) -> None: ...

# Stage 1B — pipeline/consumer.py
def run_consumer(group_id: str, max_records: int) -> list[dict]: ...

# Stage 2A and 2B — pipeline/ingest_job.py
def build_stream(spark, kafka_conf, sink_conf) -> StreamingQuery: ...

# Stage 3A and 3B — pipeline/windowed_job.py
def windowed_counts(spark, kafka_conf, output_path, checkpoint_path) -> StreamingQuery: ...
```

You modify three files: `pipeline/producer.py`, `pipeline/consumer.py`,
`pipeline/ingest_job.py`, and `pipeline/windowed_job.py`. Everything else is
infrastructure.

---

## Project Structure

```
.                                       ← project root
├── 00-introduction.md                  ← you are here
├── stages/                             ← stage-by-stage lessons
│   ├── 01-kafka-basics/
│   ├── 02-spark-ingest/
│   └── 03-windowed-counts/
├── pipeline/
│   ├── config.py                       ← provided — bootstrap servers, paths, group_id
│   ├── producer.py                     ← YOU MODIFY — send_event (stage 1A)
│   ├── consumer.py                     ← YOU MODIFY — run_consumer (stage 1B)
│   ├── ingest_job.py                   ← YOU MODIFY — build_stream (stage 2)
│   └── windowed_job.py                 ← YOU MODIFY — windowed_counts (stage 3)
├── jobs/                               ← spark-submit entrypoints (provided)
│   ├── run_ingest_job.py
│   └── run_windowed_job.py
├── scripts/
│   └── event_generator.py              ← provided — live + deterministic modes
├── tests/                              ← stage tests (provided, don't edit)
├── helpers/
│   └── test_utils.py                   ← provided — kafka admin helpers, parquet readers
└── compose.yml                         ← Kafka × 3 + Spark + Jupyter (mirrors labs/streaming/)
```

You modify four files: `pipeline/{producer,consumer,ingest_job,windowed_job}.py`.

---

## Workflow

1. **Read the stage** — `stages/0N-.../lesson.md` for the contract and the two parts.
2. **Implement Part A** — usually a small function or query.
3. **Test Part A** — `pytest tests/test_stageN.py::test_part_a -v`
4. **Implement Part B** — extends Part A.
5. **Test Part B** — `pytest tests/test_stageN.py::test_part_b -v`
6. **Run for real** — start the producer, run the job, watch it in the Spark UI.

---

## Test Commands

| Command | Runs |
|---|---|
| `make test` | all stage tests |
| `docker exec project-streaming-jupyter pytest tests/test_stage1.py -v` | stage 1 only |
| `docker exec project-streaming-jupyter pytest tests/test_stage2.py -v` | stage 2 only |
| `docker exec project-streaming-jupyter pytest tests/test_stage3.py -v` | stage 3 only |

Tests call your functions as black boxes. They reset Kafka topics and parquet
output directories between tests so state never leaks.

---

## Submission

This project is scoped across the three streaming sessions. You'll start it
in class and finish it individually. Submit:

- Your `pipeline/` directory.
- A short `DESIGN.md` covering: which delivery guarantee you chose for the
  consumer, what watermark threshold you picked and why, how you verified
  the checkpoint-based recovery in Stage 2B.
- `make test` passing against your code.
