# MVP architecture (no big code, just crisp buildable artifacts)

## 0) MVP goals

* **Translate NL → obligations (IR)** and back, with **no LLM scoring**.
* **Satisfy obligations** using **registered tools** against a **small IR DB**.
* **Verify** before answer leaves.
* **Traceable**: every answer has a provenance trail.

---

## 1) Components (thin, pluggable)

* **IR Store (DB)**: Postgres/SQLite as a graph-ish schema.
* **Translator–In (LLM)**: NL → obligations JSON (schema-validated).
* **Translator–Out (LLM)**: IR → NL phrasing.
* **Registry**: tool contracts (capabilities, pre/post-conditions).
* **Conductor**: selects tools to satisfy obligations; runs verify; escalates.
* **Tool Runners**: deterministic ops (can contain tiny NNs internally).
* **Observer**: logging, traces, metrics.

---

## 2) IR DB (start small)

**Tables**

* `entity(id, type, alias_jsonb)` — people, docs, concepts…
* `relation(id, src_id, rel_type, dst_id, attrs_jsonb)`
* `modifier(id, target_kind, target_id, key, value, unit)`
* `assertion(id, subject_id, predicate, object, confidence, valid_from, valid_to, source_id)`
* `event(id, kind, at_time, payload_jsonb)` — “asked…”, “tool\_run…”
* `source(id, kind, uri, info_jsonb)` — where facts came from
* `obligation(id, kind, details_jsonb, status, created_at, event_id)` — active/resolved
* `tool_run(id, tool_name, inputs_jsonb, outputs_jsonb, status, duration_ms, event_id)`

**Sample rows (tiny)**

* `entity: (E1,'person',{"aliases":["User"]})`
* `assertion: (A1,E_expr,'evaluatesTo',"4",1.0,now,null,S_evalmath)`
* `event: (EV3,'tool_run',now,{"tool":"EvalMath","expr":"2+2"})`
* `obligation: (OB5,'REPORT',{"math":"2+2"},'resolved',now,EV1)`

---

## 3) Obligation grammar (input contract)

**Types**

* `REPORT(query)` · `ACHIEVE(state)` · `MAINTAIN(pred)` · `AVOID(pred)`
* `JUSTIFY(claim)` · `SCHEDULE(event,time)` · `CLARIFY(slot)` · `VERIFY(ans)`

**Wire format (JSON)**

```json
{
  "obligations":[
    {"type":"REPORT","payload":{"kind":"math","expr":"2+2"}},
    {"type":"VERIFY","payload":{"target":"last_answer"}}
  ]
}
```

**Quick examples**

* Name: `{"type":"REPORT","payload":{"kind":"status","field":"name"}}`
* People query: `{"type":"REPORT","payload":{"kind":"query.people","filters":[{"is_friend":"user"},{"city":"Seattle"}]}}`
* Control: `{"type":"MAINTAIN","payload":{"pred":"ball.within_radius","args":{"r":0.1}}}`

---

## 4) Tool contract (registry entry)

**Schema (YAML/JSON)**

```yaml
name: EvalMath
consumes:
  - kind: query.math
    schema: { expr: string }
produces:
  - assertion: { subject: Expression, predicate: evaluatesTo, object: number }
satisfies:
  - REPORT(query.math)
  - VERIFY(answer.math)
preconditions:
  - expr_parses
postconditions:
  - result_is_number
cost: tiny
reliability: high
```

**Adapter contract (example)**

```yaml
adapter_for: PeopleSQL
maps:
  filters:
    - from: {is_friend: "user"}   to: {relation: "friend"}
    - from: {city: "<X>"}         to: {city: "<X>"}
```

---

## 5) Conductor loops

**Top-level request loop**

1. Log `event: user_utterance`.
2. **Translator–In** → obligations JSON (validate).
3. Insert obligations; for each:

   * **Plan loop** (below).
4. If any `REPORT` produced → **VERIFY** pass.
5. **Translator–Out** → NL answer.
6. Log tool runs, assertions, and final response.

**Plan loop (per obligation)**

1. Gather candidate tools: `tool.satisfies ⊇ obligation.type`.
2. Check **inputs satisfiable** from IR (or emit `CLARIFY`).
3. Pick by policy: reliability > cost > latency (deterministic tiebreak).
4. Run tool; write outputs (`assertion`, `event`, `source`).
5. Check **postconditions** → resolve or escalate to next candidate.
6. If no tool resolves → create `DISCOVER_OP` (defer) or `JUSTIFY(failure)`.

**Verify loop (before reply)**

* For math/DB/rules: re-evaluate deterministically.
* For facts: cross-check against IR (existence, non-contradiction, provenance).
* Fail → replace with uncertainty message + `JUSTIFY/CLARIFY`.

---

## 6) Minimal tool set (MVP)

* `EvalMath` — exact arithmetic; satisfies `REPORT.math`, `VERIFY`.
* `TextOps.CountLetters` — satisfies `REPORT.count`.
* `PeopleSQL` — simple SELECT with adapter; `REPORT.query.people`.
* `TimeNow` — `REPORT.status.time`.
* `CalendarRead/Write` (read-only for MVP if you prefer) — `REPORT.schedule`, `ACHIEVE.schedule` (later).

---

## 7) Request lifecycles (tiny traces)

**A) “What’s 2+2?”**

* In → `REPORT.math("2+2")`
* Conductor → `EvalMath`
* Out → assertion `(Expr_1 evaluatesTo 4)` + event(tool\_run)
* Verify → recompute → pass
* Out LLM → “4”

**B) “List my friends in Seattle”**

* In → `REPORT.query.people(filters=[is_friend(user), city=Seattle])`
* Conductor → `PeopleSQL` (adapter maps filters)
* Tool → rows → assertions (`person(X) friend(user) city=Seattle`) + source
* Verify → count/type sanity
* Out LLM → names + “per contacts DB”

**C) “What’s your name?” (needs memory)**

* In → `REPORT.status.name`
* Conductor → `MemoryCheck`

  * If absent → `CLARIFY(name)` → user answer → `Save(name)` → assertion
* Out LLM → name

---

## 8) Prompts (thin, bounded)

**Translator–In system prompt (sketch)**

* “Map NL to obligations JSON. Use only the allowed types. Validate against this schema. Do not solve.”

**Translator–Out system prompt**

* “Given assertions & sources, render a concise answer. Include source notes when present. Avoid inventing.”

(Keep 6–8 few-shots each; enforce JSON schema on input side.)

---

## 9) Folder skeleton (Cursor-friendly)

```
/mvp
  /contracts
    obligations.schema.json
    tool.schema.json
    tools/
      evalmath.yaml
      people_sql.yaml
      textops_countletters.yaml
      adapters/
        people_sql_adapter.yaml
  /conductor
    plan.md           # algorithm notes (above)
    policy.md         # selection rules
  /db
    schema.sql        # tables listed above
    examples.sql      # seed rows shown above
  /prompts
    translator_in.md
    translator_out.md
  /ops
    evalmath.md       # IO & postconditions
    people_sql.md
    textops_countletters.md
  /observability
    trace_format.md   # what to log per run
  README.md
```

(You can turn each `.md/.yaml` into code later; MVP keeps them as specs.)

---

## 10) Metrics & traces (what to log)

* `event`: user text, obligations JSON, tool runs (name, inputs hash, outputs hash), verify result, final answer.
* `coverage`: % obligations resolved w/o escalate; clarify rate; verify fail rate.
* `latency`: per tool and end-to-end.

---

## 11) What to build first (bite-sized)

1. DB schema + tiny seed.
2. Translator–In with schema validation (no code gen).
3. Registry with **3 tools** (EvalMath, CountLetters, PeopleSQL + adapter).
4. Conductor: candidate selection → run → postcondition check → verify.
5. Translator–Out minimal.
6. Observability: one compact JSON trace per request.

That’s the MVP. From there, you just **add tools** and **tighten adapters**—the conductor, IR, and verify loop stay the same.
