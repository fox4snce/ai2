## AI2 MVP Manual (Obligations -> Operations Engine)

This document is the **real manual** for the project: what it is, how it works, why it works, and how to use/extend it safely.

It is written for the current state of the repository (the MVP), which already includes:
- deterministic obligations execution (FastAPI + in-process)
- contract-driven tool selection
- missing-capability detection + toolsmith generation loop
- deterministic “plan emit -> execute” chaining (Reasoning.Core emits obligation steps; Conductor executes them)
- consolidation planning (manual plan generation with fingerprints + safety gates)

---

## 1) What this program is

This repo is a **tool-driven engine** whose core job is:

- Take a structured list of **obligations** (“what must hold”)
- Select deterministic **tools** (small programs) that can satisfy them
- Execute those tools and store results as structured outputs (“assertions” + trace)
- Return an answer and a complete trace of “what ran and why”

The key principle is:

- **LLMs are optional translators.**
  - When used: translate natural language -> obligations, and optionally render output to natural language.
  - When not used: you send obligations JSON directly, everything stays deterministic.

You can think of it as a **mini compiler/runtime**:

- Obligations are the “IR” of intention.
- Tool contracts are the “linker symbols”.
- The conductor is the “scheduler/executor”.
- Tool outputs are the “effects / facts / artifacts”.

---

## 2) Why it works (and why it’s not a card house)

Systems collapse when they depend on “magic strings” and silent conventions.
This MVP avoids that by putting “truth” in:

- **Tool contracts** (schemas + capabilities)
- **Deterministic routing policy**
- **Plan-time schema validation** (planner refuses to emit steps that don’t typecheck)
- **Missing capability is structured**, not a generic error string
- **Tests and trace replays** as safety gates
- **Consolidation plans are fingerprinted artifacts**, so refactors are repeatable and safe

In practice you get predictable outcomes:

1) A request executes cleanly.
2) It returns `clarify` (missing required input).
3) It returns structured `missing_capability` (no tool exists).
4) Toolsmith can generate a new tool + test, and the engine can retry.

---

## 3) The mental model (one page)

### 3.1 Obligations

An obligation is a small JSON object:

- `type`: what sort of requirement it is (`REPORT`, `ACHIEVE`, …)
- `payload`: structured input for that requirement

The MVP mostly uses:
- `REPORT` (produce an answer)
- `ACHIEVE` with `state=plan` (produce a plan)
- `CLARIFY` (ask for missing info)
- `DISCOVER_OP` (we lack a tool; toolsmith can create one)

### 3.2 Tools

A tool is:

- A **contract** (YAML) describing:
  - what it consumes (input kind + JSON schema)
  - what it produces
  - which obligation patterns it satisfies (`REPORT(query.math)`, etc.)
  - cost/reliability/latency (routing policy)
- A **deterministic implementation** (python function today)

Tool contracts live here:
- `mvp/contracts/tools/*.yaml`
- generated tools: `mvp/contracts/tools/generated/*.yaml`

### 3.3 Conductor

The conductor does:

- obligation parsing + validation
- tool selection from contracts
- tool execution
- trace building
- (optional) plan step execution: if a tool emits `trajectory.steps` containing obligations, execute them

The conductor is intentionally dumb. It does not “think”. It enforces policy.

### 3.4 Reasoning.Core

`Reasoning.Core` is a deterministic tool that can emit:

- proofs (logic mode)
- plans (planning mode)

The key point: a plan can contain **obligations** as steps.
That means the “planner” can be separate from the “executor”.

### 3.5 Toolsmith

Toolsmith is the “missing capability compiler”:

1) engine emits `missing_capability` and a `DISCOVER_OP`
2) toolsmith generates:
   - tool contract
   - tool python code
   - pytest test
3) toolsmith runs the test
4) if test fails, toolsmith asks the LLM to repair only the tool code (not the test) until it passes or attempts run out

This keeps the conductor deterministic and uses the LLM only for code synthesis with test gating.

---

## 4) Core data formats

### 4.1 Obligations JSON (input)

File shape:

```json
{
  "obligations": [
    { "type": "REPORT", "payload": { "kind": "query.math", "expr": "2+2" } }
  ]
}
```

Schema:
- `mvp/schemas/obligation.schema.json`

Guide with working examples:
- `mvp/ops/obligations.md`

Validator:

```powershell
cd mvp
.\.venv\Scripts\python scripts\validate_obligations.py path\to\obligations.json
```

### 4.2 Trace JSON (output)

Each run returns a trace containing:

- obligations (what was asked)
- tool_runs (what ran)
- outputs (what each tool returned)
- assertions (facts generated)
- final_answer

Traces are written by automation into:
- `.toolsmith/traces/*.json`

### 4.3 Trajectory format (plans/proofs)

Tools may return:

```json
{
  "trajectory": {
    "steps": [
      { "obligation": { "type": "REPORT", "payload": { "kind": "query.math", "expr": "2+2" } } },
      { "obligation": { "type": "REPORT", "payload": { "kind": "query.count", "letter": "r", "word": "strawberry" } } }
    ]
  }
}
```

If `steps` contain `obligation` objects, the conductor executes them deterministically (routing by contracts).

---

## 5) How execution works (step-by-step)

### 5.1 Deterministic “execute obligations” flow

1) Parse/validate obligations JSON.
2) For each obligation:
   - find candidate tools whose contracts satisfy it
   - validate payload vs tool input schemas
   - choose best tool deterministically (reliability > cost > latency)
   - execute tool and record outputs
3) If a tool output contains a trajectory with obligation steps:
   - execute each step obligation in order the same way
4) Return final trace with all tool runs and outputs.

### 5.2 Missing capability flow

If no tool can satisfy an obligation:

- Conductor produces a structured `missing_capability` payload and emits a `DISCOVER_OP`.
- API returns status 422.

Then you can run toolsmith to generate the missing tool.

### 5.3 Plan-time schema hardening

When planning via `capability.sequence`, `Reasoning.Core` checks:

- “Do we have a tool that satisfies the capability?”
- “Does the requested input match the tool’s consumes schema?”

If required fields are missing, it emits `clarify` (instead of emitting a plan that will fail).

---

## 6) How to use it (Windows PowerShell)

### 6.1 Setup

```powershell
cd mvp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r ..\requirements.txt
python -m pip install -r ..\requirements-dev.txt
```

### 6.2 Run the demo (prints traces)

```powershell
.\.venv\Scripts\python demo.py
```

### 6.3 Run the API server

```powershell
.\.venv\Scripts\python -m src.api
```

Endpoints:
- `GET /v1/tools`
- `POST /v1/obligations/execute`

### 6.4 Run a small test

```powershell
cd mvp
.\.venv\Scripts\python -m pytest -q
```

### 6.5 Run the one-command automation loop (toolsmith)

Given an obligations file:

```powershell
cd mvp
.\.venv\Scripts\python scripts\auto_toolsmith.py --obligations .\schemas\obligations.normalize_email.json --model gpt-5-mini
```

This will:
- run obligations
- if missing tool: generate tool + test, repair tool until test passes
- rerun obligations
- print tool name + outputs
- save traces under `.toolsmith/traces/`

### 6.6 Reset a generated tool (start over)

Dry-run (see what would be deleted):

```powershell
cd mvp
.\.venv\Scripts\python scripts\cleanup_generated_tool.py --tool ReportNormalizeEmail
```

Actually delete:

```powershell
cd mvp
.\.venv\Scripts\python scripts\cleanup_generated_tool.py --tool ReportNormalizeEmail --yes
```

---

## 7) Planning + chaining demos

### 7.1 Contract-derived plan steps

This demo asks for capabilities and inputs, and the planner derives steps from contracts:

- `mvp/schemas/obligations.demo_chain_math_then_count.json`

Run:

```powershell
cd mvp
.\.venv\Scripts\python scripts\auto_toolsmith.py --obligations .\schemas\obligations.demo_chain_math_then_count.json --dry-run
```

You should see:
- `Reasoning.Core` emits trajectory steps containing obligations
- conductor executes the step obligations
- trace includes tool runs for `Reasoning.Core`, `EvalMath`, `TextOps.CountLetters`

### 7.2 Intentional schema mismatch (planner should clarify)

- `mvp/schemas/obligations.demo_chain_count_missing_word.json`

Run:

```powershell
cd mvp
.\.venv\Scripts\python scripts\auto_toolsmith.py --obligations .\schemas\obligations.demo_chain_count_missing_word.json --dry-run
```

Expected: `clarify: word` and **no toolsmith**.

---

## 8) Consolidation (manual, safe, fingerprinted)

### 8.1 What consolidation is (in this repo)

Consolidation is a **periodic refactor process** to prevent tool sprawl:

- build a plan (no changes)
- review it
- (later) apply changes only if fingerprints match
- run tests + replay traces as safety gates

### 8.2 Generate a consolidation plan

```powershell
cd mvp
.\.venv\Scripts\python scripts\consolidate_tools.py --family normalization --write-json
```

Outputs:
- `.toolsmith/consolidation_plans/*.md`
- `.toolsmith/consolidation_plans/*.json`

The plan includes:
- duplicates/near-duplicates
- a proposed library tool shape (for normalization)
- wrappers to preserve backward compatibility
- safety gate tests and trace fixtures
- fingerprints (tool registry + trace set)

### 8.3 Replay trace fixtures (safety gate)

```powershell
cd mvp
.\.venv\Scripts\python scripts\replay_trace_fixtures.py --fixtures ..\.toolsmith\consolidation_plans\<PLAN_JSON>
```

### 8.4 Stability experiment (plan diff should be clean)

```powershell
cd mvp
.\.venv\Scripts\python scripts\run_consolidation_stability_experiment.py --model gpt-5-mini
```

This:
- generates plan (before)
- generates a new normalizer (`normalize_phone`) via toolsmith
- generates plan (after)
- prints a stable diff summary

---

## 9) Extending the system

### 9.1 Add a new deterministic tool by hand

1) Add a contract YAML in `mvp/contracts/tools/` (or `generated/` for experiments).
2) Implement `run(inputs: dict) -> dict` and set `implementation.entry_point` to it.
3) Add a test under `mvp/tests/`.

### 9.2 Add a new tool via toolsmith

1) Write an obligations file that uses a new `kind`.
2) Run:

```powershell
cd mvp
.\.venv\Scripts\python scripts\auto_toolsmith.py --obligations path\to\your_obligations.json --model gpt-5-mini
```

### 9.3 Add new “planner vocabulary” without hardcoding tool names

Do not add new demo predicates that hardcode tool names.

Preferred pattern:
- express requested work as **capabilities**
- have the planner read contracts and emit obligations
- the conductor routes deterministically

---

## 10) Troubleshooting

### 10.1 “missing_capabilities”

If you see missing capability:
- check `trace.missing_capabilities[]` (it will tell you the required input kind)
- run toolsmith loop via `auto_toolsmith.py`

### 10.2 “clarify”

If you see clarify:
- the planner or tool requires a missing field
- update your obligations JSON to include it

### 10.3 Windows BOM / encoding issues

The validator and runners accept `utf-8-sig` (UTF-8 with BOM) so PowerShell-created JSON is OK.

---

## 11) Where to look in the repo (map)

- Engine entry points:
  - `mvp/src/main.py` (`MVPAPI`)
  - `mvp/src/api.py` (FastAPI)
- Conductor:
  - `mvp/src/conductor/conductor.py`
- Tool contracts:
  - `mvp/contracts/tools/`
  - generated: `mvp/contracts/tools/generated/`
- Tool implementations:
  - builtins and mock implementations: `mvp/src/core/tools.py`
  - generated python tools: `mvp/src/tools_generated/`
  - stable library tools: `mvp/src/tools/`
- Toolsmith + automation:
  - `mvp/scripts/toolsmith.py`
  - `mvp/scripts/auto_toolsmith.py`
- Consolidation:
  - `mvp/scripts/consolidate_tools.py`
  - `mvp/scripts/replay_trace_fixtures.py`
  - `mvp/scripts/diff_consolidation_plans.py`
  - `mvp/scripts/run_consolidation_stability_experiment.py`


