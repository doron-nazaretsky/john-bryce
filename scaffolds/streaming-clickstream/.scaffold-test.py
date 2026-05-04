#!/usr/bin/env python3
"""Scaffold self-test for streaming-clickstream.

Same pattern as scaffolds/spark-etl/.scaffold-test.py.

Phases:
  * reset   — wipe volumes (down -v --remove-orphans). Only on --fresh.
  * fail    — bring up the stack, wait for project-streaming-jupyter healthy, run
              pytest. Expect non-zero exit and `NotImplementedError` in the
              output (student stubs).
  * pass    — re-run after solutions are overlaid; expect green.
  * cleanup — stop containers, preserve volumes.

Stdlib only.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


FAIL_MARKER = "NotImplementedError"
JUPYTER_CONTAINER = "project-streaming-jupyter"
JUPYTER_HEALTHY_TIMEOUT_S = 300
POLL_INTERVAL_S = 5


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    sys.stdout.write(out)
    sys.stdout.flush()
    return proc.returncode, out


def wait_for_healthy(container: str, timeout_s: int) -> int:
    deadline = time.monotonic() + timeout_s
    last_status = ""
    while time.monotonic() < deadline:
        proc = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container],
            capture_output=True,
            text=True,
        )
        status = (proc.stdout or "").strip()
        if proc.returncode != 0:
            print(f"[scaffold-test] docker inspect {container} failed: {proc.stderr}", file=sys.stderr)
            return 2
        if status != last_status:
            print(f"[scaffold-test] {container}: {status}")
            last_status = status
        if status == "healthy":
            return 0
        if status == "unhealthy":
            print(f"[scaffold-test] {container} reported unhealthy", file=sys.stderr)
            return 1
        time.sleep(POLL_INTERVAL_S)
    print(f"[scaffold-test] {container} did not become healthy in {timeout_s}s", file=sys.stderr)
    return 1


def _bring_up() -> int:
    rc, _ = run(["docker", "compose", "up", "-d", "--build", "--remove-orphans"])
    if rc != 0:
        print(f"[scaffold-test] docker compose up failed (rc={rc})", file=sys.stderr)
        return rc
    return wait_for_healthy(JUPYTER_CONTAINER, JUPYTER_HEALTHY_TIMEOUT_S)


def phase_reset() -> int:
    run(["docker", "compose", "down", "-v", "--remove-orphans"])
    return 0


def phase_fail() -> int:
    if _bring_up() != 0:
        return 2
    rc, out = run(["make", "test"])
    if rc == 0:
        print("[scaffold-test] FAIL phase expected non-zero, got 0", file=sys.stderr)
        return 1
    if FAIL_MARKER not in out:
        print(f"[scaffold-test] FAIL phase: expected '{FAIL_MARKER}' in output", file=sys.stderr)
        return 1
    return 0


def phase_pass() -> int:
    rc, _ = run(["make", "test"])
    if rc != 0:
        print(f"[scaffold-test] PASS phase: test returned {rc}", file=sys.stderr)
        return 1
    return 0


def phase_cleanup() -> int:
    run(["docker", "compose", "down", "--remove-orphans"])
    return 0


PHASES = {
    "reset": phase_reset,
    "fail": phase_fail,
    "pass": phase_pass,
    "cleanup": phase_cleanup,
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in PHASES:
        print(f"usage: {Path(sys.argv[0]).name} {{reset|fail|pass|cleanup}}", file=sys.stderr)
        return 64
    return PHASES[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
