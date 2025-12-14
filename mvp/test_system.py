#!/usr/bin/env python3
"""
Simple test to demonstrate the MVP system working correctly.
"""

import sys
sys.path.append('src')

from main import MVPAPI


def test_math_query():
    """Test a simple math query."""
    test_name = "Math: What's 2+2?"
    expected_answer = "4"
    print(f"\n[TEST] {test_name}")
    
    # Load a minimal registry with only EvalMath and CountLetters
    api = MVPAPI()
    trace = api.execute_obligations({
        "obligations": [
            {"type": "REPORT", "payload": {"kind": "math", "expr": "2+2"}}
        ]
    })
    actual_answer = trace.get('final_answer')
    
    # Core signals
    evalmath_used = any(tr.get('tool_name') == 'EvalMath' for tr in trace['tool_runs'])
    math_assertion = any(a['predicate'] == 'evaluatesTo' and a['object'] == expected_answer for a in trace['assertions'])
    
    # Report
    print(f"  Expected: {expected_answer}")
    print(f"  Actual:   {actual_answer}")
    print(f"  Tool:     EvalMath used = {evalmath_used}")
    print(f"  Assert:   evaluatesTo = {math_assertion}")
    print(f"  TraceID:  {trace['trace_id']}")
    
    api.close()
    # Consider test passed if tool + assertion are correct, even if VERIFY suppresses final phrasing
    return evalmath_used and math_assertion and actual_answer == expected_answer


def test_counting_query():
    """Test a counting query."""
    test_name = "Count: r in 'strawberry'"
    expected_answer = "3"
    print(f"\n[TEST] {test_name}")
    
    api = MVPAPI()
    trace = api.execute_obligations({
        "obligations": [
            {"type": "REPORT", "payload": {"kind": "count", "letter": "r", "word": "strawberry"}}
        ]
    })
    actual_answer = trace.get('final_answer')
    
    countletters_used = any(tr.get('tool_name') == 'TextOps.CountLetters' for tr in trace['tool_runs'])
    count_assertion = any(a['predicate'] == 'containsLetterCount' and a['object'] == expected_answer for a in trace['assertions'])
    
    print(f"  Expected: {expected_answer}")
    print(f"  Actual:   {actual_answer}")
    print(f"  Tool:     TextOps.CountLetters used = {countletters_used}")
    print(f"  Assert:   containsLetterCount = {count_assertion}")
    print(f"  TraceID:  {trace['trace_id']}")
    
    api.close()
    return countletters_used and count_assertion and actual_answer == expected_answer


def main():
    """Run the tests."""
    print("=" * 60)
    print(" MVP SYSTEM FUNCTIONALITY TEST")
    print("=" * 60)
    
    # Test math query
    math_success = test_math_query()
    
    # Test counting query  
    count_success = test_counting_query()
    
    print("\n" + "=" * 60)
    print(" TEST RESULTS")
    print("=" * 60)
    def mark(ok: bool) -> str:
        return "PASS" if ok else "FAIL"
    print(f"- Math query:     {mark(math_success)}")
    print(f"- Counting query: {mark(count_success)}")
    
    if math_success and count_success:
        print("\nALL TESTS PASSED")
        print("The MVP Obligations -> Operations system is working correctly!")
        return 0
    else:
        print("\nSOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
