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


def test_type_mismatch_and_rules_scope():
    proc = Popen([sys.executable, "-m", "src.api"], stdout=PIPE, stderr=PIPE)
    try:
        assert wait_for_server(), "API server did not start in time"

        # Type mismatch: args contain non-strings
        body_type = {
            "obligations": [
                {
                    "type": "REPORT",
                    "payload": {
                        "kind": "logic",
                        "mode": "deduction",
                        "domains": ["kinship"],
                        "query": {"predicate": "grandparentOf", "args": ["Alice", 123]},
                        "facts": [],
                        "budgets": {"max_depth": 3, "beam": 4, "time_ms": 100}
                    }
                }
            ]
        }
        r = requests.post(BASE + "/v1/obligations/execute", json=body_type)
        print("Type mismatch status:", r.status_code)
        data = r.json()
        print("Tool error:", (data.get("tool_runs") or [])[0].get("error"))
        assert r.status_code in (200, 500)
        assert "type_mismatch" in ((data.get("tool_runs") or [])[0].get("error") or "")

        # Rules scope: missing rules/domains
        body_rules = {
            "obligations": [
                {
                    "type": "REPORT",
                    "payload": {
                        "kind": "logic",
                        "mode": "deduction",
                        "query": {"predicate": "grandparentOf", "args": ["Alice", "Cara"]},
                        "facts": [],
                        "rules": [],
                        "domains": [],
                        "budgets": {"max_depth": 3, "beam": 4, "time_ms": 100}
                    }
                }
            ]
        }
        r = requests.post(BASE + "/v1/obligations/execute", json=body_rules)
        print("Rules scope status:", r.status_code)
        data = r.json()
        print("Tool error:", (data.get("tool_runs") or [])[0].get("error"))
        assert r.status_code in (200, 500)
        assert "no_rules_or_domains" in ((data.get("tool_runs") or [])[0].get("error") or "")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


