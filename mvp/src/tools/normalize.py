from __future__ import annotations

import re
from typing import Any, Dict, Tuple
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


def normalize_email(email: str) -> str:
    if email is None:
        return ""
    s = str(email).strip()
    s = re.sub(r"\s+", "", s)
    return s.lower()


def _ensure_scheme(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme:
        return url
    return "https://" + url


def normalize_url(url: str) -> str:
    url_with_scheme = _ensure_scheme(str(url).strip())
    parsed = urlparse(url_with_scheme)

    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    hostname = (parsed.hostname or "").lower()

    port = parsed.port
    netloc = hostname
    if port is not None:
        default_port = 443 if scheme == "https" else 80
        if port != default_port:
            netloc = f"{hostname}:{port}"

    path = parsed.path or ""
    if path == "/":
        path = ""
    elif path.endswith("/"):
        path = path[:-1]

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if query_pairs:
        query_pairs.sort()
        query = urlencode(query_pairs, doseq=True)
    else:
        query = ""

    fragment = ""
    return urlunparse((scheme, netloc, path, "", query, fragment))


def normalize_phone(phone: str) -> str:
    if phone is None:
        phone = ""
    s = phone if isinstance(phone, str) else str(phone)
    s = s.strip()
    has_plus = s.startswith("+")
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits == "":
        return ""
    if has_plus:
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits


def normalize(target: str, value: str) -> Tuple[str, str]:
    """
    Returns (normalized_value, specific_key)
    """
    t = (target or "").strip().lower()
    if t == "email":
        return normalize_email(value), "normalized_email"
    if t == "url":
        return normalize_url(value), "normalized_url"
    if t == "phone":
        return normalize_phone(value), "normalized_phone"
    return "", "normalized_value"


def run(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool entry point for Normalize.
    Expects: { "target": "email|url|phone", "value": "<string>" }
    Outputs:
      - normalized_value (generic)
      - normalized_<target> (specific key)
      - final_answer (stable, human readable)
    """
    if not isinstance(inputs, dict):
        return {"final_answer": "Error: inputs must be a dict", "error": "invalid_inputs"}
    target = inputs.get("target")
    value = inputs.get("value")
    if not isinstance(target, str) or not isinstance(value, str):
        return {"final_answer": "Error: missing/invalid target/value", "error": "invalid_args"}
    normalized_value, specific_key = normalize(target, value)
    out: Dict[str, Any] = {
        "target": target,
        "original_value": value,
        "normalized_value": normalized_value,
        "final_answer": f"normalized_{target.strip().lower()}: {normalized_value}",
        "success": True,
    }
    # Also include specific key for compatibility with wrapper expectations.
    if specific_key:
        out[specific_key] = normalized_value
    return out


