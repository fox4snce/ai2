# AI2: Obligations → Operations Engine

**A deterministic AI system that separates translation from reasoning, making AI behavior transparent, testable, and cacheable.**

## What This System Does

AI2 is a **deterministic execution substrate** for LLM translation. It's not a general-purpose agent replacement—it's infrastructure for problems where reliability, provenance, and repeatability matter more than creative reasoning.

**The Core Idea**: LLM output is not "actions"—it's a bounded, testable IR (obligations). Everything after translation is deterministic.

- **LLMs translate**: Natural language ↔ structured obligations (what must be done)
- **Tools execute**: Deterministic operations that actually do the work (math, database queries, file operations)
- **IR Database remembers**: Facts, assertions, and provenance live in a database, not in prompts
- **Conductor orchestrates**: Selects tools by policy (reliability > cost > latency), not by LLM guessing

**Result**: Same request → same answer (bit-for-bit), with full provenance, caching, and no context window bloat.

### What Makes AI2 Unique

AI2 provides three properties that are hard to get cleanly elsewhere:

1. **Reproducibility as a first-class guarantee**
   - Same obligations + same inputs → same outputs (bit-for-bit)
   - In typical tool-calling, the model can still vary the plan or tool choice run-to-run
   - AI2: Tool choice happens by policy and contracts, not "model vibes"

2. **Dependency-aware caching + invalidation as part of the runtime**
   - Cache keys include: inputs + declared dependencies (files, env vars, DB state, tool versions)
   - Cache invalidates automatically when dependencies change
   - This is a core execution contract, not an optional feature

3. **Audit/provenance as the default output, not optional logging**
   - Assertions/events/tool_runs live in an IR DB
   - Provenance is the product, not a bolt-on
   - Every answer has a complete trace showing what ran, why, and where results came from

**One-line summary**: AI2 is a deterministic, cacheable, auditable "operations VM" where the LLM is only a compiler (NL → obligations).

## Core Capabilities

### 1. **Deterministic Execution**
- Same obligations + same inputs → same outputs (bit-for-bit)
- No randomness, no "sometimes it works"
- Perfect for testing, debugging, and production reliability

### 2. **Intelligent Caching**
- Tool outputs cached automatically
- Cache invalidates when dependencies change (files, env vars, DB state, tool versions)
- Dramatically reduces LLM calls and tool executions

### 3. **Complete Provenance**
- Every answer has a full trace: which tools ran, why they were chosen, what they produced
- All assertions, events, and tool runs stored in IR database
- Audit trail for every decision

### 4. **Skill-Based Translation** (New)
- Local skill search (no LLM tokens) finds matching workflows
- LLM only sees a menu of available skills, not tool internals
- Translation results cached by user text + skill menu fingerprint
- Prevents LLM from inventing tools or guessing names

### 5. **Verification & Evidence**
- Answers verified before returning (recompute, consistency checks)
- Verification evidence stored as structured objects (not just pass/fail)
- Know exactly what was checked and how

### 6. **Capability Budgeting**
- Enforce limits on tool runs, cache misses, toolsmith calls, external access
- Prevents runaway execution and cost overruns
- Structured errors when budgets exceeded

### 7. **Tool Generation (Toolsmith)**
- Automatically generate tools when capabilities are missing
- **Requires LLM**: Uses OpenAI via `llm_utils.py` (requires `OPENAI_API_KEY` environment variable)
- Generates tool contracts, Python implementations, and tests from `DISCOVER_OP` obligations
- Tools have metadata: owner, version, tests, status (experimental/stable/deprecated)
- Package management for generated tools

## Architecture Overview

- **IR Database**: Stores ideas as entities, relations, assertions, and events (persistent memory)
- **Obligations**: Universal grammar for "what must hold" (REPORT, ACHIEVE, RUN_SKILL, etc.)
- **Skills**: Reusable workflow templates that compile to obligations
- **Tools**: Deterministic operations with contracts (EvalMath, PeopleSQL, etc.)
- **Conductor**: Selects tools to satisfy obligations using policy, not LLM scoring
- **Translators**: LLMs only translate NL ↔ obligations, not solve problems

## Quick Start

### 1) Setup
```powershell
cd mvp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# Note: requirements.txt lives at the repo root, not inside mvp/
python -m pip install -r ..\requirements.txt

# Optional: For LLM features (translation, tool generation)
# Set OPENAI_API_KEY environment variable (currently only OpenAI supported)
$env:OPENAI_API_KEY = "your-api-key-here"
```

### 2) Run the API Server
```powershell
python -m src.api
# Server on http://0.0.0.0:8000
```

### 3) LLM Requirements (Optional)

**For Natural Language Translation and Tool Generation:**

- **Currently only OpenAI supported** via `llm_utils.py` (at repo root)
- Set `OPENAI_API_KEY` environment variable
- Required for:
  - Natural language → obligations translation (skill-based or legacy)
  - Tool generation via `scripts/toolsmith.py` (generates tools from `DISCOVER_OP` obligations)

**For Direct Obligations (No LLM needed):**

- You can use the system without any LLM by sending obligations directly
- All tool execution, caching, and verification work without LLM

### 4) Use the API

#### Direct Obligations (Deterministic, No LLM)

**PowerShell (Windows):**
```powershell
# Math calculation
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/obligations/execute `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"obligations":[{"type":"REPORT","payload":{"kind":"math","expr":"2+2"}}]}'

# Count letters in word
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/obligations/execute `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"obligations":[{"type":"REPORT","payload":{"kind":"count","letter":"r","word":"strawberry"}}]}'

# Query people database
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/obligations/execute `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"obligations":[{"type":"REPORT","payload":{"kind":"query.people","filters":[{"is_friend":"user"},{"city":"Seattle"}]}}]}'
```

**Bash/Linux/Mac:**
```bash
# Math calculation
curl -s -X POST http://127.0.0.1:8000/v1/obligations/execute \
  -H "Content-Type: application/json" \
  -d '{"obligations":[{"type":"REPORT","payload":{"kind":"math","expr":"2+2"}}]}'

# Count letters in word
curl -s -X POST http://127.0.0.1:8000/v1/obligations/execute \
  -H "Content-Type: application/json" \
  -d '{"obligations":[{"type":"REPORT","payload":{"kind":"count","letter":"r","word":"strawberry"}}]}'

# Query people database
curl -s -X POST http://127.0.0.1:8000/v1/obligations/execute \
  -H "Content-Type: application/json" \
  -d '{"obligations":[{"type":"REPORT","payload":{"kind":"query.people","filters":[{"is_friend":"user"},{"city":"Seattle"}]}}]}'
```

#### Natural Language (With LLM Translation)
```python
from src.main import MVPAPI
import os

# With skill-based translator (recommended)
api = MVPAPI(
    db_path=".ir/test.db",
    use_real_llm=True,
    api_key=os.getenv("OPENAI_API_KEY"),
    use_skill_translator=True  # Uses skill menu instead of direct tool names
)

# Ask questions
answer = api.ask("What's 2+2?")
trace = api.ask_with_trace("Extract emails from text and count distinct domains")

# Or use direct obligations (no LLM needed)
obligations = {
    "obligations": [
        {"type": "REPORT", "payload": {"kind": "math", "expr": "2+2"}}
    ]
}
result = api.execute_obligations(obligations)
```

### 5) Run Tests
```powershell
# Smoke test (no server)
python scripts/smoke_api.py

# API tests
python -m pytest tests/test_api.py -q

# Cache invalidation tests
python tests/test_cache_invalidation_real.py
```

## What You Can Build

### Current Capabilities

1. **Mathematical Computation**: Evaluate expressions, verify results
2. **Text Processing**: Count letters, extract patterns, normalize text
3. **Database Queries**: Query people, documents, structured data
4. **Email Processing**: Extract emails, normalize, count domains (with denylist support)
5. **Logical Reasoning**: Deductive reasoning with facts and rules
6. **Planning**: Generate execution plans for complex goals
7. **Skill Workflows**: Reusable workflow templates (email extraction → normalization → domain counting)

### Extending the System

Add new capabilities by:
- **Adding Tools**: Create tool contracts in `mvp/contracts/tools/` with YAML definitions
- **Adding Skills**: Create workflow templates in `mvp/skills/` that compile to obligations
- **Tool Generation**: Use `scripts/toolsmith.py` to auto-generate tools from traces
  - **Requires LLM**: Currently only OpenAI supported via `llm_utils.py` (set `OPENAI_API_KEY` environment variable)
  - Reads traces with `DISCOVER_OP` obligations and generates tool contracts, implementations, and tests

The system is designed to scale: add tools and skills without changing the core conductor, IR, or verification logic.

## Documentation

- **Obligation Writing Guide**: `mvp/docs/obligation_writing_guide_for_llms.md` - Complete reference for LLMs
- **Skill Translator Guide**: `mvp/docs/skill_translator_implementation.md` - Skill-based translation system
- **Obligations Examples**: `mvp/ops/obligations.md` - Working examples
- **Schema Reference**: `mvp/schemas/obligation.schema.json` - JSON schema
- **Full Manual**: `docs/manual.md` - In-depth explanation of architecture, toolsmith, planning, consolidation

## License

This project is licensed under a **Fair Use + Enterprise License**.

- Free for individuals, nonprofits, and companies under $100M revenue
- Paid license required for large enterprises

See `LICENSE.md` and `NOTICE.md` for details.

## How It Works: Request Flow

### Example 1: Direct Obligations (No LLM)
1. User sends: `{"obligations": [{"type": "REPORT", "payload": {"kind": "math", "expr": "2+2"}}]}`
2. Conductor: Selects `EvalMath` tool (by policy: reliability > cost > latency)
3. Tool executes: Evaluates expression → `Assertion(Expression "2+2" evaluatesTo 4)`
4. Verify: Recomputes → passes → stores verification evidence
5. Response: `{"final_answer": "4", "tool_runs": [...], "assertions": [...]}`

### Example 2: Natural Language with Skill Translation
1. User: "Extract emails from text and count distinct domains"
2. **Skill Search** (local, no LLM): Finds `workflow.email_domains` skill
3. **LLM Translation**: Outputs `RUN_SKILL` with skill name + inputs
4. **Validation**: Checks skill name in menu, inputs match schema
5. **Skill Compilation**: Skill template → obligations (email.extract → normalize → count)
6. **Conductor**: Executes each obligation, selecting tools by policy
7. **Cache**: Tool outputs cached for future runs
8. **Response**: Final answer with full trace

### Example 3: Cached Execution
1. User: Same request as before
2. **Cache Lookup**: Same inputs + same dependencies → cache hit
3. **Response**: Returns cached result (near-zero latency, no tool execution)

## File Structure

```
mvp/
├── db/
│   ├── schema.sql          # Core IR tables (entities, relations, assertions, events, tool_runs)
│   └── examples.sql        # Sample data
├── contracts/
│   ├── obligation.schema.json  # Obligation grammar schema
│   ├── tool.schema.json        # Tool contract schema
│   └── tools/
│       ├── evalmath.yaml
│       ├── textops_countletters.yaml
│       ├── people_sql.yaml
│       └── adapters/
│           └── people_sql_adapter.yaml
├── skills/
│   └── workflow.email_domains.yaml  # Skill/workflow templates
├── conductor/
│   ├── plan.md            # Conductor algorithm
│   └── policy.md           # Tool selection policy
├── prompts/
│   ├── translator_in.md    # NL → obligations prompt (legacy)
│   ├── translator_skill_in.md  # Skill-based translation prompt
│   └── translator_out.md   # Assertions → NL prompt
├── docs/
│   ├── obligation_writing_guide_for_llms.md  # Complete LLM reference
│   └── skill_translator_implementation.md     # Skill translator docs
├── ops/
│   ├── evalmath.md         # Math tool implementation
│   ├── textops_countletters.md
│   └── people_sql.md
├── observability/
│   └── trace_format.md     # Request tracing spec
├── scripts/
│   ├── smoke_api.py        # In-process API smoke test
│   ├── toolsmith.py        # Tool generation from traces
│   └── validate_obligations.py  # Schema validator
├── src/
│   ├── api.py              # FastAPI app (deterministic obligations API)
│   ├── main.py             # Main request handler
│   ├── core/
│   │   ├── database.py     # IR database interface
│   │   ├── obligations.py # Obligation parsing/validation
│   │   ├── tools.py        # Tool registry and contracts
│   │   ├── skills.py       # Skill registry and compilation
│   │   ├── cache.py        # Caching with dependency tracking
│   │   └── packages.py    # Package management for generated tools
│   ├── conductor/
│   │   └── conductor.py    # Main orchestration engine
│   └── translators/
│       ├── translators.py  # Legacy translator
│       ├── real_llm.py     # OpenAI integration
│       └── skill_translator.py  # Skill-based translator
├── tests/
│   ├── test_api.py         # Live API endpoint tests
│   ├── test_cache_invalidation_real.py  # Cache abuse tests
│   └── test_workflow_email_domains_adult_demo.py  # Workflow demo
└── README.md
```

## Core Components

### Obligation Types

- `REPORT(query)` - Produce answers (math, count, query.people, query.documents, logic, plan, etc.)
- `RUN_SKILL(name, inputs)` - Execute a skill/workflow template (new)
- `ACHIEVE(state)` - Make states true (set status, create plans)
- `MAINTAIN(pred)` - Keep predicates true (continuous conditions)
- `AVOID(pred)` - Keep predicates false (prevent conditions)
- `JUSTIFY(claim)` - Show provenance and evidence
- `SCHEDULE(event,time)` - Bind actions to time
- `CLARIFY(slot)` - Ask for missing information
- `VERIFY(ans)` - Check answers before sending
- `DISCOVER_OP(goal)` - Request tool generation when capability missing

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

### Math Query (With Verification)
```json
{
  "user_input": "What's 2+2?",
  "obligations": [
    {"type": "REPORT", "payload": {"kind": "math", "expr": "2+2"}},
    {"type": "VERIFY", "payload": {"target": "last_answer"}}
  ],
  "tool_runs": [
    {
      "tool_name": "EvalMath",
      "inputs": {"expr": "2+2"},
      "outputs": {"result": 4},
      "cache_hit": false,
      "duration_ms": 2
    }
  ],
  "assertions": [
    {"subject_id": "E2", "predicate": "evaluatesTo", "object": "4", "confidence": 1.0}
  ],
  "verification": {
    "passed": true,
    "method": "recompute",
    "evidence": [
      {"check_type": "recompute", "comparison_result": "match"}
    ]
  },
  "final_answer": "4"
}
```

### Skill-Based Workflow (Email Domain Extraction)
```json
{
  "user_input": "Extract emails from text and count distinct domains",
  "obligations": [
    {
      "type": "RUN_SKILL",
      "payload": {
        "name": "workflow.email_domains",
        "inputs": {
          "text": "Contact alice@example.com or bob@test.com",
          "denylist_domains": []
        }
      }
    }
  ],
  "tool_runs": [
    {"tool_name": "EmailExtract", "inputs": {...}, "cache_hit": false},
    {"tool_name": "NormalizeEmails", "inputs": {...}, "cache_hit": false},
    {"tool_name": "CountDomains", "inputs": {...}, "cache_hit": false}
  ],
  "final_answer": "Found 2 distinct domains: example.com, test.com"
}
```

### People Query (With Cache Hit)
```json
{
  "user_input": "List friends in Seattle",
  "obligations": [
    {"type": "REPORT", "payload": {"kind": "query.people", "filters": [{"is_friend": "user"}, {"city": "Seattle"}]}}
  ],
  "tool_runs": [
    {
      "tool_name": "PeopleSQL",
      "inputs": {"filters": [...]},
      "outputs": {"people": [...]},
      "cache_hit": true,  // Second run uses cache
      "duration_ms": 0
    }
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

## What This System Guarantees

### Core Guarantees

1. **Deterministic Execution**: Same obligations + same inputs → same outputs (bit-for-bit)
2. **Cache Safety**: Cache invalidates when dependencies change (filesystem, env vars, DB, tool versions)
3. **Complete Provenance**: Every answer has a full trace showing what ran, why, and where results came from
4. **Verification Evidence**: Verification checks are stored as evidence objects (not just pass/fail)
5. **Capability Budgeting**: Enforced limits on tool runs, cache misses, toolsmith calls, external access
6. **Package Management**: Generated tools have metadata (owner, status, tests, trace origin)
7. **Tool Selection Policy**: Deterministic selection based on reliability > cost > latency (no LLM scoring)
8. **Schema Validation**: Obligations and tool inputs validated against schemas before execution
9. **Missing Capability Detection**: Structured errors when no tool can satisfy an obligation
10. **Trace Persistence**: All tool runs, assertions, and events stored in IR database

### Cache Invalidation Guarantees

- **File Dependencies**: Cache invalidates when file mtime/size changes
- **Environment Variables**: Cache invalidates when env var values change
- **Database Dependencies**: Cache invalidates when DB file mtime/size changes
- **Tool Versions**: Cache invalidates when tool contract version changes
- **Clock Dependencies**: Tools with `depends_on: ["clock"]` rarely cache (minute-level granularity)

## What It Explicitly Does Not Do

1. **No LLM-Based Tool Selection**: Tools are selected by deterministic policy, not LLM scoring
2. **No Prompt Engineering for Reasoning**: LLMs only translate NL ↔ obligations at the edges
3. **No Context Window Bloat**: Facts live in IR database, not in prompts
4. **No Silent Failures**: Missing capabilities return structured errors, not generic messages
5. **No Magic Strings**: All routing based on contracts and schemas, not string matching
6. **No Side Effects During Planning**: Planning mode emits plans only, never modifies world state
7. **No Unbounded Execution**: Capability budgets enforce limits on resource usage
8. **No Cache Without Invalidation**: Tools must declare dependencies or are assumed pure
9. **No Verification Without Evidence**: Verification stores what was checked, not just pass/fail
10. **No Generated Tools Without Metadata**: All toolsmith-generated tools have package metadata

## Key Principles

1. **LLMs ≠ Universal Solvers**: They're translators between NL and structure, not problem solvers
2. **Reasoning Lives in Tools**: Math, search, planning, control live in deterministic tools
3. **IR is Memory**: Facts live outside prompts in a database, not in context windows
4. **Obligations Drive Behavior**: "What must hold" determines "how we do it"
5. **Verify Before Answer**: Check answers before they leave the system
6. **Trace Everything**: Every answer has a complete provenance trail
7. **Cache Aggressively**: Same inputs → reuse cached outputs (with dependency tracking)
8. **Skills Over Tools**: LLM sees workflows (skills), not tool internals

## Why This Architecture?

### The Problem with Traditional LLM Systems

- **Non-deterministic**: Same question → different answers
- **No provenance**: Can't explain why an answer was given
- **Context bloat**: Facts stuffed into prompts, hitting token limits
- **No caching**: Every request is expensive
- **Black box reasoning**: Can't audit or verify decisions
- **Tool selection guessing**: LLM picks tools by "vibes", not policy

### How AI2 Solves This

- **Deterministic**: Same obligations → same outputs (cacheable, testable)
- **Full provenance**: Every decision traceable to tool runs and assertions
- **IR database**: Facts live in SQLite, not prompts
- **Smart caching**: Cache by inputs + dependencies, invalidate on change
- **Policy-based selection**: Tools chosen by reliability > cost > latency (deterministic)
- **Verification evidence**: Know exactly what was checked and how
- **Skill abstraction**: LLM sees workflows, not implementation details

## Comparison to Alternatives

### 1. Manual Scripting (No LLM)
**AI2 wins**: Usability, translation, adapting to messy inputs  
**AI2 loses**: Manual scripts are more reliable and debuggable for simple cases

**AI2's advantage**: You keep the deterministic backend but regain natural language as an interface without letting NL drive runtime behavior. If a user can say "extract emails, normalize, count domains" and you can compile that into a known workflow, you've basically built "CLI power" with "human interface."

### 2. Plain LLM Chat
**AI2 wins**: Determinism, provenance, testability, caching  
**AI2 loses**: Fast to build, flexible

**AI2's advantage**: Categorically better whenever "same request must mean same result" matters.

### 3. LLM + Tools (Function Calling)
**AI2 wins**: Stable planning/tool choice, caching discipline, verification evidence, end-to-end reproducibility  
**AI2 loses**: Simpler setup, faster iteration

**AI2's advantage**: Function calling gives you structured calls to tools, but doesn't guarantee deterministic orchestration. AI2: Tool choice happens by policy and contracts, not "model vibes."

### 4. Agent Frameworks (LangChain/LangGraph, LlamaIndex, etc.)
**AI2 wins**: Determinism + caching + evidence + provenance as default runtime behavior  
**AI2 loses**: Ecosystem, integrations, community

**AI2's advantage**: You made the "hard parts" (determinism + caching + evidence + provenance) the default runtime behavior, not a best-practice suggestion. Most teams still end up with mixed control logic, inconsistent caching, and provenance that exists but isn't "the IR truth."

### 5. MCP (Model Context Protocol)
**AI2's relationship**: Orthogonal, not competitive

- **MCP**: Standard way to expose tools/resources to models (universal adapter)
- **AI2**: Deterministic orchestration + evidence + caching semantics layer

**How they work together**: MCP can supply transport + discovery for tools. AI2 supplies the deterministic orchestration layer. Your "skill menu" idea parallels MCP's direction (tool search / handling large toolsets), but you're applying it to reliability ("LLM only sees a menu, not internals"), not just scale.

## When to Use AI2

AI2 is most valuable when **at least two of these are true**:

1. ✅ **You must be able to reproduce results later** (debugging, regression tests, "why did it do that?")
2. ✅ **You need traceable provenance/evidence** (audit, compliance, user trust, internal reviews)
3. ✅ **You expect repeated queries over the same underlying data** (caching becomes a multiplier)
4. ✅ **You have a bounded set of real operations** (skills/tools are definable and contractable)

### Concrete Use Cases Where AI2 Shines

**A) Deterministic Data Workbench**
- "Take this blob of text, extract entities, normalize, store in DB, then answer queries about it"
- The LLM only maps request → skill/obligations; everything else is deterministic and cacheable

**B) Policy / Rules Extraction into Executable Checks**
- Translate obligations/prohibitions into executable rules with guarded schemas + deterministic checks
- Compliance teams care about provenance + repeatability more than "creative reasoning"

**C) Internal Automation Where "No Silent Failures" Matters**
- If a tool is missing: structured "no tool can satisfy" is better than an agent hallucinating
- Verification evidence stored is a big deal for reliability culture

**D) Cost/Latency Control at Scale**
- Budgeting + cache invalidation is "agent runaway prevention" as a runtime feature, not a discipline

### When AI2 Has No Benefits

AI2 does **not** win when:

- ❌ The work is mostly open-ended writing/ideation (no stable "operations" to ground)
- ❌ You don't care about reproducibility, evidence, or debugging traces
- ❌ The "skills" can't be stabilized (every request is bespoke, and you'd constantly be toolsmithing)

In those cases, a normal "LLM + tools" agent framework (or even plain tool calling) is simpler and will feel better.

### Realistic Workflow: How to Use AI2

If you're adopting AI2, don't pitch it as "one tool to rule them all." Use it like this:

1. **Pick 5–10 high-value skills** that are common and repeatable (ETL-ish tasks, DB queries, normalization, summarization with citations, report generation, etc.)

2. **Make the LLM translator do only**:
   - Choose skill from menu
   - Fill input schema
   - Emit CLARIFY when missing required slots

3. **Treat every tool output as an assertion/event** stored in IR DB (you already do this)

4. **Add verification tools** for the few high-risk operations (math, DB queries, transforms), so "VERIFY" isn't symbolic—it becomes measurable evidence

5. **Use the cache** to make the system feel "instant" on repeats (this is where it stops feeling like a science project and starts feeling like infrastructure)

6. **If you later want MCP**: Expose your deterministic tools behind MCP servers, but keep AI2 as the orchestrator that decides what runs and when

## Validating Usefulness

If you want the fastest way to validate usefulness, build one "killer" demo around a repeated workflow (something like: ingest → normalize → store → query → justify/trace) and measure:

- **Repeat latency**: Cache hits should make second runs near-instant
- **Diffability**: Bit-for-bit identical outputs on same inputs
- **Trace explainability**: Can point to exactly why an answer was given

That's where AI2 will look obviously better than the alternatives.

## Next Steps

The core system is stable. To extend:

1. **Add Skills**: Create workflow templates in `mvp/skills/`
2. **Add Tools**: Create tool contracts in `mvp/contracts/tools/`
3. **Generate Tools**: Use `scripts/toolsmith.py` for auto-generation
   - Requires `OPENAI_API_KEY` environment variable
   - Currently only OpenAI supported (via `llm_utils.py` at repo root)
   - Generates tools from `DISCOVER_OP` obligations in traces
4. **Enhance Verification**: Add more sophisticated checking methods
5. **Build Integrations**: Connect to external systems via tools

The conductor, IR, and verify loop stay the same as you add tools and skills.

## Bottom Line

**Yes**: AI2 is uniquely useful as a deterministic, auditable, cacheable execution runtime where the LLM is a compiler, not an actor.

**No**: It's not a universal agent replacement—it's infrastructure for the slice of the world where reliability, provenance, and repeatability matter more than "figure it out somehow."

