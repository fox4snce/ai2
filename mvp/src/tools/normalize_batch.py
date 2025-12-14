from __future__ import annotations

import json
from typing import Any, Dict, List

from src.tools.normalize import normalize_email


def normalize_emails_batch(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool entry point: Normalize.EmailsBatch
    Input: { kind: "normalize_emails", emails: ["JEFF@Example.COM", ...] }
    Output: { normalized_emails: [...], final_answer: "<json array>" }
    """
    emails = (inputs or {}).get("emails", [])
    if not isinstance(emails, list) or any(not isinstance(e, str) for e in emails):
        return {"error": "invalid_emails", "final_answer": "Error: emails must be an array of strings"}

    normalized: List[str] = [normalize_email(e) for e in emails]
    return {"normalized_emails": normalized, "final_answer": json.dumps(normalized)}


