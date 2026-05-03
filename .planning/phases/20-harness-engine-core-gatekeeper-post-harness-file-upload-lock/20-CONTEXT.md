# Phase 20: Harness Engine Core + Gatekeeper + Post-Harness + File Upload + Locked Plan Panel - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship a backend state-machine **harness engine** that drives deterministic typed phases (`programmatic` / `llm_single` / `llm_agent`) against a thin orchestrator (~5k tokens) with workspace-passed context, plus the four wrapper systems that make the engine usable end-to-end:

1. **Harness Engine Core** (`HarnessRegistry` dict + typed `PhaseDefinition` dataclass + `PhaseDispatcher`) — dispatches by `PhaseType` enum, persists run state in `harness_runs` (migration **042**, NOT 041), enforces per-phase timeouts (120s `llm_single` / 300s `llm_agent`), checks cancellation between rounds/phases, structured-output validation via Pydantic + `response_format: json_schema` for `llm_single`, full SSE event suite (`harness_phase_start/_complete/_error`, `harness_complete`, `harness_human_input_required`).
2. **Gatekeeper LLM** — stateless conversational agent that runs ONLY when a harness is registered AND no active/completed `harness_runs` exists for the thread; multi-turn dialogue ("upload your contract first"); fires `[TRIGGER_HARNESS]` sentinel detected end-of-stream, sentinel suppressed from output, harness begins in same SSE response.
3. **Post-Harness Summary LLM** — separate LLM call after `harness_complete`, streams ~500-token summary inline in same SSE generator, persisted as separate assistant message with `messages.harness_mode='contract-review'`. Truncation when phase results exceed 30k chars: keep last 2 phases full, summarize earlier phases via heading + first 200 chars (POST-05).
4. **DOCX/PDF File Upload** — `POST /threads/{id}/files/upload` writes binary to `workspace-files` bucket + metadata row with `source='upload'`; text extraction is **lazy at harness-phase runtime** (Phase 1 of any consumer harness reads binary + runs `python-docx`/`PyPDF2`); paperclip icon in chat input, always visible when `WORKSPACE_ENABLED`.
5. **Locked Plan Panel variant** — lock icon 🔒 + harness-type label + tooltip ("System-driven plan — cannot be modified during execution") + Cancel button in panel header; defense-in-depth lock enforcement: LLM-side strip of `write_todos`/`read_todos` from harness phase tool sets (PANEL-03) AND UI removes mutation affordances AND backend rejects PUT/DELETE on `agent_todos` when thread has active `harness_run`.
6. **Cross-cuts** — privacy egress (SEC-04, every harness LLM call routed through `redaction/egress.py`), sub-agents under parent JWT (SEC-02, no privilege escalation, reuse Phase 19 `sub_agent_loop`), provider keys server-side (SEC-03), single-writer `progress.md` per phase transition (OBS-01), `thread_id` correlation logging (OBS-02), LangSmith tracing covers new code paths (OBS-03).
7. **Smoke Harness for engine validation** — ship a 2-phase echo harness (`harnesses/smoke_echo.py`: programmatic + llm_single) so Phase 20's six success criteria can be E2E verified before Phase 22 lands Contract Review. Stays in registry as developer/admin diagnostic, feature-flagged off in production.

**Strict scope guardrail (carried from ROADMAP.md):**
- `llm_batch_agents` and `llm_human_input` phase types — Phase 21.
- Contract Review domain harness (8-phase deterministic workflow) and DOCX deliverable — Phase 22.
- OCR fallback for scanned PDFs — deferred; Phase 20 extraction is text-layer-only. If empty/short text, Phase 1 of consumer harness writes a structured error to `phase_results` + `contract-text.md`. Phase 22 UAT decides whether to wire RAG-03 vision-OCR fallback.
- `MIG-04` (`messages.deep_mode` boolean + `messages.harness_mode` text) — already added in migration 038 (Phase 17). Phase 20 only USES the existing `harness_mode` column; no new `messages` ALTER.

</domain>

<decisions>
## Implementation Decisions

### Harness State Machine + Migration 042

- **D-01 (Separate `harness_runs` table mirroring `agent_runs` schema pattern):** New migration `supabase/migrations/042_harness_runs.sql`. Sequencing rationale — migrations applied to date: 038 (Phase 17 `agent_todos`), 039 (Phase 18 `workspace_files`), 040 (Phase 19 `agent_runs`), 041 (`rag_improvements_legacy.sql`, the renamed-from-024 file from the duplicate-024 cleanup). **042 is the next free integer — NOT 041 as the ROADMAP comment suggests.** Schema mirrors Phase 19's `agent_runs` partial-unique-on-active-row pattern with harness-specific columns:
  | Column | Type | Notes |
  |---|---|---|
  | `id` | `uuid PRIMARY KEY DEFAULT gen_random_uuid()` | |
  | `thread_id` | `uuid NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE` | RLS anchor |
  | `user_id` | `uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE` | defense-in-depth |
  | `harness_type` | `text NOT NULL` | matches the registry key (e.g. `'contract-review'`, `'smoke-echo'`) |
  | `status` | `text NOT NULL CHECK (status IN ('pending','running','paused','completed','failed','cancelled'))` | `paused` reserved for Phase 21 `llm_human_input`; Phase 20 uses pending→running→completed/failed/cancelled |
  | `current_phase` | `integer NOT NULL DEFAULT 0` | phase index into `harness.phases` |
  | `phase_results` | `jsonb NOT NULL DEFAULT '{}'::jsonb` | `{phase_index: {phase_name, output, started_at, completed_at}}` |
  | `input_file_ids` | `uuid[] NOT NULL DEFAULT '{}'` | workspace_files.id values for inputs |
  | `error_detail` | `text` | NULL unless status='failed' |
  | `created_at` | `timestamptz NOT NULL DEFAULT now()` | |
  | `updated_at` | `timestamptz NOT NULL DEFAULT now()` | trigger-maintained |
  - Constraints: `UNIQUE (thread_id) WHERE status IN ('pending','running','paused')` — partial unique index ensures **at most one active run per thread** (mirrors `agent_runs` D-03 pattern); completed/failed/cancelled rows accumulate as history.
  - RLS: thread-ownership scoped, identical predicate as `agent_runs` / `workspace_files` / `agent_todos`.
  - Indexes: `idx_harness_runs_thread_active (thread_id) WHERE status IN ('pending','running','paused')` for active-run lookup; `idx_harness_runs_user_created (user_id, created_at DESC)` for admin auditing.
  - Phase 19 `agent_runs` table is UNTOUCHED — the two state machines coexist; resume-detection branch in `chat.py` checks both tables independently.

- **D-02 (Reject new chat messages while harness_run is active):** When the user sends a normal chat message and `harness_runs` has a row with `status IN ('pending','running','paused')` for the thread, backend returns a structured response: `{"error": "harness_in_progress", "harness_type": "...", "current_phase": N, "phase_name": "..."}`. Frontend renders a banner: "Contract Review running (phase N/M) — please wait." with a Cancel button. One workflow per thread at a time. Note: this DOES NOT apply to the Phase 19 `ask_user` resume path — that's a different mechanism (no active `harness_run`, only `agent_runs.status='waiting_for_user'`).

- **D-03 (Cancel button in Plan Panel header — primary affordance):** Click → backend sets `harness_runs.status='cancelled'`, cancellation event checked between rounds/phases (HARN-07), partial workspace artifacts preserved (so user can see what was done). No `/cancel-harness` slash command in v1.3 (deferred — discoverability poor for legal users).

- **D-04 (`messages.harness_mode` carries harness type only — e.g. `'contract-review'`):** Simple discriminator on assistant messages produced by harness flow (gatekeeper turns, post-harness summary, follow-ups within the same harness context). NULL for normal/deep-mode messages. Lets UI badge messages and lets history reconstruction know whether to show locked Plan Panel state. NOT per-phase index (rejected — harness phases mostly write to workspace files, not assistant messages, so per-phase tag is rarely meaningful). NOT JSONB (rejected — `harness_runs.id` already provides the join path).

### Gatekeeper LLM Contract + Harness Selection

- **D-05 (Gatekeeper runs ONLY when a harness is registered AND no active/completed `harness_runs` for thread — per GATE-01):** Implementation: `chat.py` entry checks (a) `HarnessRegistry.list_harnesses()` is non-empty AND (b) `harness_runs.get_latest_for_thread(thread_id)` is `None` (no active OR terminal run). If both true → run gatekeeper before standard/deep loop. Normal chats and post-harness chats skip gatekeeper entirely. Adds ~one extra small LLM call per pre-harness message; zero overhead when no harness registered.

- **D-06 (Single registered harness for v1.3, gatekeeper hardcoded to it):** Engine registry holds N harnesses; gatekeeper instance is built per-harness with that harness's `HarnessPrerequisites` + `harness_intro` baked into its system prompt. For v1.3 (Phase 20–22), only one harness exists at any time (`smoke-echo` until Phase 22, then `contract-review` joins it). Multi-harness picker (gatekeeper classifies intent and routes) deferred to a future milestone when 2+ user-facing harnesses exist. Per-thread sticky harness binding deferred (no UI surface).

- **D-07 (`[TRIGGER_HARNESS]` sentinel — buffer-and-check at end-of-stream):** Gatekeeper streams character-by-character into a backend buffer; on `done` from the LLM, check if buffer ends with `[TRIGGER_HARNESS]` (with optional trailing whitespace). If yes — strip sentinel, flush remaining text to user, then immediately emit `harness_phase_start` in same SSE stream. If no — flush full buffer. Sentinel never reaches the client. Worst case: user sees a tiny lag at end of gatekeeper's last sentence. Inline-streaming with mid-token detection (rejected — tokenization edge cases). JSON-envelope sentinel (rejected — prompt-engineering brittleness).

- **D-08 (Gatekeeper turns persisted to `messages` table with `harness_mode='contract-review'`):** Every gatekeeper exchange (user msg + assistant reply) saved to messages table with the appropriate `harness_mode` tag. Reload-safe: refresh shows full conversation. Gatekeeper LLM is stateless from the LLM's perspective, but the BACKEND reconstructs prior gatekeeper turns from the messages table when computing prerequisites (load all messages for thread where `harness_mode IS NOT NULL` and no `harness_runs` exists yet → those are the gatekeeper conversation history).

### Post-Harness Summary + Locked Plan Panel UX

- **D-09 (Post-harness summary streams INLINE in same SSE response, right after `harness_complete`):** After last harness phase fires `harness_complete`, the same SSE generator immediately makes a separate LLM call with `phase_results` in system prompt and streams the ~500-token summary as a new assistant message. Single user-perceived event: "harness done, here's the summary, here's the report link." Persisted as a separate `messages` row with `harness_mode='contract-review'` so history reconstruction shows it correctly. NOT via `post_execute` callback (rejected — tangles two concerns: deliverable generation and conversational summarization; the engine itself owns the summary, harness definitions own their `post_execute` for things like DOCX). NOT wait-for-next-message (rejected — dead air after completion).

- **D-10 (Truncation strategy when `phase_results` exceeds 30k chars — POST-05):** For phases `1..N-2`, include phase name + brief output summary (first 200 chars + truncation marker `...[truncated, see workspace artifact]`). For phases `N-1` and `N`, full content. Predictable, deterministic, no extra LLM call. Most-recent phases (executive summary, redlines) usually most decision-relevant. Recursive LLM summarization (rejected — extra LLM call to every harness completion). Hard byte-truncate (rejected — chops mid-JSON).

- **D-11 (Locked Plan Panel visual treatment — lock icon + tooltip + Cancel button):** Panel header shows: `🔒 Contract Review` (the harness-type label) + tooltip on icon hover ("System-driven plan — cannot be modified during execution") + Cancel button (D-03). List items render normally with the existing pending/in_progress/completed visual differentiation, but no add/delete affordances. Matches calibrated-restraint design tokens (no full purple banner — rejected per CLAUDE.md design system rules; subtle icon-only — rejected per discoverability).

- **D-12 (Lock enforcement — defense in depth):** Three layers:
  1. **LLM-side (PANEL-03):** Harness phase tool sets exclude `write_todos`/`read_todos` from the LLM's available tools list. The LLM literally cannot modify the plan — no prompt-injection escape.
  2. **UI-side:** `PlanPanel.tsx` checks `harness_runs.status` for the thread; if active, hides any future mutation buttons (currently none, but future-proofs).
  3. **Backend-side:** `agent_todos` PUT/DELETE endpoints (if ever added) check for active `harness_run` and reject with 409 Conflict. Today's POST `write_todos` tool already gates on tool registration which is gated on flag — but adding the active-run check provides belt-and-suspenders.

### File-Upload UX + Extraction Timing + Engine Smoke-Test Strategy

- **D-13 (Paperclip icon in chat input toolbar — always visible when `WORKSPACE_ENABLED`):** Per UPL-04 the spec says "when a harness mode is active" but `workspace_files` supports general agent uploads too (Phase 18 left this open). Paperclip in chat input is intuitive (matches Slack/WhatsApp), works for both harness flows (gatekeeper sees the new file in workspace and triggers) AND general workspace upload. When no harness is registered, file just lands in workspace as `source='upload'`. Gates on `WORKSPACE_ENABLED` (Phase 18 D-08); when off, the icon hides entirely. (Note: this is a small extension beyond UPL-04 verbatim — captured here so plan-phase doesn't undo it.)

- **D-14 (DOCX/PDF text extraction — lazy at harness-phase runtime — UPL-03):** Upload endpoint just stores binary in `workspace-files` bucket + metadata row in `workspace_files` with `source='upload'`. Extraction happens in Phase 1 (`programmatic`) of any consumer harness — that phase reads the binary via `WorkspaceService.read_file` and runs `python-docx` (DOCX) / `PyPDF2` (PDF). Per Contract Review CR-01 spec. Extraction errors surface as harness phase failures (clean error path via the structured-error pattern). Eager extraction (rejected — couples upload latency to extraction; wastes work on uploads that never trigger harness). Both eager+lazy fallback (rejected — two code paths for marginal benefit).

- **D-15 (OCR fallback for scanned PDFs — deferred to Phase 22+):** Phase 20 extraction is text-layer-only. If `PyPDF2` extracts <500 chars from a PDF, Phase 1 of the consumer harness writes a structured error to `phase_results` + `contract-text.md` ("Scanned PDF — no text layer detected"). User sees the error in the post-harness summary. Avoids re-implementing the GPT-4o vision OCR path (RAG-03) inside the harness now — keeps Phase 20 scope tight. If Phase 22 UAT shows real customers uploading scans, add the fallback then. Sandbox/Tesseract OCR (rejected — Dockerfile bloat).

- **D-16 (Ship a 2-phase smoke harness — `harnesses/smoke_echo.py`):** **CRITICAL for verifier to pass Phase 20.** Adds ~50 LOC: Phase 1 `programmatic` ("echo upload metadata to workspace") + Phase 2 `llm_single` ("summarize the echo as JSON via Pydantic schema {echo_count: int, summary: str}"). Lets us E2E test gatekeeper → `harness_runs` → phase dispatch → `phase_results` persistence → post-harness summary → locked Plan Panel without waiting for Phase 22. Without this, success criteria #1–6 cannot be E2E-verified. Smoke harness stays in the registry as a developer/admin diagnostic, gated behind `HARNESS_SMOKE_ENABLED` flag (default `False` in production, `True` in test/dev environments). 3-phase variant adding `llm_agent` (rejected for now — `llm_agent` is exercised via integration tests against Phase 19's `sub_agent_loop`; if engine validation reveals a gap we add it during execution).

### Claude's Discretion (locked sensible defaults; plan-phase / executor finalizes)

- **Single feature flag `HARNESS_ENABLED`** (default `False`, Pydantic Settings). Mirrors `DEEP_MODE_ENABLED` / `WORKSPACE_ENABLED` / `SUB_AGENT_ENABLED` precedent. When OFF: gatekeeper not registered, harness engine not invoked, REST upload endpoint returns 404, locked Plan Panel variant inert, post-harness summary path inert. Codebase byte-identical to pre-Phase-20 when off (matches Phase 19 D-17 single-flag rationale — sub-features are tightly coupled).
- **Separate `HARNESS_SMOKE_ENABLED` flag** (default `False` production, `True` dev/test) controls whether `smoke-echo` is registered in the harness registry. Independent from `HARNESS_ENABLED` so prod can enable harness engine + only register `contract-review` (Phase 22) without the smoke harness.
- **Phase timeout defaults from PRD:** `llm_single` = 120s, `llm_agent` = 300s, `programmatic` = 60s (PRD silent — pick a sane default). Configurable per `PhaseDefinition`.
- **Gatekeeper LLM provider:** Same OpenRouter model as deep mode by default (cheap small model is fine). Per-feature provider override via existing admin settings UI (PROVIDER-* from v1.0).
- **`HarnessPrerequisites` dataclass shape** (per PRD §Feature 2.2): `requires_upload: bool`, `upload_description: str` (e.g. "your contract DOCX or PDF"), `harness_intro: str` (the welcome message). Plus `accepted_mime_types: list[str]` to constrain upload validation. Plus `min_files: int = 1` and `max_files: int = 1` for explicit bounds.
- **`PhaseDefinition` dataclass shape** (per HARN-10): `name`, `description`, `phase_type` (enum), `system_prompt_template` (5-15 lines), `tools` (list[str]), `output_schema` (Pydantic class), `validator` (optional callable), `workspace_inputs` (list[str]), `workspace_output` (str), `batch_size` (int, default 5 — used by Phase 21), `post_execute` (optional async callable). Plus `timeout_seconds: int` per phase override.
- **`HarnessRegistry` directory layout:** `backend/app/harnesses/` directory with one Python file per harness; `__init__.py` auto-imports and registers. `harnesses/smoke_echo.py` is the canonical example.
- **`progress.md` format (OBS-01):** Single-writer markdown file in workspace, written after each phase transition. Append-only header + per-phase section: `## Phase N: <name>` followed by status emoji + intermediate detail (classification summary, clause count, risk tally, etc. — phase-specific). Engine writes; harness phases don't.
- **Post-harness summary prompt** instructs the LLM to keep response ≤500 tokens via system-prompt guidance ("Be concise — 3-5 short paragraphs. Reference workspace files by path"); soft enforcement, no hard token cut. If model overshoots significantly, plan-phase may add a max-tokens kwarg.
- **i18n strings (ID + EN)** — chip wording, tooltip text, banner messages. Plan-phase / executor finalizes; defaults follow Phase 19 D-26 conventions (short, friendly, chip-fit).
- **File upload size cap** = 25 MB (large enough for typical contracts including scanned ones; small enough to bound storage cost). Server-side validation + clear error message if exceeded.
- **Locked Plan Panel `paused` state** (Phase 21 territory) reserved in the UI rendering logic now (case in the status switch), but not exercised in Phase 20.

### Folded Todos

(No todos folded — `gsd-sdk query todo.match-phase 20` returned 0 matches.)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary PRD & Roadmap
- `docs/PRD-Agent-Harness.md` §Part 2 (lines 176–342) — Domain-Specific Harness Engine: phase types, phase definition dataclass, engine architecture, data model, registry, SSE events.
- `docs/PRD-Agent-Harness.md` §Feature 2.2 (lines 246–258) — Gatekeeper LLM contract: stateless, sentinel-based trigger, multi-turn, `HarnessPrerequisites` dataclass.
- `docs/PRD-Agent-Harness.md` §Feature 2.3 (lines 261–273) — Post-Harness Response LLM: phase results into system prompt, ~500-token summary, separate assistant message, 30k-char truncation.
- `docs/PRD-Agent-Harness.md` §Feature 2.6 (lines 314–325) — File Upload: endpoint, Storage, metadata, extraction utilities.
- `docs/PRD-Agent-Harness.md` §Feature 2.7 (lines 329–340) — Plan Panel locked variant: `agent_todos` write, tool stripping, lock icon.
- `docs/PRD-Agent-Harness.md` §Cross-Cutting Concerns (lines 403–422) — Security, SSE, provider compatibility, observability.
- `docs/PRD-Agent-Harness.md` §Configuration (lines 459–465) — `MAX_DEEP_ROUNDS`, `MAX_TOOL_ROUNDS`, `MAX_SUB_AGENT_ROUNDS` (already shipped in Phase 17).
- `.planning/ROADMAP.md` §Phase 20 (lines 127–140) — Goal, depends_on (17, 18, 19), 35 requirements, 6 Success Criteria.
- `.planning/REQUIREMENTS.md` §HARN-* §GATE-* §POST-* §PANEL-* §UPL-* §MIG-03 §SEC-02..04 §OBS-01..03 (lines 74–174) — full requirement text for Phase 20's 35 reqs.
- `.planning/PROJECT.md` §"Current Milestone: v1.3", §"Key Decisions" — invariants and prior milestone decisions still in force.
- `.planning/STATE.md` §"Roadmap Snapshot (v1.3)", §"v1.3 contract / invariants" — wave structure, no auto retries, no frontend loop, raw SDK only, recursive sub-agents disabled, harness definitions are global.

### Phase 19 (sub-agent + ask_user + status) — direct ancestor for `llm_agent` phase type
- `.planning/phases/19-sub-agent-delegation-ask-user-status-recovery/19-CONTEXT.md` — D-01..D-04 close-and-resume protocol pattern (mirrored for harness pause/resume in Phase 21), D-03 `agent_runs` schema (template for `harness_runs` D-01), D-08 sub-agent context_files inline pattern, D-11 sub-agent loop-cap fallback (mirrored for harness phase timeouts), D-12 sub-agent failure isolation, D-17 single feature flag pattern (template for `HARNESS_ENABLED`), D-18..D-20 append-only error contract, D-21 egress filter coverage, D-22 sub-agent JWT inheritance.
- `backend/app/services/sub_agent_loop.py` (Phase 19 plan 19-03) — REUSED DIRECTLY by `llm_agent` phase dispatcher; do NOT duplicate.
- `backend/app/services/agent_runs_service.py` (Phase 19 plan 19-02) — service-layer template for `harness_runs_service.py`.
- `supabase/migrations/040_agent_runs.sql` — partial-unique-on-active-row + RLS template for migration 042.

### Phase 18 (workspace) — context-passing substrate
- `.planning/phases/18-workspace-virtual-filesystem/18-CONTEXT.md` — D-02 `workspace_files` schema (extended by Phase 20 file upload via `source='upload'`), D-04 `workspace-files` bucket + 4-segment path RLS (used for upload binary storage), D-05 path validator (1 MB text cap, no traversal), D-08 `WORKSPACE_ENABLED` feature-flag pattern (mirrored), D-09 REST endpoints (file upload extends with `POST /threads/{id}/files/upload`), D-10 `workspace_updated` SSE event (fires after upload).
- `backend/app/services/workspace_service.py` — `validate_workspace_path`, `read_file` (used by harness Phase 1 to read uploaded binary), `register_sandbox_files` (template for `register_uploaded_file`), CRUD against `workspace_files`. Sub-agent inherits these tools as-is via `llm_agent` phases.
- `backend/app/routers/workspace.py` (Phase 18 plan 18-04) — extension target for `POST /threads/{id}/files/upload` (Phase 20 plan adds it here).
- `supabase/migrations/039_workspace_files.sql` — bucket + RLS template; `workspace-files` bucket already exists.

### Phase 17 (deep mode + todos) — Plan Panel substrate
- `.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-CONTEXT.md` — D-08 hand-coded loop pattern, D-12 loop-cap fallback (mirrored for harness phase timeouts), D-14 env-driven CONF (defaults locked), D-16 dark-launch flag pattern, D-17 SSE event format, D-31 tool registry adapter-wrap invariant, D-32 egress filter coverage.
- `backend/app/services/agent_todos_service.py` (Phase 17 plan 17-03) — `write_todos`/`read_todos` service; Phase 20 PANEL-01 calls this from harness engine to write phase progress.
- `backend/app/services/deep_mode_prompt.py` — Phase 17 deep-mode prompt template (NOT modified by Phase 20).
- `frontend/src/components/chat/PlanPanel.tsx` (Phase 17 plan 17-07) — extension target for locked variant (lock icon, tooltip, Cancel button, hide mutation affordances).
- `supabase/migrations/038_agent_todos_and_deep_mode.sql` — provides `agent_todos` table and `messages.deep_mode` + `messages.harness_mode` columns (MIG-04 already done; Phase 20 only USES `harness_mode`).

### Codebase patterns to mirror
- `backend/app/routers/chat.py` — gatekeeper invocation site (entry of `stream_chat`, before deep-mode dispatch); resume-detection branch from Phase 19 D-04 is the closest analog for harness-active-run check; SSE event ordering and queue-drain pattern for sub-agent forwarding (Phase 19 D-06).
- `backend/app/services/tool_service.py` — adapter-wrap invariant from Phase 13 D-P13-01 (no edits to lines 1-1283); harness phase tool sets are CURATED (per-phase `tools: list[str]`), constructed by filtering the unified registry.
- `backend/app/services/tool_registry.py` (v1.2) — `ToolRegistry.list_tools()` and per-name lookup for harness phase tool curation.
- `backend/app/services/agent_service.py` — v1.0 multi-agent classifier (research/data_analyst/general/explorer); UNCHANGED by Phase 20, coexists with gatekeeper (gatekeeper runs BEFORE classifier; if gatekeeper fires harness, classifier never runs for that turn).
- `backend/app/services/redaction/egress.py` — egress filter wrapper used by harness LLM payloads (gatekeeper, `llm_single`, `llm_agent`, post-harness summary). SEC-04 invariant.
- `backend/app/services/audit_service.py` — `log_action(...)` for harness lifecycle events (`harness_started`, `harness_completed`, `harness_cancelled`, `harness_failed`).
- `backend/app/services/system_settings_service.py` — `get_system_settings()` 60s cache for `harness_enabled` admin toggle (if surfaced; v1.3 stays env-var only).

### Frontend patterns to mirror
- `frontend/src/components/chat/PlanPanel.tsx` (Phase 17) — extension target for locked variant.
- `frontend/src/components/chat/WorkspacePanel.tsx` (Phase 18) — visibility-rule + reducer pattern; file upload progress UI mirrors download UI.
- `frontend/src/components/chat/AgentStatusChip.tsx` (Phase 19) — status-chip pattern; Phase 20 adds `harness_status` slice or extends `agentStatus` (plan-phase decides).
- `frontend/src/components/chat/MessageView.tsx` — assistant message rendering; harness gatekeeper turns + post-harness summary render normally.
- `frontend/src/components/chat/AppLayout.tsx` — chat header slot; harness banner ("Contract Review running phase N/M") sits here.
- `frontend/src/components/chat/ChatInput.tsx` (or wherever the input toolbar lives) — paperclip icon insertion site for file upload.
- `frontend/src/hooks/useChatState.{ts,tsx}` — reducer + slice patterns; Phase 20 adds `harnessRun` slice (status, currentPhase, phaseName, harnessType) + `uploadingFiles` slice for in-flight uploads.
- `frontend/src/i18n/` — Indonesian + English label conventions (banner, tooltip, paperclip aria-label, error messages).
- Vitest 3.2 (v1.2 D-P16-02) — `LockedPlanPanel.test.tsx`, `FileUploadButton.test.tsx`, `HarnessBanner.test.tsx` follow co-located convention.

### Migration reference
- `supabase/migrations/040_agent_runs.sql` — closest analog template for `042_harness_runs.sql` (partial unique on active-row + RLS pattern).
- `supabase/migrations/039_workspace_files.sql` — bucket pattern (workspace-files bucket already provisioned).
- `supabase/migrations/036_code_executions_and_sandbox_outputs.sql` — partial unique constraint precedent / RLS pattern.
- `supabase/migrations/001_initial_schema.sql` lines 7–80 — `threads` and `messages` tables; FK targets for `harness_runs.thread_id`.

### Project conventions
- `CLAUDE.md` — TDD rule, atomic commits via `gsd-sdk query commit`, RLS on every new table, no LangChain/LangGraph (harness engine is hand-coded state machine), Pydantic for structured LLM outputs, base-ui `asChild` shim conventions, glass-only-on-overlays rule, `/create-migration` skill (BUT plan-phase MUST verify next free integer is 042, not 041 — see D-01).
- `.planning/codebase/STACK.md`, `STRUCTURE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `TESTING.md`, `INTEGRATIONS.md`, `CONCERNS.md` — codebase living docs.

### Prior milestone artifacts (decisions still in force)
- `.planning/milestones/v1.0-ROADMAP.md`, `v1.0-REQUIREMENTS.md` — privacy invariant, egress filter coverage, audit log convention, async-lock D-31 deferral.
- `.planning/milestones/v1.1-ROADMAP.md`, `v1.1-REQUIREMENTS.md` — code execution sandbox (Phase 22 DOCX uses sandbox via `post_execute`).
- `.planning/milestones/v1.2-ROADMAP.md`, `v1.2-REQUIREMENTS.md` — `ToolRegistry` adapter-wrap invariant (lines 1-1283 untouched), MCP integration, Vitest 3.2.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`run_deep_mode_loop`** (`chat.py:1545+`) — the deep-mode entry pattern; harness engine sits ALONGSIDE it (not inside) as a peer dispatcher invoked by the gatekeeper-trigger or resume-detection branch. The standard tool-calling loop, deep-mode loop, and harness engine are three peer execution modes selected at the top of `stream_chat`.
- **`sub_agent_loop`** (`backend/app/services/sub_agent_loop.py`, Phase 19 plan 19-03) — REUSED DIRECTLY by `llm_agent` phase dispatcher. Each `llm_agent` phase dispatch invokes `sub_agent_loop.run(description, context_files=phase.workspace_inputs, tools=phase.tools, max_rounds=10_default_or_per_phase_override)`. No duplication — this is the entire point of Phase 19 landing first.
- **`tool_registry.register()`** + per-name lookup — harness phase tool curation reads `phase.tools: list[str]` and constructs a curated tool subset by name lookup. New tool registration: NONE in Phase 20 (the engine USES existing tools; doesn't add new ones).
- **`get_supabase_authed_client(token)`** — `harness_runs_service` and resume-detection branch reuse identically for RLS-scoped queries.
- **PII redaction egress filter** (`backend/app/services/redaction/egress.py`) — already wraps deep-mode + sub-agent LLM payloads; harness engine's gatekeeper, `llm_single`, `llm_agent`, and post-harness summary calls reuse the same wrapper. Privacy invariant covered with zero new code.
- **`WorkspaceService` from Phase 18** — `validate_workspace_path`, `read_file`, `write_file`, dual storage routing, `register_sandbox_files` template; harness file upload extends with `register_uploaded_file(thread_id, file_obj, source='upload')`.
- **Audit logging** (`audit_service.log_action(...)`) — used for harness lifecycle (started/completed/cancelled/failed) and file upload (uploaded).
- **Executor-emitted SSE event queue** (`chat.py:455+`) — sandbox emits via callback into a queue; chat-loop drains between events. Harness engine's `harness_phase_*` SSE events reuse the same queue/drain pattern. Sub-agent SSE forwarding (Phase 19 D-06) tagged with `task_id` is the model for harness-spawned sub-agents.
- **`handle_updated_at` trigger** — defined in `001_initial_schema.sql`; reused by `harness_runs` migration without redefinition.
- **Pydantic + `response_format: json_schema`** — used across v1.0 document tools, v1.2 redaction settings; harness `llm_single` phases enforce structured output identically.
- **`messages.harness_mode` column** — already exists from migration 038 (Phase 17 plan 17-01). Phase 20 ONLY USES it (no ALTER). MIG-04 from Phase 17.
- **Vitest 3.2** — frontend test framework bootstrapped in v1.2; `LockedPlanPanel.test.tsx`, `FileUploadButton.test.tsx`, `HarnessBanner.test.tsx` follow `CodeExecutionPanel.test.tsx` co-located convention.

### Established Patterns
- **Numbered sequential migrations:** Next is **042**. PreToolUse hook blocks edits to applied migrations 001-041 (CLAUDE.md gotcha: hook regex blocks 001-027 only — 028+ NOT auto-blocked despite being applied; treat all numbered migrations as immutable regardless).
- **Feature flags via Pydantic Settings:** `TOOL_REGISTRY_ENABLED`, `SANDBOX_ENABLED`, `WORKSPACE_ENABLED`, `DEEP_MODE_ENABLED`, `SUB_AGENT_ENABLED` precedent — `HARNESS_ENABLED` and `HARNESS_SMOKE_ENABLED` follow. Default `False` for v1.3 dark launch.
- **SSE event format:** `data: {"type": "<event_name>", ...}\n\n`; `harness_phase_start` / `harness_phase_complete` / `harness_phase_error` / `harness_complete` / `harness_human_input_required` (Phase 21) follow.
- **Atomic per-plan commits:** Each PLAN.md = one `gsd-sdk query commit` invocation.
- **Pydantic structured output:** `llm_single` phases validate via Pydantic before advancing; `response_format: json_schema` for OpenAI/OpenRouter.
- **Form duplication rule (CLAUDE.md):** N/A for Phase 20 (no form fields added; chat input toolbar is single-component).
- **Glass / panel rule (CLAUDE.md):** Locked Plan Panel is a persistent surface — NO `backdrop-blur`. Solid panel surface only. Tooltip CAN use glass per design system rules.
- **Indonesian-default i18n:** All harness UI strings (banner, tooltip, paperclip aria-label, error messages, post-harness summary system prompt user-facing fragments) routed through `I18nProvider`; supply ID + EN strings.
- **Tool-result structured errors (NOT exceptions):** Phase 19 D-18 codified; harness phase failures follow the same shape — engine catches, transforms to `{"error": "...", "code": "...", "detail": "..."}`, persists in `phase_results[N]`, emits `harness_phase_error` SSE event, parent decides next move (retry next phase, abort, etc.).
- **No automatic retries (STATUS-03):** Harness engine has NO catch-and-retry. Phase failure → `harness_runs.status='failed'` + emit error → engine stops. Operator/user re-triggers via cancel + new message.

### Integration Points
- **`backend/app/routers/chat.py`:**
  - `stream_chat` entry: NEW gatekeeper-routing branch (D-05) BEFORE existing deep-mode/standard dispatch. Order: (1) check Phase 19 `agent_runs` resume-detection (existing) → (2) check `harness_runs` active-run-block (D-02 — reject new chat msg) → (3) check `HarnessRegistry` non-empty AND no harness_runs for thread (D-05 — run gatekeeper) → (4) standard/deep dispatch.
  - `run_harness_engine`: NEW async generator alongside `run_deep_mode_loop`. Drives phase transitions, persists to `harness_runs`, emits SSE events, calls post-harness summary on completion.
- **`backend/app/services/harness_engine.py`:** NEW file. Core dispatcher: `class HarnessEngine` with `run(harness, run_id, thread_id, user_id, token)` async generator. Per-`PhaseType` execution methods.
- **`backend/app/services/harness_runs_service.py`:** NEW file. CRUD + state-machine helpers (start_run, advance_phase, complete, fail, cancel) + active-run lookup.
- **`backend/app/services/harness_registry.py`:** NEW file. Module-level dict + `register()` decorator + `get_harness(name)` + `list_harnesses()` + auto-import from `backend/app/harnesses/` directory.
- **`backend/app/harnesses/__init__.py`:** NEW. Auto-imports every `.py` in directory.
- **`backend/app/harnesses/smoke_echo.py`:** NEW. The 2-phase smoke harness (D-16). Gated behind `HARNESS_SMOKE_ENABLED`.
- **`backend/app/services/gatekeeper.py`:** NEW file. `class Gatekeeper` with `run(thread_id, user_msg, harness, token)` async generator. Handles multi-turn dialogue, sentinel detection, sentinel stripping.
- **`backend/app/services/post_harness.py`:** NEW file. `summarize_harness_run(harness_run, token)` async generator. Truncation per D-10. Streams ~500-token summary.
- **`backend/app/routers/workspace.py`:** EXTEND with `POST /threads/{id}/files/upload` endpoint. 25 MB cap. Multipart form parsing. RLS-scoped via `get_supabase_authed_client(token)`.
- **`backend/app/services/workspace_service.py`:** EXTEND with `register_uploaded_file(thread_id, file_obj, source='upload')` mirroring `register_sandbox_files`.
- **`backend/app/services/tool_service.py`:** NO edits (adapter-wrap invariant). Per-phase tool curation reads from existing registry by name.
- **`backend/app/config.py`:** add `harness_enabled: bool = False` and `harness_smoke_enabled: bool = False` Pydantic Settings fields.
- **`frontend/src/components/chat/PlanPanel.tsx`:** EXTEND with locked variant (D-11, D-12). Reads `harnessRun` slice; if active, shows lock icon + tooltip + Cancel button + harness-type label; hides mutation affordances.
- **`frontend/src/components/chat/HarnessBanner.tsx`:** NEW component. Renders when `harnessRun.status` is active; shows "Contract Review running phase N/M" + Cancel button. Slotted in chat header by `AppLayout.tsx`.
- **`frontend/src/components/chat/FileUploadButton.tsx`:** NEW component. Paperclip icon in chat input toolbar. Multipart upload with progress, error handling, MIME validation.
- **`frontend/src/hooks/useChatState.{ts,tsx}`:** add `harnessRun` slice (status, harnessType, currentPhase, phaseName) + `uploadingFiles` slice + reducer cases for `harness_phase_*` SSE events.
- **`frontend/src/i18n/`:** add harness banner / tooltip / paperclip / error strings (ID + EN).
- **`supabase/migrations/042_harness_runs.sql`:** NEW migration — `harness_runs` table + RLS + partial unique index + indexes (D-01).

</code_context>

<specifics>
## Specific Ideas

- **Migration 042 (NOT 041) is the recurring footgun for this phase.** The ROADMAP comment "will be 040–041 if numbering preserved" was written BEFORE the duplicate-024 cleanup that renamed `024_rag_improvements.sql` → `041_rag_improvements_legacy.sql` (commit `53768e2`, recorded in CLAUDE.md Gotchas). Plan-phase MUST verify with `ls supabase/migrations/` before generating the migration. `/create-migration` skill picks next free integer correctly.
- **Three peer execution modes at `stream_chat` top:** (1) standard tool-calling loop, (2) deep-mode loop (Phase 17), (3) harness engine (Phase 20). The gatekeeper is a router that may select (3); resume-detection from Phase 19 may continue (2). Order of checks at entry: ask_user resume → harness active-run block → gatekeeper-eligibility → standard/deep dispatch.
- **`harness_runs.status='paused'`** is reserved in the CHECK constraint for Phase 21's `llm_human_input` phase but unused in Phase 20. Locking the enum value now prevents a migration churn in Phase 21.
- **Smoke harness validates the verifier's path.** Without `smoke-echo`, Phase 20 verifier cannot E2E test success criteria #1–6 (gatekeeper conversation → harness trigger → phase dispatch → post-harness summary → locked Plan Panel) because Contract Review is Phase 22. The smoke harness is small (~50 LOC) and stays as a developer/admin tool post-Phase-22.
- **Banner wording (plan-phase finalizes ID + EN):**
  - EN: "Contract Review running — phase 3 of 8 (Gather Context)" + Cancel button
  - ID: "Tinjauan Kontrak berjalan — fase 3 dari 8 (Kumpulkan Konteks)" + tombol Batalkan
- **Tooltip wording:** "System-driven plan — cannot be modified during execution" (EN) / "Rencana sistem — tidak dapat diubah saat berjalan" (ID).
- **Gatekeeper sentinel:** literal `[TRIGGER_HARNESS]` (12 chars) stripped end-of-stream before flush. Match with regex `\s*\[TRIGGER_HARNESS\]\s*$` to allow trailing whitespace tolerance.
- **`harness_runs.id` in SSE payload:** every harness-related SSE event includes `harness_run_id` so the frontend can correlate events to the active run (in case multiple SSE streams overlap during a refresh).
- **`progress.md` lives at workspace path `progress.md`** (root, no subdirectory). Single writer = harness engine; harness phases never write to `progress.md` directly. Format: append a `## Phase {N}: {name}` section with status emoji + a 5-10 line intermediate summary after each phase transition.
- **File upload validation:** content-type AND magic-bytes check (DOCX = `PK\x03\x04` + `[Content_Types].xml`, PDF = `%PDF-`); reject 25 MB+, reject if MIME doesn't match `accepted_mime_types` from the active harness's `HarnessPrerequisites`.

</specifics>

<deferred>
## Deferred Ideas

(Most ideas surfaced are in-scope for Phase 20 or already explicitly deferred to Phase 21/22 by the v1.3 ROADMAP.)

- **`llm_batch_agents` and `llm_human_input` phase types** — Phase 21.
- **Contract Review domain harness, DOCX deliverable** — Phase 22.
- **OCR fallback for scanned PDFs (vision via GPT-4o, RAG-03 pattern)** — deferred to Phase 22+ if UAT shows scanned uploads in real customer use. Phase 20 surfaces extraction failure cleanly, so a future addition is non-breaking.
- **Multi-harness picker / dispatcher** — deferred until 2+ user-facing harnesses exist (likely a future milestone with NDA / vendor-assessment / compliance-check harnesses per PRD Post-MVP §Additional domain harnesses).
- **`/cancel-harness` slash command** — Cancel button in panel is sufficient for v1.3.
- **Per-thread sticky harness binding** — deferred; gatekeeper-driven harness selection is sufficient for v1.3.
- **Eager DOCX/PDF text extraction at upload time** — lazy at harness-phase runtime is the chosen pattern; eager could revisit if Phase 22 UAT shows perceptible Phase 1 latency.
- **Cross-process advisory lock for harness_runs race conditions** — same async-lock D-31 carryover from v1.0; deferred. Risk: two simultaneous `/chat` POSTs after gatekeeper trigger could both transition status. Mitigation: partial unique index + transactional INSERT with `ON CONFLICT DO NOTHING` is sufficient for v1.3 single-worker.
- **Admin UI surface for `HARNESS_ENABLED` / `HARNESS_SMOKE_ENABLED`** — env-var only in v1.3; admin surface deferred to a future milestone (or post-MVP).
- **System-settings cache integration** — toggle via `system_settings.harness_enabled` (60s TTL pattern) deferred alongside admin UI.
- **Background / async harness runs (continue server-side after disconnect)** — explicit Post-MVP per PRD; Phase 20 honors this stance. Mid-stream disconnect = lose in-progress phase, persisted state up to last completed phase = recoverable on follow-up trigger.
- **Auto-resume from `failed` state** — explicitly out of scope per success criterion #6 + STATUS-03 (LLM-driven recovery only); failed runs stay failed until user re-triggers.
- **Per-user harness preferences / customization** — explicitly out of scope per ROADMAP "harness definitions are global / system-defined" invariant. Per-user variants undermine deterministic-flow guarantee.
- **Mid-stream cancellation of an llm_human_input phase** — Phase 21 territory; cancellation only between rounds/phases per HARN-07.
- **`harness_runs` history admin UI / cleanup tooling** — completed/failed/cancelled rows accumulate; cleanup deferred to a maintenance phase.
- **Workspace garbage-collection for orphaned uploaded files** — `ON DELETE CASCADE` removes the DB row when a thread is deleted but does not evict Storage. Deferred (carried from Phase 18 deferred).
- **Filename / document-metadata PII redaction** (already in PROJECT.md Out of Scope) — still out of scope for Phase 20 file upload; chat message content only.
- **3-phase smoke harness adding `llm_agent` coverage** — D-16 chose 2-phase; if Phase 20 execution reveals an `llm_agent` integration gap, the smoke harness can grow during execution.

### Reviewed Todos (not folded)

(No pre-existing `.planning/todos/` matches surfaced — `gsd-sdk query todo.match-phase 20` returned 0 matches.)

</deferred>

---

*Phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock*
*Context gathered: 2026-05-03*
