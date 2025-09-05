# TextOps.CountLetters Tool Implementation

## Purpose
Counts occurrences of a specific letter in a given text string.

## Input/Output Contract
- **Input**: `{"letter": "r", "word": "strawberry"}` (single letter + text)
- **Output**: `{"count": 2}` (integer count)
- **Assertion**: `(Text "strawberry" containsLetterCount 2)` for letter "r"

## Implementation Details

### Input Validation
- Letter must be exactly one character
- Word must be non-empty string
- Case-sensitive counting by default
- Optional case-insensitive mode

### Preconditions
- `letter_is_single_char`: Input letter is exactly 1 character
- `word_is_non_empty`: Input word has length > 0

### Postconditions
- `count_is_non_negative`: Result count >= 0
- `count_is_integer`: Result is an integer
- `count_matches_manual`: Result matches manual count

### Error Handling
- Empty letter → return error
- Empty word → return error
- Non-string inputs → return error

## Example Usage

```python
def count_letters(letter: str, word: str, case_sensitive: bool = True) -> dict:
    """
    Count occurrences of a letter in a word.
    
    Args:
        letter: Single character to count
        word: Text to search in
        case_sensitive: Whether to match case exactly
        
    Returns:
        dict: {"count": int} or {"error": "message"}
    """
    try:
        # Validate inputs
        if not isinstance(letter, str) or len(letter) != 1:
            return {"error": "Letter must be exactly one character"}
        
        if not isinstance(word, str) or len(word) == 0:
            return {"error": "Word must be a non-empty string"}
        
        # Count occurrences
        if case_sensitive:
            count = word.count(letter)
        else:
            count = word.lower().count(letter.lower())
        
        return {"count": count}
        
    except Exception as e:
        return {"error": f"Counting failed: {str(e)}"}
```

## Test Cases

### Valid Cases
- `letter="r", word="strawberry"` → `{"count": 2}`
- `letter="a", word="banana"` → `{"count": 3}`
- `letter="z", word="hello"` → `{"count": 0}`
- `letter="A", word="Apple"` → `{"count": 1}` (case-sensitive)
- `letter="a", word="Apple", case_sensitive=False` → `{"count": 1}`

### Invalid Cases
- `letter="", word="hello"` → `{"error": "Letter must be exactly one character"}`
- `letter="ab", word="hello"` → `{"error": "Letter must be exactly one character"}`
- `letter="a", word=""` → `{"error": "Word must be a non-empty string"}`

## Edge Cases
- Empty string: handled by validation
- Special characters: counted normally
- Unicode characters: handled by Python's count method
- Whitespace: counted as regular characters

## Integration Notes
- Tool name: `TextOps.CountLetters`
- Entry point: `textops.count_letters`
- Reliability: High (deterministic)
- Cost: Tiny (string operations)
- Latency: ~2ms
- Dependencies: None (pure Python)
