"""Producer control CLI.

The daemon is on-demand: invoke ``producer start`` (typically from a MyST
{code-cell}) to begin streaming, ``producer stop`` to halt. Rate and bad-data
controls work whenever the daemon is running by writing a JSON control file
that the daemon polls every second.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import click

CONTROL_PATH = Path(os.environ.get("PRODUCER_CONTROL_FILE", "/tmp/producer-control.json"))
STATUS_PATH = CONTROL_PATH.with_suffix(".status")
PID_PATH = Path("/tmp/producer-daemon.pid")
LOG_PATH = Path("/tmp/producer-daemon.log")

PRESETS = {"normal": 1.0, "slow": 0.5, "off": 0.0}


def _read() -> dict:
    if not CONTROL_PATH.exists():
        return {"rate_mult": 1.0, "inject_bad": 0}
    return json.loads(CONTROL_PATH.read_text())


def _write(state: dict) -> None:
    CONTROL_PATH.write_text(json.dumps(state))


def _running_pid() -> int | None:
    if not PID_PATH.exists():
        return None
    try:
        pid = int(PID_PATH.read_text().strip())
    except ValueError:
        return None
    try:
        os.kill(pid, 0)
        return pid
    except ProcessLookupError:
        return None


@click.group()
def producer() -> None:
    """Control the synthetic click-event producer daemon."""


@producer.command()
@click.option("--rate", "rate_mult", default="normal", help="Initial rate (number or normal|slow|off).")
def start(rate_mult: str) -> None:
    """Start the producer daemon in the background."""
    if _running_pid():
        raise click.ClickException(f"already running (pid {_running_pid()})")

    if rate_mult in PRESETS:
        mult = PRESETS[rate_mult]
    else:
        try:
            mult = float(rate_mult.rstrip("x"))
        except ValueError as exc:
            raise click.ClickException(f"invalid rate: {rate_mult!r}") from exc

    _write({"rate_mult": mult, "inject_bad": 0})

    log_fd = LOG_PATH.open("ab")
    proc = subprocess.Popen(
        [sys.executable, "-m", "producer.producer_daemon"],
        stdout=log_fd,
        stderr=log_fd,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    PID_PATH.write_text(str(proc.pid))
    click.echo(f"started pid={proc.pid} rate_mult={mult}")


@producer.command()
def stop() -> None:
    """Stop the producer daemon."""
    pid = _running_pid()
    if pid is None:
        PID_PATH.unlink(missing_ok=True)
        raise click.ClickException("not running")
    os.kill(pid, signal.SIGTERM)
    PID_PATH.unlink(missing_ok=True)
    click.echo(f"stopped pid={pid}")


@producer.command()
@click.argument("rate")
def rate(rate: str) -> None:
    """Set the rate multiplier. Use a number (e.g. 5) or a preset (normal|slow|off)."""
    if rate in PRESETS:
        mult = PRESETS[rate]
    else:
        try:
            mult = float(rate.rstrip("x"))
        except ValueError as exc:
            raise click.ClickException(f"invalid rate: {rate!r}") from exc
    state = _read()
    state["rate_mult"] = mult
    _write(state)
    click.echo(f"rate_mult={mult}")


@producer.command("inject-bad")
@click.argument("count", type=int)
def inject_bad(count: int) -> None:
    """Schedule N malformed records (missing product_id) to be sent next tick."""
    state = _read()
    state["inject_bad"] = int(state.get("inject_bad", 0)) + count
    _write(state)
    click.echo(f"pending_bad={state['inject_bad']}")


@producer.command()
def status() -> None:
    """Show daemon state + last status snapshot."""
    pid = _running_pid()
    if pid is None:
        click.echo("running=false")
        return
    click.echo(f"running=true pid={pid}")
    if STATUS_PATH.exists():
        click.echo(STATUS_PATH.read_text())


if __name__ == "__main__":
    producer()
