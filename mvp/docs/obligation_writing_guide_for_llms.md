# Obligation Writing Guide for LLMs

**Purpose**: This document explains how to translate natural language into valid obligation JSON. Use this as your reference when generating obligations.

## Core Structure

All obligations must follow this structure:
```json
{
  "obligations": [
    {
      "type": "OBLIGATION_TYPE",
      "payload": { /* type-specific fields */ }
    }
  ]
}
```

**Rules**:
- Always return valid JSON
- The `obligations` array must have at least 1 item
- Each obligation must have `type` and `payload`
- Use exact field names from the schema (case-sensitive)
- Do NOT solve problems - only translate to obligations

## Obligation Types

### 1. REPORT - Produce an answer/explanation

**Purpose**: Request information or computation.

**Payload structure**:
- `kind` (required): One of: `math`, `count`, `status`, `logic`, `plan`, `query.people`, `query.documents`, `schedule`, `time`
- Additional fields depend on `kind` (see examples below)

#### REPORT: math
**When to use**: Mathematical expressions, calculations
```json
{
  "type": "REPORT",
  "payload": {
    "kind": "math",
    "expr": "2+2"
  }
}
```
- `expr` (required): Mathematical expression as string

#### REPORT: count
**When to use**: Count occurrences of a letter in a word
```json
{
  "type": "REPORT",
  "payload": {
    "kind": "count",
    "letter": "r",
    "word": "strawberry"
  }
}
```
- `letter` (required): Single character to count
- `word` (required): Word to search in

#### REPORT: status
**When to use**: Query system status or memory fields
```json
{
  "type": "REPORT",
  "payload": {
    "kind": "status",
    "field": "name"
  }
}
```
- `field` (required): Status field name (e.g., "name")

#### REPORT: time
**When to use**: Current time queries
```json
{
  "type": "REPORT",
  "payload": {
    "kind": "time"
  }
}
```

#### REPORT: query.people
**When to use**: Query person/contact database
```json
{
  "type": "REPORT",
  "payload": {
    "kind": "query.people",
    "filters": [
      {"is_friend": "user"},
      {"city": "Seattle"}
    ]
  }
}
```
- `filters` (required): Array of filter objects (key-value pairs)

#### REPORT: query.documents
**When to use**: Query document database
```json
{
  "type": "REPORT",
  "payload": {
    "kind": "query.documents",
    "filters": [
      {"author": "Alice"},
      {"date": "2025-01-01"}
    ]
  }
}
```
- `filters` (required): Array of filter objects

#### REPORT: logic
**When to use**: Logical reasoning queries
```json
{
  "type": "REPORT",
  "payload": {
    "kind": "logic",
    "mode": "deduction",
    "query": {
      "predicate": "grandparentOf",
      "args": ["Alice", "Cara"]
    },
    "facts": [
      {"predicate": "parentOf", "args": ["Alice", "Bob"]},
      {"predicate": "parentOf", "args": ["Bob", "Cara"]}
    ],
    "domains": ["kinship"],
    "budgets": {
      "max_depth": 3,
      "beam": 4,
      "time_ms": 100
    }
  }
}
```
- `mode` (optional): Reasoning mode (e.g., "deduction")
- `query` (optional): Query object with `predicate` and `args`
- `facts` (optional): Array of fact objects
- `domains` (optional): Array of domain strings
- `budgets` (optional): Budget constraints object

#### REPORT: plan
**When to use**: Planning queries
```json
{
  "type": "REPORT",
  "payload": {
    "kind": "plan",
    "goal": {
      "predicate": "event.scheduled",
      "args": {"person": "Dana", "time": "2025-09-06T13:00-07:00"}
    },
    "budgets": {
      "max_depth": 3,
      "beam": 3,
      "time_ms": 150
    }
  }
}
```
- `goal` (optional): Goal object
- `budgets` (optional): Budget constraints

#### REPORT: schedule
**When to use**: Schedule queries
```json
{
  "type": "REPORT",
  "payload": {
    "kind": "schedule",
    "filters": [
      {"date": "2025-01-15"}
    ]
  }
}
```
- `filters` (optional): Array of filter objects

---

### 2. ACHIEVE - Make a state true

**Purpose**: Change system state or achieve a goal.

**Payload structure**:
- `state` (required): State identifier string
- `value` (optional): Value to set
- `goal` (optional): Goal object
- `mode` (optional): Mode string (e.g., "planning")
- `budgets` (optional): Budget constraints object

#### ACHIEVE: Set status field
```json
{
  "type": "ACHIEVE",
  "payload": {
    "state": "status.name",
    "value": "Jeff"
  }
}
```

#### ACHIEVE: Planning mode
```json
{
  "type": "ACHIEVE",
  "payload": {
    "state": "plan",
    "mode": "planning",
    "goal": {
      "predicate": "event.scheduled",
      "args": {"person": "Dana", "time": "2025-09-06T13:00-07:00"}
    },
    "budgets": {
      "max_depth": 3,
      "beam": 3,
      "time_ms": 150
    }
  }
}
```

---

### 3. MAINTAIN - Keep a predicate true

**Purpose**: Maintain a condition continuously.

**Payload structure**:
- `pred` (required): Predicate name string
- `args` (optional): Arguments object
- `duration` (optional): Duration string

```json
{
  "type": "MAINTAIN",
  "payload": {
    "pred": "ball.within_radius",
    "args": {"r": 0.1}
  }
}
```

---

### 4. AVOID - Keep a predicate false

**Purpose**: Prevent a condition from becoming true.

**Payload structure**:
- `pred` (required): Predicate name string
- `args` (optional): Arguments object
- `duration` (optional): Duration string

```json
{
  "type": "AVOID",
  "payload": {
    "pred": "ball.fallen",
    "args": {}
  }
}
```

---

### 5. JUSTIFY - Show reasons/provenance

**Purpose**: Provide evidence or justification for a claim.

**Payload structure**:
- `claim` (required): Claim string
- `evidence` (optional): Array of evidence objects
- `confidence` (optional): Number between 0 and 1

```json
{
  "type": "JUSTIFY",
  "payload": {
    "claim": "The answer is 4",
    "evidence": [
      {"source": "EvalMath", "method": "computation"}
    ],
    "confidence": 1.0
  }
}
```

---

### 6. SCHEDULE - Bind an action to time

**Purpose**: Schedule an event or action.

**Payload structure**:
- `event` (required): Event object
- `time` (required): Time string (ISO 8601 format)
- `timezone` (optional): Timezone string

```json
{
  "type": "SCHEDULE",
  "payload": {
    "event": {
      "type": "meeting",
      "participants": ["Alice", "Bob"]
    },
    "time": "2025-09-06T13:00:00-07:00",
    "timezone": "America/Los_Angeles"
  }
}
```

---

### 7. CLARIFY - Ask for missing info

**Purpose**: Request clarification when information is missing.

**Payload structure**:
- `slot` (required): Slot name string
- `context` (optional): Context string
- `options` (optional): Array of option strings

```json
{
  "type": "CLARIFY",
  "payload": {
    "slot": "person_name",
    "context": "Which person do you mean?",
    "options": ["Alice", "Bob", "Charlie"]
  }
}
```

---

### 8. VERIFY - Check before sending

**Purpose**: Verify an answer before returning it.

**Payload structure**:
- `target` (required): Target string (usually "last_answer")
- `method` (optional): Verification method string
- `threshold` (optional): Confidence threshold (0-1)

```json
{
  "type": "VERIFY",
  "payload": {
    "target": "last_answer"
  }
}
```

**Common pattern**: Add VERIFY after REPORT for factual answers:
```json
{
  "obligations": [
    {
      "type": "REPORT",
      "payload": {
        "kind": "math",
        "expr": "2+2"
      }
    },
    {
      "type": "VERIFY",
      "payload": {
        "target": "last_answer"
      }
    }
  ]
}
```

---

### 9. DISCOVER_OP - Find or draft a tool

**Purpose**: Request tool discovery when no tool can satisfy an obligation.

**Payload structure**:
- `goal` (required): Goal string or object
- `domain` (optional): Domain string
- `constraints` (optional): Constraints object

```json
{
  "type": "DISCOVER_OP",
  "payload": {
    "goal": "normalize email addresses",
    "domain": "text_processing",
    "constraints": {
      "cost": "low",
      "reliability": "high"
    }
  }
}
```

---

## Common Patterns

### Pattern 1: Simple query with verification
```json
{
  "obligations": [
    {
      "type": "REPORT",
      "payload": {
        "kind": "math",
        "expr": "2+2"
      }
    },
    {
      "type": "VERIFY",
      "payload": {
        "target": "last_answer"
      }
    }
  ]
}
```

### Pattern 2: Query with clarification
```json
{
  "obligations": [
    {
      "type": "REPORT",
      "payload": {
        "kind": "query.people",
        "filters": [
          {"name": "Dana"}
        ]
      }
    },
    {
      "type": "CLARIFY",
      "payload": {
        "slot": "person",
        "context": "Multiple people named Dana found"
      }
    }
  ]
}
```

### Pattern 3: State change
```json
{
  "obligations": [
    {
      "type": "ACHIEVE",
      "payload": {
        "state": "status.name",
        "value": "Alice"
      }
    }
  ]
}
```

---

## Error Handling

### Missing Information
If the input is ambiguous or missing required information, use CLARIFY:
```json
{
  "obligations": [
    {
      "type": "CLARIFY",
      "payload": {
        "slot": "missing_information",
        "context": "Need more details to proceed"
      }
    }
  ]
}
```

### Unknown Capability
If the request requires a capability that doesn't exist, use DISCOVER_OP:
```json
{
  "obligations": [
    {
      "type": "DISCOVER_OP",
      "payload": {
        "goal": "process image files",
        "domain": "image_processing"
      }
    }
  ]
}
```

---

## Validation Checklist

Before returning obligations, verify:

1. ✅ JSON is valid and parseable
2. ✅ `obligations` array exists and has at least 1 item
3. ✅ Each obligation has `type` and `payload`
4. ✅ `type` is one of the allowed values (case-sensitive)
5. ✅ `payload` contains required fields for the obligation type
6. ✅ Field names match schema exactly (case-sensitive)
7. ✅ No extra fields beyond what's allowed in the schema
8. ✅ For REPORT, `kind` is one of the allowed values
9. ✅ Arrays are actual arrays, objects are actual objects
10. ✅ String values are properly quoted

---

## Schema Reference

The authoritative schema is at: `mvp/schemas/obligation.schema.json`

When in doubt, refer to the schema for exact field requirements and allowed values.

---

## Examples by Use Case

### "What's 2+2?"
```json
{
  "obligations": [
    {"type": "REPORT", "payload": {"kind": "math", "expr": "2+2"}},
    {"type": "VERIFY", "payload": {"target": "last_answer"}}
  ]
}
```

### "List my friends in Seattle"
```json
{
  "obligations": [
    {
      "type": "REPORT",
      "payload": {
        "kind": "query.people",
        "filters": [
          {"is_friend": "user"},
          {"city": "Seattle"}
        ]
      }
    }
  ]
}
```

### "How many r's in 'strawberry'?"
```json
{
  "obligations": [
    {
      "type": "REPORT",
      "payload": {
        "kind": "count",
        "letter": "r",
        "word": "strawberry"
      }
    }
  ]
}
```

### "What's your name?"
```json
{
  "obligations": [
    {
      "type": "REPORT",
      "payload": {
        "kind": "status",
        "field": "name"
      }
    }
  ]
}
```

### "Set my name to Alice"
```json
{
  "obligations": [
    {
      "type": "ACHIEVE",
      "payload": {
        "state": "status.name",
        "value": "Alice"
      }
    }
  ]
}
```

### "Keep the ball centered"
```json
{
  "obligations": [
    {
      "type": "MAINTAIN",
      "payload": {
        "pred": "ball.centered",
        "args": {}
      }
    }
  ]
}
```

---

## Important Notes

1. **You are a translator, not a solver**: Your job is to convert NL to obligations, not to solve problems.

2. **Use exact field names**: The schema is strict - use `kind` not `type` in REPORT payloads, `pred` not `predicate` in MAINTAIN/AVOID, etc.

3. **Include VERIFY for factual answers**: When the user asks a factual question, add a VERIFY obligation after the REPORT.

4. **One obligation per core request**: Don't over-complicate. Most simple requests map to one REPORT obligation.

5. **When in doubt, use CLARIFY**: If information is missing or ambiguous, create a CLARIFY obligation rather than guessing.

6. **Validate your JSON**: Before returning, ensure your JSON is valid and matches the schema structure.
