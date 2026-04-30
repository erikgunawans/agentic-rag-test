---
phase: 08-llm-tool-integration-discovery
plan: "02"
subsystem: skill-catalog-service
tags: [tdd, skill-catalog, system-prompt, rlc-scoped, fail-soft]
dependency_graph:
  requires: []
  provides:
    - "backend/app/services/skill_catalog_service.py::build_skill_catalog_block"
  affects:
    - "backend/app/routers/chat.py (Plan 08-04 will consume build_skill_catalog_block)"
tech_stack:
  added: []
  patterns:
    - "Empty-string-when-disabled: same convention as get_pii_guidance_block in prompt_guidance.py"
    - "RLS-scoped authed client: get_supabase_authed_client(token) — no service-role"
    - "Fail-soft try/except: WARNING log + return '' — chat never breaks"
    - "Limit-21 overflow detection: fetch 21 rows to detect N > 20 without a COUNT query"
key_files:
  created:
    - path: "backend/app/services/skill_catalog_service.py"
      lines: 112
      role: "Async service exporting build_skill_catalog_block(user_id, token) -> str"
    - path: "backend/tests/unit/test_skill_catalog_service.py"
      lines: 178
      role: "9 async unit tests covering all SKILL-07 invariants"
  modified: []
decisions:
  - "D-P8-02 enforced: build_skill_catalog_block returns '' when user has 0 enabled skills — no behavioral change to chat for users without skills"
  - "D-P8-06: cap at 20 rows via .limit(21) + rows[:20] slice — avoids separate COUNT query"
  - "D-P8-07: count-free footer phrasing honest at any N > 20"
  - "Pipe/newline sanitization in _format_table_row prevents markdown table corruption from user-supplied skill descriptions"
metrics:
  duration_minutes: 3
  completed_date: "2026-04-30"
  tasks_completed: 2
  files_changed: 2
---

# Phase 8 Plan 02: Skill Catalog Service Summary

**One-liner:** RLS-scoped async service returning markdown '## Your Skills' block from enabled skills table, with 20-row cap, alphabetical order, fail-soft exception handling, and D-P8-02 empty-string invariant.

## What Was Built

Created `backend/app/services/skill_catalog_service.py` (112 lines), a new service module providing a single exported async function `build_skill_catalog_block(user_id: str, token: str) -> str`.

The function:
- Fetches up to 21 enabled skills (RLS-scoped via `get_supabase_authed_client(token)`) ordered alphabetically by name
- Returns `""` when 0 enabled skills (D-P8-02 invariant — chat behavior byte-identical to pre-feature state)
- Formats a markdown system-prompt block starting with `"\n\n## Your Skills\n"` plus an anti-speculation guardrail and `| Skill | Description |` table
- Caps display at 20 rows; appends count-free footer `"Showing 20 enabled skills. More are available — call load_skill with any skill name to load it directly."` when N > 20 (D-P8-07)
- Sanitizes pipe characters and newlines in skill names/descriptions to prevent table corruption
- Returns `""` on any DB exception (fail-soft per CONVENTIONS.md §Error Handling)

Created `backend/tests/unit/test_skill_catalog_service.py` (178 lines, 9 tests) covering all SKILL-07 decision invariants.

## TDD Gate Compliance

- RED commit: `a7348e7` — `test(08-02): add failing tests for build_skill_catalog_block` (9 failing tests; `ModuleNotFoundError` confirmed)
- GREEN commit: `5104954` — `feat(08-02): implement build_skill_catalog_block service` (all 9 tests pass)
- REFACTOR: no structural changes needed — implementation was clean on first pass

## Test Results

```
9 passed, 1 warning in 2.41s
```

All 9 tests pass:
- `test_zero_enabled_skills_returns_empty_string` — D-P8-02
- `test_single_skill_returns_formatted_block` — D-P8-05 table format
- `test_twenty_skills_no_truncation_footer` — D-P8-06 at boundary
- `test_more_than_twenty_skills_caps_and_appends_footer` — D-P8-06/D-P8-07
- `test_alphabetical_ordering` — verifies `.order("name")` call
- `test_filters_by_enabled_true` — verifies `.eq("enabled", True)` call
- `test_db_exception_returns_empty_string_fail_soft` — fail-soft invariant
- `test_empty_or_missing_token_returns_empty_string` — defensive falsy-token guard
- `test_anti_speculation_guardrail_present` — D-P8-05 guardrail text

## Security Verification

- `grep "get_supabase_client()" backend/app/services/skill_catalog_service.py` → 0 matches (no service-role bypass)
- T-08-02-01 (information disclosure via cross-user skill leak) mitigated: only `get_supabase_authed_client(token)` used; RLS SELECT policy `user_id = auth.uid() OR user_id IS NULL` filters server-side
- T-08-02-02 (pipe/newline injection in descriptions) mitigated: `_format_table_row` escapes `|` → `\|` and replaces `\n` with space
- T-08-02-03 (DoS via large skill count) mitigated: `.limit(21)` query cap + `rows[:20]` display cap
- T-08-02-04 (DB outage breaks chat) mitigated: try/except returns `""` — verified by `test_db_exception_returns_empty_string_fail_soft`

## Deviations from Plan

None — plan executed exactly as written. The test file, service implementation, and all acceptance criteria match the plan specification verbatim.

## Known Stubs

None — the service is fully implemented. Plan 08-04 will wire `build_skill_catalog_block` into `chat.py`.

## Threat Flags

No new threat surface introduced beyond what the plan's threat model already covers.

## Self-Check: PASSED

- `backend/app/services/skill_catalog_service.py` exists: FOUND
- `backend/tests/unit/test_skill_catalog_service.py` exists: FOUND
- Commit `a7348e7` exists: FOUND (RED test commit)
- Commit `5104954` exists: FOUND (GREEN impl commit)
- 9 tests pass: CONFIRMED
- Backend import smoke: `python -c "from app.main import app; print('OK')"` → OK
- Empty-string invariant: `asyncio.run(build_skill_catalog_block('u1', ''))` → `''`
