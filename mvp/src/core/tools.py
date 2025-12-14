"""
Tool registry and contract management.

This module handles tool registration, contract validation,
and tool selection based on obligations.
"""

import json
import yaml
import jsonschema
from typing import Dict, List, Optional, Any, Tuple
import hashlib
from dataclasses import dataclass
from pathlib import Path
import logging
import os
import importlib

logger = logging.getLogger(__name__)


@dataclass
class ToolContract:
    """Represents a tool contract."""
    name: str
    description: str
    version: str
    consumes: List[Dict]
    produces: List[Dict]
    satisfies: List[str]
    preconditions: List[str]
    postconditions: List[str]
    cost: str
    reliability: str
    latency_ms: int
    verify_mode: str = "blocking"
    capability_tier: str = "safe"
    auth_required: bool = False
    scopes: List[str] = None
    supports: List[str] = None
    implementation: Dict = None
    
    def __post_init__(self):
        if self.scopes is None:
            self.scopes = []
        if self.supports is None:
            self.supports = []
        if self.implementation is None:
            self.implementation = {}


class ToolRegistry:
    """Registry for managing tool contracts."""
    
    def __init__(self, contracts_dir: str = None, fail_on_schema_error: bool = True):
        """Initialize registry with contracts directory."""
        if contracts_dir is None:
            # Resolve to repo root/mvp/contracts/tools relative to this file
            base_dir = Path(__file__).resolve().parents[2]
            self.contracts_dir = base_dir / "contracts" / "tools"
        else:
            self.contracts_dir = Path(contracts_dir)
        self.tools: Dict[str, ToolContract] = {}
        self.fail_on_schema_error = fail_on_schema_error
        self.schema = self._load_tool_schema()
        self._load_tools()
    
    def _load_tool_schema(self) -> Dict:
        """Load tool contract schema."""
        base_dir = Path(__file__).resolve().parents[2]
        schema_path = base_dir / "schemas" / "tool.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)
    
    def _load_tools(self):
        """Load all tool contracts from directory (recursively)."""
        if not self.contracts_dir.exists():
            logger.warning(f"Contracts directory {self.contracts_dir} does not exist")
            return
        
        # Support both .yaml and .yml, recursively
        yaml_paths = list(self.contracts_dir.rglob("*.yaml")) + list(self.contracts_dir.rglob("*.yml"))
        
        for yaml_file in yaml_paths:
            # Skip adapters or non-tool specs by path
            if any(part.lower() == "adapters" for part in yaml_file.parts):
                logger.info(f"Skipping adapter/non-tool spec: {yaml_file}")
                continue
            try:
                tool_contract = self._load_tool_contract(yaml_file)
                self.tools[tool_contract.name] = tool_contract
                logger.info(f"Loaded tool: {tool_contract.name} from {yaml_file}")
            except Exception as e:
                logger.error(f"Failed to load tool from {yaml_file}: {e}")
                if self.fail_on_schema_error and not bool(os.getenv("ALLOW_TOOL_CONTRACT_ERRORS", "")):
                    raise
    
    def _load_tool_contract(self, yaml_file: Path) -> ToolContract:
        """Load a single tool contract from YAML file."""
        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)
        
        # Validate against schema
        try:
            jsonschema.validate(data, self.schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Invalid tool contract in {yaml_file}: {e.message}")
        
        return ToolContract(
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            consumes=data["consumes"],
            produces=data["produces"],
            satisfies=data["satisfies"],
            preconditions=data.get("preconditions", []),
            postconditions=data.get("postconditions", []),
            cost=data.get("cost", "medium"),
            reliability=data.get("reliability", "medium"),
            latency_ms=data.get("latency_ms", 100),
            verify_mode=data.get("verify_mode", "blocking"),
            capability_tier=data.get("capability_tier", "safe"),
            auth_required=data.get("auth_required", False),
            scopes=data.get("scopes", []),
            supports=data.get("supports", []),
            implementation=data.get("implementation", {})
        )
    
    def get_tool(self, name: str) -> Optional[ToolContract]:
        """Get tool contract by name."""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self.tools.keys())

    def find_support_tools(self, required_preconditions: List[str]) -> List[ToolContract]:
        """Find tools that declare support for any of the given preconditions."""
        if not required_preconditions:
            return []
        req = set(required_preconditions)
        results: List[ToolContract] = []
        for tool in self.tools.values():
            supports = set(tool.supports or [])
            if supports.intersection(req):
                results.append(tool)
        return results
    
    def find_tools_for_obligation(self, obligation_type: str) -> List[ToolContract]:
        """Find tools that can satisfy an obligation type."""
        matching_tools = []
        for tool in self.tools.values():
            for satisfies_pattern in tool.satisfies:
                # Handle pattern matching for REPORT(query.math) -> REPORT with kind=math
                if self._matches_obligation_pattern(obligation_type, satisfies_pattern, tool):
                    matching_tools.append(tool)
                    break
        return matching_tools
    
    def _matches_obligation_pattern(self, obligation_type: str, satisfies_pattern: str, tool: ToolContract) -> bool:
        """Check if obligation type matches a satisfies pattern."""
        # Direct match
        if obligation_type == satisfies_pattern:
            return True
        
        # Pattern matching for REPORT(query.X)
        if satisfies_pattern.startswith("REPORT(") and satisfies_pattern.endswith(")"):
            pattern_content = satisfies_pattern[7:-1]  # Remove "REPORT(" and ")"
            if obligation_type == "REPORT":
                for input_spec in tool.consumes:
                    if input_spec.get("kind") == pattern_content:
                        return True
        # Pattern matching for ACHIEVE(plan.X)
        if satisfies_pattern.startswith("ACHIEVE(") and satisfies_pattern.endswith(")"):
            pattern_content = satisfies_pattern[8:-1]  # Remove "ACHIEVE(" and ")"
            if obligation_type == "ACHIEVE":
                for input_spec in tool.consumes:
                    if input_spec.get("kind") == pattern_content:
                        return True
        
        return False
    
    def validate_tool_inputs(self, tool: ToolContract, obligation_payload: Dict) -> Tuple[bool, str]:
        """Validate that tool can handle the given inputs."""
        # If any of the declared input kinds are satisfied, accept (OR semantics for MVP)
        reasons = []
        for input_spec in tool.consumes:
            input_kind = input_spec["kind"]
            if self._payload_provides_input(input_kind, obligation_payload):
                return True, "Inputs satisfied"
            else:
                reasons.append(f"missing {input_kind}")
        return False, ", ".join(reasons) or "No matching inputs"
    
    def _payload_provides_input(self, input_kind: str, payload: Dict) -> bool:
        """Check if payload provides the required input kind."""
        # General case: if the obligation payload's kind matches the tool input kind, accept.
        # This is important for newly added query.* kinds (e.g., query.astronauts) that aren't hard-coded.
        try:
            if isinstance(payload, dict) and isinstance(payload.get("kind"), str) and payload.get("kind") == input_kind:
                return True
        except Exception:
            pass
        if input_kind == "query.math":
            return payload.get("kind") == "math" and "expr" in payload
        elif input_kind == "query.people":
            return payload.get("kind") == "query.people" and "filters" in payload
        elif input_kind == "query.count":
            return payload.get("kind") == "count" and "letter" in payload and "word" in payload
        elif input_kind == "query.status":
            return payload.get("kind") == "status" and "field" in payload
        elif input_kind == "query.logic":
            return payload.get("kind") == "logic" and isinstance(payload.get("query"), dict)
        elif input_kind == "plan.goal":
            # ACHIEVE with planning goal
            return (payload.get("kind") == "plan" and isinstance(payload.get("goal"), dict)) or (
                payload.get("state") == "plan" and isinstance(payload.get("goal"), dict)
            )
        else:
            # Generic check
            return input_kind in payload or f"query.{input_kind}" in payload.get("kind", "")
    
    def select_best_tool(self, obligation_type: str, obligation_payload: Dict, selection_seed: Optional[str] = None) -> Optional[ToolContract]:
        """Select the best tool for an obligation using the policy."""
        candidates = self.find_tools_for_obligation(obligation_type)
        
        if not candidates:
            return None
        
        # Filter candidates that can handle the inputs
        valid_candidates = []
        for tool in candidates:
            can_handle, reason = self.validate_tool_inputs(tool, obligation_payload)
            if can_handle:
                valid_candidates.append(tool)
            else:
                logger.debug(f"Tool {tool.name} cannot handle inputs: {reason}")
        
        if not valid_candidates:
            return None
        
        # Select by policy: reliability > cost > latency > alphabetical
        def tool_score(tool: ToolContract) -> Tuple[int, int, int, int]:
            reliability_score = {"high": 3, "medium": 2, "low": 1}[tool.reliability]
            cost_score = {"tiny": 4, "low": 3, "medium": 2, "high": 1}[tool.cost]
            latency_score = 1000 / max(tool.latency_ms, 1)  # Higher is better
            # Stable tiebreak using hash of (selection_seed, tool_name)
            local_seed = selection_seed or "default-seed"
            tiebreak_bytes = f"{local_seed}:{tool.name}".encode("utf-8")
            tiebreak_int = int(hashlib.sha256(tiebreak_bytes).hexdigest(), 16)
            return (reliability_score, cost_score, int(latency_score), tiebreak_int)
        
        return max(valid_candidates, key=tool_score)


class ToolExecutor:
    """Executes tools and manages their lifecycle."""
    
    def __init__(self, registry: ToolRegistry):
        """Initialize with tool registry."""
        self.registry = registry
        self.tool_implementations = {}
        self._load_tool_implementations()
        self._load_sandbox_policy()
    
    def _load_tool_implementations(self):
        """Load tool implementations."""
        # This would normally load actual tool implementations
        # For MVP, we'll create mock implementations
        self.tool_implementations = {
            "EvalMath": self._mock_evalmath,
            "TextOps.CountLetters": self._mock_countletters,
            "PeopleSQL": self._mock_peoplesql,
            "Reasoning.Core": self._mock_reasoning_core,
            "Prep.Stub": self._mock_prep_stub,
            "GuardrailChecker": self._mock_guardrail_checker
        }

        # Additionally, allow python tools to be loaded dynamically from their contract implementation.entry_point.
        # This is required for toolsmith-generated tools.
        for tool in (self.registry.tools or {}).values():
            impl = getattr(tool, "implementation", {}) or {}
            if impl.get("type") != "python":
                continue
            entry = impl.get("entry_point")
            if not isinstance(entry, str) or "." not in entry:
                continue
            # Don't override builtins unless explicitly desired later.
            if tool.name in self.tool_implementations:
                continue
            module_name, func_name = entry.rsplit(".", 1)
            try:
                mod = importlib.import_module(module_name)
                fn = getattr(mod, func_name)
                if callable(fn):
                    self.tool_implementations[tool.name] = fn
                    logger.info(f"Loaded python tool implementation for {tool.name} from {entry}")
            except Exception as e:
                logger.warning(f"Failed to import python tool {tool.name} entry_point={entry}: {e}")

    def _load_sandbox_policy(self):
        try:
            base_dir = Path(__file__).resolve().parents[2]
            policy_path = base_dir / "policies" / "sandbox.yaml"
            if policy_path.exists():
                with open(policy_path, "r") as f:
                    self.sandbox = yaml.safe_load(f) or {}
            else:
                self.sandbox = {"capabilities": {"safe": {}}, "secrets": {"vault": "env"}}
        except Exception:
            self.sandbox = {"capabilities": {"safe": {}}, "secrets": {"vault": "env"}}
    
    def execute_tool(self, tool_name: str, inputs: Dict) -> Dict:
        """Execute a tool with given inputs."""
        if tool_name not in self.tool_implementations:
            return {"error": f"Tool {tool_name} not implemented"}
        
        try:
            # Sandbox enforcement
            tool = self.registry.get_tool(tool_name)
            tier = getattr(tool, "capability_tier", "safe") if tool else "safe"
            caps = (self.sandbox.get("capabilities", {}) or {}).get(tier, {})
            # Simple deny logic example: net disallowed but inputs ask for net
            if caps is not None and caps.get("net") is False and inputs.get("requires_net"):
                return {"error": "capability_denied", "why_not": ["capability_denied"]}

            tool_func = self.tool_implementations[tool_name]
            result = tool_func(inputs)
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}")
            return {"error": str(e)}
    
    def _mock_evalmath(self, inputs: Dict) -> Dict:
        """Mock implementation of EvalMath."""
        expr = inputs.get("expr", "")
        try:
            # Simple safe evaluation for MVP
            allowed_chars = set('0123456789+-*/().eE ')
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
    
    def _mock_countletters(self, inputs: Dict) -> Dict:
        """Mock implementation of CountLetters."""
        letter = inputs.get("letter", "")
        word = inputs.get("word", "")
        
        if len(letter) != 1:
            return {"error": "Letter must be exactly one character"}
        
        if not word:
            return {"error": "Word must be non-empty"}
        
        count = word.count(letter)
        return {"count": count}
    
    def _mock_peoplesql(self, inputs: Dict) -> Dict:
        """Mock implementation of PeopleSQL."""
        filters = inputs.get("filters", [])
        
        # Mock data for testing
        mock_people = [
            {"id": "E3", "name": "Alice Smith", "city": "Seattle"},
            {"id": "E4", "name": "Bob Johnson", "city": "Seattle"},
            {"id": "E5", "name": "Charlie Brown", "city": "Portland"}
        ]
        
        # Simple filter logic for MVP
        results = []
        for person in mock_people:
            matches = True
            for filter_dict in filters:
                if "city" in filter_dict:
                    if person["city"] != filter_dict["city"]:
                        matches = False
                        break
                elif "is_friend" in filter_dict:
                    # Mock: assume Alice and Bob are friends
                    if person["name"] not in ["Alice Smith", "Bob Johnson"]:
                        matches = False
                        break
            
            if matches:
                results.append(person)
        
        return {"people": results}

    def _mock_prep_stub(self, inputs: Dict) -> Dict:
        """Mock preparation tool that marks preconditions as satisfied."""
        names = inputs.get("preconditions", [])
        return {"ok": True, "satisfied": names}

    def _mock_guardrail_checker(self, inputs: Dict) -> Dict:
        """Mock guardrail checker: returns failure for known violating predicates."""
        constraints = inputs.get("constraints", []) or []
        violations = []
        for c in constraints:
            pred = c.get("predicate") or c.get("pred")
            if pred == "calendar.free" and c.get("args"):
                # pretend the guardrail fails if person == "Alice" on Mondays
                args = c.get("args")
                who = args[0] if isinstance(args, list) and args else args.get("person") if isinstance(args, dict) else None
                if who in ("Alice", "Dana"):
                    violations.append({"predicate": pred, "args": args, "reason": "Busy at requested interval"})
            elif pred == "double_book":
                args = c.get("args")
                violations.append({"predicate": pred, "args": args, "reason": "Existing event overlaps the requested time"})
        if violations:
            return {"status": "failed", "justification": violations}
        return {"status": "passed"}

    def _mock_reasoning_core(self, inputs: Dict) -> Dict:
        """Minimal deterministic reasoning/planning stub.

        Deduction mode: if query predicate is grandparentOf and facts include a simple two-hop parent chain, return proof.
        Planning mode: return a canned 3-4 step plan for event.scheduled.
        Always enforces budgets presence; if missing, return error.
        """
        budgets = inputs.get("budgets")
        if not isinstance(budgets, dict):
            return {"error": "budgets_required"}
        # enforce hard caps (no real search in stub)
        mode = inputs.get("mode")
        if mode == "deduction":
            # boundary checks: query/facts types
            query = inputs.get("query", {})
            if not isinstance(query, dict):
                return {"error": "invalid_query_type"}
            facts = inputs.get("facts", [])
            if not isinstance(facts, list):
                return {"error": "invalid_facts_type"}
            # require either rules or domains to be present
            rules = inputs.get("rules", []) or []
            domains = inputs.get("domains", []) or []
            if len(rules) == 0 and len(domains) == 0:
                return {"error": "no_rules_or_domains"}
            query = inputs.get("query", {})
            pred = (query or {}).get("predicate")
            args = (query or {}).get("args", [])
            # domain/type enforcement
            if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
                return {"error": "type_mismatch"}
            # timers/metrics
            import time as _t
            t0 = _t.time()
            if pred == "grandparentOf" and len(args) == 2:
                # toy facts from inputs
                x, z = args[0], args[1]
                # build edge set for parentOf
                edges = []
                for f in facts:
                    if f.get("predicate") == "parentOf" and isinstance(f.get("args"), list) and len(f.get("args")) == 2:
                        edges.append((f.get("args")[0], f.get("args")[1]))
                y_candidates = sorted([y for (a, y) in edges if a == x])
                # If a chain is theoretically possible but depth cap prevents it, truncate early
                if budgets.get("max_depth") is not None and int(budgets.get("max_depth")) < 2:
                    if any((y, z) in edges for y in y_candidates):
                        dt = int((_t.time() - t0) * 1000)
                        return {"status": "truncated", "kind": "logic.answer", "value": None, "trajectory": {"steps": [], "alt_paths": [], "metrics": {"depth_used": 1, "nodes_expanded": 0, "time_ms": dt}}, "capabilities_satisfied": ["REPORT.logic"]}
                steps = []
                alt_paths = []
                found = False
                nodes = 0
                for y in y_candidates:
                    nodes += 1
                    # budget checks (beam, depth, time)
                    if budgets.get("beam") is not None and nodes > int(budgets.get("beam")):
                        dt = int((_t.time() - t0) * 1000)
                        return {"status": "truncated", "kind": "logic.answer", "value": None, "trajectory": {"steps": steps, "alt_paths": alt_paths, "metrics": {"depth_used": 1, "nodes_expanded": nodes, "time_ms": dt}}, "capabilities_satisfied": ["REPORT.logic"]}
                    if budgets.get("max_depth") is not None and int(budgets.get("max_depth")) < 2:
                        dt = int((_t.time() - t0) * 1000)
                        return {"status": "truncated", "kind": "logic.answer", "value": None, "trajectory": {"steps": steps, "alt_paths": alt_paths, "metrics": {"depth_used": 1, "nodes_expanded": nodes, "time_ms": dt}}, "capabilities_satisfied": ["REPORT.logic"]}
                    if budgets.get("time_ms") is not None:
                        if inputs.get("simulate_slow"):
                            _t.sleep(int(budgets.get("time_ms")) / 1000.0 + 0.001)
                        if int((_t.time() - t0) * 1000) > int(budgets.get("time_ms")):
                            dt = int((_t.time() - t0) * 1000)
                            return {"status": "truncated", "kind": "logic.answer", "value": None, "trajectory": {"steps": steps, "alt_paths": alt_paths, "metrics": {"depth_used": 1, "nodes_expanded": nodes, "time_ms": dt}}, "capabilities_satisfied": ["REPORT.logic"]}
                    if (y, z) in edges:
                        # Keep rule names ASCII-only so traces print cleanly on Windows consoles.
                        st = {"op": "infer", "rule": "parent_o_parent->grandparent", "bindings": {"X": x, "Y": y, "Z": z}}
                        (steps if not found else alt_paths).append(st)
                        found = True
                if found:
                    dt = int((_t.time() - t0) * 1000)
                    traj = {"steps": steps, "alt_paths": alt_paths, "metrics": {"depth_used": 1, "nodes_expanded": nodes, "time_ms": dt}, "rules_fired": [s["rule"] for s in steps], "why_not": []}
                    # attach rule_version to assertions (simple stub uses @1)
                    rv = f"{steps[0]['rule']}@1" if steps else None
                    return {
                        "kind": "logic.answer",
                        "value": True,
                        "trajectory": traj,
                        "assertions": [{"subject": f"{x}", "predicate": "grandparentOf", "object": f"{z}", "proof_ref": "local", "rule_version": rv}],
                        "capabilities_satisfied": ["REPORT.logic"]
                    }
                dt = int((_t.time() - t0) * 1000)
                return {"kind": "logic.answer", "value": False, "trajectory": {"steps": [], "metrics": {"depth_used": 1, "nodes_expanded": nodes, "time_ms": dt}, "rules_fired": [], "why_not": ["no_chain_found"]}, "capabilities_satisfied": ["REPORT.logic"]}
            return {"error": "unsupported_query"}
        elif mode == "planning":
            goal = inputs.get("goal", {})
            pred = (goal or {}).get("predicate")
            # Contract-derived step synthesis (deterministic, not full planning):
            # goal describes a sequence of desired capabilities; we derive obligation steps by matching tool contracts.
            #
            # Expected shape:
            # goal = {
            #   "predicate": "capability.sequence",
            #   "args": {
            #     "sequence": [
            #        {"type":"REPORT","kind":"query.math"},
            #        {"type":"REPORT","kind":"query.count"}
            #     ],
            #     "inputs": {
            #        "query.math": {"expr":"2+2"},
            #        "query.count": {"letter":"r","word":"strawberry"}
            #     }
            #   }
            # }
            if pred == "capability.sequence":
                args = (goal or {}).get("args", {}) or {}
                seq = args.get("sequence", [])
                inputs_map = args.get("inputs", {}) or {}
                contracts = inputs.get("tool_contracts", []) or []

                if not isinstance(seq, list) or not all(isinstance(s, dict) for s in seq):
                    return {"error": "invalid_capability_sequence"}
                if not isinstance(inputs_map, dict):
                    return {"error": "invalid_capability_inputs"}
                if not isinstance(contracts, list):
                    return {"error": "invalid_tool_contracts"}

                # Index tools by (capability_kind, obligation_type) they satisfy, based on satisfies patterns.
                def _score(c: dict) -> tuple:
                    rel = {"high": 3, "medium": 2, "low": 1}.get(str(c.get("reliability") or "medium"), 2)
                    cost = {"tiny": 4, "low": 3, "medium": 2, "high": 1}.get(str(c.get("cost") or "medium"), 2)
                    lat = int(c.get("latency_ms") or 100)
                    name = str(c.get("name") or "")
                    return (-rel, -cost, lat, name)

                def _matches_satisfies(tool: dict, want_type: str, want_kind: str) -> bool:
                    sat = tool.get("satisfies") or []
                    if not isinstance(sat, list):
                        return False
                    target = f"{want_type}({want_kind})"
                    return target in sat or want_type in sat

                def _consumes_kind(tool: dict, want_kind: str) -> bool:
                    consumes = tool.get("consumes") or []
                    if not isinstance(consumes, list):
                        return False
                    return any(isinstance(c, dict) and c.get("kind") == want_kind for c in consumes)

                def _get_consumes_schema(tool: dict, want_kind: str) -> dict | None:
                    consumes = tool.get("consumes") or []
                    if not isinstance(consumes, list):
                        return None
                    for c in consumes:
                        if isinstance(c, dict) and c.get("kind") == want_kind:
                            s = c.get("schema")
                            return s if isinstance(s, dict) else None
                    return None

                steps = []
                for item in seq:
                    want_type = str(item.get("type") or "")
                    want_kind = str(item.get("kind") or "")
                    if want_type not in ("REPORT", "ACHIEVE", "MAINTAIN", "AVOID", "JUSTIFY", "SCHEDULE"):
                        return {"error": "unsupported_sequence_type"}
                    if not want_kind:
                        return {"error": "missing_sequence_kind"}

                    # Choose best tool deterministically.
                    candidates = []
                    for t in contracts:
                        if not isinstance(t, dict):
                            continue
                        if _consumes_kind(t, want_kind) and _matches_satisfies(t, want_type, want_kind):
                            candidates.append(t)
                    if not candidates:
                        return {
                            "error": "missing_capability",
                            "missing": {"type": want_type, "kind": want_kind},
                        }
                    candidates.sort(key=_score)

                    # Build step obligation (tool name is NOT embedded; conductor will route via contracts again).
                    payload_inputs = inputs_map.get(want_kind, {})
                    if not isinstance(payload_inputs, dict):
                        return {"error": "invalid_step_inputs"}

                    # Harden contract matching: validate payload_inputs against consumes schema BEFORE emitting.
                    # This prevents the "card house collapses" feeling where the plan is emitted but cannot run.
                    schema_mismatches = []
                    valid_candidates = []
                    for t in candidates:
                        schema = _get_consumes_schema(t, want_kind)
                        if not schema:
                            # If no schema, treat as mismatch (contracts should be authoritative).
                            schema_mismatches.append({"tool": t.get("name"), "reason": "missing_consumes_schema"})
                            continue
                        try:
                            jsonschema.validate(payload_inputs, schema)
                            valid_candidates.append(t)
                        except Exception as e:
                            schema_mismatches.append({"tool": t.get("name"), "reason": "schema_mismatch", "error": str(e)})

                    if not valid_candidates:
                        # If the problem is simply missing required fields, emit CLARIFY instead of toolsmithing.
                        # Pick the first required field from the schema of the best candidate, if available.
                        try:
                            best = candidates[0]
                            schema = _get_consumes_schema(best, want_kind) or {}
                            req = schema.get("required") if isinstance(schema, dict) else None
                            if isinstance(req, list):
                                for field in req:
                                    if isinstance(field, str) and field not in payload_inputs:
                                        return {
                                            "kind": "plan",
                                            "clarify": field,
                                            "why_not": ["input_missing"],
                                            "missing_inputs": {"kind": want_kind, "required": req, "provided": list(payload_inputs.keys())},
                                            "found_tools": [t.get("name") for t in candidates if isinstance(t, dict)],
                                        }
                        except Exception:
                            pass
                        return {
                            "error": "input_schema_mismatch",
                            "missing_capability": {
                                "type": "missing_capability",
                                "reason": "tools_exist_but_inputs_do_not_match_schema",
                                "requested": {"type": want_type, "kind": want_kind, "inputs": payload_inputs},
                                "candidates": [t.get("name") for t in candidates if isinstance(t, dict)],
                                "mismatches": schema_mismatches,
                            },
                        }

                    # Deterministic tie-break after schema filtering.
                    valid_candidates.sort(key=_score)
                    chosen = valid_candidates[0]
                    step_ob = {"type": want_type, "payload": {"kind": want_kind, **payload_inputs}}
                    steps.append({"obligation": step_ob, "derived_from": {"tool": chosen.get("name")}})

                return {
                    "kind": "plan",
                    "trajectory": {"steps": steps, "metrics": {"depth_used": 1, "beam_used": 1, "time_ms": 0}},
                    "feasible": True,
                    "capabilities_satisfied": ["ACHIEVE.plan"],
                }
            if pred == "event.scheduled":
                steps = ["ResolvePerson", "CheckCalendar", "ProposeSlots", "CreateEvent"]
                # do not write assertions; plan only
                result = {
                    "kind": "plan",
                    "trajectory": {"steps": steps, "metrics": {"depth_used": 1, "beam_used": 1, "time_ms": 0}},
                    "feasible": True,
                    "capabilities_satisfied": ["ACHIEVE.plan"]
                }
                # simple ambiguity check (stub): if person ambiguous, request clarify
                args = (goal or {}).get("args", {})
                person = args.get("person")
                if person in ("Dana", "Alex"):
                    result["clarify"] = "person"
                return result
            return {"error": "unsupported_goal"}
        return {"error": "mode_required"}


# Example usage
if __name__ == "__main__":
    # Test tool registry
    registry = ToolRegistry()
    print(f"Loaded {len(registry.list_tools())} tools")
    
    # Test tool selection
    math_tools = registry.find_tools_for_obligation("REPORT")
    print(f"Tools for REPORT: {[t.name for t in math_tools]}")
    
    # Test tool execution
    executor = ToolExecutor(registry)
    
    # Test EvalMath
    result = executor.execute_tool("EvalMath", {"expr": "2+2"})
    print(f"EvalMath result: {result}")
    
    # Test CountLetters
    result = executor.execute_tool("TextOps.CountLetters", {"letter": "r", "word": "strawberry"})
    print(f"CountLetters result: {result}")
    
    # Test PeopleSQL
    result = executor.execute_tool("PeopleSQL", {"filters": [{"city": "Seattle"}]})
    print(f"PeopleSQL result: {result}")
