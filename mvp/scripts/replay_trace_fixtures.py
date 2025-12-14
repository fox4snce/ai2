#!/usr/bin/env python3
r"""
Replay trace fixtures as a safety gate (manual).

This is intended to be used during consolidation apply:
- Re-run the obligations found in each trace fixture
- Compare key outputs (final_answer + normalize outputs) to the recorded trace

Usage:
  cd mvp
  .\.venv\Scripts\python scripts\replay_trace_fixtures.py --fixtures ..\.toolsmith\consolidation_plans\experiment_after_normalization.json

Or provide explicit trace paths:
  .\.venv\Scripts\python scripts\replay_trace_fixtures.py --trace ..\.toolsmith\traces\some_trace.json --trace ..\.toolsmith\traces\another.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


HERE = Path(__file__).resolve()
MVP_ROOT = HERE.parents[1]
REPO_ROOT = MVP_ROOT.parent

if str(MVP_ROOT) not in sys.path:
    sys.path.insert(0, str(MVP_ROOT))


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _extract_obligations_from_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    obs = []
    for o in (trace.get("obligations") or []):
        t = (o or {}).get("type")
        p = (o or {}).get("payload")
        if not t or not isinstance(p, dict):
            continue
        if t == "DISCOVER_OP":
            continue
        obs.append({"type": t, "payload": p})
    return {"obligations": obs}


def _normalize_runs_only(tool_runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for tr in tool_runs or []:
        tool = (tr or {}).get("tool_name") or ""
        if "Normalize" in str(tool):
            out.append(tr)
    return out


def _extract_normalized_signals(tool_runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract stable "normalized value" signals from tool outputs, ignoring tool naming.
    This is used to avoid false failures when the chosen tool name changes but the semantics do not.
    """
    signals: List[Dict[str, Any]] = []
    for tr in tool_runs or []:
        out = (tr or {}).get("outputs") or {}
        if not isinstance(out, dict):
            continue
        for k in ("normalized_email", "normalized_url", "normalized_phone", "normalized_value", "normalized"):
            if k in out and isinstance(out.get(k), str):
                signals.append({"key": k, "value": out.get(k)})
    # Stable ordering
    signals.sort(key=lambda x: (x["key"], x["value"]))
    return signals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", default=None, help="Path to a consolidation plan JSON (uses its trace_fixtures list)")
    ap.add_argument("--trace", action="append", default=[], help="Explicit trace json path (repeatable)")
    args = ap.parse_args()

    traces: List[Path] = []
    if args.fixtures:
        plan = _read_json(Path(args.fixtures))
        for rel in (plan.get("safety_gate", {}) or {}).get("trace_fixtures", []) or []:
            traces.append(REPO_ROOT / Path(rel))
    for t in args.trace:
        traces.append(Path(t))

    traces = [p for p in traces if p.exists()]
    if not traces:
        print("No trace fixtures found.")
        return 2

    from src.main import MVPAPI

    failures = 0
    for p in traces:
        recorded = _read_json(p)
        obligations = _extract_obligations_from_trace(recorded)
        api = MVPAPI(":memory:")
        try:
            rerun = api.execute_obligations(obligations)
        finally:
            api.close()

        # Compare final_answer and normalization tool outputs only (stable, relevant for consolidation).
        if rerun.get("final_answer") != recorded.get("final_answer"):
            # Allow mismatch if the normalized semantic signals match. This prevents "card house" failures
            # when tool selection or formatting changes but the normalized result is identical.
            rec_sig = _extract_normalized_signals(recorded.get("tool_runs") or [])
            run_sig = _extract_normalized_signals(rerun.get("tool_runs") or [])
            if rec_sig != run_sig:
                print(f"FAIL: final_answer mismatch for {p}")
                print(f"- recorded: {recorded.get('final_answer')}")
                print(f"- rerun:    {rerun.get('final_answer')}")
                print(f"- recorded_normalized_signals: {rec_sig}")
                print(f"- rerun_normalized_signals:    {run_sig}")
                failures += 1
                continue

        # For normalization consolidation, tool names and wrapper formatting may change.
        # The safety property we care about is that the normalized values remain identical.
        rec_sig = _extract_normalized_signals(recorded.get("tool_runs") or [])
        run_sig = _extract_normalized_signals(rerun.get("tool_runs") or [])
        if rec_sig != run_sig:
            print(f"FAIL: normalize semantic signals mismatch for {p}")
            print(f"- recorded_normalized_signals: {rec_sig}")
            print(f"- rerun_normalized_signals:    {run_sig}")
            failures += 1
            continue

        print(f"OK: {p}")

    if failures:
        print(f"{failures} failures")
        return 1
    print("All trace fixtures OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


