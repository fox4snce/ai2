#!/usr/bin/env python3
r"""
Stability experiment:
1) Generate a normalization consolidation plan (before)
2) Add a new generated normalizer tool by running auto_toolsmith on normalize_phone
3) Generate the normalization plan again (after)
4) Diff the two plan JSONs with a stable summary

Usage:
  cd mvp
  .\.venv\Scripts\python scripts\run_consolidation_stability_experiment.py --model gpt-5-mini
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve()
MVP_ROOT = HERE.parents[1]
REPO_ROOT = MVP_ROOT.parent
PLANS_DIR = REPO_ROOT / ".toolsmith" / "consolidation_plans"


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, cwd=str(MVP_ROOT))
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5-mini")
    args = ap.parse_args()

    py = MVP_ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = MVP_ROOT / ".venv" / "bin" / "python"

    PLANS_DIR.mkdir(parents=True, exist_ok=True)

    before_md = PLANS_DIR / "experiment_before_normalization.md"
    after_md = PLANS_DIR / "experiment_after_normalization.md"

    # 1) before
    _run([str(py), "scripts/consolidate_tools.py", "--family", "normalization", "--out", str(before_md), "--write-json"])
    before_json = before_md.with_suffix(".json")
    print(f"BEFORE plan: {before_json}")

    # 2) add normalize_phone tool
    obligations = MVP_ROOT / "schemas" / "obligations.normalize_phone.json"
    _run([str(py), "scripts/auto_toolsmith.py", "--obligations", str(obligations), "--model", str(args.model)])

    # 3) after
    _run([str(py), "scripts/consolidate_tools.py", "--family", "normalization", "--out", str(after_md), "--write-json"])
    after_json = after_md.with_suffix(".json")
    print(f"AFTER plan: {after_json}")

    # 4) diff
    _run([str(py), "scripts/diff_consolidation_plans.py", str(before_json), str(after_json)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


