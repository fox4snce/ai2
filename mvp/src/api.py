"""
Deterministic Obligations API (FastAPI)

Endpoints:
- POST /v1/obligations/execute
- GET  /v1/tools

Maps engine outcomes to HTTP statuses:
- 200 OK: resolved | clarify
- 400 Bad Request: schema/validation error
- 422 Unprocessable Entity: no tool can satisfy
- 500 Internal Server Error: tool crash
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import uvicorn

from .main import MVPAPI

app = FastAPI(title="Deterministic Obligations API", version="0.1.0")
api = MVPAPI()


def classify_status(trace: Dict[str, Any]) -> int:
    # Schema errors
    if trace.get("final_answer", "").startswith("Error: Obligation parsing failed"):
        return 400
    # Clarify vs resolved vs failed
    status = trace.get("status")
    if status == "clarify":
        return 200
    if status == "resolved":
        return 200
    if status == "failed":
        # Differentiate no tool vs crash vs truncated budget
        err = trace.get("final_answer", "")
        # Inspect tool_runs
        truncated = False
        for tr in trace.get("tool_runs", []):
            out = (tr or {}).get("outputs") or {}
            if (out or {}).get("status") == "truncated":
                truncated = True
                break
            e = (tr or {}).get("error") or ""
            if "No tools available" in e or "No suitable tool" in e:
                return 422
        if truncated:
            return 200
        if "No tools available" in err or "No suitable tool" in err:
            return 422
        return 500
    # default OK if not provided
    return 200


@app.post("/v1/obligations/execute")
def execute_obligations(body: Dict[str, Any], authorization: Optional[str] = Header(default=None)):
    try:
        trace = api.execute_obligations(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    code = classify_status(trace)
    return JSONResponse(status_code=code, content=trace)


@app.get("/v1/tools")
def list_tools():
    tools = api.handler.registry.list_tools()
    return {"tools": tools}


if __name__ == "__main__":
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=False)


