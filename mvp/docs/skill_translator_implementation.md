# Skill-Based Translator Implementation

## Overview

The skill-based translator implements a new translation pipeline that:
1. Does **local skill search** (no LLM) to find matching skills
2. Presents a **skill menu** to the LLM
3. LLM **chooses from menu only** (no tool names, no guessing)
4. **Validates strictly** against schemas
5. **Caches translations** by user text + skill menu fingerprint

## Architecture

### Components

1. **SkillRegistry** (`src/core/skills.py`)
   - Loads skills from `mvp/skills/*.yaml`
   - Provides `search_skills()` for local keyword matching
   - Extracts input/constraint schemas from skills
   - Compiles skills to obligations

2. **SkillTranslator** (`src/translators/skill_translator.py`)
   - Implements the translation pipeline
   - Handles caching
   - Validates LLM output
   - Returns RUN_SKILL, CLARIFY, or DISCOVER_OP obligations

3. **Conductor** (`src/conductor/conductor.py`)
   - Handles RUN_SKILL obligations
   - Compiles skills to obligations
   - Executes compiled obligations recursively

## Pipeline Steps

### Step 0: Preprocess (local, deterministic)
- Build context: user_text, platform, cwd, budgets
- No LLM involved

### Step 1: Local Skill Search
```python
skill_menu = skill_registry.get_skill_menu(user_text, top_n=10)
```
- Keyword matching on skill name + description
- Returns top N skills with schemas
- Includes `__NO_MATCH__` if no skills found

### Step 2: LLM Translation
- Send: user text + skill menu + schemas
- LLM outputs: JSON with RUN_SKILL, CLARIFY, or DISCOVER_OP
- **Strict rules**: Only choose from menu, no tool names, no planning

### Step 3: Validate (local, deterministic)
- Check: valid JSON, obligation type, skill name in menu
- Check: inputs match schema, required fields present
- One repair attempt if validation fails

### Step 4: Cache
- Key: `hash(user_text_hash + skill_menu_fingerprint + model + prompt_version)`
- Store: validated obligations JSON

## Obligation Types

### RUN_SKILL
```json
{
  "type": "RUN_SKILL",
  "payload": {
    "name": "workflow.email_domains",
    "inputs": {
      "text": "...",
      "denylist_domains": []
    },
    "constraints": {},
    "capability_budgets": {
      "max_tool_runs": 20,
      "max_cache_misses": 5,
      "max_toolsmith_calls": 0
    }
  }
}
```

### CLARIFY
```json
{
  "type": "CLARIFY",
  "payload": {
    "slots": ["folder"],
    "question": "Which folder should I search?"
  }
}
```

### DISCOVER_OP
```json
{
  "type": "DISCOVER_OP",
  "payload": {
    "goal": "Generate a 3D model",
    "inputs": {},
    "constraints": {}
  }
}
```

## Usage

### Enable Skill Translator
```python
from src.main import MVPAPI

api = MVPAPI(
    db_path=".ir/test.db",
    use_real_llm=True,
    api_key=os.getenv("OPENAI_API_KEY"),
    use_skill_translator=True  # Enable skill-based translation
)

trace = api.ask_with_trace("Extract emails from text and count domains")
```

### Direct Translation
```python
from src.translators.skill_translator import SkillTranslator
from src.translators.real_llm import OpenAILLM
from src.core.skills import SkillRegistry

llm = OpenAILLM(api_key="...")
registry = SkillRegistry()
translator = SkillTranslator(llm, registry)

obligations = translator.translate("Show me images in D:\\Pics")
```

## Caching

Translations are cached by:
- `user_text_hash`: SHA256 of user input (first 16 chars)
- `skill_menu_fingerprint`: Hash of skill names + versions in menu
- `translator_model`: LLM model name
- `translator_prompt_version`: Prompt version string

Cache key: `SHA256(user_text_hash + skill_menu_fingerprint + model + prompt_version)`

**Cache invalidation**:
- User text changes
- Skill menu changes (skills added/removed/updated)
- Translator model changes
- Prompt version changes

## Validation Rules

1. ✅ JSON is valid and parseable
2. ✅ Obligation type is RUN_SKILL, CLARIFY, or DISCOVER_OP
3. ✅ If RUN_SKILL, `name` is in the skill menu
4. ✅ If RUN_SKILL, `inputs` match the skill's inputs_schema
5. ✅ If CLARIFY, `slots` array is present
6. ✅ If DISCOVER_OP, `goal` is present
7. ✅ No extra fields beyond schema

## Error Handling

### Validation Failure
- One repair attempt with validation errors
- If still invalid → return CLARIFY obligation

### Skill Not Found
- If skill name not in menu → validation error
- LLM should only choose from menu

### Missing Information
- LLM should output CLARIFY with missing slots
- Not a validation error, but expected behavior

## Schema Updates

### Obligation Schema
- Added `RUN_SKILL` to obligation type enum
- Added `runSkillPayload` definition
- Updated `clarifyPayload` to support `slots` array and `question` field

### Skill Schema
Skills can include:
- `name`: Skill identifier
- `version`: Version string
- `description`: Human-readable description
- `inputs_schema`: JSON schema for inputs (optional, auto-extracted if missing)
- `constraints_schema`: JSON schema for constraints (optional)
- `obligations`: Template obligations with `{{inputs.key}}` placeholders

## Example Flow

1. **User**: "Extract emails from text and count distinct domains"
2. **Skill Search**: Finds `workflow.email_domains` skill
3. **Menu**: `[{name: "workflow.email_domains", inputs_schema: {...}}]`
4. **LLM**: Outputs RUN_SKILL with `name: "workflow.email_domains"`, `inputs: {text: "..."}`
5. **Validation**: ✅ Skill name in menu, inputs match schema
6. **Conductor**: Compiles skill to obligations, executes
7. **Result**: Email extraction → normalization → domain counting

## Benefits

1. **No tool name guessing**: LLM only sees skills, not tools
2. **Schema validation**: Inputs validated against skill schemas
3. **Caching**: Same request + same menu = cache hit
4. **Local search**: Fast skill matching without LLM
5. **Strict validation**: Prevents invalid obligations
