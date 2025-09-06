# MVP: Obligations → Operations Architecture

This is a minimal viable implementation of the Obligations → Operations architecture described in the playbook. The system separates reasoning (tools) from translation (LLMs) using a structured IR database and obligation-driven execution.

## Architecture Overview

- **IR Database**: Stores ideas as entities, relations, assertions, and events
- **Obligations**: Universal grammar for "what must hold" (REPORT, ACHIEVE, etc.)
- **Tools**: Deterministic operations with contracts (EvalMath, PeopleSQL, etc.)
- **Conductor**: Selects tools to satisfy obligations using policy, not LLM scoring
- **Translators**: LLMs only translate NL ↔ obligations, not solve problems

## Quick Start (Deterministic API)

### 1) Create venv and install minimal runtime deps
```powershell
cd mvp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2) Run the API server
```powershell
python -m src.api
# Server on http://0.0.0.0:8000
```

### 3) Exercise the API (cURL):
```bash
# Math
curl -s -X POST http://127.0.0.1:8000/v1/obligations/execute \
  -H "Content-Type: application/json" \
  -d '{"obligations":[{"type":"REPORT","payload":{"kind":"math","expr":"2+2"}}]}'

# Count letters
curl -s -X POST http://127.0.0.1:8000/v1/obligations/execute \
  -H "Content-Type: application/json" \
  -d '{"obligations":[{"type":"REPORT","payload":{"kind":"count","letter":"r","word":"strawberry"}}]}'

# Clarify name
curl -s -X POST http://127.0.0.1:8000/v1/obligations/execute \
  -H "Content-Type: application/json" \
  -d '{"obligations":[{"type":"REPORT","payload":{"kind":"status.name"}}]}'
```

### 4) Deterministic in-process smoke (no server):
```powershell
python scripts/smoke_api.py
```

### 5) API tests (spawns a server in the test)
```powershell
python -m pytest tests/test_api.py -q
```

### 4. Request Flow
1. User: "What's 2+2?"
2. Translator-In: `REPORT(math: "2+2")` + `VERIFY(target: "last_answer")`
3. Conductor: Selects `EvalMath` tool
4. Tool: Evaluates → `Assertion(Expression "2+2" evaluatesTo 4)`
5. Verify: Recomputes → passes
6. Translator-Out: "4"

## File Structure

```
mvp/
├── db/
│   ├── schema.sql          # Core IR tables
│   └── examples.sql        # Sample data
├── contracts/
│   ├── obligations.schema.json  # Obligation grammar
│   ├── tool.schema.json          # Tool contract schema
│   └── tools/
│       ├── evalmath.yaml
│       ├── textops_countletters.yaml
│       ├── people_sql.yaml
│       └── adapters/
│           └── people_sql_adapter.yaml
├── conductor/
│   ├── plan.md            # Conductor algorithm
│   └── policy.md           # Tool selection policy
├── prompts/
│   ├── translator_in.md    # NL → obligations prompt
│   └── translator_out.md   # Assertions → NL prompt
├── ops/
│   ├── evalmath.md         # Math tool implementation
│   ├── textops_countletters.md
│   └── people_sql.md
├── observability/
│   └── trace_format.md     # Request tracing spec
├── scripts/
│   └── smoke_api.py        # In-process API smoke test
├── src/
│   ├── api.py              # FastAPI app (deterministic obligations API)
│   └── ...                 # engine code (conductor/core/tools/...)
├── tests/
│   └── test_api.py         # Live API endpoint tests
└── README.md
```

## Core Components

### Obligation Types
- `REPORT(query)` - Produce answers
- `ACHIEVE(state)` - Make states true
- `MAINTAIN(pred)` - Keep predicates true
- `AVOID(pred)` - Keep predicates false
- `JUSTIFY(claim)` - Show provenance
- `SCHEDULE(event,time)` - Bind to time
- `CLARIFY(slot)` - Ask for missing info
- `VERIFY(ans)` - Check before sending
- `DISCOVER_OP(goal)` - Find/create tools

### Tool Contracts
Each tool declares:
- **Inputs**: What it consumes (with schema)
- **Outputs**: What it produces (assertions, events)
- **Satisfies**: Which obligations it can fulfill
- **Pre/Postconditions**: Truth conditions
- **Cost/Reliability**: For selection policy

### Conductor Policy
Tool selection by priority:
1. **Reliability**: high > medium > low
2. **Cost**: tiny > low > medium > high  
3. **Latency**: lower is better
4. **Tiebreak**: alphabetical by name

## Example Traces

### Math Query
```json
{
  "user_input": "What's 2+2?",
  "obligations": [
    {"type": "REPORT", "payload": {"kind": "math", "expr": "2+2"}},
    {"type": "VERIFY", "payload": {"target": "last_answer"}}
  ],
  "tool_runs": [
    {"tool_name": "EvalMath", "inputs": {"expr": "2+2"}, "outputs": {"result": 4}}
  ],
  "assertions": [
    {"subject_id": "E2", "predicate": "evaluatesTo", "object": "4", "confidence": 1.0}
  ],
  "verification": {"passed": true, "method": "recompute"},
  "final_answer": "4"
}
```

### People Query
```json
{
  "user_input": "List friends in Seattle",
  "obligations": [
    {"type": "REPORT", "payload": {"kind": "query.people", "filters": [{"is_friend": "user"}, {"city": "Seattle"}]}}
  ],
  "tool_runs": [
    {"tool_name": "PeopleSQL", "inputs": {"filters": [...]}, "outputs": {"people": [...]}}
  ],
  "assertions": [
    {"subject_id": "E3", "predicate": "matchesQuery", "object": "true"}
  ],
  "final_answer": "Alice Smith, Bob Johnson (per your contacts database)"
}
```

## API Status Mapping

- 200: resolved | clarify
- 400: schema/validation error (e.g., empty obligations)
- 422: no tool can satisfy (unknown/unsupported obligation)
- 500: tool crash / unexpected error

## Key Principles

1. **LLMs ≠ Universal Solvers**: They're translators between NL and structure
2. **Reasoning Lives in Tools**: Math, search, planning, control, etc.
3. **IR is Memory**: Facts live outside prompts in a database
4. **Obligations Drive Behavior**: "What must hold" determines "how we do it"
5. **Verify Before Answer**: Check answers before they leave the system
6. **Trace Everything**: Every answer has a complete provenance trail

## Next Steps

1. **Implement Core**: Database, conductor, basic tools
2. **Add Tools**: More domains by adding tool contracts
3. **Tighten Adapters**: Better IR ↔ tool parameter mapping
4. **Scale Verification**: More sophisticated checking
5. **Tool Discovery**: Automated tool creation for missing capabilities

The conductor, IR, and verify loop stay the same as you add tools and tighten adapters.

