# Core Guarantees

*Quick reference for 2am debugging sessions*

## What the system promises

### Deterministic execution
Same obligations + same inputs → same outputs (bit-for-bit). No randomness, no "sometimes it works."

### Cache reuse across runs
If you run the same obligations twice, the second run uses cached tool outputs. Check `cache_hit: true` in tool_runs.

### No hidden LLM calls during execution
LLMs only translate at the edges (NL → obligations, assertions → NL). The conductor never asks an LLM "which tool should I use?" or "is this answer correct?"

### All decisions traceable
Every trace shows: which tools ran, why they were chosen, what they produced, and where results came from. No black boxes.

## What the system does NOT promise

### No natural language understanding
It doesn't "understand" language. It translates NL to obligations using schemas. If the translator fails, you get a structured error, not a hallucination.

### No creativity
It doesn't invent solutions. It executes tools that exist. If no tool can satisfy an obligation, you get `missing_capability`, not a made-up answer.

### No implicit reasoning
It doesn't "figure things out" on its own. Reasoning lives in tools (math, logic, planning). The conductor just routes obligations to tools.

### No magic
Everything is explicit: tool contracts, cache keys, verification evidence, budgets. If something happens, you can point to why.

## Where intelligence actually lives

### Tool contracts
Tools declare what they can do, what they need, and what they produce. The conductor matches obligations to tools by contract, not by guessing.

### Planner constraints
The planner (Reasoning.Core) respects budgets (max_depth, beam, time_ms) and schema constraints. It doesn't make up steps that can't execute.

### Cached reuse
Deterministic tools cache their outputs. The cache key includes: tool_name + inputs + version + dependencies (files, env vars, DB state).

### Skills (workflows)
Reusable workflow patterns stored as YAML. They're just obligation templates, not magic workflows.

## How to tell if it's lying

### Cache hits > 0 on second run
Run the same obligations twice. If `cache_hit: true` appears in tool_runs on run #2, caching works. If not, something's wrong.

### Same obligations → same trace shape
Identical obligations should produce identical trace structures (same tools, same order, same outputs). If traces differ, something non-deterministic snuck in.

### Budget violations throw explicit failures
If you set `max_tool_runs: 1` and try to run 2 tools, you get a structured error with the budget that was exceeded. Not a crash, not silence.
