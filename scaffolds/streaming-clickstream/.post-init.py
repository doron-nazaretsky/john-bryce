#!/usr/bin/env python3
"""Post-init hook for the streaming-clickstream scaffold.

Invoked by scripts/new-project.py after the scaffold is copied. CWD is the
target. Stdlib only — students have not run `uv sync` yet.

Responsibilities:
  * Ensure data/ and checkpoints/ exist with .gitkeep so git tracks the empty
    directories the pipeline will populate at runtime.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main(target: Path) -> int:
    for sub in ("data", "checkpoints"):
        d = target / sub
        d.mkdir(exist_ok=True)
        (d / ".gitkeep").touch(exist_ok=True)
        print(f"[post-init] ensured {d}/.gitkeep")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    sys.exit(main(target))
