from typing import Dict

from src.tools.normalize import normalize_email


def run(inputs: Dict) -> Dict:
    """Run entry point for ReportNormalizeEmail tool.

    Expects an input dict matching the contract consumes.kind "normalize_email":
      {"email": "...", "kind": "normalize_email"}

    Returns a dict including 'final_answer' (string) and 'normalized_email' (string).
    """
    # Basic validation
    kind = inputs.get("kind") if isinstance(inputs, dict) else None
    if kind != "normalize_email":
        return {
            "final_answer": "Error: tool expects kind=normalize_email",
            "error": "invalid_kind"
        }

    email = inputs.get("email") if isinstance(inputs, dict) else None
    if not isinstance(email, str):
        return {
            "final_answer": "Error: missing or invalid 'email' field",
            "error": "invalid_email"
        }

    normalized = normalize_email(email)
    final = f"Normalized email: {normalized}"
    return {
        "final_answer": final,
        "normalized_email": normalized
    }
