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


def test_proof_and_provenance():
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
        print("Status:", r.status_code)
        data = r.json()
        print("Trace capabilities:", data.get("capabilities_satisfied"))
        tool_runs = data.get("tool_runs", [])
        assertions = data.get("assertions", [])
        print("Assertions:", assertions)
        assert r.status_code == 200
        assert data.get("final_answer") == "true"
        # proof_ref is trajectory id, and source is Reasoning.Core@...
        assert any(a.get("proof_ref", "").startswith("T_OB_") for a in assertions)
        assert any(a.get("source_id", "").startswith("Reasoning.Core@") for a in assertions)

        # negative: write no assertions
        body_neg = {
            "obligations": [
                {
                    "type": "REPORT",
                    "payload": {
                        "kind": "logic",
                        "mode": "deduction",
                        "domains": ["kinship"],
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
        print("Neg Status:", r.status_code)
        data = r.json()
        print("Neg Assertions:", data.get("assertions"))
        assert r.status_code == 200
        assert data.get("final_answer") == "false"
        # assert no new assertions for negative
        assert len(data.get("assertions", [])) == 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


