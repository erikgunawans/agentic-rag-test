# Phase 12: Chat UX — Context Window Indicator & Interleaved History - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning
**Mode:** `--auto` (single-pass; recommended-default selected for every gray area)

<domain>
## Phase Boundary

Two user-visible chat-UX deliverables, scoped together because they share the same SSE pipeline, the same `messages.tool_calls` JSONB column, and the same chat input footer:

1. **Context Window Usage Indicator (CTX-01..06)** — Slim progress bar above the chat input that shows `Xk / Yk (Z%)` with a green→yellow→red fill at the 60%/80% thresholds. Backend captures token counts via OpenAI-compatible `stream_options: {"include_usage": true}` and emits a `usage` SSE event before `done`. The bar's denominator comes from `GET /settings/public` (no auth) so changing `LLM_CONTEXT_WINDOW` env var without a frontend redeploy still updates the bar.

2. **Interleaved Chat History (HIST-01..06)** — Faithful replay of past chats on thread reload / switch. Backend persists **one `messages` row per agentic round** (not one row per exchange), preserving natural ordering by `created_at`. Sub-agent state and code-execution state are stored as JSONB sub-keys on `tool_calls.calls[N]` (`sub_agent_state`, `code_execution_state`) with **no schema migration**. Frontend reconstructs an interleaved `ConversationItem[]` so the order `text → tool calls → sub-agent panel → code-execution panel → text` is visually identical to live streaming.

**Deliverables:**

1. `backend/app/config.py` patch — Add `LLM_CONTEXT_WINDOW: int = 128_000` Pydantic Settings field.
2. `backend/app/routers/settings.py` — NEW router exposing `GET /settings/public` (no `get_current_user` dependency) that returns `{"context_window": settings.llm_context_window}`. Mounted in `backend/app/main.py`.
3. `backend/app/services/openrouter_service.py` patch — Pass `stream_options={"include_usage": True}` on every chat completion stream; capture the final-chunk `usage` payload and surface it to the caller (callback or return value).
4. `backend/app/routers/chat.py` patch — Track usage across the multi-round tool-calling loop: accumulate `completion_tokens` per round, retain the **last** round's `prompt_tokens` (most accurate snapshot), emit `usage` SSE event (`{type:"usage", prompt_tokens, completion_tokens, total_tokens}`) immediately before the terminal `delta:{done:true}`. Skip emit when no usage data is available (CTX-06 graceful fallback).
5. `backend/app/routers/chat.py` patch (HIST) — Change `_run_tool_loop` so each agentic round persists its own `messages` row (containing that round's `content` + that round's `tool_calls.calls[]`); the final user-visible text remains the LAST round (or its own row if final round had no tool calls). Each row's `tool_calls.calls[N]` carries `sub_agent_state` + `code_execution_state` JSONB sub-keys when applicable.
6. `backend/app/models/tools.py` patch — Extend `ToolCallRecord` with optional `sub_agent_state: dict | None` and `code_execution_state: dict | None`. JSONB-passthrough — no validators beyond what's needed for serialization safety.
7. `backend/app/routers/chat.py` patch — `_expand_history_row` already exists from Phase 11; extend to detect and pass through `sub_agent_state` / `code_execution_state` so the OpenAI tool-call triplet's `{role:"tool", content}` round-trip carries the same context the LLM saw live (HIST-06).
8. `frontend/src/lib/database.types.ts` patch — Extend `SSEEvent` with `UsageEvent` (`{type:"usage", prompt_tokens, completion_tokens, total_tokens}`). Extend `Message.tool_calls.calls[N]` type with optional `sub_agent_state` and `code_execution_state` mirrors of the backend Pydantic types. Add `PublicSettings` type for `GET /settings/public`.
9. `frontend/src/hooks/useChatState.ts` patch — Add `usage: { prompt: number, completion: number, total: number } | null` per-thread state. SSE handler appends `usage` event into this state. State resets to `null` on thread switch (CTX-05). On history load (`fetchMessages`), aggregate the last `usage` row's data if persisted (otherwise leave null until next message).
10. `frontend/src/components/chat/ContextWindowBar.tsx` — NEW slim progress bar (`h-1` track + `h-1` fill, `Xk / Yk (Z%)` text label). Tailwind utility classes only (zinc base, emerald-500 / amber-500 / rose-500 fill at 60%/80%). Reads `usage` from `useChatState`, denominator from a new `usePublicSettings` hook (cached fetch of `/settings/public`).
11. `frontend/src/components/chat/MessageInput.tsx` patch — Mount `<ContextWindowBar />` above the textarea, inside the `max-w-2xl` container (NOTE: PRD says `max-w-3xl` but existing input is `max-w-2xl`; use the existing container — flag for planner).
12. `frontend/src/hooks/usePublicSettings.ts` — NEW lightweight hook (`useEffect` + module-level cache) that fetches `/settings/public` once per app load.
13. `frontend/src/lib/messageTree.ts` patch — Reconstruct interleaved `ConversationItem[]` from per-round message rows. Process rows sequentially in `created_at` order; for each row emit text → tool-call panels (StepsPanel) → sub-agent panels (when `sub_agent_state` present) → code-execution panels (when `code_execution_state` present) → final assistant text.

**Out of scope (deferred):**

- Database persistence of per-message token counts (CTX-FUT-02 — frontend-state-only is acceptable for v1.2 indicator).
- Auto-detection of context window from provider APIs (CTX-FUT-01 — env-var driven for now).
- Schema migration for `tool_calls` JSONB sub-keys (explicit non-goal in REQUIREMENTS.md — JSONB is schema-flexible).
- Backfill of legacy single-row exchanges into per-round rows (legacy rows still load via existing `_expand_history_row` legacy branch).
- Tool registry / `tool_search` / sandbox bridge / MCP — Phase 13/14/15.

</domain>

<decisions>
## Implementation Decisions

> All decisions auto-picked per `--auto` mode rules (first option = recommended default). Inline rationale follows project conventions and prior-phase precedent.

### Token-Usage Tracking Across Multi-Round Tool Loop

- **D-P12-01:** **Track `last_prompt_tokens` and accumulate `completion_tokens` across rounds.** Per PRD §Feature 1: the multi-round loop sees `prompt_tokens` rise on each round (full history + accumulated tool results), so the LAST round's `prompt_tokens` is the most accurate snapshot. `completion_tokens` is purely additive across rounds — sum them. `total_tokens = last_prompt_tokens + sum(completion_tokens)`. Emit ONE `usage` SSE event at the end of the entire exchange (after the last LLM round, before the terminal `delta:{done:true}`). Do NOT emit per-round usage events — keeps the frontend state machine trivial and avoids flicker on the bar.
- **D-P12-02:** **`stream_options` is plumbed into `openrouter_service.py`, not chat.py.** Single source of truth: every chat stream initiated through `OpenRouterService.stream_chat_completion` automatically passes `stream_options={"include_usage": True}`. The service exposes captured usage to the caller via either a callback parameter or as a return-tuple. Mirrors how Phase 10's sandbox service exposes `stream_callback` (D-P10-05). Avoids scattering `stream_options` flags across both single-agent and multi-agent branches in chat.py.
- **D-P12-03:** **Provider compatibility — silently no-op when usage absent.** Per CTX-06: if a provider ignores `stream_options` (no usage chunk), the service captures `None`, chat.py simply skips emitting `usage` SSE, and the frontend bar never appears for that thread. No errors, no warnings logged at INFO level (a single DEBUG-level log is acceptable). LangSmith trace still records the round; just without the usage tag.

### Public Settings Endpoint Shape

- **D-P12-04:** **NEW `backend/app/routers/settings.py` with a single `GET /settings/public` endpoint.** Body: `{"context_window": int}`. Source of truth: `app.config.settings.llm_context_window` (Pydantic Settings reads `LLM_CONTEXT_WINDOW` env var, default 128000). NOT routed through `system_settings` table — context window is deployment-time config, not admin-tunable runtime state, and we want to honor "changing `LLM_CONTEXT_WINDOW` env var without a frontend redeploy" (CTX-03 success criterion #5) without forcing a DB write.
- **D-P12-05:** **No auth on `/settings/public`.** Explicit per requirement CTX-03 ("no auth required"). Mount in `main.py` BEFORE the `get_current_user`-guarded routers; the router itself has no `Depends(get_current_user)` on the endpoint. Future-proof: any field added to this endpoint later must be intentionally non-sensitive.
- **D-P12-06:** **Frontend caches the value per app load via a `usePublicSettings` hook.** Module-level cache so the fetch happens once. No long-poll, no refresh — env-var change requires a Railway redeploy (which itself triggers a new frontend session via Vercel cache bust on the next user load). Acceptable per "changing env var without a *frontend redeploy*" — the *backend* redeploy is what propagates the new value, and the next page load picks it up.

### Progress Bar Visual Placement & State Ownership

- **D-P12-07:** **Bar lives inside `MessageInput.tsx` above the textarea, inside the existing `max-w-2xl` container.** PRD says `max-w-3xl` but the actual existing input wrapper is `max-w-2xl`. Reuse the existing container — visual consistency with current design beats literal PRD wording. Flag the discrepancy for planner; if user later prefers the wider variant, that's a one-line CSS change.
- **D-P12-08:** **Token-usage state lives in `useChatState`, scoped per active thread.** New state: `usage: { prompt: number, completion: number, total: number } | null`. Reset to `null` when `currentThreadId` changes (CTX-05). Mirrors how `streamingContent` and `sandboxStreams` are already thread-scoped. Don't put it in `ChatContext` — context-scoped state would force re-renders on every other consumer; thread-local hook state is the right scope.
- **D-P12-09:** **Bar visibility: hidden until `usage !== null`, animates in on first usage event.** CSS opacity transition (200ms) once `usage` is non-null. Simple `{usage && <ContextWindowBar usage={usage} contextWindow={ctxWindow} />}` JSX guard — no separate "loading" state. CTX-05 explicit: "appears only after the first message exchange in a thread."
- **D-P12-10:** **Color thresholds via three CSS classes — emerald-500 (0–59%), amber-500 (60–79%), rose-500 (80–100%).** Tailwind tokens that match the design system (zinc-neutral base, no purple accent here — purple is reserved for primary actions). Threshold computation in JS, not CSS variables. Bar height: `h-1` (4px) — slim per PRD wording.

### Per-Round Persistence Model (HIST-01)

- **D-P12-11:** **One `messages` row inserted per agentic round, including the final round.** A round = one LLM completion + the tool calls produced by that completion. The final user-visible text becomes the LAST row's `content` (which may be empty if the final round only produced tool calls and no text). Each row carries that round's `tool_calls.calls[]` only — NOT the cumulative array. Natural ordering via `created_at` (existing column, indexed). All rows share the same `parent_message_id` chain (each round's row's `parent_message_id` points to the previous round's row, with the first round pointing to the user message).
- **D-P12-12:** **Replace the single end-of-exchange `client.table("messages").insert(insert_data)` (chat.py L817-829) with per-round inserts.** Insert happens immediately after each round's `tool_records` are finalized but before the next round's LLM call. Single code path used by both single-agent and multi-agent branches via a small `_persist_round_message(client, thread_id, user_id, parent_message_id, round_text, round_tool_records, agent_name) → message_id` helper. The returned `message_id` becomes the next round's `parent_message_id`.
- **D-P12-13:** **`_expand_history_row` already supports per-row triplet expansion (Phase 11 D-P11-03).** Phase 12 doesn't change the expansion logic — it only changes how MANY rows are emitted from the persistence side. Legacy single-row exchanges still load (legacy branch in `_expand_history_row` handles them). The frontend's interleaved reconstruction (D-P12-15) processes rows in `created_at` order regardless of how many rounds produced them.

### Sub-Agent / Code-Execution State Shape (HIST-02, HIST-03, HIST-05)

- **D-P12-14:** **`sub_agent_state` and `code_execution_state` are optional JSONB sub-keys on `ToolCallRecord`.** Pydantic schema: both `dict | None = None`. Written at record-construction time (chat.py multi-agent branch for sub_agent_state, sandbox branch for code_execution_state). NOT derived at read time — write-time materialization keeps history-load O(rows) with zero extra LLM/sandbox calls. Sub-keys mirror the *exact* shape the live SSE events carried (mode, document, reasoning, explorer tool calls for sub-agent; code, stdout, stderr, exit_code, execution_ms, files for code-exec). The 50 KB head-truncate Pydantic validator from Phase 11 (D-P11-04) already applies to `output`; a parallel validator caps `code_execution_state.stdout` + `stderr` at 50 KB each, since these can balloon. `sub_agent_state` is generally small (≤5 KB typical) — no cap needed for v1.
- **D-P12-15:** **Frontend reconstruction in `messageTree.ts` (or a sibling `historyReconstruction.ts`) emits `ConversationItem[]` keyed by `tool_call_id`.** For each row in `created_at` order: emit any `content` text first, then iterate `tool_calls.calls[N]` and emit one item per call — `ToolCallCard` for generic tools, `SubAgentPanel` (when `sub_agent_state` present), `CodeExecutionPanel` (when `code_execution_state` present, leveraging the existing Phase 11 component which already keys by `tool_call_id`). Visual parity with live streaming is the success criterion (HIST-05) — components reuse exactly. The per-round flattening means the rendered transcript is naturally interleaved with no extra ordering logic.
- **D-P12-16:** **HIST-06 (LLM context reconstruction for follow-ups) — leverage existing `_expand_history_row` triplet expansion.** Each persisted round row already produces the OpenAI `{assistant + tool_calls}` → `{tool, content}` × N → `{assistant, text}` triplet via Phase 11 logic. Multi-row threads naturally concatenate into the full historical context. Phase 12 only ensures `sub_agent_state` and `code_execution_state` data flow into the `{role:"tool", content}` payload (likely embedded inside `output` already; verify during planning that nothing is dropped).

### Claude's Discretion

- Exact Tailwind color values for the three threshold bands — emerald-500 / amber-500 / rose-500 are strong defaults, but planner may swap to design-token CSS variables if `--success`, `--warning`, `--danger` exist in `index.css`.
- Whether `usage` SSE event payload uses snake_case (`prompt_tokens`) or camelCase keys — match existing SSE event convention (snake_case per `redaction_status`, `tool_start`, `code_stdout`).
- Bar animation choice: instant snap to new percentage on each `usage` event, or 300ms tween. Both acceptable; tween is slightly nicer.
- Persisting empty-content rounds — if a round has no tool calls AND no text (shouldn't happen but possible), planner decides whether to skip the insert or persist a sentinel.
- Whether to include a `usage` event in the persisted history (so reload shows the last bar position) — explicit non-goal per CTX (ephemeral / frontend-only state), but planner may surface this as a future enhancement.
- Test split: unit tests for `ContextWindowBar` (color thresholds, label format, hidden state), unit tests for `usePublicSettings` (cache behavior, error fallback), integration test for chat.py per-round persistence (3-round multi-agent transcript loads as 3 rows + reconstructs identically), backend test for `GET /settings/public` (no-auth, returns env-driven value).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Specification

- `docs/superpowers/PRD-advanced-tool-calling.md` §Feature 1 — Context Window Usage Indicator: backend usage capture, SSE delivery, frontend rendering, color thresholds, UI placement, design decisions (no DB persistence, provider compatibility, manual context limit).
- `docs/superpowers/PRD-advanced-tool-calling.md` §Feature 2 — Chat History Interleaved Rendering: per-round message persistence, rich state persistence (`sub_agent_state` + `code_execution_state` JSONB), faithful reconstruction, no schema migration.

### Requirements & Roadmap

- `.planning/REQUIREMENTS.md` §CTX-01..06 — Context window indicator (6 requirements; usage capture, SSE event, public settings endpoint, frontend bar, visibility/reset, graceful provider fallback).
- `.planning/REQUIREMENTS.md` §HIST-01..06 — Interleaved history (6 requirements; per-round rows, sub-agent state, code-execution state, frontend reconstruction, visual parity, multi-row LLM context).
- `.planning/REQUIREMENTS.md` §"New Configuration Surface" — `LLM_CONTEXT_WINDOW=128000` env var.
- `.planning/REQUIREMENTS.md` §"Out of Scope" — DB persistence of per-message token counts; auto-detect context window; schema migration for `tool_calls` JSONB sub-keys (all explicit non-goals).
- `.planning/ROADMAP.md` §Phase 12 — 5 success criteria (authoritative scope anchor).

### Prior Phase Decisions (binding)

- `.planning/phases/11-code-execution-ui-persistent-tool-memory/11-CONTEXT.md` — D-P11-03 (legacy-row triplet skip), D-P11-04 (50 KB head-truncate validator), D-P11-07 (MEM applies to all tools), D-P11-08 (`ToolCallRecord` shape extension pattern), D-P11-10 (anonymizer integration in history loading), D-P11-11 (truncation lives at construction). Phase 12 extends `ToolCallRecord` with two more optional JSONB sub-keys using the same pattern.
- `.planning/phases/10-code-execution-sandbox-backend/10-CONTEXT.md` — D-P10-06 (SSE event shape `{type, line, tool_call_id}`), D-P10-07 (`tool_result` payload shape — same fields Phase 12 persists into `code_execution_state`), D-P10-08 (errors via `code_stderr`, `tool_result` carries `exit_code` + `error_type`).
- `.planning/phases/09-skills-frontend/09-CONTEXT.md` — Sub-agent panel rendering pattern (relevant for HIST-05 visual parity).
- `.planning/phases/08-llm-tool-integration-discovery/08-CONTEXT.md` — Multi-agent branch in chat.py (the path that produces `sub_agent_state` data).

### Codebase Conventions

- `.planning/codebase/STRUCTURE.md` — Repo layout, key file roles (chat.py god-node, messageTree.ts).
- `.planning/codebase/ARCHITECTURE.md` §Flow 1 — Chat with tool-calling and SSE streaming.
- `.planning/codebase/CONVENTIONS.md` — Pydantic schemas, FastAPI router conventions, Tailwind class conventions.
- `CLAUDE.md` §"system_settings is a single-row table with columns" — clarifies why context_window is config-derived NOT system_settings-derived (D-P12-04).
- `CLAUDE.md` §Design System — 2026 Calibrated Restraint (no `backdrop-blur` on persistent panels, no gradients, flat solid; relevant for ContextWindowBar styling).

### Code Integration Points (must read)

- `backend/app/routers/chat.py` — SSE emission patterns (search `yield f"data:`), per-round loop in `_run_tool_loop` (~L300-L600 single-agent, L900-L1100 multi-agent), persistence at L817-829 (the single-insert site Phase 12 splits per-round), `_expand_history_row` at L97 (extend for `sub_agent_state` / `code_execution_state` passthrough).
- `backend/app/services/openrouter_service.py` — Streaming helper that needs `stream_options={"include_usage": True}` plumbed in.
- `backend/app/models/tools.py` — `ToolCallRecord` (Phase 11 shape; Phase 12 adds two optional fields). `ToolCallSummary` for the JSONB envelope.
- `backend/app/config.py` — Add `LLM_CONTEXT_WINDOW` Pydantic Settings field.
- `backend/app/main.py` — Mount the new `settings` router.
- `frontend/src/components/chat/MessageInput.tsx` — Existing `max-w-2xl rounded-2xl` input wrapper — `<ContextWindowBar />` mounts inside, above the textarea.
- `frontend/src/hooks/useChatState.ts` — Existing SSE handler dispatcher (~L172-L210); add `usage` case + thread-scoped `usage` state.
- `frontend/src/lib/database.types.ts` — `SSEEvent` discriminated union (~L73-L92); add `UsageEvent`. `Message` type's `tool_calls.calls[N]`; add optional `sub_agent_state` and `code_execution_state`.
- `frontend/src/lib/messageTree.ts` — Existing tree-building helpers; extend or sibling-add reconstruction logic for per-round rows.
- `frontend/src/components/chat/CodeExecutionPanel.tsx` — Existing Phase 11 panel; reused at history-reload time when `code_execution_state` present.
- `frontend/src/components/chat/MessageView.tsx` — `tool_calls.calls` render at L97-101; reconstruction extension surfaces here.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`_expand_history_row` (`backend/app/routers/chat.py` L97-145)** — Phase 11 helper that already produces the OpenAI tool-call triplet from a persisted row. Phase 12 keeps the function signature; per-round persistence (D-P12-11) just means it runs once per row instead of once per exchange. Sub-key passthrough (HIST-06) is a small extension.
- **`ToolCallRecord` / `ToolCallSummary` (`backend/app/models/tools.py`)** — Phase 11 shape (`tool`, `input`, `output`, `error`, `tool_call_id`, `status`). Phase 12 adds `sub_agent_state: dict | None` and `code_execution_state: dict | None` — same backwards-compatible pattern as Phase 11.
- **`OpenRouterService.stream_chat_completion`** — Single LLM streaming path used by both single-agent and multi-agent branches. Plumb `stream_options={"include_usage": True}` here once and every caller benefits (D-P12-02).
- **`useChatState` SSE dispatcher (`frontend/src/hooks/useChatState.ts` ~L172-L210)** — Existing event-type switch with cases for `tool_start`, `tool_result`, `delta`, `agent_start`, `agent_done`, `redaction_status`, `code_stdout`, `code_stderr`, `thread_title`. Phase 12 adds a `usage` case; thread-scoped state reset already exists for streaming buffers.
- **`SSEEvent` discriminated union (`frontend/src/lib/database.types.ts` L73-L92)** — Type-safe event union; Phase 12 adds `UsageEvent` variant.
- **`CodeExecutionPanel` (`frontend/src/components/chat/CodeExecutionPanel.tsx`)** — Phase 11 component that already reads from persisted `tool_calls.calls[N].output` after refetch. Phase 12 history reconstruction reuses it directly when `code_execution_state` is present (HIST-05 visual parity).
- **`MessageInput` (`frontend/src/components/chat/MessageInput.tsx`)** — Existing chat input; ContextWindowBar mounts here (D-P12-07).
- **`apiFetch` (`frontend/src/lib/api.ts`)** — Used for `usePublicSettings` hook fetch of `/settings/public`. Note: `/settings/public` is unauth, but `apiFetch` injects Bearer JWT — either special-case or use plain `fetch` for this endpoint (planner discretion).
- **`get_system_settings()` (`backend/app/services/system_settings_service.py`)** — Reference for how the project caches read-mostly settings (60s TTL). NOT used here per D-P12-04 — context_window is env-var driven, not DB-driven.

### Established Patterns

- **SSE event JSON shape** — Every event has `type` discriminator; payload fields are flat snake_case (`tool_call_id`, `prompt_tokens`). New `usage` event follows: `{"type": "usage", "prompt_tokens": N, "completion_tokens": N, "total_tokens": N}`.
- **`messages.tool_calls` JSONB column** — Schema-flexible. Phase 11 added `tool_call_id` + `status` to `tool_calls.calls[N]` without a migration; Phase 12 adds `sub_agent_state` + `code_execution_state` the same way (REQUIREMENTS.md "Out of Scope" explicitly precludes a migration).
- **Pydantic optional-field extension** — Phase 11 D-P11-08 pattern: add new fields as `Optional` with `None` defaults so legacy persisted rows still validate. Phase 12 follows.
- **Per-round insert vs. single-insert** — Currently single-insert at chat.py L817-829 (after the entire stream completes). Phase 12 changes this — but the existing pattern (`client.table("messages").insert({...})`) is the building block; per-round just means N inserts in the loop instead of 1 at the end.
- **Frontend thread-scoped state** — `useChatState` already manages `streamingContent`, `sandboxStreams: Map<...>`, etc. with thread-switch reset. Add `usage` to the same lifecycle.
- **Public-config-via-env-var pattern** — `LLM_CONTEXT_WINDOW`, `TOOL_REGISTRY_ENABLED`, `SANDBOX_ENABLED` all share this pattern (env → Pydantic Settings → endpoint or chat-loop check). Adds zero DB surface.
- **`_anonymize_history_text` reuse for reconstructed tool messages (D-P11-10)** — Still applies in Phase 12: when `redaction_on=True`, the `{role:"tool", content}` reconstructed messages flow through the same anonymizer batch. Phase 12's per-round split means the batch is slightly larger (more tool messages) but the path is unchanged.

### Integration Points

- **`backend/app/config.py`** — Add `llm_context_window: int = 128_000` to the existing `Settings` class. Pydantic Settings reads `LLM_CONTEXT_WINDOW` env var automatically.
- **`backend/app/routers/settings.py`** (NEW, ~30 lines) — Single FastAPI router with one unauth GET endpoint. Mounted in `main.py` alongside other routers.
- **`backend/app/services/openrouter_service.py`** — Streaming method's `extra_body` (or equivalent) gets `stream_options={"include_usage": True}`. Capture the final-chunk usage and either return as part of the result or invoke a callback.
- **`backend/app/routers/chat.py`** — Three changes: (1) `_persist_round_message` helper extracted from the existing single-insert; (2) `_run_tool_loop` calls it once per round (both single-agent and multi-agent branches); (3) tracks `cumulative_completion_tokens` and `last_prompt_tokens` across rounds, emits one `usage` SSE event before the terminal `done`.
- **`backend/app/models/tools.py`** — Two new optional fields on `ToolCallRecord`. Optional Pydantic validator on `code_execution_state.stdout`/`stderr` for the same 50 KB head-truncate as `output` (D-P11-04 parity).
- **`frontend/src/components/chat/ContextWindowBar.tsx`** (NEW, ~40 lines) — Props: `{ usage: { prompt: number, completion: number, total: number }, contextWindow: number }`. Internal: compute percentage, pick color band, render `h-1` track + fill + label.
- **`frontend/src/hooks/usePublicSettings.ts`** (NEW, ~20 lines) — Fetches `/settings/public` once, caches in module scope, returns `{ contextWindow: number | null }`.
- **`frontend/src/hooks/useChatState.ts`** — Add `usage` state field, thread-switch reset, SSE handler case.
- **`frontend/src/components/chat/MessageInput.tsx`** — Mount `<ContextWindowBar />` above textarea.
- **`frontend/src/lib/database.types.ts`** — Extend `SSEEvent` and `Message.tool_calls.calls[N]` types.
- **`frontend/src/lib/messageTree.ts`** (or new sibling) — Add helper that flattens `messages` rows (multiple per exchange) into interleaved `ConversationItem[]`.

</code_context>

<specifics>
## Specific Ideas

- **`usage` SSE payload shape:** `{"type": "usage", "prompt_tokens": 12345, "completion_tokens": 678, "total_tokens": 13023}`. Snake_case to match existing events.
- **`/settings/public` payload:** `{"context_window": 128000}` — single field. Future-extensible: anything added must remain non-sensitive.
- **Bar text format:** `45k / 128k (35%)` per PRD literal. `k` for thousands (1k = 1000, divisor `Math.round(n / 1000)` for both numerator and denominator). At <1000 tokens, render as raw number (`523 / 128k (0%)`).
- **Color thresholds (exact):** `< 0.6 → emerald-500`, `>= 0.6 && < 0.8 → amber-500`, `>= 0.8 → rose-500`. Background track: `bg-zinc-200 dark:bg-zinc-800`. Bar height: `h-1` (4px).
- **Visibility transition:** `opacity-0 → opacity-100` over 200ms once `usage` becomes non-null. Mount/unmount the bar in JSX (not just opacity) so it doesn't take vertical space when hidden.
- **Per-round insert helper signature:**
  ```python
  def _persist_round_message(client, *, thread_id: str, user_id: str,
                              parent_message_id: str, content: str,
                              tool_records: list[ToolCallRecord],
                              agent_name: str | None) -> str:
      """Insert one assistant message row for a single agentic round.
      Returns the new message_id (becomes parent_message_id for the next round)."""
      insert_data = {
          "thread_id": thread_id,
          "user_id": user_id,
          "role": "assistant",
          "content": content,
          "parent_message_id": parent_message_id,
      }
      if tool_records or agent_name:
          insert_data["tool_calls"] = ToolCallSummary(
              agent=agent_name, calls=tool_records,
          ).model_dump()
      result = client.table("messages").insert(insert_data).execute()
      return result.data[0]["id"]
  ```
- **`sub_agent_state` shape (HIST-02):** `{"mode": "explorer"|"analysis", "document_id": str|None, "reasoning": str, "explorer_tool_calls": [{"tool": str, "input": dict, "output": dict|str, "tool_call_id": str}]}` — mirror exactly what the live `agent_start`/`agent_done` events carried.
- **`code_execution_state` shape (HIST-03):** `{"code": str, "stdout": str, "stderr": str, "exit_code": int, "execution_ms": int, "files": [{"filename": str, "size_bytes": int, "signed_url": str|None}], "error_type": str|None}` — mirror the Phase 10 `tool_result` payload exactly. Note: `signed_url` may be expired at history-load time; planner decides whether to refresh on render via `GET /code-executions/{id}` (existing Phase 11 D-P11-06 path).
- **Context window display divisor:** `Math.round(n / 1000)` for both prompt and total. Avoid `Math.floor` (would show 999 → 0k). Use `(percentage * 100).toFixed(0)` for the `%` portion.
- **`useChatState` thread-switch reset:** Existing reset at thread switch already clears `streamingContent`. Phase 12 reset clears `usage` at the same site (single line addition: `setUsage(null)`).
- **History reconstruction order test:** Given a 2-round exchange (round 1: user query → search_documents tool → text; round 2: same row → execute_code → text), reload should produce: text₁ → SearchPanel → text-mid → CodeExecutionPanel → text₂ — visually identical to live streaming order.
- **No new env var required for `LLM_CONTEXT_WINDOW` to land** — Pydantic Settings default is `128000`; admin sets it explicitly only when the deployment uses a non-default model.

</specifics>

<deferred>
## Deferred Ideas

- **Persisting per-thread token-usage history** (CTX-FUT-02) — Out of scope for v1.2; ephemeral frontend state is acceptable. Would enable analytics (cost per thread, trending usage) — future milestone.
- **Auto-detecting context window from provider APIs** (CTX-FUT-01) — OpenRouter `/models` and Ollama `/api/show` both expose model-specific limits. Future enhancement; v1.2 uses env var.
- **Per-round usage SSE events** (vs. one terminal event) — Discarded per D-P12-01 to keep frontend trivial. Could revisit if users want a "live" climbing bar during multi-round tool loops.
- **Showing usage breakdown** (`prompt_tokens` vs `completion_tokens` separate bars, or hover tooltip) — PRD spec is a single bar with single label; richer disclosure is a polish item.
- **Bar persistence across thread switch** (showing the most recent thread's usage on switch-back) — Discarded per CTX-05 explicit reset; could revisit if users complain about losing context indicator.
- **Refreshing expired signed URLs on history load** for `code_execution_state.files` — Phase 11 D-P11-06 already handles refresh via `GET /code-executions/{id}` on download click. Eager refresh on render rejected as wasteful (most files never re-downloaded).
- **Backfill migration** to split legacy single-row exchanges into per-round rows — Discarded per HIST-01 "no schema migration" and the legacy-row branch in `_expand_history_row` (Phase 11 D-P11-03) handles them gracefully. Conversation-level interleaving for legacy threads would be best-effort; documented as a known gap.
- **Renaming `output` → `result` on `ToolCallRecord`** — Already discarded in Phase 11 D-P11-08; noted again so planner doesn't re-litigate.
- **Truncation cap on `sub_agent_state`** — Not added in v1; sub-agent payloads are typically <5 KB. If observed bloat occurs, add the same 50 KB head-truncate validator as `code_execution_state.stdout`.
- **Per-tool `usage` SSE channel** (not the LLM `usage` event but per-tool token attribution) — Out of v1.2 scope; would require provider-side per-tool accounting that doesn't exist.
- **Admin-tunable context window via system_settings** — Discarded per D-P12-04; would require a DB write path and admin-UI surface for negligible benefit. Env-var driven is correct for deployment-time config.

</deferred>

---

*Phase: 12 — Chat UX — Context Window Indicator & Interleaved History*
*Context gathered: 2026-05-02*
*Mode: --auto (single-pass; recommended-default selected for every gray area)*
