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


def test_budget_truncation_depth_and_time():
    proc = Popen([sys.executable, "-m", "src.api"], stdout=PIPE, stderr=PIPE)
    try:
        assert wait_for_server(), "API server did not start in time"

        # Depth cap: forbid depth-2 chain by max_depth=1
        body_depth = {
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
                            {"predicate": "parentOf", "args": ["Bob", "Cara"]}
                        ],
                        "budgets": {"max_depth": 1, "beam": 10, "time_ms": 100}
                    }
                }
            ]
        }
        r = requests.post(BASE + "/v1/obligations/execute", json=body_depth)
        data = r.json()
        print("Depth status:", r.status_code, "trace status:", data.get("status"))
        assert r.status_code == 200
        assert data.get("status") in ("failed", "clarify")  # conductor marks failed on truncated
        tr = (data.get("tool_runs") or [])[0].get("outputs") or {}
        metrics = (tr.get("trajectory") or {}).get("metrics") or {}
        assert tr.get("status") == "truncated"
        assert metrics.get("depth_used") == 1
        assert metrics.get("time_ms", 0) >= 0

        # Time cap: simulate slow so we exceed time_ms
        body_time = {
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
                            {"predicate": "parentOf", "args": ["Bob", "Cara"]}
                        ],
                        "simulate_slow": True,
                        "budgets": {"max_depth": 3, "beam": 10, "time_ms": 1}
                    }
                }
            ]
        }
        r = requests.post(BASE + "/v1/obligations/execute", json=body_time)
        data = r.json()
        tr = (data.get("tool_runs") or [])[0].get("outputs") or {}
        metrics = (tr.get("trajectory") or {}).get("metrics") or {}
        print("Time metrics:", metrics)
        assert tr.get("status") == "truncated"
        assert metrics.get("time_ms", 0) >= 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


