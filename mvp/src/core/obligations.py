"""
Obligation parsing and validation.

This module handles parsing natural language into obligations
and validating obligation structures against the schema.
"""

import json
import jsonschema
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ObligationPayload:
    """Represents an obligation payload."""
    kind: Optional[str] = None
    expr: Optional[str] = None
    field: Optional[str] = None
    filters: Optional[List[Dict]] = None
    letter: Optional[str] = None
    word: Optional[str] = None
    state: Optional[str] = None
    pred: Optional[str] = None
    args: Optional[Dict] = None
    claim: Optional[str] = None
    target: Optional[str] = None
    slot: Optional[str] = None
    goal: Optional[Any] = None
    value: Optional[str] = None
    query: Optional[Dict] = None
    budgets: Optional[Dict] = None
    rules: Optional[List[Dict]] = None
    domains: Optional[List[str]] = None
    mode: Optional[str] = None
    facts: Optional[List[Dict]] = None
    facts_bundle_id: Optional[str] = None


@dataclass
class ParsedObligation:
    """Represents a parsed obligation."""
    type: str
    payload: ObligationPayload
    raw_payload: Dict[str, Any]


class ObligationValidator:
    """Validates obligations against the schema."""
    
    def __init__(self, schema_path: str = "schemas/obligation.schema.json"):
        """Initialize with schema."""
        with open(schema_path, "r") as f:
            self.schema = json.load(f)
    
    def validate(self, obligations_data: Dict) -> bool:
        """Validate obligations data against schema."""
        try:
            jsonschema.validate(obligations_data, self.schema)
            return True
        except jsonschema.ValidationError as e:
            logger.error(f"Schema validation failed: {e.message}")
            return False
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False
    
    def validate_obligation(self, obligation: Dict) -> bool:
        """Validate a single obligation."""
        try:
            # Create a minimal obligations structure for validation
            obligations_data = {"obligations": [obligation]}
            return self.validate(obligations_data)
        except Exception as e:
            logger.error(f"Obligation validation error: {e}")
            return False


class ObligationParser:
    """Parses obligations from JSON data."""
    
    def __init__(self):
        """Initialize parser."""
        self.validator = ObligationValidator()
    
    def parse_obligations(self, obligations_data: Dict) -> List[ParsedObligation]:
        """Parse obligations from JSON data."""
        if not self.validator.validate(obligations_data):
            raise ValueError("Invalid obligations data")
        
        parsed_obligations = []
        for obligation_data in obligations_data.get("obligations", []):
            parsed = self._parse_single_obligation(obligation_data)
            parsed_obligations.append(parsed)
        
        return parsed_obligations
    
    def _parse_single_obligation(self, obligation_data: Dict) -> ParsedObligation:
        """Parse a single obligation."""
        obligation_type = obligation_data["type"]
        payload_data = obligation_data["payload"]
        # Enforce mode for logic/planning kinds
        if isinstance(payload_data, dict):
            k = payload_data.get("kind")
            if k in ("logic", "plan") and not payload_data.get("mode"):
                raise ValueError("mode is required for logic/plan payloads")
        
        # Create payload object based on type
        payload = self._create_payload(obligation_type, payload_data)
        
        return ParsedObligation(
            type=obligation_type,
            payload=payload,
            raw_payload=payload_data
        )
    
    def _create_payload(self, obligation_type: str, payload_data: Dict) -> ObligationPayload:
        """Create payload object based on obligation type."""
        if obligation_type == "REPORT":
            return ObligationPayload(
                kind=payload_data["kind"],
                expr=payload_data.get("expr"),
                field=payload_data.get("field"),
                filters=payload_data.get("filters"),
                letter=payload_data.get("letter"),
                word=payload_data.get("word"),
                query=payload_data.get("query"),
                budgets=payload_data.get("reasoning", {}).get("budgets") if isinstance(payload_data.get("reasoning"), dict) else payload_data.get("budgets"),
                rules=payload_data.get("rules"),
                domains=payload_data.get("domains"),
                mode=payload_data.get("mode"),
                facts=payload_data.get("facts"),
                facts_bundle_id=payload_data.get("facts_bundle_id")
            )
        elif obligation_type == "ACHIEVE":
            return ObligationPayload(
                state=payload_data["state"],
                pred=payload_data.get("pred"),
                args=payload_data.get("args"),
                value=payload_data.get("value"),
                budgets=payload_data.get("reasoning", {}).get("budgets") if isinstance(payload_data.get("reasoning"), dict) else payload_data.get("budgets"),
                mode=payload_data.get("mode")
            )
        elif obligation_type in ["MAINTAIN", "AVOID"]:
            return ObligationPayload(
                pred=payload_data["pred"],
                args=payload_data.get("args")
            )
        elif obligation_type == "JUSTIFY":
            return ObligationPayload(
                claim=payload_data["claim"]
            )
        elif obligation_type == "VERIFY":
            return ObligationPayload(
                target=payload_data["target"]
            )
        elif obligation_type == "CLARIFY":
            return ObligationPayload(
                slot=payload_data["slot"]
            )
        elif obligation_type == "DISCOVER_OP":
            return ObligationPayload(
                goal=payload_data["goal"]
            )
        else:
            # Generic payload for unknown types
            return ObligationPayload(
                kind=payload_data.get("kind", "unknown")
            )


class ObligationBuilder:
    """Builds obligations programmatically."""
    
    @staticmethod
    def report_math(expr: str) -> Dict:
        """Build a math report obligation."""
        return {
            "type": "REPORT",
            "payload": {
                "kind": "math",
                "expr": expr
            }
        }
    
    @staticmethod
    def report_people_query(filters: List[Dict]) -> Dict:
        """Build a people query obligation."""
        return {
            "type": "REPORT",
            "payload": {
                "kind": "query.people",
                "filters": filters
            }
        }
    
    @staticmethod
    def report_count(letter: str, word: str) -> Dict:
        """Build a count obligation."""
        return {
            "type": "REPORT",
            "payload": {
                "kind": "count",
                "letter": letter,
                "word": word
            }
        }
    
    @staticmethod
    def report_status(field: str) -> Dict:
        """Build a status report obligation."""
        return {
            "type": "REPORT",
            "payload": {
                "kind": "status",
                "field": field
            }
        }
    
    @staticmethod
    def verify_answer(target: str = "last_answer") -> Dict:
        """Build a verify obligation."""
        return {
            "type": "VERIFY",
            "payload": {
                "target": target
            }
        }
    
    @staticmethod
    def clarify_slot(slot: str, context: str = None) -> Dict:
        """Build a clarify obligation."""
        payload = {"slot": slot}
        if context:
            payload["context"] = context
        return {
            "type": "CLARIFY",
            "payload": payload
        }
    
    @staticmethod
    def discover_op(goal: Any) -> Dict:
        """Build a discover operation obligation.

        goal can be a simple string or a structured object (e.g., a missing-capability payload).
        """
        return {
            "type": "DISCOVER_OP",
            "payload": {
                "goal": goal
            }
        }


# Example usage and testing
if __name__ == "__main__":
    # Test obligation parsing
    parser = ObligationParser()
    
    # Test math obligation
    math_obligations = {
        "obligations": [
            ObligationBuilder.report_math("2+2"),
            ObligationBuilder.verify_answer()
        ]
    }
    
    parsed = parser.parse_obligations(math_obligations)
    print(f"Parsed {len(parsed)} obligations")
    for p in parsed:
        print(f"  {p.type}: {p.payload}")
    
    # Test people query
    people_obligations = {
        "obligations": [
            ObligationBuilder.report_people_query([
                {"is_friend": "user"},
                {"city": "Seattle"}
            ])
        ]
    }
    
    parsed = parser.parse_obligations(people_obligations)
    print(f"Parsed {len(parsed)} obligations")
    for p in parsed:
        print(f"  {p.type}: {p.payload}")
