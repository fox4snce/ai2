import json

from src.main import MVPAPI


def test_reasoning_core_plan_executes_emitted_obligations():
    """
    If Reasoning.Core emits a trajectory whose steps contain obligation objects,
    the conductor should execute those obligations deterministically.
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
                                "sequence": [
                                    {"type": "REPORT", "kind": "query.math"},
                                    {"type": "REPORT", "kind": "query.count"},
                                ],
                                "inputs": {
                                    "query.math": {"expr": "2+2"},
                                    "query.count": {"letter": "r", "word": "strawberry"},
                                },
                            },
                        },
                        "budgets": {"max_depth": 1, "beam": 1, "time_ms": 50},
                    },
                }
            ]
        }
        trace = api.execute_obligations(obligations)

        assert trace.get("status") == "resolved"

        # Expect multi-tool runs: Reasoning.Core (plan) + EvalMath + CountLetters.
        tools = [tr.get("tool_name") for tr in trace.get("tool_runs", [])]
        assert "Reasoning.Core" in tools
        assert "EvalMath" in tools
        assert "TextOps.CountLetters" in tools

        # Parent returns a deterministic summary: JSON list of step final answers.
        answers = json.loads(trace.get("final_answer"))
        assert answers[0] == "4"
        assert answers[1] == "3"
    finally:
        api.close()


