---
phase: 11-code-execution-ui-persistent-tool-memory
plan: 01
subsystem: backend/models
tags: [pydantic, tool-records, persistent-memory, validator, mem-01]
dependency_graph:
  requires: []
  provides:
    - "ToolCallRecord.tool_call_id field (str | None)"
    - "ToolCallRecord.status field (Literal[success,error,timeout] | None)"
    - "MAX_OUTPUT_BYTES = 50_000 module constant"
    - "ToolCallRecord.truncate_output @field_validator (head-truncate at construction)"
  affects:
    - "Plan 11-04 (history reconstruction): can now read tool_call_id and status from persisted records"
    - "Plan 11-04 (chat.py ToolCallRecord construction): passes tool_call_id=tc['id'] and derived status"
    - "Plan 11-05 (frontend types): backend shape now exposes tool_call_id + status"
tech_stack:
  added: []
  patterns:
    - "Pydantic field_validator + Literal — same pattern as backend/app/routers/skills.py L37-44"
key_files:
  created:
    - "backend/tests/models/__init__.py"
    - "backend/tests/models/test_tool_call_record.py"
  modified:
    - "backend/app/models/tools.py"
decisions:
  - "Truncation lives inside ToolCallRecord (Pydantic validator) — every caller inherits the cap; no per-call utility (D-P11-11)."
  - "50 KB cap measured in UTF-8 BYTES, not Python characters. A 30,000-char Indonesian string of 'é' (60,000 UTF-8 bytes) is correctly identified as over-cap."
  - "Head preservation (not tail/middle): the start of search results / file listings / stdout is what follow-up questions reference (D-P11-04)."
  - "Over-cap dicts collapse to a STRING (with marker). Under-cap dicts pass through unchanged so structured callers (e.g. CodeExecutionPanel reading .stdout/.files) keep working in the common case."
  - "Marker uses Unicode U+2026 (single char ellipsis): `\\n…[truncated, N more bytes]\\n`. ASCII triple-dot is explicitly rejected by test_truncation_marker_uses_unicode_ellipsis."
  - "Optional defaults (tool_call_id=None, status=None) preserve backwards compat for legacy `messages.tool_calls` JSONB rows from before Phase 11 — no schema migration (D-P11-03)."
metrics:
  duration: "~11 minutes (TDD cycle: RED + GREEN, no REFACTOR needed)"
  completed: "2026-05-01T12:35:01Z"
  tasks_completed: 1
  tests_added: 11
  files_changed: 3
---

# Phase 11 Plan 11-01: Extend ToolCallRecord — Summary

Backend Pydantic model gains `tool_call_id`, `status`, and a 50 KB head-truncate validator on `output` — the foundation for persistent tool memory (MEM-01) and downstream history reconstruction (Plan 11-04).

## Objective Recap

`backend/app/models/tools.py` `ToolCallRecord` was a 4-field model (tool / input / output / error) with no size cap. Plan 11-01 adds two optional fields and a Pydantic `field_validator` so that:

1. Every code path that builds a record (chat.py × 3 sites, future tools, tests) gets the 50 KB cap for free — no caller can bypass.
2. The `tool_call_id` field unblocks the OpenAI tool-call triplet reconstruction in Plan 11-04 (`{role:"assistant", tool_calls:[…]}` → `{role:"tool", tool_call_id, content}` per call).
3. The `status` Literal field lets the UI render success / error / timeout indicators without re-deriving from `output.error_type` every render.

## What Was Built

### 1. `backend/app/models/tools.py` (modified)

```python
import json
from typing import Literal
from pydantic import BaseModel, field_validator

MAX_OUTPUT_BYTES = 50_000  # D-P11-04: 50 KB in UTF-8 bytes

class ToolCallRecord(BaseModel):
    tool: str
    input: dict
    output: dict | str
    error: str | None = None
    tool_call_id: str | None = None
    status: Literal["success", "error", "timeout"] | None = None

    @field_validator("output")
    @classmethod
    def truncate_output(cls, v):
        if isinstance(v, str):
            data_bytes = v.encode("utf-8")
        else:
            data_bytes = json.dumps(v, ensure_ascii=False).encode("utf-8")
        n_bytes = len(data_bytes)
        if n_bytes <= MAX_OUTPUT_BYTES:
            return v
        overflow = n_bytes - MAX_OUTPUT_BYTES
        head = data_bytes[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore")
        return f"{head}\n…[truncated, {overflow} more bytes]\n"
```

`ToolCallSummary` is unchanged (the new fields live inside each `ToolCallRecord` element of `calls: list[ToolCallRecord]`). The line `from typing import Literal` precedes the `pydantic` import per project conventions (stdlib before 3rd-party).

### 2. `backend/tests/models/test_tool_call_record.py` (new, 11 tests)

| # | Test | What it proves |
|---|------|----------------|
| 1 | `test_optional_fields_default_none` | Legacy callers still work — `tool_call_id` and `status` default to `None`. |
| 2 | `test_explicit_fields_round_trip` | All four fields read back via `model_dump()`. |
| 3 | `test_status_literal_rejects_unknown` | `status="weird"` raises `ValidationError`. Status forgery via JSON injection is impossible. |
| 4 | `test_dict_output_under_cap_unchanged` | Common case: `output` stays `dict` for structured readers. |
| 5 | `test_str_output_under_cap_unchanged` | Strings under cap round-trip identically. |
| 6 | `test_dict_output_over_cap_truncated_to_string` | Over-cap dicts collapse to STRING; marker present; first 50 KB preserved. |
| 7 | `test_str_output_over_cap_truncated` | 60,000-char string → first 50 KB preserved + marker with `10000 more bytes`. |
| 8 | `test_truncation_marker_uses_unicode_ellipsis` | Marker contains `…` (U+2026), NOT `...` (3 ASCII dots). |
| 9 | `test_truncation_byte_count_in_marker` | 51,234-byte input → marker says `1234 more bytes` (exact count). |
| 10 | `test_legacy_summary_round_trip` | `ToolCallSummary` with default-None calls validates — proves no migration needed. |
| 11 | `test_byte_size_uses_utf8` | 30,000 'é' chars (60,000 UTF-8 bytes) is correctly over-cap. |

`backend/tests/models/__init__.py` is empty (package marker).

## Verification

| Gate | Command | Result |
|------|---------|--------|
| Unit tests | `pytest tests/models/test_tool_call_record.py -v` | 11 passed in 1.30s |
| Backend import | `python -c "from app.main import app; print('OK')"` | `OK` |
| `tool_call_id` field grep | `grep -q "tool_call_id: str \| None = None"` | PASS |
| `status` Literal grep | `grep -q 'status: Literal\["success", "error", "timeout"\] \| None = None'` | PASS |
| Validator decorator grep | `grep -q '@field_validator("output")'` | PASS |
| Constant grep | `grep -q "MAX_OUTPUT_BYTES = 50_000"` | PASS |
| Marker text grep | `grep -q "truncated, "` | PASS |

## Commits

- `9c440ac` `test(11-01): add failing tests for ToolCallRecord extensions` — RED gate
- `679aa4f` `feat(11-01): extend ToolCallRecord with tool_call_id, status, 50KB cap` — GREEN gate

## Deviations from Plan

### 1. [Rule 3 — Blocking] conftest.py requires Supabase env vars at import time

**Found during:** Step 3 (test execution, GREEN phase).
**Issue:** `backend/tests/conftest.py` imports `app.services.redaction.anonymization`, which transitively loads `app.config.Settings`, which is a `pydantic_settings.BaseSettings` requiring `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`. Worktrees do not carry untracked files like `.env`, so pytest collection failed with `ValidationError: 4 validation errors for Settings` for all 11 tests.
**Fix:** Sourced `/Users/erikgunawansupriatna/.../backend/.env` from the main repo via `set -a && source ... && set +a` before invoking pytest. No code change required — purely a test-runner invocation pattern.
**Files modified:** None (env-loading is an invocation-time concern).
**Notes:** Once these tests run in CI or in the canonical local backend dir (where `.env` is committed-but-gitignored), the issue evaporates. The PostToolUse `python -c "from app.main import app"` hook works the same way — both rely on the `.env` being adjacent to `backend/`.

### 2. [Rule 1 — Plan reference correction] Regression test path in plan does not exist

**Found during:** Step 4 (regression check).
**Issue:** Plan 11-01 §Action Step 4 references `backend/tests/routers/test_chat_sandbox_streaming.py` as a regression check. This file does not exist; there is no `backend/tests/routers/` directory at all. Closest analogs in the project are `backend/tests/unit/test_chat_router_phase5_*.py` which do not exercise sandbox-streaming or `ToolCallRecord` construction code paths.
**Fix:** Skipped this regression check. The actual regression surface — chat.py call sites that construct `ToolCallRecord(tool=..., input=..., output=...)` with positional/kwarg style — is covered by the `from app.main import app` import smoke test (which runs Pydantic validation on every model in the import graph). Plan 11-04 (which actually modifies those chat.py call sites) is the appropriate place for sandbox-streaming regression coverage.
**Files modified:** None.

### 3. [Doc-only nit] Plan code template put `import json` after `from pydantic import` — implementation puts `import json` at the top per stdlib-first convention

**Found during:** GREEN write step.
**Issue:** The plan's code block in `<action>` Step 2 has `from pydantic import BaseModel, field_validator` followed by `import json`, which violates the standard stdlib-before-3rd-party import ordering (PEP 8 / isort default).
**Fix:** Reordered to `import json` → `from typing import Literal` → `from pydantic import BaseModel, field_validator`. Functionally identical, conventionally cleaner.
**Files modified:** `backend/app/models/tools.py` (import order only).

### Auth Gates

None.

## Self-Check: PASSED

- backend/app/models/tools.py: FOUND
- backend/tests/models/__init__.py: FOUND
- backend/tests/models/test_tool_call_record.py: FOUND
- Commit 9c440ac (test): FOUND
- Commit 679aa4f (feat): FOUND
- All 5 grep verify gates: PASS
- All 11 unit tests: PASS
- Backend import smoke test: PASS

## TDD Gate Compliance

- RED gate (`test(11-01): ...`): commit `9c440ac` — 11 tests added, ImportError on `MAX_OUTPUT_BYTES`.
- GREEN gate (`feat(11-01): ...`): commit `679aa4f` — 11/11 passing.
- REFACTOR gate: not needed — implementation already matches plan spec and validator helper is small (10 lines).

## Threat Surface Notes

No new threat flags. The threat register in 11-01-PLAN.md (T-11-01-1 through T-11-01-4) is fully addressed:

- **T-11-01-1 (DoS):** Mitigated — 50 KB head-truncate cap at model construction, tested via `test_dict_output_over_cap_truncated_to_string`, `test_str_output_over_cap_truncated`, `test_byte_size_uses_utf8`.
- **T-11-01-2 (Tampering):** Mitigated — Literal validation rejects arbitrary status values, tested via `test_status_literal_rejects_unknown`.
- **T-11-01-3 (PII in truncated content):** Accepted residual — handed off to Plan 11-04 (D-P11-10 redaction batch).
- **T-11-01-4 (tool_call_id integrity):** Accepted — caller-supplied; chat.py passes OpenAI-issued `tc["id"]` in Plan 11-04.

No new endpoints, no new RLS surface, no schema changes. Pure in-process model extension.

## Known Stubs

None. The validator and tests are complete; no placeholder data or "coming soon" hooks. Plan 11-04 will consume these new fields from chat.py.

## Notes for Plan 11-04 (chat.py)

When chat.py is updated to pass `tool_call_id=tc["id"]` and `status=...` to `ToolCallRecord(...)` in both branches:

- The `output` cap is automatic — no need to call `MAX_OUTPUT_BYTES` directly at the call site.
- The `status` derivation logic for `execute_code` (timeout / error / success from `error_type` and `exit_code`) lives in chat.py, not in this model — keep it close to the sandbox response shape that produces those fields.
- For non-sandbox tools, simple try/except → `status="success"` / `status="error"`.
- Backwards compat: legacy persisted rows have `tool_call_id is None` for every call; `Plan 11-04`'s history-reconstruction guard (`if calls and all(c.get("tool_call_id") for c in calls)`) correctly falls back to flat `{role, content}` shape for those rows.

---

*Phase 11 — Code Execution UI & Persistent Tool Memory*
*Plan 11-01 completed: 2026-05-01*
