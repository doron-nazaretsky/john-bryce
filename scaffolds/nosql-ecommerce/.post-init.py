#!/usr/bin/env python3
"""Post-init hook for the nosql-ecommerce scaffold.

Invoked by scripts/new-project.py after the scaffold has been copied to the
student's target directory. CWD is the target. Stdlib-only — students have
not run `uv sync` yet.

Responsibilities:
  * Seed .env from .env.example if the student doesn't already have one.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main(target: Path) -> int:
    env = target / ".env"
    template = target / ".env.example"
    if env.exists():
        print("[post-init] .env already present — leaving it alone")
        return 0
    if not template.exists():
        print("[post-init] .env.example not found; skipping env seed", file=sys.stderr)
        return 0
    shutil.copyfile(template, env)
    print(f"[post-init] seeded {env.name} from {template.name}")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    sys.exit(main(target))
