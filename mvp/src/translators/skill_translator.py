"""
Skill-based translator: translates NL to RUN_SKILL obligations using a skill menu.

This translator:
1. Does local skill search (no LLM)
2. Presents skill menu to LLM
3. LLM chooses from menu only
4. Validates strictly
5. Caches translations
"""

import json
import hashlib
import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from .real_llm import OpenAILLM
from ..core.skills import SkillRegistry
from ..core.obligations import ObligationValidator
from ..core.cache import canonicalize_inputs

logger = logging.getLogger(__name__)


class SkillTranslator:
    """Translates natural language to RUN_SKILL obligations using skill menu."""
    
    def __init__(
        self,
        llm: OpenAILLM,
        skill_registry: SkillRegistry,
        translator_model: str = "gpt-4o-mini",
        translator_prompt_version: str = "1.0.0"
    ):
        """Initialize skill-based translator."""
        self.llm = llm
        self.skill_registry = skill_registry
        self.translator_model = translator_model
        self.translator_prompt_version = translator_prompt_version
        self.validator = ObligationValidator()
        self.system_prompt = self._load_system_prompt()
        self._translation_cache: Dict[str, Dict[str, Any]] = {}
    
    def _load_system_prompt(self) -> str:
        """Load the skill-based translator system prompt."""
        try:
            prompt_path = Path("prompts/translator_skill_in.md")
            if prompt_path.exists():
                return prompt_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to load skill translator prompt: {e}")
        
        return self._get_default_system_prompt()
    
    def _get_default_system_prompt(self) -> str:
        """Default system prompt for skill-based translation."""
        return """You are a translator. Output JSON only. You must choose from the allowed skills list. If none match, output CLARIFY or DISCOVER_OP. Do not mention tools. Do not mention internal reasoning.

Output format:
{
  "obligations": [
    {
      "type": "RUN_SKILL",
      "payload": {
        "name": "<skill_name_from_menu>",
        "inputs": {},
        "constraints": {},
        "capability_budgets": {}
      }
    }
  ]
}

If missing information, use CLARIFY:
{
  "obligations": [
    {
      "type": "CLARIFY",
      "payload": {
        "slots": ["<slot_name>"],
        "question": "<short question>"
      }
    }
  ]
}

If no skill matches, use DISCOVER_OP:
{
  "obligations": [
    {
      "type": "DISCOVER_OP",
      "payload": {
        "goal": "<what the user wants>",
        "inputs": {},
        "constraints": {}
      }
    }
  ]
}"""
    
    def _compute_cache_key(
        self,
        user_text: str,
        skill_menu: List[Dict[str, Any]]
    ) -> str:
        """Compute cache key for translation."""
        # Create fingerprint of skill menu (names + versions)
        menu_fingerprint = {
            "skills": [
                {"name": s["name"], "version": s.get("version", "1.0.0")}
                for s in skill_menu
            ]
        }
        menu_str = json.dumps(menu_fingerprint, sort_keys=True)
        menu_hash = hashlib.sha256(menu_str.encode()).hexdigest()[:16]
        
        # Hash user text
        user_hash = hashlib.sha256(user_text.encode()).hexdigest()[:16]
        
        # Combine with model and prompt version
        cache_data = {
            "user_text_hash": user_hash,
            "skill_menu_fingerprint": menu_hash,
            "translator_model": self.translator_model,
            "translator_prompt_version": self.translator_prompt_version
        }
        
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()
    
    def _lookup_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Look up cached translation."""
        return self._translation_cache.get(cache_key)
    
    def _store_cache(self, cache_key: str, obligations: Dict[str, Any]):
        """Store translation in cache."""
        self._translation_cache[cache_key] = obligations
    
    def _build_user_prompt(
        self,
        user_text: str,
        skill_menu: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> str:
        """Build user prompt with skill menu."""
        prompt_parts = []
        
        prompt_parts.append(f"USER_TEXT: {user_text}\n")
        
        prompt_parts.append("ALLOWED SKILLS MENU:")
        for i, skill in enumerate(skill_menu, 1):
            prompt_parts.append(f"\n{i}. {skill['name']}")
            prompt_parts.append(f"   Description: {skill.get('description', 'No description')}")
            
            # Add inputs schema
            inputs_schema = skill.get('inputs_schema', {})
            if inputs_schema:
                prompt_parts.append(f"   Inputs schema: {json.dumps(inputs_schema, indent=6)}")
            
            # Add constraints schema if present
            constraints_schema = skill.get('constraints_schema')
            if constraints_schema:
                prompt_parts.append(f"   Constraints schema: {json.dumps(constraints_schema, indent=6)}")
        
        # Add context info
        if context.get("platform"):
            prompt_parts.append(f"\nPLATFORM: {context['platform']}")
        if context.get("cwd"):
            prompt_parts.append(f"CWD: {context['cwd']}")
        if context.get("budgets"):
            prompt_parts.append(f"DEFAULT BUDGETS: {json.dumps(context['budgets'], indent=2)}")
        
        prompt_parts.append("\nOUTPUT OBLIGATIONS SCHEMA:")
        prompt_parts.append("- type: RUN_SKILL | CLARIFY | DISCOVER_OP")
        prompt_parts.append("- RUN_SKILL requires: payload.name (must be from menu), payload.inputs")
        prompt_parts.append("- CLARIFY requires: payload.slots (array), payload.question")
        prompt_parts.append("- DISCOVER_OP requires: payload.goal")
        
        return "\n".join(prompt_parts)
    
    def _validate_obligations(
        self,
        obligations_data: Dict[str, Any],
        skill_menu: List[Dict[str, Any]]
    ) -> tuple[bool, Optional[str], Optional[List[str]]]:
        """Validate obligations against schema and skill menu.
        
        Returns: (is_valid, error_message, validation_errors)
        """
        # Check basic structure
        if not isinstance(obligations_data, dict):
            return False, "Invalid JSON structure", ["Root must be an object"]
        
        if "obligations" not in obligations_data:
            return False, "Missing obligations array", ["Must have 'obligations' field"]
        
        obligations = obligations_data.get("obligations", [])
        if not isinstance(obligations, list) or len(obligations) == 0:
            return False, "Invalid obligations array", ["obligations must be a non-empty array"]
        
        errors = []
        allowed_skill_names = {s["name"] for s in skill_menu}
        
        for i, ob in enumerate(obligations):
            if not isinstance(ob, dict):
                errors.append(f"Obligation {i}: must be an object")
                continue
            
            ob_type = ob.get("type")
            payload = ob.get("payload", {})
            
            if ob_type == "RUN_SKILL":
                skill_name = payload.get("name")
                if not skill_name:
                    errors.append(f"Obligation {i}: RUN_SKILL missing 'name' in payload")
                elif skill_name not in allowed_skill_names:
                    errors.append(f"Obligation {i}: skill name '{skill_name}' not in menu")
                
                # Check inputs match schema
                if skill_name and skill_name in allowed_skill_names:
                    skill = next(s for s in skill_menu if s["name"] == skill_name)
                    inputs_schema = skill.get("inputs_schema", {})
                    inputs = payload.get("inputs", {})
                    
                    # Basic schema validation (can be enhanced)
                    required = inputs_schema.get("required", [])
                    for req_field in required:
                        if req_field not in inputs:
                            errors.append(f"Obligation {i}: missing required input '{req_field}'")
            
            elif ob_type == "CLARIFY":
                slots = payload.get("slots")
                question = payload.get("question")
                if not slots and not payload.get("slot"):
                    errors.append(f"Obligation {i}: CLARIFY missing 'slots' or 'slot'")
                if not question and not payload.get("context"):
                    errors.append(f"Obligation {i}: CLARIFY missing 'question' or 'context'")
            
            elif ob_type == "DISCOVER_OP":
                if not payload.get("goal"):
                    errors.append(f"Obligation {i}: DISCOVER_OP missing 'goal'")
            
            elif ob_type not in ["CLARIFY", "DISCOVER_OP", "RUN_SKILL"]:
                errors.append(f"Obligation {i}: invalid type '{ob_type}' (must be RUN_SKILL, CLARIFY, or DISCOVER_OP)")
        
        # Also validate against JSON schema
        if not self.validator.validate(obligations_data):
            errors.append("Failed JSON schema validation")
        
        if errors:
            return False, "Validation failed", errors
        
        return True, None, None
    
    def translate(
        self,
        user_text: str,
        context: Optional[Dict[str, Any]] = None,
        top_n_skills: int = 10
    ) -> Dict[str, Any]:
        """Translate natural language to RUN_SKILL obligations.
        
        Args:
            user_text: Natural language input
            context: Optional context (platform, cwd, budgets)
            top_n_skills: Number of skills to include in menu
        
        Returns:
            Dict with obligations or error
        """
        if context is None:
            context = {
                "platform": os.name,
                "cwd": str(Path.cwd()),
                "budgets": {
                    "max_tool_runs": 20,
                    "max_cache_misses": 5,
                    "max_toolsmith_calls": 0
                }
            }
        
        try:
            # Step 1: Local skill search (no LLM)
            skill_menu = self.skill_registry.get_skill_menu(user_text, top_n=top_n_skills)
            
            # Step 2: Check cache
            cache_key = self._compute_cache_key(user_text, skill_menu)
            cached = self._lookup_cache(cache_key)
            if cached:
                logger.info(f"Cache hit for translation: {cache_key[:8]}...")
                return cached
            
            # Step 3: Build prompt
            user_prompt = self._build_user_prompt(user_text, skill_menu, context)
            
            # Step 4: LLM translation
            logger.info(f"Translating with {len(skill_menu)} skills in menu")
            response = self.llm.generate_structured(
                user_prompt,
                system_prompt=self.system_prompt
            )
            
            # Step 5: Validate
            is_valid, error_msg, validation_errors = self._validate_obligations(
                response, skill_menu
            )
            
            if not is_valid:
                # One repair attempt
                logger.warning(f"Initial validation failed: {error_msg}")
                if validation_errors:
                    repair_prompt = f"{user_prompt}\n\nVALIDATION ERRORS:\n" + "\n".join(validation_errors)
                    repair_prompt += "\n\nPlease fix the JSON to address these errors."
                    response = self.llm.generate_structured(
                        repair_prompt,
                        system_prompt=self.system_prompt
                    )
                    
                    # Re-validate
                    is_valid, error_msg, validation_errors = self._validate_obligations(
                        response, skill_menu
                    )
                
                if not is_valid:
                    # Return CLARIFY on validation failure
                    logger.error(f"Translation validation failed after repair: {error_msg}")
                    return {
                        "obligations": [
                            {
                                "type": "CLARIFY",
                                "payload": {
                                    "slots": ["translation_error"],
                                    "question": f"Translation failed: {error_msg}"
                                }
                            }
                        ]
                    }
            
            # Step 6: Cache and return
            self._store_cache(cache_key, response)
            logger.info(f"Successfully translated: {user_text} -> {len(response.get('obligations', []))} obligations")
            return response
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return {
                "obligations": [
                    {
                        "type": "CLARIFY",
                        "payload": {
                            "slots": ["translation_error"],
                            "question": f"Translation error: {str(e)}"
                        }
                    }
                ]
            }
