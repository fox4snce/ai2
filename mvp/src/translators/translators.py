"""
Translator interfaces for LLM integration.

This module provides interfaces for translating between natural language
and structured obligations, designed to work with any LLM API.
"""

import json
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
import logging

from ..core.obligations import ObligationBuilder, ObligationValidator

logger = logging.getLogger(__name__)


class LLMInterface(ABC):
    """Abstract interface for LLM communication."""
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """Generate text using the LLM."""
        pass


class MockLLM(LLMInterface):
    """Mock LLM for testing without actual LLM calls."""
    
    def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """Mock LLM response."""
        # Simple pattern matching for MVP testing
        lower = prompt.lower()
        # Save name pattern
        if "my name is" in lower:
            # naive extract last word as name token
            try:
                name = prompt.split("my name is", 1)[1].strip().strip(". !?")
            except Exception:
                name = ""
            return json.dumps({
                "obligations": [
                    {
                        "type": "ACHIEVE",
                        "payload": {"state": "status.name", "value": name}
                    }
                ]
            })
        if "2+2" in prompt:
            return json.dumps({
                "obligations": [
                    ObligationBuilder.report_math("2+2"),
                    ObligationBuilder.verify_answer()
                ]
            })
        elif "strawberry" in prompt and "r" in prompt:
            return json.dumps({
                "obligations": [
                    ObligationBuilder.report_count("r", "strawberry")
                ]
            })
        elif "friends" in prompt and "Seattle" in prompt:
            return json.dumps({
                "obligations": [
                    ObligationBuilder.report_people_query([
                        {"is_friend": "user"},
                        {"city": "Seattle"}
                    ])
                ]
            })
        elif "name" in prompt:
            return json.dumps({
                "obligations": [
                    ObligationBuilder.report_status("name")
                ]
            })
        else:
            return json.dumps({
                "obligations": [
                    ObligationBuilder.clarify_slot("intent", "Could you clarify what you're looking for?")
                ]
            })


class TranslatorIn:
    """Translates natural language to obligations."""
    
    def __init__(self, llm: LLMInterface):
        """Initialize with LLM interface."""
        self.llm = llm
        self.validator = ObligationValidator()
        self.system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        """Load the translator-in system prompt."""
        try:
            with open("prompts/translator_in.md", "r") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("Translator-in prompt file not found, using default")
            return self._get_default_system_prompt()
    
    def _get_default_system_prompt(self) -> str:
        """Get default system prompt."""
        return """
You are a translator that converts natural language into structured obligations.
Return valid JSON with this structure:
{
  "obligations": [
    {
      "type": "REPORT",
      "payload": {
        "kind": "math",
        "expr": "2+2"
      }
    }
  ]
}

Use only these obligation types: REPORT, ACHIEVE, MAINTAIN, AVOID, JUSTIFY, SCHEDULE, CLARIFY, VERIFY, DISCOVER_OP
"""
    
    def translate(self, user_input: str) -> Dict:
        """
        Translate natural language to obligations.
        
        Args:
            user_input: Natural language input from user
            
        Returns:
            Dict: Parsed obligations data or error
        """
        try:
            # Create the prompt
            prompt = f"Translate this to obligations: {user_input}"
            
            # Generate response
            response = self.llm.generate(prompt, system_prompt=self.system_prompt)
            
            # Parse JSON response
            try:
                obligations_data = json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                return {"error": f"Invalid JSON response: {e}"}
            
            # Validate against schema
            if not self.validator.validate(obligations_data):
                logger.error("Generated obligations failed schema validation")
                return {"error": "Generated obligations failed validation"}
            
            logger.info(f"Successfully translated: {user_input} -> {len(obligations_data.get('obligations', []))} obligations")
            return obligations_data
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return {"error": f"Translation failed: {e}"}


class TranslatorOut:
    """Translates assertions to natural language."""
    
    def __init__(self, llm: LLMInterface):
        """Initialize with LLM interface."""
        self.llm = llm
        self.system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        """Load the translator-out system prompt."""
        try:
            with open("prompts/translator_out.md", "r") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("Translator-out prompt file not found, using default")
            return self._get_default_system_prompt()
    
    def _get_default_system_prompt(self) -> str:
        """Get default system prompt."""
        return """
You are a translator that converts structured assertions into natural language answers.
Be concise, accurate, and include source attribution when appropriate.
Base answers ONLY on provided assertions.
"""
    
    def translate(self, assertions: List[Dict], sources: List[Dict] = None, verification_passed: bool = True) -> str:
        """
        Translate assertions to natural language.
        
        Args:
            assertions: List of assertion dictionaries
            sources: List of source dictionaries
            verification_passed: Whether verification passed
            
        Returns:
            str: Natural language answer
        """
        try:
            if not verification_passed:
                return "I'm not certain about this answer. Let me double-check."
            
            if not assertions:
                return "I don't have the information needed to answer that question."
            
            # Try deterministic rendering first (no LLM) for common patterns
            for a in assertions:
                pred = a.get("predicate")
                obj = a.get("object")
                if pred in ("evaluatesTo", "containsLetterCount") and isinstance(obj, str) and obj.strip() != "":
                    return obj
            
            # Fallback to LLM rendering
            context = self._create_context(assertions, sources)
            prompt = f"Generate a natural language answer based on these assertions:\n{context}"
            response = self.llm.generate(prompt, system_prompt=self.system_prompt)
            logger.info(f"Generated answer from {len(assertions)} assertions")
            return response.strip()
            
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"Error generating answer: {e}"
    
    def _create_context(self, assertions: List[Dict], sources: List[Dict] = None) -> str:
        """Create context string for LLM."""
        context_parts = []
        
        # Add assertions
        for assertion in assertions:
            context_parts.append(f"Assertion: {assertion['subject_id']} {assertion['predicate']} {assertion['object']}")
        
        # Add sources
        if sources:
            for source in sources:
                context_parts.append(f"Source: {source['kind']} - {source.get('uri', 'unknown')}")
        
        return "\n".join(context_parts)


class TranslatorManager:
    """Manages both input and output translators."""
    
    def __init__(self, llm: LLMInterface):
        """Initialize with LLM interface."""
        self.translator_in = TranslatorIn(llm)
        self.translator_out = TranslatorOut(llm)
    
    def process_request(self, user_input: str) -> Dict:
        """
        Process a complete translation request.
        
        Args:
            user_input: Natural language input
            
        Returns:
            Dict: Obligations data or error
        """
        return self.translator_in.translate(user_input)
    
    def generate_answer(self, assertions: List[Dict], sources: List[Dict] = None, verification_passed: bool = True) -> str:
        """
        Generate natural language answer.
        
        Args:
            assertions: List of assertions
            sources: List of sources
            verification_passed: Whether verification passed
            
        Returns:
            str: Natural language answer
        """
        return self.translator_out.translate(assertions, sources, verification_passed)


# Example usage and testing
if __name__ == "__main__":
    # Test with mock LLM
    mock_llm = MockLLM()
    translator_manager = TranslatorManager(mock_llm)
    
    # Test input translation
    test_inputs = [
        "What's 2+2?",
        "How many r's in 'strawberry'?",
        "List my friends in Seattle",
        "What's your name?"
    ]
    
    for user_input in test_inputs:
        print(f"\nInput: {user_input}")
        obligations = translator_manager.process_request(user_input)
        print(f"Obligations: {json.dumps(obligations, indent=2)}")
    
    # Test output translation
    test_assertions = [
        {"subject_id": "Expr_1", "predicate": "evaluatesTo", "object": "4"},
        {"subject_id": "Text_1", "predicate": "containsLetterCount", "object": "2"}
    ]
    
    answer = translator_manager.generate_answer(test_assertions)
    print(f"\nGenerated answer: {answer}")
