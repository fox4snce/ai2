"""
Identity policy stubs for canonical IDs and alias handling.

Phase 0: Provide simple helpers that can be extended later.
"""

from typing import List


def canonicalize_name(name: str) -> str:
    """Return a canonical, lowercased, trimmed form of a name."""
    return (name or "").strip().lower()


def stable_id_for_names(names: List[str]) -> str:
    """Compute a stable identifier from a list of alias names."""
    import hashlib
    canon = ",".join(sorted(canonicalize_name(n) for n in names if n))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


