import json
from typing import Dict, Any
import sys
from pathlib import Path

from fastapi.testclient import TestClient

# Ensure repo mvp root is on sys.path so `src` package is importable when run as a script
sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.api import app


def run_obligation(obligations: Dict[str, Any]) -> Dict[str, Any]:
    client = TestClient(app)
    # The API expects the deterministic obligations shape directly
    r = client.post("/v1/obligations/execute", json=obligations)
    r.raise_for_status()
    return r.json()


def demo_logic_true() -> Dict[str, Any]:
    obligations = {
        "obligations": [
            {
                "type": "REPORT",
                "payload": {
                    "kind": "logic",
                    "mode": "deduction",
                    "query": {"predicate": "grandparentOf", "args": ["Alice", "Cara"]},
                    "facts": [
                        {"predicate": "parentOf", "args": ["Alice", "Bob"]},
                        {"predicate": "parentOf", "args": ["Bob", "Cara"]}
                    ],
                    "domains": ["kinship"],
                    "budgets": {"max_depth": 3, "beam": 4, "time_ms": 100}
                }
            }
        ]
    }
    return run_obligation(obligations)


def demo_plan_clarify() -> Dict[str, Any]:
    obligations = {
        "obligations": [
            {
                "type": "ACHIEVE",
                "payload": {
                    "state": "plan",
                    "mode": "planning",
                    "goal": {"predicate": "event.scheduled", "args": {"person": "Dana", "time": "2025-09-06T13:00-07:00"}},
                    "budgets": {"max_depth": 3, "beam": 3, "time_ms": 150}
                }
            }
        ]
    }
    return run_obligation(obligations)


def demo_truncated() -> Dict[str, Any]:
    obligations = {
        "obligations": [
            {
                "type": "REPORT",
                "payload": {
                    "kind": "logic",
                    "mode": "deduction",
                    "query": {"predicate": "grandparentOf", "args": ["Alice", "Cara"]},
                    "facts": [
                        {"predicate": "parentOf", "args": ["Alice", "Bob"]},
                        {"predicate": "parentOf", "args": ["Bob", "Cara"]}
                    ],
                    "domains": ["kinship"],
                    "budgets": {"max_depth": 1, "beam": 4, "time_ms": 100}
                }
            }
        ]
    }
    return run_obligation(obligations)


def main():
    cases = [
        ("logic_true", demo_logic_true),
        ("plan_clarify", demo_plan_clarify),
        ("logic_truncated", demo_truncated),
    ]
    results = {}
    for name, fn in cases:
        trace = fn()
        results[name] = {
            "status": trace.get("status"),
            "final_answer": trace.get("final_answer"),
            "capabilities": trace.get("capabilities_satisfied"),
            "tool_runs": trace.get("tool_runs"),
            "assertions": trace.get("assertions"),
        }
        print(f"=== {name} ===")
        print(json.dumps(results[name], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


