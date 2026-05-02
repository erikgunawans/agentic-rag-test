# Phase 17: Deep Mode Foundation + Planning Todos + Plan Panel - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 17-deep-mode-foundation-planning-todos-plan-panel
**Mode:** `--auto` (autonomous decision-making from project defaults)
**Areas discussed:** Migration strategy, Loop architecture, Configuration & loop caps, SSE event taxonomy, Frontend Plan Panel & Deep Mode toggle, REST endpoints, LLM tool schemas, Privacy & RLS, Testing strategy

---

## Migration Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| A. Single migration `038_agent_todos_and_deep_mode.sql` (table + RLS + `messages.deep_mode` column) | One reviewable file; both columns serve the same Phase 17 feature | ✓ |
| B. Split into `038_agent_todos.sql` + `039_messages_deep_mode_column.sql` | Strict one-table-per-migration discipline | |
| C. Combine with Phase 18's `workspace_files` migration | Couples two independent foundation phases (cross-team coordination cost) | |

**Selected:** A — single migration. Reason: simpler reviewer story, atomic ship, both changes serve Phase 17's MIG-01 + MIG-04 requirements. STATE.md mention of separate "041" for `messages.deep_mode` is reconciled by collapsing into 038. `harness_mode TEXT` deferred to Phase 20 since `harness_runs` table lands there.
**Auto-decision rationale:** Default project preference for atomic, reviewer-friendly migrations (v1.0–v1.2 precedent: 029, 032, 035, 036 all bundle related changes).

---

## RLS Pattern for `agent_todos`

| Option | Description | Selected |
|--------|-------------|----------|
| A. Thread-ownership via JOIN (`EXISTS (SELECT FROM threads ...)`) | Pure derivation from `threads.user_id`; matches v1.0 entity_registry pattern | |
| B. Direct `auth.uid() = user_id` on a mirrored `user_id` column | Faster, defense-in-depth, matches `code_executions` (036) | |
| C. Both — JOIN policy plus mirrored `user_id` column for short-circuit | Belt-and-suspenders | ✓ |

**Selected:** C — both. RLS policy uses `auth.uid() = user_id`; `user_id` mirrored from `threads.user_id` on insert; JOIN-based defensive check optional in policy. Covers SEC-01 with no edge cases.
**Auto-decision rationale:** Matches the most recent migration (036) which uses direct `user_id` on `code_executions`; belt-and-suspenders is project default for sensitive new tables.

---

## Loop Caps Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| A. Env vars in Pydantic `Settings` (`MAX_DEEP_ROUNDS`, etc.) | Deployment knobs; matches `tools_max_iterations`, `llm_context_window` precedent | ✓ |
| B. `system_settings` DB columns (admin-toggleable) | Runtime configurable | |
| C. Hard-coded constants | Simplest, no flexibility | |

**Selected:** A. Reason: loop caps are deployment-time knobs (not user/admin runtime settings), and the existing convention in `config.py` (lines 67–104) is to use Pydantic env-var Settings for that purpose. `system_settings` is reserved for admin-toggleable runtime settings (PII toggle, RAG provider).
**Auto-decision rationale:** The user's prompt explicitly stated "auto-decide: env var (system_settings is for user-configurable settings; loop caps are deployment knobs)."

---

## Loop Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| A. Hand-coded new branch in chat.py mirroring existing tool-loop | Raw SDK only; consistent with v1.0–v1.2; preserves byte-identical fallback | ✓ |
| B. Adopt LangChain/LangGraph for the deep loop | Out-of-scope per PROJECT.md and STATE.md invariants | |
| C. Rewrite the existing loop and add a `deep_mode` flag inside | Touches the v1.2 byte-identical fallback surface; high blast radius | |

**Selected:** A. Reason: PROJECT.md Key Decisions and STATE.md v1.3 invariants both explicitly forbid LangChain/LangGraph; v1.2 D-P13-01 establishes the adapter-wrap-to-preserve-fallback invariant. New deep-mode branch added without touching the existing loop.
**Auto-decision rationale:** Hard project rule (CLAUDE.md, PROJECT.md, STATE.md).

---

## Feature Flag

| Option | Description | Selected |
|--------|-------------|----------|
| A. `DEEP_MODE_ENABLED=false` (env-var Pydantic Settings, dark launch) | Matches v1.2 `TOOL_REGISTRY_ENABLED`, `SANDBOX_ENABLED` | ✓ |
| B. Always on once shipped | Skips dark-launch phase; faster to flip on | |
| C. Behind `system_settings` DB toggle | Admin-runtime toggleable | |

**Selected:** A. Reason: v1.3 dark-launch milestone discipline. Toggle hidden in UI, deep_mode=true rejected at endpoint, agent_todos unused when flag off (DEEP-03 byte-identical invariant).
**Auto-decision rationale:** v1.2 milestone precedent.

---

## SSE `todos_updated` Event Format

| Option | Description | Selected |
|--------|-------------|----------|
| A. Full snapshot of todo list on every mutation | Simpler frontend reducer; matches full-replacement write semantic | ✓ |
| B. Diff (added/removed/changed) | Smaller events; complex frontend | |
| C. Single-todo deltas | Even smaller; many events per round | |

**Selected:** A. Reason: full-replacement semantic (PRD Feature 1.2) makes diffs unnecessary; per-thread todo lists are naturally small (<50 items); reducer logic stays trivial.
**Auto-decision rationale:** Match PRD's full-replacement design for `write_todos`.

---

## REST Endpoint for History Reconstruction

| Option | Description | Selected |
|--------|-------------|----------|
| A. `GET /threads/{id}/todos` only (read-only) | Hydrate live state on thread reload; LLM is sole writer | ✓ |
| B. Full CRUD `/threads/{id}/todos` | User can edit todos manually (out of scope for v1.3) | |
| C. Embed in existing `/threads/{id}/messages` payload | Avoids new endpoint; couples message reads to todo reads | |

**Selected:** A. Reason: PRD says LLM is the sole writer; no CRUD needed. Hydrate-on-reload solves TODO-07. Endpoint placed in existing `routers/threads.py` (no new router for one GET).
**Auto-decision rationale:** Avoid scope creep; surface area minimum.

---

## Plan Panel UI Pattern

| Option | Description | Selected |
|--------|-------------|----------|
| A. New component `PlanPanel.tsx` mirroring `SubAgentPanel.tsx` + `CodeExecutionPanel.tsx` | Battle-tested sidebar pattern with history reconstruction | ✓ |
| B. Inline rendering inside chat thread | No persistent visibility; clutters scroll | |
| C. Modal on toggle click | Hides plan during execution | |

**Selected:** A. Reason: PRD specifies sidebar Plan Panel; existing components (SubAgentPanel, CodeExecutionPanel) are the proven precedent. Reuse `useSidebar` collapse pattern, SSE accumulation via `useChatState`.
**Auto-decision rationale:** PRD + existing pattern.

---

## Plan Panel Visibility Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| A. Visible whenever current message is deep_mode OR thread has any agent_todos rows | History reconstruction works on reload; panel doesn't disappear after deep run | ✓ |
| B. Visible only while deep mode is active | Disappears on non-deep-mode follow-ups; loses plan history | |
| C. Always visible | Empty panel clutter on standard threads | |

**Selected:** A. Reason: TODO-07 requires last-known todo state on thread reload. Panel reflects state, not toggle.
**Auto-decision rationale:** Direct PRD requirement (TODO-07).

---

## Deep Mode Toggle Placement

| Option | Description | Selected |
|--------|-------------|----------|
| A. Button next to Send in `MessageInput.tsx` (mobile + desktop variants) and `WelcomeInput.tsx` | Form-duplication rule (CLAUDE.md); covers first-message + ongoing-message paths | ✓ |
| B. Just `MessageInput.tsx` (desktop) | Misses mobile + welcome screen | |
| C. Settings page toggle | Per-message requirement violated (PRD Feature 1.1) | |

**Selected:** A.
**Auto-decision rationale:** CLAUDE.md form duplication rule + PRD per-message requirement.

---

## Tool Registry Integration

| Option | Description | Selected |
|--------|-------------|----------|
| A. Register `write_todos`/`read_todos` via unified `ToolRegistry` adapter wrap | Honors v1.2 D-P13-01 byte-identical fallback invariant | ✓ |
| B. Hand-code in `tool_service.py` lines 1-1283 | Violates the adapter-wrap invariant | |

**Selected:** A.
**Auto-decision rationale:** v1.2 invariant (D-P13-01).

---

## Privacy / Egress Filter

| Option | Description | Selected |
|--------|-------------|----------|
| A. Route deep-mode payloads through existing `redaction/egress.py` filter | Privacy invariant preserved (no real PII to cloud) | ✓ |
| B. Bypass for performance | Violates v1.0 privacy invariant | |

**Selected:** A.
**Auto-decision rationale:** v1.0 hard project invariant.

---

## Testing Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| A. TDD: failing test first, layered (migration / unit / integration / RLS / frontend Vitest / byte-identical fallback) | Per CLAUDE.md "Always follow TDD" rule | ✓ |
| B. Tests-after | Project rule says no | |

**Selected:** A.
**Auto-decision rationale:** CLAUDE.md hard rule.

---

## Claude's Discretion

The following items are auto-resolved with downstream-agent flexibility (planner / executor decides exact form):

- Plan ordering and granularity (likely 6–8 atomic plans).
- Exact wording of the deep-mode system prompt's planning / recitation / sub-agent stub / ask-user stub sections (constraint: deterministic, KV-cache stable, ~30–60 lines).
- Plan Panel default collapsed/expanded state on first deep-mode message; precise hover/click affordances.
- Vitest test file layout (single `PlanPanel.test.tsx` vs split per-state-test).

---

## Deferred Ideas

All ideas surfaced during analysis are either in-scope for Phase 17 or already explicitly deferred to other Phase 18..22 phases by the v1.3 ROADMAP. No new deferred items beyond what is already in `STATE.md` Deferred and PRD post-MVP. See `17-CONTEXT.md` `<deferred>` section for the full list.

---

*Generated 2026-05-03 by `gsd-discuss-phase 17 --auto`*
