# Phase 12: Chat UX — Context Window Indicator & Interleaved History - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 12-chat-ux-context-window-indicator-interleaved-history
**Mode:** `--auto` (autonomous, single-pass)
**Areas discussed:** Token-Usage Tracking Across Multi-Round Loop, Public Settings Endpoint Shape, Progress Bar Visual Placement & State Ownership, Per-Round Persistence Model, Sub-Agent / Code-Execution State Shape

---

## Token-Usage Tracking Across Multi-Round Tool Loop

| Option | Description | Selected |
|--------|-------------|----------|
| Track `last_prompt_tokens` + accumulate `completion_tokens`, plumb `stream_options` in `openrouter_service.py`, emit one terminal `usage` SSE event | PRD-aligned (last round's prompt_tokens is most accurate). Single end-of-exchange event keeps frontend state trivial. | ✓ |
| Per-round `usage` SSE events emitted as each round completes | Frontend bar climbs live during multi-round loops; more flicker; no observable benefit since user only acts after the response settles. | |
| Track usage outside `openrouter_service.py` (in chat.py only) | Forces duplicate `stream_options` flag in single-agent and multi-agent branches; brittle. | |

**Auto-selected (recommended default):** Track last `prompt_tokens` + accumulate `completion_tokens` + plumb `stream_options` in service + emit one terminal `usage` event before `done`.
**Notes:** `[auto] [Token-Usage Tracking] — Q: "How should backend track tokens across multi-round tool loop?" → Selected: "Track last_prompt_tokens + accumulate completion_tokens, single terminal usage SSE" (recommended default)`. Also handles graceful fallback when provider ignores `stream_options` (CTX-06): no usage chunk → no SSE emit → no errors.

---

## Public Settings Endpoint Shape

| Option | Description | Selected |
|--------|-------------|----------|
| New `backend/app/routers/settings.py` with `GET /settings/public` reading `app.config.settings.llm_context_window` directly (env-var driven, no auth) | Simple. Honors CTX-03 success criterion #5 ("env-var change without frontend redeploy updates the bar"). No DB write path. | ✓ |
| Route through `system_settings` table as a new column | Forces a migration + admin UI surface; `system_settings` is for admin-tunable runtime state, not deployment config. | |
| Embed context window value in the per-message SSE event | Couples deployment config to chat lifecycle; bar would be undefined until first message even at app load. | |

**Auto-selected:** Standalone unauth `GET /settings/public` endpoint sourced from Pydantic Settings.
**Notes:** `[auto] [Public Settings Endpoint] — Q: "Where does /settings/public read its data from?" → Selected: "config.settings.llm_context_window (env var, no DB)" (recommended default)`. Frontend caches via `usePublicSettings` hook (module-level cache, fetched once per app load).

---

## Progress Bar Visual Placement & State Ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Mount `<ContextWindowBar />` inside `MessageInput.tsx` above textarea (existing `max-w-2xl` container); state in `useChatState`, thread-scoped, reset on switch | Reuses existing input wrapper. Mirrors `streamingContent`/`sandboxStreams` thread-scoping. CTX-05 reset is a one-liner. | ✓ |
| Mount in `ChatPage` outside the input footer | Breaks the "inside the input footer" PRD wording; harder to align with the textarea. | |
| Token-usage state in `ChatContext` (global) | Forces re-renders on every chat consumer; thread-local hook state is correct scope. | |

**Auto-selected:** Mount in `MessageInput`, state in `useChatState`, reset on thread switch.
**Notes:** `[auto] [Progress Bar Placement] — Q: "Where does the bar live and what owns its state?" → Selected: "Inside MessageInput, useChatState-owned, thread-scoped" (recommended default)`. PRD says `max-w-3xl` but existing input is `max-w-2xl` — flagged for planner to confirm or adjust. Color thresholds: emerald-500 / amber-500 / rose-500 at <0.6 / <0.8 / >=0.8.

---

## Per-Round Persistence Model (HIST-01)

| Option | Description | Selected |
|--------|-------------|----------|
| One `messages` row per agentic round (replace single end-of-exchange insert with per-round inserts via `_persist_round_message` helper); each row carries that round's `tool_calls.calls[]` only | PRD-literal. Natural ordering via existing `created_at` column. `_expand_history_row` already supports per-row triplet expansion (Phase 11 D-P11-03). | ✓ |
| Single row per exchange, with rounds embedded as a JSONB array under `tool_calls.rounds[]` | Requires schema design + frontend reconstruction logic + breaks Phase 11's `_expand_history_row` triplet shape. | |
| Migrate existing rows + add explicit `round_index` column | Schema migration explicitly out of scope per REQUIREMENTS.md "Out of Scope". | |

**Auto-selected:** One `messages` row per round, parent_message_id chain, `_persist_round_message` helper.
**Notes:** `[auto] [Per-Round Persistence] — Q: "How are agentic rounds persisted?" → Selected: "One row per round, parent_message_id chained, helper extracted from existing single-insert" (recommended default)`. Backwards-compat: legacy single-row exchanges still load (legacy branch in `_expand_history_row`).

---

## Sub-Agent / Code-Execution State Shape (HIST-02, HIST-03, HIST-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Optional JSONB sub-keys on `ToolCallRecord` (`sub_agent_state: dict \| None`, `code_execution_state: dict \| None`), written at record-construction time, mirror live SSE event payloads exactly. Frontend reuses `CodeExecutionPanel` (Phase 11) and renders `SubAgentPanel` when sub_agent_state present. | No migration. Matches Phase 11 D-P11-08 backwards-compat pattern. Visual parity with live streaming via component reuse (HIST-05). | ✓ |
| Add new top-level columns on `messages` for sub_agent and code_execution state | Schema migration explicitly out of scope. | |
| Derive state at history-load time by re-running tools/sub-agents | O(N) extra LLM/sandbox cost per history load; unacceptable. | |

**Auto-selected:** Optional JSONB sub-keys, write-time materialization, frontend component reuse.
**Notes:** `[auto] [Sub-Agent / Code-Execution State] — Q: "Where do sub_agent_state and code_execution_state live and when are they materialized?" → Selected: "Optional JSONB sub-keys on ToolCallRecord, written at construction" (recommended default)`. 50 KB head-truncate validator (Phase 11 D-P11-04 parity) applies to `code_execution_state.stdout`/`stderr`; sub_agent_state generally <5 KB so no cap needed in v1.

---

## Claude's Discretion

- Exact Tailwind color tokens vs. design-system CSS variables (planner may swap to `--success`/`--warning`/`--danger` if defined in `index.css`).
- `usage` SSE event key naming (snake_case `prompt_tokens` chosen to match existing event convention).
- Bar animation: instant snap vs. 300ms tween (both acceptable).
- Empty-content round handling — whether to skip insert or persist sentinel (planner decides edge-case behavior).
- Exact Pydantic validator wording for `code_execution_state` size cap.
- Test split: unit tests for `ContextWindowBar`, `usePublicSettings`, integration tests for per-round persistence + reconstruction round-trip, backend test for unauth `/settings/public`.

## Deferred Ideas

- Persisting per-thread token-usage history (CTX-FUT-02; ephemeral state is acceptable for v1).
- Auto-detecting context window from provider APIs (CTX-FUT-01).
- Per-round `usage` SSE events (frontend trivial state preferred).
- Usage breakdown / hover tooltip with prompt vs completion split.
- Bar persistence across thread switch (CTX-05 explicit reset).
- Eager signed-URL refresh on history load (lazy refresh on download click is fine).
- Backfill migration for legacy single-row exchanges (legacy branch handles them).
- Truncation cap on `sub_agent_state` (deferred until observed bloat).
- Admin-tunable context window via `system_settings` (env-var is correct for deployment config).
