#!/usr/bin/env python3
"""Interactive CLI to scaffold a capstone project into a new directory.

Discovers scaffolds under `scaffolds/<name>/` — each scaffold must ship a
`.scaffold.yml` manifest. The manifest drives: exclude globs during copy,
the post-init hook, and the next-steps message.

Usage:
    scripts/new-project.py                                 # interactive
    scripts/new-project.py --list
    scripts/new-project.py --scaffold spark-etl --target ~/code/etl
    scripts/new-project.py --scaffold nosql-ecommerce --target ./shop --force
    scripts/new-project.py --scaffold spark-etl --target /tmp/x --no-post-init

Exit codes:
    0   success
    1   user error (invalid target, scaffold not found, ...)
    2   scaffold error (manifest invalid, scaffold missing)
    3   post-init hook script missing
    4   post-init hook failed
    130 cancelled via Ctrl-C
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml  # type: ignore[import-not-found]
except ImportError:
    sys.stderr.write(
        "[new-project] PyYAML is required. Run `uv sync` in the course repo first.\n"
    )
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLDS_ROOT = REPO_ROOT / "scaffolds"
MANIFEST_NAME = ".scaffold.yml"
POST_INIT_TIMEOUT_S = 120


@dataclass
class ScaffoldManifest:
    name: str
    title: str
    description: str
    path: Path
    exclude: list[str] = field(default_factory=list)
    post_init: str | None = None
    next_steps: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, scaffold_dir: Path) -> "ScaffoldManifest":
        manifest_file = scaffold_dir / MANIFEST_NAME
        if not manifest_file.exists():
            raise FileNotFoundError(f"{scaffold_dir.name}: missing {MANIFEST_NAME}")
        data = yaml.safe_load(manifest_file.read_text()) or {}
        required = ("name", "title", "description")
        for key in required:
            if key not in data:
                raise ValueError(f"{scaffold_dir.name}/{MANIFEST_NAME}: missing '{key}'")
        return cls(
            name=data["name"],
            title=data["title"],
            description=data["description"].strip(),
            path=scaffold_dir,
            exclude=list(data.get("exclude", [])),
            post_init=data.get("post_init"),
            next_steps=list(data.get("next_steps", [])),
        )


def discover_scaffolds() -> list[ScaffoldManifest]:
    if not SCAFFOLDS_ROOT.is_dir():
        return []
    out: list[ScaffoldManifest] = []
    for entry in sorted(SCAFFOLDS_ROOT.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if not (entry / MANIFEST_NAME).exists():
            continue
        out.append(ScaffoldManifest.load(entry))
    return out


def prompt_scaffold(scaffolds: list[ScaffoldManifest]) -> ScaffoldManifest:
    print("Available scaffolds:")
    for i, s in enumerate(scaffolds, 1):
        print(f"  [{i}] {s.name}  —  {s.title}")
    print()
    while True:
        raw = input("Pick a scaffold (number or name): ").strip()
        if not raw:
            continue
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(scaffolds):
                return scaffolds[idx]
        for s in scaffolds:
            if s.name == raw:
                return s
        print(f"  ! no scaffold matches '{raw}' — try again")


def prompt_target(default: Path | None = None) -> Path:
    prompt = "Target directory: "
    if default is not None:
        prompt = f"Target directory [{default}]: "
    while True:
        raw = input(prompt).strip()
        if not raw and default is not None:
            return default.expanduser().resolve()
        if raw:
            return Path(raw).expanduser().resolve()


def validate_target(target: Path, *, force: bool) -> None:
    if target.exists():
        if not target.is_dir():
            print(f"[new-project] target {target} exists and is not a directory", file=sys.stderr)
            sys.exit(1)
        # Empty (ignoring .git) → fine. Non-empty → either --force was passed
        # (script use, e.g. via Make), or we ask the user interactively.
        children = [p for p in target.iterdir() if p.name != ".git"]
        if children and not force:
            if not sys.stdin.isatty():
                print(
                    f"[new-project] target {target} is not empty (pass --force to overlay into it)",
                    file=sys.stderr,
                )
                sys.exit(1)
            print(f"[new-project] target {target} already contains:")
            for p in sorted(children)[:10]:
                print(f"    {p.name}{'/' if p.is_dir() else ''}")
            if len(children) > 10:
                print(f"    ... and {len(children) - 10} more")
            print("[new-project] .git/ (if present) will be left untouched.")
            try:
                resp = input("Overlay the scaffold on top of these files? [y/N]: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\n[new-project] cancelled", file=sys.stderr)
                sys.exit(130)
            if resp not in {"y", "yes"}:
                print("[new-project] aborted by user", file=sys.stderr)
                sys.exit(1)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)


def build_ignore(exclude_patterns: list[str], scaffold_root: Path):
    """Return a shutil.copytree-compatible ignore callback.

    Patterns match relative POSIX paths from the scaffold root (e.g.
    "notebooks/*.ipynb", "data/", ".scaffold.yml"). The scaffold's own
    metadata files and the instructor-only hooks are always excluded.
    """
    always_excluded = {
        MANIFEST_NAME,
        ".scaffold-test.py",
    }

    def ignore(dirpath: str, names: list[str]) -> list[str]:
        rel_dir = Path(dirpath).resolve().relative_to(scaffold_root.resolve())
        skipped: set[str] = set()
        for name in names:
            if name in always_excluded and rel_dir == Path("."):
                skipped.add(name)
                continue
            rel = (rel_dir / name).as_posix()
            # Treat directories as both "dir" and "dir/"
            full = Path(dirpath) / name
            for pat in exclude_patterns:
                candidates = [rel, name]
                if full.is_dir():
                    candidates.append(rel + "/")
                if any(fnmatch.fnmatch(c, pat) for c in candidates):
                    skipped.add(name)
                    break
        return sorted(skipped)

    return ignore


def copy_scaffold(manifest: ScaffoldManifest, target: Path) -> None:
    ignore = build_ignore(manifest.exclude, manifest.path)
    shutil.copytree(manifest.path, target, ignore=ignore, dirs_exist_ok=True)


def run_post_init(manifest: ScaffoldManifest, target: Path) -> int:
    if not manifest.post_init:
        return 0
    hook = target / manifest.post_init
    if not hook.exists():
        print(f"[new-project] post-init script {hook} not found", file=sys.stderr)
        return 3
    print(f"[new-project] running post-init hook: {manifest.post_init}")
    try:
        proc = subprocess.run(
            [sys.executable, str(hook), str(target)],
            cwd=str(target),
            timeout=POST_INIT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        print(f"[new-project] post-init hook timed out after {POST_INIT_TIMEOUT_S}s", file=sys.stderr)
        return 4
    if proc.returncode != 0:
        print(f"[new-project] post-init hook failed (rc={proc.returncode})", file=sys.stderr)
        return 4
    return 0


def print_next_steps(manifest: ScaffoldManifest, target: Path) -> None:
    if not manifest.next_steps:
        return
    print()
    print(f"Scaffolded {manifest.name} → {target}")
    print("Next steps:")
    for step in manifest.next_steps:
        print(f"  $ {step.format(target=target)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a capstone project into a new directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--scaffold", help="scaffold name (skip interactive pick)")
    parser.add_argument("--target", help="target directory (skip interactive prompt)")
    parser.add_argument("--force", action="store_true", help="overlay into a non-empty target")
    parser.add_argument("--list", action="store_true", help="list available scaffolds and exit")
    parser.add_argument(
        "--no-post-init", action="store_true", help="skip the scaffold's post-init hook"
    )
    args = parser.parse_args()

    scaffolds = discover_scaffolds()
    if not scaffolds:
        print(f"[new-project] no scaffolds found under {SCAFFOLDS_ROOT}", file=sys.stderr)
        return 2

    if args.list:
        for s in scaffolds:
            print(f"{s.name:20s}  {s.title}")
            if s.description:
                for line in s.description.splitlines():
                    print(f"  {line}")
            print()
        return 0

    by_name = {s.name: s for s in scaffolds}
    try:
        if args.scaffold:
            if args.scaffold not in by_name:
                print(
                    f"[new-project] no scaffold named '{args.scaffold}'. Available: "
                    f"{', '.join(by_name)}",
                    file=sys.stderr,
                )
                return 1
            manifest = by_name[args.scaffold]
        else:
            manifest = prompt_scaffold(scaffolds)

        if args.target:
            target = Path(args.target).expanduser().resolve()
        else:
            target = prompt_target()
    except (KeyboardInterrupt, EOFError):
        print("\n[new-project] cancelled", file=sys.stderr)
        return 130

    validate_target(target, force=args.force)
    copy_scaffold(manifest, target)
    print(f"[new-project] copied {manifest.name} → {target}")

    if not args.no_post_init:
        rc = run_post_init(manifest, target)
        if rc != 0:
            return rc

    print_next_steps(manifest, target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
