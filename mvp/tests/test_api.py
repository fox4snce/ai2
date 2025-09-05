"""API tests for deterministic obligations API."""

import json
import threading
import time
import requests
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


def test_api_endpoints():
    # Start server
    proc = Popen([sys.executable, "-m", "src.api"], stdout=PIPE, stderr=PIPE)
    try:
        assert wait_for_server(), "API server did not start in time"

        # Tools
        r = requests.get(BASE + "/v1/tools")
        assert r.status_code == 200
        assert "tools" in r.json()

        # Math 200
        r = requests.post(BASE + "/v1/obligations/execute", json={
            "obligations": [{"type": "REPORT", "payload": {"kind": "math", "expr": "2+2"}}]
        })
        assert r.status_code == 200
        data = r.json()
        assert data.get("final_answer") == "4"

        # Count 200
        r = requests.post(BASE + "/v1/obligations/execute", json={
            "obligations": [{"type": "REPORT", "payload": {"kind": "count", "letter": "r", "word": "strawberry"}}]
        })
        assert r.status_code == 200
        assert r.json().get("final_answer") == "3"

        # Clarify 200
        r = requests.post(BASE + "/v1/obligations/execute", json={
            "obligations": [{"type": "REPORT", "payload": {"kind": "status.name"}}]
        })
        assert r.status_code == 200
        data = r.json()
        assert data.get("final_answer", "") == ""
        assert "clarify" in data and "name" in data["clarify"]

        # 400 bad schema
        r = requests.post(BASE + "/v1/obligations/execute", json={"obligations": []})
        assert r.status_code == 400

        # 422 no tool
        r = requests.post(BASE + "/v1/obligations/execute", json={
            "obligations": [{"type": "REPORT", "payload": {"kind": "query.astronauts"}}]
        })
        assert r.status_code == 422

        # ACHIEVE + REPORT name flow 200
        r = requests.post(BASE + "/v1/obligations/execute", json={
            "obligations": [{"type": "ACHIEVE", "payload": {"state": "status.name", "value": "Jeff"}}]
        })
        assert r.status_code == 200
        r = requests.post(BASE + "/v1/obligations/execute", json={
            "obligations": [{"type": "REPORT", "payload": {"kind": "status.name"}}]
        })
        assert r.status_code == 200
        assert r.json().get("final_answer") == "Jeff"

        # PeopleSQL deterministic array 200
        r = requests.post(BASE + "/v1/obligations/execute", json={
            "obligations": [{
                "type": "REPORT",
                "payload": {
                    "kind": "query.people",
                    "filters": [{"is_friend": "user"}, {"city": "Seattle"}]
                }
            }]
        })
        assert r.status_code == 200
        names = json.loads(r.json().get("final_answer", "[]"))
        assert set(names) >= {"Alice Smith", "Bob Johnson"}

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


