# Phase 17: Deep Mode Foundation + Planning Todos + Plan Panel - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** `--auto` (decisions auto-resolved from project defaults)

<domain>
## Phase Boundary

Deliver the foundation of the General-Purpose Agent Harness (Deep Mode):

1. **Per-message Deep Mode toggle** — UI button next to Send that flags the next message to route through an extended agent loop (extended system prompt, deep-mode tools loaded, `MAX_DEEP_ROUNDS=50` cap). When OFF, behavior is byte-identical to v1.2 (zero token overhead, no extra tools, no extended prompt).
2. **Planning Todos system** — `agent_todos` table with RLS (thread-ownership scope), `write_todos` (full-replacement) and `read_todos` LLM tools, recitation pattern in deep-mode system prompt, adaptive replanning (add / remove / rewrite mid-execution), `todos_updated` SSE event on every mutation.
3. **Plan Panel sidebar UI** — real-time todo state display (pending → in_progress → completed), Deep Mode badge on deep-mode messages, history reconstruction on thread reload from `agent_todos` + `messages.deep_mode`.
4. **Migrations** — `038_agent_todos.sql` creates `agent_todos` table + RLS + adds `messages.deep_mode` boolean (single migration; MIG-01 + MIG-04 bundled — see D-MIG-01).
5. **Loop discipline** — graceful summarize-and-deliver fallback at `MAX_DEEP_ROUNDS`, mid-loop interrupt safety (all completed work persists). Loop-cap env vars `MAX_DEEP_ROUNDS=50`, `MAX_TOOL_ROUNDS=25`, `MAX_SUB_AGENT_ROUNDS=15` (CONF-01..03).

**Explicitly NOT in this phase** (enforced by ROADMAP.md scope):
- Workspace Filesystem (Phase 18 — `workspace_files` table, file tools, Workspace Panel).
- Sub-agent `task` tool, `ask_user`, agent status indicators, error recovery (Phase 19).
- Harness engine, gatekeeper, post-harness LLM, file upload, locked Plan Panel (Phase 20).
- Batched parallel sub-agents, HIL phase type (Phase 21).
- Contract Review domain harness, DOCX deliverable (Phase 22).

</domain>

<decisions>
## Implementation Decisions

### Migration Strategy

- **D-01 (MIG-01 + MIG-04 bundled into a single migration):** `supabase/migrations/038_agent_todos_and_deep_mode.sql` creates `agent_todos` table + RLS, and `ALTER TABLE messages ADD COLUMN deep_mode BOOLEAN NOT NULL DEFAULT false` in the same migration. Reason: simpler reviewer story, both columns serve the same Phase 17 feature (Deep Mode persistence + plan panel reconstruction), atomic ship. `harness_mode TEXT` is NOT added in this migration — that ships with Phase 20's `harness_runs` migration (040). State.md mention of "041" is reconciled by collapsing it into Phase 17's 038.
- **D-02 (Numbering):** Migration `038` follows v1.2's last applied migration (`037`). Sequential, no gap.
- **D-03 (RLS pattern):** `agent_todos` enforces thread-ownership via thread JOIN — `EXISTS (SELECT 1 FROM threads WHERE threads.id = agent_todos.thread_id AND threads.user_id = auth.uid())`. Mirrors the v1.0/v1.1 pattern used in `code_executions`/`skill_files`. Direct `auth.uid() = user_id` is also added as a defense-in-depth column (`agent_todos.user_id` mirrored from `threads.user_id` on insert) so the RLS policy can short-circuit without a JOIN if the row carries the user_id directly.
- **D-04 (Schema):** `agent_todos` columns:
  - `id UUID PK default gen_random_uuid()`
  - `thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE`
  - `user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE` (defense-in-depth + RLS short-circuit)
  - `content TEXT NOT NULL`
  - `status TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed'))`
  - `position INTEGER NOT NULL` (ordering within a thread; full-replacement writes use 0..N-1)
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` (with `handle_updated_at` trigger reused from migration 001)
- **D-05 (Indexes):** `idx_agent_todos_thread (thread_id, position)` for ordered list reads; `idx_agent_todos_user (user_id, created_at DESC)` for admin auditing.
- **D-06 (Full-replacement write semantics):** `write_todos` deletes ALL rows for `thread_id` and re-inserts the new full list within a single transaction (Supabase RPC or two-step). Eliminates partial-update edge cases and matches PRD Feature 1.2's full-replacement design.
- **D-07 (`messages.deep_mode` default):** `BOOLEAN NOT NULL DEFAULT false`. Backfill is a no-op (default applies to existing rows). UI history reconstruction reads this column to render the Deep Mode badge.

### Loop Architecture (Deep Mode Branch)

- **D-08 (Hand-coded loop, no LangChain/LangGraph):** Deep mode is a NEW branch in `backend/app/routers/chat.py` that mirrors the existing tool-calling loop pattern (`for _iteration in range(max_iterations)` at lines 400, 1220) but uses `MAX_DEEP_ROUNDS=50`, loads deep-mode tools, and assembles an extended system prompt. Reuses existing pre-flight egress filter, per-round persistence (`tool_calls` JSONB), and SSE event taxonomy. This honors the v1.0–v1.2 invariant: raw SDK only.
- **D-09 (Extended system prompt assembly):** Deep mode prompt = base prompt + 4 deterministic sections (planning instructions, recitation pattern, sub-agent stub for Phase 19, ask-user stub for Phase 19). KV-cache friendly: no timestamps, no volatile data, todo state flows through tools (NOT prompt). Sub-agent / ask-user stubs are placeholders in Phase 17 — Phase 19 wires the actual tools. The stub guidance in the prompt is fine for KV-cache stability.
- **D-10 (Tool loading):** When `deep_mode=true`, the loop loads: existing tools (search_documents, query_database, web_search, code execution if enabled, skills, MCP, etc.) PLUS deep-mode foundation tools (`write_todos`, `read_todos`). NO `task`, `ask_user`, `write_file`/`read_file`/`edit_file`/`list_files` in Phase 17 — those land in Phases 18/19.
- **D-11 (Loop entry point):** New parameter `deep_mode: bool` on the chat SSE endpoint payload. When `true`, `/chat` routes to the new deep-mode branch; when `false` or absent, behavior is identical to v1.2. The decision splits at the request handler — no shared inner loop changes (preserves the byte-identical fallback invariant from v1.2 D-P13-01 / DEEP-03).
- **D-12 (Loop exhaustion fallback):** At iteration `MAX_DEEP_ROUNDS - 1`, if the LLM still emits tool_calls, the system swaps the next round's tool list with an empty list AND injects a system message "You have reached the iteration limit. Please summarize what you have completed and deliver a final answer to the user." This forces a terminal text round per DEEP-06.
- **D-13 (Mid-loop interrupt):** Existing SSE-disconnect handling preserves all completed work because each round already persists messages + tool_calls + (now) todos to DB. No new code path needed beyond ensuring `write_todos` commits to DB synchronously before SSE event emission.

### Configuration & Deployment

- **D-14 (Env-driven loop caps, NOT system_settings):** `MAX_DEEP_ROUNDS=50`, `MAX_TOOL_ROUNDS=25`, `MAX_SUB_AGENT_ROUNDS=15` are added to `backend/app/config.py` as Pydantic `Settings` fields (env vars). Reason: deployment knobs (Railway env), not user-configurable runtime settings; matches the existing `tools_max_iterations`, `llm_context_window` precedent (env-driven, surfaced via config). System_settings is reserved for admin-toggleable runtime settings (PII toggle, RAG provider, etc.).
- **D-15 (`tools_max_iterations` migration):** The legacy `settings.tools_max_iterations: int = 5` (chat.py line 992) is REPLACED by `MAX_TOOL_ROUNDS` env var (default 25 per CONF-02). The default jumps from 5 → 25 to match the v1.3 spec. Migration: keep `tools_max_iterations` as a deprecated alias for one milestone, log a deprecation warning on read; default-derived from `MAX_TOOL_ROUNDS` if both are unset. Document in CHANGELOG and STATE.md deferred items.
- **D-16 (Feature gating):** Deep Mode ships behind a feature flag `DEEP_MODE_ENABLED` (default `false` for the v1.3 dark-launch milestone, flipped to `true` once Phase 17 + 18 + 19 land and UAT passes). Mirrors v1.2 `TOOL_REGISTRY_ENABLED` / `SANDBOX_ENABLED` precedent. When `false`, the toggle button is hidden in the UI, the chat endpoint rejects `deep_mode=true` payloads (400), and the `agent_todos` table is unused. When the flag is OFF, the codebase is byte-identical to pre-Phase-17 (DEEP-03 invariant).

### SSE Event Taxonomy

- **D-17 (`todos_updated` event format):** `data: {"type": "todos_updated", "todos": [{"id": "...", "content": "...", "status": "pending|in_progress|completed", "position": 0}, ...]}\n\n`. Full list snapshot on every `write_todos` AND `read_todos` (PRD requires both — TODO-03). Reasoning: simpler diff logic on frontend, matches the full-replacement write semantic, keeps event size bounded (per-thread todo list is naturally small, <50 items).
- **D-18 (Event ordering):** `todos_updated` fires AFTER the DB write commits, BEFORE the tool result is appended to the message stream. This matches the existing `tool_start` / `tool_result` ordering in chat.py.
- **D-19 (No new SSE event types beyond `todos_updated`):** Other Phase 17 features (loop exhaustion, deep-mode badge, interrupt) reuse existing events (`done`, `delta`, `tool_start`/`tool_result`). Deep Mode itself does not need an `agent_status` event in Phase 17 — that lands in Phase 19 with `STATUS-01`.

### Frontend (Plan Panel UI)

- **D-20 (Plan Panel component pattern):** Follows `frontend/src/components/chat/SubAgentPanel.tsx` and `CodeExecutionPanel.tsx` precedent — sidebar panel, collapsibility via `useSidebar` (or inherited panel-collapse pattern), real-time SSE event consumption via `useChatState` hook, history reconstruction from per-message `tool_calls` JSONB on thread reload.
- **D-21 (Plan Panel data source):** Live state from `todos_updated` SSE events accumulated into a `todos: Todo[]` slice in chat state. On thread reload, hydrate from `GET /threads/{id}/todos` REST endpoint (new endpoint added in this phase) which returns the current `agent_todos` rows ordered by `position`.
- **D-22 (Plan Panel visibility):** Panel is visible whenever (a) the current message has `deep_mode=true`, OR (b) the thread has any `agent_todos` rows on reload. Decoupled from the Deep Mode TOGGLE (the toggle is per-message, the panel reflects state). On a non-deep-mode thread, the panel is hidden.
- **D-23 (Deep Mode badge):** Each assistant message rendered with `messages.deep_mode=true` shows a subtle "Deep Mode" badge in the message header. Implementation: extend `MessageView.tsx` to read the new flag. No design system tokens added — uses existing zinc/purple accent.
- **D-24 (Deep Mode toggle button):** New button next to Send in `frontend/src/components/chat/MessageInput.tsx` (and `WelcomeInput.tsx` if welcome screen has its own input — confirm during planning). Toggles a per-message-only state (does NOT persist between messages). Visual treatment: ghost button when off, filled purple accent when on. Form duplication rule from CLAUDE.md applies — also add to mobile/desktop variants.
- **D-25 (Status indicators in Plan Panel):** Pending = zinc dot, in_progress = pulsing purple dot, completed = green check. Use existing icon set from `lucide-react`. No new design tokens.
- **D-26 (Real-time UI):** State updates flow through the existing `useChatState` reducer pattern. New action type `TODOS_UPDATED` mutates a `todos` slice. No global redux / zustand additions.

### REST Endpoints

- **D-27 (Endpoints to add):**
  - `GET /threads/{thread_id}/todos` — returns current todo list ordered by `position`. RLS-scoped via `get_supabase_authed_client(token)`. Used for thread-reload hydration (TODO-07).
  - `POST /threads/{thread_id}/todos` is NOT exposed — todos are written ONLY by the LLM via `write_todos` tool. Avoids drift between the LLM's full-replacement semantic and a separate REST surface.
- **D-28 (Endpoint placement):** Endpoints added to existing `backend/app/routers/threads.py` (extends the threads namespace; consistent with how `messages` are nested under threads). NOT a new `agent_todos.py` router for v1.3 — the surface is too small (single GET).

### LLM Tool Schemas

- **D-29 (`write_todos` schema):** `write_todos(todos: list[{content: str, status: 'pending'|'in_progress'|'completed'}])`. The tool implementation auto-assigns `position` from list order. Returns the saved list (echo) so the LLM sees the canonical state. Validation: max 50 todos per thread (defensive cap; logs a warning if exceeded but truncates). No JSON-schema strict mode required — Pydantic validation at the tool service boundary.
- **D-30 (`read_todos` schema):** `read_todos()` (no args). Returns current list. Per PRD recitation pattern (TODO-04), the deep-mode system prompt instructs the agent to call `read_todos` after each step.
- **D-31 (Tool registry integration):** Both tools register through the unified `ToolRegistry` (v1.2 D-P13-01) when `TOOL_REGISTRY_ENABLED=true`. When the flag is off, they fall back to the legacy hand-coded tool dispatch in `tool_service.py`. NEW tools follow the registry's adapter-wrap invariant — no edits to `tool_service.py` lines 1-1283.

### Privacy & Security

- **D-32 (Egress filter coverage):** Deep-mode LLM payloads (system prompt + messages + tools) MUST route through the existing `backend/app/services/redaction/egress.py` egress filter. The new branch in `chat.py` reuses the same `_pii_safe_request()` wrapper used by the standard tool-calling loop. Privacy invariant preserved (no real PII to cloud LLM payloads).
- **D-33 (`SEC-01` enforcement test):** A regression test asserts User A cannot read or write to User B's `agent_todos` rows via direct table access (Supabase JS client with User A's JWT). Mirrors the v1.0 `entity_registry` RLS test pattern.
- **D-34 (Audit log):** Each `write_todos` / `read_todos` call logs via the existing `audit_service.log_action(...)` helper with `resource_type='agent_todos'`, `resource_id=thread_id`. Consistent with v1.0–v1.2 mutation logging convention.

### Testing Strategy

- **D-35 (TDD-first):** Each plan writes a failing test first (per CLAUDE.md Testing & TDD rule). Test layers:
  - Migration test: applied schema matches expected columns + RLS policies (Supabase migration verification).
  - Service-level unit tests: `write_todos` full-replacement semantic, `read_todos` ordering, edge cases (empty list, >50 items truncation).
  - Router integration tests: `POST /chat` with `deep_mode=true` returns SSE stream including `todos_updated` events; `GET /threads/{id}/todos` returns RLS-scoped list.
  - RLS test: User A cannot access User B's todos.
  - Frontend Vitest tests: `PlanPanel.tsx` renders states correctly, history reconstruction from REST hydrate.
  - Byte-identical fallback test: `DEEP_MODE_ENABLED=false` → toggle hidden, `deep_mode=true` payload rejected, no agent_todos writes occur even if LLM hallucinates a `write_todos` call (tool not registered).
- **D-36 (Hooks-driven CI):** Existing PostToolUse hook runs `pytest` on `.py` edits, `ESLint + tsc` on `.ts/.tsx` edits — relied on for fast feedback. No new CI infrastructure.

### Atomic Commits

- **D-37 (One commit per plan):** Per CLAUDE.md Git Workflow rule. Each PLAN.md produced by plan-phase becomes one commit via `gsd-sdk query commit`. Migration ships in its own plan (e.g., 17-01) BEFORE any code that depends on it (17-02..N).
- **D-38 (Migration apply discipline):** After `038_agent_todos_and_deep_mode.sql` is committed, the operator runs `supabase db push` against the production project (`qedhulpfezucnfadlfiz`). This is documented as a manual step in PLAN 17-01 — NOT auto-applied by the plan executor. The PreToolUse hook blocks edits to applied migrations, so once pushed, the file is frozen. (Same convention as v1.0–v1.2 milestones.)

### Claude's Discretion

- **Plan ordering and granularity:** Plan-phase decides how to split into atomic plans (likely ~6–8 plans: migration + config/env vars + tool service additions + chat-loop branch + REST endpoint + Plan Panel UI + Deep Mode toggle button + integration + RLS regression test). Wave layout if applicable: independent UI work could parallelize with backend tool/loop work after migration lands.
- **Exact prompt wording:** Plan-phase / executor decides the precise text of the deep-mode system prompt (planning instructions, recitation pattern, sub-agent stub, ask-user stub). Constraint: deterministic, KV-cache stable, ~30–60 lines.
- **Plan Panel collapse behavior:** Default collapsed-or-expanded on first deep-mode message, hover/click affordances. Use existing `useSidebar` pattern.

### Folded Todos

(No pre-existing `.planning/todos/` matches surfaced by the discuss-phase scout. Phase 17 scope is clean from the v1.3 ROADMAP.)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary PRD & Roadmap
- `docs/PRD-Agent-Harness.md` §Part 1, Features 1.1, 1.2, 1.6, 1.7 — Deep Mode toggle, planning todos, status, persistence (the four PRD features that fall in Phase 17 scope).
- `.planning/ROADMAP.md` §Phase 17 — Goal, depends_on (none), requirements (DEEP-01..07, TODO-01..07, MIG-01, MIG-04, SEC-01, CONF-01..03), Success Criteria (5 items).
- `.planning/REQUIREMENTS.md` §"Deep Mode Foundation (DEEP-*)", §"Planning System / Todos (TODO-*)", §"Migrations (MIG-01, MIG-04)", §"Security (SEC-01)", §"Configuration (CONF-01..03)" — full requirement text for Phase 17's 20 reqs.
- `.planning/PROJECT.md` §"Current Milestone: v1.3", §"Key Decisions" — invariants and prior milestone decisions still in force.
- `.planning/STATE.md` §"Roadmap Snapshot (v1.3)", §"v1.3 contract / invariants" — wave structure, no auto retries, no frontend loop, raw SDK only.

### Codebase patterns to mirror
- `backend/app/routers/chat.py` lines 373–700, 1208–1416 — existing tool-calling loop pattern (the deep-mode branch will mirror this).
- `backend/app/services/tool_service.py` (entire) — tool dispatch, `execute_tool()` signature, RLS-scoped token plumbing.
- `backend/app/services/tool_registry.py` (v1.2) — `ToolRegistry.register()` adapter-wrap invariant for new tools.
- `backend/app/services/redaction/egress.py` — egress filter wrapper used by the deep-mode branch (privacy invariant).
- `backend/app/services/system_settings_service.py` — single-row settings cache (NOT used for loop caps; used as reference for what NOT to use here).
- `backend/app/config.py` lines 73, 67–104 — Pydantic Settings pattern for env-driven config (`MAX_DEEP_ROUNDS`, etc. land here).
- `backend/app/services/audit_service.py` — `log_action(...)` helper for tool-call audit.
- `backend/app/routers/threads.py` — existing thread-scoped router pattern (where `GET /threads/{id}/todos` lands).
- `backend/app/main.py` — FastAPI app instantiation (router registration).

### Frontend patterns to mirror
- `frontend/src/components/chat/SubAgentPanel.tsx` — sidebar panel with history reconstruction; closest analog for `PlanPanel.tsx`.
- `frontend/src/components/chat/CodeExecutionPanel.tsx` — collapsible panel + SSE event consumption pattern.
- `frontend/src/components/chat/MessageView.tsx` — assistant message rendering (Deep Mode badge target).
- `frontend/src/components/chat/MessageInput.tsx` — input with action buttons (Deep Mode toggle target).
- `frontend/src/components/chat/WelcomeInput.tsx` — welcome screen input (verify if toggle needed here too).
- `frontend/src/hooks/useChatState.{ts,tsx}` — state reducer and SSE event consumption.
- `frontend/src/i18n/` — Indonesian + English label conventions.
- `frontend/src/components/chat/CodeExecutionPanel.test.tsx` — Vitest 3.2 component test precedent (v1.2 D-P16-02).

### Migration RLS pattern reference
- `supabase/migrations/036_code_executions_and_sandbox_outputs.sql` — most recent table-with-RLS migration; thread-ownership RLS template for `agent_todos`.
- `supabase/migrations/001_initial_schema.sql` lines 7–80 — `threads` and `messages` tables; FK targets for `agent_todos.thread_id` and the `messages.deep_mode` ALTER.
- `supabase/migrations/032_pii_redaction_enabled_setting.sql` — example of column-add migration on an existing table (analog for the `messages.deep_mode` ALTER).

### Project conventions
- `CLAUDE.md` — TDD rule, atomic commits via `gsd-sdk query commit`, RLS on every new table, no LangChain/LangGraph, Pydantic for structured LLM outputs, single-row `system_settings` is NOT a key-value store, base-ui `asChild` shim conventions, glass-only-on-overlays rule, form duplication for mobile/desktop, `/create-migration` skill for next sequential migration.
- `.planning/codebase/STACK.md`, `STRUCTURE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `TESTING.md`, `INTEGRATIONS.md`, `CONCERNS.md` — codebase living docs (refreshed 2026-04-25).

### Prior milestone artifacts (decisions still in force)
- `.planning/milestones/v1.0-ROADMAP.md`, `v1.0-REQUIREMENTS.md` — privacy invariant, egress filter coverage, audit log convention.
- `.planning/milestones/v1.1-ROADMAP.md`, `v1.1-REQUIREMENTS.md` — Skills system, code execution sandbox, `tool_calls` JSONB persistence pattern.
- `.planning/milestones/v1.2-ROADMAP.md`, `v1.2-REQUIREMENTS.md` — `ToolRegistry` adapter-wrap invariant, `tool_search` meta-tool, MCP integration, base-ui `asChild` shim sweep, Vitest 3.2 frontend tests.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Tool-calling loop** — `chat.py` lines 373–700 (single-agent path) and 1208–1416 (multi-agent path) provide a battle-tested template for the deep-mode loop branch (per-iteration egress filter, per-round persistence, SSE event ordering, `tool_calls` JSONB row construction).
- **Tool registry** — `tool_registry.py` (v1.2) accepts new native tools via adapter wrap; `write_todos` / `read_todos` register through it without touching `tool_service.py` lines 1-1283.
- **Audit logging** — `audit_service.log_action(...)` already used across all mutations; reuse for `agent_todos` writes.
- **System-prompt assembly** — `chat.py` already injects skill catalog, tool catalog (v1.2), and PII guidance into the system prompt; deep-mode adds 4 deterministic sections through the same pipeline.
- **History reconstruction** — `_expand_history_row()` in `chat.py` reconstructs per-round tool calls from `tool_calls` JSONB; `agent_todos` reload uses a NEW REST endpoint (`GET /threads/{id}/todos`) but does NOT need to alter the existing reconstruction.
- **SubAgentPanel + CodeExecutionPanel** — proven sidebar-panel + history-reconstruction pattern. PlanPanel mirrors structure; reads from chat state (live SSE) + REST hydrate (history).
- **Vitest 3.2** — frontend test framework bootstrapped in v1.2; PlanPanel.test.tsx follows `CodeExecutionPanel.test.tsx` co-located convention.
- **`handle_updated_at` trigger** — defined in `001_initial_schema.sql`; reused by `agent_todos` migration without redefinition.
- **`get_supabase_authed_client(token)`** — RLS-scoped DB client; standard pattern for new endpoints.
- **`useChatState` hook + reducer** — handles SSE event accumulation; new `TODOS_UPDATED` action follows existing patterns (no architectural change).
- **`AgentBadge.tsx`** — existing component for badges on assistant messages; potential reuse for the Deep Mode badge.

### Established Patterns
- **Numbered sequential migrations:** Next is `038`. PreToolUse hook blocks edits to 001-032; same applies to 038 once committed.
- **Feature flags via Pydantic Settings:** `TOOL_REGISTRY_ENABLED`, `SANDBOX_ENABLED` — `DEEP_MODE_ENABLED` follows the same env-var-default-false-dark-launch pattern.
- **SSE event format:** `data: {"type": "<event_name>", ...}\n\n`; `todos_updated` follows.
- **Atomic per-plan commits:** Each PLAN.md = one `gsd-sdk query commit` invocation.
- **Pydantic structured output:** Tool schemas validated via Pydantic before reaching the LLM dispatcher.
- **Form duplication rule (CLAUDE.md):** Mobile + desktop variants both updated when adding form sections (Deep Mode toggle goes into both `MessageInput.tsx` panel halves).
- **Glass / panel rule (CLAUDE.md):** Plan Panel is a persistent sidebar — NO `backdrop-blur`. Solid panel surface only.
- **Indonesian-default i18n:** All Plan Panel labels routed through `I18nProvider`; supply ID + EN strings.

### Integration Points
- **`backend/app/routers/chat.py`:** new branching at the chat handler entry — deep_mode=true routes to a new function that mirrors the existing loop with extended prompt + deep-mode tools + `MAX_DEEP_ROUNDS` cap.
- **`backend/app/routers/threads.py`:** add `GET /threads/{id}/todos` endpoint.
- **`backend/app/services/tool_service.py`:** register `write_todos` / `read_todos` via the unified registry's adapter wrap (NO edits to lines 1-1283; v1.2 D-P13-01 invariant).
- **`backend/app/config.py`:** add `MAX_DEEP_ROUNDS`, `MAX_TOOL_ROUNDS`, `MAX_SUB_AGENT_ROUNDS`, `DEEP_MODE_ENABLED` env-var Settings fields.
- **`backend/app/services/audit_service.py`:** consumed for tool-call audit (no new code in audit service itself).
- **`frontend/src/components/chat/PlanPanel.tsx`:** NEW component, mirrors `SubAgentPanel.tsx`.
- **`frontend/src/components/chat/MessageInput.tsx`:** add Deep Mode toggle button (mobile + desktop variants).
- **`frontend/src/components/chat/WelcomeInput.tsx`:** verify if Deep Mode toggle belongs here too (likely yes — first-message path).
- **`frontend/src/components/chat/MessageView.tsx`:** add Deep Mode badge for `messages.deep_mode=true`.
- **`frontend/src/hooks/useChatState.{ts,tsx}`:** add `todos` slice + `TODOS_UPDATED` action; consume `todos_updated` SSE event.
- **`frontend/src/i18n/`:** add Plan Panel + Deep Mode strings (ID + EN).
- **`supabase/migrations/038_agent_todos_and_deep_mode.sql`:** NEW migration — `agent_todos` table + RLS + `messages.deep_mode` column.

</code_context>

<specifics>
## Specific Ideas

- **Migration 038 file name:** `supabase/migrations/038_agent_todos_and_deep_mode.sql` — bundle `agent_todos` table + `messages.deep_mode` column in one file (D-MIG-01).
- **Loop-cap defaults:** `MAX_DEEP_ROUNDS=50`, `MAX_TOOL_ROUNDS=25`, `MAX_SUB_AGENT_ROUNDS=15` — non-negotiable per ROADMAP / PRD.
- **`DEEP_MODE_ENABLED=false` default:** Dark launch convention (matches v1.2 `TOOL_REGISTRY_ENABLED`, `SANDBOX_ENABLED`).
- **Plan Panel position in sidebar:** Same position as `SubAgentPanel` / `CodeExecutionPanel` (sidebar slot, collapsible). Verify exact stacking during planning.
- **Deep Mode badge styling:** Subtle purple-accent text or icon, NOT a loud chip. Calibrated Restraint design system tokens only.
- **Deep Mode toggle styling:** Ghost button when off, filled purple accent when on; matching ID/EN labels.
- **Recitation prompt language (default suggestion):** "After completing each step, call `read_todos` to confirm your plan and progress before deciding the next action." Plan-phase finalizes wording.
- **`write_todos` 50-item cap:** Defensive limit; truncation logged (not error). Plan-phase confirms.

</specifics>

<deferred>
## Deferred Ideas

(All ideas surfaced during analysis are in-scope for Phase 17 or already explicitly deferred to later phases by the v1.3 ROADMAP.)

- **Workspace Filesystem (`workspace_files` table, file tools, Workspace Panel)** — Phase 18 (independent foundation, parallel with Phase 17).
- **Sub-agent `task` tool, `ask_user` tool, `agent_status` SSE event, error append-only recovery** — Phase 19 (depends on Phase 17 deep loop).
- **Harness engine, gatekeeper LLM, post-harness LLM, file upload, locked Plan Panel variant** — Phase 20.
- **Batched parallel sub-agents (`llm_batch_agents`), human-in-the-loop (`llm_human_input`)** — Phase 21.
- **Contract Review domain harness, DOCX deliverable** — Phase 22.
- **Cross-process async-lock upgrade (D-31, carried from v1.0)** — Post-MVP, see STATE.md Deferred.
- **PERF-02 server-class-hardware confirmation** — Carried from v1.0; unrelated to Phase 17.
- **Multi-worker IPython sandbox session semantics** — Carried from v1.1; unrelated to Phase 17.
- **Context auto-compaction / summarization for very-long sessions** — Explicit PRD-flagged post-MVP.
- **Stall detection and auto-replan** — Explicit PRD-flagged post-MVP.
- **Full SSE reconnection with automatic loop resumption mid-flight** — Explicit PRD-flagged post-MVP. (In Phase 17, mid-flight interrupt only preserves committed state; the user must send a follow-up to resume.)
- **Per-user Deep Mode toggle preference** — Per-message in v1.3; per-user persisted preference is out of scope.
- **Tool-approval prompts inside the loop** — Explicit PRD-flagged post-MVP.

### Reviewed Todos (not folded)

(No pre-existing todos surfaced for Phase 17. Section omitted of substance.)

</deferred>

---

*Phase: 17-deep-mode-foundation-planning-todos-plan-panel*
*Context gathered: 2026-05-03*
*Mode: --auto (decisions auto-resolved from CLAUDE.md / PROJECT.md Key Decisions / v1.0–v1.2 milestone patterns)*
