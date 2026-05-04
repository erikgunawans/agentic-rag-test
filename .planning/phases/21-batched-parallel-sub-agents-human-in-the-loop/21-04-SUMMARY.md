---
phase: 21-batched-parallel-sub-agents-human-in-the-loop
plan: 04
subsystem: chat-router
tags: [hil, harness, sse, chat, router, resume, b4-registry, blocker-2]
requires:
  - 21-02  # harness_runs_service.resume_from_pause + start_phase_index engine signature + paused-terminal handler
  - 20-*   # Phase 20 chat.py 409 block + _gatekeeper_stream_wrapper + _get_or_build_conversation_registry
provides:
  - "_resume_harness_engine_sse(...) — NEW SSE wrapper near chat.py:1724 that calls run_harness_engine(start_phase_index=N+1) with a registry loaded once via _get_or_build_conversation_registry (B4 invariant)"
  - "HIL resume branch at stream_chat entry — handles paused harness runs (workspace write → resume_from_pause → SSE) BEFORE the 409 block"
  - "409 block condition narrowed to ('pending', 'running') — paused rows fall through to HIL resume"
  - "messages.harness_mode tagging on HIL user replies — preserves Q→A history reconstruction"
affects:
  - backend/app/routers/chat.py
tech-stack:
  added: []
  patterns:
    - "B4 single-registry invariant — registry loaded once per request via _get_or_build_conversation_registry; egress filter wraps all subsequent LLM calls (SEC-04)"
    - "Stale-state guard pattern — resume_from_pause returns None when row is no longer paused; surface as 500 hil_resume_state_invalid (race-safe)"
    - "harness_mode message tagging convention (mirrors post_harness:150-155) for HIL user replies"
    - "WorkspaceService.write_text_file with source='harness' for HIL answer persistence"
key-files:
  created:
    - backend/tests/routers/test_chat_hil_resume.py    # 7 router tests (10 collected with parametrize)
  modified:
    - backend/app/routers/chat.py                       # +imports, +HIL resume branch, +_resume_harness_engine_sse, narrowed 409
decisions:
  - "Used harness_runs_service.resume_from_pause (NOT advance_phase) for the paused → running transition. advance_phase guards `.in_(\"status\", [\"pending\", \"running\"])` and would silently reject paused rows (BLOCKER-2). resume_from_pause's `.in_(\"status\", [\"paused\"])` guard is the correct path."
  - "Stale-state guard returns 500 with `hil_resume_state_invalid` when resume_from_pause returns None — surfaces the rare race where the row was cancelled or terminal'd between get_active_run and resume_from_pause. run_harness_engine MUST NOT be invoked in this branch (regression test 7 covers)."
  - "_resume_harness_engine_sse loads registry exactly once via _get_or_build_conversation_registry — B4 invariant preserved. The egress filter (SEC-04) wraps all subsequent LLM calls in run_harness_engine just as in _gatekeeper_stream_wrapper."
  - "HIL resume branch placed BEFORE the 409 block so paused falls through to resume rather than triggering a stale 409. Order at stream_chat entry: (1) Phase 19 ask_user resume → (2) NEW Phase 21 HIL resume → (3) 409 block (now only blocks pending/running) → (4) gatekeeper eligibility → (5) standard/deep dispatch."
  - "User reply persisted to messages with harness_mode=harness_type (NOT harness.name) — uses the literal harness type string from paused_run, consistent with how post_harness tags messages and what the frontend reducer keys on."
  - "WorkspaceService and get_supabase_authed_client added at module top-level imports so tests can patch app.routers.chat.WorkspaceService cleanly (mirrors run_sub_agent_loop / harness_runs_service module-level import pattern)."
metrics:
  start: "2026-05-04T07:51:00Z"
  end: "2026-05-04T07:55:00Z"
  duration_seconds: 240
  tasks_completed: 1
  files_modified: 1
  files_created: 1
  tests_added: 7         # 7 distinct test functions; 10 cases collected (parametrize × 4 on test 6)
  tests_pre_existing: 14  # test_chat_harness_routing.py (no regression)
  tests_total_green: 24
---

# Phase 21 Plan 04: Chat HIL Resume Branch + 409 Fix Summary

The chat router now wires the HIL resume flow that makes HIL-04 observable end-to-end. Three surgical edits to `backend/app/routers/chat.py`: (1) the 409 conflict block now only blocks `pending` and `running` (not `paused`); (2) a NEW `_resume_harness_engine_sse` helper near `_gatekeeper_stream_wrapper` (line 1724) wraps `run_harness_engine(start_phase_index=...)` with SSE serialization while reusing the existing `_get_or_build_conversation_registry` (line 1695) for B4 single-registry invariance; (3) a NEW HIL resume branch inserted BEFORE the 409 block drives the user's reply through workspace write → `harness_runs_service.resume_from_pause` (NOT `advance_phase` — BLOCKER-2 fix) → `_resume_harness_engine_sse`.

Without this branch, a paused harness saw the user's reply but the engine never resumed — the run sat forever at `status='paused'`. With it, the user reply produces an SSE stream that resumes the engine from `current_phase + 1`, with the answer persisted in both workspace (`phase.workspace_output`) and `messages` table (with `harness_mode` tag), partial results in `phase_results`, and the registry loaded once via `_get_or_build_conversation_registry`. 409 still blocks pending/running but no longer blocks paused. Race-safe via the resume_from_pause return-value check.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | _resume_harness_engine_sse helper + HIL resume branch + 409 condition change + 7 FastAPI TestClient tests (RED → GREEN) | `c3fcbc9` | `backend/app/routers/chat.py`, `backend/tests/routers/test_chat_hil_resume.py` |

## Verification

```
cd backend && pytest tests/routers/test_chat_hil_resume.py tests/routers/test_chat_harness_routing.py
```

Result: **24 passed** (10 new + 14 pre-existing).

Backend import smoke test: `python -c "from app.main import app; print('OK')"` → OK.

Wider router suite: `pytest tests/routers/` → **81 passed** (no regression).

Harness service suite: `pytest tests/services/test_harness_runs_service.py tests/services/test_harness_runs_service_pause.py tests/services/test_harness_engine.py tests/services/test_harness_engine_human_input.py` → **39 passed**.

## Acceptance-Criteria Grep

| Pattern | Expected | Got |
|---------|----------|-----|
| `Phase 21 / D-01, D-02: HIL resume detection` | 1 | 1 |
| `paused_run.get("status") == "paused"` | 1 | 1 |
| `active_harness.get("status") in ("pending", "running")` | 1 | 1 |
| `def _resume_harness_engine_sse` | 1 | 1 |
| `_resume_harness_engine_sse` (def + invocation) | ≥2 | 3 |
| `_get_or_build_conversation_registry` (def + reuse) | ≥2 | 7 |
| `_load_conversation_registry\|_load_parent_registry` (must be 0) | 0 | 0 |
| `harness_runs_service\.resume_from_pause` | ≥1 | 1 |
| `hil_resume_state_invalid` | ≥1 | 1 |
| `start_phase_index=current_phase_idx + 1` | 1 | 1 |
| `"harness_mode": harness_type` | ≥1 | 1 |

All 11 acceptance criteria pass.

## Tests Added

7 distinct test functions in `backend/tests/routers/test_chat_hil_resume.py` (10 test cases collected after parametrize × 4 on test 6):

1. **test_hil_resume_detects_paused_status** — paused row triggers SSE (200) + `text/event-stream`, NOT 409. Asserts `resume_from_pause` awaited; `advance_phase` NOT called (BLOCKER-2 regression).
2. **test_hil_resume_writes_answer_to_workspace** — `WorkspaceService(token="tok")` instantiated and `write_text_file` awaited with `thread_id="thread-1"`, `file_path="test-answer.md"`, `content="Test answer 123"`, `source="harness"`.
3. **test_hil_resume_calls_resume_from_pause_with_next_index** — `resume_from_pause` invoked with `run_id="run-1"`, `new_phase_index=3` (current 2 + 1), `phase_results_patch["2"]["phase_name"]="ask-label"`, `output.answer="Test answer 123"`. `advance_phase` NEVER called.
4. **test_hil_resume_calls_run_harness_engine_with_start_phase_index** — `run_harness_engine` awaited with `start_phase_index=3`, `harness_run_id="run-1"`, `thread_id="thread-1"`.
5. **test_hil_resume_persists_user_message_with_harness_mode** — `messages` insert payload contains `role="user"`, `content="Test answer 123"`, `harness_mode="smoke-echo"`.
6. **test_409_only_blocks_pending_running** — parametrized `(pending → 409, running → 409, paused → 200, None → 200)`. Confirms paused falls through and missing row falls through.
7. **test_hil_resume_returns_500_when_resume_from_pause_returns_none** — stale-state guard surfaces 500 with `hil_resume_state_invalid`. `run_harness_engine` MUST NOT be invoked (assertion: `engine_invoked["called"] is False`).

## SSE Event Contract — HIL Resume Flow

```
[user POSTs body.message to paused thread]

# In stream_chat (chat.py):
HIL resume detection
  → WorkspaceService.write_text_file(thread_id, phase.workspace_output, body.message, source="harness")
  → messages.insert({role: "user", content: body.message, harness_mode: harness_type, ...})
  → harness_runs_service.resume_from_pause(run_id, new_phase_index=N+1, phase_results_patch={...})
     ├─ updated_row is not None  →  StreamingResponse(_resume_harness_engine_sse(...))
     │                                ├─ _get_or_build_conversation_registry(thread_id, sys_settings)
     │                                ├─ async for ev in run_harness_engine(start_phase_index=N+1, ...):
     │                                │    yield f"data: {json.dumps(ev)}\n\n"
     │                                └─ yield f"data: {json.dumps({'type': 'done'})}\n\n"
     └─ updated_row is None      →  500 JSONResponse {error: "hil_resume_state_invalid", ...}
```

## Threat-Model Mitigations Implemented

| Threat ID | Disposition | Implementation |
|-----------|-------------|----------------|
| T-21-04-01 (Spoofing — non-owner resume) | mitigate | `get_active_run` is RLS-scoped via `get_supabase_authed_client(user["token"])`; user_id implicit via JWT; forged thread_ids return None and fall through to 409/normal flow. |
| T-21-04-02 (Tampering — path traversal via workspace_output) | mitigate | `WorkspaceService.write_text_file` calls `validate_workspace_path` before write; rejects `../` traversal. Workspace_output is developer-defined in `PhaseDefinition`, not user input. |
| T-21-04-03 (DoS — spam paused thread) | mitigate | First call advances `current_phase` and flips status to `running` via resume_from_pause's transactional guard; second message arrives at status='running' and either falls into the 409 block or normal flow. resume_from_pause's `.in_("status", ["paused"])` rejects double-resume — no infinite loop. |
| T-21-04-04 (Repudiation — who replied?) | mitigate | messages insert records `user_id` from JWT and `harness_mode=harness_type`; resume_from_pause emits `audit_service.log_action(action="harness_run_resumed")`; full audit trail. |
| T-21-04-05 (Information Disclosure — egress bypass on resume) | mitigate | `_resume_harness_engine_sse` calls `_get_or_build_conversation_registry` (line 1695) — same single-registry helper as gatekeeper. Egress filter wraps subsequent LLM calls in run_harness_engine. B4 invariant preserved. |
| T-21-04-06 (Elevation — start_phase_index attacker control) | accept | `start_phase_index = current_phase_idx + 1` derived from RLS-scoped `paused_run` row; attacker would need to forge a paused row in another user's thread, which RLS prevents. |
| T-21-04-07 (Race — resume vs cancel/timeout) | mitigate | resume_from_pause's transactional guard `.in_("status", ["paused"])` returns None when row is no longer paused; the resume branch checks the return and surfaces 500 with `hil_resume_state_invalid` (Test 7 covers). |

## Deviations from Plan

None — Task 1 executed exactly as planned. Edge cases noted:
- `body.parent_message_id` is read via `getattr(body, "parent_message_id", None)` for defensive consistency with the rest of stream_chat (the field is declared in `SendMessageRequest` so the attribute always exists — `getattr` is harmless).
- Test 5's `_Chain` mock subclass-style design is a slight enrichment over a plain MagicMock — needed because `messages.insert(payload).execute()` returns a result with `.data` and the test must capture `payload`. This is a test-side adaptation, not a plan deviation.

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Worktree branch was on stale base (6164e2d) before Wave 2/3 commits**
- **Found during:** Worktree branch check at agent start.
- **Issue:** HEAD was at `6164e2d` (pre-phase-21); Wave 2 (`pause`/`resume_from_pause` helpers) and Wave 3 (LLM_BATCH_AGENTS dispatcher) were not in the worktree's history. Plan 21-04 imports `harness_runs_service.resume_from_pause` and the `start_phase_index` engine parameter from those waves.
- **Fix:** `git reset --hard 5418c876d09a3b60aa8f1e1d1fac38c3dc186f40` (the expected base from the worktree_branch_check). Verified `git rev-parse HEAD` matches the expected base.
- **Files modified:** None (state-only correction).
- **Commit:** No new commit — this was a pre-implementation worktree alignment.

**2. [Rule 3 - Blocking issue] Backend `.env` missing in worktree (pydantic Settings validation crash)**
- **Found during:** First test collection — `pydantic_core.ValidationError: supabase_url Field required`.
- **Issue:** Worktree backend lacked the `.env` that `app.config.Settings` reads at module import. Existing tests fail in this state too, so it's not a Plan 21-04 regression.
- **Fix:** `cp /Users/.../backend/.env /Users/.../worktree/backend/.env` (one-shot copy from the parent repo). The .env is gitignored and not committed.
- **Files modified:** None tracked.
- **Commit:** N/A.

### Authentication Gates

None.

## Known Stubs

None new — Plan 21-04 introduces no stubs. The existing `LLM_BATCH_AGENTS` PHASE21_PENDING runtime stub in `_dispatch_phase` is unaffected by this plan and remains scheduled for completion via Wave 3 (Plan 21-03), which is already merged on the worktree base (commit `e99d853`).

## Threat Flags

None — no new security-relevant surface beyond the threat register entries above. The HIL resume branch reuses existing patterns (egress filter via `_get_or_build_conversation_registry`, RLS-scoped client via `get_supabase_authed_client`, audit log via `resume_from_pause`).

## Self-Check: PASSED

- File `backend/app/routers/chat.py`: FOUND, contains:
  - `Phase 21 / D-01, D-02: HIL resume detection` marker (1 occurrence)
  - `paused_run.get("status") == "paused"` (1 occurrence)
  - `active_harness.get("status") in ("pending", "running")` (1 occurrence — narrowed 409)
  - `def _resume_harness_engine_sse` (1 occurrence)
  - `_resume_harness_engine_sse` references (3 occurrences — definition + invocation in resume branch + comment)
  - `_get_or_build_conversation_registry` references (7 occurrences)
  - `harness_runs_service.resume_from_pause` (1 occurrence)
  - `hil_resume_state_invalid` (1 occurrence)
  - `start_phase_index=current_phase_idx + 1` (1 occurrence)
  - `"harness_mode": harness_type` (1 occurrence)
  - No leakage of placeholder symbols `_load_conversation_registry` / `_load_parent_registry` (0 occurrences).
- File `backend/tests/routers/test_chat_hil_resume.py`: FOUND, 10 tests passing.
- Commit `c3fcbc9`: FOUND in `git log`.
- All 81 router tests pass (no regression).
- Backend import smoke test passes (`from app.main import app` → OK).
