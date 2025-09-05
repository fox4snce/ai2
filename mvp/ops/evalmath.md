# EvalMath Tool Implementation

## Purpose
Evaluates mathematical expressions deterministically and safely.

## Input/Output Contract
- **Input**: `{"expr": "2+2"}` (string expression)
- **Output**: `{"result": 4}` (numeric result)
- **Assertion**: `(Expression "2+2" evaluatesTo 4)`

## Implementation Details

### Safety Constraints
- Only allow basic arithmetic: +, -, *, /, **, ()
- No function calls (sin, cos, etc.)
- No variable references
- No file system access
- No external API calls

### Preconditions
- Expression parses as valid Python arithmetic
- No division by zero
- Result is finite (not NaN or infinity)

### Postconditions
- Result is a number (int or float)
- Result matches direct Python evaluation
- No side effects

### Error Handling
- Invalid syntax → return error with explanation
- Division by zero → return error
- Overflow → return error
- Invalid characters → return error

## Example Usage

```python
def evaluate(expr: str) -> dict:
    """
    Evaluate a mathematical expression safely.
    
    Args:
        expr: Mathematical expression as string
        
    Returns:
        dict: {"result": number} or {"error": "message"}
    """
    try:
        # Validate expression contains only safe characters
        allowed_chars = set('0123456789+-*/().eE ')
        if not all(c in allowed_chars for c in expr):
            return {"error": "Invalid characters in expression"}
        
        # Evaluate using Python's built-in eval (safe for arithmetic)
        result = eval(expr)
        
        # Check for valid numeric result
        if not isinstance(result, (int, float)):
            return {"error": "Expression must evaluate to a number"}
        
        if not math.isfinite(result):
            return {"error": "Result is not finite"}
        
        return {"result": result}
        
    except ZeroDivisionError:
        return {"error": "Division by zero"}
    except SyntaxError:
        return {"error": "Invalid syntax"}
    except Exception as e:
        return {"error": f"Evaluation failed: {str(e)}"}
```

## Test Cases

### Valid Expressions
- `"2+2"` → `{"result": 4}`
- `"10/2"` → `{"result": 5.0}`
- `"(3+2)*4"` → `{"result": 20}`
- `"2**3"` → `{"result": 8}`
- `"1.5 + 2.5"` → `{"result": 4.0}`

### Invalid Expressions
- `"2+"` → `{"error": "Invalid syntax"}`
- `"1/0"` → `{"error": "Division by zero"}`
- `"import os"` → `{"error": "Invalid characters in expression"}`
- `"sin(0)"` → `{"error": "Invalid characters in expression"}`

## Integration Notes
- Tool name: `EvalMath`
- Entry point: `evalmath.evaluate`
- Reliability: High (deterministic)
- Cost: Tiny (local computation)
- Latency: ~5ms
