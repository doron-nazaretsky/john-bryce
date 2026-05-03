"""Stage 3 — Windowed pageview counts with watermarks.

Implement ``windowed_counts`` so it computes pageviews-per-page-per-1-minute
window and writes them to parquet as windows close.

Across Part A and Part B you'll evolve the *same function*:

* Part A — basic tumbling window count, no watermark (use ``update`` mode
  so it works without one).
* Part B — add ``withWatermark`` so ``append`` mode is legal and the test
  for late-data tolerance passes.
"""
from __future__ import annotations

from pyspark.sql import SparkSession
from pyspark.sql.streaming import StreamingQuery

from pipeline.config import KafkaConf


def windowed_counts(
    spark: SparkSession,
    kafka_conf: KafkaConf,
    output_path: str,
    checkpoint_path: str,
) -> StreamingQuery:
    """Build and start the windowed-counts streaming query.

    Args:
        spark: An existing SparkSession.
        kafka_conf: Bootstrap servers + topic.
        output_path: Where to write the windowed result parquet.
        checkpoint_path: Where Spark stores its state and offsets.

    Behavior (final, Part B):
        * Read the pageviews topic from earliest, parse JSON.
        * ``withWatermark("ts", "2 minutes")`` — declare lateness tolerance.
        * Group by ``window(col("ts"), "1 minute")`` and ``page``.
        * ``count()`` to get pageviews per (window, page).
        * Write to parquet at ``output_path`` with checkpoint at
          ``checkpoint_path``.
        * ``outputMode("append")`` — emit each (window, page) row exactly
          once when the watermark passes the window end.
        * Trigger every ``"5 seconds"``.
        * Output schema must include ``window_start``, ``window_end``,
          ``page``, ``count`` (project the ``window`` struct's start and
          end into top-level columns).

    Raise NotImplementedError until you've implemented the function.
    """
    raise NotImplementedError(
        "Stage 3: implement pipeline.windowed_job.windowed_counts"
    )
