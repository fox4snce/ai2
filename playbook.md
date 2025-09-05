# The Obligations → Operations Playbook

*(aka: LLM as Translator, Everything Else as Process)*


## 0) The Big Idea (Why this isn’t just “more RAG”)

* **LLMs ≠ universal solver.** They’re insanely good **translators** between natural language and structure.
* **Reasoning/doing** lives in **processes** (tools): math, search, planning, control, DB queries, sims, tiny NNs, etc.
* We glue it together with a tiny, universal **idea representation** (IR) living in a **DB/graph**, not inside the prompt.
* We drive behavior with **Obligations** (“what must hold”) and satisfy them with **Operations** (“how we do it”).

Result: transparent, testable, upgradable intelligence that doesn’t drown in context windows.

---

## 1) The Substrate (Idea-IR as a DB/Graph)

Think “relational+graph” that stores meaning, not tokens.

**Core atoms**

* **Entity** — a thing (person, task, document, sensor, concept)
* **Relation** — typed edge between entities (Alice —parentOf→ Bob)
* **Modifier** — attributes on entities/relations (priority=high, tone=friendly)
* **Event** — something that occurred (a question asked, a tool run)
* **Assertion** — a claim about anything (Expr\_1 evaluatesTo 4) with confidence & provenance

**Provenance & time**

* Source, timestamp, method (“calculated by EvalMath v1.2”)
* Versioning/supersedes — never overwrite, append facts

**Patterns**

* Query-shaped subgraphs with holes (e.g., “friends(User) who live in Seattle”)

This is your **memory**. It lives **outside** the LLM and survives every turn.

---

## 2) Obligations (the “What must hold”)

Keep the set tiny and universal:

* **REPORT(q)** — produce an answer/explanation
* **ACHIEVE(s)** — make a state true
* **MAINTAIN(p)** — keep a predicate true
* **AVOID(p)** — keep a predicate false
* **JUSTIFY(c)** — show reasons/provenance
* **SCHEDULE(e,t)** — bind an action to time
* **CLARIFY(slot)** — ask for missing info
* **VERIFY(ans)** — check before sending
* **DISCOVER\_OP(goal)** — we don’t have a tool; find or draft one

Everything you’ll do is a combo of these.

**Examples**

* “What’s 2+2?” → `REPORT(math.eval("2+2"))`
* “Keep the ball on the table.” → `MAINTAIN(ball.on_table) + AVOID(ball.fallen)`
* “Book lunch with Dana tomorrow 1pm PT.” → `ACHIEVE(event.scheduled(…)) + SCHEDULE(… ) + JUSTIFY(source=calendar)`

---

## 3) Operations (the “How we do it”)

A **tool** is an operation with a contract. It’s a small, deterministic program (or a tiny NN inside) that declares:

* **Inputs (IR types)** — what it consumes
* **Outputs (IR types)** — what it writes back
* **Preconditions / Postconditions** — truth you can check
* **Can satisfy** — which obligations it fulfills
* **Cost/latency/reliability** — for choosing among tools

**Examples**

* `EvalMath` → parses & evaluates expressions; satisfies `REPORT(math)` and `VERIFY`
* `PeopleSQL` → runs person queries; satisfies `REPORT(query:people)`
* `ComputeControl_PID` → returns plate tilts; satisfies `MAINTAIN(ball.centered)` partially
* `EstimateState` → from sensors to position/velocity; prerequisite for control
* `CiteWeb` or `RetrieveKB` → satisfies `JUSTIFY`/`REPORT` with sources

**Adapters** translate generic IR filters (e.g., `lives_in(Seattle)`) to tool-specific params (e.g., `city='Seattle'`). Deterministic, no vibes.

---

## 4) The Conductor (selection, sequencing, monitoring)

The Conductor is a thin policy engine that:

1. **Reads obligations**
2. **Back-chains** from tool postconditions (affordances) to pick a minimal set of operations
3. **Executes** in a small loop
4. **Checks postconditions**

   * met → done
   * unmet → escalate (alternate tool), `CLARIFY`, or `DISCOVER_OP`

**No “scoring” by the LLM.** The Conductor uses set inclusion, constraints, and postcondition checks. Think: tiny planner + set cover + guards.

**Monitoring**

* Every turn: “Did the obligation hold?” If not, we don’t bluff — we repair or ask.

---

## 5) Where the LLM fits (and stops)

Two narrow roles, both swappable:

1. **Input Translator**
   NL → obligations + pattern query → STRICT schema

   * Few shots, schema validation, re-emit on error
   * No free text, no scoring, no tool names

2. **Output Translator**
   IR → human-readable NL answer, with optional sourcing/justification

   * Can be fine-tuned later for style, but not required

**Optional:** LLM “toolsmith” only when `DISCOVER_OP` fires — draft a new tool spec under human review.

---

## 6) Retrieval without Prompt Bloat (RAG, the right way)

* Retrieval lives **inside the IR** as **pattern matching**, not dumping text.
* `REPORT:query:people(conditions=[is_friend(user), lives_in(Seattle)])`

  * Conductor picks `PeopleSQL`
  * Adapter compiles to SQL
  * Results stored as `Assertion(person(X) & friend(User) & city=Seattle)`

No giant context; just the **few fragments** a tool needs.

---

## 7) The Verify Reflex (teach it to know when it doesn’t know)

Before answers leave:

* **VERIFY(ans)** triggers:

  * Deterministic recompute (math, DB, rule engine)
  * Consistency check against memory (“does this contradict?”)
  * Confidence/provenance sanity (do we *have* a source?)

Fail → `JUSTIFY(failure)` + `CLARIFY` or a friendly “I’m not certain; want me to check X?”

---

## 8) End-to-End Micro-Traces

**A) Counting letters**
User: “How many r’s in ‘strawberry’?”

1. Translator → `REPORT:count:letter_frequency(letter='r', word='strawberry')`
2. Conductor → picks `TextOps.CountLetters`
3. Tool → writes `Assertion(letter_frequency(...)=2)` with provenance
4. VERIFY (deterministic repeat) → pass
5. Output Translator → “2”

**B) People in Seattle**
User: “List friends who live in Seattle.”

1. `REPORT:query:people(conditions=[is_friend(user), lives_in(Seattle)])`
2. Conductor → `PeopleSQL`
3. Adapter → SQL; results stored with sources
4. VERIFY → cross-check counts/types
5. Output → names + “(per your contacts DB on <date>)”

**C) Ball on table**
User: “Keep the ball centered.”

1. `MAINTAIN(|x|,|z|<r) + AVOID(fall)`
2. Conductor → loop: `EstimateState` → `ComputeControl_PID` → `SafetyClamp` → `Actuate`
3. Monitor → if unmet, escalate to `LQR` or add residual learner; log events/provenance

**D) Book lunch**
User: “Book lunch with Dana tomorrow 1pm PT.”

1. `ACHIEVE(event.scheduled(person=Dana,time=…)) + SCHEDULE + JUSTIFY`
2. Conductor → `ResolvePerson` (CLARIFY if 2 Danas) → `CalendarCheck` → `CreateEvent`
3. VERIFY → event exists, invite sent
4. Output → confirmation + source link

---

## 9) Avoiding Domain Explosion

* **Domains = tools.** You don’t write new “grammars” per domain; you add tools with contracts.
* The **IR stays stable**: entities, relations, modifiers, events, assertions, patterns.
* Coverage grows by registering tools; the Conductor’s affordance match scales cleanly.
* Missing coverage isn’t a crash; it’s a **meta-obligation**: `DISCOVER_OP` (search, ask, or draft a tool).

---

## 10) Debugging & Transparency

Every answer is traceable:

* Obligations received
* Tools chosen and why (pre/postconditions matched)
* Inputs supplied (from IR, not vibes)
* Outputs produced (assertions with provenance)
* VERIFY result
* Final NL rendering

If something’s wrong, you can **point to the step** — no “the model just said so.”

---

## 11) Safety, Policy, and Practical Stuff

* **Auth & scopes** live as constraints on tools (e.g., Calendar write vs read).
* **Rate limiting / cost** in the tool registry; the Conductor can choose cheaper tools first.
* **Privacy**: IR can carry sensitivity tags; some assertions never leave the box.
* **Consolidation**: periodic dedupe/decay; keep memory tidy.
* **Style**: output translator handles tone; memory stores user prefs (concise, emoji, etc.).

---

## 12) Build Order (no code, just milestones)

**Phase 0 — Skeleton**

* IR tables/graph: Entities, Relations, Modifiers, Events, Assertions, Sources
* Obligation schema & validator
* Tiny Conductor loop (select → run → check → escalate)

**Phase 1 — Bread-and-butter tools**

* `EvalMath`, `PeopleSQL/Graph`, `TextOps`, `TimeNow`, `CalendarRead/Write`
* Adapters for filters/params
* Output translator for basic phrasing

**Phase 2 — Memory & Verify**

* Provenance everywhere; VERIFY hooks (math/DB consistency)
* CLARIFY loop for missing slots
* Basic consolidation & conflict resolution

**Phase 3 — Control/Planning spice**

* `EstimateState`, `ComputeControl_PID`, `SafetyClamp`
* A planner tool (A\* / simple task planner)

**Phase 4 — Toolsmith (optional)**

* Only when `DISCOVER_OP` fires: draft tool spec via LLM; human review; register

---

## 13) Mental Model Cheatsheet

* **Obligations** = requirements; **Operations** = capabilities.
* **IR** = shared language; **Adapters** = dialect bridges.
* **Conductor** = tiny planner; **LLM** = translator + occasional toolsmith.
* **VERIFY** = reflex before speech; **Memory** = facts with receipts.

---

## 14) FAQ (super short)

* *Isn’t this just old chatbots?*
  No — chatbots stuffed rules into prompts. We separate **meaning (IR)** from **doing (tools)** and keep LLMs at the edges.

* *Why not fine-tune the LLM?*
  Keep it dumb and constrained. Power lives in tools + IR. Swap LLMs anytime.

* *What about creativity?*
  Use the output translator for prose, stories, UX tone. Keep factual stuff verified.

* *Won’t we need tons of tools?*
  You’ll add them over time, but each is small. The IR and Conductor don’t change.

