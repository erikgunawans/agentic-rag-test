---
phase: 11-code-execution-ui-persistent-tool-memory
plan: 05
subsystem: ui

tags: [typescript, react, hook, sse, frontend, code-execution, sandbox-streaming]

# Dependency graph
requires:
  - phase: 10-code-execution-sandbox-backend
    provides: "code_stdout / code_stderr SSE wire shape (D-P10-06: {type, line, tool_call_id})"
  - plan: 11-02
    provides: "frontend SSEEvent union widened with CodeStdoutEvent + CodeStderrEvent — discriminated-union narrowing on event.type now works without `as` casts"
provides:
  - "useChatState exposes sandboxStreams: Map<string, { stdout: string[]; stderr: string[] }> keyed by tool_call_id, updated on code_stdout / code_stderr SSE events"
  - "Live → persisted transition: Map clears in the post-stream finally; CodeExecutionPanel (Plan 11-06) reads persisted msg.tool_calls.calls[N].output afterward"
  - "Lifecycle reset on thread switch + new send + post-stream finally — three sites matching the activeTools/toolResults reset pattern"
affects: [11-06, 11-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Immutable Map update: setSandboxStreams((prev) => { const next = new Map(prev); next.set(key, {...cur, stdout: [...cur.stdout, line]}); return next }) — mirrors setActiveTools((prev) => [...prev, event]) immutability style for React-stable rendering"
    - "Live-stream buffer cleared at the same 3 lifecycle sites as activeTools/toolResults (handleSelectThread, sendMessageToThread, post-stream finally) — keyed by tool_call_id; prevents cross-thread leakage (T-11-05-1)"

key-files:
  created: []
  modified:
    - "frontend/src/hooks/useChatState.ts — +41 lines: 1 new state declaration, 2 new SSE handler branches, 3 lifecycle reset sites, 1 return-shape addition"

key-decisions:
  - "Stuck literally to the 3-site reset specified by the plan and threat model T-11-05-1 (handleSelectThread + sendMessageToThread + post-stream finally). handleNewChat and handleCreateThread also exist as entry points but they unconditionally clear allMessages/messages, so a stale Map has no rendering surface — adding resets there would be defensive-dead-code per the plan's explicit 3-site contract."
  - "Used immutable Map updates with explicit fallback `next.get(event.tool_call_id) ?? { stdout: [], stderr: [] }` (rather than spread-only) so the first event for a tool_call_id seeds a fresh entry rather than crashing on undefined — matches the threat model T-11-05-2 mitigation (Tampering / stale render)."
  - "Preserved the existing else { delta fallback } branch position. Both new code_stdout / code_stderr branches inserted BEFORE it so unknown future event types still hit the delta fallback — no change to non-execute_code SSE flow (Phase 5 SC#5 invariant; non-execute_code SSE flow byte-identical)."

requirements-completed: [SANDBOX-07]

# Metrics
duration: ~5m
completed: 2026-05-01
---

# Phase 11 Plan 05: useChatState SSE Buffer for Code Execution Streaming Summary

**`useChatState` now exposes `sandboxStreams: Map<tool_call_id, { stdout: string[]; stderr: string[] }>` and consumes Phase 10's `code_stdout` / `code_stderr` SSE events with immutable Map updates — bridging the previously-unhandled backend stream into the Code Execution Panel pipeline.**

## Performance

- **Duration:** ~5m (single task; one Edit pass per splice; no re-work needed once edits stuck)
- **Started:** 2026-05-01T13:00Z (approximate — execution began after worktree branch reset to `master` HEAD `6668fe8`)
- **Completed:** 2026-05-01T13:05:45Z
- **Tasks:** 1
- **Files modified:** 1
- **Net change:** +41 lines

## Accomplishments

- **State declaration** at L25-27: `sandboxStreams: Map<string, { stdout: string[]; stderr: string[] }>`. Map keyed by `tool_call_id` (the same UUID Phase 10 emits in every SSE event and Plan 11-04 will persist on `ToolCallRecord.tool_call_id`).

- **SSE handler cases** at L211-233: two new `else if` branches for `event.type === 'code_stdout'` and `'code_stderr'`, inserted BEFORE the existing `else { delta fallback }`. Both use an immutable Map update pattern that seeds a `{ stdout: [], stderr: [] }` entry on first event for a given `tool_call_id`, then appends the new line. The TypeScript discriminated-union narrowing means `event.line` and `event.tool_call_id` are typed `string` without casts — this is the payoff from Plan 11-02's union extension.

- **Three lifecycle reset sites:**
  - L68 in `handleSelectThread` — clears stale entries on thread switch (T-11-05-1 Information Disclosure mitigation; matches the `setRedactionStage(null)` reset cluster).
  - L148 in `sendMessageToThread` — fresh send starts with an empty buffer (alongside `setActiveTools([])` / `setToolResults([])`).
  - L264 in the post-stream `finally` block — clears the Map after the messages refetch completes; CodeExecutionPanel (Plan 11-06) then reads from persisted `msg.tool_calls.calls[N].output` instead.

- **Return-shape exposure** at L304: `sandboxStreams` added to the hook's return object alongside `activeTools` / `toolResults`, ready for `MessageView` (Plan 11-07) to thread down to `CodeExecutionPanel` (Plan 11-06) — but only for the actively-streaming message.

- **Non-`execute_code` SSE flow byte-identical:** the existing `if/else if` chain for `thread_title`, `agent_start`, `agent_done`, `tool_start`, `tool_result`, `redaction_status`, and the final `else { delta fallback }` is structurally unchanged. Verified by diff inspection — the only changes are the splice insertions, no existing branches reordered.

## Task Commits

Each task was committed atomically (single-task plan):

1. **Task 1: Add sandboxStreams state, SSE handlers, lifecycle resets, return-shape exposure** — `62efb5a` (feat)

## Files Created/Modified

- `frontend/src/hooks/useChatState.ts` — Added `sandboxStreams` state at L25-27, two SSE handler branches at L211-233, lifecycle resets at L68 / L148 / L264, return-shape exposure at L304. File grew from 277 → 318 lines (+41).

## Decisions Made

- **3 reset sites only — `handleNewChat` / `handleCreateThread` deliberately omitted.** The plan and threat model T-11-05-1 specifies exactly 3 reset sites (handleSelectThread + sendMessageToThread + post-stream finally). `handleNewChat` and `handleCreateThread` clear `allMessages`/`messages` unconditionally, so any leftover Map entry has no rendering surface. Adding redundant resets there would diverge from the plan's explicit contract and add maintenance noise. If a future hazard emerges (e.g., `MessageView` decides to render the buffer outside an active message context), the reset can be added then.

- **Immutable Map fallback initialization.** Used `next.get(event.tool_call_id) ?? { stdout: [], stderr: [] }` so the first stdout/stderr event for a given `tool_call_id` seeds a fresh entry rather than mutating undefined. Mirrors the `setActiveTools((prev) => [...prev, event])` immutability style at L195. Threat model T-11-05-2 (Tampering — mutable update yields React stale render) is mitigated by always returning a fresh `Map` instance from the setter callback.

- **Branch order preserved.** Inserted both new `else if` cases AFTER `redaction_status` and BEFORE the final `else { delta fallback }`. Unknown future SSE event types still flow into the delta fallback — Phase 5 SC#5 invariant preserved (non-execute_code SSE flow byte-identical).

## Deviations from Plan

**[Recoverable - Tooling] Working tree reset on first attempt — re-applied splices.**

- **Found during:** Task 1 — initial Edit pass appeared to apply but a subsequent `git status` showed clean working tree and `wc -l` reverted to 277 lines. Caused by an environmental artifact in the worktree (the worktree branch was initially behind `master`, and the recovery `git reset --hard master` occurred before edits were re-applied).
- **Fix:** Re-applied all 4 splices in sequence with intermediate `wc -l` and `grep -c` verification after each Edit to confirm persistence before proceeding to the next splice.
- **Files affected:** `frontend/src/hooks/useChatState.ts` (final state matches plan exactly).
- **Commit:** `62efb5a` — single task commit captures the full intended diff.

**No plan-substantive deviations.** The implementation matches the plan's `<action>` block verbatim — 4 splices, exact code text from the plan, exact lifecycle site coverage.

## Auth Gates Encountered

None.

## Test Coverage

**No test infrastructure exists for `useChatState` in the repo.** A search for `*useChatState*` test files returns only the hook source itself. Per the orchestrator's guidance ("if no test infrastructure exists for this hook, document the gap in SUMMARY's Test Coverage section and rely on Plan 11-07's UAT for end-to-end verification"), no new tests were added.

**Implications & follow-up:**
- The discriminated-union narrowing is enforced at compile time — `tsc --noEmit` would catch any regression where `event.line` or `event.tool_call_id` got incorrect types.
- The immutable Map update pattern is structurally identical to `setActiveTools((prev) => [...prev, event])` which has shipped successfully across Phases 5-10. No new mechanism risk.
- End-to-end behavior (live stream → persisted transition) is gated on Plan 11-06 (`CodeExecutionPanel`) and Plan 11-07 (`MessageView` plumbing). UAT in Plan 11-07 will exercise the full path.
- If a `useChatState` test infrastructure ever lands, the natural cases to add are: (a) `code_stdout` event appends to the correct tool_call_id, (b) thread switch clears the Map, (c) post-stream finally clears the Map, (d) unknown event types still hit the delta fallback.

## Issues Encountered

**1. Initial worktree state lagged master.** The worktree branch HEAD was at `7541fed` (Wave-0 master pre-Phase-11) when the orchestrator's prompt assumed `master` HEAD `6668fe8` (post-Plan-11-03 merge). Resolved by `git reset --hard master` per the workflow's `<worktree_branch_check>` protocol — the reset was safe because no agent work had been committed yet.

**2. Lint / tsc tooling not installed in worktree.** Ran `cd frontend && npm install` once to populate `node_modules` so `npx tsc --noEmit` and `npx eslint` could resolve. Standard worktree setup cost; no lasting state change.

**3. `grep -c` semantics confusion (resolved).** During verification, `grep -c "sandboxStreams"` reported 2 (counting matching lines, not occurrences). Confirmed via `grep -n "setSandboxStreams"` that all 6 expected occurrences were intact (1 declaration + 3 resets + 2 SSE handlers).

## Self-Check: PASSED

- File modified exists: `frontend/src/hooks/useChatState.ts` — FOUND (318 lines)
- Commit `62efb5a` — FOUND in `git log --oneline`
- All plan verify-block grep assertions pass:
  - `sandboxStreams` declaration — FOUND at L25
  - `code_stdout` SSE case — FOUND at L211
  - `code_stderr` SSE case — FOUND at L223
  - `setSandboxStreams(new Map())` count — 3 occurrences (matches plan `>= 3`)
  - `sandboxStreams,` in return shape — FOUND at L304
- `cd frontend && npx tsc --noEmit` exits 0
- `cd frontend && npx eslint src/hooks/useChatState.ts` exits 0
- Non-`execute_code` SSE flow byte-identical — verified by inspection of unchanged branches at L184-210 and the unchanged `else { delta fallback }` at L234-241.

## Next Phase Readiness

- **Plan 11-06 (`CodeExecutionPanel.tsx` NEW component):** Ready. Component can be passed `live: { stdout: string[]; stderr: string[] } | undefined` (from `sandboxStreams.get(toolCallId)`) and resolve `stdoutLines = live?.stdout ?? persistedOutput.stdout_lines ?? []` per the pattern in 11-PATTERNS.md §3.
- **Plan 11-07 (`MessageView` / `ToolCallList` plumbing):** Ready. Hook's return shape already exposes `sandboxStreams`; the plumbing layer just needs to thread it down only for the actively-streaming message (the same lifecycle window where `streamingContent` is populated).
- **Plan 11-04 (backend `chat.py` record-construction):** Independent and lateral — Plan 11-04's `tool_call_id` persistence is the source for the persisted-record fallback in Plan 11-06's panel. The two waves can land in any order; no ordering blocker.

No new blockers. Type contract and live-buffer mechanism are locked in.
