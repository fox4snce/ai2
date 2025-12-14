"""
Real cache invalidation abuse test.

Creates tools with actual dependencies and verifies cache invalidation works.
"""

import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

# Add mvp to path
mvp_dir = Path(__file__).resolve().parent.parent
if str(mvp_dir) not in sys.path:
    sys.path.insert(0, str(mvp_dir))

from src.main import MVPAPI


def create_test_tool_with_env_dependency():
    """Create a test tool contract that depends on an env var."""
    contracts_dir = mvp_dir / "contracts" / "tools" / "generated"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    
    tool_yaml = """name: TestTool.EnvDependent
description: Test tool that depends on environment variable
version: 1.0.0
consumes:
  - kind: test.env_dependent
    schema:
      type: object
      properties:
        kind:
          type: string
          enum: [test.env_dependent]
        value:
          type: string
      required: [kind, value]
produces:
  - assertion:
      subject: TestValue
      predicate: dependsOnEnv
      object: string
satisfies:
  - REPORT(test.env_dependent)
depends_on:
  - env:TEST_CACHE_ENV_VAR
cost: tiny
reliability: high
latency_ms: 5
implementation:
  type: python
  entry_point: src.tools_generated.test_env_dependent.run
"""
    
    tool_file = contracts_dir / "test_env_dependent.yaml"
    tool_file.write_text(tool_yaml)
    
    # Create implementation
    tools_dir = mvp_dir / "src" / "tools_generated"
    tools_dir.mkdir(parents=True, exist_ok=True)
    
    impl_code = '''"""Test tool that depends on environment variable."""
from typing import Dict, Any

def run(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Tool that returns env var value."""
    import os
    value = inputs.get("value", "")
    env_value = os.environ.get("TEST_CACHE_ENV_VAR", "default")
    return {
        "result": f"{value}_{env_value}",
        "final_answer": f"{value}_{env_value}"
    }
'''
    
    impl_file = tools_dir / "test_env_dependent.py"
    impl_file.write_text(impl_code)
    
    return tool_file, impl_file


def test_real_env_dependency_invalidation():
    """Test cache invalidation with real env-dependent tool."""
    print("\n=== Real Test: Environment Variable Cache Invalidation ===")
    
    # Create test tool
    tool_file, impl_file = create_test_tool_with_env_dependency()
    
    try:
        # Set initial env var
        test_env = "TEST_CACHE_ENV_VAR"
        original_value = os.environ.get(test_env, None)
        os.environ[test_env] = "value1"
        
        obligations = {
            "obligations": [
                {
                    "type": "REPORT",
                    "payload": {
                        "kind": "test.env_dependent",
                        "value": "test"
                    }
                }
            ]
        }
        
        db_path = ".ir/test_cache_real_env.db"
        if Path(db_path).exists():
            # Clear cache
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tool_run")
            conn.commit()
            conn.close()
        
        # Compute contract fingerprint
        from src.core.contract_fingerprint import compute_contract_fingerprint
        import yaml
        contract_data = yaml.safe_load(tool_file.read_text())
        contract_fingerprint = compute_contract_fingerprint(contract_data)
        
        api = MVPAPI(db_path)
        try:
            runs_data = []
            
            # First run
            trace1 = api.execute_obligations(obligations)
            tool_run1 = next((tr for tr in trace1.get("tool_runs", []) if tr.get("tool_name") == "TestTool.EnvDependent"), None)
            cache_info1 = tool_run1.get("cache_info", {}) if tool_run1 else {}
            answer1 = trace1.get("final_answer", "")
            runs_data.append({
                "run": 1,
                "env": cache_info1.get("dependency_snapshot", {}),
                "input_hash": cache_info1.get("input_hash", ""),
                "depends_on_hash": cache_info1.get("depends_on_hash"),
                "cache_key": cache_info1.get("cache_key", ""),
                "cache_hit": tool_run1.get("cache_hit", False) if tool_run1 else False,
                "cache_lookup_reason": tool_run1.get("cache_lookup_reason", "miss_not_found") if tool_run1 else "miss_not_found",
                "executed": not (tool_run1.get("cache_hit", False) if tool_run1 else False),
                "answer": answer1
            })
            print(f"Run 1: executed={runs_data[0]['executed']}, cache_hit={runs_data[0]['cache_hit']}, answer: {answer1}")
            
            # Second run (should cache)
            trace2 = api.execute_obligations(obligations)
            tool_run2 = next((tr for tr in trace2.get("tool_runs", []) if tr.get("tool_name") == "TestTool.EnvDependent"), None)
            cache_info2 = tool_run2.get("cache_info", {}) if tool_run2 else {}
            answer2 = trace2.get("final_answer", "")
            runs_data.append({
                "run": 2,
                "env": cache_info2.get("dependency_snapshot", {}),
                "input_hash": cache_info2.get("input_hash", ""),
                "depends_on_hash": cache_info2.get("depends_on_hash"),
                "cache_key": cache_info2.get("cache_key", ""),
                "cache_hit": tool_run2.get("cache_hit", False) if tool_run2 else False,
                "cache_lookup_reason": tool_run2.get("cache_lookup_reason", "miss_not_found") if tool_run2 else "miss_not_found",
                "executed": not (tool_run2.get("cache_hit", False) if tool_run2 else False),
                "answer": answer2
            })
            print(f"Run 2: executed={runs_data[1]['executed']}, cache_hit={runs_data[1]['cache_hit']}, answer: {answer2}")
            
            assert answer1 == answer2, "Answers should match before env change"
            assert runs_data[1]["cache_hit"], "Run 2 should be a cache hit"
            
            # Change env var
            os.environ[test_env] = "value2"
            print(f"Changed {test_env} from 'value1' to 'value2'")
            
            # Third run (should invalidate cache and re-execute)
            trace3 = api.execute_obligations(obligations)
            tool_run3 = next((tr for tr in trace3.get("tool_runs", []) if tr.get("tool_name") == "TestTool.EnvDependent"), None)
            cache_info3 = tool_run3.get("cache_info", {}) if tool_run3 else {}
            answer3 = trace3.get("final_answer", "")
            runs_data.append({
                "run": 3,
                "env": cache_info3.get("dependency_snapshot", {}),
                "input_hash": cache_info3.get("input_hash", ""),
                "depends_on_hash": cache_info3.get("depends_on_hash"),
                "cache_key": cache_info3.get("cache_key", ""),
                "cache_hit": tool_run3.get("cache_hit", False) if tool_run3 else False,
                "cache_lookup_reason": tool_run3.get("cache_lookup_reason", "miss_not_found") if tool_run3 else "miss_not_found",
                "executed": not (tool_run3.get("cache_hit", False) if tool_run3 else False),
                "answer": answer3
            })
            print(f"Run 3: executed={runs_data[2]['executed']}, cache_hit={runs_data[2]['cache_hit']}, answer: {answer3}")
            
            # Determine why cache invalidated
            cache_invalidated = runs_data[2]["depends_on_hash"] != runs_data[1]["depends_on_hash"]
            cache_key_changed = runs_data[2]["cache_key"] != runs_data[1]["cache_key"]
            
            if cache_invalidated:
                reason = f"depends_on_hash_changed: env:{test_env} ({runs_data[1]['depends_on_hash'][:16]} -> {runs_data[2]['depends_on_hash'][:16]})"
            elif cache_key_changed:
                reason = f"cache_key_changed: {runs_data[1]['cache_key'][:16]} -> {runs_data[2]['cache_key'][:16]}"
            else:
                reason = "unknown"
            
            # Verify cache was invalidated
            assert answer3 != answer1, f"Answer should change after env var change. Got: {answer3}, Expected different from: {answer1}"
            assert runs_data[2]["executed"], "Should have re-executed after env change"
            assert cache_invalidated, "depends_on_hash should have changed"
            
            # Collect verification evidence
            verification_evidence = trace3.get("verification", {}).get("evidence", [])
            evidence_types = list(set(ev.get("check_type", "") for ev in verification_evidence if ev.get("check_type")))
            evidence_passed = sum(1 for ev in verification_evidence if ev.get("comparison_result") == "match")
            evidence_failed = sum(1 for ev in verification_evidence if ev.get("comparison_result") == "mismatch")
            
            print(f"[PASS] Cache correctly invalidated when env var changed")
            print(f"  Answer changed from '{answer1}' to '{answer3}'")
            print(f"  depends_on_hash changed: {runs_data[1]['depends_on_hash'][:16]} -> {runs_data[2]['depends_on_hash'][:16]}")
            
            # Restore original
            if original_value:
                os.environ[test_env] = original_value
            else:
                os.environ.pop(test_env, None)
            
            # Format report in tight, boring format
            return {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "test": "real_cache_invalidation",
                "tool": {
                    "name": "TestTool.EnvDependent",
                    "version": "1.0.0",
                    "contract_fingerprint": contract_fingerprint
                },
                "runs": runs_data,
                "summary": {
                    "cache_invalidated": cache_invalidated,
                    "reason": reason,
                    "verification_evidence": {
                        "count": len(verification_evidence),
                        "types": evidence_types,
                        "passed": evidence_passed,
                        "failed": evidence_failed
                    }
                }
            }
        finally:
            api.close()
    finally:
        # Cleanup test files
        if tool_file.exists():
            tool_file.unlink()
        if impl_file.exists():
            impl_file.unlink()


def run_real_abuse_test():
    """Run the real abuse test."""
    print("=" * 60)
    print("REAL CACHE INVALIDATION ABUSE TEST")
    print("=" * 60)
    
    try:
        result = test_real_env_dependency_invalidation()
        
        # Report is already in the tight format from test function
        report = result
        
        # Save report in project (gitignored)
        reports_dir = mvp_dir / ".reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file = reports_dir / f"cache_invalidation_real_{int(time.time())}.json"
        
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n[REPORT] Saved to: {report_file}")
        print("=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        
        return report
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    run_real_abuse_test()
