#!/usr/bin/env python3
r"""
Deterministic diff helper for consolidation plan JSON files.

This intentionally prints a small, stable summary (no noisy full diffs):
- tool contract additions/removals
- trace fixture additions/removals
- fingerprint changes

Usage:
  cd mvp
  .\.venv\Scripts\python scripts\diff_consolidation_plans.py before.json after.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _tool_id(t: Dict[str, Any]) -> str:
    return f"{t.get('name')}@{t.get('contract_path')}"


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/diff_consolidation_plans.py before.json after.json")
        return 2

    before = _read_json(Path(sys.argv[1]))
    after = _read_json(Path(sys.argv[2]))

    bmeta = before.get("meta") or {}
    ameta = after.get("meta") or {}

    print("FINGERPRINTS")
    print(f"- tool_registry: {bmeta.get('tool_registry_fingerprint')} -> {ameta.get('tool_registry_fingerprint')}")
    print(f"- trace_set:     {bmeta.get('trace_set_fingerprint')} -> {ameta.get('trace_set_fingerprint')}")

    btools = before.get("analysis", {}).get("tools") or []
    atools = after.get("analysis", {}).get("tools") or []
    bset = {_tool_id(t) for t in btools if isinstance(t, dict)}
    aset = {_tool_id(t) for t in atools if isinstance(t, dict)}

    added_tools = sorted(aset - bset)
    removed_tools = sorted(bset - aset)

    print("\nTOOLS")
    print(f"- before: {len(bset)}  after: {len(aset)}")
    if added_tools:
        print("- added:")
        for x in added_tools:
            print(f"  - {x}")
    if removed_tools:
        print("- removed:")
        for x in removed_tools:
            print(f"  - {x}")
    if not added_tools and not removed_tools:
        print("- no tool set changes")

    bfix = before.get("safety_gate", {}).get("trace_fixtures") or []
    afix = after.get("safety_gate", {}).get("trace_fixtures") or []
    bfix_set = set([str(x) for x in bfix])
    afix_set = set([str(x) for x in afix])

    added_fix = sorted(afix_set - bfix_set)
    removed_fix = sorted(bfix_set - afix_set)

    print("\nTRACE FIXTURES")
    print(f"- before: {len(bfix_set)}  after: {len(afix_set)}")
    if added_fix:
        print("- added:")
        for x in added_fix:
            print(f"  - {x}")
    if removed_fix:
        print("- removed:")
        for x in removed_fix:
            print(f"  - {x}")
    if not added_fix and not removed_fix:
        print("- no fixture set changes")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


