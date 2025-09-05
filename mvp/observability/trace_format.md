# Trace Format Specification

## Overview
Every request generates a compact JSON trace containing the complete execution path from user input to final answer.

## Trace Structure

```json
{
  "trace_id": "uuid",
  "timestamp": "2024-01-20T15:30:00Z",
  "user_input": "What's 2+2?",
  "obligations": [...],
  "tool_runs": [...],
  "assertions": [...],
  "verification": {...},
  "final_answer": "4",
  "metrics": {...}
}
```

## Required Fields

### Basic Info
- `trace_id`: Unique identifier for this request
- `timestamp`: When the request started
- `user_input`: Original user question/request

### Execution Path
- `obligations`: Array of obligations created from user input
- `tool_runs`: Array of tool executions with inputs/outputs
- `assertions`: Array of assertions created by tools
- `verification`: Results of verification checks
- `final_answer`: Final natural language response

### Metrics
- `latency_ms`: Total request duration
- `obligation_count`: Number of obligations created
- `tool_run_count`: Number of tools executed
- `verification_passed`: Boolean verification result

## Detailed Field Specifications

### Obligations Array
```json
{
  "obligations": [
    {
      "id": "OB1",
      "type": "REPORT",
      "payload": {"kind": "math", "expr": "2+2"},
      "status": "resolved",
      "created_at": "2024-01-20T15:30:00Z"
    }
  ]
}
```

### Tool Runs Array
```json
{
  "tool_runs": [
    {
      "id": "TR1",
      "tool_name": "EvalMath",
      "inputs": {"expr": "2+2"},
      "outputs": {"result": 4},
      "status": "completed",
      "duration_ms": 5,
      "started_at": "2024-01-20T15:30:00Z",
      "completed_at": "2024-01-20T15:30:00Z"
    }
  ]
}
```

### Assertions Array
```json
{
  "assertions": [
    {
      "id": "A1",
      "subject_id": "E2",
      "predicate": "evaluatesTo",
      "object": "4",
      "confidence": 1.0,
      "source_id": "S1",
      "created_at": "2024-01-20T15:30:00Z"
    }
  ]
}
```

### Verification Object
```json
{
  "verification": {
    "passed": true,
    "method": "recompute",
    "details": "Re-evaluated expression 2+2 = 4",
    "duration_ms": 2
  }
}
```

### Metrics Object
```json
{
  "metrics": {
    "total_latency_ms": 150,
    "obligation_count": 2,
    "tool_run_count": 1,
    "assertion_count": 1,
    "verification_passed": true,
    "escalation_count": 0,
    "clarify_count": 0
  }
}
```

## Example Complete Trace

```json
{
  "trace_id": "req_12345",
  "timestamp": "2024-01-20T15:30:00Z",
  "user_input": "What's 2+2?",
  "obligations": [
    {
      "id": "OB1",
      "type": "REPORT",
      "payload": {"kind": "math", "expr": "2+2"},
      "status": "resolved"
    },
    {
      "id": "OB2", 
      "type": "VERIFY",
      "payload": {"target": "last_answer"},
      "status": "resolved"
    }
  ],
  "tool_runs": [
    {
      "id": "TR1",
      "tool_name": "EvalMath",
      "inputs": {"expr": "2+2"},
      "outputs": {"result": 4},
      "status": "completed",
      "duration_ms": 5
    }
  ],
  "assertions": [
    {
      "id": "A1",
      "subject_id": "E2",
      "predicate": "evaluatesTo", 
      "object": "4",
      "confidence": 1.0,
      "source_id": "S1"
    }
  ],
  "verification": {
    "passed": true,
    "method": "recompute",
    "details": "Re-evaluated expression 2+2 = 4",
    "duration_ms": 2
  },
  "final_answer": "4",
  "metrics": {
    "total_latency_ms": 150,
    "obligation_count": 2,
    "tool_run_count": 1,
    "assertion_count": 1,
    "verification_passed": true,
    "escalation_count": 0,
    "clarify_count": 0
  }
}
```

## Error Cases

### Tool Failure
```json
{
  "tool_runs": [
    {
      "id": "TR1",
      "tool_name": "EvalMath",
      "inputs": {"expr": "2+"},
      "outputs": {"error": "Invalid syntax"},
      "status": "failed",
      "duration_ms": 3,
      "error": "SyntaxError: unexpected EOF while parsing"
    }
  ]
}
```

### Verification Failure
```json
{
  "verification": {
    "passed": false,
    "method": "recompute",
    "details": "Re-evaluation produced different result",
    "duration_ms": 5,
    "error": "Result mismatch: expected 4, got 5"
  }
}
```

### Escalation
```json
{
  "obligations": [
    {
      "id": "OB1",
      "type": "REPORT",
      "payload": {"kind": "unknown"},
      "status": "escalated",
      "escalation_reason": "No tool available for obligation type"
    },
    {
      "id": "OB2",
      "type": "DISCOVER_OP",
      "payload": {"goal": "Handle unknown query type"},
      "status": "active"
    }
  ]
}
```

## Logging Requirements

### Per-Request Logging
- Log complete trace as single JSON object
- Include all timing information
- Capture all errors and escalations
- Store in searchable format (JSON logs)

### Aggregation Metrics
- Success rate by tool
- Average latency by tool
- Obligation resolution rate
- Verification failure rate
- Escalation frequency

### Debugging Support
- Full execution path visible
- Input/output for every tool
- Timing breakdown
- Error context and stack traces
- Source attribution for all assertions
