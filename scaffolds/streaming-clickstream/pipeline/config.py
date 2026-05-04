"""Project-wide configuration. Provided — do not edit.

All settings come from environment variables with sensible defaults so the
same code runs in tests (with overrides via env) and in the live cluster.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


# Kafka
KAFKA_BOOTSTRAP_SERVERS = _env(
    "KAFKA_BOOTSTRAP_SERVERS",
    "project-kafka-1:9092,project-kafka-2:9092,project-kafka-3:9092",
)
PAGEVIEWS_TOPIC = _env("PAGEVIEWS_TOPIC", "pageviews")

# Filesystem
DATA_DIR = _env("DATA_DIR", "/home/jovyan/work/data")
CHECKPOINT_DIR = _env("CHECKPOINT_DIR", "/home/jovyan/work/checkpoints")

INGEST_OUTPUT_PATH = f"{DATA_DIR}/ingested"
INGEST_CHECKPOINT_PATH = f"{CHECKPOINT_DIR}/ingest"
WINDOWED_OUTPUT_PATH = f"{DATA_DIR}/windowed"
WINDOWED_CHECKPOINT_PATH = f"{CHECKPOINT_DIR}/windowed"

# Consumer group used by jobs and CLI consumers (tests override with their own).
DEFAULT_GROUP_ID = _env("DEFAULT_GROUP_ID", "streaming-clickstream-default")


@dataclass(frozen=True)
class KafkaConf:
    bootstrap_servers: str
    topic: str
    group_id: str = DEFAULT_GROUP_ID


@dataclass(frozen=True)
class SinkConf:
    output_path: str
    checkpoint_path: str


def kafka_conf(group_id: str | None = None, topic: str | None = None) -> KafkaConf:
    return KafkaConf(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        topic=topic or PAGEVIEWS_TOPIC,
        group_id=group_id or DEFAULT_GROUP_ID,
    )


def ingest_sink_conf() -> SinkConf:
    return SinkConf(
        output_path=INGEST_OUTPUT_PATH,
        checkpoint_path=INGEST_CHECKPOINT_PATH,
    )


def windowed_sink_conf() -> SinkConf:
    return SinkConf(
        output_path=WINDOWED_OUTPUT_PATH,
        checkpoint_path=WINDOWED_CHECKPOINT_PATH,
    )
