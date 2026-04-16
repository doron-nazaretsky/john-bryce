#!/usr/bin/env python3
"""Scaffold self-test for nosql-ecommerce.

Invoked by scripts/test_scaffolds.py as:

    python3 .scaffold-test.py <phase>

Phases:
  * reset   — wipe volumes (docker compose down -v --remove-orphans). Called
              only when the harness is invoked with --fresh.
  * fail    — start the four DB containers, install deps, run pytest; expect
              non-zero and a NotImplementedError marker in output.
  * pass    — re-run pytest after solutions are overlaid; expect green.
  * cleanup — stop containers, preserving volumes so subsequent harness runs
              reuse the images.

CWD is the scaffold copy. COMPOSE_PROJECT_NAME is set by the harness to
`nosql-ecommerce-harness`. Stdlib only.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


FAIL_MARKER = "NotImplementedError"


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    sys.stdout.write(out)
    sys.stdout.flush()
    return proc.returncode, out


def _bring_up() -> int:
    rc, _ = run(["docker", "compose", "up", "-d", "--wait"])
    if rc != 0:
        print(f"[scaffold-test] docker compose up failed (rc={rc})", file=sys.stderr)
        return rc
    rc, _ = run(["uv", "sync", "--all-extras"])
    if rc != 0:
        print(f"[scaffold-test] uv sync failed (rc={rc})", file=sys.stderr)
        return rc
    return 0


def phase_fail() -> int:
    if _bring_up() != 0:
        return 2
    rc, out = run(["uv", "run", "--all-extras", "pytest", "tests/", "-x", "--tb=short"])
    if rc == 0:
        print("[scaffold-test] FAIL phase expected non-zero pytest, got 0", file=sys.stderr)
        return 1
    if FAIL_MARKER not in out:
        print(f"[scaffold-test] FAIL phase: expected '{FAIL_MARKER}' in output", file=sys.stderr)
        return 1
    return 0


def phase_pass() -> int:
    rc, _ = run(["uv", "run", "--all-extras", "pytest", "tests/"])
    if rc != 0:
        print(f"[scaffold-test] PASS phase: pytest returned {rc}", file=sys.stderr)
        return 1
    return 0


def phase_reset() -> int:
    run(["docker", "compose", "down", "-v", "--remove-orphans"])
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
