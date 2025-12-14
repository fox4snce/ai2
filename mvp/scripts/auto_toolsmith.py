#!/usr/bin/env python3
r"""
One-command automation loop:
1) Run obligations (in-process, no server)
2) Save the trace to .toolsmith/traces/
3) If trace contains missing_capabilities, invoke toolsmith on that trace
4) Save the rerun trace to .toolsmith/traces/

Usage (from repo root):
  cd mvp
  .\.venv\Scripts\python scripts\auto_toolsmith.py --obligations obligations.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


HERE = Path(__file__).resolve()
MVP_ROOT = HERE.parents[1]
REPO_ROOT = MVP_ROOT.parent

if str(MVP_ROOT) not in sys.path:
    sys.path.insert(0, str(MVP_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _read_json(path: Path) -> Dict[str, Any]:
    # Accept UTF-8 with BOM too (common on Windows editors/PowerShell).
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8", newline="\n")


def _stamp(prefix: str, trace: Dict[str, Any]) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tid = (trace.get("trace_id") or "no_trace_id").replace("-", "")[:16]
    return f"{ts}_{prefix}_{tid}.json"

def _print_tool_runs(label: str, trace: Dict[str, Any]) -> None:
    runs = trace.get("tool_runs") or []
    print(f"{label} tool_runs ({len(runs)}):")
    for i, tr in enumerate(runs, start=1):
        tool = (tr or {}).get("tool_name")
        out = (tr or {}).get("outputs")
        print(f"- {i}. tool={tool} outputs={out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--obligations", required=True, help="Path to obligations JSON (shape: {obligations:[...]})")
    ap.add_argument("--model", default="gpt-5-mini", help="Model name for toolsmith via llm_utils (fast model)")
    ap.add_argument("--dry-run", action="store_true", help="Run obligations and save trace, but do not invoke toolsmith")
    args = ap.parse_args()

    obligations_path = Path(args.obligations)
    obligations = _read_json(obligations_path)

    from src.main import MVPAPI

    api = MVPAPI(":memory:")
    try:
        trace = api.execute_obligations(obligations)
    finally:
        api.close()

    out_dir = REPO_ROOT / ".toolsmith" / "traces"
    trace_path = out_dir / _stamp("trace", trace)
    _write_json(trace_path, trace)
    print(f"Wrote trace: {trace_path}")
    _print_tool_runs("TRACE", trace)

    missing = trace.get("missing_capabilities") or []
    if not missing:
        print("No missing_capabilities. Done.")
        return 0

    if args.dry_run:
        print("missing_capabilities present, but --dry-run set. Skipping toolsmith.")
        return 0

    # Invoke toolsmith on the trace we just wrote.
    import scripts.toolsmith as toolsmith_mod

    # toolsmith uses argparse in main(); we call it via subprocess-style argv to keep behavior identical.
    # Configure model via args.
    old_argv = sys.argv
    try:
        sys.argv = ["toolsmith.py", "--trace", str(trace_path), "--model", str(args.model)]
        rc = int(toolsmith_mod.main() or 0)
    finally:
        sys.argv = old_argv

    # toolsmith already prints a rerun summary, but we also rerun and persist the new trace here.
    api2 = MVPAPI(":memory:")
    try:
        rerun = api2.execute_obligations(obligations)
    finally:
        api2.close()

    rerun_path = out_dir / _stamp("rerun", rerun)
    _write_json(rerun_path, rerun)
    print(f"Wrote rerun trace: {rerun_path}")
    _print_tool_runs("RERUN", rerun)

    # Exit non-zero if toolsmith failed.
    return rc


if __name__ == "__main__":
    raise SystemExit(main())


