# Tool Selection Policy

## Selection Criteria (in priority order)

### 1. Reliability Score
- **high**: Tool has deterministic behavior, well-tested
- **medium**: Tool generally reliable but may have edge cases
- **low**: Tool is experimental or has known issues

### 2. Cost Score
- **tiny**: Minimal computational cost (e.g., simple math)
- **low**: Low cost operations (e.g., database queries)
- **medium**: Moderate cost (e.g., API calls)
- **high**: Expensive operations (e.g., ML inference)

### 3. Latency Score
- Lower latency is preferred
- Measured in milliseconds
- Used for tiebreaking when reliability and cost are equal

### 4. Deterministic Tiebreak
- Alphabetical by tool name
- Ensures consistent selection across runs

## Selection Algorithm

```python
def select_tool(obligation, candidates):
    # Filter candidates that can satisfy the obligation
    satisfiable = [t for t in candidates if obligation.type in t.satisfies]
    
    if not satisfiable:
        return None  # Will trigger DISCOVER_OP
    
    # Sort by selection criteria
    def tool_score(tool):
        reliability_score = {"high": 3, "medium": 2, "low": 1}[tool.reliability]
        cost_score = {"tiny": 4, "low": 3, "medium": 2, "high": 1}[tool.cost]
        latency_score = 1000 / max(tool.latency_ms, 1)  # Higher is better
        
        return (reliability_score, cost_score, latency_score, tool.name)
    
    return max(satisfiable, key=tool_score)
```

## Input Satisfaction Check

Before selecting a tool, verify inputs are available:

```python
def check_inputs_satisfiable(tool, obligation, ir_db):
    for input_spec in tool.consumes:
        if not ir_db.has_data_for(input_spec.kind, obligation.payload):
            return False, f"Missing input: {input_spec.kind}"
    return True, None
```

## Postcondition Verification

After tool execution, verify postconditions:

```python
def verify_postconditions(tool, outputs, ir_db):
    for postcondition in tool.postconditions:
        if not evaluate_postcondition(postcondition, outputs, ir_db):
            return False, f"Postcondition failed: {postcondition}"
    return True, None
```

## Escalation Policy

When tool selection or execution fails:

1. **Missing inputs**: Create CLARIFY obligation
2. **No suitable tools**: Create DISCOVER_OP obligation  
3. **Postcondition failure**: Try next candidate tool
4. **All candidates failed**: Create JUSTIFY(failure) obligation

## Examples

### Math Query
- Obligation: `REPORT(query.math)`
- Candidates: `EvalMath` (reliability: high, cost: tiny, latency: 5ms)
- Selection: `EvalMath` (only candidate, satisfies requirement)

### People Query  
- Obligation: `REPORT(query.people)`
- Candidates: `PeopleSQL` (reliability: high, cost: low, latency: 50ms)
- Selection: `PeopleSQL` (only candidate, satisfies requirement)

### Complex Query (future)
- Obligation: `REPORT(query.complex)`
- Candidates: `SimpleTool` (reliability: medium), `ComplexTool` (reliability: high)
- Selection: `ComplexTool` (higher reliability wins)
