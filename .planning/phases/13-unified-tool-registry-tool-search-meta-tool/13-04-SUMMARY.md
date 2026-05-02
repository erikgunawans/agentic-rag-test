---
plan: 13-04-tool-search-meta-tool-active-set
phase: 13-unified-tool-registry-tool-search-meta-tool
status: complete
commit: 0e3b4c8
tests: 15 new (test_tool_search) + 4 cross-plan fixture updates
---

# Plan 13-04 — tool_search Meta-Tool

## What was built

The `tool_search` meta-tool that lets the LLM discover deferred-loading tools
by keyword (case-insensitive substring) or regex (re.search, IGNORECASE).
Matched tools are added to the per-request `active_set` so they appear in
the LLM tools array for the rest of the turn.

Self-registers as `source="native"`, `loading="immediate"` so it always
appears in the LLM tools array — but is excluded from the catalog table rows
(only the meta-callout line in `_CATALOG_HEADER` advertises it).

## Files modified

| File | Change | LOC |
|------|--------|-----|
| `backend/app/services/tool_registry.py` | Appended `tool_search` async function, `_score_match`, `_register_tool_search`, `_TOOL_SEARCH_SCHEMA`. Updated `_clear_for_tests` to re-register tool_search. | +175 |
| `backend/tests/unit/test_tool_search.py` | NEW — 15 unit tests | new |
| `backend/tests/unit/test_tool_registry.py` | Updated 2 tests (Test 7: empty-registry → `{tool_search}` baseline; Test 11: build_llm_tools empty → `{tool_search}` schema) | +4 / -2 |
| `backend/tests/unit/test_tool_registry_natives.py` | Updated idempotency test to subset check (no `_REGISTRY == {}` assertion) | +3 / -1 |
| `backend/tests/unit/test_skill_catalog_service.py` | Updated 5 tests to check `source='skill'` count instead of total registry equality | +12 / -5 |

## Public API

```python
async def tool_search(
    *,
    keyword: str | None = None,
    regex: str | None = None,
    active_set: set[str] | None = None,
    agent_allowed_tools: list[str] | None = None,
) -> dict:
    """Returns {"matches": [<full openai schemas>...], "hint": str|None, "error": str|None}"""
```

## Result-shape contract

| Input | Returned `error` | `hint` | `matches` | `active_set` |
|-------|------------------|--------|-----------|--------------|
| both null | "either keyword or regex required" | None | [] | not mutated |
| both set | None | "regex wins when both keyword and regex are passed" | regex matches only | mutated with regex matches |
| regex > 200 chars | "regex pattern too long (max 200 chars)" | (preserves both-set hint) | [] | not mutated |
| invalid regex | "invalid regex: ..." | (preserves both-set hint) | [] | not mutated |
| valid keyword | None | None | top 10 by ranking | mutated |
| valid regex | None | None | top 10 by ranking | mutated |

## Ranking algorithm

```
sort key = (-match_class, -span_len, name_lower)
match_class: 2 = name match, 1 = description match
span_len: matched substring length (longer span sorts first)
name_lower: alphabetical tiebreaker
```

After `tool_search` self-exclusion and `_passes_agent_filter`, top 10 returned.

## Regex safety

- **Length cap**: patterns > 200 chars rejected without `re.compile`.
- **Compile error**: `re.error` caught and returned as `{"error": "invalid regex: ..."}`.
- **DoS smoke test**: `tool_search(regex="A"*250)` returns in < 100ms (verified inline).

## Self-exclusion + agent filter

- `tool_search` never matches itself (D-P13-04).
- `_passes_agent_filter` reused: skill bypass + tool_search always-on; native/mcp gated by `agent.tool_names`.

## Test 7 baseline change (controlled cross-plan edit)

Plan 13-01's Test 7 (`test_registry_empty_at_module_load`) asserted
`_REGISTRY == {}`. After 13-04 self-registers tool_search at module load,
the clean baseline is `{tool_search}`. Renamed to
`test_registry_only_contains_tool_search_at_clean_state` and updated the
assertion. Plan 13-01's `_clear_for_tests` was also updated to re-register
tool_search, matching production module-load state.

Other 13-01 tests (build_llm_tools / build_catalog_block) were independent —
they `_register(...)` their own fixtures on top of the cleared state, so they
naturally include tool_search in the registry now (and the catalog formatter
still excludes it from rows per D-P13-04).

## TOOL-02 / TOOL-03 satisfied

- TOOL-02 (LLM can call tool_search, receives matches + active set updated): ✓
- TOOL-03 (active set is caller-owned; no cross-request persistence in registry): ✓

## What's NOT in this plan

- chat.py wiring of `active_set` and `agent_allowed_tools` into the executor
  context dict → Plan 13-05.

## Self-Check: PASSED

- [x] `pytest tests/unit/test_tool_search.py -v` → 15 passed
- [x] `pytest tests/unit/test_tool_registry.py tests/unit/test_tool_registry_natives.py tests/unit/test_skill_catalog_service.py tests/unit/test_tool_search.py` → 63 passed
- [x] `python -c "from app.main import app"` → OK
- [x] Regex DoS smoke: 250-char pattern returns in < 100ms with structured error
- [x] All 5 D-P13-05 requirements verified (keyword/regex/both-null/both-set/regex-wins)
