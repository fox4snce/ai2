import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(os.getenv("IFE_RUN_LIVE_TOOLSMITH", "").strip() != "1", reason="live toolsmith integration test disabled")
def test_missing_capability_mid_plan_triggers_toolsmith_and_rerun_completes(tmp_path: Path):
    """
    Test 3 (integration):
      Plan executes step 1, fails missing capability at step 2, toolsmith generates tool,
      and the automatic rerun completes (no manual reruns, no human edits).
    """
    mvp_root = Path(__file__).resolve().parents[1]
    repo_root = mvp_root.parent

    # Use a unique kind each run to guarantee "missing" without manual cleanup.
    suffix = os.urandom(4).hex()
    kind = f"normalize_username_{suffix}"

    obligations = {
        "obligations": [
            {
                "type": "ACHIEVE",
                "payload": {
                    "state": "plan",
                    "mode": "planning",
                    "goal": {
                        "predicate": "capability.sequence",
                        "args": {
                            "sequence": [
                                {"type": "REPORT", "kind": "query.math"},
                                {"type": "REPORT", "kind": kind},
                            ],
                            "inputs": {
                                "query.math": {"expr": "2+2"},
                                kind: {"username": "  Jeff  "},
                            },
                        },
                    },
                    "budgets": {"max_depth": 1, "beam": 2, "time_ms": 50},
                },
            }
        ]
    }
    ob_path = tmp_path / f"obligations_{kind}.json"
    ob_path.write_text(json.dumps(obligations, indent=2), encoding="utf-8", newline="\n")

    # Run auto_toolsmith and capture paths.
    cmd = [sys.executable, "scripts/auto_toolsmith.py", "--obligations", str(ob_path), "--model", "gpt-5-mini"]
    proc = subprocess.run(cmd, cwd=str(mvp_root), capture_output=True, text=True, env=os.environ.copy(), timeout=600)
    assert proc.returncode == 0, f"auto_toolsmith failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

    # Extract trace paths written by the script.
    trace_paths = re.findall(r"Wrote (?:rerun )?trace:\s+(.+\.json)", proc.stdout)
    assert trace_paths, f"Could not find trace paths in output:\n{proc.stdout}"

    # First is trace, last is rerun trace.
    initial_trace_path = Path(trace_paths[0].strip())
    rerun_trace_path = Path(trace_paths[-1].strip())
    assert initial_trace_path.exists()
    assert rerun_trace_path.exists()

    initial = json.loads(initial_trace_path.read_text(encoding="utf-8-sig"))
    rerun = json.loads(rerun_trace_path.read_text(encoding="utf-8-sig"))

    # Initial run: step 1 ran, step 2 missing.
    tools_initial = [tr.get("tool_name") for tr in initial.get("tool_runs", [])]
    assert "EvalMath" in tools_initial
    assert (initial.get("missing_capabilities") or []), "Expected missing_capabilities in initial trace"

    # Rerun: should be resolved and show both tools executed.
    assert rerun.get("status") == "resolved"
    tools_rerun = [tr.get("tool_name") for tr in rerun.get("tool_runs", [])]
    assert "EvalMath" in tools_rerun
    assert not (rerun.get("missing_capabilities") or []), "Expected no missing_capabilities after toolsmith rerun"

    # Strong proof step 2 executed: some tool was invoked with inputs.kind == our unique kind.
    ran_kind = False
    for tr in rerun.get("tool_runs", []) or []:
        inp = (tr or {}).get("inputs") or {}
        if isinstance(inp, dict) and inp.get("kind") == kind:
            ran_kind = True
            break
    assert ran_kind, f"Expected a tool run with inputs.kind == {kind}"

    # Cleanup generated artifacts for this kind so this test doesn't permanently bloat the repo.
    cleanup = [sys.executable, "scripts/cleanup_generated_tool.py", "--kind", kind, "--yes"]
    _ = subprocess.run(cleanup, cwd=str(mvp_root), capture_output=True, text=True, env=os.environ.copy(), timeout=120)


