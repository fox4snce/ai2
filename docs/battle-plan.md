# AI Organism MVP — Battle Plan (Plain-English)

> Goal in one line: **A deterministic “reasoning core” that takes structured tasks, picks safe tools, proves what it did, and gives you receipts.** LLMs only translate at the edges.

---

## 0) What we’re actually building (no buzzwords)

* **Input:** A small JSON task that says *what must be true* (e.g., “Is Alice Cara’s grandparent?”, “Make a meeting plan, but don’t actually schedule it”).
* **Core:** A tiny engine that **chooses tools** (math, text ops, database, rules), **runs them deterministically**, and **stores facts + proof** of how it got them.
* **Output:** A clean JSON answer plus a **trace** (what ran, what rules fired, budgets, why something was skipped). Optionally, an LLM turns that into pretty English.
* **Why it’s useful:** It’s **reliable and auditable**. Great for anything where you need *evidence*, not vibes.

**Non‑negotiables:**

1. Same input → **bit‑for‑bit same output**.
2. Every fact has **provenance** (which rule/tool produced it).
3. **No side effects** during planning mode.
4. **Safety gates** on tools (capabilities, network/file access, secrets).

---

## 1) This week’s “Show Me” demo (10 minutes, no cuts)

Run exactly these five obligations live, then re-run on a fresh machine and show identical outputs + traces:

1. **Multi‑hop logic (REPORT.logic)**
   *Question:* Is Alice a grandparent of Cara?
   *Data:* `parentOf(Alice, Bob)`, `parentOf(Bob, Cara)`.
   *Expect:* `true`, with a single **canonical** proof path (store alternates too).

2. **Bounded plan (ACHIEVE.plan)**
   *Goal:* “Propose a meeting plan for Mon–Fri 9–5 if both people are free.”
   *Expect:* A **list of steps only** (ResolvePerson → CheckCalendar → ProposeSlots → CreateEvent). **No writes** to the world.

3. **Ambiguous entity (CLARIFY)**
   *Input:* “Email Dana the plan.” (Two Danas in DB.)
   *Expect:* Engine stops and returns a **clarify payload** (which fields it needs). Store the clarify event in the trace.

4. **Guardrails (MAINTAIN/AVOID)**
   *Input:* “Schedule only if constraints X/Y hold.”
   *Expect:* Guard stops execution if violated. Return a **justification** for the stop.

5. **Budget truncation**
   *Set:* `max_depth = 1` or tiny `time_ms`.
   *Expect:* `status: "truncated"`, partial trace, **clean rollback** (no side effects).

**Numbers to capture on the same run:** P50/P95 latency, CPU/RAM per obligation type, throughput at N=32 and N=128, and cost with vs without LLM translator.

---

## 2) Minimal architecture you need (keep it tiny)

* **Tool registry (YAML):** `name, inputs, outputs, satisfies, supports, preconditions, postconditions, VERIFY_MODE (off|non_blocking|blocking), capability_tier`.
* **IR DB (tables):** `entity, relation, assertion, event, source, obligation, tool_run, rule, trajectory`.
* **Conductor (the loop):** match obligation → candidate tools → pick deterministically (Reliability > Cost > Latency > **stable tiebreak** using a hash of `(obligation_id, tool_name)`) → run → verify → write assertions/events → mark resolved/clarify/failed/truncated.
* **Reasoning.Core:**

  * *Deduction:* Forward‑chain over simple rules (Datalog/Prolog‑lite). Every derived fact gets `proof_ref` + `rule_version`.
  * *Planning:* Bounded search (`max_depth`, `beam`, `time_ms`). **Actions are tool postconditions.** Planning writes only a plan artifact, never world state.
* **Trace JSON (frozen format):** `{ run_id, obligations[], tools_used[], rules_fired[], verify[], budgets, why_not[], duration_ms }` with deterministic ordering.
* **Clarify handshake:** When ambiguous, return `{status:"clarify", need:[…], options:[…]}` and log it as an `event(payload_jsonb)`.
* **Deterministic LLM edges:** When used for NL→JSON or JSON→NL, force **JSON Schema**, validate, and log the raw prompt + response for replay (or return a refusal cleanly).

---

## 3) Day‑by‑day plan (7 days)

**Day 1 — Skeleton + schema**

* Lock `trace_format.json`, tool YAML schema, and IR tables.
* Implement **stable tiebreak** and **identity policy**: how we decide two records are the same (aliases, stable IDs).

**Day 2 — Three tools + conductor loop**

* Ship `EvalMath`, `TextOps.CountLetters`, `PeopleSQL` adapters.
* Build routing (capability match) and verify modes (off/non‑blocking/blocking).
* Write/read assertions with `proof_ref` and `source`.

**Day 3 — Reasoning.Core (deduction)**

* Load a few rules (e.g., grandparent via parent).
* Forward‑chain + produce proof‑carrying assertions.
* Unit tests: positive, negative, multi‑path → canonical trajectory.

**Day 4 — Planning (no side effects) + budgets**

* Bounded search that only emits steps; never writes world state.
* Budget enforcement + `status:"truncated"` behavior.

**Day 5 — Clarify loop + sandbox**

* Implement clarify handshake + store events.
* Tool sandboxing: capability gating, network/file allowlist, secrets vault.

**Day 6 — Determinism harness + metrics**

* CLI that runs the **five demo obligations**, prints **trace JSON**.
* Re-run on fresh machine; prove bit‑for‑bit identical outputs.
* Add counters: P50/P95 latency, CPU/RAM, throughput at 32 & 128.

**Day 7 — Demo polish + README**

* "Proof Packet": README + three tiny seed datasets + scripts for the five demos.
* Optional MCP server wrapper + one client (VS Code or simple CLI).

---

## 4) Tests you must pass (green bars)

* **Deduction:** positive/negative/multipath; derived facts carry `proof_ref` + `rule_version`.
* **Type safety:** bad rules/tools rejected at load with clear trace errors.
* **Budgets:** truncation returns partial trace, **no side effects**.
* **Clarify:** multiple matches trigger `status:"clarify"` with payload.
* **Verify policy:** any **blocking** sub‑verify fails → entire response fails.
* **Routing:** `REPORT.logic` routes to Reasoning.Core before any fallback.

---

## 5) Safety, correctness, replay (plain answers to hard questions)

* **Do we assume unknown = false?** Inside this system, treat it as **closed‑world per dataset**: if we don’t have a fact, we can’t assert it’s true. We can output “unknown”.
* **How do we fix wrong facts?** Every assertion points to a **justification** (the `proof_ref`). To retract, we mark the source or rule invalid and re‑derive. (Add a simple Truth‑Maintenance pass in Phase 4.)
* **Time & validity windows?** Facts can have `valid_from/valid_to`. Temporal rules arrive in Phase 4.
* **Types & units?** Types are first‑class; add units later. If two “John Smiths” exist, the system **clarifies** instead of guessing.
* **Planning safety?** Planning cannot write world state. Only an explicit “execute” step (later) can, under policy.
* **Concurrency & idempotency?** Use DB transactions + `tool_run(idempotency_key)` to ensure exactly‑once writes.
* **Security?** Each tool declares capabilities. The runner enforces **least privilege** + outbound network policy + secrets vault.
* **LLM drift?** Edges are schema‑checked. If the LLM refuses or returns junk, we return a clean error—core stays deterministic.

---

## 6) Pick a simple wedge to sell (choose one to start)

1. **Scheduling with evidence (fastest to demo).**

   * Examples: “Only schedule if constraints X/Y hold; give me the proof bundle.”
   * Buyers: Internal IT/ops teams; safer than chatty assistants.

2. **Compliance playbooks (higher value, slower).**

   * KYC refresh, adverse media checks, policy attestations with proof bundles.
   * Buyers: FinServ/Healthcare compliance.

3. **Data quality checks for data teams.**

   * Deterministic assertions with explainable rule fires → PR comments.

**Landing plan:** 2–3 design partners; open‑source the core (AGPL/BUSL) to seed adoption; sell a **control plane** (tenancy, policy, dashboards, MCP, SSO) and on‑prem.

---

## 7) Roadmap after the demo (phased, plain talk)

**Phase 0 → 1 (Now → 1 month):** Ship the demo + Proof Packet; freeze schemas; finish sandboxing & verify modes; trace UI v0 (searchable tree + “why not?” panel).
**Phase 2 (1–3 months):** Wedge: build 3–5 repeatable playbooks + exportable proof bundles; MCP integration solid.
**Phase 3 (2–4 months):** **Truth Maintenance** (retractions/conflicts), **temporal reasoning**, and a basic **policy engine** to gate tool execution at runtime.
**Phase 4 (3–6 months):** **Operator discovery loop**: mine traces → suggest macros → stability tests before adoption. Start publishing domain packs.
**Phase 5 (6–9 months):** Control plane (multi‑tenant, RBAC, SSO), benchmarks (solve‑rate/latency vs incumbents), and pricing.

---

## 8) What to measure and publish

* **Determinism report:** identical traces across runs/hosts.
* **Latency & cost:** P50/P95 per obligation; cost with vs without LLM edges.
* **Throughput:** N=32/128 concurrency on a single machine.
* **Coverage:** pass‑rate on your demo suite + a small public multi‑hop set (CLUTRR‑style).

---

## 9) Risks to watch (and how we dodge them)

* **Ambiguity hell:** If identity/canonicalization is weak, you’ll stall. *Fix:* clear identity policy + clarify loop.
* **Planner creep:** If planning does side effects, trust dies. *Fix:* hard rule: planning only emits steps.
* **LLM nondeterminism:** If edges leak inside, you lose repeatability. *Fix:* strict schemas + refusal paths.
* **Scope spread:** Trying to be a general agent. *Fix:* pick one wedge, master it, then expand.

---

## 10) Deliverables checklist (print this and tick boxes)

* [ ] **Trace format frozen** (file + example).
* [ ] **Tool YAML schema** (`VERIFY_MODE`, `supports` vs `satisfies`, capabilities).
* [ ] **IR tables** (with `rule_version`, `proof_ref`, identity policy).
* [ ] **Three tools** (Math, Letters, PeopleSQL).
* [ ] **Reasoning.Core** (deduction + planning stub).
* [ ] **Clarify handshake** (status + payload).
* [ ] **Budgets + truncation** (no side effects).
* [ ] **Sandbox & secrets** (least privilege).
* [ ] **Determinism harness** (bit‑for‑bit replays).
* [ ] **Metrics** (P50/P95, CPU/RAM, throughput).
* [ ] **Proof Packet** (README + 5 demo scripts + tiny seed data).
* [ ] **(Optional) MCP wrapper** + one client.

---

## 11) FAQs for partners (plain answers)

* **Can I make my own domain?** Yes. Add your rules and tools; the engine stays deterministic and gives you receipts.
* **Can I skip the LLM?** Yes. You can feed obligations directly and get JSON answers + proofs.
* **Why is this better than an agent with a prompt?** Because you get **proof‑carrying outputs** and **repeatability**. Auditors love that.

---

**That’s the battle plan.** It’s intentionally boring, small, and testable—so it ships. 