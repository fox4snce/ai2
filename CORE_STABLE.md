# Core-Stable Release

**Date**: 2025-12-14  
**Tag**: `core-stable`

## Summary

This release marks the core system as stable with verified cache invalidation, capability budgeting, verification evidence, and package management.

## Key Features Implemented

### 1. Cache Invalidation with Dependencies
- ✅ Tool contracts support `depends_on` field
- ✅ Cache invalidates on:
  - File mtime/size changes (`filesystem:path`)
  - Environment variable changes (`env:VAR_NAME`)
  - Database file changes (`db:path`)
  - Tool version changes (automatic)
  - Clock dependencies (`clock` - minute-level granularity)

### 2. Verification Evidence System
- ✅ Verification checks stored as evidence objects in IR
- ✅ Evidence includes: check type, method, expected/actual values, comparison results
- ✅ Full audit trail of what was verified and how

### 3. Capability Budgeting
- ✅ Enforced limits on:
  - `max_tool_runs`
  - `max_cache_misses`
  - `max_toolsmith_calls`
  - `max_external_access`
- ✅ Budgets configurable per request
- ✅ Usage tracked and reported in traces

### 4. Package Management for Generated Tools
- ✅ Generated tools have metadata:
  - owner, created_at, created_from_trace
  - tests, status (experimental/stable/deprecated)
  - contract_path, implementation_path
- ✅ PackageManager for lifecycle management
- ✅ Automatic metadata creation by toolsmith

### 5. Cache Hit Tracking
- ✅ Tool runs marked with `cache_hit: true/false`
- ✅ Cache hits have near-zero duration
- ✅ Test verification of cache behavior

## Verification

### Cache Invalidation Abuse Test
- ✅ Environment variable change invalidates cache
- ✅ File dependency change invalidates cache  
- ✅ Tool version change invalidates cache
- ✅ Test report: `~/.ai2_reports/cache_invalidation_real_*.json`

### Test Results
```
Run 1: 1 execution (no cache)
Run 2: 0 executions, 1 cache hit (cached)
Run 3 (after env change): 1 execution, 0 cache hits (cache invalidated)
Answer changed from 'test_value1' to 'test_value2' ✓
```

## What This System Guarantees

See `README.md` for full guarantees. Key points:
- Deterministic execution
- Cache safety with dependency invalidation
- Complete provenance
- Verification evidence
- Capability budgeting
- Package management

## What It Explicitly Does Not Do

See `README.md` for full list. Key points:
- No LLM-based tool selection
- No prompt engineering for reasoning
- No context window bloat
- No silent failures
- No magic strings

## Files Changed

- `README.md` - Added guarantees and limitations sections
- `mvp/src/core/cache.py` - Dependency hash computation
- `mvp/src/core/tools.py` - `depends_on` support in contracts
- `mvp/src/conductor/conductor.py` - Cache hit tracking, capability budgets
- `mvp/src/core/database.py` - Verification evidence storage
- `mvp/src/core/packages.py` - Package management (new)
- `mvp/db/schema.sql` - Verification evidence table
- `mvp/schemas/tool.schema.json` - `depends_on` field
- `mvp/tests/test_workflow_email_domains_adult_demo.py` - Cache verification
- `mvp/tests/test_cache_invalidation_abuse.py` - Abuse tests
- `mvp/tests/test_cache_invalidation_real.py` - Real dependency tests

## Next Steps

1. Continue abuse testing with file dependencies
2. Add more tool examples with dependencies
3. Monitor cache hit rates in production
4. Expand verification evidence types
