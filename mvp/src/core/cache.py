"""
Tool execution caching utilities.

Provides canonicalization and hashing for cache keys.
"""

import json
import hashlib
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional


def canonicalize_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Canonicalize tool inputs for consistent hashing.
    
    - Sorts dict keys
    - Sorts list items if they're comparable
    - Removes None values (optional fields)
    - Normalizes whitespace in strings
    """
    if not isinstance(inputs, dict):
        return inputs
    
    canonical = {}
    for key in sorted(inputs.keys()):
        val = inputs[key]
        if val is None:
            continue  # Skip None values
        if isinstance(val, dict):
            canonical[key] = canonicalize_inputs(val)
        elif isinstance(val, list):
            # Try to sort if items are comparable
            try:
                canonical[key] = sorted([canonicalize_inputs(v) if isinstance(v, dict) else v for v in val])
            except TypeError:
                # Not sortable, keep original order
                canonical[key] = [canonicalize_inputs(v) if isinstance(v, dict) else v for v in val]
        elif isinstance(val, str):
            # Normalize whitespace
            canonical[key] = " ".join(val.split())
        else:
            canonical[key] = val
    
    return canonical


def compute_dependency_hash(depends_on: List[str]) -> tuple[Optional[str], Dict[str, Any]]:
    """Compute hash of external dependencies for cache invalidation.
    
    Args:
        depends_on: List of dependency specifiers in format "type:identifier"
                    Examples: ["filesystem:path/to/file", "env:TZ", "db:people.sqlite", "clock"]
    
    Returns:
        Tuple of (SHA256 hash of dependency states, dependency snapshot dict)
        Hash is None if no dependencies, snapshot is empty dict if no dependencies
    """
    if not depends_on:
        return None, {}
    
    dependency_states = {}
    dependency_snapshot = {}
    
    for dep in depends_on:
        if not isinstance(dep, str):
            continue
        
        parts = dep.split(":", 1)
        if len(parts) != 2:
            continue
        
        dep_type, dep_id = parts[0].strip(), parts[1].strip()
        
        if dep_type == "filesystem":
            # Hash file mtime and size, or directory contents
            path = Path(dep_id)
            try:
                if path.is_file():
                    stat = path.stat()
                    dependency_states[dep] = {
                        "mtime": stat.st_mtime,
                        "size": stat.size
                    }
                    dependency_snapshot[dep] = {
                        "mtime": stat.st_mtime,
                        "size": stat.size
                    }
                elif path.is_dir():
                    # Hash directory contents (file names and mtimes)
                    files = {}
                    for item in path.rglob("*"):
                        if item.is_file():
                            stat = item.stat()
                            files[str(item.relative_to(path))] = {
                                "mtime": stat.st_mtime,
                                "size": stat.size
                            }
                    dependency_states[dep] = files
                    dependency_snapshot[dep] = files
                else:
                    # File doesn't exist - hash None
                    dependency_states[dep] = None
                    dependency_snapshot[dep] = None
            except Exception:
                dependency_states[dep] = None
                dependency_snapshot[dep] = None
        
        elif dep_type == "env":
            # Hash environment variable value
            env_value = os.environ.get(dep_id, None)
            dependency_states[dep] = env_value
            # Store hashed value for snapshot (safe to share)
            if env_value:
                value_hash = hashlib.sha256(str(env_value).encode('utf-8')).hexdigest()
                value_preview = str(env_value)[:3] if len(str(env_value)) >= 3 else str(env_value)
                dependency_snapshot[dep_id] = {
                    "hash": f"sha256:{value_hash}",
                    "preview": value_preview
                }
            else:
                dependency_snapshot[dep_id] = None
        
        elif dep_type == "db":
            # Hash database file mtime and size
            db_path = Path(dep_id)
            try:
                if db_path.exists():
                    stat = db_path.stat()
                    dependency_states[dep] = {
                        "mtime": stat.st_mtime,
                        "size": stat.size
                    }
                    dependency_snapshot[dep] = {
                        "mtime": stat.st_mtime,
                        "size": stat.size
                    }
                else:
                    dependency_states[dep] = None
                    dependency_snapshot[dep] = None
            except Exception:
                dependency_states[dep] = None
                dependency_snapshot[dep] = None
        
        elif dep_type == "clock":
            # For clock, we typically don't cache, but if we do, use a time window
            # For now, just include current time (this makes clock-dependent tools rarely cache)
            clock_value = int(time.time() / 60)  # Minute-level granularity
            dependency_states[dep] = clock_value
            dependency_snapshot[dep] = clock_value
        
        else:
            # Unknown dependency type - include as-is
            dependency_states[dep] = dep
            dependency_snapshot[dep] = dep
    
    if not dependency_states:
        return None, {}
    
    # Hash the dependency states
    dep_json = json.dumps(dependency_states, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(dep_json.encode('utf-8')).hexdigest(), dependency_snapshot


def compute_input_hash(tool_name: str, inputs: Dict[str, Any], tool_version: str = "1.0.0", depends_on: List[str] = None) -> Dict[str, Any]:
    """Compute cache key components with detailed breakdown.
    
    Args:
        tool_name: Name of the tool
        inputs: Tool input parameters
        tool_version: Tool version string
        depends_on: Optional list of external dependencies (e.g., ["filesystem:path", "env:TZ"])
    
    Returns:
        Dict with keys:
        - input_hash: hash of canonicalized inputs only
        - depends_on_hash: hash of dependencies (None if no deps)
        - cache_key: full cache key hash
        - dependency_snapshot: snapshot of dependency states (for reporting)
    """
    canonical = canonicalize_inputs(inputs)
    
    # Hash inputs only (without dependencies)
    input_only_data = {
        "tool_name": tool_name,
        "inputs": canonical,
        "tool_version": tool_version
    }
    input_only_json = json.dumps(input_only_data, sort_keys=True, separators=(',', ':'))
    input_hash = hashlib.sha256(input_only_json.encode('utf-8')).hexdigest()
    
    # Compute dependency hash and snapshot
    dep_hash, dep_snapshot = compute_dependency_hash(depends_on or [])
    
    # Create full cache key
    key_data = {
        "tool_name": tool_name,
        "inputs": canonical,
        "tool_version": tool_version
    }
    
    # Include dependency hash if present
    if dep_hash:
        key_data["depends_on_hash"] = dep_hash
    
    key_json = json.dumps(key_data, sort_keys=True, separators=(',', ':'))
    cache_key = hashlib.sha256(key_json.encode('utf-8')).hexdigest()
    
    return {
        "input_hash": input_hash,
        "depends_on_hash": dep_hash,
        "cache_key": cache_key,
        "dependency_snapshot": dep_snapshot
    }


