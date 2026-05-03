"""spark-submit entrypoint for the windowed-counts job. Provided — do not edit."""
from __future__ import annotations

from pyspark.sql import SparkSession

from pipeline import config
from pipeline.windowed_job import windowed_counts


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("streaming-clickstream-windowed")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    sink = config.windowed_sink_conf()
    query = windowed_counts(
        spark=spark,
        kafka_conf=config.kafka_conf(group_id="windowed"),
        output_path=sink.output_path,
        checkpoint_path=sink.checkpoint_path,
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
