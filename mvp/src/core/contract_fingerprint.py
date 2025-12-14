"""
Compute contract fingerprints for tools.
"""

import hashlib
import json
from typing import Dict, Any


def compute_contract_fingerprint(contract_data: Dict[str, Any]) -> str:
    """Compute a fingerprint hash of a tool contract.
    
    Includes all contract fields except implementation details that don't affect behavior.
    """
    # Fields that affect tool behavior (included in fingerprint)
    fingerprint_data = {
        "name": contract_data.get("name"),
        "version": contract_data.get("version", "1.0.0"),
        "consumes": contract_data.get("consumes", []),
        "produces": contract_data.get("produces", []),
        "satisfies": contract_data.get("satisfies", []),
        "preconditions": contract_data.get("preconditions", []),
        "postconditions": contract_data.get("postconditions", []),
        "depends_on": contract_data.get("depends_on", []),
        "supports": contract_data.get("supports", []),
        "cost": contract_data.get("cost", "medium"),
        "reliability": contract_data.get("reliability", "medium"),
        "verify_mode": contract_data.get("verify_mode", "blocking"),
        "capability_tier": contract_data.get("capability_tier", "safe")
    }
    
    # Create stable JSON representation
    fingerprint_json = json.dumps(fingerprint_data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(fingerprint_json.encode('utf-8')).hexdigest()
