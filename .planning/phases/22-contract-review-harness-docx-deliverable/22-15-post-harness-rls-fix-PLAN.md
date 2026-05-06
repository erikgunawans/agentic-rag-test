---
phase: 22-contract-review-harness-docx-deliverable
plan: 15
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/post_harness.py
  - backend/tests/services/test_post_harness.py
autonomous: true
gap_closure: true
requirements: [CR-08]
must_haves:
  truths:
    - "post_harness._persist_summary inserts a messages row that satisfies the RLS policy 'users can create own messages' (auth.uid() = user_id)"
    - "summarize_harness_run threads user_id from the entrypoint down to _persist_summary"
    - "A regression test exists that asserts the messages insert payload contains user_id (mirrors CR-21-04 commit ed615e6 pattern in gatekeeper)"
  artifacts:
    - path: "backend/app/services/post_harness.py"
      provides: "_persist_summary widened to accept user_id; insert payload includes user_id"
      contains: "\"user_id\": user_id"
    - path: "backend/tests/services/test_post_harness.py"
      provides: "Regression test that asserts user_id is in the messages insert payload"
      contains: "test_persist_summary_includes_user_id"
  key_links:
    - from: "post_harness.summarize_harness_run"
      to: "post_harness._persist_summary"
      via: "user_id keyword argument"
      pattern: "_persist_summary\\([^)]*user_id=user_id"
    - from: "post_harness._persist_summary"
      to: "messages table insert"
      via: "Supabase PostgREST insert with user_id column"
      pattern: "\"user_id\": user_id"
---

<objective>
Close UAT Gap 3 (MAJOR): `post_harness._persist_summary` builds the messages insert payload WITHOUT `user_id`, fails the RLS policy `users can create own messages` (which enforces `auth.uid() = user_id`), and PostgREST returns 42501. The post-harness summary message is silently dropped — user sees streamed delta tokens but no persisted message exists, breaking thread reload-safety. Same shape as Phase 21 issue CR-21-04 (gatekeeper persistence) which was fixed in commit `ed615e6`. The fix pattern is fully proven; we mirror it.

Purpose: Mirror the CR-21-04 fix pattern verbatim in `_persist_summary`. Caller `summarize_harness_run` ALREADY accepts `user_id: str` (post_harness.py:176), so threading it down is mechanical. CLAUDE.md mandates "Every bug fix gets a regression test. Write the test first."
Output: post_harness.py with widened signature + regression test mirroring the existing test_gatekeeper.py:497-505 CR-21-04 assertion.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-HUMAN-UAT.md
@CLAUDE.md
@backend/app/services/post_harness.py
@backend/app/services/gatekeeper.py
@backend/tests/services/test_gatekeeper.py
@backend/tests/services/test_post_harness.py

<interfaces>
<!-- Authoritative source: backend/app/services/post_harness.py:130-164 -->
Current broken _persist_summary:
```python
async def _persist_summary(
    *,
    thread_id: str,
    content: str,
    harness_name: str,
    token: str,
) -> str | None:
    client = get_supabase_authed_client(token)
    try:
        result = client.table("messages").insert({
            "thread_id": thread_id,
            "role": "assistant",
            "content": content,
            "harness_mode": harness_name,
        }).execute()
        return (result.data or [{}])[0].get("id")
    except Exception as exc:
        logger.error(...)
        return None
```

<!-- Authoritative source: backend/app/services/post_harness.py:171-180 -->
summarize_harness_run signature ALREADY has user_id (no change needed at the entrypoint):
```python
async def summarize_harness_run(
    *,
    harness: HarnessDefinition,
    harness_run: dict,
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    registry,
) -> AsyncIterator[dict]:
```

<!-- Authoritative source: backend/app/services/post_harness.py:261-266 -->
Current call site to _persist_summary (does NOT pass user_id — must be widened):
```python
msg_id = await _persist_summary(
    thread_id=thread_id,
    content=full,
    harness_name=harness.name,
    token=token,
)
```

<!-- Authoritative prior-art: backend/app/services/gatekeeper.py:147-200 (commit ed615e6 fix for CR-21-04) -->
The canonical pattern to mirror:
```python
async def _persist_message(
    *,
    thread_id: str,
    user_id: str,                      # required
    role: str,
    content: str,
    harness_name: str,
    token: str,
    parent_message_id: str | None = None,
    chain_to_prev_assistant: bool = False,
) -> str | None:
    """Insert a message row with harness_mode tag. Returns the row id.

    `user_id` is required: the messages RLS policy `users can create own messages`
    enforces `auth.uid() = user_id`. Without it, postgrest raises 42501.
    ...
    """
    ...
    # gatekeeper.py:193 — payload includes user_id
    payload = {
        "thread_id": thread_id,
        "user_id": user_id,            # <-- the fix
        "role": role,
        "content": content,
        "harness_mode": harness_name,
        ...
    }
    result = client.table("messages").insert(payload).execute()
```

<!-- Authoritative prior-art test: backend/tests/services/test_gatekeeper.py:495-505 -->
Existing CR-21-04 regression test pattern (mirror this for post_harness):
```python
for ins in harness_mode_inserts:
    assert ins["harness_mode"] == harness.name
    # CR-21-04 regression: messages RLS policy `users can create own messages`
    # requires `auth.uid() = user_id`. Without `user_id` in the insert payload,
    # postgrest raises 42501 mid-stream and the gatekeeper aborts before
    # emitting any SSE events, surfacing as ERR_INCOMPLETE_CHUNKED_ENCODING
    # to the browser.
    assert ins.get("user_id") == "user-1", (
        f"CR-21-04: gatekeeper insert missing user_id (got {ins!r}) — "
        f"would be blocked by messages RLS policy in production."
    )
```
</interfaces>

<invariants>
- CLAUDE.md: "Every bug fix gets a regression test. Write the test first." — Task 1 = test (RED), Task 2 = fix (GREEN).
- CLAUDE.md: PostToolUse hook auto-runs py_compile + import check on every .py edit; must pass.
- D-22 parent token: token reuse pattern preserved (no new client mint).
- D-16 dark-launch byte-identical OFF-mode: post_harness only runs when a harness completed; OFF-mode unchanged.
- tool_service.py frozen-range invariant preserved (this plan doesn't touch tool_service.py).
- All other call sites in post_harness.py that already use `user_id` (e.g. audit_service.log_action at line 220) keep their existing parameters unchanged.
</invariants>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write regression test FIRST asserting user_id is in messages insert payload</name>
  <read_first>
    - backend/app/services/post_harness.py (full file: focus on _persist_summary at 130-164 and summarize_harness_run at 171-268)
    - backend/tests/services/test_post_harness.py (existing test patterns; especially the test that uses _make_harness, _make_run, _async_iter_chunks, and patches OpenRouterService)
    - backend/tests/services/test_gatekeeper.py (lines 495-505: the CR-21-04 assertion pattern to mirror)
    - backend/app/services/gatekeeper.py (lines 147-200: the canonical user_id-in-payload fix pattern)
  </read_first>
  <files>backend/tests/services/test_post_harness.py</files>
  <action>
APPEND a new test to `backend/tests/services/test_post_harness.py` (do NOT replace existing tests; add at the bottom of the file).

The test must drive `summarize_harness_run` end-to-end with mocked OpenRouter streaming and capture the dict passed to `client.table("messages").insert(...)`. It must assert that `user_id` is present in the payload AND equals the value passed to `summarize_harness_run`.

Test name (load-bearing for grep gates):
`test_persist_summary_includes_user_id`

Approximate test body to append (adapt fixture imports/helpers to match existing file conventions):

```python
# ---------------------------------------------------------------------------
# Test 12: CR-22-15 regression — _persist_summary must include user_id (Gap 3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persist_summary_includes_user_id():
    """Mirrors CR-21-04 (gatekeeper) fix for the post_harness path.

    Failure mode pre-fix: PostgreSQL RLS policy 'users can create own messages'
    enforces auth.uid() = user_id. _persist_summary's insert payload omitted
    user_id, raising 42501 — the post-harness summary was silently dropped.

    Reproduces the exact assertion shape from
    backend/tests/services/test_gatekeeper.py:495-505.
    """
    insert_calls: list[dict] = []

    def mock_get_client(token):
        client = MagicMock()
        # Simulate RLS-scoped behavior: capture the insert payload, return a row id.
        def _capture_insert(payload):
            insert_calls.append(payload)
            chain = MagicMock()
            chain.execute.return_value = MagicMock(data=[{"id": "msg-new"}])
            return chain
        client.table.return_value.insert.side_effect = _capture_insert
        return client

    # Mock OpenRouter streaming with a tiny payload.
    mock_completions = AsyncMock()
    mock_completions.create.return_value = _async_iter_chunks(["Done."])
    mock_or_client = MagicMock()
    mock_or_client.chat.completions = mock_completions

    harness = _make_harness()
    run = _make_run({"echo": {"text": "ok"}})

    with patch("app.services.post_harness.get_supabase_authed_client", side_effect=mock_get_client), \
         patch("app.services.post_harness.openrouter_service.client", mock_or_client), \
         patch("app.services.post_harness.openrouter_service.model", "gpt-4o-mini"):
        events = []
        async for ev in summarize_harness_run(
            harness=harness,
            harness_run=run,
            thread_id="thread-22",
            user_id="user-22",
            user_email="user22@test.com",
            token="tok-22",
            registry=None,
        ):
            events.append(ev)

    # At least one insert into messages should have happened.
    assert insert_calls, "No insert calls captured — _persist_summary did not run"
    persisted = insert_calls[-1]   # the summary insert is the only one in this test

    # CR-22-15 regression (mirrors CR-21-04 in gatekeeper):
    # messages RLS policy `users can create own messages` enforces
    # `auth.uid() = user_id`. Without `user_id` in the insert payload,
    # postgrest raises 42501 and the post-harness summary is silently dropped.
    assert persisted.get("user_id") == "user-22", (
        f"CR-22-15: _persist_summary insert missing user_id (got {persisted!r}) — "
        f"would be blocked by messages RLS policy in production."
    )
    # And the existing fields must remain.
    assert persisted.get("thread_id") == "thread-22"
    assert persisted.get("role") == "assistant"
    assert persisted.get("harness_mode") == harness.name
```

If the existing test file uses a slightly different mock-client construction (e.g. a `_make_supabase_mock` helper), reuse THAT helper instead of re-implementing the mock from scratch. Match the existing style.

Run the new test BEFORE applying the fix in Task 2 — it MUST FAIL with an `AssertionError` saying `user_id missing` (or with KeyError if `persisted.get("user_id") is None`). Capture the failure output for the SUMMARY.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_post_harness.py::test_persist_summary_includes_user_id -x 2>&1 | grep -E "AssertionError|FAILED|user_id" | head -5 || echo "RED-STEP-NOT-CAPTURED"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/tests/services/test_post_harness.py` contains a new function `test_persist_summary_includes_user_id`.
    - The test asserts `persisted.get("user_id") == "user-22"` (or analogous user-id value).
    - Running the test on UNMODIFIED post_harness.py produces an AssertionError or FAILED line (RED step). Capture in the SUMMARY.
    - Existing test count increased by exactly 1 (no existing tests removed — `grep -c "^def test_\|^async def test_" backend/tests/services/test_post_harness.py` increases by 1).
  </acceptance_criteria>
  <done>RED test exists, asserts user_id presence in messages insert payload, and currently fails on the broken code.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Fix _persist_summary — thread user_id through, mirror CR-21-04 commit ed615e6</name>
  <read_first>
    - backend/app/services/post_harness.py (lines 130-164: _persist_summary; lines 171-268: summarize_harness_run + call site at 261-266)
    - backend/app/services/gatekeeper.py (lines 147-200: the canonical _persist_message pattern with user_id docstring; mirror its docstring text precisely)
    - backend/tests/services/test_post_harness.py (the RED test from Task 1)
  </read_first>
  <files>backend/app/services/post_harness.py</files>
  <action>
Edit `backend/app/services/post_harness.py` with TWO changes (both required):

CHANGE 1: Widen `_persist_summary` signature + add user_id to insert payload + add the RLS docstring comment.

OLD (lines ~130-164):
```python
async def _persist_summary(
    *,
    thread_id: str,
    content: str,
    harness_name: str,
    token: str,
) -> str | None:
    """Insert a summary assistant message row with harness_mode tag.

    Args:
        thread_id:   Thread UUID.
        content:     Full summary text.
        harness_name: Value for messages.harness_mode (D-04, POST-03).
        token:       JWT for RLS-scoped Supabase client.

    Returns:
        The new row's id, or None if insert failed.
    """
    client = get_supabase_authed_client(token)
    try:
        result = client.table("messages").insert({
            "thread_id": thread_id,
            "role": "assistant",
            "content": content,
            "harness_mode": harness_name,
        }).execute()
        return (result.data or [{}])[0].get("id")
    except Exception as exc:
        logger.error(
            "post_harness: persist failed thread=%s exc=%s",
            thread_id,
            exc,
            exc_info=True,
        )
        return None
```

NEW:
```python
async def _persist_summary(
    *,
    thread_id: str,
    user_id: str,
    content: str,
    harness_name: str,
    token: str,
) -> str | None:
    """Insert a summary assistant message row with harness_mode tag.

    `user_id` is required (CR-22-15 / mirrors CR-21-04 fix in gatekeeper.py):
    the messages RLS policy `users can create own messages` enforces
    `auth.uid() = user_id`. Without it, postgrest raises 42501 and the
    post-harness summary is silently dropped.

    Args:
        thread_id:   Thread UUID.
        user_id:     Supabase auth.users UUID — REQUIRED for RLS.
        content:     Full summary text.
        harness_name: Value for messages.harness_mode (D-04, POST-03).
        token:       JWT for RLS-scoped Supabase client.

    Returns:
        The new row's id, or None if insert failed.
    """
    client = get_supabase_authed_client(token)
    try:
        result = client.table("messages").insert({
            "thread_id": thread_id,
            "user_id": user_id,
            "role": "assistant",
            "content": content,
            "harness_mode": harness_name,
        }).execute()
        return (result.data or [{}])[0].get("id")
    except Exception as exc:
        logger.error(
            "post_harness: persist failed thread=%s exc=%s",
            thread_id,
            exc,
            exc_info=True,
        )
        return None
```

CHANGE 2: Update the call site in `summarize_harness_run` to pass `user_id`.

OLD (around line 261-266):
```python
msg_id = await _persist_summary(
    thread_id=thread_id,
    content=full,
    harness_name=harness.name,
    token=token,
)
```

NEW:
```python
msg_id = await _persist_summary(
    thread_id=thread_id,
    user_id=user_id,
    content=full,
    harness_name=harness.name,
    token=token,
)
```

Do NOT modify any other code in post_harness.py. The egress filter, audit log, error path, and SSE shape are all unchanged. The only mutations are:
1. `_persist_summary` signature widened by one keyword arg.
2. `_persist_summary` insert payload includes `"user_id": user_id`.
3. `_persist_summary` docstring updated with the CR-22-15/CR-21-04 RLS comment (mirroring gatekeeper.py:160-161).
4. `summarize_harness_run` call site passes `user_id=user_id`.

After the edit, run:
```
cd backend && source venv/bin/activate && \
  pytest tests/services/test_post_harness.py -v
```
Expected: test_persist_summary_includes_user_id is now GREEN (along with the existing 11 tests). PostToolUse hook will run py_compile + app-import check.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.post_harness import _persist_summary, summarize_harness_run; import inspect; sig = inspect.signature(_persist_summary); assert 'user_id' in sig.parameters, f'user_id missing from signature: {list(sig.parameters)}'; print('SIG_OK')" && grep -q '"user_id": user_id' app/services/post_harness.py && grep -q "user_id=user_id" app/services/post_harness.py && pytest tests/services/test_post_harness.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `inspect.signature(_persist_summary).parameters` contains `user_id` (asserted via the python one-liner above).
    - `grep -q '"user_id": user_id' backend/app/services/post_harness.py` exits 0 (insert payload includes user_id).
    - `grep -q 'user_id=user_id' backend/app/services/post_harness.py` exits 0 (call site passes it).
    - `grep -q "CR-22-15\|CR-21-04" backend/app/services/post_harness.py` exits 0 (RLS docstring comment present and references the prior-art fix).
    - `pytest backend/tests/services/test_post_harness.py -v` reports test_persist_summary_includes_user_id PASSED + all existing tests still PASSED (count check: 11 prior + 1 new = 12 passed).
    - `python -c "from app.main import app; print('OK')"` succeeds (app boots).
    - tool_service.py frozen-range SHA still matches `cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2`.
  </acceptance_criteria>
  <done>_persist_summary now accepts user_id, payload includes user_id, call site passes it, regression test GREEN, no existing tests regressed, app boots.</done>
</task>

</tasks>

<verification>
- Signature widened with user_id keyword.
- Insert payload includes "user_id": user_id.
- Call site in summarize_harness_run passes user_id=user_id.
- Docstring references CR-22-15/CR-21-04 prior-art so future readers understand why.
- Regression test exists and is GREEN.
- All 11 existing post_harness tests still GREEN (12 total).
- App imports cleanly.
- tool_service.py frozen-range invariant preserved.
</verification>

<success_criteria>
- [ ] backend/tests/services/test_post_harness.py contains test_persist_summary_includes_user_id
- [ ] RED step captured (test fails before fix; output saved in SUMMARY)
- [ ] _persist_summary signature has user_id parameter
- [ ] Insert payload includes "user_id": user_id
- [ ] Call site passes user_id=user_id
- [ ] Docstring documents the RLS requirement (mirrors gatekeeper.py:160-161)
- [ ] All 12 post_harness tests GREEN
- [ ] app.main imports cleanly
- [ ] tool_service.py SHA invariant preserved
</success_criteria>

<output>
After completion, write `.planning/phases/22-contract-review-harness-docx-deliverable/22-15-SUMMARY.md` documenting:
- The captured RED-step failure output (AssertionError text)
- The diff of post_harness.py (signature widened + 1 new line in insert payload + 1 line at call site + docstring update)
- Pytest GREEN summary
- Confirmation that the fix mirrors the canonical CR-21-04 pattern from commit ed615e6
</output>
