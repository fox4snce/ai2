"""
Comprehensive tests for the MVP system.

This module tests all components of the Obligations → Operations architecture.
"""

import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch

# Import the components to test
import sys
sys.path.append('src')

from core.database import IRDatabase, Entity, Relation, Assertion, Event, Source, Obligation, ToolRun
from core.obligations import ObligationParser, ObligationValidator, ObligationBuilder
from core.tools import ToolRegistry, ToolExecutor, ToolContract
from conductor.conductor import Conductor, ExecutionResult, VerificationResult
from translators.translators import TranslatorManager, MockLLM, TranslatorIn, TranslatorOut
from main import MVPRequestHandler, MVPAPI


# --- small reporting helper for explicit expected vs actual in console ---
def report(label: str, expected, actual) -> None:
    print(f"[CHECK] {label}")
    print(f"  expected: {expected}")
    print(f"  actual:   {actual}")


class TestDatabase:
    """Test the IR database layer."""
    
    def setup_method(self):
        """Set up test database."""
        self.db = IRDatabase(":memory:")
    
    def teardown_method(self):
        """Clean up test database."""
        self.db.close()
    
    def test_create_entity(self):
        """Test entity creation."""
        entity = Entity("E1", "person", {"name": "Alice"})
        entity_id = self.db.create_entity(entity)
        assert entity_id == "E1"
    
    def test_create_relation(self):
        """Test relation creation."""
        # Create entities first
        self.db.create_entity(Entity("E1", "person"))
        self.db.create_entity(Entity("E2", "person"))
        
        relation = Relation("R1", "E1", "friend", "E2")
        relation_id = self.db.create_relation(relation)
        assert relation_id == "R1"
    
    def test_create_assertion(self):
        """Test assertion creation."""
        assertion = Assertion("A1", "E1", "evaluatesTo", "4", 1.0)
        assertion_id = self.db.create_assertion(assertion)
        assert assertion_id == "A1"
    
    def test_get_assertions_by_subject(self):
        """Test getting assertions by subject."""
        # Create assertion
        assertion = Assertion("A1", "E1", "evaluatesTo", "4", 1.0)
        self.db.create_assertion(assertion)
        
        # Retrieve assertions
        assertions = self.db.get_assertions_by_subject("E1")
        assert len(assertions) == 1
        assert assertions[0].predicate == "evaluatesTo"
        assert assertions[0].object == "4"


class TestObligations:
    """Test obligation parsing and validation."""
    
    def test_obligation_validation(self):
        """Test obligation schema validation."""
        validator = ObligationValidator()
        
        # Valid obligations
        valid_obligations = {
            "obligations": [
                ObligationBuilder.report_math("2+2"),
                ObligationBuilder.verify_answer()
            ]
        }
        assert validator.validate(valid_obligations) == True
        
        # Invalid obligations
        invalid_obligations = {
            "obligations": [
                {"type": "INVALID", "payload": {}}
            ]
        }
        assert validator.validate(invalid_obligations) == False
    
    def test_obligation_parsing(self):
        """Test obligation parsing."""
        parser = ObligationParser()
        
        obligations_data = {
            "obligations": [
                ObligationBuilder.report_math("2+2"),
                ObligationBuilder.verify_answer()
            ]
        }
        
        parsed = parser.parse_obligations(obligations_data)
        assert len(parsed) == 2
        assert parsed[0].type == "REPORT"
        assert parsed[0].payload.kind == "math"
        assert parsed[0].payload.expr == "2+2"
        assert parsed[1].type == "VERIFY"
    
    def test_obligation_builder(self):
        """Test obligation builder utilities."""
        # Test math obligation
        math_obligation = ObligationBuilder.report_math("2+2")
        assert math_obligation["type"] == "REPORT"
        assert math_obligation["payload"]["kind"] == "math"
        assert math_obligation["payload"]["expr"] == "2+2"
        
        # Test people query obligation
        people_obligation = ObligationBuilder.report_people_query([
            {"is_friend": "user"},
            {"city": "Seattle"}
        ])
        assert people_obligation["type"] == "REPORT"
        assert people_obligation["payload"]["kind"] == "query.people"
        assert len(people_obligation["payload"]["filters"]) == 2


class TestTools:
    """Test tool registry and execution."""
    
    def setup_method(self):
        """Set up test tools."""
        # Create temporary contracts directory
        self.temp_dir = tempfile.mkdtemp()
        os.makedirs(f"{self.temp_dir}/tools", exist_ok=True)
        
        # Create test tool contract
        test_tool_yaml = """
name: TestEvalMath
description: Test math evaluator
version: 1.0.0
consumes:
  - kind: query.math
    schema:
      type: object
      properties:
        expr:
          type: string
      required: [expr]
produces:
  - assertion:
      subject: Expression
      predicate: evaluatesTo
      object: number
satisfies:
  - REPORT(query.math)
preconditions:
  - expr_parses
postconditions:
  - result_is_number
cost: tiny
reliability: high
latency_ms: 5
implementation:
  type: python
  entry_point: test_evalmath.evaluate
"""
        
        with open(f"{self.temp_dir}/tools/test_evalmath.yaml", "w") as f:
            f.write(test_tool_yaml)
    
    def teardown_method(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_tool_registry(self):
        """Test tool registry loading."""
        registry = ToolRegistry(self.temp_dir, fail_on_schema_error=True)
        
        # Should load the test tool
        assert "TestEvalMath" in registry.list_tools()
        
        # Get tool contract
        tool = registry.get_tool("TestEvalMath")
        assert tool.name == "TestEvalMath"
        assert tool.reliability == "high"
        assert tool.cost == "tiny"
    
    def test_tool_selection(self):
        """Test tool selection policy."""
        registry = ToolRegistry(self.temp_dir, fail_on_schema_error=True)
        
        # Find tools for REPORT obligation
        tools = registry.find_tools_for_obligation("REPORT")
        assert len(tools) >= 1
        
        # Test input validation
        payload = {"kind": "math", "expr": "2+2"}
        can_handle, reason = registry.validate_tool_inputs(tools[0], payload)
        assert can_handle == True
    
    def test_tool_execution(self):
        """Test tool execution."""
        registry = ToolRegistry(self.temp_dir)
        executor = ToolExecutor(registry)
        
        # Test EvalMath execution
        result = executor.execute_tool("EvalMath", {"expr": "2+2"})
        report("EvalMath 2+2 result", expected=4, actual=result.get("result"))
        assert "result" in result
        assert result["result"] == 4
        
        # Test error handling
        result = executor.execute_tool("EvalMath", {"expr": "2+"})
        report("EvalMath invalid expr error present", expected="error key", actual="error" if "error" in result else "missing")
        assert "error" in result


class TestConductor:
    """Test conductor orchestration."""
    
    def setup_method(self):
        """Set up test conductor."""
        self.db = IRDatabase(":memory:")
        self.registry = ToolRegistry()
        self.conductor = Conductor(self.db, self.registry)
    
    def teardown_method(self):
        """Clean up test conductor."""
        self.db.close()
    
    def test_execution_result(self):
        """Test execution result creation."""
        result = ExecutionResult(
            obligation_id="OB1",
            success=True,
            tool_name="EvalMath",
            duration_ms=5
        )
        assert result.success == True
        assert result.tool_name == "EvalMath"
    
    def test_verification_result(self):
        """Test verification result creation."""
        result = VerificationResult(
            passed=True,
            method="recompute",
            details="All good",
            duration_ms=2
        )
        assert result.passed == True
        assert result.method == "recompute"


class TestTranslators:
    """Test translator interfaces."""
    
    def test_mock_llm(self):
        """Test mock LLM responses."""
        mock_llm = MockLLM()
        
        # Test math question
        response = mock_llm.generate("What's 2+2?")
        data = json.loads(response)
        assert "obligations" in data
        assert len(data["obligations"]) >= 1
    
    def test_translator_in(self):
        """Test input translator."""
        mock_llm = MockLLM()
        translator_in = TranslatorIn(mock_llm)
        
        result = translator_in.translate("What's 2+2?")
        assert "obligations" in result
        assert len(result["obligations"]) >= 1
    
    def test_translator_out(self):
        """Test output translator."""
        mock_llm = MockLLM()
        translator_out = TranslatorOut(mock_llm)
        
        assertions = [
            {"subject_id": "Expr_1", "predicate": "evaluatesTo", "object": "4"}
        ]
        
        answer = translator_out.translate(assertions)
        report("TranslatorOut basic answer non-empty", expected="> 0 chars", actual=len(answer))
        assert isinstance(answer, str)
        assert len(answer) > 0


class TestMVPIntegration:
    """Test full MVP system integration."""
    
    def setup_method(self):
        """Set up test API."""
        self.api = MVPAPI(":memory:")
    
    def teardown_method(self):
        """Clean up test API."""
        self.api.close()
    
    def test_math_question(self):
        """Test math question processing."""
        answer = self.api.ask("What's 2+2?")
        report("API answer for 2+2", expected="4 (final may be gated by VERIFY)", actual=answer)
        assert isinstance(answer, str)
        assert len(answer) > 0
    
    def test_counting_question(self):
        """Test counting question processing."""
        answer = self.api.ask("How many r's in 'strawberry'?")
        report("API answer for count r in 'strawberry'", expected="3 (final may be gated by VERIFY)", actual=answer)
        assert isinstance(answer, str)
        assert len(answer) > 0
    
    def test_clarify_then_resolve_name(self):
        """CLARIFY path then resolve name and answer."""
        # No name stored yet → expect clarify
        # Call deterministic obligations API
        from main import MVPAPI
        api = MVPAPI()
        trace1 = api.execute_obligations({
            "obligations": [
                {"type": "REPORT", "payload": {"kind": "status.name"}}
            ]
        })
        assert trace1.get('final_answer','') == ""
        assert 'clarify' in trace1 and 'name' in trace1['clarify']

        # Provide name via ACHIEVE
        _ = api.execute_obligations({
            "obligations": [
                {"type": "ACHIEVE", "payload": {"state": "status.name", "value": "Jeff"}}
            ]
        })
        
        # Ask again → should return stored name
        trace2 = api.execute_obligations({
            "obligations": [
                {"type": "REPORT", "payload": {"kind": "status.name"}}
            ]
        })
        assert trace2.get('final_answer','') == 'Jeff'
    
    def test_people_query(self):
        """Test people query processing via deterministic obligations API."""
        trace = self.api.execute_obligations({
            "obligations": [
                {
                    "type": "REPORT",
                    "payload": {
                        "kind": "query.people",
                        "filters": [
                            {"is_friend": "user"},
                            {"city": "Seattle"}
                        ]
                    }
                }
            ]
        })
        # Deterministic renderer returns JSON array of names from mock data
        import json
        names = json.loads(trace.get('final_answer','[]'))
        assert isinstance(names, list)
        assert set(names) >= {"Alice Smith", "Bob Johnson"}
    
    def test_full_trace(self):
        """Test full trace generation."""
        trace = self.api.execute_obligations({
            "obligations": [
                {"type": "REPORT", "payload": {"kind": "math", "expr": "2+2"}}
            ]
        })
        
        # Check trace structure
        assert "trace_id" in trace
        assert "user_input" in trace
        assert "obligations" in trace
        assert "tool_runs" in trace
        assert "assertions" in trace
        assert "verification" in trace
        assert "final_answer" in trace
        assert "metrics" in trace
        
        # Check metrics
        metrics = trace["metrics"]
        assert "total_latency_ms" in metrics
        assert "success_rate" in metrics
    
    def test_system_status(self):
        """Test system status."""
        status = self.api.status()
        assert "status" in status
        assert "tools_registered" in status
        assert "tool_names" in status
        assert status["status"] == "running"


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def setup_method(self):
        """Set up test API."""
        self.api = MVPAPI(":memory:")
    
    def teardown_method(self):
        """Clean up test API."""
        self.api.close()
    
    def test_invalid_input(self):
        """Test handling of invalid input."""
        answer = self.api.ask("")
        assert isinstance(answer, str)
        assert len(answer) > 0
    
    def test_unknown_question(self):
        """Test handling of unknown question types."""
        answer = self.api.ask("What is the meaning of life?")
        assert isinstance(answer, str)
        assert len(answer) > 0
    
    def test_error_trace(self):
        """Test error trace generation."""
        trace = self.api.execute_obligations({"obligations": []})
        assert "trace_id" in trace
        # Empty obligations are invalid; engine returns error response
        assert trace.get("final_answer", "").startswith("Error:")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
