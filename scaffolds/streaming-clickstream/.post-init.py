#!/usr/bin/env python3
"""Post-init hook for the streaming-clickstream scaffold.

Invoked by scripts/new-project.py after the scaffold is copied. CWD is the
target. Stdlib only — students have not run `uv sync` yet.

Responsibilities:
  * Ensure data/, checkpoints/, and notebooks/ exist with .gitkeep so git
    tracks the empty directories. data/ and checkpoints/ are populated by
    the pipeline at runtime; notebooks/ is a scratch space for students to
    experiment in JupyterLab. Pre-creating notebooks/ on the host is what
    keeps Docker from auto-creating it as root on first `compose up`, which
    would leave it unwritable by both the host user and the container's
    jovyan user.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main(target: Path) -> int:
    for sub in ("data", "checkpoints", "notebooks"):
        d = target / sub
        d.mkdir(exist_ok=True)
        (d / ".gitkeep").touch(exist_ok=True)
        print(f"[post-init] ensured {d}/.gitkeep")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    sys.exit(main(target))
