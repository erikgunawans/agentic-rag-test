---
phase: 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co
plan: 05-05
subsystem: pii-redaction
tags: [frontend, sse, types, react-hook, i18n, redaction-status, spinner, d-88, d-89]

# Dependency graph
requires:
  - phase: 00-baseline
    provides: SSEEvent discriminated union + useChatState hook + i18n translations.ts (Phase 0 / CHAT-06 baseline)
  - phase: 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co
    provides: D-88 SSE event sequence shape + D-89 skeleton tool events + D-94 'blocked' egress trip semantics (CONTEXT decisions; backend emit owned by Plan 05-04)
provides:
  - "RedactionStatusEvent discriminated-union variant exported from frontend/src/lib/database.types.ts (BUFFER-02 wire shape)"
  - "useChatState.redactionStage hook return value — non-null during anonymizing/deanonymizing/blocked stages, null otherwise"
  - "ToolStartEvent.input + ToolResultEvent.output relaxed to optional (D-89 skeleton-mode wire compat)"
  - "3 i18n keys (id + en): redactionAnonymizing, redactionDeanonymizing, redactionBlocked"
  - "Backward-compat: when backend doesn't emit redaction_status events, frontend behavior is byte-identical to Phase 0 / CHAT-06 (no-op variant)"

# Tasks executed

## Task 1: SSEEvent union extension (database.types.ts)
**Status:** COMPLETE

Added `RedactionStatusEvent` discriminated-union variant to `frontend/src/lib/database.types.ts`:
```ts
export type RedactionStatusEvent = {
  type: 'redaction_status';
  stage: 'anonymizing' | 'deanonymizing' | 'blocked';
};
```
Updated `SSEEvent` union to include `| RedactionStatusEvent`. Also relaxed `ToolStartEvent.input` and `ToolResultEvent.output` to `optional` (`?:`) for D-89 skeleton-mode wire compatibility.

**Files changed:** `frontend/src/lib/database.types.ts` (+22, -3)

## Task 2: useChatState dispatch (useChatState.ts)
**Status:** COMPLETE

Added `redactionStage` state (`string | null`) and dispatch case for `redaction_status` events in the SSE handler within `useChatState.ts`. When backend emits `redaction_status:anonymizing/deanonymizing/blocked`, `redactionStage` is set accordingly; reset to `null` on `done:true` or new message start. When backend doesn't emit the event, state stays `null` (no-op path).

**Files changed:** `frontend/src/hooks/useChatState.ts` (+19)

## Task 3: i18n strings (translations.ts)
**Status:** COMPLETE

Added 3 bilingual i18n keys to `frontend/src/i18n/translations.ts`:
- `redactionAnonymizing`: `'Mengantonimkan…'` (id) / `'Anonymizing…'` (en)
- `redactionDeanonymizing`: `'Memulihkan nama…'` (id) / `'Restoring names…'` (en)
- `redactionBlocked`: `'Pengiriman diblokir'` (id) / `'Egress blocked'` (en)

**Files changed:** `frontend/src/i18n/translations.ts` (+12)

# Commits
- `2120b04` feat(05-05): extend SSEEvent union with RedactionStatusEvent variant
- `42b0d1f` feat(05-05): wire useChatState dispatch for redaction_status events
- `a4b0e13` feat(05-05): add 3 i18n keys for redaction status spinner

# REQ-ID coverage
- BUFFER-02: RedactionStatusEvent type + useChatState dispatch wired
- TOOL-01: ToolStartEvent.input / ToolResultEvent.output made optional (D-89 skeleton compat)

# Decisions honored
- D-88: two redaction_status stage values (anonymizing, deanonymizing) + blocked third value
- D-89: ToolStartEvent/ToolResultEvent optional fields for skeleton tool events
- SC#5 invariant: when backend doesn't emit redaction_status, frontend behavior unchanged

# Deviations
None. All 3 tasks executed as planned.

# Test results
- TypeScript compilation: `cd frontend && npx tsc --noEmit` — PASS
- Frontend lint: `cd frontend && npm run lint` — PASS

# Duration
~8 minutes (3 tasks across 3 files)
