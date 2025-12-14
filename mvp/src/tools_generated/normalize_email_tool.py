"""
Deterministic email normalization tool.
Expects inputs of kind 'normalize_email' with an 'email' string.
Normalizes by trimming surrounding whitespace and lowercasing the entire address.
Returns a dict containing at least 'final_answer' (the normalized email string)
and 'normalized_email' for convenience.
"""
from typing import Dict


def _normalize_email_str(email: str) -> str:
    # Trim surrounding whitespace
    s = email.strip()
    # If contains @, lowercase local and domain parts deterministically
    if '@' in s:
        local, domain = s.split('@', 1)
        return f"{local.lower()}@{domain.lower()}"
    # Otherwise just lowercase the whole string
    return s.lower()


def run(inputs: Dict) -> Dict:
    """Run the normalization.

    Args:
        inputs: dict with keys 'kind' == 'normalize_email' and 'email' (string)

    Returns:
        dict with 'final_answer' (string) and 'normalized_email' (string)
    """
    if not isinstance(inputs, dict):
        raise TypeError("inputs must be a dict")
    kind = inputs.get('kind')
    if kind != 'normalize_email':
        raise ValueError("inputs['kind'] must be exactly 'normalize_email'")
    email = inputs.get('email')
    if not isinstance(email, str):
        raise ValueError("inputs['email'] must be a string")

    normalized = _normalize_email_str(email)
    return {
        'final_answer': normalized,
        'normalized_email': normalized
    }
