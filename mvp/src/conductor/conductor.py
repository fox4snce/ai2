"""
Conductor implementation.

The Conductor orchestrates obligation satisfaction through tool selection
and execution. It implements the core loops: request loop, plan loop, and verify loop.
"""

import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging

from ..core.database import IRDatabase, Entity, Event, Assertion, Source, Obligation, ToolRun
from ..core.obligations import ParsedObligation, ObligationBuilder
from ..core.tools import ToolRegistry, ToolExecutor, ToolContract

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of obligation execution."""
    obligation_id: str
    success: bool
    tool_name: Optional[str] = None
    assertions: List[Assertion] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    clarify_slot: Optional[str] = None
    inputs: Optional[Dict] = None
    outputs: Optional[Dict] = None


@dataclass
class VerificationResult:
    """Result of verification."""
    passed: bool
    method: str
    details: str
    duration_ms: int
    error: Optional[str] = None


class Conductor:
    """Main conductor for orchestrating obligation satisfaction."""
    
    def __init__(self, db: IRDatabase, registry: ToolRegistry, verify_enabled: bool = False):
        """Initialize conductor with database and tool registry.

        verify_enabled: when False, verification is bypassed (always passes).
        """
        self.db = db
        self.registry = registry
        self.executor = ToolExecutor(registry)
        self.verify_enabled = verify_enabled
    
    def process_request(self, user_input: str, obligations_data: Dict) -> Dict:
        """
        Process a complete request from user input to final answer.
        
        This implements the top-level request loop:
        1. Log user utterance event
        2. Parse obligations
        3. Execute plan loop for each obligation
        4. Verify results
        5. Return final answer
        """
        trace_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"Processing request {trace_id}: {user_input}")
        
        # 1. Log user utterance event
        user_event = Event(
            id=f"EV_{trace_id}",
            kind="user_utterance",
            payload_jsonb={"text": user_input}
        )
        self.db.create_event(user_event)
        
        # 2. Parse obligations
        try:
            from ..core.obligations import ObligationParser
            parser = ObligationParser()
            parsed_obligations = parser.parse_obligations(obligations_data)
        except Exception as e:
            logger.error(f"Failed to parse obligations: {e}")
            return self._create_error_response(trace_id, f"Obligation parsing failed: {e}")
        
        # 3. Create obligations in database
        obligation_ids = []
        for parsed_obligation in parsed_obligations:
            obligation = Obligation(
                id=f"OB_{len(obligation_ids)+1}_{trace_id}",
                kind=parsed_obligation.type,
                details_jsonb=parsed_obligation.raw_payload,
                event_id=user_event.id
            )
            obligation_id = self.db.create_obligation(obligation)
            obligation_ids.append(obligation_id)
        
        # 4. Execute plan loop for each obligation
        execution_results = []
        for obligation_id, parsed_obligation in zip(obligation_ids, parsed_obligations):
            result = self._execute_plan_loop(obligation_id, parsed_obligation)
            execution_results.append(result)
        
        # 5. Verify results (selective or disabled)
        verification_result = self._execute_verify_loop(execution_results)
        
        # 6. Generate final answer
        final_answer = self._generate_final_answer(execution_results, verification_result)
        
        # Compute high-level status
        if any(er.clarify_slot for er in execution_results):
            status = "clarify"
        elif all(er.success for er in execution_results if er is not None):
            status = "resolved"
        else:
            status = "failed"

        # 7. Calculate metrics
        total_duration = int((time.time() - start_time) * 1000)
        metrics = self._calculate_metrics(execution_results, verification_result, total_duration)
        
        # 8. Create trace
        trace = {
            "trace_id": trace_id,
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "obligations": [self._serialize_obligation(oid) for oid in obligation_ids],
            "tool_runs": [self._serialize_execution_result(er) for er in execution_results],
            "assertions": [self._serialize_assertion(a) for er in execution_results for a in (er.assertions or [])],
            "verification": self._serialize_verification_result(verification_result),
            "status": status,
            "final_answer": final_answer,
            "metrics": metrics,
            "capabilities_satisfied": self._collect_capabilities(execution_results)
        }
        # If any clarify requested, include it in trace for gating
        if any(er.clarify_slot for er in execution_results):
            trace["clarify"] = [er.clarify_slot for er in execution_results if er.clarify_slot]
        
        logger.info(f"Request {trace_id} completed in {total_duration}ms")
        return trace
    
    def _execute_plan_loop(self, obligation_id: str, parsed_obligation: ParsedObligation) -> ExecutionResult:
        """
        Execute the plan loop for a single obligation.
        
        This implements:
        1. Find candidate tools
        2. Check input satisfaction
        3. Select best tool
        4. Execute tool
        5. Check postconditions
        6. Handle failures
        """
        start_time = time.time()
        
        try:
            # Special-case: ACHIEVE(status.name) with value → save directly
            if parsed_obligation.type == "ACHIEVE":
                state = parsed_obligation.raw_payload.get("state")
                value = parsed_obligation.raw_payload.get("value")
                if state == "status.name" and value:
                    assertion = Assertion(
                        id=f"A_{obligation_id}_name",
                        subject_id="E1",
                        predicate="name",
                        object=str(value),
                        confidence=1.0,
                        source_id="S_user_input"
                    )
                    self.db.create_assertion(assertion)
                    self.db.update_obligation_status(obligation_id, "resolved")
                    return ExecutionResult(
                        obligation_id=obligation_id,
                        success=True,
                        tool_name="MemorySave",
                        assertions=[assertion],
                        duration_ms=int((time.time() - start_time) * 1000),
                        inputs={"state": state, "value": value},
                        outputs={"saved": True}
                    )

            # Special-case: REPORT.status.name → read memory or clarify
            if parsed_obligation.type == "REPORT" and parsed_obligation.raw_payload.get("kind") in ("status.name", "status"):
                field = parsed_obligation.raw_payload.get("field")
                if parsed_obligation.raw_payload.get("kind") == "status.name" or field == "name":
                    # try read
                    name_assertions = [a for a in self.db.get_assertions_by_subject("E1") if a.predicate == "name"]
                    if name_assertions:
                        # resolved
                        return ExecutionResult(
                            obligation_id=obligation_id,
                            success=True,
                            tool_name="MemoryRead",
                            assertions=[name_assertions[-1]],
                            duration_ms=int((time.time() - start_time) * 1000),
                            inputs={"field": "name"},
                            outputs={"name": name_assertions[-1].object}
                        )
                    # clarify
                    return ExecutionResult(
                        obligation_id=obligation_id,
                        success=False,
                        clarify_slot="name",
                        error="CLARIFY(name) required"
                    )
            # 1. Find candidate tools
            candidate_tools = self.registry.find_tools_for_obligation(parsed_obligation.type)
            
            if not candidate_tools:
                # If this looks like a status.name report, emit CLARIFY(name)
                if parsed_obligation.type == "REPORT" and parsed_obligation.raw_payload.get("kind") == "status" and parsed_obligation.raw_payload.get("field") == "name":
                    # return a clarify execution result (no tool)
                    return ExecutionResult(
                        obligation_id=obligation_id,
                        success=False,
                        clarify_slot="name",
                        error="CLARIFY(name) required"
                    )
                error_msg = f"No tools available for obligation type: {parsed_obligation.type}"
                logger.warning(error_msg)
                return ExecutionResult(
                    obligation_id=obligation_id,
                    success=False,
                    error=error_msg
                )
            
            # 2. Select best tool
            selected_tool = self.registry.select_best_tool(
                parsed_obligation.type,
                parsed_obligation.raw_payload,
                selection_seed=obligation_id
            )
            
            if not selected_tool:
                error_msg = f"No suitable tool found for obligation: {parsed_obligation.type}"
                logger.warning(error_msg)
                return ExecutionResult(
                    obligation_id=obligation_id,
                    success=False,
                    error=error_msg
                )
            
            # 3a. Pre-run supports: execute any tools that can establish selected tool preconditions
            try:
                required_preconds = list(selected_tool.preconditions or [])
                support_tools = self.registry.find_support_tools(required_preconds)
                for st in support_tools:
                    try:
                        _ = self.executor.execute_tool(st.name, {"preconditions": required_preconds})
                    except Exception:
                        logger.warning(f"Support tool {st.name} failed; continuing without it")
            except Exception:
                logger.debug("No support tools executed")

            # 3b. Execute tool
            tool_inputs = self._prepare_tool_inputs(selected_tool, parsed_obligation)
            tool_outputs = self.executor.execute_tool(selected_tool.name, tool_inputs)
            
            # 4. Check for tool execution errors
            if "error" in tool_outputs:
                error_msg = f"Tool {selected_tool.name} failed: {tool_outputs['error']}"
                logger.error(error_msg)
                return ExecutionResult(
                    obligation_id=obligation_id,
                    success=False,
                    tool_name=selected_tool.name,
                    error=error_msg,
                    inputs=tool_inputs,
                    outputs=tool_outputs
                )
            
            # 5. Create assertions from tool outputs
            assertions = self._create_assertions_from_outputs(
                selected_tool, tool_outputs, obligation_id
            )
            
            # 6. Store assertions in database
            for assertion in assertions:
                self.db.create_assertion(assertion)
            
            # 7. Update obligation status
            # Guardrails check (precedes clarify/truncated handling)
            if parsed_obligation.type == "ACHIEVE" and parsed_obligation.raw_payload.get("state") == "plan":
                constraints = parsed_obligation.raw_payload.get("guardrails") or []
                if constraints:
                    checker = self.registry.get_tool("GuardrailChecker")
                    if checker:
                        chk_inputs = {"constraints": constraints, "goal": parsed_obligation.raw_payload.get("goal")}
                        chk_out = self.executor.execute_tool("GuardrailChecker", chk_inputs)
                        if (chk_out or {}).get("status") == "failed":
                            self.db.update_obligation_status(obligation_id, "failed")
                            tool_outputs = dict(tool_outputs)
                            tool_outputs.setdefault("why_not", []).append("guardrail_failed")
                            tool_outputs["justification"] = chk_out.get("justification", [])
                            return ExecutionResult(
                                obligation_id=obligation_id,
                                success=False,
                                tool_name=selected_tool.name,
                                assertions=assertions,
                                duration_ms=int((time.time() - start_time) * 1000),
                                inputs=tool_inputs,
                                outputs=tool_outputs
                            )

            # If tool indicated truncated or clarify, do not mark resolved
            if tool_outputs.get("status") == "truncated":
                self.db.update_obligation_status(obligation_id, "failed")
                return ExecutionResult(
                    obligation_id=obligation_id,
                    success=False,
                    tool_name=selected_tool.name,
                    assertions=assertions,
                    duration_ms=int((time.time() - start_time) * 1000),
                    inputs=tool_inputs,
                    outputs=tool_outputs
                )
            elif tool_outputs.get("clarify"):
                # surface clarify without resolving
                return ExecutionResult(
                    obligation_id=obligation_id,
                    success=False,
                    tool_name=selected_tool.name,
                    assertions=assertions,
                    duration_ms=int((time.time() - start_time) * 1000),
                    inputs=tool_inputs,
                    outputs=tool_outputs,
                    clarify_slot=tool_outputs.get("clarify")
                )
            # Guardrail enforcement for ACHIEVE.plan: run GuardrailChecker if constraints present
            if parsed_obligation.type == "ACHIEVE" and parsed_obligation.raw_payload.get("state") == "plan":
                constraints = parsed_obligation.raw_payload.get("guardrails") or []
                if constraints:
                    checker = self.registry.get_tool("GuardrailChecker")
                    if checker:
                        chk_inputs = {"constraints": constraints, "goal": parsed_obligation.raw_payload.get("goal")}
                        chk_out = self.executor.execute_tool("GuardrailChecker", chk_inputs)
                        if (chk_out or {}).get("status") == "failed":
                            self.db.update_obligation_status(obligation_id, "failed")
                            # augment outputs with why_not and justification for trace
                            tool_outputs = dict(tool_outputs)
                            tool_outputs.setdefault("why_not", []).append("guardrail_failed")
                            tool_outputs["justification"] = chk_out.get("justification", [])
                            return ExecutionResult(
                                obligation_id=obligation_id,
                                success=False,
                                tool_name=selected_tool.name,
                                assertions=assertions,
                                duration_ms=int((time.time() - start_time) * 1000),
                                inputs=tool_inputs,
                                outputs=tool_outputs
                            )
            else:
                self.db.update_obligation_status(obligation_id, "resolved")
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Obligation {obligation_id} resolved by {selected_tool.name} in {duration_ms}ms")
            
            return ExecutionResult(
                obligation_id=obligation_id,
                success=True,
                tool_name=selected_tool.name,
                assertions=assertions,
                duration_ms=duration_ms,
                inputs=tool_inputs,
                outputs=tool_outputs
            )
            
        except Exception as e:
            error_msg = f"Plan loop failed for obligation {obligation_id}: {e}"
            logger.error(error_msg)
            return ExecutionResult(
                obligation_id=obligation_id,
                success=False,
                error=error_msg
            )
    
    def _execute_verify_loop(self, execution_results: List[ExecutionResult]) -> VerificationResult:
        """
        Execute verification loop on execution results.
        
        This implements:
        1. Re-evaluate deterministic results
        2. Check consistency
        3. Validate provenance
        """
        start_time = time.time()
        if not getattr(self, 'verify_enabled', False):
            # Short-circuit: verification disabled for deterministic-only test runs
            return VerificationResult(
                passed=True,
                method="disabled",
                details="Verification disabled",
                duration_ms=0
            )
        
        try:
            any_blocking_fail = False
            for result in execution_results:
                if not result.success:
                    continue
                
                if not result.tool_name:
                    continue
                
                tool = self.registry.get_tool(result.tool_name)
                if not tool:
                    continue
                
                verify_mode = getattr(tool, "verify_mode", "blocking")
                
                # Non-blocking or off: log implicitly, do not flip overall pass
                if verify_mode in ("off", "non_blocking"):
                    # Optionally, we could attempt a quick recompute and add to details/logs
                    # but NEVER block final answer for non_blocking tiers.
                    continue
                
                # Blocking verification: attempt recompute and strict compare
                verification_outputs = self.executor.execute_tool(
                    result.tool_name,
                    self._get_tool_inputs_from_result(result)
                )
                if verification_outputs != self._get_tool_outputs_from_result(result):
                    any_blocking_fail = True
                    break
            
            duration_ms = int((time.time() - start_time) * 1000)
            if any_blocking_fail:
                return VerificationResult(
                    passed=False,
                    method="recompute",
                    details="Blocking verify failed",
                    duration_ms=duration_ms,
                    error="Result mismatch"
                )
            else:
                return VerificationResult(
                    passed=True,
                    method="recompute",
                    details="Verify passed or non-blocking",
                    duration_ms=duration_ms
                )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return VerificationResult(
                passed=False,
                method="recompute",
                details=f"Verification failed: {e}",
                duration_ms=duration_ms,
                error=str(e)
            )
    
    def _prepare_tool_inputs(self, tool: ToolContract, parsed_obligation: ParsedObligation) -> Dict:
        """Prepare tool inputs from obligation payload."""
        payload = parsed_obligation.raw_payload
        
        if tool.name == "EvalMath":
            return {"expr": payload.get("expr", "")}
        elif tool.name == "TextOps.CountLetters":
            return {
                "letter": payload.get("letter", ""),
                "word": payload.get("word", "")
            }
        elif tool.name == "PeopleSQL":
            return {"filters": payload.get("filters", [])}
        elif tool.name == "Reasoning.Core":
            # Map REPORT.logic and ACHIEVE.plan to engine modes
            if parsed_obligation.type == "REPORT" and payload.get("kind") == "logic":
                return {
                    "mode": payload.get("mode") or "deduction",
                    "query": payload.get("query"),
                    "facts": payload.get("facts", []),
                    "rules": payload.get("rules", []),
                    "domains": payload.get("domains", []),
                    "simulate_slow": payload.get("simulate_slow"),
                    "budgets": (payload.get("budgets") or (parsed_obligation.raw_payload.get("budgets") if isinstance(parsed_obligation.raw_payload, dict) else None)) or {"max_depth": 3, "beam": 4, "time_ms": 100}
                }
            if parsed_obligation.type == "ACHIEVE" and payload.get("kind") == "plan":
                return {
                    "mode": payload.get("mode") or "planning",
                    "goal": payload.get("goal"),
                    "budgets": payload.get("budgets") or {"max_depth": 3, "beam": 3, "time_ms": 150}
                }
            return payload
        else:
            return payload
    
    def _create_assertions_from_outputs(self, tool: ToolContract, outputs: Dict, obligation_id: str) -> List[Assertion]:
        """Create assertions from tool outputs."""
        assertions = []
        
        if tool.name == "EvalMath":
            result = outputs.get("result")
            if result is not None:
                assertion = Assertion(
                    id=f"A_{obligation_id}_math",
                    subject_id=f"Expr_{obligation_id}",
                    predicate="evaluatesTo",
                    object=str(result),
                    confidence=1.0,
                    source_id=f"S_{tool.name}"
                )
                assertions.append(assertion)
        
        elif tool.name == "TextOps.CountLetters":
            count = outputs.get("count")
            if count is not None:
                assertion = Assertion(
                    id=f"A_{obligation_id}_count",
                    subject_id=f"Text_{obligation_id}",
                    predicate="containsLetterCount",
                    object=str(count),
                    confidence=1.0,
                    source_id=f"S_{tool.name}"
                )
                assertions.append(assertion)
        
        elif tool.name == "PeopleSQL":
            people = outputs.get("people", [])
            for i, person in enumerate(people):
                assertion = Assertion(
                    id=f"A_{obligation_id}_person_{i}",
                    subject_id=person["id"],
                    predicate="matchesQuery",
                    object="true",
                    confidence=1.0,
                    source_id=f"S_{tool.name}"
                )
                assertions.append(assertion)

        elif tool.name == "Reasoning.Core":
            # Persist trajectory if provided and use its id for proof_ref
            proof_tid = None
            if outputs.get("trajectory"):
                from ..core.database import Trajectory
                tid = f"T_{obligation_id}"
                traj = Trajectory(
                    id=tid,
                    run_id=obligation_id,
                    steps_jsonb=outputs["trajectory"].get("steps", []),
                    start_context_jsonb=None,
                    end_context_jsonb=None,
                    metrics_jsonb=outputs["trajectory"].get("metrics", {})
                )
                self.db.create_trajectory(traj)
                proof_tid = tid
            # If deduction true, persist assertions with proof_ref and source
            if outputs.get("kind") == "logic.answer" and outputs.get("value") is True:
                for i, a in enumerate(outputs.get("assertions", [])):
                    subject = a.get("subject", f"Subj_{obligation_id}_{i}")
                    predicate = a.get("predicate", "proves")
                    obj = a.get("object", "true")
                    assertion = Assertion(
                        id=f"A_{obligation_id}_logic_{i}",
                        subject_id=str(subject),
                        predicate=str(predicate),
                        object=str(obj),
                        rule_version=a.get("rule_version"),
                        proof_ref=proof_tid,
                        confidence=1.0,
                        source_id=f"Reasoning.Core@0.1.0"
                    )
                    assertions.append(assertion)
            # False: do not write assertions
        
        # Minimal ACHIEVE(name) handling → save as assertion for status.name
        elif tool.name not in ("EvalMath", "TextOps.CountLetters", "PeopleSQL"):
            # If an ACHIEVE was emitted for status.name with a value, persist it
            if "value" in outputs and "state" in outputs and outputs.get("state") == "status.name":
                assertion = Assertion(
                    id=f"A_{obligation_id}_name",
                    subject_id="E1",  # user entity
                    predicate="name",
                    object=str(outputs.get("value")),
                    confidence=1.0,
                    source_id="S_user_input"
                )
                assertions.append(assertion)
        
        return assertions
    
    def _generate_final_answer(self, execution_results: List[ExecutionResult], verification_result: VerificationResult) -> str:
        """Generate final natural language answer.

        With selective verify: only block when a blocking tool failed verify.
        If verify_result is failed, we still attempt to return non-blocking
        deterministic answers when available.
        """
        # Block if required obligations unresolved / clarify present
        # If there is any clarify requested, do not emit an answer
        # (renderer gating per verify_doc)
        # Note: execution_results carry clarify_slot when needed
        if any(er.clarify_slot for er in execution_results):
            return ""
        
        # Simple answer generation for MVP
        for result in execution_results:
            if not result.success:
                continue
            
            # If we have a stored name, return it for status.name
            for a in (result.assertions or []):
                if a.predicate == "name":
                    return a.object

            if result.tool_name == "EvalMath":
                for assertion in (result.assertions or []):
                    if assertion.predicate == "evaluatesTo":
                        return assertion.object
            
            elif result.tool_name == "TextOps.CountLetters":
                for assertion in (result.assertions or []):
                    if assertion.predicate == "containsLetterCount":
                        return assertion.object
            
            elif result.tool_name == "PeopleSQL":
                # Prefer deterministic rendering from outputs
                try:
                    import json as _json
                    people = (result.outputs or {}).get("people", [])
                    names = [p.get("name") for p in people if p.get("name")]
                    return _json.dumps(names)
                except Exception:
                    pass
            elif result.tool_name == "Reasoning.Core":
                outputs = result.outputs or {}
                if outputs.get("kind") == "logic.answer":
                    return "true" if outputs.get("value") else "false"
                if outputs.get("kind") == "plan":
                    steps = outputs.get("trajectory", {}).get("steps", [])
                    try:
                        import json as _json
                        return _json.dumps(steps)
                    except Exception:
                        return ", ".join(map(str, steps))
        
        # If we get here and verify failed, we fallback to uncertainty message.
        if not verification_result.passed:
            return "I'm not certain about this answer. Let me double-check."
        return "I couldn't generate a proper answer."
    
    def _calculate_metrics(self, execution_results: List[ExecutionResult], verification_result: VerificationResult, total_duration: int) -> Dict:
        """Calculate request metrics."""
        successful_obligations = sum(1 for r in execution_results if r.success)
        total_tool_runs = len(execution_results)
        
        return {
            "total_latency_ms": total_duration,
            "obligation_count": len(execution_results),
            "tool_run_count": total_tool_runs,
            "assertion_count": sum(len(r.assertions or []) for r in execution_results),
            "verification_passed": verification_result.passed,
            "escalation_count": 0,  # TODO: implement escalation tracking
            "clarify_count": 0,     # TODO: implement clarification tracking
            "success_rate": successful_obligations / max(total_tool_runs, 1)
        }
    
    def _create_error_response(self, trace_id: str, error: str) -> Dict:
        """Create error response."""
        return {
            "trace_id": trace_id,
            "timestamp": datetime.now().isoformat(),
            "user_input": "",
            "obligations": [],
            "tool_runs": [],
            "assertions": [],
            "verification": {"passed": False, "error": error},
            "final_answer": f"Error: {error}",
            "metrics": {"total_latency_ms": 0, "success_rate": 0}
        }
    
    def _serialize_obligation(self, obligation_id: str) -> Dict:
        """Serialize obligation for trace."""
        # This would normally fetch from database
        return {"id": obligation_id, "status": "resolved"}
    
    def _serialize_execution_result(self, result: ExecutionResult) -> Dict:
        """Serialize execution result for trace."""
        return {
            "id": result.obligation_id,
            "tool_name": result.tool_name,
            "success": result.success,
            "duration_ms": result.duration_ms,
            "error": result.error,
            "clarify_slot": result.clarify_slot,
            "inputs": result.inputs,
            "outputs": result.outputs
        }
    
    def _serialize_assertion(self, assertion: Assertion) -> Dict:
        """Serialize assertion for trace."""
        return {
            "id": assertion.id,
            "subject_id": assertion.subject_id,
            "predicate": assertion.predicate,
            "object": assertion.object,
            "rule_version": getattr(assertion, "rule_version", None),
            "proof_ref": getattr(assertion, "proof_ref", None),
            "source_id": assertion.source_id,
            "confidence": assertion.confidence
        }
    
    def _serialize_verification_result(self, result: VerificationResult) -> Dict:
        """Serialize verification result for trace."""
        return {
            "passed": result.passed,
            "method": result.method,
            "details": result.details,
            "duration_ms": result.duration_ms,
            "error": result.error
        }
    
    def _get_tool_inputs_from_result(self, result: ExecutionResult) -> Dict:
        """Get tool inputs from execution result (for verification)."""
        # This would normally be stored in the result
        return {}
    
    def _get_tool_outputs_from_result(self, result: ExecutionResult) -> Dict:
        """Get tool outputs from execution result (for verification)."""
        # This would normally be stored in the result
        return {}

    def _collect_capabilities(self, execution_results: List[ExecutionResult]) -> List[str]:
        caps = []
        for er in execution_results:
            if not er or not er.outputs:
                continue
            for c in er.outputs.get("capabilities_satisfied", []) or []:
                if c not in caps:
                    caps.append(c)
        return caps
