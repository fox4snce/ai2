#!/usr/bin/env python3
"""
MVP Demo Script

This script demonstrates the Obligations -> Operations architecture
in action with various example queries.
"""

import sys
import os
import json
from datetime import datetime

# Ensure the mvp/ directory is on sys.path so the `src` package is importable
HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from src.main import MVPAPI


def print_separator(title=""):
    """Print a visual separator."""
    if title:
        print(f"\n{'='*60}")
        print(f" {title}")
        print(f"{'='*60}")
    else:
        print("-" * 60)


def print_trace_summary(trace):
    """Print a summary of the trace."""
    print(f"Trace ID: {trace['trace_id']}")
    print(f"User Input: {trace['user_input']}")
    print(f"Final Answer: {trace['final_answer']}")
    print(f"Obligations: {len(trace['obligations'])}")
    print(f"Tool Runs: {len(trace['tool_runs'])}")
    print(f"Assertions: {len(trace['assertions'])}")
    print(f"Verification: {'OK' if trace['verification']['passed'] else 'FAIL'}")
    print(f"Latency: {trace['metrics']['total_latency_ms']}ms")
    print(f"Success Rate: {trace['metrics']['success_rate']:.2%}")


def demo_basic_queries():
    """Demonstrate basic query types."""
    print_separator("BASIC QUERIES DEMO")
    
    api = MVPAPI()
    
    queries = [
        "What's 2+2?",
        "How many r's in 'strawberry'?",
        "List my friends in Seattle",
        "What's your name?"
    ]
    
    for query in queries:
        print(f"\nQ: {query}")
        answer = api.ask(query)
        print(f"A: {answer}")
    
    api.close()


def demo_detailed_traces():
    """Demonstrate detailed trace information."""
    print_separator("DETAILED TRACES DEMO")
    
    api = MVPAPI()
    
    query = "What's 2+2?"
    print(f"Q: {query}")
    
    trace = api.ask_with_trace(query)
    print_trace_summary(trace)
    
    # Show detailed trace
    print(f"\nDetailed Trace:")
    print(json.dumps(trace, indent=2))
    
    api.close()


def demo_system_status():
    """Demonstrate system status."""
    print_separator("SYSTEM STATUS DEMO")
    
    api = MVPAPI()
    
    status = api.status()
    print("System Status:")
    print(json.dumps(status, indent=2))
    
    api.close()


def demo_error_handling():
    """Demonstrate error handling."""
    print_separator("ERROR HANDLING DEMO")
    
    api = MVPAPI()
    
    error_queries = [
        "",  # Empty input
        "What is the meaning of life?",  # Unknown question
        "Please solve world hunger",  # Complex request
    ]
    
    for query in error_queries:
        print(f"\nQ: '{query}'")
        trace = api.ask_with_trace(query)
        print(f"A: {trace['final_answer']}")
        print(f"Verification: {'OK' if trace['verification']['passed'] else 'FAIL'}")
    
    api.close()


def demo_performance():
    """Demonstrate performance metrics."""
    print_separator("PERFORMANCE DEMO")
    
    api = MVPAPI()
    
    queries = [
        "What's 2+2?",
        "How many r's in 'strawberry'?",
        "List my friends in Seattle",
        "What's your name?"
    ]
    
    total_latency = 0
    successful_queries = 0
    
    for query in queries:
        trace = api.ask_with_trace(query)
        latency = trace['metrics']['total_latency_ms']
        success = trace['verification']['passed']
        
        print(f"Query: {query}")
        print(f"  Latency: {latency}ms")
        print(f"  Success: {'OK' if success else 'FAIL'}")
        
        total_latency += latency
        if success:
            successful_queries += 1
    
    print(f"\nPerformance Summary:")
    print(f"  Total Queries: {len(queries)}")
    print(f"  Successful: {successful_queries}")
    print(f"  Success Rate: {successful_queries/len(queries):.2%}")
    print(f"  Average Latency: {total_latency/len(queries):.1f}ms")
    
    api.close()


def main():
    """Run all demos."""
    print_separator("MVP OBLIGATIONS -> OPERATIONS DEMO")
    print("This demo showcases the MVP implementation of the")
    print("Obligations -> Operations architecture.")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Run all demos
        demo_basic_queries()
        demo_detailed_traces()
        demo_system_status()
        demo_error_handling()
        demo_performance()
        
        print_separator("DEMO COMPLETED")
        print("All demos completed successfully!")
        
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
