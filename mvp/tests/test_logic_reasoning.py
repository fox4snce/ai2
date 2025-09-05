import json
import requests
import time
import sys
from subprocess import Popen, PIPE

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


def test_reasoning_grandparent_true_and_false():
    proc = Popen([sys.executable, "-m", "src.api"], stdout=PIPE, stderr=PIPE)
    try:
        assert wait_for_server(), "API server did not start in time"

        # Positive case: Alice -> Bob -> Cara
        body = {
            "obligations": [
                {
                    "type": "REPORT",
                    "payload": {
                        "kind": "logic",
                        "query": {"predicate": "grandparentOf", "args": ["Alice", "Cara"]},
                        "facts": [
                            {"predicate": "parentOf", "args": ["Alice", "Bob"]},
                            {"predicate": "parentOf", "args": ["Bob", "Cara"]}
                        ],
                        "budgets": {"max_depth": 3, "beam": 4, "time_ms": 100}
                    }
                }
            ]
        }
        r = requests.post(BASE + "/v1/obligations/execute", json=body)
        assert r.status_code == 200
        data = r.json()
        assert data.get("final_answer") == "true"

        # Negative case: no chain
        body_neg = {
            "obligations": [
                {
                    "type": "REPORT",
                    "payload": {
                        "kind": "logic",
                        "query": {"predicate": "grandparentOf", "args": ["Alice", "Zoe"]},
                        "facts": [
                            {"predicate": "parentOf", "args": ["Alice", "Bob"]}
                        ],
                        "budgets": {"max_depth": 3, "beam": 4, "time_ms": 100}
                    }
                }
            ]
        }
        r = requests.post(BASE + "/v1/obligations/execute", json=body_neg)
        assert r.status_code == 200
        data = r.json()
        assert data.get("final_answer") == "false"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


