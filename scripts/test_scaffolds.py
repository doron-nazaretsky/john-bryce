#!/usr/bin/env python3
"""Scaffold self-testing harness.

For each scaffold, the flow is:

  1. Scaffold it into a tempdir via new-project.py.
  2. (Optional, with --fresh) invoke `.scaffold-test.py reset` to wipe any
     persisted volumes from previous harness runs.
  3. Invoke the scaffold's `.scaffold-test.py fail` — it is expected to
     bring the stack up, run the tests, and exit 0 IFF the tests failed
     with the scaffold's "not implemented" marker.
  4. Overlay the solutions from `materials/projects/<name>/solutions/`
     onto the tempdir.
  5. Invoke `.scaffold-test.py pass` — expected to re-run the tests and
     exit 0 IFF they now pass.
  6. Always invoke `.scaffold-test.py cleanup` in a finally block. Cleanup
     does NOT remove volumes — that way repeated harness runs reuse any
     expensive bootstrap caches (Spark taxi parquet, ~1.6 GB). Use
     `--fresh` to force a full rebuild.

Each scaffold's hooks run under a stable `COMPOSE_PROJECT_NAME=<name>-harness`
so volumes survive across runs.

Non-zero exit from any phase aborts the scaffold as failed.

Usage:
    scripts/test_scaffolds.py                  # all scaffolds, reuses volumes
    scripts/test_scaffolds.py --scaffold spark-etl
    scripts/test_scaffolds.py --fresh          # wipe volumes first (full cycle)
    scripts/test_scaffolds.py --keep-on-fail   # leave tmpdir for inspection
    scripts/test_scaffolds.py --phase fail     # stop after the fail phase
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLDS_ROOT = REPO_ROOT / "scaffolds"
MATERIALS_ROOT = REPO_ROOT / "materials" / "projects"
NEW_PROJECT = REPO_ROOT / "scripts" / "new-project.py"
HOOK_NAME = ".scaffold-test.py"


@dataclass
class ScaffoldRun:
    name: str
    target: Path
    keep: bool = False


def hook_env(scaffold_name: str) -> dict[str, str]:
    env = dict(os.environ)
    env["COMPOSE_PROJECT_NAME"] = f"{scaffold_name}-harness"
    # Stop uv from complaining about the outer repo's VIRTUAL_ENV leaking in.
    env.pop("VIRTUAL_ENV", None)
    return env


def run_hook(scaffold_name: str, target: Path, phase: str) -> int:
    hook = SCAFFOLDS_ROOT / scaffold_name / HOOK_NAME
    if not hook.exists():
        print(f"[test-scaffolds] {scaffold_name}: missing {hook}", file=sys.stderr)
        return 3
    print(
        f"\n[test-scaffolds] {scaffold_name}: phase={phase} "
        f"(COMPOSE_PROJECT_NAME={scaffold_name}-harness)"
    )
    proc = subprocess.run(
        [sys.executable, str(hook), phase],
        cwd=str(target),
        env=hook_env(scaffold_name),
    )
    return proc.returncode


def scaffold_into(name: str, target: Path) -> int:
    proc = subprocess.run(
        [
            sys.executable,
            str(NEW_PROJECT),
            "--scaffold",
            name,
            "--target",
            str(target),
            "--force",
        ]
    )
    return proc.returncode


def overlay_solutions(name: str, target: Path) -> int:
    src = MATERIALS_ROOT / name / "solutions"
    if not src.is_dir():
        print(
            f"[test-scaffolds] {name}: solutions directory not found at {src} — "
            f"instructor must populate it",
            file=sys.stderr,
        )
        return 2
    shutil.copytree(src, target, dirs_exist_ok=True)
    print(f"[test-scaffolds] {name}: overlaid solutions from {src}")
    return 0


def test_scaffold(
    name: str,
    *,
    keep_on_fail: bool,
    stop_after_phase: str | None,
    fresh: bool,
) -> bool:
    tmp = Path(tempfile.mkdtemp(prefix=f"scaffold-test-{name}-"))
    print(f"[test-scaffolds] {name}: tmp={tmp}")
    success = False
    try:
        rc = scaffold_into(name, tmp)
        if rc != 0:
            print(f"[test-scaffolds] {name}: scaffold copy failed (rc={rc})", file=sys.stderr)
            return False

        if fresh:
            rc = run_hook(name, tmp, "reset")
            if rc != 0:
                print(f"[test-scaffolds] {name}: RESET phase returned {rc}", file=sys.stderr)
                return False

        rc = run_hook(name, tmp, "fail")
        if rc != 0:
            print(f"[test-scaffolds] {name}: FAIL phase returned {rc}", file=sys.stderr)
            return False
        if stop_after_phase == "fail":
            success = True
            return True

        rc = overlay_solutions(name, tmp)
        if rc != 0:
            return False

        rc = run_hook(name, tmp, "pass")
        if rc != 0:
            print(f"[test-scaffolds] {name}: PASS phase returned {rc}", file=sys.stderr)
            return False

        success = True
        return True
    finally:
        run_hook(name, tmp, "cleanup")
        if success and not keep_on_fail:
            shutil.rmtree(tmp, ignore_errors=True)
        elif not success:
            if keep_on_fail:
                print(f"[test-scaffolds] kept {tmp} for inspection")
            else:
                shutil.rmtree(tmp, ignore_errors=True)


def discover() -> list[str]:
    if not SCAFFOLDS_ROOT.is_dir():
        return []
    return sorted(
        p.name
        for p in SCAFFOLDS_ROOT.iterdir()
        if p.is_dir() and (p / ".scaffold.yml").exists()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--scaffold", help="test just this scaffold")
    parser.add_argument(
        "--keep-on-fail", action="store_true", help="keep the tmpdir when a phase fails"
    )
    parser.add_argument(
        "--phase",
        choices=("fail", "pass"),
        help="stop after the given phase (fail = skip overlay + pass phase)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="wipe the harness volumes before bringing the stack up — forces a full bootstrap",
    )
    args = parser.parse_args()

    names = [args.scaffold] if args.scaffold else discover()
    if not names:
        print("[test-scaffolds] no scaffolds found", file=sys.stderr)
        return 2

    failures: list[str] = []
    for name in names:
        if not (SCAFFOLDS_ROOT / name / ".scaffold.yml").exists():
            print(f"[test-scaffolds] {name}: not a scaffold", file=sys.stderr)
            failures.append(name)
            continue
        ok = test_scaffold(
            name,
            keep_on_fail=args.keep_on_fail,
            stop_after_phase=args.phase,
            fresh=args.fresh,
        )
        if not ok:
            failures.append(name)

    print()
    if failures:
        print(f"[test-scaffolds] FAILED: {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"[test-scaffolds] OK ({len(names)} scaffold(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
