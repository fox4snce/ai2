from __future__ import annotations

import re
from typing import Any, Dict, List


_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b")
_EMAIL_RE_STRICT = re.compile(r"(?i)\b[A-Z0-9](?:[A-Z0-9._%+\-]{0,62}[A-Z0-9])?@[A-Z0-9](?:[A-Z0-9\-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9\-]{0,61}[A-Z0-9])?)+\b")


def extract_emails(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool entry point: EmailOps.Extract
    Input: { kind: "email.extract", text: "<blob>" }
    Output: { emails: [...], final_answer: "<json array>" }
    """
    text = (inputs or {}).get("text", "")
    if not isinstance(text, str):
        return {"error": "invalid_text", "final_answer": "Error: text must be a string"}

    found = _EMAIL_RE.findall(text)
    # Deterministic normalization for extraction output: strip surrounding whitespace only.
    emails = [e.strip() for e in found if isinstance(e, str) and e.strip()]
    return {"emails": emails, "final_answer": __import__("json").dumps(emails)}


def extract_emails_strict(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool entry point: EmailOps.ExtractStrict
    Stricter extraction with additional checks to reduce false positives.
    """
    text = (inputs or {}).get("text", "")
    if not isinstance(text, str):
        return {"error": "invalid_text", "final_answer": "Error: text must be a string"}

    found = _EMAIL_RE_STRICT.findall(text)
    emails = []
    for e in found:
        if not isinstance(e, str):
            continue
        s = e.strip()
        if not s:
            continue
        # Extra deterministic checks: no consecutive dots in local part, no trailing dot in domain.
        local, _, dom = s.partition("@")
        if ".." in local:
            continue
        if dom.endswith("."):
            continue
        emails.append(s)
    return {"emails": emails, "final_answer": __import__("json").dumps(emails)}


def count_distinct_domains(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool entry point: EmailOps.CountDistinctDomains
    Input: { kind: "email.count_distinct_domains", emails: ["a@x.com", ...] }
    Output: { distinct_domains: [...], distinct_domain_count: N, final_answer: "N" }
    """
    emails = (inputs or {}).get("emails", [])
    deny = (inputs or {}).get("denylist_domains", []) or []
    if not isinstance(emails, list) or any(not isinstance(e, str) for e in emails):
        return {"error": "invalid_emails", "final_answer": "Error: emails must be an array of strings"}
    if deny is not None and (not isinstance(deny, list) or any(not isinstance(d, str) for d in deny)):
        return {"error": "invalid_denylist_domains", "final_answer": "Error: denylist_domains must be an array of strings"}
    deny_set = {d.strip().lower() for d in deny if isinstance(d, str) and d.strip()}

    domains = set()
    for e in emails:
        if "@" not in e:
            continue
        dom = e.split("@", 1)[1].strip().lower()
        if dom:
            if dom in deny_set:
                continue
            domains.add(dom)

    distinct = sorted(domains)
    return {
        "distinct_domains": distinct,
        "distinct_domain_count": len(distinct),
        "final_answer": str(len(distinct)),
    }


