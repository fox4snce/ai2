"""
Skill layer: versioned, named workflows that compile to obligations.

Skills are reusable workflow templates stored as JSON/YAML that can include:
- Branching policy
- Constraints
- Step references ($ref)
- Versioning
"""

import json
import yaml
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Registry for workflow skills."""
    
    def __init__(self, skills_dir: str = None):
        """Initialize skill registry.
        
        If skills_dir is None, defaults to mvp/skills/
        """
        if skills_dir is None:
            base_dir = Path(__file__).resolve().parents[2]
            skills_dir = str(base_dir / "skills")
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Dict[str, Any]] = {}
        self._load_skills()
    
    def _load_skills(self):
        """Load all skills from directory."""
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            return
        
        skill_files = list(self.skills_dir.glob("*.yaml")) + list(self.skills_dir.glob("*.yml")) + list(self.skills_dir.glob("*.json"))
        for skill_file in skill_files:
            try:
                with open(skill_file, "r", encoding="utf-8-sig") as f:
                    if skill_file.suffix == ".json":
                        skill_data = json.load(f)
                    else:
                        skill_data = yaml.safe_load(f)
                
                name = skill_data.get("name")
                version = skill_data.get("version", "1.0.0")
                key = f"{name}@{version}"
                self.skills[key] = skill_data
                logger.info(f"Loaded skill: {key}")
            except Exception as e:
                logger.warning(f"Failed to load skill from {skill_file}: {e}")
    
    def get_skill(self, name: str, version: str = "1.0.0") -> Optional[Dict[str, Any]]:
        """Get a skill by name and version."""
        key = f"{name}@{version}"
        return self.skills.get(key)
    
    def compile_to_obligations(self, skill_name: str, inputs: Dict[str, Any], version: str = "1.0.0") -> Dict[str, Any]:
        """Compile a skill to obligations with provided inputs.
        
        Skills are templates that may include:
        - Branching logic (on_no_emails, etc.)
        - Constraints (denylist_domains, etc.)
        - Step references ($ref)
        """
        skill = self.get_skill(skill_name, version)
        if not skill:
            raise ValueError(f"Skill {skill_name}@{version} not found")
        
        # Simple template substitution: replace {{inputs.key}} with actual values
        template = json.dumps(skill.get("obligations", []))
        for key, value in inputs.items():
            template = template.replace(f"{{{{inputs.{key}}}}}", json.dumps(value) if not isinstance(value, str) else value)
        
        obligations = json.loads(template)
        
        # Merge constraints if provided
        if "constraints" in inputs:
            for ob in obligations:
                if ob.get("type") == "ACHIEVE" and ob.get("payload", {}).get("state") == "plan":
                    ob["payload"]["constraints"] = inputs.get("constraints", {})
        
        return {"obligations": obligations}
    
    def extract_input_schema(self, skill: Dict[str, Any]) -> Dict[str, Any]:
        """Extract input schema from a skill by analyzing template variables.
        
        Returns a JSON schema for the inputs based on {{inputs.key}} patterns.
        """
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # Find all {{inputs.key}} patterns in the skill
        skill_str = json.dumps(skill, indent=2)
        pattern = r'\{\{inputs\.(\w+)\}\}'
        matches = re.findall(pattern, skill_str)
        
        for key in set(matches):
            # Check if it's used in a way that suggests it's required
            # For now, mark all as optional unless we have better heuristics
            schema["properties"][key] = {
                "type": "string",  # Default to string, can be refined
                "description": f"Input parameter: {key}"
            }
        
        # Also check for explicit schema in skill metadata
        if "inputs_schema" in skill:
            schema = skill["inputs_schema"]
        
        return schema
    
    def extract_constraints_schema(self, skill: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract constraints schema from a skill."""
        if "constraints_schema" in skill:
            return skill["constraints_schema"]
        return None
    
    def search_skills(self, query: str, top_n: int = 10, threshold: float = 0.0) -> List[Dict[str, Any]]:
        """Search skills by name and description using simple keyword matching.
        
        This is a local, deterministic search - no LLM involved.
        Returns skills sorted by relevance (simple keyword match score).
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        results = []
        
        for key, skill in self.skills.items():
            name = skill.get("name", "")
            description = skill.get("description", "")
            text = f"{name} {description}".lower()
            
            # Simple keyword matching score
            score = 0.0
            matched_words = 0
            
            for word in query_words:
                if word in text:
                    score += 1.0
                    matched_words += 1
                    # Boost if word appears in name
                    if word in name.lower():
                        score += 0.5
            
            # Normalize score by query length
            if len(query_words) > 0:
                score = score / len(query_words)
            
            if score >= threshold:
                # Extract schemas
                inputs_schema = self.extract_input_schema(skill)
                constraints_schema = self.extract_constraints_schema(skill)
                
                results.append({
                    "name": name,
                    "version": skill.get("version", "1.0.0"),
                    "description": description or f"Skill: {name}",
                    "inputs_schema": inputs_schema,
                    "constraints_schema": constraints_schema,
                    "score": score
                })
        
        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Return top N
        return results[:top_n]
    
    def get_skill_menu(self, query: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get skill menu for LLM translation.
        
        Returns list of skills with schemas, or includes __NO_MATCH__ if no skills found.
        """
        results = self.search_skills(query, top_n=top_n, threshold=0.0)
        
        if not results:
            return [{
                "name": "__NO_MATCH__",
                "description": "No matching skills found",
                "inputs_schema": {},
                "constraints_schema": None
            }]
        
        return results


