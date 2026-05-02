---
plan: 13-03-skills-as-first-class-tools
phase: 13-unified-tool-registry-tool-search-meta-tool
status: complete
commit: 7b04920
tests: 16 passed (9 pre-existing + 7 new)
---

# Plan 13-03 — Skills as First-Class Tools

## What was built

D-P13-02 skill registration: a new `register_user_skills(user_id, token)`
async helper in `skill_catalog_service.py` plus a `_make_skill_executor(name)`
closure factory. Each enabled skill becomes a `source="skill"`,
`loading="deferred"` registry entry with a parameterless OpenAI schema; the
executor delegates to `ToolService.execute_tool("load_skill", {"name": skill_name}, ...)`
so no skill-loading logic is duplicated.

## Files modified

| File | Change | LOC |
|------|--------|-----|
| `backend/app/services/skill_catalog_service.py` | Additive: `register_user_skills` + `_make_skill_executor`. Legacy `build_skill_catalog_block` byte-identical. | +112 |
| `backend/tests/unit/test_skill_catalog_service.py` | Appended 7 Phase 13 tests; pre-existing 9 untouched. | +173 |

## API surface

```python
async def register_user_skills(user_id: str, token: str) -> None:
    """Per-request RLS-scoped query → register every enabled skill as
    source='skill', loading='deferred'. Fail-soft on DB errors."""

def _make_skill_executor(skill_name: str) -> Callable[..., Awaitable[dict | str]]:
    """Closure factory: captures skill_name via default-arg `_name=skill_name`
    (late-binding fix). Closure delegates to
    ToolService.execute_tool('load_skill', {'name': _name}, ...)."""
```

## Tests (16 passed total)

| Range | Coverage |
|-------|----------|
| 9 pre-existing | `build_skill_catalog_block` byte-identical (TOOL-05 invariant) |
| Test 1 | 2 enabled skills → 2 entries with source='skill', loading='deferred' |
| Test 2 | Schema is exact OpenAI parameterless shape |
| Test 3 | Falsy token → no DB call, no registration |
| Test 4 | DB exception → WARNING logged, no propagation, registry empty |
| Test 5 | Zero rows → no registration |
| Test 6 | Each closure delegates to `execute_tool('load_skill', {'name': skill_name})` (late-binding fix verified) |
| Test 7 | Re-running idempotent — first-write-wins kept original; WARNINGs logged |

## TOOL-05 byte-identical invariant

```
$ git diff backend/app/services/skill_catalog_service.py | grep -c "^-[^-]"
0
```

The legacy `build_skill_catalog_block` function (lines 54-112) was not
modified. All 9 pre-existing tests still pass.

## What's NOT in this plan

- chat.py call site for `register_user_skills(user_id, token)` → Plan 13-05
- `tool_search` matcher (which discovers these deferred skills) → Plan 13-04
- Frontend UI changes — none.

## Self-Check: PASSED

- [x] `pytest tests/unit/test_skill_catalog_service.py -v` → 16 passed
- [x] `python -c "from app.main import app"` → OK
- [x] `git diff` shows additive only on production file
- [x] Late-binding fix verified by Test 6 with 2 distinct skills
