---
phase: 11-code-execution-ui-persistent-tool-memory
plan: 04
subsystem: backend/routers
tags: [chat, history-reconstruction, tool-call-record, persistent-memory, mem-01, mem-02, mem-03, redaction]
dependency_graph:
  requires:
    - "Plan 11-01: ToolCallRecord.tool_call_id + status fields + 50 KB output cap (validator)"
  provides:
    - "_expand_history_row(row) module-level helper — emits OpenAI triplet for modern rows, flat fallback for legacy"
    - "_derive_tool_status(tool_name, tool_output, *, exception_caught=False) module-level helper — D-P11-08 status derivation"
    - "Both history SELECTs widened to include `tool_calls` JSONB column"
    - "All 4 ToolCallRecord constructor sites carry `tool_call_id` + derived `status`"
    - "Multi-agent success-path ToolCallRecord persistence (silent-bug fix; pre-Phase-11 only the exception path persisted)"
  affects:
    - "Plan 11-05 (frontend useChatState): downstream consumer of persisted call.tool_call_id and call.status"
    - "All future chat turns: prior tool calls (search_documents UUIDs, file listings, code stdout) reconstructable on history-load"
tech_stack:
  added: []
  patterns:
    - "Module-level testable helpers (mirrors `_run_tool_loop_for_test` from Plan 10-05)"
    - "OpenAI tool-call triplet reconstruction: assistant{tool_calls} → tool{tool_call_id, content} × N → optional assistant{content}"
    - "Per-row legacy cutoff: if calls and all(c.get('tool_call_id') for c in calls) — no per-call cherry-picking (D-P11-03)"
key_files:
  created:
    - "backend/tests/routers/test_chat_history_reconstruction.py"
  modified:
    - "backend/app/routers/chat.py"
decisions:
  - "Single per-row legacy cutoff: any call missing tool_call_id forces the entire row to flat {role, content} (D-P11-03). No partial-cherry-pick path."
  - "Tool message content is the JSON-serialized output for dict outputs, but verbatim string for already-truncated string outputs — avoids double-encoding of the Plan 11-01 truncation marker."
  - "Multi-agent branch silent-bug fix (T-11-04-4): pre-Phase-11 only the exception path appended ToolCallRecord. New success-path append closes the MEM-01 gap for multi-agent turns (E.2)."
  - "Splice F was a no-op grep verification: the existing redaction batch at L485 already iterates `m['content']` correctly because every dict emitted by _expand_history_row carries a 'content' key (D-P11-10)."
  - "Both helpers extracted to module level (not nested inside the per-request handler) so they can be unit-tested without booting FastAPI — mirrors `_run_tool_loop_for_test` pattern from Plan 10-05."
metrics:
  duration: "~30 minutes (TDD cycle: rebase + RED + GREEN; no REFACTOR needed)"
  completed: "2026-05-01T20:30:00Z"
  tasks_completed: 1
  tests_added: 13
  files_changed: 2
---

# Phase 11 Plan 11-04: Chat History Reconstruction & ToolCallRecord Persistence Summary

Wires `backend/app/routers/chat.py` to the Phase 11 schema (Plan 11-01). Three coordinated splices reconstruct prior tool calls on history-load (MEM-01..03), so the LLM can reference earlier UUIDs, search results, file listings, and code outputs without re-executing — and a silent multi-agent persistence bug (only the exception path was recording tool calls) is fixed in the same patch.

## Objective Recap

`backend/app/routers/chat.py` was loading history as `[{role, content}]` only, dropping the structured `tool_calls.calls[]` JSONB on every turn. This plan widens both history SELECTs to include `tool_calls`, expands modern rows into the OpenAI tool-call triplet (assistant → tool × N → assistant), and pipes `tool_call_id` + derived `status` into all 4 `ToolCallRecord(...)` constructor sites — including a NEW success-path constructor in the multi-agent branch that was previously missing.

## What Was Built

### 1. `backend/app/routers/chat.py` (modified) — 5 logical splices

#### Splice A — Module-level helpers (chat.py L62-130 after the splice)

```python
def _derive_tool_status(
    tool_name: str,
    tool_output: dict | str | None,
    *,
    exception_caught: bool = False,
) -> str:
    """D-P11-08: derive ToolCallRecord.status from tool execution outcome."""
    if exception_caught:
        return "error"
    if tool_name == "execute_code" and isinstance(tool_output, dict):
        if tool_output.get("error_type") == "timeout":
            return "timeout"
        exit_code = tool_output.get("exit_code")
        if tool_output.get("error_type") or (
            exit_code is not None and exit_code != 0
        ):
            return "error"
        return "success"
    return "success"


def _expand_history_row(row: dict) -> list[dict]:
    """D-P11-03/07/10: expand a `messages` row into LLM-format items.
    Modern triplet for rows where every call has tool_call_id;
    flat {role, content} fallback otherwise. Every emitted dict carries
    a 'content' key (precondition of the existing redaction batch at L485).
    """
    tc = row.get("tool_calls") or {}
    calls = tc.get("calls") or []
    if calls and all(c.get("tool_call_id") for c in calls):
        items: list[dict] = [{
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": c["tool_call_id"],
                    "type": "function",
                    "function": {
                        "name": c["tool"],
                        "arguments": json.dumps(c.get("input") or {}),
                    },
                }
                for c in calls
            ],
        }]
        for c in calls:
            output = c.get("output")
            if isinstance(output, str):
                content = output  # avoid double-encoding (Plan 11-01 truncated str)
            else:
                content = json.dumps(output, ensure_ascii=False)
            items.append({
                "role": "tool",
                "tool_call_id": c["tool_call_id"],
                "content": content,
            })
        if row.get("content"):
            items.append({"role": "assistant", "content": row["content"]})
        return items
    return [{"role": row.get("role"), "content": row.get("content") or ""}]
```

Inserted at L65 (`_derive_tool_status`) and L97 (`_expand_history_row`), AFTER `compute_web_search_effective` and BEFORE `router = APIRouter(...)`.

#### Splice B — Branch-mode history SELECT (chat.py L201-225 after the splice)

```python
.select("id, role, content, parent_message_id, tool_calls")  # was: parent_message_id only
...
history = []
for m in chain:
    history.extend(_expand_history_row(m))  # was: list comprehension
```

#### Splice C — Flat-mode history SELECT (chat.py L228-238 after the splice)

```python
flat_rows = (
    client.table("messages")
    .select("role, content, tool_calls")  # was: role, content only
    ...
).data or []
history = []
for m in flat_rows:
    history.extend(_expand_history_row(m))
```

#### Splice D — Single-agent ToolCallRecord constructors (chat.py L526-549 after the splice)

```python
# Success path (was: tool=, input=, output= only)
tool_records.append(ToolCallRecord(
    tool=func_name,
    input=func_args,
    output=tool_output,
    tool_call_id=tc["id"],
    status=_derive_tool_status(func_name, tool_output),
))
...
# Exception path (was: tool=, input=, output={}, error= only)
tool_records.append(ToolCallRecord(
    tool=func_name,
    input=func_args,
    output={},
    error=str(e),
    tool_call_id=tc["id"],
    status=_derive_tool_status(func_name, None, exception_caught=True),
))
```

#### Splice E — Multi-agent branch (chat.py L1063-1090 after the splice)

E.1 — exception-path ctor gains `tool_call_id` + `status`.

E.2 — **NEW** success-path ctor inserted at the END of the inner `try` block (after the if/else that resolves `tool_output` from the queue-drain or non-sandbox path; before `except EgressBlockedAbort:`):

```python
# Phase 11 Plan 11-04 (MEM-01): persist successful multi-agent tool call.
# Pre-Phase-11 only the exception path below appended a record — the success
# path was a silent gap.
from app.models.tools import ToolCallRecord
tool_records.append(ToolCallRecord(
    tool=func_name,
    input=func_args,
    output=tool_output,
    tool_call_id=tc["id"],
    status=_derive_tool_status(func_name, tool_output),
))
```

The inline `from app.models.tools import ToolCallRecord` mirrors the existing inline import on the original L957 (now L1080) — preserved for symmetry. Top-level import on L17 also covers it.

#### Splice F — Redaction batch (chat.py L578 — unchanged code)

NO code change. Verified by grep:

```
raw_strings = [m["content"] for m in history] + [body.message]
```

Every dict emitted by `_expand_history_row` (assistant-with-tool_calls, tool message, plain assistant, legacy fallback) carries a `content` key — empty string for assistant-with-tool_calls is valid. Redaction batch index alignment with `zip(history, anonymized_strings[:-1])` is preserved (D-P11-10). Test 8 (`test_every_expanded_item_has_content_key`) and Test 7 (`test_redaction_batch_compatibility`) enforce this precondition.

### 2. `backend/tests/routers/test_chat_history_reconstruction.py` (new — 13 unit tests)

| # | Test | What it proves |
|---|------|----------------|
| 1 | `test_expand_modern_row_with_two_calls` | 4-item triplet expansion: assistant{tool_calls} → tool{c1} → tool{c2} → assistant{content}. dict outputs JSON-encoded. |
| 2 | `test_expand_modern_row_empty_assistant_text` | Empty content → trailing assistant text omitted (3 items, not 4). |
| 3 | `test_expand_legacy_row_no_tool_call_id` | Single call with `tool_call_id: None` → flat `{role, content}` fallback. |
| 4 | `test_expand_row_no_tool_calls_at_all` | `tool_calls: None` → flat fallback. |
| 5 | `test_expand_partial_legacy_calls_falls_back` | Mixed calls (one with id, one without) → entire row falls back (per-row cutoff per D-P11-03). |
| 6 | `test_str_output_in_tool_message_no_double_encoding` | Pre-truncated string output (Plan 11-01) is verbatim, NOT `json.dumps(string)` (no extra wrapping quotes). |
| 7 | `test_redaction_batch_compatibility` | All expanded items have `content` key — `[m["content"] for m in expanded]` does not raise KeyError. |
| 8 | `test_every_expanded_item_has_content_key` | Splice F precondition — assistant-with-tool_calls rows MUST set `content: ""` not omit it. |
| 9 | `test_status_derive_for_execute_code_success` | `_derive_tool_status("execute_code", {exit_code:0, error_type:None})` → `"success"`. |
| 10 | `test_status_derive_for_execute_code_timeout` | `error_type: "timeout"` → `"timeout"`. |
| 11 | `test_status_derive_for_execute_code_error` | `error_type: "runtime_error", exit_code: 1` → `"error"`. |
| 12 | `test_status_derive_for_non_sandbox_success` | Non-sandbox tool with output → `"success"`. |
| 13 | `test_status_derive_for_exception_path` | `exception_caught=True` → `"error"` regardless of tool. |

## Verification

| Gate | Command | Result |
|------|---------|--------|
| New unit tests | `pytest tests/routers/test_chat_history_reconstruction.py -v` | 13 passed in 155.28s |
| Plan 11-01 regression | `pytest tests/models/test_tool_call_record.py -v` | 11 passed in 2.02s |
| Phase 10 sandbox-streaming regression | `pytest tests/routers/test_chat_sandbox_streaming.py -v` | 8 passed in 153.12s |
| Backend import smoke | `python -c "from app.main import app; print('OK')"` | `OK` |
| `_expand_history_row` defined | `grep -q "^def _expand_history_row"` | PASS |
| `_derive_tool_status` defined | `grep -q "^def _derive_tool_status"` | PASS |
| Branch SELECT widened | `grep -q '.select("id, role, content, parent_message_id, tool_calls")'` | PASS |
| Flat SELECT widened | `grep -q '.select("role, content, tool_calls")'` | PASS |
| 4 ToolCallRecord ctor sites carry kwarg | `grep -cP "tool_call_id=tc\[.id.\]"` | 4 (expected 4) |
| Anonymizer site unchanged | `grep -q 'raw_strings = \[m\["content"\] for m in history\]'` | PASS |
| Empty-string content emitted | `grep -q '"content": ""'` | PASS |

Final ToolCallRecord constructor lines: **530, 544, 1071, 1084** (4 sites — single-agent success, single-agent exception, multi-agent success NEW, multi-agent exception). Helper definitions: **L65 (`_derive_tool_status`), L97 (`_expand_history_row`)**. Helper call sites in history load: **L222 (branch mode), L235 (flat mode)**.

## Commits

- `3c20de5` `test(11-04): add failing tests for chat history reconstruction helpers` — RED gate
- `6944c9f` `feat(11-04): wire chat history reconstruction + ToolCallRecord persistence` — GREEN gate

## Deviations from Plan

### 1. [Rule 3 — Blocking, environmental] Worktree was 169 commits behind master and lacked Wave 1 commits

**Found during:** Initial `grep -n "ToolCallRecord" backend/app/routers/chat.py` verification.

**Issue:** The worktree branch `worktree-agent-a51419fed6d670cd5` was created at an old base — it had 0 commits ahead of master and 169 commits behind. `chat.py` was 649 lines (vs 978 on master), with only 2 ToolCallRecord constructor sites (vs 4) and no Plan 11-01 ToolCallRecord schema extension. Without Plan 11-01's `tool_call_id` and `status` fields, the new ctor kwargs would have failed Pydantic validation.

**Fix:** `git rebase master` — clean rebase (no conflicts), brought in Plan 11-01 + 11-02 + 11-03 commits and the multi-agent branch in chat.py. After rebase, all line numbers and grep targets matched the plan exactly.

**Files modified:** None at the code level — the rebase was a worktree-state operation.

### 2. [Rule 3 — Blocking, environmental] conftest.py + Settings init require .env at test-collect time

**Found during:** Step 3 (RED gate run).

**Issue:** Same as Plan 11-01 §Deviation 1 — `backend/tests/conftest.py` imports `app.services.redaction.anonymization`, which transitively loads `app.config.Settings` (a `pydantic_settings.BaseSettings` requiring `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`). Worktrees do not carry untracked `.env` files.

**Fix:** Sourced `/Users/erikgunawansupriatna/.../backend/.env` from the main repo via `set -a && source ... && set +a` before invoking pytest and `python -c "from app.main import app"`. Also used the main repo venv (`/Users/.../backend/venv/`) since the worktree has no venv. No code change required — purely a test-runner invocation pattern, identical to the Plan 11-01 deviation. Backend import smoke and all three test suites passed cleanly with the env loaded.

**Files modified:** None.

### 3. [Doc-only] Multi-agent success-path placement

**Found during:** Splice E.2 implementation.

**Issue:** Plan 11-04 §Splice E.2 says "still inside the `try`, BEFORE the `except EgressBlockedAbort:` line". This is exactly where the new ctor was placed. However, the placement at the END of the inner `try` (after both the redaction-on and redaction-off branches resolve `tool_output`) means a single ctor handles BOTH redaction-on and redaction-off success paths — which is the intended behavior (D-P11-08 status derivation runs on the post-anonymized `tool_output` for redaction-on; on the raw output for redaction-off; both are correct because anonymization preserves the dict shape and Phase 10 status keys).

**Fix:** None needed — the plan placement is correct. Documenting for clarity in case future readers wonder why the success ctor is OUTSIDE the inner if/else but INSIDE the outer try.

**Files modified:** N/A.

### Auth Gates

None.

## Self-Check: PASSED

- backend/app/routers/chat.py: FOUND (modified)
- backend/tests/routers/test_chat_history_reconstruction.py: FOUND (created)
- .planning/phases/11-code-execution-ui-persistent-tool-memory/11-04-SUMMARY.md: FOUND (this file)
- Commit 3c20de5 (test): FOUND in `git log`
- Commit 6944c9f (feat): FOUND in `git log`
- All grep verification gates: PASS (8/8)
- All 13 new unit tests: PASS
- Plan 11-01 regression (11 tests): PASS
- Phase 10 sandbox-streaming regression (8 tests): PASS
- Backend import smoke: PASS

## TDD Gate Compliance

- RED gate (`test(11-04): ...`): commit `3c20de5` — 13 tests added, all fail with `ImportError` on `_expand_history_row` and `_derive_tool_status`.
- GREEN gate (`feat(11-04): ...`): commit `6944c9f` — 13/13 passing.
- REFACTOR gate: not needed — implementation matches plan spec; helpers are small (~35 + ~50 LOC); no duplication or dead code introduced.

## Threat Surface Notes

No new threat flags. The threat register in 11-04-PLAN.md (T-11-04-1 through T-11-04-7) is fully addressed:

- **T-11-04-1 (Information Disclosure — PII in reconstructed tool messages):** Mitigated. Every `_expand_history_row` output dict has a `content` key, so the existing `redact_text_batch` at L578 picks them up under `redaction_on=True`. Tests 7 + 8 enforce. Old rows persisted while redaction was OFF still get anonymized at history-load time.
- **T-11-04-2 (Tampering — forged tool_call_id via direct SQL):** Accepted. RLS already restricts INSERT to `user_id = auth.uid()`. A user could only forge an ID for their own row; worst case is the LLM seeing inconsistent triplets — no cross-user impact.
- **T-11-04-3 (DoS — unbounded history-load expansion):** Accepted. Per-row expansion is O(N_calls) with N_calls bounded by the existing 50 KB output cap from Plan 11-01. Acceptable for a single-user chat thread.
- **T-11-04-4 (Repudiation — multi-agent success path silent gap):** Mitigated. Splice E.2 adds the missing `ToolCallRecord` append in the multi-agent success branch. MEM-01 success-path persistence is now complete in both single-agent and multi-agent paths.
- **T-11-04-5 (Spoofing — legacy mis-classified as modern):** Mitigated. D-P11-03 cutoff `if calls and all(c.get("tool_call_id") for c in calls)`. Test 5 enforces per-row partial-legacy fallback (no per-call cherry-picking).
- **T-11-04-6 (Information Disclosure — double JSON-encoding of pre-truncated string):** Mitigated. Test 6 verifies `isinstance(output, str)` skips `json.dumps`. The LLM sees clean tool output strings without spurious wrapping quotes.
- **T-11-04-7 (Tampering — race between Plan 11-01 truncation and history reconstruction):** Accepted. Truncation runs at write-time in the model validator; history reconstruction reads already-truncated output — no race.

No new endpoints, no new RLS surface, no schema changes. Pure in-process router patch.

## Known Stubs

None. The history reconstruction is fully wired end-to-end; the multi-agent success-path persistence bug is fixed. Plan 11-05 (frontend `useChatState` `sandboxStreams` Map) is the downstream consumer for the live-streaming UX, but the persisted-message reading path it relies on is now byte-correct.

## Notes for Plan 11-05 (frontend useChatState)

When `useChatState` reads from `msg.tool_calls.calls[N]` after the post-stream refetch:

- Every modern persisted call now carries `tool_call_id` (the OpenAI UUID) and `status` (Literal `"success" | "error" | "timeout" | null`). Both are nullable in the Plan 11-02 frontend type so legacy rows still typecheck.
- The Map key for `sandboxStreams` should be `call.tool_call_id` — guaranteed stable across the live → persisted transition (the same UUID flows from the SSE event to the persisted record).
- `status === "success"` for non-sandbox tools means the call completed without an exception; for `execute_code` it additionally means `exit_code === 0` and `error_type` is falsy.
- Multi-agent turns now persist successful tool calls (silent-bug fix). Frontend code that previously relied on multi-agent tool calls being absent from history (e.g., to infer "this turn was multi-agent and the tool ran successfully") will now see them in the persisted record. Re-check any logic that branches on `msg.tool_calls.calls.length`.

---

*Phase 11 — Code Execution UI & Persistent Tool Memory*
*Plan 11-04 completed: 2026-05-01*
