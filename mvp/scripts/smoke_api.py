"""Simple smoke test for the FastAPI app using TestClient.
Run with: .venv\Scripts\python -m mvp.scripts.smoke_api (from repo root) or python -m mvp.scripts.smoke_api when venv active and cwd=mvp.
"""

import json
import os
import sys
from fastapi.testclient import TestClient

# Ensure we can import the package 'src' when running as a script
HERE = os.path.dirname(__file__)
PROJ_ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

from src.api import app


def main():
    c = TestClient(app)
    r = c.get("/v1/tools")
    print("TOOLS:", r.status_code, r.json())

    r = c.post(
        "/v1/obligations/execute",
        json={"obligations": [{"type": "REPORT", "payload": {"kind": "math", "expr": "2+2"}}]},
    )
    print("MATH:", r.status_code, r.json())

    r = c.post(
        "/v1/obligations/execute",
        json={
            "obligations": [
                {"type": "REPORT", "payload": {"kind": "count", "letter": "r", "word": "strawberry"}}
            ]
        },
    )
    print("COUNT:", r.status_code, r.json())

    r = c.post(
        "/v1/obligations/execute",
        json={"obligations": [{"type": "REPORT", "payload": {"kind": "status.name"}}]},
    )
    print("NAME clarify:", r.status_code, r.json())

    r = c.post("/v1/obligations/execute", json={"obligations": []})
    print("EMPTY obligations:", r.status_code, r.json())

    r = c.post(
        "/v1/obligations/execute",
        json={"obligations": [{"type": "REPORT", "payload": {"kind": "query.astronauts"}}]},
    )
    print("UNKNOWN tool:", r.status_code, r.json())


if __name__ == "__main__":
    main()


