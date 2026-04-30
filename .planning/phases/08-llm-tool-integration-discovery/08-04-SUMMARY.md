---
phase: 08-llm-tool-integration-discovery
plan: "04"
subsystem: backend/chat-router
tags: [chat, skill-catalog, system-prompt, token-plumbing, tdd, rls]
dependency_graph:
  requires: ["08-01 (execute_tool token kwarg)", "08-02 (build_skill_catalog_block)"]
  provides:
    - "chat.py: skill_catalog_block injected at both single-agent and multi-agent system-prompt sites"
    - "chat.py: token=user['token'] forwarded through _run_tool_loop to execute_tool"
  affects:
    - "All chat requests: catalog queried on every turn (fail-soft, indexed)"
    - "Skill tools (load_skill, save_skill, read_skill_file): now receive RLS-scoped token"
tech_stack:
  added: []
  patterns:
    - "D-P8-02 empty-string invariant: build_skill_catalog_block returns '' for 0 skills — byte-identical to pre-Phase-8"
    - "D-P8-03 both-paths injection: catalog appended to system prompt at multi-agent AND single-agent assembly sites"
    - "Token plumbing: keyword-only token kwarg flows chat -> _run_tool_loop -> execute_tool"
    - "Strategy A integration test: inspect.getsource() + mock RLS client — no live LLM needed"
key_files:
  modified:
    - path: "backend/app/routers/chat.py"
      lines: 679
      changes: "20 lines added across 6 patch sites: 1 import, 2 catalog injection sites, 1 _run_tool_loop signature, 2 execute_tool call sites, 2 _run_tool_loop call sites"
  created:
    - path: "backend/tests/api/test_chat_skill_catalog.py"
      lines: 190
      role: "5 integration tests covering D-P8-02 invariant, catalog injection positive case, disabled-skill exclusion, D-P8-03 both-paths smoke test, token plumbing smoke test"
decisions:
  - "Tests placed under tests/api/ (not tests/integration/) because integration/ directory does not exist in this project"
  - "Strategy A (mock + inspect.getsource) chosen over Strategy B (live SSE) for deterministic, fast assertions without LLM dependency"
  - "5 tests written (plan minimum was 4) to explicitly cover disabled-skill exclusion as a separate case"
metrics:
  duration: "~195 seconds"
  completed_date: "2026-05-01"
  tasks_completed: 3
  files_modified: 1
  files_created: 1
---

# Phase 8 Plan 04: Chat Pipeline Catalog Injection + Token Plumbing Summary

**One-liner:** Wired `build_skill_catalog_block` into both chat.py system-prompt assembly paths and plumbed `token=user["token"]` through `_run_tool_loop` to `execute_tool`, making skill tools RLS-scoped and the skill catalog visible to the LLM on every chat turn.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Inject skill_catalog_block into both chat.py system-prompt sites | 21f668b | backend/app/routers/chat.py |
| 2 | Plumb token kwarg through _run_tool_loop to execute_tool | cfe9800 | backend/app/routers/chat.py |
| 3 | Add integration tests for catalog injection + token plumbing | 0988307 | backend/tests/api/test_chat_skill_catalog.py |

## Changes Made

### `backend/app/routers/chat.py` (pre-patch line count ~659, post-patch 679)

**6 patch sites applied:**

**Patch 1 — Import (line ~14):**
```python
from app.services.skill_catalog_service import build_skill_catalog_block
```

**Patch 2 — Multi-agent system-prompt assembly (D-P8-03):**
```python
# Phase 8 D-P8-03: append the enabled-skills catalog.
skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
messages = (
    [{"role": "system", "content": agent_def.system_prompt + skill_catalog}]
    ...
)
```

**Patch 3 — Single-agent system-prompt assembly (D-P8-01):**
```python
# Phase 8 D-P8-01: append enabled-skills catalog (D-P8-02 SC#5-style invariant).
skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
messages = (
    [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance + skill_catalog}]
    ...
)
```

**Patch 4 — `_run_tool_loop` signature:**
```python
async def _run_tool_loop(
    ...,
    token: str | None = None,   # Phase 8 D-P8-XX: enables RLS-scoped DB access for skill tools
):
```

**Patches 5 & 6 — `execute_tool` call sites (redaction-on branch line ~269, redaction-off branch line ~296):**
```python
tool_output = await tool_service.execute_tool(
    func_name, real_args, user_id, tool_context,
    registry=registry,
    token=token,          # NEW
)
# and
tool_output = await tool_service.execute_tool(
    func_name, func_args, user_id, tool_context,
    token=token,          # NEW
)
```

**Patches 7 & 8 — `_run_tool_loop` call sites (multi-agent ~line 456, single-agent ~line 521):**
```python
async for event_type, data in _run_tool_loop(
    ...,
    available_tool_names=available_tool_names,
    token=user["token"],  # NEW
):
```

**tool_redaction.py — NOT edited:** Grep confirmed it does not invoke `tool_service.execute_tool` (lines 4, 30, 31, 66 are docstring/comment matches only).

### `backend/tests/api/test_chat_skill_catalog.py` (190 lines, created)

5 async test functions:
1. `test_zero_enabled_skills_does_not_inject_catalog_block` — D-P8-02 invariant
2. `test_enabled_skills_inject_catalog_block_into_system_prompt` — positive catalog injection
3. `test_disabled_skill_excluded_from_catalog` — enabled-filter verified via mock
4. `test_chat_router_imports_build_skill_catalog_block` — D-P8-03 both-paths smoke via inspect.getsource
5. `test_chat_router_passes_token_to_execute_tool` — token plumbing smoke via inspect.getsource

## Verification Results

```
# Acceptance criteria grep checks
grep -c "from app.services.skill_catalog_service import build_skill_catalog_block" chat.py  -> 1 ✓
grep -c "build_skill_catalog_block" chat.py                                                 -> 3 ✓ (1 import + 2 await sites)
grep -c "agent_def.system_prompt + skill_catalog" chat.py                                  -> 1 ✓
grep -c "SYSTEM_PROMPT + pii_guidance + skill_catalog" chat.py                             -> 1 ✓
grep -c "skill_catalog = await build_skill_catalog_block" chat.py                          -> 2 ✓
grep -c "token=token" chat.py                                                               -> 2 ✓
grep -c "token=user[\"token\"]" chat.py                                                     -> 2 ✓
grep -c "token: str | None = None" chat.py                                                  -> 1 ✓

# Test results
pytest tests/api/test_chat_skill_catalog.py -v               -> 5 passed ✓
pytest tests/unit/test_chat_router_phase5_imports.py          -> 41 passed ✓ (regression)
pytest tests/unit/test_chat_router_phase5_wiring.py           -> included in 41 above ✓
pytest tests/unit/test_tool_service_skill_tools.py            -> 12 passed ✓ (Plan 08-01)
pytest tests/unit/test_skill_catalog_service.py               -> 9 passed ✓ (Plan 08-02)
pytest tests/unit/test_redaction_barrel_walker.py             -> 8 passed ✓
All unit tests combined                                        -> 62 passed ✓

# Backend import smoke
python -c "from app.main import app; print('OK')"             -> OK ✓
```

## Invariants Explicitly Verified

**D-P8-02:** `test_zero_enabled_skills_does_not_inject_catalog_block` — `build_skill_catalog_block("u1", "tok")` returns `""` when DB returns `[]`; `SYSTEM_PROMPT + "" + ""` does not contain `"## Your Skills"`.

**D-P8-03 (both paths):** `test_chat_router_imports_build_skill_catalog_block` asserts `"agent_def.system_prompt + skill_catalog" in source` (multi-agent) AND `"SYSTEM_PROMPT + pii_guidance + skill_catalog" in source` (single-agent). These patterns cannot coexist on the same code path, proving both paths are instrumented.

## Deviations from Plan

**1. [Process] Test file placed under `tests/api/` not `tests/integration/`**
- **Reason:** `tests/integration/` directory does not exist in this project. The plan allowed this: "Create `backend/tests/integration/test_chat_skill_catalog.py` (or place at `backend/tests/api/test_chat_skill_catalog.py` if `tests/integration/` doesn't exist"
- **Impact:** None — tests run identically under `tests/api/`

**2. [Rule 2 - Enhancement] Added 5th test case for disabled-skill exclusion**
- **Plan specified:** 4 test functions minimum
- **Added:** `test_disabled_skill_excluded_from_catalog` as an explicit third function (plan listed it in behavior but the skeleton only showed 4 functions)
- **Impact:** Stronger coverage, no regressions

## Manual UAT Checklist (for user verification)

1. Start backend: `cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000`
2. As `test@test.com`, create a skill: `POST /skills` with `name="legal-review"`, `description="Reviews NDA contracts."`
3. Open chat, send: `"I have an NDA to review — can you use the legal-review skill?"`
4. Check LangSmith trace (or backend logs):
   - System message contains `## Your Skills` and the `legal-review` row
   - LLM emits a `load_skill` tool call with `name=legal-review`
   - `_execute_load_skill` returns full instructions + files table
   - Final response references skill instructions
5. Save-skill UAT: Send `"Help me create a new skill called 'summarize-meetings'"`
   - After exchange, LLM calls `save_skill(name="summarize-meetings", ...)`
   - Verify: `GET /skills?search=summarize-meetings` returns the new skill

## Known Stubs

None — all wiring is complete end-to-end. The LLM receives the catalog; skill tools receive the RLS-scoped token.

## Threat Flags

None — no new network endpoints or auth paths beyond what the plan's threat model (T-08-04-01 through T-08-04-07) already covers. `user["token"]` is the only value forwarded (no service-role token leak).

## Self-Check: PASSED

Files exist:
- backend/app/routers/chat.py: FOUND (679 lines)
- backend/tests/api/test_chat_skill_catalog.py: FOUND (190 lines)

Commits:
- 21f668b: FOUND (feat(08-04): inject skill_catalog_block into both chat.py system-prompt sites)
- cfe9800: FOUND (feat(08-04): plumb token kwarg through _run_tool_loop to execute_tool)
- 0988307: FOUND (test(08-04): add integration tests for chat skill catalog injection)
