import json

from src.main import MVPAPI


def _find_tool_run(trace: dict, tool_name: str) -> dict | None:
    for tr in trace.get("tool_runs", []) or []:
        if tr.get("tool_name") == tool_name:
            return tr
    return None


def test_plan_execution_resolves_step_output_templates():
    """
    Test 2: Composition with data dependency (step 2 uses step 1 output).

    Mechanism:
      Trajectory steps can reference prior step outputs via {{STEP_1.result}},
      and the conductor resolves those references before executing the next tool.

    Pass:
      - Reasoning.Core trajectory retains the original template string
      - ReportNormalizeEmail tool input shows the substituted value (JEFF+4@Example.COM)
      - Output is normalized and includes the substituted value (jeff+4@example.com)
    """
    obligations = json.loads(
        open("schemas/obligations.demo_chain_math_then_normalize_email_template.json", "r", encoding="utf-8-sig").read()
    )

    api = MVPAPI(":memory:")
    try:
        trace = api.execute_obligations(obligations)
    finally:
        api.close()

    assert trace.get("status") == "resolved"

    rc = _find_tool_run(trace, "Reasoning.Core")
    assert rc is not None
    traj = (rc.get("outputs") or {}).get("trajectory") or {}
    steps = traj.get("steps") or []
    assert len(steps) >= 2
    step2_payload = (steps[1] or {}).get("obligation", {}).get("payload", {}) or {}
    assert step2_payload.get("email") == "JEFF+{{STEP_1.result}}@Example.COM"

    # Step 2 actual execution input should show resolved template value.
    rn = _find_tool_run(trace, "ReportNormalizeEmail")
    assert rn is not None
    assert (rn.get("inputs") or {}).get("email") == "JEFF+4@Example.COM"

    # And it should normalize successfully.
    assert (rn.get("outputs") or {}).get("normalized_email") == "jeff+4@example.com"


