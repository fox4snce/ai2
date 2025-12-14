#!/usr/bin/env python3
r"""
Toolsmith: turn DISCOVER_OP (missing capability) into a new tool contract + implementation + test.

High-level flow:
1) Read a trace JSON produced by the deterministic API / conductor.
2) Find DISCOVER_OP payloads (structured "missing_capability" goals).
3) Ask an LLM to draft:
   - a tool contract YAML (mvp/contracts/tools/generated/*.yaml)
   - a python implementation (mvp/src/tools_generated/*.py) exposing `run(inputs: dict) -> dict`
   - a pytest test (mvp/tests/test_generated_*.py)
4) Run the generated test locally.
5) If the test passes, re-run the original obligations using MVPAPI.

Usage (from repo root):
  cd mvp
  .\.venv\Scripts\python scripts\toolsmith.py --trace path\to\trace.json

Requires OPENAI_API_KEY to be available in the environment (llm_utils.py will use it).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


HERE = Path(__file__).resolve()
MVP_ROOT = HERE.parents[1]
REPO_ROOT = MVP_ROOT.parent

if str(MVP_ROOT) not in sys.path:
    sys.path.insert(0, str(MVP_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "tool"


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _extract_discover_ops(trace: Dict[str, Any]) -> List[Dict[str, Any]]:
    ops: List[Dict[str, Any]] = []
    for o in (trace.get("emitted_obligations") or []):
        if (o or {}).get("type") == "DISCOVER_OP":
            ops.append(o)
    for o in (trace.get("obligations") or []):
        if (o or {}).get("type") == "DISCOVER_OP":
            ops.append(o)
    # de-dupe by id when present
    seen = set()
    out = []
    for o in ops:
        oid = o.get("id") or json.dumps(o, sort_keys=True)
        if oid in seen:
            continue
        seen.add(oid)
        out.append(o)
    return out


def _extract_original_obligations(trace: Dict[str, Any]) -> Dict[str, Any]:
    # Trace obligations are already serialized as {id, type, status, payload}
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


def _load_tool_schema() -> Dict[str, Any]:
    schema_path = MVP_ROOT / "schemas" / "tool.schema.json"
    return _read_json(schema_path)

def _toolsmith_dir() -> Path:
    return REPO_ROOT / ".toolsmith" / "toolsmith_runs"


def _llm_generate_tool(
    missing_capability: Dict[str, Any],
    tool_schema: Dict[str, Any],
) -> Dict[str, Any]:
    # Use project-provided GPT utilities (Responses API / JSON mode fallback).
    try:
        import llm_utils
    except Exception as e:
        raise RuntimeError(f"Failed to import llm_utils.py from repo root: {e}")

    system = (
        "You are a code synthesis toolsmith.\n"
        "You produce a NEW tool that satisfies a missing capability in an obligations->tools system.\n"
        "Return ONLY a JSON object (no markdown) with these keys:\n"
        "- tool_name: string (unique, PascalCase or dotted)\n"
        "- contract_yaml: string (YAML) that validates against the tool schema\n"
        "- python_module_name: string (python import path) for implementation, e.g. 'src.tools_generated.foo'\n"
        "- python_code: string (python) implementing a callable 'run(inputs: dict) -> dict'\n"
        "- pytest_filename: string (file name only) like 'test_generated_foo.py'\n"
        "- pytest_code: string (python) test that fails before the tool exists and passes after\n"
        "\n"
        "Constraints:\n"
        "- The python implementation MUST be deterministic.\n"
        "- The tool MUST return outputs with a 'final_answer' string so the conductor can render it.\n"
        "- The tool contract implementation.entry_point MUST point to python_module_name + '.run'.\n"
        "- Keep everything ASCII-only.\n"
        "- IMPORTANT: Use missing_capability.required_input_kind EXACTLY as the tool consumes.kind, and in satisfies as REPORT(<required_input_kind>).\n"
    )
    user = {
        "missing_capability": missing_capability,
        "tool_schema": tool_schema,
        "notes": [
            "This system routes obligations to tools based on tool contracts.",
            "REPORT tools are matched via satisfies: ['REPORT(X)'] and consumes kind 'X'.",
            "Obligation payloads have a 'kind' field; sometimes it is 'query.something', sometimes it is a plain kind like 'normalize_url'.",
        ],
    }
    # Optional: allow caller to force a specific fast model via env used by llm_utils
    # (llm_utils selects model via IFE_FORCE_MINI + IFE_FAST_MODEL).
    # toolsmith defaults to "gpt-5-mini" by setting those env vars in main().

    json_schema = {
        "name": "toolsmith_output",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["tool_name", "contract_yaml", "python_module_name", "python_code", "pytest_filename", "pytest_code"],
            "properties": {
                "tool_name": {"type": "string"},
                "contract_yaml": {"type": "string"},
                "python_module_name": {"type": "string"},
                "python_code": {"type": "string"},
                "pytest_filename": {"type": "string"},
                "pytest_code": {"type": "string"},
            },
        },
    }

    prompt = json.dumps(user, indent=2)
    out = llm_utils.generate_json_response(
        input_text=prompt,
        system_prompt=system,
        temperature=0.1,
        gen_id="toolsmith.generate",
        json_schema=json_schema,
    )
    if not isinstance(out, dict):
        raise RuntimeError("llm_utils.generate_json_response did not return a dict")
    # Clean text fields to avoid non-ASCII surprises on Windows consoles/editors.
    for k in ("tool_name", "contract_yaml", "python_module_name", "python_code", "pytest_filename", "pytest_code"):
        if isinstance(out.get(k), str):
            out[k] = llm_utils.clean_text(out[k])
    return out

def _llm_repair_tool_code(
    *,
    missing_capability: Dict[str, Any],
    tool_schema: Dict[str, Any],
    python_module_name: str,
    current_python_code: str,
    pytest_code: str,
    pytest_output: str,
    attempt: int,
) -> str:
    """
    Ask the LLM to repair ONLY the tool implementation so that the existing pytest passes.
    """
    try:
        import llm_utils
    except Exception as e:
        raise RuntimeError(f"Failed to import llm_utils.py from repo root: {e}")

    system = (
        "You are repairing a deterministic python tool implementation.\n"
        "You MUST NOT change the test.\n"
        "Return ONLY a JSON object with key: python_code.\n"
        "Constraints:\n"
        "- Keep it deterministic.\n"
        "- Keep it ASCII-only.\n"
        "- Provide a full module that defines run(inputs: dict) -> dict.\n"
        "- Ensure outputs include a 'final_answer' string.\n"
    )
    user = {
        "attempt": attempt,
        "missing_capability": missing_capability,
        "tool_schema": tool_schema,
        "python_module_name": python_module_name,
        "current_python_code": current_python_code,
        "pytest_code": pytest_code,
        "pytest_output": pytest_output,
    }
    json_schema = {
        "name": "toolsmith_repair",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["python_code"],
            "properties": {"python_code": {"type": "string"}},
        },
    }
    out = llm_utils.generate_json_response(
        input_text=json.dumps(user, indent=2),
        system_prompt=system,
        temperature=0.1,
        gen_id="toolsmith.repair",
        json_schema=json_schema,
    )
    if not isinstance(out, dict) or not isinstance(out.get("python_code"), str):
        raise RuntimeError("LLM did not return python_code during repair")
    return llm_utils.clean_text(out["python_code"])


def _run_pytest(venv_python: Path, test_path: Path) -> Tuple[int, str]:
    p = subprocess.run(
        [str(venv_python), "-m", "pytest", str(test_path), "-q"],
        cwd=str(MVP_ROOT),
        capture_output=True,
        text=True,
    )
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    return p.returncode, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, help="Path to a trace JSON file")
    ap.add_argument("--model", default="gpt-5-mini", help="OpenAI model name")
    ap.add_argument("--max-repair-attempts", type=int, default=3, help="Max repair iterations if generated test fails")
    ap.add_argument("--dry-run", action="store_true", help="Generate but do not write files or run tests")
    args = ap.parse_args()

    trace_path = Path(args.trace)
    trace = _read_json(trace_path)

    discover_ops = _extract_discover_ops(trace)
    if not discover_ops:
        print("No DISCOVER_OP found in trace.")
        return 2

    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        print("Missing OPENAI_API_KEY in environment.")
        return 2

    # Configure llm_utils model selection for this run.
    os.environ["IFE_FORCE_MINI"] = "1"
    os.environ["IFE_FAST_MODEL"] = str(args.model or "gpt-5-mini")

    tool_schema = _load_tool_schema()

    venv_python = MVP_ROOT / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        # fallback (non-windows)
        venv_python = MVP_ROOT / ".venv" / "bin" / "python"

    for op in discover_ops:
        goal = ((op.get("payload") or {}).get("goal"))
        if not isinstance(goal, dict):
            print("DISCOVER_OP goal is not a structured object; skipping:", goal)
            continue
        missing = goal

        draft = _llm_generate_tool(missing, tool_schema)

        tool_name = str(draft.get("tool_name") or "GeneratedTool")
        contract_yaml = str(draft.get("contract_yaml") or "")
        python_module_name = str(draft.get("python_module_name") or "")
        python_code = str(draft.get("python_code") or "")
        pytest_filename = str(draft.get("pytest_filename") or "")
        pytest_code = str(draft.get("pytest_code") or "")

        if not (contract_yaml and python_module_name and python_code and pytest_filename and pytest_code):
            print("LLM output missing required fields. Aborting.")
            return 2

        mod_slug = _slug(python_module_name.split(".")[-1])
        py_path = MVP_ROOT / "src" / "tools_generated" / f"{mod_slug}.py"
        yaml_path = MVP_ROOT / "contracts" / "tools" / "generated" / f"{_slug(tool_name)}.yaml"
        test_path = MVP_ROOT / "tests" / pytest_filename

        print(f"Drafted tool: {tool_name}")
        print(f"- contract: {yaml_path}")
        print(f"- code:     {py_path}")
        print(f"- test:     {test_path}")

        if args.dry_run:
            continue

        _write_text(py_path, python_code)
        _write_text(yaml_path, contract_yaml)
        _write_text(test_path, pytest_code)

        # Iterative repair loop: if the generated test fails, feed the failure back to the LLM
        # and ask it to repair ONLY the tool code until tests pass or we hit the limit.
        attempt_dir = _toolsmith_dir() / f"{_slug(tool_name)}"
        attempt_dir.mkdir(parents=True, exist_ok=True)

        rc = 1
        out = ""
        cur_code = python_code
        for attempt in range(1, max(1, int(args.max_repair_attempts)) + 2):  # 1 initial + repairs
            rc, out = _run_pytest(venv_python, test_path)
            _write_text(attempt_dir / f"attempt_{attempt:02d}_pytest.txt", out.strip() + "\n")
            _write_text(attempt_dir / f"attempt_{attempt:02d}_tool.py", cur_code)
            if rc == 0:
                print(out.strip())
                break
            print(out.strip())
            if attempt > int(args.max_repair_attempts):
                print("Generated test failed; leaving files for inspection.")
                return 1
            print(f"Repairing tool code using test failure (attempt {attempt}/{args.max_repair_attempts})...")
            cur_code = _llm_repair_tool_code(
                missing_capability=missing,
                tool_schema=tool_schema,
                python_module_name=python_module_name,
                current_python_code=cur_code,
                pytest_code=pytest_code,
                pytest_output=out,
                attempt=attempt,
            )
            _write_text(py_path, cur_code)

        # Re-run original obligations with a fresh API instance so the new contract is loaded.
        from src.main import MVPAPI

        original = _extract_original_obligations(trace)
        api = MVPAPI(":memory:")
        try:
            rerun = api.execute_obligations(original)
            print("RERUN status:", rerun.get("status"))
            print("RERUN final_answer:", rerun.get("final_answer"))
            # Always print what tool ran and what it output (for debugging).
            runs = rerun.get("tool_runs") or []
            print(f"RERUN tool_runs ({len(runs)}):")
            for i, tr in enumerate(runs, start=1):
                print(f"- {i}. tool={tr.get('tool_name')} outputs={tr.get('outputs')}")
        finally:
            api.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


