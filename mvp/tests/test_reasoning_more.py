import time
import json
import sys
from subprocess import Popen, PIPE
import requests

BASE = "http://127.0.0.1:8000"


def wait_for_server(timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(BASE + "/v1/tools", timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.2)
    return False


def test_reasoning_multipath_grandparent_and_planning():
    proc = Popen([sys.executable, "-m", "src.api"], stdout=PIPE, stderr=PIPE)
    try:
        assert wait_for_server(), "API server did not start in time"

        # Multi-path: Alice->Bob->Cara and Alice->Beth->Cara
        body_multi = {
            "obligations": [
                {
                    "type": "REPORT",
                    "payload": {
                        "kind": "logic",
                        "mode": "deduction",
                        "domains": ["kinship"],
                        "query": {"predicate": "grandparentOf", "args": ["Alice", "Cara"]},
                        "facts": [
                            {"predicate": "parentOf", "args": ["Alice", "Bob"]},
                            {"predicate": "parentOf", "args": ["Bob", "Cara"]},
                            {"predicate": "parentOf", "args": ["Alice", "Beth"]},
                            {"predicate": "parentOf", "args": ["Beth", "Cara"]}
                        ],
                        "budgets": {"max_depth": 3, "beam": 4, "time_ms": 100}
                    }
                }
            ]
        }
        print("\n[Multi-path Deduction] Request:")
        print(json.dumps(body_multi, indent=2))
        r = requests.post(BASE + "/v1/obligations/execute", json=body_multi)
        print("Status:", r.status_code)
        data = r.json()
        print("final_answer=", data.get("final_answer"))
        expected = "true"
        actual = data.get("final_answer")
        print("Expected:", expected, "Actual:", actual)
        assert r.status_code == 200
        assert actual == expected

        # Planning: event.scheduled goal should return the canned steps list
        planning = {
            "obligations": [
                {
                    "type": "ACHIEVE",
                    "payload": {
                        "state": "plan",
                        "kind": "plan",
                        "mode": "planning",
                        "goal": {"predicate": "event.scheduled", "args": {"person": "Dana", "time": "2025-09-06T13:00-07:00"}},
                        "budgets": {"max_depth": 3, "beam": 3, "time_ms": 150}
                    }
                }
            ]
        }
        print("\n[Planning] Request:")
        print(json.dumps(planning, indent=2))
        r = requests.post(BASE + "/v1/obligations/execute", json=planning)
        print("Status:", r.status_code)
        resp = r.json()
        print("Trace clarify:", resp.get("clarify"))
        print("Final answer:", resp.get("final_answer"))
        # Ambiguity on person triggers clarify, not steps
        assert r.status_code == 200
        assert resp.get("final_answer", "") == ""
        assert "clarify" in resp and "person" in resp["clarify"]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


