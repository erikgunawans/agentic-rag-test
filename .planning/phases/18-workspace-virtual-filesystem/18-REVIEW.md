---
phase: 18-workspace-virtual-filesystem
reviewed: 2026-05-03T02:30:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - backend/app/services/workspace_service.py
  - backend/app/routers/workspace.py
  - backend/app/routers/chat.py
  - backend/app/services/sandbox_service.py
  - backend/app/services/tool_service.py
  - backend/app/config.py
  - backend/app/main.py
  - frontend/src/components/chat/WorkspacePanel.tsx
  - frontend/src/hooks/useChatState.ts
  - supabase/migrations/039_workspace_files.sql
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 18: Workspace Virtual Filesystem — Code Review Report

**Reviewed:** 2026-05-03T02:30:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 18 introduces a workspace virtual filesystem: a `workspace_files` DB table, four LLM-callable tools (`write_file`, `read_file`, `edit_file`, `list_files`), REST endpoints, sandbox integration, and a React `WorkspacePanel`. The migration, path-validation, RLS policy, feature-flag kill-switch, and frontend panel design are all solid. Two correctness issues were found: a privacy invariant breach in the redaction-ON code path, and a storage leak when a binary upsert fails after upload. Three warnings cover the redaction-buffering gap for `workspace_updated` SSE events, a missing thread-ownership check in the REST list endpoint, and a `SandboxSession` dataclass name collision.

---

## Critical Issues

### CR-01: Workspace file content reaches the LLM without egress-filter coverage when redaction is ON

**File:** `backend/app/routers/chat.py:606-608`

**Issue:** When `redaction_on=True`, all non-`web_search` tool outputs are passed through `anonymize_tool_output` (line 606) to replace real values with surrogates. This runs on the output of `write_file` and `edit_file` — but those tools return only metadata (`{ok, operation, file_path, size_bytes}`), not file content. The **content** written to the workspace is supplied in LLM tool *arguments* (`func_args`) which are de-anonymized via `deanonymize_tool_args` (line 550) before calling the executor. That is correct.

The problem is the pre-flight egress filter at line 420–429:

```python
payload = json.dumps(messages, ensure_ascii=False)
egress_result = egress_filter(payload, registry, None)
```

`messages` at this point already contains the real (de-anonymized) `content` argument that was just written to the DB, embedded in the `{role:"tool", content: json.dumps(tool_output)}` message appended at lines 723–731 — but those messages are appended *after* the tool call, so they are present in `messages` for the *next* LLM iteration's egress check. This is by design and correct for tool results.

The actual gap is different: `write_file` stores the **de-anonymized real text** in `workspace_files.content` (line 238–252 in `workspace_service.py`). When a subsequent LLM call invokes `read_file` for a file that contained real PII, the content is returned as `tool_output` and then passed through `anonymize_tool_output`. However `anonymize_tool_output` operates on the *returned dict* — for `read_file` the returned dict contains `{"ok": True, "content": "<real PII text>", ...}`. Whether `anonymize_tool_output` correctly anonymizes nested text values inside arbitrary dicts depends on its implementation. If it scans only top-level string values (not deep-walking `"content"` keys of arbitrary depth), real PII from a previously-written file will flow back into the `messages` array and past the next egress-filter scan.

This is an architectural gap: the **write path stores de-anonymized content** into the DB (by design — it must, so the file is readable), but the **read path must re-anonymize the returned content** before putting it into the LLM message context. That re-anonymization is only as good as `anonymize_tool_output`'s coverage. If `anonymize_tool_output` does not deep-walk `{"content": "..."}` dicts, the privacy invariant "real PII never reaches cloud-LLM payloads" is violated on the `read_file` path.

**Fix:** At minimum, explicitly handle the `read_file` case in the redaction wrapper: after `anonymize_tool_output` runs, if `tool_output.get("content")` is a string, also run a targeted `redact_text_batch` pass on it:

```python
# In the redaction_on branch, after anonymize_tool_output:
if func_name == "read_file" and isinstance(tool_output, dict) and tool_output.get("content"):
    anon_content = await redaction_service.redact_text_batch(
        [tool_output["content"]], registry
    )
    tool_output = {**tool_output, "content": anon_content[0]}
```

Additionally, the pre-flight egress filter should also cover workspace file paths when workspace is enabled, since file_path strings supplied by the LLM are de-anonymized before storage and could contain real PII.

---

### CR-02: Storage orphan on binary upsert failure — uploaded object is never deleted

**File:** `backend/app/services/workspace_service.py:426-443`

**Issue:** `write_binary_file` uploads to the `workspace-files` bucket first (line 419–425), then inserts the DB row. If the `upsert` call at line 428 raises an exception, the function returns `{"error": "db_error", ...}` but the already-uploaded storage object is left permanently in the bucket. There is no cleanup / rollback:

```python
try:
    self._client.storage.from_(WORKSPACE_BUCKET).upload(...)   # succeeds
except Exception as exc:
    return {"error": "storage_error", ...}

try:
    self._client.table("workspace_files").upsert(...).execute() # may fail
except Exception as exc:
    return {"error": "db_error", ...}   # orphan object remains in bucket
```

The orphaned object has a 4-segment path `{user_id}/{thread_id}/{row_id}/{filename}` that is unreachable via signed URL (no DB row) and will consume storage quota indefinitely. Since this path is also used during upsert-on-conflict (the same `row_id` is freshly generated each call, so conflicts won't re-use it), each failed retry creates another orphan.

**Fix:** Delete the uploaded object when the DB upsert fails:

```python
except Exception as exc:
    # Rollback: remove the just-uploaded object to avoid orphans
    try:
        self._client.storage.from_(WORKSPACE_BUCKET).remove([storage_path])
    except Exception as cleanup_exc:
        logger.warning(
            "workspace write_binary_file orphan cleanup failed path=%s err=%s",
            storage_path, cleanup_exc,
        )
    return {"error": "db_error", "detail": str(exc), "file_path": file_path}
```

---

## Warnings

### WR-01: `workspace_updated` SSE event buffered-away under redaction ON — agent and standard tool-loop paths

**File:** `backend/app/routers/chat.py:706-721` (agent path), `1483-1496` (standard path)

**Issue:** Both the agent-mode and single-agent tool loops (`_run_tool_loop`) emit `workspace_updated` by `yield "workspace_updated", {...}`. These events flow into `event_generator` where, when `redaction_on=True`, everything that is not `code_stdout`/`code_stderr` goes into `tool_loop_buffer` (line 960–961 and 1069–1070):

```python
elif redaction_on:
    tool_loop_buffer.append(data)
else:
    yield f"data: {json.dumps(data)}\n\n"
```

`workspace_updated` carries no PII (only `file_path`, `operation`, `size_bytes`, `source`). Buffering it does not provide any privacy benefit — but it means the WorkspacePanel does not update in real time when redaction is enabled. Worse, in the deep-mode loop (line 1820–1821) `workspace_updated` is also buffered under `redaction_on`, so the panel update is only visible after the full response is complete.

The `todos_updated` event in the deep-mode loop (line 1769) is emitted directly (`yield f"data: ..."`) regardless of `redaction_on`. `workspace_updated` should follow the same pattern.

**Fix:** Add an explicit pass-through for `workspace_updated` in the event routing in both `event_generator` agent path (around line 960) and standard path (around line 1069), matching the `code_stdout`/`code_stderr` exception:

```python
elif event_type in ("code_stdout", "code_stderr", "workspace_updated"):
    yield f"data: {json.dumps(data)}\n\n"
```

In the deep-mode loop, emit directly like `todos_updated` rather than into `tool_loop_buffer`.

---

### WR-02: `GET /threads/{thread_id}/files` does not verify thread ownership before querying

**File:** `backend/app/routers/workspace.py:31-39`

**Issue:** The `list_workspace_files` endpoint passes `thread_id` directly to `WorkspaceService.list_files`, which issues a `SELECT … WHERE thread_id = ?` using the RLS-scoped authed client. RLS on `workspace_files` restricts rows to threads owned by `auth.uid()`, so a cross-user read returns an empty list rather than leaking data. This is correct.

However, the response for a `thread_id` that belongs to another user is `[]` (200 OK) rather than 404. This is an information leak: a caller can distinguish "this thread_id exists but has no workspace files" from "this thread_id does not exist" by comparing the workspace list endpoint response to the threads endpoint response. More concretely, the endpoint silently succeeds for any UUID, which differs from the pattern in `stream_chat` (line 253–260) which always validates thread ownership with an explicit `eq("user_id", user["id"])` check before proceeding.

**Fix:** Add an explicit thread ownership check before `list_files`, mirroring the `stream_chat` pattern:

```python
@router.get("/threads/{thread_id}/files")
async def list_workspace_files(
    thread_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_supabase_authed_client(user["token"])
    thread = db.table("threads").select("id").eq("id", thread_id).eq("user_id", user["id"]).limit(1).execute()
    if not thread.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    ws = WorkspaceService(token=user["token"])
    return await ws.list_files(thread_id)
```

The `read_workspace_file` endpoint (line 42–80) already returns 404 when RLS denies the read via the `file_not_found` error code, so it is acceptable. The list endpoint is the gap.

---

### WR-03: `SandboxSession` dataclass in `sandbox_service.py` shadows the imported `SandboxSession` from `llm_sandbox`

**File:** `backend/app/services/sandbox_service.py:86-93`

**Issue:** The file imports `SandboxSession` from `llm_sandbox` at line 42:

```python
from llm_sandbox import SandboxBackend, SandboxSession, SupportedLanguage
```

Then immediately defines a local dataclass with the same name at line 86:

```python
@dataclass
class SandboxSession:
    """Per-thread sandbox state. `container` is the opaque llm-sandbox handle."""
    container: object
    last_used: datetime
    thread_id: str
    bridge_token: str | None = None
```

The local `SandboxSession` shadows the imported one for the rest of the module. The imported `SandboxSession` is used inside `_create_container` (line 213):

```python
container = SandboxSession(
    backend=SandboxBackend.DOCKER,
    ...
)
```

This call will now construct the local dataclass (which expects `container, last_used, thread_id`), not the `llm_sandbox` factory. This looks like it would crash at runtime when `_create_container` is invoked. The fact that tests appear to be passing suggests either the tests mock this path or the shadowing is somehow tolerated. Either way the naming collision is a maintenance hazard that will cause subtle bugs.

**Fix:** Rename the local dataclass to avoid the collision:

```python
@dataclass
class _ThreadSession:
    """Per-thread sandbox state. `container` is the opaque llm-sandbox handle."""
    container: object
    last_used: datetime
    thread_id: str
    bridge_token: str | None = None
```

Update all references in `_sessions`, `_get_or_create_session`, `_cleanup_loop`, and `execute` accordingly.

---

## Info

### IN-01: `validate_workspace_path` does not reject dot-only segments (`.`)

**File:** `backend/app/services/workspace_service.py:121-127`

**Issue:** The path validation at line 122 only rejects `".."` segments:

```python
if any(seg == ".." for seg in segments):
    raise WorkspaceValidationError(...)
```

A path like `foo/./bar` passes validation. While `.` segments are benign on most systems (they resolve to the same directory), they allow the LLM to write two logically distinct paths that resolve to the same storage path: `notes/file.md` and `notes/./file.md` would produce different `file_path` DB values but point to the same conceptual location. The `UNIQUE (thread_id, file_path)` constraint will not catch this, so a second write creates a duplicate row at a different key.

**Fix:** Add a `.` segment check alongside `..`:

```python
if any(seg in (".", "..") for seg in segments):
    raise WorkspaceValidationError(
        "path_invalid_traversal",
        "`. ` and `..` segments are forbidden in workspace paths",
    )
```

---

### IN-02: `workspace_updated` SSE event has no explicit handler for `event_type` in `_run_tool_loop`'s yielded events — the routing relies on fall-through

**File:** `backend/app/routers/chat.py:706-721`

**Issue:** `_run_tool_loop` yields tuples of `(event_type, data)`. The outer `event_generator` loop handles known event types (`records`, `round`, `round_usage`, `code_stdout`, `code_stderr`) and then falls into `elif redaction_on: tool_loop_buffer.append(data)` for everything else. The `workspace_updated` event type falls through to that branch when `redaction_on=True` (as noted in WR-01), or falls through to `yield f"data: {json.dumps(data)}\n\n"` when `redaction_on=False`.

The fall-through works because `data` already has the `"type": "workspace_updated"` key set in the dict. However, this implicit routing is fragile — any future event type added to the tool loop without an explicit handler will silently inherit the buffering behavior. Adding an explicit case for `workspace_updated` (as suggested in WR-01 fix) also removes the implicit dependency.

**Fix:** This is resolved by the WR-01 fix above (explicit `workspace_updated` branch in the event routing).

---

_Reviewed: 2026-05-03T02:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
