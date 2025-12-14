from __future__ import annotations

from typing import Any, Dict


def fail(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Always fails. Intended for policy-driven branching demos.
    """
    msg = (inputs or {}).get("message") or "failed"
    if not isinstance(msg, str):
        msg = str(msg)
    return {"error": msg}


