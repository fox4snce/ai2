#!/usr/bin/env python3
r"""
Fast, local-only "toolbox sprawl" check.

Goal: automatic awareness without automatic token spend.

It never calls an LLM. It just counts generated tools/kinds and enforces cooldowns.

Usage:
  cd mvp
  .\.venv\Scripts\python scripts\consolidation_check.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any

import yaml


HERE = Path(__file__).resolve()
MVP_ROOT = HERE.parents[1]
REPO_ROOT = MVP_ROOT.parent


def _read_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _write_state(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8", newline="\n")


def main() -> int:
    gen_contracts = MVP_ROOT / "contracts" / "tools" / "generated"
    gen_py = MVP_ROOT / "src" / "tools_generated"
    state_path = REPO_ROOT / ".toolsmith" / "consolidation_state.json"

    contracts = sorted(list(gen_contracts.glob("*.y*ml"))) if gen_contracts.exists() else []
    py_files = sorted([p for p in gen_py.glob("*.py") if p.name != "__init__.py"]) if gen_py.exists() else []

    kinds = set()
    for c in contracts:
        try:
            d = yaml.safe_load(c.read_text(encoding="utf-8")) or {}
            for cons in (d.get("consumes") or []):
                if isinstance(cons, dict) and isinstance(cons.get("kind"), str):
                    kinds.add(cons["kind"])
        except Exception:
            continue

    tool_count = len(contracts)
    kind_count = len(kinds)
    ratio = (tool_count / kind_count) if kind_count else tool_count

    # Policy knobs (simple defaults)
    MAX_TOOLS = 25
    MAX_RATIO = 1.8
    COOLDOWN_SEC = 24 * 3600
    MIN_NEW_TOOLS_SINCE_LAST = 5

    now = int(time.time())
    state = _read_state(state_path)
    last_suggest = int(state.get("last_suggest_ts") or 0)
    last_tool_count = int(state.get("last_tool_count") or 0)

    new_tools = max(0, tool_count - last_tool_count)
    cooldown_ok = (now - last_suggest) >= COOLDOWN_SEC

    recommend = False
    reasons = []
    if tool_count >= MAX_TOOLS:
        recommend = True
        reasons.append(f"generated_tool_contracts={tool_count} >= {MAX_TOOLS}")
    if kind_count and ratio >= MAX_RATIO:
        recommend = True
        reasons.append(f"tools_to_kinds_ratio={ratio:.2f} >= {MAX_RATIO}")

    if recommend and (not cooldown_ok or new_tools < MIN_NEW_TOOLS_SINCE_LAST):
        # Gated by cooldown/new-tools threshold
        recommend = False

    print(f"Generated contracts: {tool_count}  Generated python: {len(py_files)}  Distinct kinds: {kind_count}  Ratio: {ratio:.2f}")
    if recommend:
        print("CONSOLIDATION_RECOMMENDED:", "; ".join(reasons))
        state["last_suggest_ts"] = now
    state["last_tool_count"] = tool_count
    state["last_check_ts"] = now
    _write_state(state_path, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


