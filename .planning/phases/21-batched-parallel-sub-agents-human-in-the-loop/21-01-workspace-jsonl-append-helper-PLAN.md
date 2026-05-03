---
phase: 21-batched-parallel-sub-agents-human-in-the-loop
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/workspace_service.py
  - backend/tests/services/test_workspace_service_append_line.py
autonomous: true
requirements:
  - BATCH-05  # JSONL append-only output is the resume artifact (D-05)
  - BATCH-07  # Atomic per-line append is what makes mid-batch resume safe (D-07)
must_haves:
  truths:
    - "WorkspaceService exposes async append_line(thread_id, file_path, line) that DB-atomically appends `line + '\\n'` to the file's `content` column."
    - "If the row does not yet exist for (thread_id, file_path), append_line creates it with content = `line + '\\n'` (first-write semantics — no separate write needed before first append). The not-yet-exists case is detected via existing read_file's `{error: 'file_not_found'}` contract — verified at line 293 of workspace_service.py."
    - "Path validation reuses validate_workspace_path — rejects path traversal, leading slash, backslash, paths >500 chars."
    - "Cumulative size cap of MAX_TEXT_CONTENT_BYTES (1 MB) is enforced — call returns {error: 'content_too_large', limit_bytes: 1048576, file_path} when adding `line + '\\n'` would exceed cap."
    - "Return shape on success: {ok: True, operation: 'append', size_bytes: <new total>, file_path: <path>}."
    - "Return shape on path/validation/db error mirrors existing write_text_file convention: {error: '<code>', detail: '<msg>', file_path: <path>}."
    - "Per-(thread_id, file_path) asyncio.Lock is keyed identity-stable: _get_append_lock(thread_id, path) returns the SAME asyncio.Lock instance on every call for the same (thread_id, path) tuple — verified by Test 6."
  artifacts:
    - path: "backend/app/services/workspace_service.py"
      provides: "append_line() method on WorkspaceService"
      contains: "async def append_line"
    - path: "backend/tests/services/test_workspace_service_append_line.py"
      provides: "Pytest coverage of 6 cases (first-write, append-existing, path-invalid, size-cap, db-error, per-key-lock identity)"
      contains: "test_append_line_first_write"
  key_links:
    - from: "WorkspaceService.append_line"
      to: "workspace_files row"
      via: "supabase RPC ws_append_line OR read-then-upsert under per-(thread,path) asyncio.Lock"
      pattern: "ws_append_line|append_line"
---

<objective>
Add a single new method `WorkspaceService.append_line(thread_id, file_path, line)` that atomically appends `line + '\n'` to a workspace text file's `content`. This is the foundational primitive for Phase 21's `llm_batch_agents` JSONL resume artifact (D-05/D-07): each completed sub-agent appends one JSON object as a newline-terminated line, the file grows monotonically, and resume reads the JSONL to compute `done_set`.

Purpose: Concurrent batch sub-agents (asyncio.gather over `run_sub_agent_loop` invocations) MUST each append one line without overwriting peers. A naive `read_file → concat → write_text_file` round-trip is racy; this plan ships the atomic primitive once so 21-03 can call it freely from inside the asyncio.Queue fan-in.
Output: One new method + 6 unit tests + an atomic-commit. No call sites yet.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-CONTEXT.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md
@CLAUDE.md
@backend/app/services/workspace_service.py
@backend/tests/services/test_workspace_service.py

<interfaces>
<!-- Extracted from workspace_service.py — append_line MUST mirror these conventions verbatim. -->

From backend/app/services/workspace_service.py:
```python
MAX_TEXT_CONTENT_BYTES = 1024 * 1024  # 1 MB per WS-03 / D-06 (line 38)

class WorkspaceService:
    def __init__(self, *, token: str): ...

    async def write_text_file(
        self,
        thread_id: str,
        file_path: str,
        content: str,
        source: str = "agent",
    ) -> dict:
        """Returns {ok: True, operation: 'write', size_bytes: N, file_path}
        OR {error: 'content_too_large'|'invalid_path'|'db_error', detail, ...}."""

    async def read_file(self, thread_id: str, file_path: str) -> dict:
        """Returns {content: str, source: str, size_bytes: int}
        OR {error: 'file_not_found'|'invalid_path'|'db_error', detail, file_path}.
        — VERIFIED at line 293: returns `{"error": "file_not_found", "file_path": file_path}`
          (NOT 'not_found'). append_line MUST treat 'file_not_found' as the empty-file case."""

# validate_workspace_path lives at lines 64-129 — reused as-is.
```

From backend/tests/services/test_workspace_service.py:
- Mock pattern: `MagicMock` on `_client.table("workspace_files").upsert(...).execute()`
- Asserts on the upsert payload's keys (thread_id, file_path, content, ...).
- Path-validation tests use bad paths and assert `error == "invalid_path"`.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add WorkspaceService.append_line with atomic semantics + size-cap enforcement (RED → GREEN)</name>
  <files>backend/app/services/workspace_service.py, backend/tests/services/test_workspace_service_append_line.py</files>
  <read_first>
    - backend/app/services/workspace_service.py — full file. Read `MAX_TEXT_CONTENT_BYTES` (line 38), `validate_workspace_path` (lines 64-129), `write_text_file` (lines 193-261), `read_file` (lines 267-324). Append_line MUST mirror error-shape conventions verbatim.
    - backend/app/services/workspace_service.py — specifically grep `read_file` for the not-found error code path. The exact contract (verified during planning) is `{"error": "file_not_found", "file_path": file_path}` at line 293. append_line treats `existing["error"] == "file_not_found"` as the empty-content case (NOT a hard error).
    - backend/tests/services/test_workspace_service.py — read the existing test file end-to-end. Reuse its `MagicMock` upsert/select fixture pattern; do NOT introduce a new mocking style.
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md — section "workspace_service.py — JSONL append (verify or add `append_line`)" (lines 358-385). Confirms the recommended Option B atomic helper.
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-CONTEXT.md — D-05 (JSONL line shape), D-07 (resume reads file via read_file, parses line-by-line).
  </read_first>
  <behavior>
    - Test 1: `test_append_line_first_write` — file does not exist; append_line writes `'foo\n'`; assert returned `{ok: True, operation: 'append', size_bytes: 4, file_path: 'x.jsonl'}`.
    - Test 2: `test_append_line_appends_to_existing` — file has content `'a\n'` (size 2); append_line('b') writes total `'a\nb\n'`; assert returned `size_bytes: 4`.
    - Test 3: `test_append_line_rejects_invalid_path` — path `'../escape.jsonl'`; assert returned `{error: 'invalid_path', ...}`.
    - Test 4: `test_append_line_enforces_size_cap` — pre-existing content size = MAX_TEXT_CONTENT_BYTES - 1; append_line('foo') (which would add 4 bytes); assert returned `{error: 'content_too_large', limit_bytes: 1048576, file_path: ...}` and NO upsert/RPC was issued.
    - Test 5: `test_append_line_db_error` — mock raises Exception; assert returned `{error: 'db_error', detail: <str>, file_path: ...}`.
    - Test 6: `test_append_line_serializes_via_per_key_lock` — assert `WorkspaceService._get_append_lock(thread_id, path) is WorkspaceService._get_append_lock(thread_id, path)` (same lock instance returned for same key — proves the cache map keys correctly). Then fire 5 concurrent `append_line('x')` against the same (thread, path) using `asyncio.gather`; with a stateful read_file/write_text_file mock that simulates the DB row, assert final content is `'x\nx\nx\nx\nx\n'` (5 lines, no overwrites). The test's intent is to confirm per-(thread,path) lock identity AND in-process serialization. NOTE: this test does NOT prove cross-process atomicity — that is deferred to v1.0 D-31 (single-worker Railway today; pg_advisory_xact_lock upgrade path documented in STATE.md).
  </behavior>
  <action>
    Implement the method using a per-(thread_id, file_path) `asyncio.Lock` cached on a class-level dict (Option A from PATTERNS.md — simplest within v1.3 single-worker scope; matches Phase 1 D-31 carryover).

    Concrete signature in `backend/app/services/workspace_service.py`, append AFTER `read_file` (around line 325):

    ```python
    # Class-level lock map — keyed by (thread_id, file_path). Per v1.0 D-31 carryover,
    # this is single-worker only; cross-process atomicity will be added when scale-out
    # happens (deferred to post-MVP per .planning/STATE.md).
    _append_locks: dict[tuple[str, str], asyncio.Lock] = {}

    @classmethod
    def _get_append_lock(cls, thread_id: str, file_path: str) -> asyncio.Lock:
        key = (thread_id, file_path)
        if key not in cls._append_locks:
            cls._append_locks[key] = asyncio.Lock()
        return cls._append_locks[key]

    async def append_line(
        self,
        thread_id: str,
        file_path: str,
        line: str,
    ) -> dict:
        """Atomically append `line + '\\n'` to the workspace text file at file_path.

        Phase 21 BATCH-05/D-05: each batch sub-agent appends one JSON object per line.
        Concurrent appends to the same (thread_id, file_path) are serialized via a
        per-key asyncio.Lock so the file grows monotonically without overwrite.

        Returns:
            {"ok": True, "operation": "append", "size_bytes": int, "file_path": str}
            OR {"error": <code>, "detail": str, "file_path": str}
        """
        # 1. Path validation (reuse validate_workspace_path)
        validation = validate_workspace_path(file_path)
        if "error" in validation:
            return {**validation, "file_path": file_path}

        # 2. Construct the new line (always newline-terminated per D-05)
        new_segment = line if line.endswith("\n") else line + "\n"
        new_segment_bytes = len(new_segment.encode("utf-8"))

        # 3. Acquire per-key lock — serializes concurrent appends within this worker
        lock = self._get_append_lock(thread_id, file_path)
        async with lock:
            # 4. Read existing content (or empty if not yet created — verified contract:
            #    read_file returns {"error": "file_not_found"} when no row exists)
            existing = await self.read_file(thread_id, file_path)
            if "error" in existing and existing["error"] != "file_not_found":
                return {
                    "error": existing["error"],
                    "detail": existing.get("detail", "read failed"),
                    "file_path": file_path,
                }
            current_content = existing.get("content", "") if "error" not in existing else ""
            current_bytes = len(current_content.encode("utf-8"))

            # 5. Size-cap check BEFORE write (consistent with write_text_file:212)
            new_total = current_bytes + new_segment_bytes
            if new_total > MAX_TEXT_CONTENT_BYTES:
                return {
                    "error": "content_too_large",
                    "limit_bytes": MAX_TEXT_CONTENT_BYTES,
                    "file_path": file_path,
                    "detail": (
                        f"append would produce {new_total} bytes (limit {MAX_TEXT_CONTENT_BYTES})"
                    ),
                }

            # 6. Write via existing write_text_file (preserves source, RLS, etc.)
            new_content = current_content + new_segment
            write_result = await self.write_text_file(
                thread_id, file_path, new_content, source="harness"
            )
            if "error" in write_result:
                return {
                    "error": write_result["error"],
                    "detail": write_result.get("detail", "write failed"),
                    "file_path": file_path,
                }

            return {
                "ok": True,
                "operation": "append",
                "size_bytes": new_total,
                "file_path": file_path,
            }
    ```

    Add the corresponding test file at `backend/tests/services/test_workspace_service_append_line.py`. Mirror the mocking style of `backend/tests/services/test_workspace_service.py`. Use `pytest.mark.asyncio` and `pytest_asyncio.fixture` consistent with the rest of the suite.

    Test 6 (per-key lock + concurrent serialization):
    - First, assert lock identity: `assert WorkspaceService._get_append_lock("t", "p.jsonl") is WorkspaceService._get_append_lock("t", "p.jsonl")`.
    - Second, use a stateful mock — track a shared `content` string in a closure, have `read_file` return it (with `{"error": "file_not_found"}` when empty per the verified contract) and `write_text_file` overwrite it. Fire 5 concurrent appends via `asyncio.gather`. Assert final content has 5 lines, all `'x'`.

    Run order:
    1. RED: write tests first; run `cd backend && source venv/bin/activate && pytest tests/services/test_workspace_service_append_line.py -x`. ALL must fail (method does not exist).
    2. GREEN: implement append_line; rerun. ALL must pass.
    3. Commit via gsd-sdk: `gsd-sdk query commit "feat(21-01): add WorkspaceService.append_line atomic JSONL primitive" --files backend/app/services/workspace_service.py backend/tests/services/test_workspace_service_append_line.py`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_workspace_service_append_line.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "async def append_line" backend/app/services/workspace_service.py` returns >= 1.
    - `grep -c "_get_append_lock\|_append_locks" backend/app/services/workspace_service.py` returns >= 2 (class-level lock map + accessor).
    - `grep -c "MAX_TEXT_CONTENT_BYTES" backend/app/services/workspace_service.py` returns >= 2 (existing in write_text_file + new in append_line).
    - `grep -c "validate_workspace_path" backend/app/services/workspace_service.py` returns >= 2 (existing call sites + new in append_line).
    - `grep -c '"file_not_found"' backend/app/services/workspace_service.py` returns >= 2 (existing read_file producer + new append_line consumer).
    - `pytest backend/tests/services/test_workspace_service_append_line.py` exits 0 with all 6 tests collected and passing.
    - `pytest backend/tests/services/test_workspace_service.py` exits 0 (no regression in pre-existing tests).
    - `cd backend && python -c "from app.services.workspace_service import WorkspaceService; assert hasattr(WorkspaceService, 'append_line'); print('OK')"` prints `OK`.
  </acceptance_criteria>
  <done>
    `WorkspaceService.append_line` exists with atomic semantics, all 6 tests pass (including per-key lock identity assertion), no regression in workspace_service tests, single atomic commit landed.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| caller (harness engine) → WorkspaceService | trusted same-process call, but path string is data-origin (could be malicious if ever exposed via user input) |
| WorkspaceService → Supabase Postgres | RLS-scoped DB write under user JWT; egress not applicable (no LLM payload) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-21-01-01 | Tampering | append_line file_path arg | mitigate | Reuse validate_workspace_path (rejects `..`, leading `/`, backslash, >500 chars) — same defense as write_text_file. |
| T-21-01-02 | Denial-of-Service | append_line size growth | mitigate | Enforce MAX_TEXT_CONTENT_BYTES cap BEFORE write (no DB call if would exceed); same cap as write_text_file. |
| T-21-01-03 | Race / data corruption | concurrent appends from asyncio.gather | mitigate | Per-(thread_id, file_path) asyncio.Lock serializes appends within a single worker. Cross-process upgrade carried as v1.0 D-31 deferred (single-worker Railway today; `pg_advisory_xact_lock(hashtext(thread_id))` upgrade path documented in STATE.md). |
| T-21-01-04 | Information disclosure | error detail leakage | accept | `detail` strings are short, non-sensitive workspace-internal state. No PII or credentials in error path. |
</threat_model>

<verification>
- All 6 unit tests in `test_workspace_service_append_line.py` pass.
- Pre-existing `test_workspace_service.py` tests unchanged and still pass (no regression).
- `from app.main import app` imports clean (PostToolUse hook will run automatically).
- Atomic commit `feat(21-01): add WorkspaceService.append_line atomic JSONL primitive` landed.
</verification>

<success_criteria>
WorkspaceService.append_line is callable, atomic per-(thread, path), respects 1MB cap, mirrors error-shape conventions, with 6 passing tests and no regression in the rest of the workspace_service test suite.
</success_criteria>

<output>
After completion, create `.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-01-SUMMARY.md`
</output>
</content>
</invoke>