---
phase: 16-v1-1-backlog-cleanup-fix-b-panel-tests-aschild-sweep
status: completed
completed: 2026-05-02
plans: 3
requirements_covered:
  - REDACT-01
  - TEST-01
  - UI-01
---

# Phase 16 Summary — v1.1 Backlog Cleanup (Fix B + Panel Tests + asChild Sweep)

## Phase Goal

Close the three operational debts carried forward from v1.1: domain-term PII false positives, missing CodeExecutionPanel test coverage, and base-ui wrappers that crash under `asChild`.

## What Was Shipped

| Plan | Requirement | Deliverable |
|------|-------------|-------------|
| 16-01 | REDACT-01 | `pii_domain_deny_list_extra` column in system_settings + 60s-cached frozenset union in `detection.py` + migration 037 applied |
| 16-02 | TEST-01 | Vitest 3.2 infrastructure + `CodeExecutionPanel.test.tsx` (streaming, terminal, signed-URL, history parity) |
| 16-03 | UI-01 | asChild shim on `select.tsx`, new `dropdown-menu.tsx`, new `dialog.tsx` |

## Requirements Coverage

- **REDACT-01** ✅ — Domain-term deny list configurable at runtime; zero-regression invariant on empty extras
- **TEST-01** ✅ — First automated frontend tests in the repo; CodeExecutionPanel coverage replaces UAT-only
- **UI-01** ✅ — All 5 base-ui wrappers support asChild (tooltip, popover, select, dropdown-menu, dialog)

## Notes

- Migration 037 was applied to Supabase production during Wave A UAT session (2026-05-02)
- Vitest version bump from 2.x → 3.2 was required due to Vite 8 incompatibility (deferred risk from v1.1 that surfaced during execution)
- 43/43 vitest tests passing post-execution
