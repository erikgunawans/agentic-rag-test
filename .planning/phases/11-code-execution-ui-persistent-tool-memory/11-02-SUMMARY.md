---
phase: 11-code-execution-ui-persistent-tool-memory
plan: 02
subsystem: ui

tags: [typescript, types, sse, frontend, code-execution, tool-memory]

# Dependency graph
requires:
  - phase: 10-code-execution-sandbox-backend
    provides: "code_stdout / code_stderr SSE wire shape (D-P10-06: {type, line, tool_call_id})"
provides:
  - "frontend SSEEvent union recognizes code_stdout and code_stderr variants — narrowing via event.type literal works without `as` casts"
  - "ToolCallRecord widened with optional tool_call_id and status — Phase 11-04 backend records and Plan 11-05/06/07 frontend components compile against the same canonical shape"
  - "Type-only contract; zero runtime emit changes (no `.tsx`/`.ts` consumers compile to different JS yet)"
affects: [11-03, 11-04, 11-05, 11-06, 11-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Discriminated union extension: new SSE event variants added as top-level `export interface` with `type: 'literal'`, then appended to the `SSEEvent` union with end-of-line phase comment"
    - "Backwards-compatible model widening: new optional + nullable (`?: T | null`) fields preserve existing readers; legacy persisted rows still typecheck"

key-files:
  created: []
  modified:
    - "frontend/src/lib/database.types.ts — +21 lines: 2 new interfaces (CodeStdoutEvent, CodeStderrEvent), 2 union additions, 2 ToolCallRecord fields"

key-decisions:
  - "Both new ToolCallRecord fields marked `?: T | null` (not just `?: T`) — matches the existing `error?: string | null` style and the D-P11-03 legacy-row tolerance: persisted JSONB rows that omit these fields and persisted rows that store explicit `null` both typecheck"
  - "End-of-line `// Phase 11 SANDBOX-07` comments on each new union variant — mirrors the pre-existing `// Phase 5 D-88` annotation on RedactionStatusEvent; gives future readers an audit trail back to the requirement and decision IDs"

patterns-established:
  - "Frontend-side SSE-event extension with zero runtime change: declare interface with discriminated `type` literal, append to SSEEvent union — Plan 11-05's `useChatState` switch can then add `else if (event.type === 'code_stdout') {…}` without `as never` casts"

requirements-completed: [SANDBOX-07, MEM-01]

# Metrics
duration: 1m 16s
completed: 2026-05-01
---

# Phase 11 Plan 02: Frontend Type Extensions for Code Execution SSE & Persistent Tool Memory Summary

**Two new SSE event variants (`code_stdout`, `code_stderr`) and two new `ToolCallRecord` fields (`tool_call_id`, `status`) added to `frontend/src/lib/database.types.ts` — type-only precondition that unblocks Plans 11-05/06/07 frontend wave.**

## Performance

- **Duration:** 1m 16s
- **Started:** 2026-05-01T12:40:31Z
- **Completed:** 2026-05-01T12:41:47Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Frontend type system now recognizes the `code_stdout` / `code_stderr` SSE events that Phase 10 has been emitting since `10-05`. `useChatState` (Plan 11-05) can narrow on `event.type === 'code_stdout'` with full IntelliSense and exhaustiveness — no `as never` casts.
- `ToolCallRecord` carries optional, nullable `tool_call_id?: string | null` and `status?: 'success' | 'error' | 'timeout' | null`. The `Message.tool_calls.calls[]` reader at line 27 automatically inherits the widened shape — no edit needed there.
- Backwards compatibility preserved: every existing reader of `ToolCallRecord` (`ToolCallCard.tsx`, `MessageView.tsx`) still compiles because both new fields are optional. Legacy persisted JSONB rows from Phases 1-10 still satisfy the type — D-P11-03's "no migration" decision is honored at the type layer.
- Zero runtime change: this is purely a `.d.ts`-shaped contract widening. No `.tsx`/`.ts` consumer of these types emits different JavaScript.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend SSEEvent union and ToolCallRecord with Phase 11 fields** — `d03c38b` (feat)

## Files Created/Modified

- `frontend/src/lib/database.types.ts` — Added `CodeStdoutEvent` and `CodeStderrEvent` interfaces (lines 76–90), extended `SSEEvent` union with both variants (lines 100–101), added `tool_call_id?: string | null` and `status?: 'success' | 'error' | 'timeout' | null` to `ToolCallRecord` (lines 16–18). Net +21 lines.

## Decisions Made

- **Nullable + optional on the two new `ToolCallRecord` fields.** The plan specified `tool_call_id?: string | null` and `status?: '...' | null`. Both forms together (`?` AND `| null`) cover (a) JSONB rows where the key is absent, (b) JSONB rows where the value is explicit `null`. This is exactly the existing `error?: string | null` pattern in this same interface, keeping the file internally consistent.
- **Comment style on union additions matches the existing D-88 precedent.** End-of-line `// Phase 11 SANDBOX-07` annotations mirror `// Phase 5 D-88` on `RedactionStatusEvent` — so a future reader scanning the union can immediately trace each variant back to its requirement and phase.

## Deviations from Plan

None — plan executed exactly as written. All three splices applied verbatim per the plan's `<action>` block.

## Issues Encountered

None during the task itself. The repository-wide `npm run lint` reported 10 pre-existing errors in unrelated files (`DocumentsPage.tsx` `react-hooks/set-state-in-effect`, `ThemeContext.tsx` `react-refresh/only-export-components`, etc.) — these were last touched in commits `3b5c0b8`, `21f3382`, `f9ef24f` (knowledge-base / global-folders work, not Phase 11). Per the SCOPE BOUNDARY rule, they are out of scope for this plan and were not modified. `npx eslint src/lib/database.types.ts` on just the modified file exits clean (0 errors).

### Pre-existing lint issues (deferred — out of scope)

| File | Rule | Note |
|------|------|------|
| `frontend/src/pages/DocumentsPage.tsx` | `react-hooks/set-state-in-effect` × 8 | Pre-existing; introduced before Phase 11 |
| `frontend/src/theme/ThemeContext.tsx` | `react-refresh/only-export-components` × 1 | Pre-existing |
| `frontend/src/pages/DocumentsPage.tsx` | `react-hooks/refs` × 1 | Pre-existing |

These should be picked up in a separate hygiene pass — not Phase 11's concern.

## User Setup Required

None — no external service configuration required. Type-only change.

## Next Phase Readiness

- **Plan 11-05 (`useChatState` SSE handler patch):** Ready. Can now write `else if (event.type === 'code_stdout') { ... }` without type-assertion gymnastics; TypeScript narrows `event` to `CodeStdoutEvent` exposing `event.line: string` and `event.tool_call_id: string`.
- **Plan 11-06 (`CodeExecutionPanel.tsx` NEW component):** Ready. Component can read `call.tool_call_id` and `call.status` from `Message.tool_calls.calls[N]` directly.
- **Plan 11-07 (`ToolCallCard.tsx` switch):** Ready. The `tool === 'execute_code'` switch can route based on whether `call.tool_call_id` is present (D-P11-03 legacy fallback to generic `ToolCallCard`).
- **Plan 11-04 (backend `chat.py` record-construction):** Independent — Plan 11-04 sets the values that Plans 11-05/06/07 read via this contract. The two waves can land in any order; plans 11-05/06/07 just won't see real `tool_call_id` / `status` data on persisted rows until 11-04 lands.

No blockers. No concerns. Type contract is locked.

## Self-Check: PASSED

- File modified exists: `frontend/src/lib/database.types.ts` — FOUND
- Commit `d03c38b` — FOUND in `git log --oneline`
- All 6 verify-block grep assertions pass:
  - `interface CodeStdoutEvent` — FOUND
  - `interface CodeStderrEvent` — FOUND
  - `tool_call_id?: string | null` — FOUND
  - `status?: 'success' | 'error' | 'timeout' | null` — FOUND
  - `| CodeStdoutEvent` (union) — FOUND
  - `| CodeStderrEvent` (union) — FOUND
- `cd frontend && npx tsc --noEmit` exits 0
- `cd frontend && npx eslint src/lib/database.types.ts` exits 0

---
*Phase: 11-code-execution-ui-persistent-tool-memory*
*Completed: 2026-05-01*
