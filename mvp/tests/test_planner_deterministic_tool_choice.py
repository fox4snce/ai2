import json

from src.main import MVPAPI


def _get_reasoning_core_derived_tool(trace: dict) -> str | None:
    for tr in trace.get("tool_runs", []) or []:
        if tr.get("tool_name") != "Reasoning.Core":
            continue
        outputs = tr.get("outputs") or {}
        traj = outputs.get("trajectory") if isinstance(outputs, dict) else None
        steps = (traj or {}).get("steps") if isinstance(traj, dict) else None
        if isinstance(steps, list) and steps:
            derived = (steps[0] or {}).get("derived_from") or {}
            if isinstance(derived, dict):
                return derived.get("tool")
    return None


def test_contract_derived_planning_picks_deterministically_between_two_math_tools():
    """
    Goal:
      Same capability, two tools can satisfy it. Planner should pick deterministically.

    Setup:
      - EvalMath (latency_ms=5)
      - EvalMath.Slow (latency_ms=50)

    Pass:
      - Same derived_from.tool every run
      - Same executed tool_name every run
      - Same final_answer every run
    """
    obligations = json.loads(open("schemas/obligations.demo_math_tool_choice.json", "r", encoding="utf-8-sig").read())

    api1 = MVPAPI(":memory:")
    try:
        t1 = api1.execute_obligations(obligations)
    finally:
        api1.close()

    api2 = MVPAPI(":memory:")
    try:
        t2 = api2.execute_obligations(obligations)
    finally:
        api2.close()

    assert t1.get("status") == "resolved"
    assert t2.get("status") == "resolved"

    # Planner determinism (derived_from.tool).
    assert _get_reasoning_core_derived_tool(t1) == "EvalMath"
    assert _get_reasoning_core_derived_tool(t2) == "EvalMath"

    # Execution determinism: conductor should also choose EvalMath, not EvalMath.Slow.
    tools1 = [tr.get("tool_name") for tr in t1.get("tool_runs", [])]
    tools2 = [tr.get("tool_name") for tr in t2.get("tool_runs", [])]
    assert "EvalMath" in tools1 and "EvalMath.Slow" not in tools1
    assert "EvalMath" in tools2 and "EvalMath.Slow" not in tools2

    # Output determinism.
    assert t1.get("final_answer") == t2.get("final_answer")
    assert json.loads(t1.get("final_answer")) == ["4"]


