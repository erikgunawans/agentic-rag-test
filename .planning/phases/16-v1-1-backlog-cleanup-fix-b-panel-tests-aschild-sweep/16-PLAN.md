# Phase 16 — v1.1 Backlog Cleanup (Fix B + Panel Tests + asChild Sweep)

**Status:** Planned
**Plans:** 3
**Waves:** 1 (all three plans run in parallel — file-disjoint)
**Generated:** 2026-05-02

## Phase Goal

Close the three operational debts carried forward from v1.1 — domain-term PII
false positives, missing `CodeExecutionPanel` test coverage, and base-ui
wrappers that crash under `asChild` — so the v1.2 milestone leaves no
inherited rough edges.

## Requirements Coverage

| REQ-ID | Plan | Status |
|--------|------|--------|
| REDACT-01 | `16-01` | Planned |
| TEST-01   | `16-02` | Planned |
| UI-01     | `16-03` | Planned |

## Plan Inventory

| Plan | Title | Wave | Depends on | Requirements | Files modified |
|------|-------|------|------------|--------------|----------------|
| `16-01` | REDACT-01 — Configurable PII Domain-term Deny List (Fix B completion) | 1 | — | REDACT-01 | `supabase/migrations/037_*.sql`, `backend/app/services/redaction/detection.py`, `backend/tests/unit/test_detection_domain_deny_list.py` |
| `16-02` | TEST-01 — Bootstrap Vitest + Add CodeExecutionPanel Component Tests | 1 | — | TEST-01 | `frontend/package.json`, `frontend/vite.config.ts`, `frontend/src/test/setup.ts`, `frontend/src/components/chat/CodeExecutionPanel.test.tsx` |
| `16-03` | UI-01 — asChild Shim Sweep (select patch + new dropdown-menu + new dialog) | 1 | — | UI-01 | `frontend/src/components/ui/select.tsx`, `frontend/src/components/ui/dropdown-menu.tsx` (new), `frontend/src/components/ui/dialog.tsx` (new) |

**Wave 1** *(no inter-plan dependencies — all three execute in parallel)*

## Wave Plan

```
Wave 1 (parallel): 16-01  ‖  16-02  ‖  16-03
```

The three plans touch disjoint files (backend Python vs. frontend test infra
vs. frontend UI wrappers) and share no schemas, no env vars, and no runtime
flags. Per CONTEXT.md D-P16-15, the executor can fan out to a 3-way wave.

## Cross-cutting Constraints (must_haves.truths shared by 2+ plans)

None — each plan is self-contained. The phase has no cross-cutting invariants
beyond the standard CLAUDE.md guidance (RLS, audit, no LangChain, etc.).

## Verification Summary

Per-plan verification commands:

| Plan | Verification |
|------|--------------|
| `16-01` | `cd backend && pytest tests/unit/ -k "redaction or detection or pii"` + `python -c "from app.main import app; print('OK')"` + live Supabase column probe |
| `16-02` | `cd frontend && npx tsc --noEmit && npm run lint && npm test` (6 vitest cases pass) |
| `16-03` | `cd frontend && npx tsc --noEmit && npm run build` (project-references `tsc -b` is the SC#3 gate) |

Phase-wide verification:
- All four ROADMAP §Phase 16 success criteria are satisfied by exactly one plan each (SC#1→16-01, SC#2→16-02, SC#3→16-03, SC#4→all three via the no-regression assertions in each plan's verify task).
- `git diff --stat` after Wave 1 should show modifications confined to the union of `files_modified` across the three plans.

## Decisions Honored (from CONTEXT.md)

- **D-P16-01..05** (REDACT-01) → 16-01: `system_settings` column, baked-in ∪ runtime extras, 60s cache, frozenset O(1) lookup, extend existing test file.
- **D-P16-06..10** (TEST-01) → 16-02: Vitest + RTL + jsdom, devDeps only, `vi.mock('@/lib/api')`, 6 test cases (4 SC#2 + 2 edge), no real signed-URL navigation.
- **D-P16-11..14** (UI-01) → 16-03: three deliverables (patch select, create dropdown-menu, create dialog), exact popover.tsx shim verbatim, no call-site rewrites, project-references `tsc -b` build verification.
- **D-P16-15** (cross-track parallelism) → Wave 1 fan-out across all three plans.
- **D-P16-16** (single phase commit) → atomic per-plan commits at execute-phase time; no per-track milestone commits.

## Deferred (out of scope this phase)

- Admin UI form for editing the deny list (D-P16-01 ships configurability via `system_settings` row only).
- Migrating `CreateFolderDialog.tsx` onto the new `dialog.tsx` primitive.
- Component tests for other Phase 11 surfaces (`SubAgentPanel`, `ToolCallList`, `MessageView`).
- MSW (mock-service-worker) for backend contract tests.
- `asChild` shim sweep for additional base-ui primitives (radio-group, tabs, accordion, slider, switch, checkbox).

## Per-Plan Files

- `16-01-PLAN.md` — REDACT-01
- `16-02-PLAN.md` — TEST-01
- `16-03-PLAN.md` — UI-01

---

*Phase directory: `.planning/phases/16-v1-1-backlog-cleanup-fix-b-panel-tests-aschild-sweep/`*
*Plans created: 2026-05-02 via `/gsd-plan-phase 16 --auto` (PLAN-ONLY, no execute chain)*
