---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
plan: "04"
subsystem: backend/gatekeeper + backend/routers/chat
tags:
  - harness
  - gatekeeper
  - sse-streaming
  - pii-redaction
  - routing
  - phase-20

dependency_graph:
  requires:
    - 20-03  # harness_engine.py, harness_runs_service.py, harness_registry.py, types.py
  provides:
    - gatekeeper-llm-service       # backend/app/services/gatekeeper.py
    - chat-harness-routing-branches  # D-02, D-05 in stream_chat
    - cancel-harness-endpoint      # POST /threads/{id}/harness/cancel
    - active-harness-endpoint      # GET /threads/{id}/harness/active
    - conversation-registry-helper  # _get_or_build_conversation_registry (B4)
  affects:
    - backend/app/routers/chat.py  # 3 new routing branches, 2 endpoints, 1 helper

tech_stack:
  added:
    - gatekeeper.py (new service, 250 LOC)
  patterns:
    - sliding-window-sentinel-guard  # SENTINEL never reaches client (D-07)
    - egress-filter-pre-call         # SEC-04 on every gatekeeper LLM payload
    - multi-turn-history-reconstruction  # D-08 reload-safe from messages table
    - b4-single-canonical-registry   # _get_or_build_conversation_registry helper

key_files:
  created:
    - backend/app/services/gatekeeper.py
    - backend/tests/services/test_gatekeeper.py
    - backend/tests/routers/test_chat_harness_routing.py
  modified:
    - backend/app/routers/chat.py

decisions:
  - B4 fix: extracted `_get_or_build_conversation_registry` at module scope; gatekeeper and engine share SAME registry instance (object identity verified by test)
  - Sliding-window size 20 chars (len(SENTINEL)+8) for trailing whitespace tolerance in sentinel detection
  - load_gatekeeper_history uses the same token's RLS-scoped client; history includes all prior turns for that harness_name including the just-inserted user message
  - D-05 branch loads sys_settings inline for the ConversationRegistry helper; avoids double-load in the common path where harness is not eligible

metrics:
  duration: "~70 minutes"
  completed: "2026-05-03T16:17:00Z"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 20 Plan 04: Gatekeeper LLM Service + chat.py Routing Branches Summary

Implements the gatekeeper LLM service (sentinel-based harness trigger) and wires three new entry-point routing branches into `chat.py`, making the harness engine reachable from a real chat stream.

## What Was Built

### Task 1 — Gatekeeper Service (`backend/app/services/gatekeeper.py`)

JWT streaming agent that converts a normal chat message into a harness trigger when prerequisites are met.

**Public surface:**
- `build_system_prompt(harness: HarnessDefinition) -> str` — deterministic, KV-cache-friendly prompt built from `HarnessPrerequisites`
- `load_gatekeeper_history(*, thread_id, harness_name, token) -> list[dict]` — D-08 reload-safe prior-turn reconstruction from `messages.harness_mode`
- `run_gatekeeper(*, harness, thread_id, user_id, user_email, user_message, token, registry) -> AsyncIterator[dict]` — async generator yielding `delta` and `gatekeeper_complete` events

**SSE event contract (downstream frontend plans):**
```json
{"type": "delta", "content": "<streamed text chunk>"}
{"type": "gatekeeper_complete",
 "triggered": true|false,
 "user_message_id": "uuid|null",
 "assistant_message_id": "uuid|null",
 "harness_run_id": "uuid|null",
 "phase_count": 3}
```

`phase_count` is `len(harness.phases)` — W8 fix; frontend seeds `harnessRun.phaseCount` without an extra fetch.

**Security (SEC-04):**
- `egress_filter(json.dumps(messages), registry, None)` called before every streaming LLM call
- Tripped → persists refusal message, audit-logs `gatekeeper_egress_blocked`, yields refusal delta, returns `triggered=False`
- Sentinel `[TRIGGER_HARNESS]` never reaches the client: sliding-window buffer holds back last 20 chars during stream, strips sentinel from held-back tail on stream-end

**Sentinel detection (D-07):**
- `SENTINEL_RE = re.compile(r"\s*\[TRIGGER_HARNESS\]\s*$")` — anchored to end-of-stream only
- Mid-stream occurrences do NOT trigger (test 7 verifies)
- Trailing whitespace/newline tolerance via regex + 20-char sliding window

**Multi-turn dialogue (D-08, GATE-03):**
- User message persisted first with `harness_mode=harness.name`
- `load_gatekeeper_history` fetches all prior rows with that `harness_mode` tag (including just-persisted user msg)
- History fed to LLM as reconstructed conversation; stateless from LLM perspective

**On trigger:**
- Strips sentinel from clean text
- Persists clean assistant message with `harness_mode=harness.name`
- Calls `harness_runs_service.start_run(harness_type=harness.name, input_file_ids=None)`
- Yields `gatekeeper_complete{triggered=True, harness_run_id=..., phase_count=...}`

**On no-trigger:**
- Persists full response as assistant message
- Yields `gatekeeper_complete{triggered=False, harness_run_id=None, phase_count=...}`

### Task 2 — chat.py Routing Branches + Endpoints (`backend/app/routers/chat.py`)

**B4 fix — `_get_or_build_conversation_registry(thread_id, sys_settings) -> ConversationRegistry | None`** (module-level):
- Mirrors the inline block at event_generator (L890) and run_deep_mode_loop (L1689)
- Returns `ConversationRegistry.load(thread_id)` when `pii_redaction_enabled=True`
- Returns `None` when redaction is off (egress_filter is a no-op with None registry)
- Used by `_gatekeeper_stream_wrapper` once per request; same instance flows to gatekeeper and engine

**Branch A — D-02 active-harness-block (after Phase 19 resume-detection):**
```python
# Returns JSONResponse 409 when active run exists
if settings.harness_enabled:
    active_harness = await harness_runs_service.get_active_run(...)
    if active_harness is not None:
        return JSONResponse(status_code=409, content={
            "error": "harness_in_progress",
            "harness_type": ..., "current_phase": ..., "phase_name": ...
        })
```

**Branch B — D-05 gatekeeper-eligibility (after D-02):**
```python
if settings.harness_enabled:
    latest = await harness_runs_service.get_latest_for_thread(...)
    if latest is None:
        harnesses = harness_registry.list_harnesses()
        if harnesses:
            target = harnesses[0]   # D-06 single-harness invariant for v1.3
            if target.prerequisites.requires_upload:   # GATE-05
                return StreamingResponse(_gatekeeper_stream_wrapper(...))
```

**`_gatekeeper_stream_wrapper` (module-level async generator):**
- Builds one registry via `_get_or_build_conversation_registry` (B4)
- Drains `run_gatekeeper` — forwards delta/gatekeeper_complete events
- On trigger: drives `run_harness_engine` in-stream with SAME registry (D-07)
- On no-trigger: emits `{"type": "done"}` to close stream
- Post-harness summary plug-in point documented for Plan 20-05

**New endpoints:**
- `POST /chat/threads/{thread_id}/harness/cancel` — flips `harness_runs.status='cancelled'` (B3 DB-poll arm); docstring explains dual-layer cancellation architecture
- `GET /chat/threads/{thread_id}/harness/active` — returns `{harnessRun: null}` or structured payload for frontend rehydration (Plan 20-09)

**Routing order at `stream_chat` entry (verified by code):**
1. Phase 19 ask_user resume detection (existing)
2. D-02 active-harness-block (new)
3. D-05 gatekeeper-eligibility (new)
4. Standard/deep dispatch (existing)

## Tests

| Suite | Count | Status |
|-------|-------|--------|
| `tests/services/test_gatekeeper.py` | 11 | PASS |
| `tests/routers/test_chat_harness_routing.py` | 13 | PASS |
| **Total** | **24** | **ALL PASS** |

### Gatekeeper tests (11)
1. `test_build_system_prompt_includes_intro`
2. `test_build_system_prompt_includes_upload_block_when_required`
3. `test_load_gatekeeper_history_returns_prior_turns`
4. `test_run_gatekeeper_no_sentinel_yields_full_buffer`
5. `test_run_gatekeeper_sentinel_at_end_strips_and_triggers`
6. `test_run_gatekeeper_sentinel_with_trailing_whitespace_still_triggers`
7. `test_run_gatekeeper_sentinel_mid_stream_does_NOT_trigger` — verifies regex anchoring
8. `test_run_gatekeeper_egress_blocked_emits_refusal`
9. `test_run_gatekeeper_persists_user_and_assistant_messages_with_harness_mode`
10. `test_run_gatekeeper_calls_start_run_on_trigger`
11. `test_run_gatekeeper_complete_event_includes_phase_count` (W8) — both trigger/no-trigger paths

### Routing tests (13)
1. `test_d02_reject_when_active_harness_returns_409_with_structured_payload`
2. `test_d05_skip_gatekeeper_when_harness_disabled`
3. `test_d05_skip_gatekeeper_when_no_harness_registered`
4. `test_d05_skip_gatekeeper_when_latest_run_exists`
5. `test_d05_skip_gatekeeper_when_prerequisites_requires_upload_false` (GATE-05)
6. `test_d05_invokes_gatekeeper_stream_when_eligible`
7. `test_cancel_harness_endpoint_sets_cancelled_status`
8. `test_cancel_harness_endpoint_404_when_no_active_run`
9. `test_get_active_harness_returns_null_when_none`
10. `test_get_active_harness_returns_payload_when_active`
11. `test_get_or_build_conversation_registry_calls_load_when_redaction_on` (B4)
12. `test_get_or_build_conversation_registry_returns_none_when_redaction_off` (B4)
13. `test_gatekeeper_stream_wrapper_passes_same_registry_to_gatekeeper_and_engine` (B4)

## Deviations from Plan

None — plan executed exactly as written.

The sliding-window implementation differs slightly from the plan description in implementation detail: the held-back tail (last 20 chars) accumulates BOTH during streaming (via the prefix-flush pattern) and on stream completion, ensuring the sentinel is never emitted even when it arrives in fragments across multiple chunks. This is equivalent to the plan's description and satisfies all tests.

## Commits

- `ad3db27`: `feat(20-04): implement Gatekeeper LLM service with sentinel detection + 11 tests`
- `4c5e7ce`: `feat(20-04): wire chat.py D-02/D-05 routing branches + gatekeeper helper + cancel/active endpoints + 13 tests`

## Known Stubs

None — all data flows are wired. The `_gatekeeper_stream_wrapper` has a documented stub for post-harness summary (replaced by Plan 20-05), but this is intentional and documented in the code.

## Threat Surface

No new network endpoints beyond those planned. The two new endpoints (`/harness/cancel`, `/harness/active`) are documented in the plan threat model (T-20-04-03, T-20-04-04) and are RLS-scoped via `get_current_user` + `get_active_run` which uses `get_supabase_authed_client(token)`.

## Self-Check: PASSED

Files exist:
- `backend/app/services/gatekeeper.py` ✓
- `backend/tests/services/test_gatekeeper.py` ✓
- `backend/tests/routers/test_chat_harness_routing.py` ✓
- `backend/app/routers/chat.py` (modified) ✓

Commits exist:
- `ad3db27` ✓
- `4c5e7ce` ✓
