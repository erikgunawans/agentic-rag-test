---
phase: 12-chat-ux-context-window-indicator-interleaved-history
plan: 05
status: complete
requirements: [CTX-01, CTX-02, CTX-04, CTX-05, HIST-02, HIST-03]
tests_added: 6
tests_passing: 6
---

# Plan 12-05 Summary: Frontend Type Plumbing + usePublicSettings + useChatState usage state

## What Was Built

### 1. `database.types.ts` extensions
- **`ToolCallRecord`**: Added optional `sub_agent_state?: Record<string, unknown> | null` (HIST-02) and `code_execution_state?: Record<string, unknown> | null` (HIST-03), mirroring backend Plan 12-01.
- **`UsageEvent`**: New SSE event interface — `{type:'usage', prompt_tokens, completion_tokens, total_tokens}` with `number | null` for each token field (CTX-06 graceful no-op semantics).
- **`SSEEvent` union**: Extended with `| UsageEvent`.
- **`PublicSettings`**: New interface `{context_window: number}` for GET /settings/public response.

### 2. `usePublicSettings` hook (NEW)
- Module-level `cachedState` + `inFlight` Promise — single fetch per app load, shared across all consumers (no thundering-herd).
- Plain `fetch` (NOT `apiFetch`) — endpoint is unauth so no Authorization header is injected.
- Returns `{contextWindow: number | null, error: Error | null}`.
- Test escape hatch: `_resetPublicSettingsCacheForTests()` exported for vitest isolation.
- HTTP error handling: non-OK responses → `error: Error("HTTP {status}")`.
- Network failure handling: rejected fetch → `error: <Error>`, `contextWindow: null`.

### 3. `useChatState` extensions
- **State**: New `usage` state — `{prompt: number | null, completion: number | null, total: number | null} | null`. Defaults to null.
- **SSE handler**: `else if (event.type === 'usage')` branch sets the state with raw provider values.
- **Resets**: `setUsage(null)` added to:
  - `handleSelectThread` — thread switch (D-P12-08 / D-P12-09)
  - `sendMessageToThread` start — fresh exchange
  - `handleNewChat` — new-chat (no active thread)
- **Return**: `usage` exposed alongside `sandboxStreams` for components to consume.

## Key Decisions Honored

- **D-P12-06**: Module-level cache, single fetch per app load, no Authorization header
- **D-P12-08**: usage state lives in useChatState, NOT ChatContext (per-thread reset locality)
- **D-P12-09**: Reset to null on thread switch ensures the bar disappears until next exchange
- **CTX-06**: Provider may emit null token values; stored as-is, component decides how to render

## Files Changed

- `frontend/src/lib/database.types.ts` — added UsageEvent, PublicSettings, extended ToolCallRecord + SSEEvent (~24 lines added)
- `frontend/src/hooks/usePublicSettings.ts` — NEW (~75 lines)
- `frontend/src/hooks/usePublicSettings.test.ts` — NEW; 6 vitest tests
- `frontend/src/hooks/useChatState.ts` — added usage state + SSE handler + 3 reset sites + return field (~25 lines added)

## Verification

```
npx tsc --noEmit                              → clean (0 errors)
npm run test -- usePublicSettings             → 6/6 passed
npm run lint                                  → no NEW errors on Phase 12 files
                                                (5 preexisting errors on master remain;
                                                they predate Phase 12)
```

## Test Coverage (6)

1. `fetches once on first mount` — single fetch call to `/settings/public`
2. `shares fetch across multiple mounts` — second hook mount reuses in-flight Promise
3. `returns null while pending` — pre-resolution state shape
4. `handles fetch failure gracefully` — rejected promise → error in state, no throw
5. `handles non-200 status` — HTTP 500 → error includes status code
6. `does not inject Bearer JWT` — no Authorization header in fetch options

## Lint Note

The repo has 5 preexisting lint errors on master (`useToolHistory.ts`, `I18nContext.tsx`, `ThemeContext.tsx`, `vitest.config.ts`). My new code does NOT add to that count — `usePublicSettings.ts` uses a single targeted `eslint-disable-next-line react-hooks/set-state-in-effect` for the cache-rehydration setState, which is the documented external-system-sync use case.

## Self-Check: PASSED

All 6 must_haves truths verified:
- UsageEvent + ToolCallRecord sub-keys + PublicSettings present in types
- usePublicSettings module-level cache + fetch dedupe
- useChatState usage state + SSE handler + thread-switch reset
- 6 hook tests pass
- TypeScript compiles cleanly; no new lint errors
