#!/usr/bin/env python3
r"""
Manual tool consolidation planner (NO changes by default).

This script produces a human-reviewable consolidation plan:
- duplicates / near-duplicates (by contract signature)
- a proposed "library tool" shape for a family (first target: normalization)
- wrapper strategy to preserve backward compatibility
- an explicit safety gate (tests + trace fixtures)

It does NOT call an LLM.
It does NOT modify files unless you explicitly pass --apply --yes (not recommended yet).

Usage:
  cd mvp
  .\.venv\Scripts\python scripts\consolidate_tools.py

  # write plan to a specific file
  .\.venv\Scripts\python scripts\consolidate_tools.py --out ..\.toolsmith\consolidation_plans\my_plan.md

  # (optional) apply mode is a stub for now; it refuses without --yes
  .\.venv\Scripts\python scripts\consolidate_tools.py --apply --yes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


HERE = Path(__file__).resolve()
MVP_ROOT = HERE.parents[1]
REPO_ROOT = MVP_ROOT.parent


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2)


def _hash_obj(obj: Any) -> str:
    b = _stable_json(obj).encode("utf-8")
    return hashlib.sha256(b).hexdigest()[:16]

def _file_sha256(path: Path) -> str:
    try:
        b = path.read_bytes()
    except Exception:
        b = _read_text(path).encode("utf-8", errors="replace")
    return hashlib.sha256(b).hexdigest()

def _tool_registry_fingerprint(tools: List[ToolInfo]) -> str:
    """
    Fingerprint the "world" the plan was generated from.
    We hash both contract paths and their current file content hashes so name changes
    or semantic changes are caught deterministically.
    """
    entries: List[Dict[str, Any]] = []
    for t in tools:
        rel = Path(t.contract_path)
        abs_path = MVP_ROOT / rel
        entries.append(
            {
                "name": t.name,
                "contract_path": t.contract_path,
                "contract_sha256": _file_sha256(abs_path) if abs_path.exists() else None,
                "signature_hash": t.signature_hash,
            }
        )
    return _hash_obj({"tools": entries})

def _trace_set_fingerprint(trace_paths: List[str]) -> str:
    entries: List[Dict[str, Any]] = []
    for rel in trace_paths:
        p = REPO_ROOT / Path(rel)
        entries.append({"path": rel, "sha256": _file_sha256(p) if p.exists() else None})
    return _hash_obj({"traces": entries})


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "plan"


@dataclass
class ToolInfo:
    name: str
    contract_path: str
    satisfies: List[str]
    consumes: List[Dict[str, Any]]
    produces: List[Dict[str, Any]]
    implementation: Dict[str, Any]
    signature_hash: str
    family: str


def _load_tool_contracts() -> List[ToolInfo]:
    tools_dir = MVP_ROOT / "contracts" / "tools"
    paths = list(tools_dir.rglob("*.yaml")) + list(tools_dir.rglob("*.yml"))
    infos: List[ToolInfo] = []
    for p in paths:
        # Skip adapters
        if any(part.lower() == "adapters" for part in p.parts):
            continue
        try:
            data = yaml.safe_load(_read_text(p)) or {}
        except Exception:
            continue
        if not isinstance(data, dict) or "name" not in data:
            continue
        name = str(data.get("name") or "")
        satisfies = list(data.get("satisfies") or [])
        consumes = list(data.get("consumes") or [])
        produces = list(data.get("produces") or [])
        impl = dict(data.get("implementation") or {})
        # Signature: satisfies + consumes schemas + produces assertion shapes (names are not authoritative)
        sig = {
            "satisfies": satisfies,
            "consumes": consumes,
            "produces": produces,
        }
        sig_hash = _hash_obj(sig)
        family = _infer_family(name, consumes, satisfies)
        infos.append(
            ToolInfo(
                name=name,
                contract_path=str(p.relative_to(MVP_ROOT)).replace("\\", "/"),
                satisfies=satisfies,
                consumes=consumes,
                produces=produces,
                implementation=impl,
                signature_hash=sig_hash,
                family=family,
            )
        )
    return sorted(infos, key=lambda x: x.name)


def _infer_family(name: str, consumes: List[Dict[str, Any]], satisfies: List[str]) -> str:
    n = (name or "").lower()
    if "normalize" in n:
        return "normalization"
    for c in consumes or []:
        k = (c or {}).get("kind")
        if isinstance(k, str) and k.startswith("normalize_"):
            return "normalization"
    for s in satisfies or []:
        if isinstance(s, str) and "normalize_" in s:
            return "normalization"
    return "other"


def _group_duplicates(tools: List[ToolInfo]) -> Dict[str, List[ToolInfo]]:
    groups: Dict[str, List[ToolInfo]] = {}
    for t in tools:
        groups.setdefault(t.signature_hash, []).append(t)
    return {h: ts for h, ts in groups.items() if len(ts) > 1}


def _find_near_duplicates(tools: List[ToolInfo]) -> List[Dict[str, Any]]:
    """
    Very conservative "near-duplicate" heuristic:
    - same family
    - same satisfies strings
    - same required fields in consumes schema (for the first consumes entry)
    """
    out: List[Dict[str, Any]] = []
    by_family: Dict[str, List[ToolInfo]] = {}
    for t in tools:
        by_family.setdefault(t.family, []).append(t)

    def req_fields(t: ToolInfo) -> Tuple[str, Tuple[str, ...]]:
        # (kind, required fields tuple)
        for c in t.consumes:
            if isinstance(c, dict):
                kind = str(c.get("kind") or "")
                schema = c.get("schema") if isinstance(c.get("schema"), dict) else {}
                req = schema.get("required") if isinstance(schema, dict) else None
                if isinstance(req, list):
                    return (kind, tuple(sorted([str(x) for x in req if isinstance(x, (str, int))])))
                return (kind, tuple())
        return ("", tuple())

    for fam, members in by_family.items():
        if fam == "other":
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                if sorted(a.satisfies) != sorted(b.satisfies):
                    continue
                if req_fields(a) != req_fields(b):
                    continue
                out.append(
                    {
                        "family": fam,
                        "reason": "same_satisfies_and_same_required_fields",
                        "a": {"name": a.name, "contract": a.contract_path},
                        "b": {"name": b.name, "contract": b.contract_path},
                    }
                )
    return out


def _collect_trace_fixtures(family: str) -> List[str]:
    traces_dir = REPO_ROOT / ".toolsmith" / "traces"
    if not traces_dir.exists():
        return []
    paths = sorted(traces_dir.glob("*.json"), reverse=True)
    fixtures: List[str] = []
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        # Detect if trace touches the family (normalize_ kinds or normalize tools)
        tool_runs = data.get("tool_runs") or []
        hit = False
        for tr in tool_runs:
            tn = str((tr or {}).get("tool_name") or "").lower()
            if family == "normalization" and "normalize" in tn:
                hit = True
                break
            out = (tr or {}).get("outputs") or {}
            if family == "normalization":
                if isinstance(out, dict) and any(k in out for k in ("normalized_url", "normalized_email")):
                    hit = True
                    break
        if hit:
            fixtures.append(str(p.relative_to(REPO_ROOT)).replace("\\", "/"))
        if len(fixtures) >= 12:
            break
    return fixtures


def _collect_tests_for_family(family: str) -> List[str]:
    tests_dir = MVP_ROOT / "tests"
    tests = sorted(tests_dir.glob("test_*.py"))
    out: List[str] = []
    for p in tests:
        name = p.name.lower()
        if family == "normalization":
            if "normalize" in name:
                out.append(str(p.relative_to(MVP_ROOT)).replace("\\", "/"))
    # Always include core suite runner (human instruction)
    return out


def _propose_normalization_library(tools: List[ToolInfo]) -> Dict[str, Any]:
    """
    Proposal-only: unify normalize_* into a single library tool while keeping wrappers.
    """
    norm_tools = [t for t in tools if t.family == "normalization"]
    kinds = []
    for t in norm_tools:
        for c in t.consumes:
            if isinstance(c, dict) and isinstance(c.get("kind"), str):
                kinds.append(c["kind"])
    kinds = sorted(set(kinds))

    return {
        "library_tool": {
            "name": "Normalize",
            "contract_path": "mvp/contracts/tools/normalize.yaml (proposed)",
            "implementation_path": "mvp/src/tools/normalize.py (proposed)",
            "idea": "Single stable implementation that normalizes multiple targets; old tools become wrappers.",
            "proposed_input_schema": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "enum": ["email", "url"]},
                    "value": {"type": "string"},
                },
                "required": ["target", "value"],
                "additionalProperties": False,
            },
            "proposed_output": {
                "type": "object",
                "properties": {
                    "normalized": {"type": "string"},
                    "final_answer": {"type": "string"},
                },
                "required": ["normalized", "final_answer"],
            },
        },
        "wrappers": [
            {
                "existing_tool": t.name,
                "existing_kinds": [c.get("kind") for c in t.consumes if isinstance(c, dict) and c.get("kind")],
                "wrapper_strategy": "Keep contract kind/satisfies stable, change implementation.entry_point to call Normalize(target=..., value=...).",
                "compatibility": "No obligation JSON changes required.",
                "notes": "Wrappers can live in tools_generated initially, later migrate to stable tools/ package.",
            }
            for t in norm_tools
        ],
        "observations": {
            "normalization_tool_count": len(norm_tools),
            "normalization_kinds": kinds,
        },
    }


def _render_plan_md(plan: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# Consolidation plan (manual, no changes)\n")
    lines.append(f"- Generated at: `{plan['meta']['generated_at']}`")
    lines.append(f"- Family: `{plan['meta']['family']}`")
    lines.append(f"- Tool contracts scanned: `{plan['meta']['tool_count']}`\n")
    lines.append("## Fingerprints (safety preflight)")
    lines.append(f"- Tool registry fingerprint: `{plan['meta']['tool_registry_fingerprint']}`")
    lines.append(f"- Trace set fingerprint: `{plan['meta']['trace_set_fingerprint']}`")
    lines.append("")
    lines.append(
        "If/when apply mode exists, it must refuse to run unless the current fingerprints match these values "
        "(meaning: tool contracts and trace fixtures are unchanged since plan generation)."
    )
    lines.append("")

    lines.append("## Duplicates (exact signature matches)")
    dups = plan["analysis"]["duplicates"]
    if not dups:
        lines.append("- (none)\n")
    else:
        for h, group in dups.items():
            lines.append(f"- **signature_hash `{h}`**:")
            for t in group:
                lines.append(f"  - `{t['name']}` (`{t['contract_path']}`)")
        lines.append("")

    lines.append("## Near-duplicates (conservative heuristic)")
    nd = plan["analysis"]["near_duplicates"]
    if not nd:
        lines.append("- (none)\n")
    else:
        for x in nd:
            lines.append(f"- **{x['reason']}**: `{x['a']['name']}` vs `{x['b']['name']}`")
        lines.append("")

    lines.append("## Proposed consolidation (normalization family)")
    prop = plan["proposal"]
    lib = prop["library_tool"]
    lines.append(f"- **New stable library tool**: `{lib['name']}`")
    lines.append(f"  - Contract: `{lib['contract_path']}`")
    lines.append(f"  - Implementation: `{lib['implementation_path']}`")
    lines.append(f"  - Idea: {lib['idea']}\n")
    lines.append("- **Wrappers (backward compatibility)**:")
    for w in prop["wrappers"]:
        lines.append(f"  - `{w['existing_tool']}` kinds={w['existing_kinds']}")
    lines.append("")

    lines.append("## Safety gate (must pass before any apply)")
    gate = plan["safety_gate"]
    lines.append("- **Tests**:")
    for t in gate["tests"]:
        lines.append(f"  - `{t}`")
    lines.append("- **Trace fixtures**:")
    for f in gate["trace_fixtures"]:
        lines.append(f"  - `{f}`")
    lines.append("")

    lines.append("## Apply mode (disabled by default)")
    lines.append("- This script currently only writes a plan.")
    lines.append("- When apply is implemented for real, it must be test-gated and produce a diff preview.\n")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default="normalization", choices=["normalization", "all"], help="Which family to plan for")
    ap.add_argument("--out", default=None, help="Plan output path (.md). Defaults to .toolsmith/consolidation_plans/<timestamp>_plan_<family>.md")
    ap.add_argument("--write-json", action="store_true", help="Also write a JSON version next to the markdown")
    ap.add_argument("--apply", action="store_true", help="(stub) apply changes (off by default)")
    ap.add_argument("--yes", action="store_true", help="Required for --apply (stub)")
    args = ap.parse_args()

    tools = _load_tool_contracts()
    family = args.family
    if family != "all":
        tools_family = [t for t in tools if t.family == family]
    else:
        tools_family = tools

    duplicates = _group_duplicates(tools_family)
    near_duplicates = _find_near_duplicates(tools_family)

    proposal = _propose_normalization_library(tools) if family in ("normalization", "all") else {}
    safety_gate = {
        "tests": [
            "python -m pytest -q",
            *(_collect_tests_for_family("normalization") if family in ("normalization", "all") else []),
            *(["python scripts/replay_trace_fixtures.py --fixtures <PLAN_JSON>"] if family in ("normalization", "all") else []),
        ],
        "trace_fixtures": _collect_trace_fixtures("normalization") if family in ("normalization", "all") else [],
    }

    tool_registry_fingerprint = _tool_registry_fingerprint(tools_family)
    trace_set_fingerprint = _trace_set_fingerprint(safety_gate["trace_fixtures"])

    plan = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "family": family,
            "tool_count": len(tools_family),
            "repo_root": str(REPO_ROOT),
            "mvp_root": str(MVP_ROOT),
            "tool_registry_fingerprint": tool_registry_fingerprint,
            "trace_set_fingerprint": trace_set_fingerprint,
        },
        "analysis": {
            "tools": [asdict(t) for t in tools_family],
            "duplicates": {h: [asdict(t) for t in ts] for h, ts in duplicates.items()},
            "near_duplicates": near_duplicates,
        },
        "proposal": proposal,
        "safety_gate": safety_gate,
    }

    default_out = REPO_ROOT / ".toolsmith" / "consolidation_plans" / f"{_now_stamp()}_plan_{_slug(family)}.md"
    out_path = Path(args.out) if args.out else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_render_plan_md(plan), encoding="utf-8", newline="\n")
    print(f"Wrote plan: {out_path}")

    if args.write_json:
        json_path = out_path.with_suffix(".json")
        json_path.write_text(_stable_json(plan), encoding="utf-8", newline="\n")
        print(f"Wrote plan JSON: {json_path}")

    if args.apply:
        if not args.yes:
            print("Refusing to apply without --yes (and apply mode is a stub for now).")
            return 2
        print("Apply mode is intentionally not implemented yet. Use the plan to guide manual refactors first.")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


