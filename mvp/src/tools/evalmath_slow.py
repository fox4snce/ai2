from __future__ import annotations

from typing import Any, Dict


def run(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic math evaluator.

    This intentionally duplicates EvalMath behavior but is meant to be a
    lower-priority alternative (by contract policy fields like latency_ms).
    """
    expr = (inputs or {}).get("expr", "")
    try:
        allowed_chars = set("0123456789+-*/().eE ")
        if not isinstance(expr, str):
            return {"error": "Expression must be a string"}
        if not all(c in allowed_chars for c in expr):
            return {"error": "Invalid characters in expression"}

        result = eval(expr)
        if not isinstance(result, (int, float)):
            return {"error": "Expression must evaluate to a number"}
        return {"result": result}
    except ZeroDivisionError:
        return {"error": "Division by zero"}
    except SyntaxError:
        return {"error": "Invalid syntax"}
    except Exception as e:
        return {"error": f"Evaluation failed: {str(e)}"}


