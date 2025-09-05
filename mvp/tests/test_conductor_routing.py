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


def test_routing_prefers_reasoning_core_and_capabilities():
    proc = Popen([sys.executable, "-m", "src.api"], stdout=PIPE, stderr=PIPE)
    try:
        assert wait_for_server(), "API server did not start in time"
        body = {
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
                        "budgets": {"max_depth": 3, "beam": 4, "time_ms": 100}
                    }
                }
            ]
        }
        r = requests.post(BASE + "/v1/obligations/execute", json=body)
        data = r.json()
        print("Capabilities:", data.get("capabilities_satisfied"))
        tool_runs = data.get("tool_runs", [])
        assert r.status_code == 200
        assert any(tr.get("tool_name") == "Reasoning.Core" for tr in tool_runs)
        assert "REPORT.logic" in (data.get("capabilities_satisfied") or [])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


