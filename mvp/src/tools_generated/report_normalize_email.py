import re
from typing import Dict

def _normalize_email(email: str) -> str:
    """Normalize an email address deterministically.

    Steps:
    - Strip leading/trailing whitespace
    - Remove all internal whitespace characters (if any)
    - Lowercase the entire address

    This is a simple, deterministic normalization suitable for reporting
    and matching purposes.
    """
    if email is None:
        return ""
    s = str(email)
    s = s.strip()
    # Remove any internal whitespace (spaces, tabs, newlines) which are invalid in emails
    s = re.sub(r"\s+", "", s)
    s = s.lower()
    return s


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

    normalized = _normalize_email(email)
    final = f"Normalized email: {normalized}"
    return {
        "final_answer": final,
        "normalized_email": normalized
    }
