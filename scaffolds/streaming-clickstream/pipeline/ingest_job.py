"""Stage 2 — Kafka → parquet ingest job.

Implement ``build_stream`` so it constructs a Spark Structured Streaming query
that reads pageview events from Kafka, parses them, and writes them as
parquet under ``sink_conf.output_path`` with checkpointing under
``sink_conf.checkpoint_path``.

Across Part A and Part B you'll evolve the *same function*:

* Part A — make the read+parse+console-sink minimal pipeline run.
* Part B — switch the sink to parquet, set the checkpoint, verify recovery.
"""
from __future__ import annotations

from pyspark.sql import SparkSession
from pyspark.sql.streaming import StreamingQuery

from pipeline.config import KafkaConf, SinkConf


def build_stream(
    spark: SparkSession,
    kafka_conf: KafkaConf,
    sink_conf: SinkConf,
) -> StreamingQuery:
    """Build and start the Kafka → parquet streaming query.

    Args:
        spark: An existing SparkSession.
        kafka_conf: Bootstrap servers + topic.
        sink_conf: Output path + checkpoint path. Both are absolute paths
            on the Spark driver's filesystem (mounted into the container).

    Behavior:
        * ``readStream`` from Kafka, subscribing to ``kafka_conf.topic``.
        * ``startingOffsets="earliest"`` so a brand-new query reads from
          the start; subsequent restarts use the checkpoint.
        * Parse the ``value`` column as JSON with the schema
          (user_id: string, session_id: string, page: string,
           referrer: string, ts: timestamp).
        * Write the parsed rows as parquet to ``sink_conf.output_path``.
        * Use ``sink_conf.checkpoint_path`` as the checkpoint location.
        * ``outputMode("append")``.
        * Trigger every ``"5 seconds"`` (so tests run quickly).
        * Return the started ``StreamingQuery``.

    Raise NotImplementedError until you've implemented the function.
    """
    raise NotImplementedError(
        "Stage 2: implement pipeline.ingest_job.build_stream"
    )
