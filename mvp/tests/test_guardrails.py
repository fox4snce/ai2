import json
from fastapi.testclient import TestClient

from src.api import app


def test_guardrails_fail_returns_justification():
    client = TestClient(app)
    body = {
        "obligations": [
            {
                "type": "ACHIEVE",
                "payload": {
                    "state": "plan",
                    "kind": "plan",
                    "mode": "planning",
                    "goal": {
                        "predicate": "event.scheduled",
                        "args": {"person": "Dana", "time": "2025-09-06T13:00-07:00"}
                    },
                    "guardrails": [
                        {"type": "MAINTAIN", "predicate": "calendar.free", "args": ["Dana", {"start": "2025-09-06T09:00-07:00", "end": "2025-09-06T17:00-07:00"}]},
                        {"type": "AVOID", "predicate": "double_book", "args": ["Dana", "2025-09-06T13:00-07:00"]}
                    ],
                    "budgets": {"max_depth": 3, "beam": 3, "time_ms": 150}
                }
            }
        ]
    }
    r = client.post("/v1/obligations/execute", json=body)
    assert r.status_code == 200
    t = r.json()
    assert t["status"] == "failed"
    # guardrail_failed should appear in some why_not location: we record per tool_run outputs
    tool_runs = t.get("tool_runs", [])
    found = any("guardrail_failed" in ((tr.get("outputs") or {}).get("why_not") or []) for tr in tool_runs)
    assert found
    # justification present
    justifications = [(tr.get("outputs") or {}).get("justification") for tr in tool_runs]
    justifications = [j for j in justifications if j]
    assert justifications and isinstance(justifications[0], list)
    # no assertions emitted for planning
    assert not t.get("assertions")


