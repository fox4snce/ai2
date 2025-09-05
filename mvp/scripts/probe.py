import json
import requests

BASE = "http://127.0.0.1:8000"

def post(label, payload):
    print(f"\n=== {label} ===")
    r = requests.post(BASE + "/v1/obligations/execute", json=payload)
    print("status:", r.status_code)
    try:
        print("body:", json.dumps(r.json(), indent=2))
    except Exception:
        print("text:", r.text[:500])


def main():
    cases = []
    # logic true
    cases.append(("logic_true", {
        "obligations": [{
            "type": "REPORT",
            "payload": {
                "kind": "logic",
                "mode": "deduction",
                "domains": ["kinship"],
                "query": {"predicate": "grandparentOf", "args": ["Alice", "Cara"]},
                "facts": [
                    {"predicate": "parentOf", "args": ["Alice", "Bob"]},
                    {"predicate": "parentOf", "args": ["Bob", "Cara"]}
                ],
                "budgets": {"max_depth": 3, "beam": 4, "time_ms": 100}
            }
        }]
    }))
    # plan clarify
    cases.append(("plan_clarify", {
        "obligations": [{
            "type": "ACHIEVE",
            "payload": {
                "state": "plan",
                "mode": "planning",
                "goal": {"predicate": "event.scheduled", "args": {"person": "Dana", "time": "2025-09-06T13:00-07:00"}},
                "budgets": {"max_depth": 3, "beam": 3, "time_ms": 150}
            }
        }]
    }))
    # truncated
    cases.append(("logic_truncated", {
        "obligations": [{
            "type": "REPORT",
            "payload": {
                "kind": "logic",
                "mode": "deduction",
                "domains": ["kinship"],
                "query": {"predicate": "grandparentOf", "args": ["Alice", "Cara"]},
                "facts": [
                    {"predicate": "parentOf", "args": ["Alice", "Bob"]},
                    {"predicate": "parentOf", "args": ["Bob", "Cara"]}
                ],
                "budgets": {"max_depth": 1, "beam": 4, "time_ms": 100}
            }
        }]
    }))
    # guardrail fail
    cases.append(("guardrail_fail", {
        "obligations": [{
            "type": "ACHIEVE",
            "payload": {
                "state": "plan",
                "mode": "planning",
                "goal": {"predicate": "event.scheduled", "args": {"person": "Alice", "time": "2025-09-08T10:00Z"}},
                "guardrails": [{"predicate": "calendar.free", "args": ["Alice", {"start": "2025-09-08T09:00Z", "end": "2025-09-08T17:00Z"}]}],
                "budgets": {"max_depth": 3, "beam": 3, "time_ms": 150}
            }
        }]
    }))
    # people query
    cases.append(("people_query", {
        "obligations": [{
            "type": "REPORT",
            "payload": {"kind": "query.people", "filters": [{"city": "Seattle"}]}
        }]
    }))

    for label, payload in cases:
        post(label, payload)


if __name__ == "__main__":
    main()


