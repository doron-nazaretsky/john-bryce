"""Pytest fixtures shared across all stage tests. Provided — do not edit.

Conventions:
  * One session-scoped SparkSession with a local[2] master so tests don't
    depend on the standalone cluster.
  * Each test gets a fresh, uniquely-named topic to isolate state.
  * Each test gets fresh, unique tmp dirs for parquet output and checkpoint
    so streaming queries don't collide.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from pyspark.sql import SparkSession

from pipeline import config
from helpers import test_utils


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    spark = (
        SparkSession.builder
        .master("local[2]")
        .appName("streaming-clickstream-tests")
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.0")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    yield spark
    spark.stop()


@pytest.fixture
def topic() -> str:
    """Unique per-test Kafka topic. Reset before yield, deleted-equivalent on teardown."""
    name = f"pageviews-test-{uuid4().hex[:8]}"
    test_utils.reset_topic(config.KAFKA_BOOTSTRAP_SERVERS, name)
    yield name
    # Topic deletion is async on the broker; we leave it and trust delete-on-recreate.


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    yield out
    shutil.rmtree(out, ignore_errors=True)


@pytest.fixture
def tmp_checkpoint(tmp_path: Path) -> Path:
    cp = tmp_path / "checkpoint"
    cp.mkdir()
    yield cp
    shutil.rmtree(cp, ignore_errors=True)
