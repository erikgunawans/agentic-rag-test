---
phase: 22-contract-review-harness-docx-deliverable
plan: 15
subsystem: backend/post-harness
tags: [rls-fix, tdd, gap-closure, messages-insert]
dependency_graph:
  requires: []
  provides: [post_harness._persist_summary includes user_id in messages insert]
  affects: [post_harness.summarize_harness_run, messages table RLS]
tech_stack:
  added: []
  patterns: [user_id in messages insert payload (mirrors gatekeeper.py CR-21-04 pattern)]
key_files:
  created:
    - backend/tests/services/test_post_harness.py (test_persist_summary_includes_user_id added)
  modified:
    - backend/app/services/post_harness.py (_persist_summary widened + call site updated)
decisions:
  - Mirror CR-21-04 fix shape exactly (authed client, no service-role switch) — same trust boundary
  - Thread user_id through summarize_harness_run -> _persist_summary (no new parameter added at outer entrypoint, already present)
metrics:
  duration: 152s
  completed: 2026-05-06T02:13:44Z
  tasks_completed: 2
  files_changed: 2
---

# Phase 22 Plan 15: Post-Harness RLS Fix Summary

**One-liner:** Threaded `user_id` through `_persist_summary` so the messages-table insert satisfies the `auth.uid() = user_id` RLS policy — mirrors the CR-21-04 fix from `gatekeeper.py` commit `ed615e6`.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Write failing regression test (RED) | `5c41c30` | `backend/tests/services/test_post_harness.py` |
| 2 | Fix `_persist_summary` — thread user_id (GREEN) | `4536c87` | `backend/app/services/post_harness.py` |

## RED Step Output

```
FAILED tests/services/test_post_harness.py::test_persist_summary_includes_user_id
AssertionError: CR-22-15: _persist_summary insert missing user_id (got {'thread_id': 'thread-22',
'role': 'assistant', 'content': 'Done.', 'harness_mode': 'smoke-echo'}) — would be blocked by
messages RLS policy in production.
assert None == 'user-22'
```

Test confirmed failing on unmodified code before any fix was applied.

## GREEN Step Output

```
12 passed, 1 warning in 0.74s
tests/services/test_post_harness.py::test_persist_summary_includes_user_id PASSED
```

All 11 prior tests remain PASSED. New test also PASSED.

## post_harness.py Diff Summary

**Change 1 — `_persist_summary` signature widened + insert payload + docstring:**

```python
# BEFORE
async def _persist_summary(
    *,
    thread_id: str,
    content: str,
    harness_name: str,
    token: str,
) -> str | None:
    ...
    result = client.table("messages").insert({
        "thread_id": thread_id,
        "role": "assistant",
        "content": content,
        "harness_mode": harness_name,
    }).execute()

# AFTER
async def _persist_summary(
    *,
    thread_id: str,
    user_id: str,                      # <-- added (CR-22-15)
    content: str,
    harness_name: str,
    token: str,
) -> str | None:
    """`user_id` is required (CR-22-15 / mirrors CR-21-04 fix in gatekeeper.py):
    the messages RLS policy `users can create own messages` enforces
    `auth.uid() = user_id`. Without it, postgrest raises 42501..."""
    ...
    result = client.table("messages").insert({
        "thread_id": thread_id,
        "user_id": user_id,            # <-- added (CR-22-15)
        "role": "assistant",
        "content": content,
        "harness_mode": harness_name,
    }).execute()
```

**Change 2 — `summarize_harness_run` call site:**

```python
# BEFORE
msg_id = await _persist_summary(
    thread_id=thread_id,
    content=full,
    harness_name=harness.name,
    token=token,
)

# AFTER
msg_id = await _persist_summary(
    thread_id=thread_id,
    user_id=user_id,                   # <-- added (CR-22-15)
    content=full,
    harness_name=harness.name,
    token=token,
)
```

## CR-21-04 Mirror Confirmation

Fix shape mirrors `ed615e6` (gatekeeper.py) exactly:
- Same client: `get_supabase_authed_client(token)` (no service-role switch)
- Same fix: `"user_id": user_id` added to the insert payload dict
- Same docstring pattern: RLS policy explanation + prior-art reference
- Same test pattern: capture insert payload, assert `persisted.get("user_id") == <expected>`

## Acceptance Criteria Verification

| Check | Result |
|-------|--------|
| `inspect.signature(_persist_summary)` contains `user_id` | PASS (SIG_OK) |
| `grep '"user_id": user_id' post_harness.py` | PASS (PAYLOAD_OK) |
| `grep 'user_id=user_id' post_harness.py` | PASS (CALLSITE_OK) |
| `grep 'CR-22-15\|CR-21-04' post_harness.py` | PASS (DOCSTRING_OK) |
| All 12 post_harness tests PASSED | PASS |
| `python -c "from app.main import app; print('OK')"` | PASS |
| `tool_service.py` frozen-range SHA | PASS (`cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2`) |

## Deviations from Plan

None — plan executed exactly as written.

**Pre-existing failures (out of scope, not introduced by this plan):**
- `tests/api/test_chat_skill_catalog.py::test_chat_router_imports_build_skill_catalog_block` — failing before and after these changes (confirmed by git stash check). Unrelated to post_harness.py.
- `tests/integration/test_phase20_e2e_smoke.py::test_sc5_engine_writes_agent_todos_with_harness_prefix` — caused by uncommitted `harness_engine.py` changes from plan 22-14 in the worktree. Not introduced by this plan.

Both pre-existing failures have been logged to `deferred-items.md` scope note: outside this plan's blast radius.

## Known Stubs

None — the fix is complete. `user_id` is now included in every `_persist_summary` call.

## Self-Check: PASSED

- `backend/app/services/post_harness.py` — exists with fix applied
- `backend/tests/services/test_post_harness.py` — exists with `test_persist_summary_includes_user_id`
- Commit `5c41c30` — exists (RED)
- Commit `4536c87` — exists (GREEN)
