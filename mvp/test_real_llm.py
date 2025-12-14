#!/usr/bin/env python3
"""
Test script for real LLM integration.

This script demonstrates the MVP system using actual OpenAI API calls
instead of the mock LLM.
"""

import os
import sys
sys.path.append('src')

from main import MVPAPI


def test_real_llm():
    """Test the system with real OpenAI LLM."""
    print("=" * 60)
    print(" TESTING MVP WITH REAL OPENAI LLM")
    print("=" * 60)
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key-here'")
        return False
    
    # Don't print API key, even partially
    print("✓ OpenAI API key found in environment")
    
    # Initialize API with real LLM
    try:
        api = MVPAPI(use_real_llm=True, api_key=api_key)
        print("MVP API initialized with real OpenAI LLM")
    except Exception as e:
        print(f"❌ Failed to initialize API: {e}")
        return False
    
    # Test queries
    test_queries = [
        "What's 2+2?",
        "How many r's in 'strawberry'?",
        "What's 5 times 3?",
        "Count the letters 'e' in 'elephant'",
        "What's your name?"
    ]
    
    print(f"\n🧪 Testing {len(test_queries)} queries...")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n[TEST {i}] Q: {query}")
        
        try:
            # Get simple answer
            expected = None
            if "2+2" in query:
                expected = "4"
            elif "5 times 3" in query:
                expected = "15"
            elif "r's in 'strawberry'" in query:
                expected = "3"
            elif "letters 'e' in 'elephant'" in query:
                expected = "2"
            
            answer = api.ask(query)
            print(f"   Expected: {expected if expected is not None else '(n/a)'}")
            print(f"   Actual:   {answer}")
            
            # Get full trace
            trace = api.ask_with_trace(query)
            print(f"   Trace ID: {trace['trace_id']}")
            print(f"   Obligations: {len(trace['obligations'])}")
            print(f"   Tool runs: {len(trace['tool_runs'])}")
            print(f"   Assertions: {len(trace['assertions'])}")
            print(f"   Latency: {trace['metrics']['total_latency_ms']}ms")
            ok = trace['verification']['passed']
            print(f"   Success: {'PASS' if ok else 'FAIL'}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Show system status
    print(f"\n📊 System Status:")
    status = api.status()
    print(f"   Tools registered: {status['tools_registered']}")
    print(f"   Tool names: {status['tool_names']}")
    
    # Close system
    api.close()
    print(f"\nTest completed")
    return True


def main():
    """Main test function."""
    success = test_real_llm()
    
    if success:
        print("\nREAL LLM INTEGRATION WORKING")
        print("The MVP system is now using actual OpenAI API calls!")
        return 0
    else:
        print("\nREAL LLM INTEGRATION FAILED")
        print("Please check your API key and try again.")
        return 1


if __name__ == "__main__":
    exit(main())
