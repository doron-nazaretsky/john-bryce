"""Long-running PySpark Structured Streaming ETL.

One Python process, one streaming query. Spark manages offsets via the
checkpoint directory; we do not. The query reads `clicks` from Kafka, applies
a watermark on event_time, groups by tumbling window x product_id, and counts.
Each micro-batch's *update* (rows whose count changed) is written to Postgres
via foreachBatch using a REPLACE upsert — idempotent under replay because
Spark replays the same epoch_id from the same state.

batch_id story — same field name as the legacy batch daemon, sourced from
Spark's epoch_id:

* Logs   : every line emitted inside foreachBatch carries `batch_id=e-<epoch>`
           in the Python JSON formatter and as an inline token so the Loki
           derived-field regex (`batch_id=([A-Za-z0-9\-]+)`) still matches.
* Traces : one manual `etl_batch` span per epoch, carrying batch_id as a span
           attribute. spot's job/stage spans (emitted by the JVM agent) are
           siblings under service.name=spark-driver/executor and are NOT
           parent/child (Spark doesn't propagate OTel context across the task
           serialization boundary). Presented honestly as production reality.
* Metrics: the streaming consumer is long-lived, so kafka_consumer_records_lag
           has a stable client_id and one series per partition — no need to
           tag it with batch_id.

Status + lifecycle:

* /var/log/etl/spark-batch.status is updated each micro-batch by the
  StreamingQueryListener so the `spark batch status` CLI keeps working.
* SIGTERM → query.stop() (graceful: finishes current micro-batch, commits
  the checkpoint), then awaitTermination returns and we spark.stop().
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone

_LOG_DIR = "/var/log/etl"
os.makedirs(_LOG_DIR, exist_ok=True)
STATUS_PATH = f"{_LOG_DIR}/spark-batch.status"

CHECKPOINT_DIR = os.environ.get("CHECKPOINT_DIR", "/var/lib/spark-checkpoints/clicks")
WATERMARK_DELAY = os.environ.get("WATERMARK_DELAY", "30 seconds")
WINDOW_SIZE = os.environ.get("WINDOW_SIZE", "30 seconds")
TRIGGER_INTERVAL = os.environ.get("TRIGGER_INTERVAL", "10 seconds")


class _JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
                "batch_id": getattr(record, "batch_id", "-"),
            }
        )


_handler = logging.FileHandler(f"{_LOG_DIR}/etl.log")
_handler.setFormatter(_JsonLineFormatter())
_stdout = logging.StreamHandler(sys.stdout)
_stdout.setFormatter(_JsonLineFormatter())

_root = logging.getLogger("etl")
_root.setLevel(logging.INFO)
_root.addHandler(_handler)
_root.addHandler(_stdout)
_root.propagate = False


def _log(batch_id: str) -> logging.LoggerAdapter:
    return logging.LoggerAdapter(_root, {"batch_id": batch_id})


from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.streaming import StreamingQueryListener  # noqa: E402
from pyspark.sql.types import StringType, StructField, StructType  # noqa: E402

# ── OTel tracer: one manual `etl_batch` span per epoch carries batch_id ──────
from opentelemetry import trace  # noqa: E402
from opentelemetry.trace import Status, StatusCode  # noqa: E402
from opentelemetry.sdk.resources import Resource  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: E402
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # noqa: E402

_OTEL_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")
_provider = TracerProvider(resource=Resource.create({"service.name": "etl-driver"}))
_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{_OTEL_ENDPOINT}/v1/traces"))
)
trace.set_tracer_provider(_provider)
_tracer = trace.get_tracer("etl")

CLICKS_SCHEMA = StructType(
    [
        StructField("event_id", StringType()),
        StructField("product_id", StringType()),
        StructField("user_id", StringType()),
        StructField("ts", StringType()),
    ]
)

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka-1:9092,kafka-2:9092")
CLICKS_TOPIC = os.environ.get("CLICKS_TOPIC", "clicks")
PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
PG_DB = os.environ.get("POSTGRES_DB", "clicks")
PG_USER = os.environ.get("POSTGRES_USER", "app")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "app")

# Placeholder product_id for malformed records (product_id field missing/null
# but event_time present). Surfaces them as a counted "bucket" in the stateful
# aggregation so we can log the bad-record count per micro-batch — preserves
# the Scenario B log-grep workflow without a second streaming query.
_BAD_PRODUCT = "__BAD__"


def _pg_connect():
    import psycopg

    return psycopg.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )


def _write_status(
    state: str,
    batch_id: str,
    started: str,
    finished: str,
    input_rows: int = 0,
    dropped_by_watermark: int = 0,
) -> None:
    with open(STATUS_PATH, "w") as f:
        json.dump(
            {
                "state": state,
                "batch_id": batch_id,
                "started_at": started,
                "finished_at": finished,
                "num_input_rows": input_rows,
                "num_dropped_by_watermark": dropped_by_watermark,
            },
            f,
        )


def upsert_to_pg(df, epoch_id: int) -> None:
    """foreachBatch sink. Writes the rows whose running count changed in this
    micro-batch into aggregated_clicks via REPLACE upsert. The aggregate is the
    state-store-maintained running total per (window, product_id); the same
    epoch + same state produce the same rows, so replay is safe."""
    batch_id = f"e-{epoch_id}"
    log = _log(batch_id)

    with _tracer.start_as_current_span(
        "etl_batch",
        attributes={
            "batch_id": batch_id,
            "etl.kafka.topic": CLICKS_TOPIC,
            "etl.epoch_id": int(epoch_id),
        },
    ) as span:
        try:
            rows = (
                df.selectExpr("product_id", "window.start AS minute_window", "click_count")
                  .collect()
            )

            bad_rows = [r for r in rows if r["product_id"] == _BAD_PRODUCT]
            good_rows = [r for r in rows if r["product_id"] != _BAD_PRODUCT]

            if bad_rows:
                # Running total of records dropped for missing product_id, summed
                # across all open windows touched this epoch. Lessons grep for
                # "dropped" + "missing product_id" — wording preserved.
                bad_total = sum(int(r["click_count"]) for r in bad_rows)
                log.warning(
                    f"dropped {bad_total} records missing product_id "
                    f"(running total across {len(bad_rows)} open window(s))"
                )

            log.info(f"epoch start batch_id={batch_id} input_rows={len(rows)} good={len(good_rows)} bad={len(bad_rows)}")

            if good_rows:
                with _pg_connect() as conn, conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO aggregated_clicks
                            (product_id, minute_window, click_count, last_batch_id, updated_at)
                        VALUES (%s, %s, %s, %s, now())
                        ON CONFLICT (product_id, minute_window)
                        DO UPDATE SET click_count = EXCLUDED.click_count,
                                      last_batch_id = EXCLUDED.last_batch_id,
                                      updated_at = now()
                        """,
                        [
                            (r["product_id"], r["minute_window"], int(r["click_count"]), batch_id)
                            for r in good_rows
                        ],
                    )

            span.set_attribute("etl.rows_written", len(good_rows))
            span.set_attribute("etl.bad_rows", len(bad_rows))
            log.info(
                f"epoch done batch_id={batch_id} rows_written={len(good_rows)} bad={len(bad_rows)}"
            )
        except Exception:
            span.set_status(Status(StatusCode.ERROR))
            log.exception(f"epoch failed batch_id={batch_id}")
            raise


class _ProgressListener(StreamingQueryListener):
    """Capture micro-batch progress for CLI status + watermark-drop log line."""

    def onQueryStarted(self, event):  # noqa: N802 (Spark API)
        _log("-").info(f"streaming query started id={event.id} runId={event.runId}")
        _write_status("running", "-", datetime.now(timezone.utc).isoformat(), "")

    def onQueryProgress(self, event):  # noqa: N802
        p = event.progress
        epoch_id = p.batchId
        batch_id = f"e-{epoch_id}"

        dropped = 0
        for so in (p.stateOperators or []):
            dropped += int(getattr(so, "numRowsDroppedByWatermark", 0) or 0)
        input_rows = int(p.numInputRows or 0)

        _write_status(
            "running",
            batch_id,
            p.timestamp,
            datetime.now(timezone.utc).isoformat(),
            input_rows=input_rows,
            dropped_by_watermark=dropped,
        )
        # Inline `batch_id=...` keeps the Loki derived-field regex matching.
        _log(batch_id).info(
            f"streaming progress batch_id={batch_id} input_rows={input_rows} "
            f"dropped_by_watermark={dropped}"
        )

    def onQueryTerminated(self, event):  # noqa: N802
        state = "failed" if event.exception else "stopped"
        reason = event.exception or "graceful"
        _log("-").info(f"streaming query terminated state={state} reason={reason}")
        try:
            with open(STATUS_PATH) as f:
                cur = json.load(f)
        except Exception:  # noqa: BLE001
            cur = {}
        cur["state"] = state
        cur["finished_at"] = datetime.now(timezone.utc).isoformat()
        with open(STATUS_PATH, "w") as f:
            json.dump(cur, f)


def main() -> int:
    log = _log("-")
    log.info(
        f"daemon starting checkpoint={CHECKPOINT_DIR} watermark={WATERMARK_DELAY} "
        f"window={WINDOW_SIZE} trigger={TRIGGER_INTERVAL}"
    )
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    spark = (
        SparkSession.builder
        .appName("etl-daemon")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.sql.streaming.metricsEnabled", "true")
        .getOrCreate()
    )
    log.info(f"spark session created app_id={spark.sparkContext.applicationId}")
    spark.streams.addListener(_ProgressListener())

    events = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", CLICKS_TOPIC)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    parsed = (
        events
        .select(F.from_json(F.col("value").cast("string"), CLICKS_SCHEMA).alias("e"))
        .select("e.*")
        .withColumn("event_time", F.to_timestamp("ts"))
        .filter(F.col("event_time").isNotNull())
    )

    windowed = (
        parsed.withWatermark("event_time", WATERMARK_DELAY)
              .groupBy(
                  F.window("event_time", WINDOW_SIZE),
                  F.coalesce(F.col("product_id"), F.lit(_BAD_PRODUCT)).alias("product_id"),
              )
              .agg(F.count(F.lit(1)).alias("click_count"))
    )

    query = (
        windowed.writeStream
        .outputMode("update")
        .foreachBatch(upsert_to_pg)
        .option("checkpointLocation", CHECKPOINT_DIR)
        .trigger(processingTime=TRIGGER_INTERVAL)
        .queryName("clicks-aggregate")
        .start()
    )

    def _stop(_signum, _frame):
        log.info("SIGTERM received, stopping streaming query")
        query.stop()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    try:
        query.awaitTermination()
    finally:
        log.info("daemon stopping")
        spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
