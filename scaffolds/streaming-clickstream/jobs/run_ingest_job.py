"""spark-submit entrypoint for the ingest job. Provided — do not edit.

Builds a SparkSession, calls pipeline.ingest_job.build_stream, and waits.
"""
from __future__ import annotations

from pyspark.sql import SparkSession

from pipeline import config
from pipeline.ingest_job import build_stream


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("streaming-clickstream-ingest")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    query = build_stream(
        spark=spark,
        kafka_conf=config.kafka_conf(group_id="ingest"),
        sink_conf=config.ingest_sink_conf(),
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
