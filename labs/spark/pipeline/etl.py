"""Student stub — the ETL entrypoint the scheduler and the tests call.

Contract (do not rename the function or change the signature):

    run_etl(spark_session, input_file_dir, connections) -> None

The function should:
  * Pick up any *new* files from `input_file_dir` (incrementally — stage 2).
  * Produce the aggregates that `serving.total_revenue(d, h)` will read
    (idempotency — stage 3).
  * Leave the analyst store in the same state whether it's called once or twice
    with the same inputs.

`connections` is a plain dict. Its exact shape is decided in class once the
storage technologies are picked. Expect keys for the analyst store and (later)
the serving store.
"""
from __future__ import annotations

from pyspark.sql import SparkSession


def run_etl(
    spark_session: SparkSession,
    input_file_dir: str,
    connections: dict,
    # TODO: once the storage technologies are picked in class, replace `connections: dict`
    # with a concrete type (e.g. a TypedDict or a small dataclass).
) -> None:
    raise NotImplementedError("stage 2 / stage 3 — implement run_etl")
