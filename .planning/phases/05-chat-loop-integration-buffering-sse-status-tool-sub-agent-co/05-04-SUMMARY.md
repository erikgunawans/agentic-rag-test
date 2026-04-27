---
phase: 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co
plan: "04"
subsystem: backend/chat-router
tags: [chat-router, sse-streaming, buffering, redaction, tool-loop, egress-filter, title-gen, phase5]
dependency_graph:
  requires:
    - 05-01 (redact_text_batch, ConversationRegistry, get_redaction_service)
    - 05-02 (deanonymize_tool_args, anonymize_tool_output, execute_tool registry kwarg)
    - 05-03 (agent_service.classify_intent registry kwarg, egress_filter)
    - 04-xx (de_anonymize_text with mode param, LLMProviderClient.call feature=title_gen)
  provides:
    - Full Phase 5 chat-loop integration: end-to-end PII privacy for all chat turns
    - Two redaction_status SSE events per turn (anonymizing + deanonymizing)
    - Single-batch buffered delta delivery after de-anon when redaction ON
    - Pre-flight egress filter on all 3 OpenRouter call sites (D-94)
    - Walker-wrapped tool execution (D-91) and skeleton tool events (D-89)
    - EgressBlockedAbort handler with clean SSE abort
    - Title-gen migrated to LLMProviderClient with title de-anon
  affects:
    - 05-06 (test suite — all 7 test classes assert on this plan's behavior)
    - Frontend SSE consumer (05-05 already ships the RedactionStatusEvent variant)
tech_stack:
  added: []
  patterns:
    - SSE buffering pattern (accumulate then emit single batch)
    - Pre-flight egress filter wrapping before cloud LLM calls
    - EgressBlockedAbort exception as clean abort signal
    - Graceful degrade try/except (D-90) for de-anon failures
    - Per-turn registry load + batch history anon (D-86 + D-93)
key_files:
  created: []
  modified:
    - backend/app/routers/chat.py (291 lines → 517 lines; +226 LOC for Phase 5 wiring)
decisions:
  - "SC#5 invariant preserved: when PII_REDACTION_ENABLED=false, all Phase 5 logic is behind redaction_on branch — zero registry load, zero buffering, zero redaction_status events"
  - "anonymizing event placed once before if/else branches (grep count=1); fires before agent_start in branch A but after the D-93 batch anon completes — satisfies D-88 behavioral contract"
  - "de-anon block placed AFTER try/except so it runs on partial full_response even if generic exception occurred mid-stream"
  - "title-gen re-anonymizes full_response before sending to LLM (full_response is REAL form after de-anon); uses anonymized_message for user turn in title prompt"
  - "EgressBlockedAbort re-raise at line 229 in _run_tool_loop bubbles to event_generator outer handler at line 418"
metrics:
  duration: "~15 minutes (tasks 4+5 only; tasks 1-3 were pre-committed)"
  completed_date: "2026-04-27"
  tasks_completed: 5
  files_modified: 1
---

# Phase 5 Plan 04: Chat-Loop Integration (Full 5-Task Wiring) Summary

Full Phase 5 chat-loop PII redaction integration into `backend/app/routers/chat.py` — composing Phases 1-4 primitives into a defensible privacy-preserving chat loop with SSE status events, single-batch buffered delivery, egress-filter defense-in-depth, and tool-call symmetry.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Phase 5 imports + EgressBlockedAbort + LLMProviderClient singleton | `6b4fc01` | `chat.py` |
| 2 | Registry load + batch history anon + classify_intent caller side | `ea3a665` | `chat.py` |
| 3 | _run_tool_loop walker wrap + egress wrapper + skeleton tool events | `78f66e0` | `chat.py` |
| 4 | Two stream_response sites — buffering + pre-flight egress + progressive delta suppression | `95718f2` | `chat.py` |
| 5 | redaction_status events + de-anon graceful degrade + single-batch delta + title-gen migration + EgressBlockedAbort handler | `23aaf44` | `chat.py` |

## Actual Line Numbers of Every Phase 5 Splice

| Edit Site | Line(s) | Decision |
|-----------|---------|----------|
| Phase 5 imports block | 16-24 | `from app.services.redaction import {ConversationRegistry, anonymize_tool_output, deanonymize_tool_args}` + egress_filter + get_redaction_service + LLMProviderClient |
| `EgressBlockedAbort` class def | 29-39 | Module-level exception; caught by event_generator outer handler |
| `_llm_provider_client` singleton | 51 | `LLMProviderClient()` at module level (no I/O at __init__) |
| `_run_tool_loop` signature extension | 143-144 | Added `*, registry=None, redaction_service=None, redaction_on=False` |
| D-94 site #1 (tool-loop egress) | 169-178 | Pre-flight egress filter before `complete_with_tools` in `_run_tool_loop` |
| D-89 skeleton tool_start emit | 196-203 | `if redaction_on: yield skeleton else yield full` |
| D-91 walker wrap around execute_tool | 207-225 | `deanonymize_tool_args` BEFORE, `anonymize_tool_output` AFTER |
| D-89 skeleton tool_result emit | 241-248 | Same pattern as tool_start |
| EgressBlockedAbort re-raise in _run_tool_loop | 229-232 | Bubbles up to event_generator outer handler |
| D-83/D-84/D-86/D-93 registry load + batch anon | 269-293 | Top of event_generator; sets `registry`, `redaction_on`, `anonymized_history`, `anonymized_message` |
| classify_intent caller side (D-96) | 301-313 | Passes `anonymized_message`, `anonymized_history`, `registry=registry` |
| D-88 redaction_status:anonymizing (single emit) | 296-301 | Before the if/else agent branch; satisfies grep count=1 |
| D-94 site #2 (branch A stream_response egress) | 350-359 | Pre-flight before branch A `stream_response` |
| D-87 branch A buffering + progressive gate | 362-366 | `if not redaction_on:` gates the progressive emit |
| D-94 site #3 (branch B stream_response egress) | 392-401 | Pre-flight before branch B `stream_response` |
| D-87 branch B buffering + progressive gate | 403-416 | Same pattern as branch A |
| EgressBlockedAbort outer handler | 418-421 | Emits `redaction_status:blocked` + `delta:{done:true}` + return |
| D-90 graceful degrade de-anon block | 429-445 | `if redaction_on and full_response:` → deanonymizing event → try/except de-anon |
| D-96 title-gen migration | 472-508 | Re-anon full_response → build title_messages with anonymized_message → LLMProviderClient.call(feature='title_gen') → de-anon title |

## _run_tool_loop Pattern

`_run_tool_loop` is an **async generator** (uses `yield` for "tool_start", "tool_result", "records" tuples). SSE emit decisions happen in TWO places:
1. `_run_tool_loop` yields raw dicts with event_type; the generator is consumed in `event_generator` with `async for event_type, data in _run_tool_loop(...)` — the `tool_start`/`tool_result` emits are IN the generator
2. On `EgressBlockedAbort` trip inside `_run_tool_loop`: raises without yielding; `event_generator`'s outer `except EgressBlockedAbort:` emits the SSE events (`redaction_status:blocked` + `delta:{done:true}`)

## LLMProviderClient Construction

`_llm_provider_client = LLMProviderClient()` at module level (line 51). `LLMProviderClient.__init__` does no I/O — lazy `AsyncOpenAI` clients are cached in `_clients` dict on first `_get_client()` call. Module-level is safe.

## SSE Event Ordering When Redaction ON

Actual ordering (after Tasks 1-5):
1. `redaction_status:anonymizing` (line 301 — before agent branch)
2. `agent_start` (line 322 — branch A only)
3. `tool_start:{type, tool}` / `tool_result:{type, tool}` (skeleton from _run_tool_loop — branch A sub-agent path)
4. `redaction_status:deanonymizing` (line 430)
5. `delta:{delta:<full_text>, done:false}` (line 445 — single batch)
6. `agent_done:{agent}` (line 449)
7. `thread_title:{title}` (line 507 — first exchange only)
8. `delta:{delta:'', done:true}` (line 511 — terminator)

Note: `redaction_status:anonymizing` fires BEFORE `agent_start` in branch A (not after, as originally planned in D-88 step ordering). This is a deviation from the literal plan step but satisfies the `grep count=1` acceptance criterion and preserves correct timing semantics (anon batch completes before this event fires in the redaction setup block at lines 269-293, before either branch runs).

## B4-Compliant Log Message Strings

| Feature Tag | Log Message |
|-------------|-------------|
| `feature=tool_loop` | `"egress_blocked event=egress_blocked feature=tool_loop match_count=%d"` (line 174) |
| `feature=stream_response_branch_a` | `"egress_blocked event=egress_blocked feature=stream_response_branch_a match_count=%d"` (line 355) |
| `feature=stream_response_branch_b` | `"egress_blocked event=egress_blocked feature=stream_response_branch_b match_count=%d"` (line 397) |
| `feature=deanonymize_text` | `"deanon_degraded event=deanon_degraded feature=deanonymize_text fallback_mode=none error_class=%s"` (line 437) |

All log messages emit counts/class names only — no payloads, no entity values (B4 invariant).

## Regression Test Status

- 242/242 tests pass (was 135 Phase 1+2+3+4 tests + Phase 5 structural + unit tests)
- SC#5 invariant: off-mode path (PII_REDACTION_ENABLED=false) byte-identical to Phase 0 CHAT-06 baseline
- All Phase 5 structural wiring tests (test_chat_router_phase5_imports.py, 41 tests) pass

## Deviations from Plan

### Auto-adjusted: anonymizing event placement

**Found during:** Task 5 implementation

**Issue:** The plan specified `redaction_status:anonymizing` after `agent_start` (branch A), AND the acceptance criteria specified `grep count=1`. These two requirements conflict: putting it only in branch A violates coverage for branch B; putting it in both branches violates `count=1`.

**Fix:** Placed the single `anonymizing` emit BEFORE the `if settings.agents_enabled:` branch (line 301). In branch A this means it fires before `agent_start`; in branch B it fires before messages construction. The D-93 batch anon already completed at lines 269-293 before this point, so the semantics are correct. `count=1` acceptance criterion satisfied.

**Impact:** Frontend sees `redaction_status:anonymizing` before `agent_start` in multi-agent mode. The Plan 05-05 frontend handler for this event shows a spinner — it doesn't depend on relative ordering with `agent_start`. No behavioral regression.

**Files modified:** `backend/app/routers/chat.py` line 300-301

**Commit:** `23aaf44`

### Pre-existing: D-85 grep quote style

**Found during:** Final verification

**Issue:** Acceptance criterion `grep -c "'content': body.message"` returns 0 because the code uses double quotes `"content": body.message` (line 129 inside a dict literal with double-quoted keys). The D-85 invariant IS preserved — user message INSERT uses `body.message` (REAL form).

**Assessment:** Pre-existing style difference introduced in tasks 1-3 (tasks 1-3 used double-quoted dict keys throughout). The behavioral contract is met; only the grep pattern in the acceptance criterion uses a different quote style.

## Known Stubs

None. All Phase 5 logic is wired end-to-end in `chat.py`. Title-gen uses `LLMProviderClient.call(feature='title_gen')` which is a real LLM call (not mocked). De-anon uses `de_anonymize_text` which is the full Phase 4 3-pass pipeline.

## Threat Flags

None new beyond what the plan's threat_model documents. All T-05-04-1 through T-05-04-8 mitigations are implemented:
- T-05-04-1 (egress): D-94 wraps all 3 cloud LLM call sites
- T-05-04-3 (degrade): D-90 try/except with mode='none' fallback
- T-05-04-4 (DoS): EgressBlockedAbort single-trip abort
- T-05-04-6 (title): D-96 title de-anon before persist and emit

## Notes for Downstream Plans

**Plan 05-06 (test suite):**
- `anonymizing` fires before `agent_start` in branch A — test assertions on event ordering should reflect this
- `redaction_status:blocked` emits from both inner egress wrappers (in `_run_tool_loop` the EgressBlockedAbort is raised; the outer handler emits blocked) and from the branch A/B stream_response raises
- `full_response` is REAL form by the time title-gen runs (already de-anon'd at line 444); title-gen re-anonymizes it before sending to LLM
- `_run_tool_loop` is an async generator — mock it with `AsyncMock` that returns an async iterator of `(event_type, data)` tuples
- The EgressBlockedAbort re-raise path at line 229 inside _run_tool_loop is the inner bubble-up; test with a mock that raises EgressBlockedAbort inside the generator body

**Plan 05-05 (frontend — already shipped):**
- No additional changes needed beyond what 05-05 already shipped (RedactionStatusEvent discriminated union + dispatch case)

## Self-Check: PASSED

Files verified:
- `backend/app/routers/chat.py` — FOUND (517 lines)
- `.planning/phases/05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co/05-04-SUMMARY.md` — FOUND

Commits verified:
- `95718f2` — FOUND (Task 4)
- `23aaf44` — FOUND (Task 5)
- `6b4fc01` — FOUND (Task 1, prior run)
- `ea3a665` — FOUND (Task 2, prior run)
- `78f66e0` — FOUND (Task 3, prior run)

Test result: 242/242 passed
