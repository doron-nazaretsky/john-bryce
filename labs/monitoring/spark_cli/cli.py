"""Spark cluster + ETL daemon control CLI.

The ETL is a long-running PySpark daemon that lives inside the spark-master
container. ``spark batch start`` launches it (one SparkSession, one warm JVM)
and ``spark batch stop`` halts it. The daemon writes its current status to a
shared file in the ``etl-logs`` volume so this CLI can read it directly from
the workspace without docker-execing.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import click

# Shared state lives in the etl-logs volume which is mounted on both workspace
# and spark-master.
SHARED_DIR = Path("/var/log/etl")
BATCH_STATUS_PATH = SHARED_DIR / "spark-batch.status"
DAEMON_PID_PATH = SHARED_DIR / "spark-batch-daemon.pid"

SPARK_MASTER_CONTAINER = "spark-master"
DAEMON_SCRIPT = "/workspace/labs/monitoring/etl/start_daemon.sh"


def _docker_exec(args: list[str], capture: bool = True, detach: bool = False) -> subprocess.CompletedProcess:
    cmd = ["docker", "exec"]
    if detach:
        cmd.append("-d")
    cmd.append(SPARK_MASTER_CONTAINER)
    cmd.extend(args)
    return subprocess.run(cmd, capture_output=capture, text=True)


def _daemon_pid() -> int | None:
    if not DAEMON_PID_PATH.exists():
        return None
    try:
        pid = int(DAEMON_PID_PATH.read_text().strip())
    except ValueError:
        return None
    # The pid lives in spark-master's namespace, so check it there.
    result = _docker_exec(["kill", "-0", str(pid)])
    return pid if result.returncode == 0 else None


@click.group()
def spark() -> None:
    """Spark cluster + ETL daemon control."""


@spark.group()
def batch() -> None:
    """ETL daemon operations."""


@batch.command()
@click.option("--trigger", "trigger_interval", default="10 seconds", show_default=True,
              help="processingTime trigger for the streaming query.")
def start(trigger_interval: str) -> None:
    """Start the long-running Structured Streaming ETL in spark-master."""
    if _daemon_pid():
        raise click.ClickException(f"already running (pid {_daemon_pid()})")
    # Stale pidfile from a crashed daemon — clear it.
    DAEMON_PID_PATH.unlink(missing_ok=True)

    result = subprocess.run(
        [
            "docker", "exec", "-d",
            "-e", f"TRIGGER_INTERVAL={trigger_interval}",
            SPARK_MASTER_CONTAINER,
            "bash", DAEMON_SCRIPT,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise click.ClickException(f"failed to start daemon: {result.stderr.strip()}")
    click.echo(f"started trigger={trigger_interval!r} (driver JVM warming up — first micro-batch in ~10s)")


@batch.command()
def stop() -> None:
    """Stop the ETL daemon."""
    pid = _daemon_pid()
    if pid is None:
        DAEMON_PID_PATH.unlink(missing_ok=True)
        raise click.ClickException("not running")
    # SIGTERM the spark-submit process inside spark-master; it will tear down
    # the SparkSession cleanly.
    _docker_exec(["kill", "-TERM", str(pid)])
    DAEMON_PID_PATH.unlink(missing_ok=True)
    click.echo(f"stopped pid={pid}")


@batch.command("status")
def batch_status() -> None:
    """Show daemon state + last micro-batch progress."""
    pid = _daemon_pid()
    click.echo(f"daemon={'running pid='+str(pid) if pid else 'stopped'}")
    if BATCH_STATUS_PATH.exists():
        raw = BATCH_STATUS_PATH.read_text()
        try:
            s = json.loads(raw)
            click.echo(
                f"state={s.get('state', '?')} "
                f"batch_id={s.get('batch_id', '?')} "
                f"input_rows={s.get('num_input_rows', 0)} "
                f"dropped_by_watermark={s.get('num_dropped_by_watermark', 0)} "
                f"last_progress_at={s.get('finished_at', '?')}"
            )
        except json.JSONDecodeError:
            click.echo(raw)


@spark.group()
def cluster() -> None:
    """Spark cluster operations."""


@cluster.command("status")
def cluster_status() -> None:
    """Show master + worker summary via the master's REST API."""
    result = _docker_exec(["curl", "-fsS", "http://localhost:8080/json/"])
    if result.returncode != 0:
        raise click.ClickException(f"master not reachable: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    workers = data.get("workers", [])
    click.echo(f"master:  {data.get('url', '?')}  status={data.get('status', '?')}")
    click.echo(f"workers: {len(workers)} alive")
    for w in workers:
        click.echo(f"  - {w.get('id', '?')}  host={w.get('host', '?')}  cores={w.get('cores', '?')}  mem={w.get('memory', '?')}MB  state={w.get('state', '?')}")
    click.echo(f"apps:    running={len(data.get('activeapps', []))}  completed={len(data.get('completedapps', []))}")


if __name__ == "__main__":
    spark()
