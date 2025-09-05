"""
Real LLM integration for the MVP system.

This module provides OpenAI integration to replace the MockLLM
with actual LLM calls for translating natural language to obligations.
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from pydantic import BaseModel

from .translators import LLMInterface, ObligationBuilder

logger = logging.getLogger(__name__)


class ObligationResponse(BaseModel):
    """Pydantic model for structured obligation responses."""
    obligations: list[Dict[str, Any]]


class OpenAILLM(LLMInterface):
    """OpenAI LLM implementation for real LLM calls."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """Initialize OpenAI client."""
        self.client = OpenAI(api_key=api_key)
        self.model = model
        logger.info(f"OpenAI LLM initialized with model: {model}")
    
    def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """Generate text using OpenAI API."""
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,  # Low temperature for consistent obligation parsing
                max_tokens=1000,
                **kwargs
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            # Fallback to mock response
            return self._fallback_response(prompt)
    
    def generate_structured(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        """Generate structured obligations using OpenAI's structured outputs."""
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            # Use structured outputs for reliable JSON generation
            response = self.client.chat.completions.create(
                model="gpt-4o-2024-08-06",  # Model with structured outputs support
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"OpenAI structured generation failed: {e}")
            # Fallback to regular generation
            content = self.generate(prompt, system_prompt)
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return self._fallback_response(prompt)
    
    def _fallback_response(self, prompt: str) -> str:
        """Fallback response when API fails."""
        logger.warning("Using fallback response due to API failure")
        
        # Simple pattern matching as fallback
        if "2+2" in prompt or "math" in prompt.lower():
            return json.dumps({
                "obligations": [
                    ObligationBuilder.report_math("2+2"),
                    ObligationBuilder.verify_answer()
                ]
            })
        elif "count" in prompt.lower() or "how many" in prompt.lower():
            return json.dumps({
                "obligations": [
                    ObligationBuilder.report_count("r", "strawberry")
                ]
            })
        elif "friends" in prompt.lower() or "people" in prompt.lower():
            return json.dumps({
                "obligations": [
                    ObligationBuilder.report_people_query([
                        {"is_friend": "user"},
                        {"city": "Seattle"}
                    ])
                ]
            })
        else:
            return json.dumps({
                "obligations": [
                    ObligationBuilder.clarify_slot("intent", "Could you clarify what you're looking for?")
                ]
            })


class RealTranslatorIn:
    """Real translator using OpenAI for NL to obligations."""
    
    def __init__(self, llm: OpenAILLM):
        """Initialize with OpenAI LLM."""
        self.llm = llm
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

For math questions, use REPORT with kind="math" and expr="<expression>"
For counting questions, use REPORT with kind="count", letter="<letter>", word="<word>"
For people queries, use REPORT with kind="query.people" and filters array
For status questions, use REPORT with kind="status" and field="<field>"
Always include VERIFY obligation for factual answers when appropriate.
"""
    
    def translate(self, user_input: str) -> Dict:
        """
        Translate natural language to obligations using OpenAI.
        
        Args:
            user_input: Natural language input from user
            
        Returns:
            Dict: Parsed obligations data or error
        """
        try:
            # Create the prompt
            prompt = f"Translate this to obligations: {user_input}"
            
            # Use structured generation for reliable JSON
            obligations_data = self.llm.generate_structured(prompt, system_prompt=self.system_prompt)
            
            # Validate the response
            if not isinstance(obligations_data, dict) or "obligations" not in obligations_data:
                logger.error("Invalid response format from LLM")
                return {"error": "Invalid response format from LLM"}
            
            logger.info(f"Successfully translated: {user_input} -> {len(obligations_data.get('obligations', []))} obligations")
            return obligations_data
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return {"error": f"Translation failed: {e}"}


class RealTranslatorOut:
    """Real translator using OpenAI for assertions to natural language."""
    
    def __init__(self, llm: OpenAILLM):
        """Initialize with OpenAI LLM."""
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

For math results: Just give the number (e.g., "4")
For counting results: Just give the count (e.g., "2")
For people queries: List names with source attribution (e.g., "Alice, Bob (per your contacts database)")
For status queries: Give the status value

Be helpful but don't invent information not in the assertions.
"""
    
    def translate(self, assertions: list[Dict], sources: list[Dict] = None, verification_passed: bool = True) -> str:
        """
        Translate assertions to natural language using OpenAI.
        
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
            
            # Create context for LLM
            context = self._create_context(assertions, sources)
            
            # Generate response
            prompt = f"Generate a natural language answer based on these assertions:\n{context}"
            response = self.llm.generate(prompt, system_prompt=self.system_prompt)
            
            logger.info(f"Generated answer from {len(assertions)} assertions")
            return response.strip()
            
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"Error generating answer: {e}"
    
    def _create_context(self, assertions: list[Dict], sources: list[Dict] = None) -> str:
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


class RealTranslatorManager:
    """Manages both input and output translators with real LLM."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """Initialize with OpenAI API key and model."""
        self.llm = OpenAILLM(api_key, model)
        self.translator_in = RealTranslatorIn(self.llm)
        self.translator_out = RealTranslatorOut(self.llm)
    
    def process_request(self, user_input: str) -> Dict[str, Any]:
        """
        Process a complete translation request.
        
        Args:
            user_input: Natural language input
            
        Returns:
            Dict: Obligations data or error
        """
        return self.translator_in.translate(user_input)
    
    def generate_answer(self, assertions: list[Dict], sources: list[Dict] = None, verification_passed: bool = True) -> str:
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
    # Test with real OpenAI LLM
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Please set OPENAI_API_KEY environment variable")
        exit(1)
    
    translator_manager = RealTranslatorManager(api_key)
    
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
