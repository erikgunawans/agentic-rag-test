# Phase 18: Workspace Virtual Filesystem - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 18-workspace-virtual-filesystem
**Mode:** `--auto` (autonomous; no interactive prompts; recommended option auto-selected per project defaults)
**Areas discussed:** Migration ordering, Schema shape, RLS scope, Storage bucket strategy, Path validation, Text size limit, Tool surface, Feature-flag strategy, REST endpoint contract, SSE event taxonomy, Sandbox re-engineering, Frontend panel pattern, Plan structure, Test fixtures, Privacy invariant coverage

---

## Migration Ordering

| Option | Description | Selected |
|--------|-------------|----------|
| 038 | Take 038 — assumes Phase 17 hasn't claimed it yet | |
| 039 | Take 039 — Phase 17 is expected to own 038/041 per STATE.md plan | ✓ |
| Defer numbering to execute-phase | Pick at apply time | |

**Auto-selection:** `039` per STATE.md migration plan (line 53–57). Plan must include a collision check at execute-phase time in case Phase 17 takes 039 first.
**Notes:** STATE.md explicitly enumerates 038=`agent_todos`, 039=`workspace_files`, 040=`harness_runs`, 041=`messages.deep_mode|harness_mode`.

---

## Table Schema Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single `data JSONB` column | Loose schema; flexible but unindexed | |
| Typed columns + CHECK constraints | First-class typed columns matching PRD; CHECK ensures exactly one of content/storage_path | ✓ |
| Two tables (text + binary) | Strict separation; complicates upsert | |

**Auto-selection:** Typed columns. Aligned with `code_executions` (Phase 10) and `entity_registry` (Phase 2) precedent.
**Notes:** Added `storage_bucket text` discriminator so service layer doesn't path-sniff.

---

## RLS Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Per-row `user_id` | Add `user_id` column and gate on it | |
| Thread-ownership predicate via subquery on `threads` | Matches REQUIREMENTS WS-01 phrasing and v1.0/v1.1 pattern | ✓ |
| Service-role only | Bypass RLS, enforce in service layer | |

**Auto-selection:** Thread-ownership predicate. Mirrors `entity_registry`, `code_executions`, etc. Lets sub-agents share the workspace transparently — RLS is on thread, not caller.

---

## Storage Bucket Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Single new `workspace-files` bucket; migrate sandbox files into it | Cleaner; one bucket; backfill required | |
| Reuse `sandbox-outputs` for sandbox + new `workspace-files` for agent/upload; track per-row via `storage_bucket` column | Backward-compat; zero migration of existing storage objects; service is bucket-aware | ✓ |
| One bucket per source type | Three buckets total — overkill | |

**Auto-selection:** Two buckets with discriminator column. Honors backward compatibility hint in user instructions; avoids storage migration; bucket-aware service.

---

## Path Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Service-layer only | Single source of truth; flexible | |
| Service-layer (primary) + DB CHECK (defense-in-depth) | Belt-and-braces; catches direct table inserts | ✓ |
| DB CHECK only | Hard to evolve | |

**Auto-selection:** Both. Service raises `WorkspaceValidationError` → tool dispatch returns structured error (no exception; LLM can recover).

---

## Text Content Cap

| Option | Description | Selected |
|--------|-------------|----------|
| 256 KB | Conservative | |
| 1 MB | Per WS-03 PRD wording | ✓ |
| 4 MB | Generous; risks DB row bloat | |

**Auto-selection:** 1 MB per requirement WS-03.

---

## Tool Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Three tools (write, read, list) — derive edit via write | Less surface; less power | |
| Four tools (write, read, edit, list) — explicit edit_file with exact-string replace | Per PRD; matches Anthropic pattern; lower token cost for edits | ✓ |
| Six+ tools (incl. delete, move) | Beyond scope | |

**Auto-selection:** Four tools. Per WS-02 + PRD §Feature 1.3.

---

## Feature-Flag Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| No flag — always on | Simplest; no kill-switch | |
| Env-var `WORKSPACE_ENABLED=True` default + admin UI toggle | UI scope creep; defer admin surface | |
| Env-var `WORKSPACE_ENABLED=True` default; no UI in this phase | Kill-switch only; admin UI deferred to Phase 20 | ✓ |

**Auto-selection:** Env-var with True default; no admin UI in this phase. Matches `TOOL_REGISTRY_ENABLED` / `SANDBOX_ENABLED` precedent.

---

## REST Endpoint Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Single endpoint with operation in payload | RPC-style | |
| Two endpoints: list + read; binary returns 307 to signed URL | RESTful; matches PRD §UI lines 110 | ✓ |
| Three endpoints: list + read-text + read-binary | Splits binary discovery | |

**Auto-selection:** Two endpoints; binary returns 307 redirect to a 1-hour signed URL.

---

## SSE Event Taxonomy

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse generic `tool_result` events | Minimal | |
| New `workspace_updated` event with `{operation, file_path, source}` payload | Per WS-10; lets panel update in real time without re-listing | ✓ |
| Per-operation events (`workspace_created`, `workspace_edited`) | Verbose | |

**Auto-selection:** Single `workspace_updated` event with discriminating `operation` field.

---

## Sandbox Re-Engineering

| Option | Description | Selected |
|--------|-------------|----------|
| Backfill all old `code_executions.files` into `workspace_files` | Migration-heavy; touches existing data | |
| Forward-only: every NEW sandbox execution writes a `workspace_files` row referencing the same `sandbox-outputs` storage path | Simple; backward-compat; deferred backfill if ever needed | ✓ |
| Replace `tool_result.output.files` with workspace lookup | Frontend regression risk | |

**Auto-selection:** Forward-only. Existing `tool_result.output.files` shape preserved → `CodeExecutionPanel.tsx` keeps working unchanged.

---

## Frontend Panel Pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Modal-based file viewer | Popup; disrupts chat | |
| Sidebar collapsible panel mirroring `CodeExecutionPanel.tsx` (inline expand for text, download for binary) | Consistent with existing chat UI; glass-rule compliant | ✓ |
| Standalone page route | Out of conversation context | |

**Auto-selection:** Sidebar panel mirroring `CodeExecutionPanel.tsx`.

---

## Plan Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Monolithic single plan | Hard to verify | |
| Eight atomic plans by surface (migration → service → tools ‖ router → sandbox → SSE → UI → e2e) | Matches phase complexity; allows TDD per surface | ✓ |
| Twelve micro-plans | Over-decomposed | |

**Auto-selection:** Eight atomic plans (see CONTEXT.md D-13).

---

## Test Fixture Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Tool-dispatch unit tests only | Insufficient for migration / RLS confidence | |
| Layered: unit (validator) + service (RLS) + API (endpoints) + tool (dispatch) + frontend (Vitest panel) | Full pyramid; matches v1.0–v1.2 standard | ✓ |
| Manual UAT only | Skips regression coverage | |

**Auto-selection:** Layered pyramid.

---

## Privacy Invariant Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Add new redaction code in workspace tools | Duplication; risk of drift | |
| Inherit existing chat-loop egress filter (already wraps tool results) — no new code; verify with explicit test | Zero new privacy code; explicit test | ✓ |
| Encrypt content at rest | Out of scope; deferred to compliance phase | |

**Auto-selection:** Inherit existing filter; explicit verification test in plan 18-08.

---

## Claude's Discretion

- Inline text-file viewer UX (expand-in-place vs modal) — Claude chose inline expand within the panel; user can revisit during UAT.
- Source-badge color palette — follow existing zinc/purple design tokens.
- `mime_type` autodetect heuristic — `text/markdown` default; CSV/JSON via extension; everything else `text/plain`.
- Path normalization rules beyond WS-03 — case-sensitive (no implicit lowercasing), reject `//` (paths must be pre-cleaned), reject control characters.

## Deferred Ideas

- `delete_file` tool — no current WS-* requirement; defer.
- `move_file` / rename tool — defer.
- File versioning — out of scope.
- DOCX/PDF upload UI + extraction — `UPL-01..04` lives in Phase 20.
- Admin Settings UI surface for `WORKSPACE_ENABLED` — Phase 20 broader toggle work.
- `system_settings.workspace_enabled` cache integration (60s TTL) — Phase 20.
- Per-bucket size cap for binaries — Phase 20 (file upload).
- Workspace garbage-collection on row replacement — defer to maintenance / Phase 6-style hardening.
- Cross-process advisory lock for `write_file`/`edit_file` race conditions — D-31 carryover; defer.
- Backfill of historical `code_executions.files` rows into `workspace_files` — defer until a use case emerges.
