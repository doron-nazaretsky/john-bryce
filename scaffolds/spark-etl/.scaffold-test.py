#!/usr/bin/env python3
"""Scaffold self-test for spark-etl.

Invoked by scripts/test_scaffolds.py as:

    python3 .scaffold-test.py <phase>

Phases:
  * reset   — wipe volumes (docker compose down -v --remove-orphans). Only
              called when the harness is invoked with --fresh.
  * fail    — bring the stack up, wait for spark-jupyter healthy, run the
              pytest stages inside the container. Exit 0 when the tests
              failed with the NotImplementedError marker.
  * pass    — re-run the tests after solutions are overlaid; expect green.
  * cleanup — stop containers (best-effort), preserving volumes so the next
              harness run reuses the expensive Spark bootstrap.

CWD is the scaffold copy. COMPOSE_PROJECT_NAME is set by the harness to
`spark-etl-harness` so volumes survive across runs. Stdlib only.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


FAIL_MARKER = "NotImplementedError"
JUPYTER_CONTAINER = "spark-jupyter"
JUPYTER_HEALTHY_TIMEOUT_S = 900  # 15 min — first-run bootstrap ~5-10 min
POLL_INTERVAL_S = 5


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    sys.stdout.write(out)
    sys.stdout.flush()
    return proc.returncode, out


def wait_for_healthy(container: str, timeout_s: int) -> int:
    """Poll `docker inspect` until the container reports Health.Status=healthy.

    We don't use `docker compose up --wait` because on a fresh volume the
    Spark bootstrap downloads ~1.6 GB of taxi parquet and splits per-day
    CSVs — comfortably longer than any default wait. Our poll respects the
    compose-level start_period implicitly: during that window Docker keeps
    status at "starting", which we tolerate.
    """
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
    rc, out = run(["make", "test-spark"])
    if rc == 0:
        print("[scaffold-test] FAIL phase expected non-zero test-spark, got 0", file=sys.stderr)
        return 1
    if FAIL_MARKER not in out:
        print(f"[scaffold-test] FAIL phase: expected '{FAIL_MARKER}' in output", file=sys.stderr)
        return 1
    return 0


def phase_pass() -> int:
    rc, _ = run(["make", "test-spark"])
    if rc != 0:
        print(f"[scaffold-test] PASS phase: test-spark returned {rc}", file=sys.stderr)
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
