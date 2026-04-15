"""Test harness: session-scoped SparkSession, per-test ephemeral stores, fixture landing dir.

Tests call `run_etl(spark, landing_dir, connections)` and the two serving functions
as black boxes. Nothing here assumes a storage technology beyond what the class
decided — `connections` is plumbed through from whatever `make_connections`
fixture the test file pulls in.

Environment expected (set by compose.yml / Makefile `test-spark` target):
    PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DB (analyst store)
    REDIS_HOST, REDIS_PORT                        (serving store)

The harness assumes it can talk to those services but makes no assumption about
their schema. Per-test fixtures clear whatever state the student's code put there.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

# Ensure /home/jovyan/work is on sys.path so `pipeline` / `helpers` import cleanly.
WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORK))

from pyspark.sql import SparkSession  # noqa: E402

from pipeline import config  # noqa: E402


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    s = (SparkSession.builder
        .appName("lab-tests")
        .master(os.environ.get("SPARK_TEST_MASTER", "local[2]"))
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate())
    yield s
    s.stop()


@pytest.fixture()
def landing_dir(tmp_path: Path) -> Path:
    d = tmp_path / "landing"
    d.mkdir()
    return d


@pytest.fixture()
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def _reset_postgres() -> None:
    """Drop everything the student created in the `taxi` DB between tests.

    We don't know the schema, so we wipe the public schema (and recreate it).
    This keeps the harness agnostic to the student's table design.
    """
    try:
        import psycopg2
    except ImportError:
        return
    kw = config.postgres_kwargs()
    conn = psycopg2.connect(**kw)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        cur.execute("GRANT ALL ON SCHEMA public TO public;")
    conn.close()


def _reset_redis() -> None:
    try:
        import redis
    except ImportError:
        return
    r = redis.Redis(**config.redis_kwargs())
    try:
        r.flushdb()
    except Exception:
        pass


@pytest.fixture()
def connections(landing_dir: Path) -> dict:
    _reset_postgres()
    _reset_redis()
    return {
        "paths": {
            "landing": str(landing_dir),
            "in_process": str(landing_dir.parent / "in_process"),
            "archive": str(landing_dir.parent / "archive"),
            "errors": str(landing_dir.parent / "errors"),
        },
        "postgres": config.postgres_kwargs(),
        "postgres_jdbc": config.postgres_jdbc(),
        "redis": config.redis_kwargs(),
    }


@pytest.fixture(autouse=True)
def _cleanup_bucket_dirs(landing_dir: Path):
    yield
    for name in ("in_process", "archive", "errors"):
        p = landing_dir.parent / name
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
