# Conductor Algorithm Notes

## Overview
The Conductor is a thin policy engine that orchestrates obligation satisfaction through tool selection and execution.

## Core Principles
- **No LLM scoring**: Uses set inclusion, constraints, and postcondition checks
- **Deterministic selection**: Reliability > cost > latency (with deterministic tiebreaking)
- **Fail-fast verification**: Check postconditions immediately after tool execution
- **Escalation handling**: When tools fail, escalate to alternatives or create meta-obligations

## Main Loops

### 1. Top-level Request Loop
```
1. Log event: user_utterance
2. Translator-In → obligations JSON (validate against schema)
3. Insert obligations into IR DB
4. For each obligation:
   - Run Plan Loop
5. If any REPORT produced → run VERIFY pass
6. Translator-Out → NL answer
7. Log tool runs, assertions, and final response
```

### 2. Plan Loop (per obligation)
```
1. Gather candidate tools: tool.satisfies ⊇ obligation.type
2. Check inputs satisfiable from IR (or emit CLARIFY)
3. Pick by policy: reliability > cost > latency (deterministic tiebreak)
4. Run tool; write outputs (assertion, event, source)
5. Check postconditions → resolve or escalate to next candidate
6. If no tool resolves → create DISCOVER_OP (defer) or JUSTIFY(failure)
```

### 3. Verify Loop (before reply)
```
- For math/DB/rules: re-evaluate deterministically
- For facts: cross-check against IR (existence, non-contradiction, provenance)
- Fail → replace with uncertainty message + JUSTIFY/CLARIFY
```

## Tool Selection Policy

### Priority Order
1. **Reliability**: high > medium > low
2. **Cost**: tiny > low > medium > high
3. **Latency**: lower is better
4. **Deterministic tiebreak**: alphabetical by tool name

### Input Satisfaction Check
- Verify all required inputs are available in IR
- Check preconditions are met
- If missing → emit CLARIFY obligation

### Postcondition Verification
- Run deterministic checks after tool execution
- If postconditions fail → escalate to next candidate tool
- If all candidates fail → create DISCOVER_OP or JUSTIFY(failure)

## Error Handling

### Escalation Path
1. Try next candidate tool (if available)
2. Create CLARIFY obligation (if missing inputs)
3. Create DISCOVER_OP obligation (if no tools available)
4. Create JUSTIFY(failure) obligation (if all attempts fail)

### Verification Failures
- Replace answer with uncertainty message
- Add JUSTIFY/CLARIFY obligations
- Log failure for debugging

## State Management
- All state lives in IR DB (not in conductor memory)
- Each tool run creates: assertion, event, source records
- Obligations track status: active → resolved/failed/escalated
- Tool runs track: inputs, outputs, status, duration
