---
plan: 13-02-native-tool-adapter-wrap
phase: 13-unified-tool-registry-tool-search-meta-tool
status: complete
commit: 47d4995
tests: 6 passed
---

# Plan 13-02 — Native Tool Adapter Wrap

## What was built

D-P13-01 adapter pattern: an additive bootstrap function at the bottom of
`tool_service.py` enumerates `TOOL_DEFINITIONS` and registers each native with
`source="native"`, `loading="immediate"`, and an executor closure that
delegates back into `ToolService.execute_tool`. Gated by
`settings.tool_registry_enabled` so flag-off is byte-identical to v1.1.

## Files modified

| File | Change | LOC |
|------|--------|-----|
| `backend/app/services/tool_service.py` | Additive splice at module bottom (after line 1283). Pre-existing 1,283 LOC unchanged. | +66 |
| `backend/tests/unit/test_tool_registry_natives.py` | NEW — 6 tests | new |

## Native tools registered

`len(TOOL_DEFINITIONS) == 12` natives at the time of this plan. Each
registers via `tool_registry.register(name, description, schema=tool, source="native", loading="immediate", executor=closure)`.

## Bootstrap signature

```python
def _register_natives_with_registry() -> None:
    """D-P13-01: enumerate TOOL_DEFINITIONS once and register each as a native tool."""
    if not settings.tool_registry_enabled:
        return  # TOOL-05: byte-identical fallback — registry NOT imported
    from app.services import tool_registry  # lazy import inside the gate
    _svc = ToolService()  # module-local instance; chat.py owns its own
    for tool in TOOL_DEFINITIONS:
        ...
```

## Tests (6 passed)

| Test | What it locks |
|------|---------------|
| `test_no_import_when_flag_off` | Subprocess: `TOOL_REGISTRY_ENABLED=false → "app.services.tool_registry" not in sys.modules` after importing tool_service. **TOOL-05 invariant.** |
| `test_subset_registration` (warning C fix) | Subset check `{names} <= set(_REGISTRY.keys())` — resilient to 13-04 self-registering tool_search (would break a count-equality assertion). |
| `test_all_natives_have_correct_source_and_loading` | Every entry: source='native', loading='immediate'. |
| `test_schema_and_description_match_tool_definitions` | `td.schema == TOOL_DEFINITIONS[entry]` (full top-level dict) and `td.description == entry["function"]["description"]`. |
| `test_executor_delegates_to_execute_tool_with_captured_name` | AsyncMock on ToolService.execute_tool; assert each closure invokes execute_tool with its OWN captured name (no late-binding leak). |
| `test_register_idempotent_on_clean_registry` | Clear + re-run produces identical registration set. |

## D-P13-01 byte-identity invariant

```
$ git diff backend/app/services/tool_service.py | grep -c "^-[^-]"
0
```

No deletions in the diff — entirely additive. Lines 1-1283 of tool_service.py
are byte-identical to the pre-13-02 commit.

## What is intentionally NOT in this plan

- Skill registration helper (`register_user_skills`) → Plan 13-03
- `tool_search` self-registration + matcher → Plan 13-04
- `chat.py` flag-gated splices → Plan 13-05

## Self-Check: PASSED

- [x] `pytest tests/unit/test_tool_registry_natives.py -v` → 6 passed
- [x] `python -c "from app.main import app"` → OK
- [x] `git diff backend/app/services/tool_service.py | grep -c "^-[^-]"` → 0
- [x] Subprocess no-import test confirms TOOL-05 invariant
- [x] Adapter delegates to `ToolService.execute_tool` (no logic re-implementation)
