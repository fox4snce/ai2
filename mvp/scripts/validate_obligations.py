#!/usr/bin/env python3
r"""
Validate an obligations JSON file against the obligation schema and parser rules.

Usage:
  cd mvp
  .\.venv\Scripts\python scripts\validate_obligations.py path\to\obligations.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve()
MVP_ROOT = HERE.parents[1]

if str(MVP_ROOT) not in sys.path:
    sys.path.insert(0, str(MVP_ROOT))


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/validate_obligations.py path\\to\\obligations.json")
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"FAIL: file not found: {path}")
        return 2

    try:
        # Accept UTF-8 with BOM as well (common on Windows).
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as e:
        print(f"FAIL: invalid JSON: {e}")
        return 2

    try:
        from src.core.obligations import ObligationParser

        parser = ObligationParser()
        parsed = parser.parse_obligations(data)
    except Exception as e:
        print(f"FAIL: obligation parsing failed: {e}")
        return 1

    print(f"OK: parsed {len(parsed)} obligations")
    for i, ob in enumerate(parsed, start=1):
        kind = None
        if isinstance(ob.raw_payload, dict):
            kind = ob.raw_payload.get("kind") or ob.raw_payload.get("state") or None
        print(f"- {i}: type={ob.type} kind/state={kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


