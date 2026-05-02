---
phase: 11-code-execution-ui-persistent-tool-memory
verified: 2026-05-02T11:15:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
verdict: PASS-WITH-CAVEATS
---

# Phase 11: Code Execution UI & Persistent Tool Memory — Verification Report

**Phase Goal:** Surface sandbox results in the chat UI with a streaming Code Execution Panel, and persist tool call results across conversation turns so the LLM can reference prior data.

**Verified:** 2026-05-02T11:15:00Z
**Status:** passed (with caveats — see Risks / Loose Ends)
**Re-verification:** No — initial verification.

---

## Phase Summary

Phase 11 lands two coupled surfaces in seven plans (11-01 through 11-07): backend persistence for the OpenAI tool-call triplet (`ToolCallRecord` extended with `tool_call_id` + `status` + 50 KB validator; `chat.py` reconstructs prior tool turns into LLM-format messages on every history load), and a frontend `CodeExecutionPanel` that streams stdout/stderr live during `execute_code` runs and re-hydrates from the persisted `messages.tool_calls.calls[N]` after the post-stream refetch. All four requirements (SANDBOX-07, MEM-01..03) trace cleanly to merged code on master, the 12-step UAT script was driven end-to-end against a live local environment, and the user replied "approved" on 2026-05-02. The phase is mergeable as-is; remaining caveats are operational (Railway sandbox image readiness, multi-worker semantics) rather than defects in this phase's deliverables.

---

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Code Execution Panel renders inline in chat with streaming stdout/stderr during execution | ✓ VERIFIED | `frontend/src/components/chat/CodeExecutionPanel.tsx` L214-302 (header + collapsible code + dark-bg terminal with green stdout / red stderr); `frontend/src/hooks/useChatState.ts` L211-233 appends `code_stdout`/`code_stderr` lines to `sandboxStreams: Map<tool_call_id, {stdout, stderr}>`; `frontend/src/components/chat/ToolCallCard.tsx` L143-186 routes the `live` buffer in over `persisted` when present. UAT step 5 confirmed live streaming behaviorally. |
| 2 | Generated files appear as download cards with filename, size, and download link | ✓ VERIFIED | `CodeExecutionPanel.tsx` L313-356 (file card row with `formatBytes`, lucide `Download` icon, `Button` variant=default purple accent); `handleDownload` L124-143 calls `apiFetch('/code-executions/{executionId}')` to refresh signed URL then `window.open(...)`. Backend endpoint at `backend/app/routers/code_execution.py` L153-192 (RLS-via-404, 1-hr signed-URL TTL refresh). UAT step 7 confirmed `fib.csv` downloaded successfully. |
| 3 | Tool call results are stored in `messages.tool_calls` JSONB after each execution | ✓ VERIFIED | `backend/app/routers/chat.py` 4 ctor sites: L526-532 (single-agent success), L539-548 (single-agent exception), L1067-1073 (multi-agent success — NEW per Plan 11-04 Splice E.2 — fixes silent gap where multi-agent successes were never persisted), L1079-1088 (multi-agent exception). Each constructs `ToolCallRecord` with `tool_call_id=tc["id"]` + `status=_derive_tool_status(...)`. `backend/app/models/tools.py` L33-60 50-KB head-truncate `field_validator` enforces uniform cap (no caller can bypass). |
| 4 | Loading conversation history reconstructs tool-call → result → assistant text message sequence | ✓ VERIFIED | `chat.py` `_expand_history_row` L97-146 emits the OpenAI triplet `{role:"assistant", tool_calls:[…]} → {role:"tool", tool_call_id, content} × N → optional {role:"assistant", content}` when every call carries `tool_call_id`; legacy rows fall back to `{role, content}` (D-P11-03). Both history SELECT sites widened to include `tool_calls`: L206 (branch mode), L227 (flat mode). Helper called at L222 + L235. |
| 5 | LLM can answer follow-up questions using data from earlier tool calls without re-executing | ✓ VERIFIED (via UAT) | The reconstruction at L97-146 places the persisted `output` (with `tool_call_id`) directly into the `history` array passed to `_run_tool_loop`. UAT step 9 confirmed: "What was the 15th Fibonacci number?" was answered by the LLM without firing a fresh `execute_code` call (browser DevTools → Network tab showed zero `code_stdout`/`code_stderr` SSE events on the follow-up turn). |

**Score:** 5/5 truths verified (4/4 must-haves at the requirement level — see Requirements Coverage below; SC #5 is observable-only via UAT and was approved).

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/models/tools.py` | `ToolCallRecord` with `tool_call_id`, `status`, 50KB validator | ✓ VERIFIED | L13 `MAX_OUTPUT_BYTES = 50_000`; L26-31 fields including `Literal["success","error","timeout"]`; L33-60 `@field_validator("output")` truncates with U+2026 ellipsis marker `\n…[truncated, N more bytes]\n`. Module imports cleanly (`from app.main import app` exits 0). |
| `backend/app/routers/chat.py` | History reconstruction + 4-site ctor wiring | ✓ VERIFIED | `_derive_tool_status` L65-92 (sandbox: timeout / error / success from `error_type`+`exit_code`; non-sandbox: success or error from `exception_caught`); `_expand_history_row` L97-146; both history SELECT sites widened (L206, L227); both helpers used (L222, L235); 4 ctor sites carry `tool_call_id` + `status` (L530, L544, L1071, L1084). |
| `backend/app/routers/code_execution.py` | `GET /code-executions/{execution_id}` for signed-URL refresh | ✓ VERIFIED | L153-192 single-row read with RLS-via-404 (T-11-03-1). `_refresh_signed_urls` regenerates 1-hr signed URLs on each call. |
| `frontend/src/lib/database.types.ts` | `CodeStdoutEvent`/`CodeStderrEvent` + widened `ToolCallRecord` | ✓ VERIFIED | L80-90 new event interfaces with `{type, line, tool_call_id}` shape (Phase 10 D-P10-06); L100-101 added to `SSEEvent` union; L17-18 `ToolCallRecord` widened with optional `tool_call_id?: string \| null` + `status?: 'success'\|'error'\|'timeout'\|null` (legacy rows still typecheck). |
| `frontend/src/hooks/useChatState.ts` | `sandboxStreams` Map + 3 lifecycle resets | ✓ VERIFIED | L25-27 state declaration; L211-233 SSE handlers (immutable Map updates); 3 lifecycle resets at L68 (thread switch), L148 (send enter), L264 (post-stream finally); L304 exported in return. |
| `frontend/src/components/chat/CodeExecutionPanel.tsx` | NEW — header, code preview toggle, terminal, file cards, glass-free | ✓ VERIFIED | 360-line component matching UI-SPEC §Component Inventory: `Terminal` Python badge (L218-221), 5-state status indicator with icons + i18n labels (L157-190), live `setInterval` execution timer (L97-107) frozen on `executionMs`, collapsible code preview (D-P11-09, default collapsed L86), terminal block with `bg-zinc-900` + `text-green-400` stdout / `text-red-400` stderr, file cards with `apiFetch` signed-URL refresh on click. NO `backdrop-blur`, NO gradient anywhere — clean 2026 Calibrated Restraint compliance. |
| `frontend/src/components/chat/ToolCallCard.tsx` | Router switch + `TOOL_CONFIG` entry | ✓ VERIFIED | L11 `TOOL_CONFIG.execute_code = { icon: Terminal, label: 'Code Execution' }`; L130-138 partition into `sandboxCalls` (`tool === 'execute_code' && tool_call_id`) vs `otherCalls`; L142-186 sandbox stack with `gap-6` (UI-SPEC §Vertical Stack); L188-198 generic stack unchanged. `executionId = out.execution_id` only — no `?? out.id` fallback (anti-grep guard verified). |
| `frontend/src/components/chat/MessageView.tsx` | `sandboxStreams` plumb-through | ✓ VERIFIED | L56 prop typed; L70 destructured; L107-112 passed to `<ToolCallList>` only on assistant messages with non-empty `tool_calls.calls`. |
| `frontend/src/pages/ChatPage.tsx` | `sandboxStreams` from context → MessageView | ✓ VERIFIED | L24 destructured from `useChatContext()`; L64 passed to `<MessageView>`. (Note: ChatContext export of `sandboxStreams` was implicitly accepted because `tsc --noEmit` passes; the prop drill is type-checked end-to-end.) |
| `frontend/src/i18n/translations.ts` | 17 sandbox.* keys × 2 languages | ✓ VERIFIED | `id` block L666-682 (17 keys); `en` block L1346-1362 (17 keys); 34 total `sandbox.*` lines. Keys cover: 5 status labels, code show/hide, files generated, download, downloadError, copyCode, codeCopied, 4 error.* labels, truncated marker. |

**Artifact Status:** 10/10 VERIFIED. All artifacts pass Levels 1-3 (exists, substantive, wired) and Level 4 (data flowing — backend → SSE → useChatState → ToolCallList → CodeExecutionPanel; or backend → DB → useChatState refetch → MessageView → CodeExecutionPanel).

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| Phase-10 sandbox callback | `useChatState.sandboxStreams` | `code_stdout`/`code_stderr` SSE events with `{type, line, tool_call_id}` | ✓ WIRED | Backend already emits per Phase 10 (10-05); useChatState L211-233 consumes them by `tool_call_id` key. |
| `useChatState.sandboxStreams` | `CodeExecutionPanel` (live) | `ChatContext → ChatPage → MessageView → ToolCallList` prop drill | ✓ WIRED | `tsc --noEmit` passes. Live takes precedence in `ToolCallCard.tsx` L155-160: `live?.stdout ?? persistedStdout ?? []`. |
| `messages.tool_calls.calls[N].output` | `CodeExecutionPanel` (persisted) | Post-stream Supabase refetch (`useChatState.ts` L246-254) → MessageView re-renders → ToolCallList partitions → CodeExecutionPanel reads persisted shape | ✓ WIRED | `out.stdout_lines` / `out.stderr_lines` / `out.files` / `out.execution_id` / `out.execution_ms` / `out.error_type` all consumed at L151-170 of ToolCallCard.tsx. |
| `ToolCallRecord(...)` ctor (4 sites) | `messages.tool_calls` JSONB | `ToolCallSummary(...).model_dump()` insert at chat.py L825 | ✓ WIRED | Each ctor passes `tool_call_id=tc["id"]` + derived `status`. The 50KB validator runs at construction so persisted rows are pre-truncated. |
| Persisted `tool_call_id` in `messages.tool_calls.calls[]` | LLM history on next turn | `_expand_history_row` triplet expansion at chat.py L97-146; both SELECT sites widened to include `tool_calls` (L206, L227); helper called at L222, L235 | ✓ WIRED | Re-emits the exact OpenAI tool-call triplet shape the API consumed in the original turn — no rename, no schema migration. |
| File-download click | Signed-URL refresh | `CodeExecutionPanel.handleDownload` → `apiFetch('/code-executions/{executionId}')` → `code_execution.py.get_code_execution` (RLS-via-404) → `window.open(signed_url)` | ✓ WIRED | UAT step 7 confirmed `fib.csv` opened in new tab. RLS path: super_admin OR `user_id = auth.uid()`. |

All 6 key links wired.

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `CodeExecutionPanel.stdoutLines` | `live?.stdout ?? persistedStdout` | (live) `useChatState.sandboxStreams` Map populated by SSE handler L211-222; (persisted) `out.stdout_lines` from `tool_output` written in `tool_service._execute_code` (Phase 10) | Yes (UAT step 5: green stdout streamed live; UAT step 8: same lines re-rendered after refresh) | ✓ FLOWING |
| `CodeExecutionPanel.files` | `out.files` | `tool_service._execute_code` uploads to `sandbox-outputs` bucket and stores `[{filename, size_bytes, signed_url}]` (Phase 10 D-P10-13) | Yes (UAT step 7: `fib.csv` card rendered with size + working Download button) | ✓ FLOWING |
| `CodeExecutionPanel.status` | `live ? 'running' : (tc.status ?? 'success')` | `_derive_tool_status` reads `tool_output.error_type` + `tool_output.exit_code` and emits `success`/`error`/`timeout`; the legacy fallback default of `'success'` only triggers for pre-Phase-11 rows that lacked `tool_call_id` (and therefore wouldn't enter this branch anyway — partition gate is `tool_call_id` truthy) | Yes (UAT steps 5/6/12 walked spinner → green check → red X end-to-end) | ✓ FLOWING |
| LLM history `messages` array | `_expand_history_row` output | `chat.py` history SELECT (L206/L227) + Pydantic-validated `ToolCallRecord.output` (50KB-capped) | Yes (UAT step 9: follow-up question answered from history without re-executing) | ✓ FLOWING |

No HOLLOW or DISCONNECTED data flows detected.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend imports cleanly post-merge | `cd backend && python -c "from app.main import app; print('OK')"` | `OK` (exit 0) | ✓ PASS |
| Frontend type-checks cleanly | `cd frontend && npx tsc --noEmit` | exit 0, no output | ✓ PASS |
| Anti-grep: `out.execution_id` present at exactly one site in ToolCallCard.tsx | `grep -n "out.execution_id" frontend/src/components/chat/ToolCallCard.tsx` | L168 | ✓ PASS |
| Anti-grep: `?? out.id` fallback chain absent | `grep -E '\?\?\s*out\.id\b' frontend/src/components/chat/ToolCallCard.tsx` | only present in a forbidding comment (L167) | ✓ PASS |
| Anti-grep: `Terminal, label: 'Code Execution'` in TOOL_CONFIG | `grep -n "Terminal, label: 'Code Execution'" ToolCallCard.tsx` | L11 | ✓ PASS |
| Anti-grep: `truncated, ` marker in tools.py | `grep -n "truncated, " backend/app/models/tools.py` | L42 (docstring), L60 (impl) | ✓ PASS |
| Module-level helpers (test-injectable) | `grep -n "^def _derive_tool_status\|^def _expand_history_row" backend/app/routers/chat.py` | L65, L97 | ✓ PASS |
| Phase-11 unit/integration tests | `find backend/tests -name 'test_tool_call_record.py' -o -name 'test_chat_history_reconstruction.py' -o -name 'test_code_executions_get_by_id.py' \| xargs grep -cE 'def test_'` | 11 + 13 + 4 = 28 | ✓ PASS |
| 17 sandbox.* keys in BOTH languages | count of `sandbox\.` lines in `translations.ts` | 34 (= 17 × 2) | ✓ PASS |
| CodeExecutionPanel free of glass/gradient (Calibrated Restraint enforcement) | `grep -nE "backdrop-blur\|bg-gradient-" frontend/src/components/chat/CodeExecutionPanel.tsx` | 0 hits | ✓ PASS |

10/10 spot-checks pass.

---

## Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| SANDBOX-07 | 11-02, 11-05, 11-06, 11-07 | Chat shows inline Code Execution Panel with code preview, streaming output, and file downloads | ✓ SATISFIED | `CodeExecutionPanel.tsx` (NEW) + SSE wiring (`useChatState.ts` L211-233) + router switch (`ToolCallCard.tsx` L130-186) + signed-URL refresh (`code_execution.py` L153-192). UAT steps 5-7, 11 confirmed end-to-end. |
| MEM-01 | 11-01, 11-04 | Full result string is stored in `messages.tool_calls` JSONB alongside name/arguments/status/summary fields | ✓ SATISFIED | `tools.py` L13-60 50KB validator + `tool_call_id`/`status` fields; `chat.py` 4 ctor sites (L530, L544, L1071, L1084) — including the Plan 11-04 Splice E.2 fix for the silent multi-agent success-path gap. |
| MEM-02 | 11-04 | History load reconstructs tool-call messages in LLM-expected format (assistant tool-call → tool result → assistant text) | ✓ SATISFIED | `_expand_history_row` at chat.py L97-146 emits the exact OpenAI triplet shape; both SELECT widening sites (L206, L227); helper called at L222 + L235; legacy rows fall back to flat `{role, content}` (D-P11-03). 13 integration tests in `test_chat_history_reconstruction.py` cover modern/legacy/redaction-on/redaction-off paths. |
| MEM-03 | 11-04 | LLM can reference data from earlier tool calls in follow-ups without re-executing tools | ✓ SATISFIED | Reconstructed `{role:"tool", tool_call_id, content}` items flow into the `history` array passed to `_run_tool_loop`, allowing the LLM to read prior `output` payloads. UAT step 9 ("What was the 15th Fibonacci number?") confirmed: LLM answered without dispatching `execute_code` (zero `code_stdout`/`code_stderr` SSE events on the follow-up turn). |

4/4 requirements SATISFIED. No orphaned requirements.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/components/chat/CodeExecutionPanel.tsx` | L150-153 | `try { … } catch { /* silent failure */ }` for `navigator.clipboard.writeText` | ℹ️ Info | Intentional and documented inline ("silent failure is acceptable since user can still read the code") — acceptable graceful degradation, not a stub. |
| `.planning/phases/11-code-execution-ui-persistent-tool-memory/deferred-items.md` | — | 10 pre-existing lint errors in unrelated files | ℹ️ Info | Logged as deferred; not introduced by Phase 11. Will not block this verification. |

No blocker or warning anti-patterns. The codebase is free of TODO/FIXME/PLACEHOLDER markers in Phase-11-touched files. No empty handlers, no `return null` short-circuits, no console.log-only implementations.

---

## Human Verification Status

The 12-step UAT script (Plan 11-07 Task 4) was driven by the orchestrator end-to-end against a live local environment on 2026-05-02:

- Backend on `:8000`, `/health = ok`
- Frontend on `:5174` (occupied 5173 → fell back to 5174 — same Vite-served HTML)
- Logged in as `test@test.com` (super_admin)

User reply: **"approved"** — captured in `11-07-SUMMARY.md` §Task 4 Checkpoint Handoff (L133-139) along with the verbatim 12-step script (L159-172).

All 12 steps passed:
1. Backend started; `/health` ok
2. Frontend started; HTML served
3. Logged in successfully
4. `execute_code` triggered for "first 20 Fibonacci numbers, save as fib.csv"
5. Live panel: spinner status, timer counting up, green stdout streaming
6. Completion: green checkmark + "Selesai/Completed", timer froze, "Show code" toggle revealed source
7. `fib.csv` download card rendered + downloaded successfully via signed URL
8. **Page refresh: panel re-rendered identically from persisted state** (proves MEM-01 round-trip)
9. **Follow-up "What was the 15th Fibonacci?" answered without re-executing** (proves MEM-02 + MEM-03)
10. Pre-Phase-11 messages with old `tool_calls` rendered without console errors (legacy fallback verified)
11. Multi-call stacking: 2 panels stacked with 24px gap
12. Error path: `1/0` → red X + "Gagal/Failed" + traceback in red + error pill "Kesalahan runtime Python"

No human verification items remain.

---

## Risks / Loose Ends

These do **not** block the phase but should be tracked operationally:

### 1. Production Sandbox infrastructure (Railway) is not part of Phase 11 scope, but Phase-11 frontend behavior depends on Phase-10 backend availability

- `SANDBOX_ENABLED` defaults to `False` (`backend/app/config.py` L74). Without an explicit env flip on Railway plus a built `lexcore-sandbox:latest` Docker image AND a Docker daemon reachable from the API container, `execute_code` is absent from the system prompt and Phase 11 panels never render in production.
- Recommendation: confirm Railway has `SANDBOX_ENABLED=true`, the sandbox image is published, and `docker.from_env()` succeeds in the deployed container before flipping the user-facing skill catalog. (Out of Phase 11 scope — owned by Phase 10 deployment; flagged here so a "Phase 11 looks broken in prod" report doesn't waste cycles.)

### 2. Multi-worker / multi-replica behavior of in-memory sandbox sessions

- Phase 10's session-per-thread state lives in process memory (`sandbox_service.py`). With Railway scaled to N>1 replicas, a follow-up `execute_code` could land on a different worker that has no IPython session for the thread, requiring re-init.
- Phase 11 is unaffected (panel reads SSE events from whichever worker handled the request), but variable-persistence promises in the PRD assume single-worker. (Pre-existing Phase 10 risk; flagged because Phase 11's UX advertises persistence.)

### 3. Signed-URL refresh failure modes

- `handleDownload` shows a 2-second `AlertCircle` + i18n `sandbox.downloadError` toast when `signed_url` is missing or `apiFetch` throws (CodeExecutionPanel.tsx L137-142). It does NOT surface 404 vs 500 vs network-error distinctions, nor does it offer retry. For the v1 contract this is acceptable; if production sees frequent signed-URL refresh failures, consider enriching the error path.
- Plan 11-03 includes a 4-test integration suite (`test_code_executions_get_by_id.py`) but the tests are smoke-only — they don't exercise concurrent download bursts or expired-URL race conditions.

### 4. PII redaction batch index alignment in `_expand_history_row`

- Plan 11-04 D-P11-10 routes reconstructed `{role:"tool", content}` items through the same `anonymize_history_text` batch that user/assistant content uses. The helper docstring (L108-109) notes "Every emitted dict carries a 'content' key (empty string is valid) so the redaction batch at chat.py ~L485 stays index-aligned". This was tested in `test_chat_history_reconstruction.py` (13 tests), but the index-alignment invariant is fragile — any future edit to the redaction batch loop must continue to expect 1-or-3-or-N items per source row.
- Recommendation: add a guard comment near the redaction batch loop at chat.py ~L485 explicitly documenting the 1-or-3-or-N expansion, so a future editor doesn't `zip(rows, anonymized)` and silently corrupt offsets.

### 5. Phase 11 has no dedicated frontend component tests

- `CodeExecutionPanel.tsx` is a 360-line UI component covering 5 status states, live/persisted reconciliation, code-preview accordion, and download-error handling. Plan 11-06 ships no Vitest/RTL tests; reliance is on the human UAT script and `tsc --noEmit`. UAT did exercise all 5 states, so the gap is not a defect — but a future regression in this component would not be caught by automated CI.
- Recommendation: add a v1.1 follow-up plan for `CodeExecutionPanel.test.tsx` (5 status states + live→persisted transition + download success/error). Not blocking.

### 6. Legacy fallback path is largely untested in production data

- `_expand_history_row` falls back to `{role, content}` for any row where ANY `calls[N].tool_call_id` is `null` (D-P11-03). This is correct, but the project has no large historical corpus of Phase-10 messages with `tool_calls` set yet (Phase 10 just shipped 2026-05-01), so the legacy path is exercised only against synthetic test fixtures. Real prod data may surface edge cases (e.g., a row where `tool_calls.calls` is `[]`, which is handled, vs. `tool_calls = {}` with no `calls` key, which is also handled — both via `tc.get("calls") or []` at L112).
- No action needed; flagging as residual uncertainty.

---

## Verdict: PASS-WITH-CAVEATS

All 5 ROADMAP success criteria, all 4 requirements (SANDBOX-07 + MEM-01..03), all 10 required artifacts, all 6 key links, and all 10 behavioral spot-checks verify against the merged code on master at HEAD `0170739`. The blocking human UAT checkpoint (Plan 11-07 Task 4) was approved by the user on 2026-05-02. The phase is mergeable and ready to ship.

The "with caveats" qualifier is operational, not technical:
- Production behavior depends on Railway sandbox infrastructure outside Phase 11's scope (Risk 1).
- Multi-worker session semantics are a Phase-10-inherited concern (Risk 2).
- Frontend component test coverage for CodeExecutionPanel is light (Risk 5).

None of these caveats indicate that Phase 11 promised something the codebase does not deliver. The codebase delivers what Phase 11 promised; the ecosystem around it (deployed sandbox, scaling, automated CI for the new component) is the open work.

---

*Verified: 2026-05-02T11:15:00Z*
*Verifier: Claude (gsd-verifier)*

## Verification Complete
