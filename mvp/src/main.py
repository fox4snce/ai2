"""
Main request handler and API.

This module provides the main entry point for the MVP system,
integrating all components into a cohesive request processing pipeline.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .core.database import IRDatabase
from .core.obligations import ObligationParser
from .core.tools import ToolRegistry, ToolExecutor
from .core.skills import SkillRegistry
from .conductor.conductor import Conductor
from .translators.translators import TranslatorManager, MockLLM
from .translators.real_llm import RealTranslatorManager, OpenAILLM
from .translators.skill_translator import SkillTranslator

logger = logging.getLogger(__name__)


class MVPRequestHandler:
    """Main request handler for the MVP system."""
    
    def __init__(self, db_path: str = None, use_real_llm: bool = False, api_key: str = None, use_skill_translator: bool = False):
        """Initialize the request handler.
        
        If db_path is None, defaults to persistent .ir/ir.db.
        Use ":memory:" explicitly for ephemeral testing.
        use_skill_translator: If True, use skill-based translator instead of direct obligation translator.
        """
        # Initialize core components
        self.db = IRDatabase(db_path)
        self.registry = ToolRegistry()
        self.skill_registry = SkillRegistry()
        self.conductor = Conductor(self.db, self.registry, verify_enabled=False, skill_registry=self.skill_registry)
        
        # Initialize translators
        self.use_skill_translator = use_skill_translator
        if use_skill_translator and use_real_llm and api_key:
            llm = OpenAILLM(api_key)
            self.translator_manager = SkillTranslator(llm, self.skill_registry)
            logger.info("Using skill-based translator with real OpenAI LLM")
        elif use_real_llm and api_key:
            self.translator_manager = RealTranslatorManager(api_key)
            logger.info("Using real OpenAI LLM")
        else:
            self.mock_llm = MockLLM()
            self.translator_manager = TranslatorManager(self.mock_llm)
            logger.info("Using mock LLM")
        
        # Load sample data
        self._load_sample_data()
        
        logger.info("MVP Request Handler initialized")
    
    def _load_sample_data(self):
        """Load sample data into the database."""
        try:
            # Create sample entities
            from .core.database import Entity, Relation, Source
            
            # Sample entities
            entities = [
                Entity("E1", "person", {"aliases": ["User"]}),
                Entity("E2", "expression", {"text": "2+2"}),
                Entity("E3", "person", {"aliases": ["Alice", "Alice Smith"]}),
                Entity("E4", "person", {"aliases": ["Bob", "Bob Johnson"]}),
                Entity("E5", "location", {"aliases": ["Seattle", "Seattle WA"]})
            ]
            
            for entity in entities:
                self.db.create_entity(entity)
            
            # Sample relations
            relations = [
                Relation("R1", "E3", "friend", "E1", {"since": "2023-01-01"}),
                Relation("R2", "E4", "friend", "E1", {"since": "2023-02-15"}),
                Relation("R3", "E3", "lives_in", "E5", {"verified": True}),
                Relation("R4", "E4", "lives_in", "E5", {"verified": True})
            ]
            
            for relation in relations:
                self.db.create_relation(relation)
            
            # Sample sources
            sources = [
                Source("S1", "tool", "EvalMath", {"version": "1.0", "reliability": "high"}),
                Source("S2", "database", "contacts.db", {"last_updated": "2024-01-15"}),
                Source("S3", "user_input", "direct", {"timestamp": "2024-01-20T10:30:00Z"})
            ]
            
            for source in sources:
                self.db.create_source(source)
            
            logger.info("Sample data loaded successfully")
            
        except Exception as e:
            logger.warning(f"Failed to load sample data: {e}")
    
    def process_request(self, user_input: str) -> Dict[str, Any]:
        """
        Process a complete user request.
        
        Args:
            user_input: Natural language input from user
            
        Returns:
            Dict: Complete trace with final answer
        """
        try:
            logger.info(f"Processing request: {user_input}")
            
            # Step 1: Translate natural language to obligations
            if self.use_skill_translator:
                # Skill translator returns obligations directly
                obligations_data = self.translator_manager.translate(user_input)
            else:
                # Regular translator
                obligations_data = self.translator_manager.process_request(user_input)
            
            if "error" in obligations_data:
                return self._create_error_response(user_input, obligations_data["error"])
            
            # Step 2: Process obligations through conductor
            trace = self.conductor.process_request(user_input, obligations_data)
            
            # Step 3: Skip translator-out for deterministic-only test mode
            
            logger.info(f"Request processed successfully: {trace['trace_id']}")
            return trace
            
        except Exception as e:
            logger.error(f"Request processing failed: {e}")
            return self._create_error_response(user_input, str(e))
    
    def _create_error_response(self, user_input: str, error: str) -> Dict[str, Any]:
        """Create error response."""
        return {
            "trace_id": f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "obligations": [],
            "tool_runs": [],
            "assertions": [],
            "verification": {"passed": False, "error": error},
            "final_answer": f"I encountered an error: {error}",
            "metrics": {
                "total_latency_ms": 0,
                "obligation_count": 0,
                "tool_run_count": 0,
                "assertion_count": 0,
                "verification_passed": False,
                "escalation_count": 0,
                "clarify_count": 0,
                "success_rate": 0
            }
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status and metrics."""
        return {
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "tools_registered": len(self.registry.list_tools()),
            "tool_names": self.registry.list_tools(),
            "database_path": self.db.db_path,
            "sample_data_loaded": True
        }
    
    def close(self):
        """Close database connection."""
        self.db.close()


class MVPAPI:
    """Simple API wrapper for the MVP system."""
    
    def __init__(self, db_path: str = None, use_real_llm: bool = False, api_key: str = None):
        """Initialize API.
        
        If db_path is None, defaults to persistent .ir/ir.db.
        Use ":memory:" explicitly for ephemeral testing.
        """
        self.handler = MVPRequestHandler(db_path, use_real_llm, api_key)
    
    def ask(self, question: str) -> str:
        """
        Ask a question and get an answer.
        
        Args:
            question: Natural language question
            
        Returns:
            str: Natural language answer
        """
        trace = self.handler.process_request(question)
        return trace.get("final_answer", "I couldn't generate an answer.")
    
    def ask_with_trace(self, question: str) -> Dict[str, Any]:
        """
        Ask a question and get full trace.
        
        Args:
            question: Natural language question
            
        Returns:
            Dict: Complete trace with answer and execution details
        """
        return self.handler.process_request(question)

    # Deterministic obligations API (bypasses translators entirely)
    def execute_obligations(self, obligations: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute obligations directly (deterministic-only path).
        """
        # Feed directly into conductor
        return self.handler.conductor.process_request("(api)", obligations)
    
    def status(self) -> Dict[str, Any]:
        """Get system status."""
        return self.handler.get_system_status()
    
    def close(self):
        """Close the system."""
        self.handler.close()


# Example usage and testing
if __name__ == "__main__":
    # Initialize the MVP system
    api = MVPAPI()
    
    # Test questions
    test_questions = [
        "What's 2+2?",
        "How many r's in 'strawberry'?",
        "List my friends in Seattle",
        "What's your name?"
    ]
    
    print("=== MVP System Test ===\n")
    
    for question in test_questions:
        print(f"Q: {question}")
        
        # Get simple answer
        answer = api.ask(question)
        print(f"A: {answer}")
        
        # Get full trace
        trace = api.ask_with_trace(question)
        print(f"Trace ID: {trace['trace_id']}")
        print(f"Obligations: {len(trace['obligations'])}")
        print(f"Tool runs: {len(trace['tool_runs'])}")
        print(f"Assertions: {len(trace['assertions'])}")
        print(f"Verification passed: {trace['verification']['passed']}")
        print(f"Latency: {trace['metrics']['total_latency_ms']}ms")
        print("-" * 50)
    
    # Show system status
    print("\n=== System Status ===")
    status = api.status()
    print(json.dumps(status, indent=2))
    
    # Close system
    api.close()
