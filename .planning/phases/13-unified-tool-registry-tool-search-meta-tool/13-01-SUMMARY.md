---
plan: 13-01-tool-registry-foundation
phase: 13-unified-tool-registry-tool-search-meta-tool
status: complete
commit: 82a0941
tests: 26 passed
---

# Plan 13-01 — Tool Registry Foundation

## What was built

The Phase 13 unified tool registry's foundational primitives. Wave 2 plans
(13-02 native adapter wrap, 13-03 skills-as-tools, 13-04 tool_search) all
depend on these primitives existing.

## Files created / modified

| File | Change | LOC |
|------|--------|-----|
| `backend/app/models/tools.py` | Added `ToolDefinition` Pydantic model (6 fields, Literal validation on source/loading) | +27 |
| `backend/app/config.py` | Added `tool_registry_enabled: bool = False` flag (env: `TOOL_REGISTRY_ENABLED`) | +4 |
| `backend/app/services/tool_registry.py` | NEW — registry primitives (~210 LOC) | new |
| `backend/tests/unit/test_tool_registry.py` | NEW — 26 unit tests | new |

## Public API surface

```python
# app.models.tools
class ToolDefinition(BaseModel):
    name: str
    description: str
    schema: dict
    source: Literal["native", "skill", "mcp"]
    loading: Literal["immediate", "deferred"]
    executor: Callable[..., Awaitable[dict | str]]

# app.services.tool_registry
def register(name, description, schema, source, loading, executor) -> None
    # First-write-wins on duplicate name; logs WARNING and ignores.

def make_active_set() -> set[str]
    # Fresh empty set per request; never shared.

def build_llm_tools(*, active_set, web_search_enabled, sandbox_enabled,
                   agent_allowed_tools) -> list[dict]
    # Immediate-loading + active_set ∪, with toggles + D-P13-06 agent filter.

async def build_catalog_block(*, agent_allowed_tools=None) -> str
    # `## Available Tools` markdown block; '' when empty.
    # tool_search excluded from rows (D-P13-04).
    # Cap 50, alphabetical sort, 80-char description truncate, pipe-sanitized.
```

## Tests (26 passed)

| Range | Coverage |
|-------|----------|
| 1-6 | ToolDefinition import, construction, Literal validation; flag default + env override |
| 7-10 | Registry empty at load; register() insertion; duplicate dedup with WARNING; make_active_set freshness |
| 11-16, 16b | build_llm_tools — empty, immediate-only, active_set add, web_search/sandbox toggles, skill bypass, **tool_search always-on under restrictive agent filter (plan-checker warning A)** |
| 17-25 | build_catalog_block — empty, header/meta-callout, columns, sort, escape, 80-char truncate, 50-cap footer, tool_search row exclusion, skill bypass + tool_search exclusion combined, native-not-allowed filter |

## What is intentionally NOT in this plan

- Native tool registration (TOOL_DEFINITIONS adapter wrap) → Plan 13-02
- Skill registration helper (`register_user_skills`) → Plan 13-03
- `tool_search` self-registration + matcher → Plan 13-04
- `chat.py` flag-gated splices + `agent_service.should_filter_tool` → Plan 13-05

## Deviations

- The plan called for `from app.config import settings`; project convention is `from app.config import get_settings` (lru_cache singleton). Tests adapted to the actual project pattern; behavior verified equivalently via `Settings()` reload under monkeypatched env (Test 6).
- `ToolDefinition.schema` triggers a `UserWarning` because `schema` shadows
  pydantic.BaseModel's reserved `schema()` classmethod. We accept the warning
  rather than rename the field (rename would propagate through every
  `register(...)` call site in 13-02, 13-03, 13-04, and 13-05). `model_config`
  uses `protected_namespaces=()` and `arbitrary_types_allowed=True`.

## Self-Check: PASSED

- [x] `pytest tests/unit/test_tool_registry.py -v` → 26 passed
- [x] `python -c "from app.main import app"` → OK (no import-time crash)
- [x] `_REGISTRY == {}` at clean module import (no auto-register in this plan)
- [x] All acceptance criteria for Tasks 1, 2, 3 met
