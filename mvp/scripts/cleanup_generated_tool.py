#!/usr/bin/env python3
r"""
Cleanup toolsmith-generated artifacts (tool contract + python + pytest + run logs).

This is meant for "reset the test / start over" workflows.

Usage (from repo root):
  cd mvp
  .\.venv\Scripts\python scripts\cleanup_generated_tool.py --tool NormalizeEmail --yes

Other selectors:
  .\.venv\Scripts\python scripts\cleanup_generated_tool.py --kind normalize_email --yes

By default this is a dry-run. Use --yes to actually delete.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List


HERE = Path(__file__).resolve()
MVP_ROOT = HERE.parents[1]
REPO_ROOT = MVP_ROOT.parent


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "tool"


def _collect_paths(tool: str | None, kind: str | None) -> List[Path]:
    paths: List[Path] = []

    # Contracts
    contracts_dir = MVP_ROOT / "contracts" / "tools" / "generated"
    if contracts_dir.exists():
        if tool:
            paths += list(contracts_dir.glob(f"{_slug(tool)}.yaml"))
            paths += list(contracts_dir.glob(f"{_slug(tool)}.yml"))
        if kind:
            # best-effort: sometimes toolsmith names align with kind
            paths += list(contracts_dir.glob(f"*{_slug(kind)}*.yaml"))
            paths += list(contracts_dir.glob(f"*{_slug(kind)}*.yml"))

    # Python code
    py_dir = MVP_ROOT / "src" / "tools_generated"
    if py_dir.exists():
        if tool:
            paths += list(py_dir.glob(f"*{_slug(tool)}*.py"))
        if kind:
            paths += list(py_dir.glob(f"*{_slug(kind)}*.py"))

    # Generated pytest files
    tests_dir = MVP_ROOT / "tests"
    if tests_dir.exists():
        if tool:
            paths += list(tests_dir.glob(f"test_generated*{_slug(tool)}*.py"))
        if kind:
            paths += list(tests_dir.glob(f"test_generated*{_slug(kind)}*.py"))

    # Toolsmith run logs (outside mvp/)
    runs_dir = REPO_ROOT / ".toolsmith" / "toolsmith_runs"
    if runs_dir.exists():
        if tool:
            paths += list(runs_dir.glob(f"{_slug(tool)}/**/*"))
            paths += [runs_dir / _slug(tool)]
        if kind:
            paths += list(runs_dir.glob(f"*{_slug(kind)}*/**/*"))

    # De-dupe and keep only existing files/dirs
    uniq = []
    seen = set()
    for p in paths:
        try:
            rp = p.resolve()
        except Exception:
            rp = p
        if str(rp) in seen:
            continue
        if p.exists():
            uniq.append(p)
            seen.add(str(rp))
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=None, help="Tool name (e.g., NormalizeEmail)")
    ap.add_argument("--kind", default=None, help="Obligation kind (e.g., normalize_email)")
    ap.add_argument("--yes", action="store_true", help="Actually delete (otherwise dry-run)")
    args = ap.parse_args()

    if not args.tool and not args.kind:
        print("Provide --tool or --kind")
        return 2

    targets = _collect_paths(args.tool, args.kind)
    if not targets:
        print("No matching generated artifacts found.")
        return 0

    print("Matched paths:")
    for p in targets:
        print(f"- {p}")

    if not args.yes:
        print("\nDry-run only. Re-run with --yes to delete.")
        return 0

    # Delete files first, then empty dirs.
    for p in targets:
        if p.is_file():
            try:
                p.unlink()
            except Exception as e:
                print(f"FAIL deleting file {p}: {e}")

    # Try removing empty directories
    # (walk deepest first)
    dirs = sorted([p for p in targets if p.is_dir()], key=lambda x: len(str(x)), reverse=True)
    for d in dirs:
        try:
            if d.exists():
                d.rmdir()
        except Exception:
            pass

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


