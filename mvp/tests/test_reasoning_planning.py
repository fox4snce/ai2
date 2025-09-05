import json
import sys
from subprocess import Popen, PIPE
import time
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


def test_planning_safety_and_clarify():
    proc = Popen([sys.executable, "-m", "src.api"], stdout=PIPE, stderr=PIPE)
    try:
        assert wait_for_server(), "API server did not start in time"

        # Ambiguous Dana triggers clarify
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
        r = requests.post(BASE + "/v1/obligations/execute", json=planning)
        data = r.json()
        print("Planning clarify:", data.get("clarify"))
        assert r.status_code == 200
        assert data.get("final_answer", "") == ""
        assert "clarify" in data and "person" in data["clarify"]
        # Ensure no world-state assertions created
        assert len(data.get("assertions", [])) == 0

        # Non-ambiguous person yields plan steps, not world-state writes
        planning_ok = {
            "obligations": [
                {
                    "type": "ACHIEVE",
                    "payload": {
                        "state": "plan",
                        "kind": "plan",
                        "mode": "planning",
                        "goal": {"predicate": "event.scheduled", "args": {"person": "Sam", "time": "2025-09-06T13:00-07:00"}},
                        "budgets": {"max_depth": 3, "beam": 3, "time_ms": 150}
                    }
                }
            ]
        }
        r = requests.post(BASE + "/v1/obligations/execute", json=planning_ok)
        data = r.json()
        print("Plan steps:", data.get("final_answer"))
        assert r.status_code == 200
        steps = json.loads(data.get("final_answer", "[]"))
        assert steps == ["ResolvePerson", "CheckCalendar", "ProposeSlots", "CreateEvent"]
        assert len(data.get("assertions", [])) == 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


