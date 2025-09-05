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
        r = requests.post(BASE + "/v1/obligations/execute", json=body_multi)
        assert r.status_code == 200
        data = r.json()
        assert data.get("final_answer") == "true"

        # Planning: event.scheduled goal should return the canned steps list
        planning = {
            "obligations": [
                {
                    "type": "ACHIEVE",
                    "payload": {
                        "state": "plan",
                        "kind": "plan",
                        "goal": {"predicate": "event.scheduled", "args": {"person": "Dana", "time": "2025-09-06T13:00-07:00"}},
                        "budgets": {"max_depth": 3, "beam": 3, "time_ms": 150}
                    }
                }
            ]
        }
        r = requests.post(BASE + "/v1/obligations/execute", json=planning)
        assert r.status_code == 200
        steps = json.loads(r.json().get("final_answer", "[]"))
        assert steps == ["ResolvePerson", "CheckCalendar", "ProposeSlots", "CreateEvent"]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


