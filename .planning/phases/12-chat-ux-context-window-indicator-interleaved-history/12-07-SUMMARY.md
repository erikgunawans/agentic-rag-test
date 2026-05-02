---
phase: 12-chat-ux-context-window-indicator-interleaved-history
plan: 07
subsystem: frontend
tags: [history-reconstruction, interleaving, sub-agent-panel, code-execution-panel, vitest]
requires:
  - frontend/src/lib/messageTree.ts (buildChildrenMap, getActivePath)
  - frontend/src/lib/database.types.ts (ToolCallRecord with sub_agent_state + code_execution_state from 12-05)
  - frontend/src/components/chat/CodeExecutionPanel.tsx (Phase 11)
  - frontend/src/components/chat/ToolCallCard.tsx (existing ToolCallList router)
  - frontend/vitest.config.ts (Phase 16-02)
provides:
  - buildInterleavedItems(messages) helper for chronological per-round flattening
  - ConversationItem discriminated-union type
  - SubAgentPanel component for history-reload sub-agent rendering
  - hasSubAgentState type guard for router branching
  - ToolCallList triple-branch: sub_agent_state -> SubAgentPanel, execute_code -> CodeExecutionPanel, other -> ToolCallCard
  - CodeExecutionPanel reads code_execution_state preferentially (richer post-history-reload state)
affects:
  - frontend/src/components/chat/MessageView.tsx (no change — existing messages.map naturally handles per-round rows)
tech-stack:
  added: []
  patterns:
    - Pure helper + discriminated-union ConversationItem (FP-style flattening)
    - Type-guard branching in router (hasSubAgentState)
    - Preferential read order: code_execution_state -> output -> live stream
key-files:
  created:
    - frontend/src/lib/__tests__/messageTree.interleaved.test.ts
    - frontend/src/components/chat/SubAgentPanel.tsx
    - frontend/src/components/chat/SubAgentPanel.test.tsx
  modified:
    - frontend/src/lib/messageTree.ts (added buildInterleavedItems + ConversationItem)
    - frontend/src/components/chat/ToolCallCard.tsx (extended ToolCallList with sub-agent branch + code_execution_state read)
decisions:
  - D-P12-15: ToolCallList branches on persisted JSONB sub-keys (sub_agent_state, code_execution_state) for history-reload routing
  - Task 4 (MessageView wiring): decided NOOP — existing messages.map(msg) iteration already renders per-round rows in chronological order with their own ToolCallList instance, achieving identical interleaving without code change
metrics:
  duration: ~6 minutes
  completed: 2026-05-02T18:45:00Z
  tasks_completed: 4 (3 implemented + 1 noop)
  vitest_tests_added: 16 (8 buildInterleavedItems + 8 SubAgentPanel)
  vitest_tests_total: 43 (5 files)
---

# Phase 12 Plan 07: Frontend Interleaved History Reconstruction Summary

`buildInterleavedItems` helper + `SubAgentPanel` component + `ToolCallList` triple-branch router complete the Phase 12 history-reconstruction loop — multi-row Phase-12-persisted exchanges reload visually identical to live streaming order (HIST-04, HIST-05).

## What Was Built

### 1. `buildInterleavedItems(messages)` helper (`frontend/src/lib/messageTree.ts`)

Pure function that flattens an ordered `Message[]` into a `ConversationItem[]` discriminated union. Defensively sorts by `created_at`, emits text-then-per-call-tool items per message. Stable React keys via `${msg.id}-text` / `${msg.id}-call-${tool_call_id}`.

```ts
export type ConversationItem =
  | { kind: 'text'; key: string; role: 'user' | 'assistant'; text: string; messageId: string }
  | { kind: 'tool'; key: string; role: 'assistant'; toolCall: ToolCallRecord; messageId: string }

export function buildInterleavedItems(messages: Message[]): ConversationItem[]
```

The toolCall passthrough preserves `sub_agent_state` and `code_execution_state` sub-keys so consumer components branch on their presence.

### 2. `SubAgentPanel` component + `hasSubAgentState` type guard (`frontend/src/components/chat/SubAgentPanel.tsx`)

Renders the persisted `sub_agent_state` JSONB shape:
- mode badge (explorer/analysis) — uppercase pill, zinc-neutral
- document badge — `Doc: <document_id>` primary-tinted, only when `document_id` present
- reasoning text — muted-foreground, whitespace-preserved
- explorer tool calls mini-list — mono-font tool name + dim tool_call_id

Design constraints honored: solid `bg-muted/40`, NO `backdrop-blur` (CLAUDE.md persistent-panel rule), no gradient, no inner HTML injection (React JSX text rendering escapes by default — XSS-safe per T-12-07-1 mitigation).

### 3. `ToolCallList` router extension (`frontend/src/components/chat/ToolCallCard.tsx`)

Triple-branch routing:
- `hasSubAgentState(call)` → `<SubAgentPanel state={call.sub_agent_state} />`
- `tool === 'execute_code' && tool_call_id` → `<CodeExecutionPanel ... />`
- everything else → `<ToolCallCard ... />`

`CodeExecutionPanel` data assembly now prefers `code_execution_state` when present, falls back to `output` for legacy/live data. Fields preferentially read from `code_execution_state`: `code`, `stdout`, `stderr`, `execution_ms`, `error_type`, `files`. The live `sandboxStreams` Map continues to override stdout/stderr during streaming.

## Deviations from Plan

### [Rule 3 — Blocking issue] ToolCallList lives in ToolCallCard.tsx, not its own file

**Found during:** Task 3
**Issue:** Plan specifies `frontend/src/components/chat/ToolCallList.tsx` as a separate file. Actual codebase has `ToolCallList` exported from `ToolCallCard.tsx` (Phase 11-07 design choice — see commit `5bab150` and observation 6722).
**Fix:** Modified `ToolCallList` in place inside `ToolCallCard.tsx`. All plan acceptance criteria (sub_agent_state routing, code_execution_state passthrough) satisfied without splitting the file.
**Files modified:** `frontend/src/components/chat/ToolCallCard.tsx`
**Commit:** `4493fa0`

### Task 4: NOOP (per plan optionality)

The plan flagged Task 4 (MessageView wiring) as optional with smoke-test gate. Existing `MessageView.tsx` already iterates `messages.map(msg => ...)` rendering each row's `<ToolCallList>` separately — Phase 12 backend's per-round row split lands naturally as separate map entries in chronological order. Visual interleaving is correct without any change. AgentBadge is rendered conditional on `msg.tool_calls?.agent`; multi-round same-agent rows do show duplicate badges, but the plan flagged this as "fix only if visible artifact" — deferred until UAT identifies it as a problem (not a regression — pre-Phase-12 single-row exchanges always had at most one agent per row).

## Tests

| File | Tests | Status |
|------|-------|--------|
| `frontend/src/lib/__tests__/messageTree.interleaved.test.ts` | 8 | PASS |
| `frontend/src/components/chat/SubAgentPanel.test.tsx` | 8 | PASS |
| (Existing) ContextWindowBar, CodeExecutionPanel, usePublicSettings | 27 | PASS |
| **Total** | **43** | **43 PASS** |

```
Test Files  5 passed (5)
     Tests  43 passed (43)
```

`buildInterleavedItems` test coverage:
1. Single-row legacy exchange flattens to text + per-call items
2. Multi-round (2-row) exchange interleaves chronologically
3. Out-of-order input is sorted by `created_at` defensively
4. `sub_agent_state` passes through on toolCall items
5. `code_execution_state` passes through on toolCall items
6. Empty assistant content does not emit empty text item
7. User messages emit text-only (no tool entries)
8. Stable keys across multiple invocations (React reconciliation safety)

`SubAgentPanel` test coverage:
1. Renders mode badge
2. Renders document badge when `document_id` set
3. Hides document badge when `document_id` is null
4. Renders reasoning text
5. Renders explorer tool calls list (multiple entries)
6. Empty `explorer_tool_calls` does not crash
7. NO `backdrop-blur` class (CLAUDE.md design rule)
8. Uses muted/zinc-neutral background

## Code Quality Gates

- `npx tsc --noEmit`: clean (0 errors)
- `npm run lint`: 6 pre-existing errors (useToolHistory.ts, I18nContext.tsx, ThemeContext.tsx, vitest.config.ts) — NONE in 12-07 files
- `npm test`: 43/43 pass

## Threat Flags

(None — Phase 12 reuses Phase 11 anonymizer-on-history-load trust boundary; no new surface.)

## Self-Check: PASSED

- All 5 created/modified files exist on disk
- All 3 commit hashes (`ffd5bf0`, `50b929a`, `4493fa0`) found in git log
- 16 new vitest tests pass; 27 existing tests still pass

## Commits

- `ffd5bf0` — feat(12-07): add buildInterleavedItems helper for per-round history reconstruction
- `50b929a` — feat(12-07): add SubAgentPanel + hasSubAgentState type guard
- `4493fa0` — feat(12-07): route sub_agent_state to SubAgentPanel and code_execution_state to CodeExecutionPanel

## Phase 12 Closeout

12-07 is the final plan in Phase 12. With 12-01 through 12-07 all executed, the Phase 12 (Chat UX — Context Window & Interleaved History) plan series is COMPLETE. CTX-01..06 (context window indicator) + HIST-01..06 (interleaved history) — 12 of 12 v1.2 requirements covered.
