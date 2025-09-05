Short answer: make VERIFY **selective, per-obligation, and capability-aware**—not global. For the MVP:

### The rule of thumb

* **Deterministic, cheap ops (math, count, SQL with constraints)**

  * **Mode:** *inline fast-check* (non-blocking)
  * **Action:** run tool → do its own postcondition check → emit result immediately → log `verify:pass`.
* **Non-deterministic / external / fuzzy ops (web cite, OCR, LLM text, heuristic joins)**

  * **Mode:** *blocking*
  * **Action:** hold answer until verify ops pass (source present, constraints satisfied, no contradiction).

### How to wire it

* **Capability tiers** (on each tool):

  * `deterministic` → non-blocking verify
  * `trusted-db` (PK/constraints) → non-blocking verify
  * `probabilistic` / `external` → blocking verify
* **Per-obligation setting**:

  * `REPORT.math`, `REPORT.count`, `REPORT.query.people` (via DB) → non-blocking
  * `REPORT.fact.web`, `JUSTIFY`, anything touching LLM output → blocking
* **Aggregator** (per response):

  * Track verify per sub-obligation; final status = **fail if any required sub-obligation fails**.
  * Don’t let one “PASS” mask other failures.

### During decomposition phase (now)

* **Turn OFF global verify.**
* Rely on **tool postconditions**.
* Enable verify **only** where the obligation demands it or the tool’s capability tier requires it.
* Log verify results, but don’t block unless tier says so.

### Tiny examples

* “What’s 2+2?” → `EvalMath` (deterministic) → non-blocking verify → print `4`.
* “List friends in Seattle” → `PeopleSQL` (trusted-db) → non-blocking verify (row/type checks) → print names.
* “When did X happen? (cite)” → `CiteWeb` (external) → **blocking** verify (must have source + consistency) → then print.

### Config (simple)

* `VERIFY_MODE` per tool: `off | non_blocking | blocking`
* Default per capability tier; override per obligation if needed.

This keeps answers snappy where they’re safe, and prevents “PASS” from papering over unmet parts.
