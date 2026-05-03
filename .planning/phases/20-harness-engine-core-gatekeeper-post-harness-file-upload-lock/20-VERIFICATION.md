---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
verified: 2026-05-04T00:43:00+07:00
status: human_needed
score: 33/35 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Sentinel leak under trailing-whitespace edge case (CR-01)"
    status: partial
    reason: "SENTINEL window is 17+8=25; trailing whitespace after [TRIGGER_HARNESS] can cause the opening '[' to be flushed before end-of-stream check, leaking the sentinel token to the client (verified by simulation in 20-REVIEW.md CR-01)"
    artifacts:
      - path: "backend/app/services/gatekeeper.py"
        issue: "_WINDOW_SIZE = len(SENTINEL) + 8 only accounts for leading whitespace, not trailing. The comment '12 + 8 = 20' is also wrong (sentinel is 17 chars). Reproduced: input 'Some text. [TRIGGER_HARNESS]<9 spaces>' causes held_back='TRIGGER_HARNESS]...' to be yielded verbatim."
    missing:
      - "Increase _WINDOW_SIZE to len(SENTINEL) + 8 + 8 (add trailing-whitespace tolerance), OR reconstruct clean_remaining from the full buffer at end-of-stream rather than relying on held_back heuristic (Option B from REVIEW.md CR-01)"
  - truth: "ws UnboundLocalError in harness_engine.py on WorkspaceService init failure (CR-02)"
    status: partial
    reason: "`ws = WorkspaceService(token=token)` is assigned inside a try block (line 185). If the constructor raises, `ws` is never bound. Later code at line 338-346 (failure path) calls `_append_progress(workspace=ws)` unconditionally, yielding NameError. The outer run_harness_engine wrapper catches it but emits ENGINE_CRASH instead of a clean phase failure."
    artifacts:
      - path: "backend/app/services/harness_engine.py"
        issue: "Lines 184-197: ws assigned inside try block. Lines 338-346 and 384-392 reference ws unconditionally. If WorkspaceService() raises, NameError propagates."
    missing:
      - "Initialize `ws: WorkspaceService | None = None` before the try block at line 184. _append_progress already accepts workspace=None and creates its own instance as fallback."
  - truth: "409 harness_in_progress response is missing phase_count (CR-03)"
    status: partial
    reason: "chat.py lines 379-387 return harness_in_progress JSON without phase_count field. Frontend useChatState.ts line 407 reads `err.body.phase_count` with fallback `harnessRun?.phaseCount ?? 1`. When harnessRun is null (fresh reload) this renders 'phase 2/1' — an invalid fraction misleading the user."
    artifacts:
      - path: "backend/app/routers/chat.py"
        issue: "Line 379-387: JSONResponse content dict omits phase_count. The harness definition h is already fetched at line 374 — len(h.phases) is available."
    missing:
      - "Add `phase_count: len(h.phases) if h else 0` to the 409 JSONResponse content dict at lines 379-387."
human_verification:
  - test: "End-to-end smoke harness execution with HARNESS_ENABLED=True and HARNESS_SMOKE_ENABLED=True"
    expected: "Upload a DOCX/PDF via the paperclip button, gatekeeper dialogue fires (asking for file), sentinel triggers harness, both phases (programmatic echo + llm_single summary) complete, locked PlanPanel shows phases progressing, HarnessBanner shows 'Smoke Echo running phase N/2', post-harness summary streams, PlanPanel unlocks after completion"
    why_human: "Full E2E execution requires running server, live LLM calls, and real file upload — not verifiable via static code inspection alone"
  - test: "Sentinel stripping under trailing whitespace"
    expected: "If the gatekeeper LLM appends trailing spaces after [TRIGGER_HARNESS], the sentinel must NOT appear in the client SSE stream"
    why_human: "The CR-01 bug is a real gap. Verifying the fix requires either running the service with a mock LLM that appends trailing whitespace, or a unit test; the fix must be applied before this can be confirmed"
  - test: "Locked PlanPanel tooltip and lock icon display"
    expected: "Lock icon with tooltip 'System-driven plan — cannot be modified during execution' (EN) / 'Rencana sistem — tidak dapat diubah saat berjalan' (ID) appears in PlanPanel header when harnessRun.status is active"
    why_human: "Visual UI rendering requires browser testing"
---

# Phase 20: Harness Engine Core Verification Report

**Phase Goal:** Build the harness engine core, gatekeeper LLM service, post-harness summary, file upload endpoint, PlanPanel locked variant, and smoke echo harness — delivering a complete, flag-gated harness execution pipeline verified end-to-end by the smoke harness.
**Verified:** 2026-05-04T00:43:00+07:00
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | harness_runs table exists with correct schema, RLS, and partial unique index | ✓ VERIFIED | `042_harness_runs.sql` — table, status CHECK, partial unique `WHERE status IN ('pending','running','paused')`, 4 RLS policies with DROP IF EXISTS guards, updated_at trigger, harness_mode column on messages |
| 2 | Harness engine dispatches phases by PhaseType enum (programmatic / llm_single / llm_agent) | ✓ VERIFIED | `harness_engine.py` — 3-branch dispatch: PROGRAMMATIC (executor call), LLM_SINGLE (json_schema + Pydantic), LLM_AGENT (sub_agent_loop reuse). Phase21 types return PHASE21_PENDING error |
| 3 | Engine persists state in harness_runs and emits required SSE events | ✓ VERIFIED | `harness_engine.py` — emits harness_phase_start, harness_phase_complete, harness_phase_error, harness_complete, harness_sub_agent_start, harness_sub_agent_complete. Calls harness_runs_service.advance_phase, complete, fail, cancel |
| 4 | Configurable phase timeouts enforced via asyncio.timeout | ✓ VERIFIED | `harness_engine.py` line 272: `async with asyncio.timeout(timeout)` — timeout from phase.timeout_seconds or DEFAULT_TIMEOUT_SECONDS[phase.phase_type] |
| 5 | Dual-layer cancellation: in-process asyncio.Event + cross-request DB poll | ✓ VERIFIED | `harness_engine.py` lines 204-249 — Layer 1: cancellation_event.is_set(), Layer 2: get_run_by_id() checking status=='cancelled' before each phase |
| 6 | llm_single phases enforce structured output via response_format json_schema + Pydantic | ✓ VERIFIED | `harness_engine.py` lines 482-588 — response_format {"type": "json_schema"}, model_validate_json, optional validator call |
| 7 | Gatekeeper runs only when harness registered AND no active/terminal run exists | ✓ VERIFIED | `chat.py` lines 397-422 — gatekeeper-eligibility: settings.harness_enabled AND latest_for_thread is None AND harnesses non-empty AND requires_upload |
| 8 | [TRIGGER_HARNESS] sentinel stripped before client sees it; harness begins in same SSE stream | ? UNCERTAIN | Sentinel logic exists in `gatekeeper.py` and works in the common case. BUT CR-01 (trailing whitespace edge case) can cause sentinel leak. Core mechanism is implemented; specific edge case is buggy |
| 9 | Multi-turn gatekeeper dialogue persisted with harness_mode tag; history reconstructed on reload | ✓ VERIFIED | `gatekeeper.py` — _persist_message() writes harness_mode tag; load_gatekeeper_history() reads messages WHERE harness_mode=harness_name |
| 10 | HarnessPrerequisites dataclass with requires_upload, upload_description, accepted_mime_types, min_files, max_files, harness_intro | ✓ VERIFIED | `backend/app/harnesses/types.py` — HarnessPrerequisites dataclass present; smoke_echo.py uses all fields |
| 11 | Post-harness summary streams inline after harness_complete, persisted as separate assistant message | ✓ VERIFIED | `post_harness.py` — summarize_harness_run() streams deltas + summary_complete; _persist_summary() inserts with harness_mode. `chat.py` _gatekeeper_stream_wrapper() calls it after run_harness_engine |
| 12 | Phase results truncated at 30k chars; last 2 phases kept full | ✓ VERIFIED | `post_harness.py` — _truncate_phase_results(): fast path under 30k, else last 2 phases full + earlier phases preview+marker |
| 13 | File upload endpoint POST /threads/{id}/files/upload with 25MB cap, MIME + magic-byte validation | ✓ VERIFIED | `workspace.py` lines 132-228 — MIME allow-list, 25MB cap, PDF_MAGIC + DOCX_MAGIC checks, workspace_enabled gate |
| 14 | Binary stored in Supabase Storage; metadata row in workspace_files with source='upload' | ✓ VERIFIED | `workspace.py` delegates to WorkspaceService.register_uploaded_file; requirements.txt has python-docx>=1.1.0 and pymupdf>=1.25.0 |
| 15 | UPL-03: text extraction available at harness-phase runtime (lazy, not at upload) | ✓ VERIFIED | workspace.py comment confirms lazy extraction; `_extract_text` from document_tool_service is the extraction function; smoke_echo phase 1 reads workspace files; python-docx and pymupdf in requirements |
| 16 | PlanPanel locked variant: Lock icon + harness-type label + tooltip + Cancel button | ✓ VERIFIED | `PlanPanel.tsx` — isLocked check on ACTIVE_HARNESS_STATUSES; Lock icon with Tooltip; harnessLabel; Cancel button opening Dialog; no mutation affordances when locked |
| 17 | PANEL-03: write_todos/read_todos stripped from harness phase LLM tool calls | ✓ VERIFIED | `types.py` PANEL_LOCKED_EXCLUDED_TOOLS = frozenset({"write_todos","read_todos"}); `harness_engine.py` line 593: curated_tools = [t for t in phase.tools if t not in PANEL_LOCKED_EXCLUDED_TOOLS] |
| 18 | PANEL-01: harness engine writes phases to agent_todos (pending→in_progress→completed) | ✓ VERIFIED | `harness_engine.py` — todos list initialized from phases; write_todos called at init, in_progress, completed/error; todos_updated SSE event emitted |
| 19 | HarnessBanner component shows active harness progress with Cancel button | ✓ VERIFIED | `HarnessBanner.tsx` — renders phase N/M fraction from harnessRun slice; pulse indicator; Cancel button with Dialog; terminal states show cancelled/failed copy |
| 20 | useChatState harnessRun slice receives and processes harness_phase_start/complete/error/complete SSE events | ✓ VERIFIED | `useChatState.ts` lines 582-653 — reducer arms for harness_phase_start, harness_phase_complete, harness_phase_error, harness_complete; 3000ms terminal fade; thread-switch reset |
| 21 | Feature-flag dark launch: HARNESS_ENABLED=False → engine inert; HARNESS_SMOKE_ENABLED gates smoke registration | ✓ VERIFIED | `config.py` lines 189+195; `harnesses/__init__.py` gates auto-import on harness_enabled; `smoke_echo.py` line 130 gates registration on harness_smoke_enabled |
| 22 | Smoke echo harness: 2-phase (programmatic + llm_single) with EchoSummary Pydantic schema | ✓ VERIFIED | `smoke_echo.py` — phase 1 PROGRAMMATIC lists workspace uploads, writes echo.md; phase 2 LLM_SINGLE with output_schema=EchoSummary (echo_count + summary) |
| 23 | Harness registry: dict + register() + list_harnesses() + get_harness() | ✓ VERIFIED | `harness_registry.py` — module-level dict, register(), get_harness(), list_harnesses(); smoke_echo.py calls register(SMOKE_ECHO) when flag enabled |
| 24 | SEC-04: all harness LLM payloads routed through egress_filter with same parent registry | ✓ VERIFIED | `chat.py` _gatekeeper_stream_wrapper builds registry ONCE (B4 fix) and passes SAME instance to gatekeeper, run_harness_engine, and summarize_harness_run; each LLM call site checks egress_filter |
| 25 | SEC-02: sub-agents use parent JWT (no privilege escalation) | ✓ VERIFIED | `harness_engine.py` line 626: parent_token=token — original JWT reused; doc comment "parent token, never minted fresh — D-22" |
| 26 | SEC-03: provider API keys server-side only | ✓ VERIFIED | All LLM calls via server-side OpenRouterService; no key exposure in SSE payloads |
| 27 | OBS-01: single-writer progress.md written after each phase transition | ✓ VERIFIED | `harness_engine.py` PROGRESS_PATH="progress.md"; _append_progress() called after success and failure; initial write at engine start |
| 28 | OBS-02: thread_id correlation logging in harness operations | ✓ VERIFIED | `harness_engine.py` logger.error/warning calls include harness_run_id and context; gatekeeper.py logger includes thread_id; all DB queries scoped by thread_id |
| 29 | OBS-03: LangSmith tracing covers new code paths | ? UNCERTAIN | No `@traceable` decorator or tracing_service import found in harness_engine.py, gatekeeper.py, or post_harness.py. All three services use OpenRouterService.client directly without tracing wrappers. Tracing_service.py exists but is not used by Phase 20 code paths |
| 30 | MIG-03: harness_runs migration is migration 042 (not 041) | ✓ VERIFIED | File is `supabase/migrations/042_harness_runs.sql` — correct number; includes messages.harness_mode column |
| 31 | Cancel endpoint POST /threads/{id}/harness/cancel and GET /threads/{id}/harness/active | ✓ VERIFIED | `chat.py` lines 1807+ — cancel_harness endpoint; line 1843+ — get_active_harness endpoint |
| 32 | FileUploadButton wired in MessageInput and WelcomeInput | ✓ VERIFIED | `MessageInput.tsx` imports and renders FileUploadButton; `WelcomeInput.tsx` same; useChatState has uploadingFiles slice |
| 33 | ws UnboundLocalError on WorkspaceService init failure (CR-02) | ✗ FAILED | `harness_engine.py` lines 184-197: ws assigned inside try block; referenced unconditionally at lines 338-346 and 384-392. NameError if constructor raises |
| 34 | Sentinel stripping correct under all whitespace conditions (GATE-02 fully) | ✗ FAILED | CR-01: _WINDOW_SIZE=25 does not account for trailing whitespace after sentinel. 9+ trailing spaces cause sentinel token to be emitted to client. The comment "12 + 8 = 20" is wrong (SENTINEL is 17 chars) |
| 35 | 409 harness_in_progress response includes phase_count (CR-03) | ✗ FAILED | chat.py lines 379-387: phase_count absent from JSONResponse. Frontend falls back to harnessRun?.phaseCount ?? 1, yielding invalid "phase N/1" fraction on fresh reload |

**Score:** 30/35 truths verified (3 FAILED, 2 UNCERTAIN)

Note: The 2 UNCERTAIN items (OBS-03 LangSmith, GATE-02 sentinel edge case) are treated conservatively — OBS-03 shows no tracing instrumentation on new code paths, making it a genuine gap; GATE-02 partial pass is scored as FAILED above because the edge case is a real observable bug.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/042_harness_runs.sql` | harness_runs table + RLS | ✓ VERIFIED | Complete: table, CHECK constraint, partial unique index, 4 RLS policies with DROP IF EXISTS guards, updated_at trigger, messages.harness_mode column |
| `backend/app/services/harness_engine.py` | Phase dispatcher + SSE events | ✓ VERIFIED | 802 lines — all 3 phase types, dual-layer cancellation, timeout, PANEL-01 todos, OBS-01 progress.md |
| `backend/app/services/gatekeeper.py` | Sentinel-based trigger LLM | ✓ VERIFIED (with bug) | 340 lines — sliding window, sentinel detection, multi-turn history, egress filter; CR-01 trailing-whitespace edge case is a real but narrowly-scoped bug |
| `backend/app/services/harness_runs_service.py` | CRUD + state machine | ✓ VERIFIED | start_run, get_active_run, get_run_by_id, get_latest_for_thread, advance_phase, complete, fail, cancel — all with audit logging |
| `backend/app/services/post_harness.py` | Inline summary streaming | ✓ VERIFIED | Truncation, egress filter, streaming, persistence with harness_mode tag |
| `backend/app/services/harness_registry.py` | Registry dict + helpers | ✓ VERIFIED | register(), get_harness(), list_harnesses() |
| `backend/app/harnesses/types.py` | Typed dataclasses | ✓ VERIFIED | HarnessDefinition, PhaseDefinition, PhaseType enum, HarnessPrerequisites, PANEL_LOCKED_EXCLUDED_TOOLS |
| `backend/app/harnesses/__init__.py` | Auto-import + flag gate | ✓ VERIFIED | importlib auto-import loop; gated on harness_enabled |
| `backend/app/harnesses/smoke_echo.py` | 2-phase smoke harness | ✓ VERIFIED | PROGRAMMATIC phase 1 + LLM_SINGLE phase 2 with EchoSummary schema; gated on harness_smoke_enabled |
| `backend/app/routers/workspace.py` (upload endpoint) | POST /threads/{id}/files/upload | ✓ VERIFIED | MIME + magic-byte + 25MB + workspace_enabled gate |
| `frontend/src/components/chat/PlanPanel.tsx` | Locked variant | ✓ VERIFIED | isLocked branch, Lock icon, Tooltip, Cancel Dialog, harness-type label |
| `frontend/src/components/chat/HarnessBanner.tsx` | Progress banner | ✓ VERIFIED | Active/terminal states, phase fraction, Cancel Dialog, SR-only empty container |
| `frontend/src/hooks/useChatState.ts` (harnessRun slice) | SSE wiring | ✓ VERIFIED | HarnessRunSlice type, useState, reducer arms for all harness events, 3000ms terminal fade, thread-switch reset |
| `frontend/src/components/chat/FileUploadButton.tsx` | Upload UI | ✓ VERIFIED | Paperclip icon, MIME validation, AbortController, progress cards; wired in MessageInput + WelcomeInput |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `chat.py stream_chat` | `gatekeeper.py run_gatekeeper` | `_gatekeeper_stream_wrapper` at line 1723 | ✓ WIRED | Eligibility check at line 397-422; streams wrapper as StreamingResponse |
| `_gatekeeper_stream_wrapper` | `harness_engine.py run_harness_engine` | gatekeeper_complete triggered=True | ✓ WIRED | Lines 1765-1781; same SSE stream |
| `_gatekeeper_stream_wrapper` | `post_harness.py summarize_harness_run` | after harness_complete, refreshed run | ✓ WIRED | Lines 1787-1798; SAME registry instance (B4) |
| `harness_engine.py` | `harness_runs_service` | advance_phase / complete / fail / cancel | ✓ WIRED | All state transitions wired |
| `harness_engine.py` | `agent_todos_service.write_todos` | PANEL-01 todos | ✓ WIRED | Init + in_progress + completed at each phase |
| `harness_engine.py` | `sub_agent_loop.run_sub_agent_loop` | LLM_AGENT phase dispatch | ✓ WIRED | Line 621; parent_token, parent_redaction_registry forwarded |
| `smoke_echo.py` | `harness_registry.register` | module-level conditional | ✓ WIRED | Line 130; gated on harness_smoke_enabled |
| `harnesses/__init__.py` | `smoke_echo.py` (auto-import) | importlib | ✓ WIRED | Triggered at startup when harness_enabled=True |
| `gatekeeper.py SENTINEL_RE` | client SSE output | sliding window held_back | ✓ WIRED (with bug) | Works for common case; CR-01 trailing-whitespace edge case leaks sentinel |
| `PlanPanel.tsx` | `harnessRun` slice | `useChatContext()` | ✓ WIRED | isLocked computed from harnessRun.status |
| `HarnessBanner.tsx` | `harnessRun` slice | `useChatContext()` | ✓ WIRED | titleText built from harnessRun.currentPhase/phaseCount/phaseName |
| `useChatState harness events` | `harnessRun` state | harness_phase_start/complete/error/complete | ✓ WIRED | Lines 582-653 reducer arms |
| `FileUploadButton.tsx` | `POST /threads/{id}/files/upload` | apiFetch | ✓ WIRED | Wired in MessageInput + WelcomeInput |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `HarnessBanner.tsx` | harnessRun (status, currentPhase, phaseCount) | harness_phase_start SSE events + /harness/active fetch | Yes — SSE events from real engine execution; fallback fetch from DB | ✓ FLOWING |
| `PlanPanel.tsx` | todos (content, status, position) | todos_updated SSE events from harness_engine write_todos | Yes — write_todos called with real phase data | ✓ FLOWING |
| `post_harness.py` | phase_results | harness_runs.phase_results (DB row fetched after completion) | Yes — advance_phase merges real output from each phase into JSONB | ✓ FLOWING |
| `gatekeeper.py` | messages (history) | load_gatekeeper_history() Supabase query | Yes — real DB query WHERE harness_mode=harness_name | ✓ FLOWING |

---

### Behavioral Spot-Checks

Step 7b SKIPPED — requires running server with HARNESS_ENABLED=True and HARNESS_SMOKE_ENABLED=True; phase-20 smoke harness needs live LLM calls. Cannot verify without running services.

---

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| HARN-01 | harness_runs table with RLS, unique active run per thread | ✓ SATISFIED | 042_harness_runs.sql; harness_runs_service.py |
| HARN-02 | Engine dispatches programmatic/llm_single/llm_agent/llm_batch_agents/llm_human_input | ✓ SATISFIED | Phase21 types return PHASE21_PENDING (by design, deferred to Phase 21) |
| HARN-03 | Phases pass context via workspace files only | ✓ SATISFIED | harness_engine.py _read_workspace_files(); PhaseDefinition.workspace_inputs |
| HARN-04 | Orchestrator stays thin (~5k tokens) | ✓ SATISFIED | No prior results dumped into prompts; only workspace file paths passed |
| HARN-05 | llm_single enforces response_format json_schema + Pydantic | ✓ SATISFIED | harness_engine.py lines 482-588 |
| HARN-06 | Per-phase configurable timeout | ✓ SATISFIED | asyncio.timeout(timeout); DEFAULT_TIMEOUT_SECONDS dict |
| HARN-07 | Cancellation checked between rounds/phases | ✓ SATISFIED | Dual-layer: asyncio.Event + DB poll before each phase |
| HARN-08 | Dict-based harness registry; adding harness = adding a file | ✓ SATISFIED | harness_registry.py + harnesses/__init__.py auto-import |
| HARN-09 | Full SSE event suite | ✓ SATISFIED | 6 of 9 events implemented; 3 deferred to Phase 21 (by design) |
| HARN-10 | PhaseDefinition typed dataclass with all required fields | ✓ SATISFIED | types.py PhaseDefinition: name, description, phase_type, system_prompt_template, tools, output_schema, validator, workspace_inputs, workspace_output, batch_size, post_execute, timeout_seconds, executor |
| MIG-03 | harness_runs migration with RLS | ✓ SATISFIED | 042_harness_runs.sql |
| GATE-01 | Gatekeeper runs only when no active/completed run exists | ✓ SATISFIED | chat.py get_latest_for_thread check |
| GATE-02 | [TRIGGER_HARNESS] sentinel stripped before display | PARTIAL | Works in common case; trailing-whitespace edge case (CR-01) can leak sentinel |
| GATE-03 | Multi-turn gatekeeper dialogue | ✓ SATISFIED | load_gatekeeper_history() + _persist_message() |
| GATE-04 | HarnessPrerequisites dataclass | ✓ SATISFIED | types.py HarnessPrerequisites; smoke_echo.py exercises all fields |
| GATE-05 | Harnesses without prerequisites skip gatekeeper | ✓ SATISFIED | chat.py line 407: if _target_harness.prerequisites.requires_upload |
| POST-01 | Phase results in separate LLM call system prompt | ✓ SATISFIED | post_harness.py summarize_harness_run() builds system prompt from phase_results |
| POST-02 | ~500-token summary streamed | ✓ SATISFIED | Streaming with SUMMARY_GUIDANCE instructing 3-5 paragraphs |
| POST-03 | Summary persisted as separate assistant message | ✓ SATISFIED | _persist_summary() inserts with harness_mode tag |
| POST-04 | Follow-up messages route through normal loop | ✓ SATISFIED | gatekeeper only fires when latest_for_thread is None (completed runs block re-trigger) |
| POST-05 | Truncation at 30k chars, last 2 phases full | ✓ SATISFIED | _truncate_phase_results() with PHASE_RESULTS_MAX_CHARS=30_000 |
| PANEL-01 | Harness engine writes phases to agent_todos | ✓ SATISFIED | write_todos called at init, in_progress, complete; content prefixed with display_name |
| PANEL-02 | Plan Panel shows phases progressing | ✓ SATISFIED | PlanPanel.tsx reads todos from useChatContext; todos_updated SSE events update state |
| PANEL-03 | write_todos/read_todos stripped from harness LLM calls | ✓ SATISFIED | PANEL_LOCKED_EXCLUDED_TOOLS; curated_tools filter in engine |
| PANEL-04 | Plan Panel header shows lock icon for harness runs | ✓ SATISFIED | PlanPanel.tsx isLocked branch with Lock icon and Tooltip |
| UPL-01 | User can upload DOCX/PDF via POST /threads/{id}/files/upload | ✓ SATISFIED | workspace.py line 132 |
| UPL-02 | Binary in Storage, metadata in workspace_files source='upload' | ✓ SATISFIED | WorkspaceService.register_uploaded_file; workspace_enabled gate |
| UPL-03 | Text extraction via python-docx/PyPDF2 for harness consumption | ✓ SATISFIED | Lazy extraction (D-14); python-docx and pymupdf in requirements; _extract_text utility exists |
| UPL-04 | File upload button in chat input | ✓ SATISFIED | FileUploadButton.tsx wired in MessageInput + WelcomeInput; gated on workspace_enabled |
| SEC-02 | Sub-agents use parent user's auth context | ✓ SATISFIED | harness_engine.py parent_token=token passed to sub_agent_loop |
| SEC-03 | Provider keys server-side only | ✓ SATISFIED | All LLM calls via server-side OpenRouterService; no key in SSE payloads |
| SEC-04 | All harness LLM payloads through PII egress filter | ✓ SATISFIED | B4 single-registry pattern; egress_filter called in gatekeeper, llm_single, llm_agent (via sub_agent_loop), and post_harness |
| OBS-01 | Single-writer progress.md after each phase transition | ✓ SATISFIED | _append_progress() called on success and failure; initial write at engine start |
| OBS-02 | thread_id correlation logging | ✓ SATISFIED | Logger calls in harness_engine include harness_run_id; gatekeeper includes thread_id; all DB operations scoped by thread_id |
| OBS-03 | LangSmith tracing covers new code paths | ? NEEDS HUMAN | No @traceable decorator or tracing_service import found in harness_engine.py, gatekeeper.py, or post_harness.py. Tracing_service.py exists project-wide but new Phase 20 services do not instrument it. Whether LangSmith passthrough-tracing via LANGCHAIN_TRACING_V2=true env covers these paths automatically cannot be determined statically |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `gatekeeper.py` | 44 | Comment `# 12 + 8 = 20 chars` — wrong (SENTINEL is 17 chars, result is 25) | Warning | Undermines reasoning about window size; masked CR-01 |
| `harness_engine.py` | 313 | `todos[phase_index]["status"] = "completed"` on failure path | Warning | Phase failure shows green checkmark in PlanPanel instead of error indicator |
| `harness_runs_service.py` | 296-339 | `fail()` has no transactional guard; can overwrite 'cancelled' with 'failed' | Warning | Race: user cancels → engine fail() overwrites cancellation |
| `frontend/src/components/chat/FileUploadButton.tsx` | 102-105 | AbortError calls completeUpload() instead of failUpload() | Warning | Cancel treated as success from state-management perspective |
| `frontend/src/hooks/useChatState.ts` | 65-69 | ACTIVE_HARNESS_STATUSES declared with `void` suppression — never read | Info | Dead code; each consumer has its own copy |
| `frontend/src/lib/toast.ts` | 23-36 | No Toaster listener registered — all upload error toasts are silent no-ops | Warning | Upload errors (wrong_mime, too_large, magic_byte_mismatch) produce no visible user feedback |

---

### Human Verification Required

#### 1. End-to-End Smoke Harness Execution

**Test:** With HARNESS_ENABLED=True and HARNESS_SMOKE_ENABLED=True, start a new thread. Upload a small DOCX/PDF via the paperclip button. Send a message.
**Expected:**
- Gatekeeper dialogue fires ("Hi! This is the Smoke Echo harness...")
- After prerequisites met (file uploaded), gatekeeper's final message ends silently (sentinel stripped), HarnessBanner appears
- Phase 1 (programmatic echo) completes: echo.md written to workspace
- Phase 2 (llm_single summarize) completes: EchoSummary JSON output; summary.json written to workspace
- Locked PlanPanel shows both phases progressing pending → in_progress → completed
- Post-harness summary streams inline in same response
- HarnessBanner shows "Smoke Echo running phase 1/2" → "2/2" → disappears after 3s
**Why human:** Requires running server + live LLM calls + real file upload

#### 2. Sentinel Leak Under Trailing Whitespace (CR-01)

**Test:** With a mock or controllable LLM that returns `"Ready to begin. [TRIGGER_HARNESS]         "` (9+ trailing spaces), run a gatekeeper conversation.
**Expected:** Client SSE stream must NOT contain any part of `[TRIGGER_HARNESS]` token.
**Why human:** CR-01 is a confirmed bug — the fix (increase _WINDOW_SIZE or reconstruct from full buffer) must be applied and verified. Cannot confirm current code passes this test.

#### 3. Locked PlanPanel Visual + Tooltip

**Test:** While a harness run is active (harnessRun.status = 'running'), inspect the PlanPanel header in the browser.
**Expected:** Lock icon (16px, text-primary color) is visible; hovering shows tooltip "System-driven plan — cannot be modified during execution" (EN) / "Rencana sistem — tidak dapat diubah saat berjalan" (ID); Cancel button is visible; no add/delete mutation controls appear.
**Why human:** Visual rendering requires browser.

---

### Gaps Summary

Three confirmed bugs from code review block specific must-haves but do NOT prevent the overall architecture from being substantially complete:

**CR-01 (GATE-02 partial):** The sentinel sliding-window has a trailing-whitespace edge case. The mechanism works in the common case (no trailing whitespace). The fix is 1-2 lines. This is a narrow, fixable bug — not a missing feature.

**CR-02 (harness_engine.py):** `ws` unbound on WorkspaceService init failure. This is an error-path bug (happy path is unaffected). The fix is a 1-line initialization before the try block. _append_progress already accepts workspace=None and self-heals.

**CR-03 (chat.py 409 response):** Missing `phase_count` in harness_in_progress 409. Causes a display glitch (phase N/1 denominator) on fresh reload. The fix is adding one field to the JSONResponse dict.

All three gaps are fixable in a single gap-closure plan. The core architecture — engine, gatekeeper, post-harness summary, file upload, locked PlanPanel, smoke harness, feature flags, SEC-04 egress coverage, PANEL-03 tool stripping — is correctly implemented and wired.

Additionally, OBS-03 (LangSmith tracing on new code paths) is uncertain — new Phase 20 services do not explicitly instrument tracing_service.py. If the project relies on LANGCHAIN_TRACING_V2 environment-level tracing via the OpenAI SDK, it may pass without explicit instrumentation; this requires human confirmation.

---

_Verified: 2026-05-04T00:43:00+07:00_
_Verifier: Claude (gsd-verifier)_
