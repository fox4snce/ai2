"""
Adult demo: workflow.email_domains showing all four pillars in one run:
1. Extract emails
2. Branch if none
3. Normalize batch
4. Count distinct domains with denylist
5. Choose strict extractor only when constrained
6. Cache makes re-run cheap
"""

import json
from src.main import MVPAPI


def test_workflow_email_domains_adult_demo():
    """Run the adult demo showing all four properties."""
    import os
    import sqlite3
    from pathlib import Path
    
    # Use persistent DB to show caching across runs
    db_path = ".ir/test_adult_demo.db"
    
    # Clear cache before first run to ensure clean state
    # (Delete tool_run entries to clear cache, but keep other data)
    if Path(db_path).exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tool_run")
        conn.commit()
        conn.close()
        print("Cleared tool_run cache for fresh start")
    
    api = MVPAPI(db_path)
    try:
        obligations = json.loads(
            open("schemas/obligations.workflow_email_domains_adult_demo.json", "r", encoding="utf-8-sig").read()
        )
        
        # First run: should execute all tools
        trace1 = api.execute_obligations(obligations)
        print(f"\n=== First Run Status: {trace1.get('status')} ===")
        tool_runs1 = trace1.get("tool_runs", [])
        tools1 = [tr.get("tool_name") for tr in tool_runs1]
        print(f"Tools executed: {tools1}")
        
        # Count actual tool executions (non-cached)
        cache_hits1 = [tr for tr in tool_runs1 if tr.get("cache_hit", False)]
        actual_executions1 = len(tool_runs1) - len(cache_hits1)
        print(f"Actual tool executions (non-cached): {actual_executions1}")
        print(f"Cache hits: {len(cache_hits1)}")
        
        if trace1.get("status") != "resolved":
            print(f"Error details: {trace1.get('error')}")
            print(f"Trace: {json.dumps(trace1, indent=2, default=str)}")
        assert trace1.get("status") == "resolved"
        assert "EmailOps.ExtractStrict" in tools1  # Constraint forces strict
        assert "Normalize.EmailsBatch" in tools1
        assert "EmailOps.CountDistinctDomains" in tools1
        # First run should have NO cache hits
        assert len(cache_hits1) == 0, f"First run should have no cache hits, but found {len(cache_hits1)}"
        
        # Second run: should hit cache for deterministic tools
        trace2 = api.execute_obligations(obligations)
        print(f"\n=== Second Run Status: {trace2.get('status')} ===")
        tool_runs2 = trace2.get("tool_runs", [])
        tools2 = [tr.get("tool_name") for tr in tool_runs2]
        print(f"Tools in trace: {tools2}")
        
        # Count cache hits and actual executions
        cache_hits2 = [tr for tr in tool_runs2 if tr.get("cache_hit", False)]
        actual_executions2 = len(tool_runs2) - len(cache_hits2)
        print(f"Actual tool executions (non-cached): {actual_executions2}")
        print(f"Cache hits: {len(cache_hits2)}")
        
        # Show which tools were cached
        cached_tools = [tr.get("tool_name") for tr in cache_hits2]
        if cached_tools:
            print(f"Cached tools: {cached_tools}")
        
        assert trace2.get("status") == "resolved"
        
        # CACHE BEHAVIOR VERIFICATION:
        # Second run should have fewer actual executions (more cache hits)
        assert actual_executions2 < actual_executions1, (
            f"Second run should have fewer actual executions. "
            f"Run 1: {actual_executions1}, Run 2: {actual_executions2}"
        )
        
        # At least some tools should be cached (deterministic tools like EmailOps, Normalize)
        deterministic_tools = ["EmailOps.ExtractStrict", "Normalize.EmailsBatch", "EmailOps.CountDistinctDomains"]
        cached_deterministic = [t for t in cached_tools if t in deterministic_tools]
        assert len(cached_deterministic) > 0, (
            f"Expected at least one deterministic tool to be cached. "
            f"Cached tools: {cached_tools}, Expected: {deterministic_tools}"
        )
        
        # Verify cache hits have near-zero duration
        for tr in cache_hits2:
            duration = tr.get("duration_ms", 999)
            assert duration < 10, (
                f"Cache hit for {tr.get('tool_name')} should have near-zero duration, "
                f"but got {duration}ms"
            )
        
        # Verify denylist was enforced (same as before)
        count_tool_runs = [tr for tr in tool_runs2 if tr.get("tool_name") == "EmailOps.CountDistinctDomains"]
        if count_tool_runs:
            outputs = count_tool_runs[0].get("outputs", {})
            domains = outputs.get("distinct_domains", [])
            assert "example.com" not in domains, "Denylist not enforced"
        
        print(f"\n[PASS] Cache verification passed:")
        print(f"  - Run 1: {actual_executions1} executions, {len(cache_hits1)} cache hits")
        print(f"  - Run 2: {actual_executions2} executions, {len(cache_hits2)} cache hits")
        print(f"  - Cached deterministic tools: {cached_deterministic}")
        
    finally:
        api.close()


if __name__ == "__main__":
    test_workflow_email_domains_adult_demo()
    print("Adult demo passed!")

