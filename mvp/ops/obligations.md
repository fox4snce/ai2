# Writing obligations (that work)

An **obligations file** is just JSON shaped like:

```json
{
  "obligations": [
    { "type": "REPORT", "payload": { "kind": "math", "expr": "2+2" } }
  ]
}
```

This is the **deterministic API input** for the engine and the FastAPI endpoint.

## Where the rules live

- **Schema**: `mvp/schemas/obligation.schema.json`
- **Parser**: `mvp/src/core/obligations.py` (`ObligationParser`)
- **Behavior**: `mvp/src/conductor/conductor.py` (tool routing, clarify, missing capabilities)

## The only top-level rule

- Your JSON must contain an **`obligations` array** with **at least 1** item.
- Each item must have:
  - `type`: one of `REPORT | ACHIEVE | MAINTAIN | AVOID | JUSTIFY | SCHEDULE | CLARIFY | VERIFY | DISCOVER_OP`
  - `payload`: an object (shape depends on `type` and `kind`)

## Common working examples (copy/paste)

### REPORT: math

```json
{
  "obligations": [
    { "type": "REPORT", "payload": { "kind": "math", "expr": "(3+2)*4" } }
  ]
}
```

### REPORT: count letters

```json
{
  "obligations": [
    { "type": "REPORT", "payload": { "kind": "count", "letter": "r", "word": "strawberry" } }
  ]
}
```

### REPORT: people query (sample data)

```json
{
  "obligations": [
    {
      "type": "REPORT",
      "payload": {
        "kind": "query.people",
        "filters": [
          { "is_friend": "user" },
          { "city": "Seattle" }
        ]
      }
    }
  ]
}
```

### REPORT: status.name (special-case memory read / CLARIFY)

If the name hasn’t been set yet, this returns `status="clarify"` and `clarify=["name"]` in the trace.

```json
{
  "obligations": [
    { "type": "REPORT", "payload": { "kind": "status.name" } }
  ]
}
```

### ACHIEVE: set status.name (special-case memory write)

```json
{
  "obligations": [
    { "type": "ACHIEVE", "payload": { "state": "status.name", "value": "Jeff" } }
  ]
}
```

### REPORT: logic (deterministic reasoning stub)

```json
{
  "obligations": [
    {
      "type": "REPORT",
      "payload": {
        "kind": "logic",
        "mode": "deduction",
        "query": { "predicate": "grandparentOf", "args": ["Alice", "Cara"] },
        "facts": [
          { "predicate": "parentOf", "args": ["Alice", "Bob"] },
          { "predicate": "parentOf", "args": ["Bob", "Cara"] }
        ],
        "domains": ["kinship"],
        "budgets": { "max_depth": 3, "beam": 4, "time_ms": 100 }
      }
    }
  ]
}
```

### ACHIEVE: plan (deterministic planning stub)

```json
{
  "obligations": [
    {
      "type": "ACHIEVE",
      "payload": {
        "state": "plan",
        "mode": "planning",
        "goal": {
          "predicate": "event.scheduled",
          "args": { "person": "Dana", "time": "2025-09-06T13:00-07:00" }
        },
        "budgets": { "max_depth": 3, "beam": 3, "time_ms": 150 }
      }
    }
  ]
}
```

## What happens if you ask for something unsupported?

If your obligation’s `type`/`kind` has no matching tool contract, the trace will include:

- `missing_capabilities: [...]` (structured)
- `emitted_obligations: [...]` containing a `DISCOVER_OP` with the missing-capability payload

This is what `scripts/toolsmith.py` and `scripts/auto_toolsmith.py` consume.

## Validate before you run

Use:

```powershell
cd mvp
.\.venv\Scripts\python scripts\validate_obligations.py path\to\obligations.json
```


