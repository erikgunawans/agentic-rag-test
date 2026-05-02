# Phase 18: Workspace Virtual Filesystem - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** `--auto` (decisions auto-selected from project defaults; see DISCUSSION-LOG.md)

<domain>
## Phase Boundary

Deliver a per-thread durable virtual filesystem (`workspace_files`) that holds text and binary artifacts produced by the agent, sandbox, or user upload. Surfaces are:

1. Four LLM tools registered through the unified Tool Registry (Phase 13 pattern): `write_file`, `read_file`, `edit_file`, `list_files`.
2. Two RLS-scoped REST endpoints: `GET /threads/{id}/files` (list) and `GET /threads/{id}/files/{path:path}` (read text inline / signed-URL redirect for binary).
3. A new frontend Workspace Panel sidebar component, decoupled from Deep Mode (visible whenever the thread has at least one workspace file).
4. Re-engineering of the v1.1 sandbox file flow so sandbox-generated outputs are auto-registered as `workspace_files` rows with `source="sandbox"` (fixes the "download link disappears on refresh" bug).
5. New SSE event `workspace_updated` emitted on every workspace mutation.

**Strict scope guardrail:**
- File upload (DOCX/PDF) UI + extraction is OUT OF SCOPE — that is `UPL-01..04` in Phase 20.
- `task` sub-agent sharing of the workspace is implemented via WS-06 read/write semantics in this phase, but the `task` tool itself is built in Phase 19. WS-06 verifies only that the data layer + RLS make sub-agent sharing trivially correct (RLS on thread, not on caller).
- Harness use of workspace as context is enabled by WS-11 decoupling, but harness engine is Phase 20.

</domain>

<decisions>
## Implementation Decisions

### D-01 — Migration number and ordering
- **Migration file:** `supabase/migrations/039_workspace_files.sql`
- **Ordering:** Phase 17 owns `038_agent_todos.sql` and `041_messages_deep_mode_harness_mode.sql` (per STATE.md plan). Phase 18 takes 039 (next sequential after 037 deny-list and Phase 17's 038). If Phase 17 lands its 038 first, no conflict. If both phases push migrations simultaneously and 039 is taken, executor renumbers to the next free integer. Record in plan: collision check at `execute-phase` time.
- **Created via:** `/create-migration` skill to keep RLS template + sequencing intact.

### D-02 — `workspace_files` table schema
| Column | Type | Notes |
|---|---|---|
| `id` | `uuid PRIMARY KEY DEFAULT gen_random_uuid()` | |
| `thread_id` | `uuid NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE` | RLS anchor |
| `file_path` | `text NOT NULL` | DB-level CHECK: length ≤ 500, no leading `/`, no `\\`, no `..` segments — defence-in-depth; primary validation lives in service layer |
| `content` | `text` | NULL for binary files; populated for text files (sub-100 ms reads target) |
| `storage_path` | `text` | NULL for text files; populated for binary files; references object in Storage bucket |
| `source` | `text NOT NULL CHECK (source IN ('agent','sandbox','upload'))` | Discriminator |
| `size_bytes` | `integer NOT NULL DEFAULT 0` | For both text and binary; cheap accessor for list endpoint |
| `mime_type` | `text` | Optional; populated for binary; defaults to `text/markdown` for text written by agent unless edit-tool overrides |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | Trigger-maintained on UPDATE |

**Constraints:**
- `UNIQUE (thread_id, file_path)` — supports `write_file` upsert semantics on `(thread_id, file_path)` conflict.
- `CHECK (content IS NOT NULL OR storage_path IS NOT NULL)` — exactly one of the two storage columns is populated.
- `CHECK (NOT (content IS NOT NULL AND storage_path IS NOT NULL))` — never both.

**Indexes:**
- Primary key on `id`.
- Composite index on `(thread_id, file_path)` (already implicit from UNIQUE).
- Index on `(thread_id, created_at DESC)` for the list endpoint.

### D-03 — RLS policies (thread-ownership scope)
Mirror the v1.0–v1.2 pattern (`code_executions`, `entity_registry`):
- `SELECT`: `thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid())` OR super_admin.
- `INSERT` / `UPDATE` / `DELETE`: same predicate, scoped to user-owned threads. (No DELETE FROM agent — DELETE policy exists for service cleanup but agent path uses `write_file` upsert + future explicit `delete_file` not in this phase.)
- Trigger maintains `updated_at` on UPDATE.
- D-03b: Agent-facing tools dispatch through `get_supabase_authed_client(token)` (RLS-scoped) — service-role client is reserved for system maintenance.

### D-04 — Storage bucket for binary files
- **Reuse strategy:** keep the existing v1.1 `sandbox-outputs` bucket as the canonical landing zone for sandbox-generated binaries (avoids re-uploading existing rows). For agent-uploaded or user-uploaded binaries, create a new private bucket `workspace-files`.
- **Bucket configuration:** `workspace-files` is private (`public=false`). Path scheme: `{user_id}/{thread_id}/{workspace_file_id}/{filename}` — 4-segment path matching the v1.1 sandbox-outputs RLS pattern (`code_executions` migration 036).
- **RLS:** segment-1 (`user_id`) gates SELECT/INSERT/UPDATE/DELETE. Mirror the policy strings from migration 036.
- **Read path:** REST endpoint generates a 1-hour signed URL (consistent with `_SIGNED_URL_TTL_SECONDS = 3600` in `sandbox_service.py`).
- **Sandbox-generated binaries** stay in `sandbox-outputs` and `workspace_files.storage_path` is set to the existing `{user_id}/{thread_id}/{execution_id}/{filename}` path. The service layer is bucket-aware: `storage_path` is unambiguous because path prefix maps to bucket.
  - **Cleaner invariant:** `workspace_files.storage_bucket` text column is added so the service knows which bucket to issue signed URLs against (rather than path-prefix sniffing). Add to schema in D-02 as an additional nullable column (omitted for text files): `storage_bucket text` (CHECK in `('sandbox-outputs','workspace-files')`).

### D-05 — Path validation (service layer, primary gate)
- Forward slashes only; reject `\\`.
- No leading `/` (relative paths only).
- No `..` segments anywhere in the path (split by `/`, reject any segment equal to `..`).
- Length ≤ 500 chars.
- Reject empty path / whitespace-only path.
- Reject paths ending with `/` (no directory writes).
- Reject control characters and NUL (`\x00`).
- Normalize case-sensitively (no implicit lowercasing — POSIX-style).
- Recommended directories (PRD): `notes/`, `data/`, `drafts/`, `deliverables/` — surfaced in tool description, not enforced.
- Path validator implemented as `validate_workspace_path(path: str) -> str` in `backend/app/services/workspace_service.py`, raises `WorkspaceValidationError` (custom exception); tool dispatch catches and returns structured tool error result (NOT exception), so the LLM can recover without crashing the loop (consistent with STATUS-02 append-only-error invariant in Phase 19).

### D-06 — Text content size limit
- **1 MB hard cap on `content`** (per WS-03). Enforced in service layer before DB write. Returns structured tool error: `{"error": "text_content_too_large", "limit_bytes": 1048576, "actual_bytes": N}`.
- Binary path has no equivalent service-layer cap in this phase; sandbox already enforces its own limits at upload time. Future Phase 20 file-upload may add a per-bucket cap; deferred.

### D-07 — Tool definitions registered through Tool Registry
Each native tool registered via `tool_registry.register(...)` from `tool_service.py` initialization (D-P13-01 pattern). All four are `loading="immediate"` (always in LLM tools array when registry is enabled), `source="native"`.

| Tool | Schema | Behavior |
|---|---|---|
| `write_file(file_path, content)` | `{file_path: string, content: string}` | Upsert text-file row by `(thread_id, file_path)`; sets `source='agent'`, `mime_type='text/markdown'` (or detected). Emits `workspace_updated` SSE. |
| `read_file(file_path)` | `{file_path: string}` | Returns `content` for text. For binary, returns `{is_binary: true, signed_url: "...", size_bytes: N, mime_type: "..."}` — agent can pass the URL to a tool that fetches bytes (out of scope for this phase). |
| `edit_file(file_path, old_string, new_string)` | `{file_path: string, old_string: string, new_string: string}` | Exact-string replacement on text files only. Returns error if `old_string` not unique or not found. Emits `workspace_updated` SSE. |
| `list_files()` | `{}` | Returns `[{file_path, size_bytes, source, mime_type, updated_at}]` ordered by `updated_at DESC`. Matches the panel's display contract. |

**Privacy invariant (SEC-04 covered downstream in Phase 20, but pattern locked here):** Tool RESULTS that contain workspace file content are routed through the existing PII redaction egress filter (`backend/app/services/redaction/egress.py`) before being added to the LLM message history. This is the same filter used today for tool results — workspace tools don't bypass it.

### D-08 — Feature flag
- New env var: `WORKSPACE_ENABLED` (default `True`). Acts as a kill-switch parallel to `TOOL_REGISTRY_ENABLED` and `SANDBOX_ENABLED`. When `False`:
  - The four workspace tools are not registered.
  - REST endpoints return 404.
  - SSE `workspace_updated` events are not emitted.
  - Sandbox file post-processing path falls back to the v1.1 behavior unchanged (signed-URL list returned to chat panel; no `workspace_files` row).
- No system-settings UI surface in this phase — env var only. Admin UI integration deferred to Phase 20 alongside the other v1.3 toggles.

### D-09 — REST endpoints
New router: `backend/app/routers/workspace.py`. Registered in `app/main.py` alongside other routers.

| Method | Path | Returns |
|---|---|---|
| `GET` | `/threads/{thread_id}/files` | `200 [{file_path, size_bytes, source, mime_type, updated_at}]`; `404` if thread doesn't exist or RLS denies; `403` if user lacks access. |
| `GET` | `/threads/{thread_id}/files/{file_path:path}` | Text: `200 text/plain` (or detected MIME) with content body. Binary: `307 redirect` to a 1-hour signed URL (same TTL as v1.1). `404` if not found. |

Both endpoints use `get_supabase_authed_client(token)` so RLS enforces ownership — no manual `user_id` checks. `:path` converter on FastAPI route allows nested paths (e.g., `notes/research.md`).

### D-10 — SSE event taxonomy addition
- Event name: `workspace_updated`
- Payload: `{"type": "workspace_updated", "file_path": "...", "operation": "create" | "update" | "delete", "size_bytes": N, "source": "agent|sandbox|upload"}`
- Emitted from chat-loop SSE generator inside `chat.py` after a successful workspace write (in the same `yield` discipline as `tool_start`/`tool_result`). For sandbox-generated files, emitted from the sandbox post-processing pipeline immediately after the `workspace_files` rows are inserted, BEFORE the existing `tool_result` event for `execute_code` so the panel can show the new files in lockstep.
- Frontend reducer in `useChatState` (or a new `useWorkspaceState`) listens for the event and updates the panel.

### D-11 — Sandbox integration (re-engineering, WS-05)
The existing `_collect_and_upload_files` in `sandbox_service.py` (lines 372-435) already uploads to `sandbox-outputs` bucket and returns `[{filename, size_bytes, signed_url, storage_path}]`. Re-engineering:

1. After successful upload to `sandbox-outputs`, also insert a `workspace_files` row for each file with:
   - `thread_id` = the existing thread_id parameter
   - `file_path` = `f"sandbox/{filename}"` (prefix to avoid collision with agent-written paths; recommended-directory convention)
   - `content` = NULL
   - `storage_path` = the existing 4-segment path
   - `storage_bucket` = `'sandbox-outputs'`
   - `source` = `'sandbox'`
   - `size_bytes`, `mime_type` (best-effort sniff)
2. Emit `workspace_updated` SSE event (or queue one — sandbox runs in executor; chat-loop generator drains the queue, see existing `tool_start` queue draining pattern at `chat.py` L455).
3. **Backward compatibility:** the existing `tool_result.output.files` array (legacy `signed_url`) keeps the same shape. `CodeExecutionPanel.tsx` continues to render. No frontend regression.
4. **Idempotency:** if a sandbox execution retries and the same `(thread_id, file_path)` row already exists, the workspace insert is upsert — uniqueness is enforced and the latest content wins. The `execution_id` differing means `storage_path` updates — old object stays in the bucket (no eviction in this phase).
5. Toggling `WORKSPACE_ENABLED=False` skips the workspace insert and reverts to v1.1 byte-identical behavior.

### D-12 — Frontend Workspace Panel
- New file: `frontend/src/components/chat/WorkspacePanel.tsx`
- Pattern reference: `frontend/src/components/chat/CodeExecutionPanel.tsx` (collapsible, status badges, `apiFetch` for downloads, glass-rule compliant — solid `bg-card`/`bg-zinc-900`, no `backdrop-blur`).
- Layout:
  - Header: title "Workspace" + count badge + collapse caret
  - List: per file → file name, size (formatBytes pattern), source badge (agent / sandbox / upload — color-coded), updated_at relative time
  - Click text file → inline view (expanded panel area or modal — auto-decide: inline expand, since panel is already a sidebar)
  - Click binary → triggers download via signed URL through GET endpoint (307 redirect)
- Visibility rule (WS-11): panel renders whenever `workspaceFiles.length > 0` for the current thread. Decoupled from Deep Mode. The thread's initial render fetches `GET /threads/{id}/files` once on mount; subsequent updates flow via `workspace_updated` SSE.
- Sidebar slot: integrates into the existing chat right-rail alongside other panels (consistent with CodeExecutionPanel slotting). Tests live alongside (`WorkspacePanel.test.tsx`).
- i18n: Indonesian + English strings via `I18nProvider`. Translation keys: `workspace.title`, `workspace.empty`, `workspace.source.{agent|sandbox|upload}`.

### D-13 — Plan structure (planner anchor)
Suggested atomic plan breakdown for `gsd-plan-phase`:
1. **18-01** Migration `039_workspace_files.sql` — table, RLS, indexes, trigger, `workspace-files` storage bucket, storage RLS. (MIG-02, WS-01)
2. **18-02** `workspace_service.py` — path validator, CRUD helpers, dual-storage routing, structured errors. (WS-03, WS-04)
3. **18-03** Tool registry registrations for `write_file` / `read_file` / `edit_file` / `list_files` + executor wiring in `tool_service.py`. (WS-02, WS-06 read/write semantics)
4. **18-04** REST router `workspace.py` (`GET list`, `GET read+redirect`) + `main.py` mount + `WORKSPACE_ENABLED` flag plumbing. (WS-09)
5. **18-05** Sandbox integration in `sandbox_service.py` — `workspace_files` row insert + SSE queue enqueue. (WS-05)
6. **18-06** SSE `workspace_updated` emission from chat-loop + frontend reducer integration. (WS-10)
7. **18-07** Frontend `WorkspacePanel.tsx` + tests + i18n + sidebar slot wiring. (WS-07, WS-08, WS-11)
8. **18-08** End-to-end pytest covering: write → read → edit → list, RLS isolation between two users, sandbox-generated file appears, binary download via signed URL, path-validation error matrix, 1 MB cap, oversize rejection.

Order: 18-01 → 18-02 → (18-03 ‖ 18-04) → 18-05 → 18-06 → 18-07 → 18-08. Plans 18-03 and 18-04 are independent of each other after the service layer exists.

### D-14 — Test fixtures and golden tests
- pytest unit suite: path validator matrix (every reject case + every accept case).
- pytest integration: workspace service against a test Supabase, checks RLS (User A insert → User B SELECT returns empty), upsert semantics, dual-storage routing.
- pytest API: `tests/api/test_workspace_endpoints.py` covering 200 list, 200 read text, 307 redirect for binary, 404 for missing, 403 for cross-thread access.
- pytest tool dispatch: `tests/tool/test_workspace_tools.py` covering each of the four tools end-to-end with a mocked Supabase client and a real path validator.
- Frontend Vitest: `WorkspacePanel.test.tsx` rendering states (empty, populated, click handler, source-badge variants).

### D-15 — Privacy invariant coverage
- All four workspace tools' RESULTS pass through the existing redaction egress filter at the chat-loop tool-result yield site (no new code; the filter is already wrapped around tool results in `chat.py`).
- File CONTENT itself stored in DB is NOT redacted — that would corrupt user data. Privacy invariant only applies to LLM payloads (egress to cloud LLM), not to at-rest storage. Confirm in plan 18-08 with an explicit test: write a file containing PII, call `read_file`, capture the LLM-bound message, assert it has been anonymized by the registry/egress filter.
- This phase introduces NO new privacy code. Documents the dependency: planner verifies coverage; no implementation work.

### Claude's Discretion
- Inline text-file viewer UX (expand-in-place vs modal) — Claude proposes inline expand within the panel (less context disruption); user can revisit during UAT.
- Source-badge color palette — Claude follows existing zinc/purple design tokens; no design review required for this phase.
- `mime_type` autodetect heuristic for agent-written text files — defaults to `text/markdown`; CSV/JSON detected by extension; everything else `text/plain`.
- Workspace path normalization — case-sensitive (no implicit lowercasing); collapse consecutive `//` to `/` is rejected (paths must already be clean).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source PRD and milestone docs
- `docs/PRD-Agent-Harness.md` §Feature 1.3 (lines 76–110) — workspace feature definition: tools, dual storage, sandbox integration, decoupling, file-path conventions, UI surfaces.
- `docs/PRD-Agent-Harness.md` §Feature 1.7 (lines 162–172) — session persistence model (workspace persisted on every write/edit).
- `docs/PRD-Agent-Harness.md` §Tool surface table (lines 432–436) — official tool names + descriptions.
- `docs/PRD-Agent-Harness.md` §Data model table (lines 444–449) — `workspace_files` table summary.
- `.planning/REQUIREMENTS.md` §WS-* (WS-01..11, MIG-02) — 12 phase-scoped requirements.
- `.planning/ROADMAP.md` §Phase 18 (lines 89–101) — success criteria and dependency declaration.
- `.planning/STATE.md` §Roadmap Snapshot — confirms migration 039 is the planned slot.
- `.planning/milestones/v1.1-ROADMAP.md` — Phase 10 sandbox file flow that we re-engineer.

### Existing code to read before implementing
- `backend/app/services/sandbox_service.py` — primary integration target; `_collect_and_upload_files` (L370–435), `_list_output_files` (L437+), the `_SIGNED_URL_TTL_SECONDS = 3600` constant.
- `backend/app/services/tool_registry.py` — `register()` API + first-write-wins (L80–123); `available` field handling; `_register_tool_search` self-registration pattern.
- `backend/app/services/tool_service.py` — native tool registration pattern; `execute_tool` dispatch.
- `backend/app/routers/chat.py` — SSE event yield pattern (`tool_start` L444–449, `tool_result` L674–679); queue-draining for executor-emitted events (L455+); redaction egress wrapping site.
- `backend/app/services/redaction/egress.py` — egress filter to verify privacy invariant.
- `supabase/migrations/036_code_executions_and_sandbox_outputs.sql` — bucket pattern, 4-segment path RLS template; `sandbox-outputs` bucket creation, INSERT/SELECT/UPDATE/DELETE storage policies.
- `frontend/src/components/chat/CodeExecutionPanel.tsx` — UI pattern reference for the new `WorkspacePanel.tsx` (collapsible, source badges, signed-URL download, glass rule compliance).
- `frontend/src/components/chat/SubAgentPanel.tsx` — secondary pattern reference for sidebar nesting.

### Cross-cutting invariants
- `CLAUDE.md` (project root) — design system rules (no glass on persistent panels), RLS conventions, migrations sequencing rule, ENV-var deploy pattern, PostToolUse hook expectations.
- `.planning/codebase/STRUCTURE.md` — backend/frontend layout (router → service → DB; component slot architecture).
- `.planning/codebase/CONVENTIONS.md` — naming, async style, FastAPI dependencies.
- `.planning/codebase/INTEGRATIONS.md` — Supabase auth client patterns (`get_supabase_authed_client(token)` for RLS, service-role client for system tasks).
- `.planning/milestones/v1.0-REQUIREMENTS.md` §SEC and §PERF — privacy invariant origin and performance targets that constrain workspace reads (sub-100 ms for text).

### Tool-registry decision archive (locked invariants)
- D-P13-01..D-P13-06 (Phase 13 plans, archived) — registration adapter, first-write-wins, catalog formatter cap of 50 tools. Workspace tools must fit within these guardrails.
- D-P15-11..D-P15-12 — `available` flag toggles MCP-attached tools; relevant if `WORKSPACE_ENABLED=False` is implemented as bulk-toggle (we instead choose registration-time gating, see D-08).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`tool_registry.register()`** (`backend/app/services/tool_registry.py:80`) — register the four workspace tools with `source="native"`, `loading="immediate"`. First-write-wins prevents accidental shadowing. Catalog formatter automatically renders into the system prompt.
- **`get_supabase_authed_client(token)`** — already used by every router for RLS-scoped queries; reuse in `workspace.py` router.
- **Supabase Storage 4-segment path + RLS** — copy the policy strings from migration 036. The `sandbox-outputs` bucket has battle-tested SELECT/INSERT/UPDATE/DELETE policies; rename to `workspace-files` for the new bucket.
- **`_SIGNED_URL_TTL_SECONDS = 3600`** (`sandbox_service.py:5–6`) — same TTL constant for binary read endpoint; lift to a shared constant if duplication grows.
- **PII redaction egress filter** (`backend/app/services/redaction/egress.py`) — already wrapped around tool-result yields; workspace tool results inherit coverage with zero new code.
- **`CodeExecutionPanel.tsx` UI primitives** — `Button`, `formatBytes`, status badges, glass-free `bg-card`. The new `WorkspacePanel.tsx` follows the same idiom.
- **`apiFetch`** + i18n provider — used identically.
- **Existing SSE generator queue-drain pattern** (`chat.py:455+`) — sandbox emits via callback into a queue; chat-loop drains between `tool_start` and `tool_result`. Workspace SSE emissions reuse the same queue.

### Established Patterns
- **Migration sequencing.** `/create-migration` skill picks the next free integer; PreToolUse hook blocks edits to applied migrations 001–037. New migration 039 is unblocked.
- **RLS thread-ownership predicate.** `thread_id IN (SELECT id FROM public.threads WHERE user_id = auth.uid()) OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'`. Used in v1.0 entity_registry, v1.1 code_executions; reuse here.
- **Dual storage with discriminator column.** `code_executions.files` is JSONB-flat, but `entity_registry` and proposed `agent_todos` use first-class columns. Workspace follows the latter (typed columns) to enable indexing and CHECK constraints.
- **Tool-result structured errors** (NOT exceptions). Pattern: tool returns `{"error": "code", ...}` so the LLM can adapt without crashing the loop. Extends to all workspace tools.
- **Per-feature env-var kill-switch.** `TOOL_REGISTRY_ENABLED`, `SANDBOX_ENABLED` precedent — `WORKSPACE_ENABLED` follows.

### Integration Points
- **`tool_service.py` registration init** — add four `register(...)` calls in the existing initialization block.
- **`sandbox_service.py:_collect_and_upload_files`** — add a single new call site after upload loop completes: `workspace_service.register_sandbox_files(thread_id, uploaded)`. Logically additive, no signature change.
- **`chat.py` SSE generator** — emit `workspace_updated` events from the same yield discipline as `tool_start` / `tool_result`. The existing redaction-aware buffering wrapper continues to apply.
- **`app/main.py` router mount** — add `app.include_router(workspace.router)`.
- **`frontend/src/hooks/useChatState`** — add `workspaceFiles` slice + reducer for `workspace_updated`. (If state grows, extract to `useWorkspaceState`; auto-decide: keep in `useChatState` for v1.0.)
- **`frontend/src/components/chat/MessageView` / right-rail layout** — slot the new `WorkspacePanel` alongside `CodeExecutionPanel` and `SubAgentPanel`.

</code_context>

<specifics>
## Specific Ideas

- **Path-prefix convention for sandbox files:** sandbox-generated files land at `sandbox/{filename}` (the v1 sandbox does NOT support nested paths — see security note T-10-19 in `sandbox_service.py:387–390` — so single-segment is safe).
- **`workspace-files` is the new private bucket** for non-sandbox binaries; created by migration 039. Follows segment-1-gated 4-segment RLS pattern from `sandbox-outputs`.
- **Inline text viewer**, not modal. Less disruption; aligns with how `CodeExecutionPanel` already uses inline collapsible sections.
- **Tool return shape contract** for binary `read_file`: the LLM is told "binary files cannot be inlined; use `signed_url` to fetch externally" via the tool description. This avoids a follow-up Phase 19 escape-hatch.
- **`updated_at` matters for the panel** — sort-by-most-recent is the default UX; the index on `(thread_id, created_at DESC)` covers list ordering, but the list query orders by `updated_at DESC`. Add a second index on `(thread_id, updated_at DESC)` if EXPLAIN shows a seq scan; deferred to plan-time.

</specifics>

<deferred>
## Deferred Ideas

- **`delete_file` tool** — not in the WS-* requirements; agent has no current need to delete. Deferred to a later phase if a use case emerges.
- **`move_file` / `rename` tool** — same rationale; deferred.
- **File versioning** (history of edits) — not in scope; PRD does not mandate it. If needed, an `audit_trail` row per workspace mutation could be added later.
- **DOCX/PDF upload UI + extraction** — `UPL-01..04` scope, owned by Phase 20.
- **Admin Settings UI for `WORKSPACE_ENABLED`** — env-var only in this phase; admin surfacing aligns with Phase 20's broader v1.3 toggle work.
- **System-settings cache integration** — toggle via `system_settings.workspace_enabled` (60s TTL pattern) — same Phase 20 deferral.
- **Per-bucket size cap for binaries** — sandbox already self-limits; user-upload cap is Phase 20 territory.
- **Workspace garbage-collection** (orphaned storage objects when a row is replaced or thread is deleted) — `ON DELETE CASCADE` removes the DB row but does not evict Storage. Deferred to a maintenance phase or Phase 6-style production hardening.
- **Cross-process advisory lock for write_file/edit_file race conditions** — same async-lock D-31 carryover from v1.0; deferred.
- **Reviewed Todos (not folded):** none — `todo.match-phase` returned 0 matches.

</deferred>

---

*Phase: 18-workspace-virtual-filesystem*
*Context gathered: 2026-05-03*
