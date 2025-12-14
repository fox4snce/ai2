import json

from src.main import MVPAPI


def test_planner_refuses_to_emit_step_when_inputs_missing_required_fields():
    """
    Planner (Reasoning.Core) should validate consumes schemas before emitting a step.
    If inputs are missing (e.g., query.count without 'word'), it should CLARIFY rather than
    emitting a plan that will fail at execution time or triggering toolsmith.
    """
    api = MVPAPI(":memory:")
    try:
        obligations = {
            "obligations": [
                {
                    "type": "ACHIEVE",
                    "payload": {
                        "state": "plan",
                        "mode": "planning",
                        "goal": {
                            "predicate": "capability.sequence",
                            "args": {
                                "sequence": [{"type": "REPORT", "kind": "query.count"}],
                                "inputs": {"query.count": {"letter": "r"}},  # missing word
                            },
                        },
                        "budgets": {"max_depth": 1, "beam": 1, "time_ms": 50},
                    },
                }
            ]
        }
        trace = api.execute_obligations(obligations)

        assert trace.get("status") == "clarify"
        assert "clarify" in trace and "word" in trace["clarify"]
        # Should not be a missing capability / toolsmith trigger.
        assert not trace.get("missing_capabilities")
        # Should not execute CountLetters since plan couldn't be emitted safely.
        tools = [tr.get("tool_name") for tr in trace.get("tool_runs", [])]
        assert "TextOps.CountLetters" not in tools
    finally:
        api.close()


