# Phase 8: LLM Tool Integration & Discovery — Pattern Map

**Mapped:** 2026-04-30
**Files analyzed:** 4 (1 NEW + 3 MODIFY)
**Analogs found:** 4 / 4 (100%)
**Scope:** Backend-only — no frontend changes

All analog line numbers below have been re-verified against the on-disk source (HEAD `3219acd`). Where the CONTEXT.md cited a line number that drifted, the corrected location is noted.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/services/skill_catalog_service.py` (NEW) | service (prompt-fragment builder) | request-response (read-only DB fetch + format) | `backend/app/services/redaction/prompt_guidance.py` (`get_pii_guidance_block`) + `backend/app/routers/skills.py` (RLS-scoped skill SELECT) | role-match (no exact analog — first prompt-fragment service that hits DB) |
| `backend/app/routers/chat.py` (MODIFY) | chat-orchestration patch | request-response (system prompt assembly) | `chat.py` itself — extend `pii_guidance` append pattern at lines 437 & 498 | exact (mirror pattern verbatim) |
| `backend/app/services/tool_service.py` (MODIFY) | tool dispatcher | request-response (tool-call dispatch + DB I/O) | `tool_service.py` itself — extend `TOOL_DEFINITIONS` and `execute_tool()` switch | exact |
| `backend/app/routers/skills.py` (MODIFY) | router (3 new endpoints) | request-response (multipart upload, JSON read, signed-content read) | `skills.py` import handler (lines 216-232) for upload; export endpoint (lines 540-576) for download | exact |

---

## Line-Number Verification (CONTEXT.md cross-check)

| CONTEXT.md citation | Actual on-disk location | Status |
|---------------------|-------------------------|--------|
| `chat.py:491` (`SYSTEM_PROMPT + pii_guidance`) | **chat.py:494-498** (block); the actual concat is on **line 498** | drift +7 — corrected below |
| `chat.py:408` (`tool_service.get_available_tools(...)`) | **chat.py:407-410** | exact |
| `chat.py:437` (multi-agent `agent_def.system_prompt`) | **chat.py:437** | exact |
| `tool_service.py:247` (`get_available_tools()` web_search gate) | **tool_service.py:247-263** | exact |
| `tool_service.py:266` (`execute_tool()` dispatch switch) | **tool_service.py:265-335** (dispatch body) | exact |
| `skills.py:218-237` (ZIP import upload pattern) | **skills.py:216-232** (loop body); call sites use `client.storage.from_("skills-files").upload(...)` at line 220 and `client.table("skill_files").insert({...})` at line 226 | drift -2 — corrected below |
| `skills.py:573-576` (`storage.from_("skills-files").download(path)`) | **skills.py:573-576** | exact |

---

## Pattern Assignments

### File 1: `backend/app/services/skill_catalog_service.py` (NEW — service, prompt-fragment builder)

**Closest analogs:**
1. `backend/app/services/redaction/prompt_guidance.py` — pattern for a "build a prompt fragment that may be empty string when feature disabled" helper (mirrors D-P8-02: return `""` when no enabled skills).
2. `backend/app/routers/skills.py` — RLS-scoped skill SELECT query pattern.

**Imports pattern** (mirror `chat.py:1-14` + `skills.py:10-11`):
```python
import logging
from app.database import get_supabase_authed_client

logger = logging.getLogger(__name__)
```

**Module-level singleton convention** (CONVENTIONS.md §Module Design — `logger = logging.getLogger(__name__)` at top of every service module).

**RLS-scoped SELECT pattern** (analog: `skills.py:532-533, 540-545`):
```python
# RLS-scoped fetch of skill (skills.py:532-533)
client = get_supabase_authed_client(user["token"])
skill_result = client.table("skills").select("*").eq("id", skill_id).execute()
```

**Adapt for D-P8-06 (cap 20, alphabetical) and D-P8-02 (empty string when no rows):**
```python
async def build_skill_catalog_block(user_id: str, token: str) -> str:
    """Return the '## Your Skills' system-prompt block, or '' if no enabled skills.

    D-P8-02: empty string when user has 0 enabled skills.
    D-P8-06: cap 20, ordered alphabetically by name.
    D-P8-07: footer indicating truncation when N > 20.
    """
    client = get_supabase_authed_client(token)
    # RLS auto-filters: SELECT WHERE enabled = true AND (user_id = auth.uid() OR user_id IS NULL)
    result = (
        client.table("skills")
        .select("name, description")
        .eq("enabled", True)
        .order("name")
        .limit(21)  # fetch 21 to detect truncation per D-P8-07
        .execute()
    )
    rows = result.data or []
    if not rows:
        return ""  # D-P8-02
    # ... build markdown table per D-P8-05 ...
```

**Empty-string-when-disabled analog** (`get_pii_guidance_block` in `redaction/prompt_guidance.py` returns `""` when `redaction_enabled=False`). Use the same convention so `chat.py`'s string concatenation stays clean.

**Catalog format** (D-P8-05, copy verbatim):
```
## Your Skills
Call `load_skill` with the skill name when the user's request clearly
matches a skill. Only load a skill when there's a strong match.

| Skill | Description |
|-------|-------------|
| {name} | {description} |
```

**Footer pattern when capped** (D-P8-07):
```
Showing 20 of N skills. Call load_skill with any skill name to load it directly.
```

**Error handling** (CONVENTIONS.md §Error Handling — fire-and-forget for non-critical, never break the chat request):
```python
try:
    result = client.table("skills").select(...).execute()
except Exception as e:
    logger.warning("build_skill_catalog_block failed: %s", e)
    return ""  # fail-soft — chat still works without catalog
```

---

### File 2: `backend/app/routers/chat.py` (MODIFY — single-agent + multi-agent prompt assembly)

**Analog:** `chat.py` itself — copy the `pii_guidance` append pattern verbatim.

**Site 1: Multi-agent path** — `chat.py:437` (D-P8-03):

Current code at lines **435-440**:
```python
# 3. Build messages with agent's system prompt
messages = (
    [{"role": "system", "content": agent_def.system_prompt}]
    + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
    + [{"role": "user", "content": anonymized_message}]
)
```

**Patch pattern:** insert `skill_catalog` before line 437 and concatenate to system prompt content:
```python
# Phase 8 D-P8-03: inject enabled-skills catalog into multi-agent system prompt
skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
messages = (
    [{"role": "system", "content": agent_def.system_prompt + skill_catalog}]
    + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
    + [{"role": "user", "content": anonymized_message}]
)
```

**Site 2: Single-agent path** — `chat.py:494-501` (the actual `SYSTEM_PROMPT + pii_guidance` concat is at **line 498**, NOT 491 as cited in CONTEXT.md):

Current code at lines **491-501**:
```python
# Phase 4 D-79/D-80: append PII guidance to SYSTEM_PROMPT when
# redaction is enabled. Plan 05-08: use the local redaction_on
# variable (sourced from sys_settings DB column, not config.py).
pii_guidance = get_pii_guidance_block(
    redaction_enabled=redaction_on,
)
messages = (
    [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance}]
    + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
    + [{"role": "user", "content": anonymized_message}]
)
```

**Patch pattern (D-P8-01):** add `skill_catalog` fetch and append to the concat string at **line 498**:
```python
# Phase 4 D-79/D-80: append PII guidance to SYSTEM_PROMPT when redaction is enabled.
pii_guidance = get_pii_guidance_block(redaction_enabled=redaction_on)
# Phase 8 D-P8-01: append enabled-skills catalog (returns "" when 0 enabled).
skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
messages = (
    [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance + skill_catalog}]
    + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
    + [{"role": "user", "content": anonymized_message}]
)
```

**Import to add** (top of file, alphabetical with other `app.services` imports — see `chat.py:8-11`):
```python
from app.services.skill_catalog_service import build_skill_catalog_block
```

**Site 3: Tool catalog (no change to call site)** — `chat.py:407-410`:
```python
all_tools = (
    tool_service.get_available_tools(web_search_enabled=web_search_effective)
    if settings.tools_enabled else []
)
```
The skill tools are added to `TOOL_DEFINITIONS` directly (no new flag) per D-P8-04. This call site does not change.

**Critical constraint (D-P8-02):** when `build_skill_catalog_block` returns `""`, the concatenation `SYSTEM_PROMPT + pii_guidance + ""` is a byte-identical no-op for the LLM. Verifies the SC#5-style invariant: zero behavioral drift when feature unused.

---

### File 3: `backend/app/services/tool_service.py` (MODIFY — add 3 LLM tools)

**Analog:** `tool_service.py` itself — copy the existing `TOOL_DEFINITIONS` entry shape and the `execute_tool` dispatch case verbatim.

**Imports pattern** (top of file, lines 1-11):
```python
import json
import logging
import re
from typing import TYPE_CHECKING

import httpx

from app.services.tracing_service import traced
from app.config import get_settings
from app.database import get_supabase_client
from app.services.hybrid_retrieval_service import HybridRetrievalService
```

Add for skill tools:
```python
from app.database import get_supabase_authed_client  # already imported as get_supabase_client; add authed
```

**TOOL_DEFINITIONS entry shape** (analog: `tool_service.py:29-66`):
```python
{
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Search the user's uploaded documents for relevant information. "
            "Use this when the user asks about content in their documents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "..."},
                # ...
            },
            "required": ["query"],
        },
    },
},
```

**Add 3 new entries to `TOOL_DEFINITIONS`** following this exact shape:
- `load_skill` — properties: `{name: str}`; required: `["name"]`
- `save_skill` — properties: `{name, description, instructions, update?: bool, skill_id?: str}`; required: `["name", "description", "instructions"]` (per D-P8-08/D-P8-09)
- `read_skill_file` — properties: `{skill_id: str, filename: str}`; required: `["skill_id", "filename"]` (per D-P8-13 specifics — use filename, not UUID)

**`get_available_tools` gating pattern** (lines 247-263) — D-P8-04: skill tools are **unconditional** (no gate, unlike `web_search`):
```python
def get_available_tools(self, *, web_search_enabled: bool = True) -> list[dict]:
    """Return tool definitions visible to the LLM for this request.

    ADR-0008: when web_search_enabled=False, the web_search tool is
    excluded from the catalog so the agent classifier and dispatcher
    never see it. The existing tavily_api_key check is preserved.
    """
    tools = []
    for tool in TOOL_DEFINITIONS:
        name = tool["function"]["name"]
        if name == "web_search":
            if not web_search_enabled:
                continue
            if not settings.tavily_api_key:
                continue
        tools.append(tool)
    return tools
```

**Patch:** no change needed — skill tools fall through the loop and are included unconditionally. D-P8-04 is satisfied by simply adding them to `TOOL_DEFINITIONS` with no name-match branch in this method.

**`execute_tool` dispatch switch** (lines 265-335) — analog for new tool case:
```python
@traced(name="execute_tool")
async def execute_tool(
    self,
    name: str,
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    registry: "ConversationRegistry | None" = None,  # Phase 5 D-86 / D-91
) -> dict:
    if name == "search_documents":
        return await self._execute_search_documents(
            query=arguments.get("query", ""),
            user_id=user_id,
            context=context or {},
            # ...
        )
    elif name == "query_database":
        return await self._execute_query_database(
            sql_query=arguments.get("sql_query", ""),
            user_id=user_id,
        )
    # ... more elif branches ...
    else:
        return {"error": f"Unknown tool: {name}"}
```

**Critical plumbing observation (matches CONTEXT.md `<code_context>`):** the dispatch passes `user_id: str` to every handler. **It does NOT pass a `token`.** All current handlers use `get_supabase_client()` (service-role) plus a `.eq("user_id", user_id)` predicate (e.g., `_execute_kb_list_files` at line 473: `.eq("user_id", user_id)`).

**Plumbing decision for Phase 8:** skill tools need **RLS-scoped** access (so they respect global skill visibility per D-P8-05 query: `WHERE enabled = true AND (user_id = auth.uid() OR user_id IS NULL)`). This means we need the user's JWT, not just `user_id`.

**Three options for the planner** (must decide; recommend Option A):
- **Option A (preferred):** Add a `token: str | None = None` keyword arg to `execute_tool()`, plumb it from `chat.py` (where `user["token"]` is already in scope — see `chat.py:514` passing `user["id"]`), pass to skill handlers, use `get_supabase_authed_client(token)`. Mirrors how Phase 5 D-86 added the `registry` keyword arg (cdd3470 — observation 3750).
- **Option B:** Pass `token` via `context` dict. Less explicit, but no new parameter.
- **Option C:** Use `get_supabase_client()` (service-role) and manually replicate the RLS predicate `(user_id = X OR user_id IS NULL)` in the query. Bypasses RLS — same anti-pattern as `kb_list_files`. Not recommended for Phase 8 because skill ownership is the auth boundary.

**Add 3 new dispatch branches** (after line 333, before the `else` fallthrough at line 334):
```python
elif name == "load_skill":
    return await self._execute_load_skill(
        skill_name=arguments.get("name", ""),
        user_id=user_id,
        token=token,  # see Option A above
    )
elif name == "save_skill":
    return await self._execute_save_skill(
        name=arguments.get("name", ""),
        description=arguments.get("description", ""),
        instructions=arguments.get("instructions", ""),
        update=arguments.get("update", False),
        skill_id=arguments.get("skill_id"),
        user_id=user_id,
        token=token,
    )
elif name == "read_skill_file":
    return await self._execute_read_skill_file(
        skill_id=arguments.get("skill_id", ""),
        filename=arguments.get("filename", ""),
        user_id=user_id,
        token=token,
    )
```

**Tool error response shape** (analog: `tool_service.py:335` and `:415`):
```python
return {"error": "Query must include user_id filter for security"}
# or
return {"error": f"Unknown tool: {name}"}
```

The LLM sees these `{"error": "..."}` dicts directly as tool result content. D-P8-08 conflict response follows the same shape:
```python
return {
    "error": "name_conflict",
    "message": "Skill 'legal-review' already exists.",
    "existing_skill_id": "uuid-...",
    "hint": "Use a different name, or resend with update=true and skill_id=<existing_id> to update.",
}
```

**Tracing decorator** (analog: `tool_service.py:265, 337, 400, 429`):
```python
@traced(name="execute_tool")          # outer dispatch
@traced(name="tool_search_documents") # each handler
```
Add `@traced(name="tool_load_skill")`, `@traced(name="tool_save_skill")`, `@traced(name="tool_read_skill_file")` to each new private handler.

---

### File 4: `backend/app/routers/skills.py` (MODIFY — 3 new file endpoints)

**Analog 1 (file UPLOAD path):** `skills.py:216-232` (the per-file upload loop inside `/skills/import`).
**Analog 2 (file DOWNLOAD path):** `skills.py:573-576` (`bytes_loader` in export endpoint).
**Analog 3 (router skeleton + Pydantic + RLS):** `skills.py:90-122` (`POST /skills` create_skill).
**Analog 4 (multipart UploadFile pattern):** `skills.py:125-130` and `documents.py:36-44` (`POST /documents/upload`).

#### Endpoint A: `POST /skills/{skill_id}/files`

**Imports already present in skills.py** (lines 1-11):
```python
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action
```

**Multipart endpoint signature** (analog: `skills.py:125-130`):
```python
@router.post("/{skill_id}/files", status_code=201)
async def upload_skill_file(
    skill_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    ...
```

**File size guard pattern** (CONTEXT.md `<code_context>` references existing 10MB limit per D-P7-08; the DB CHECK is at the `skill_files.size_bytes` column). Read content first, validate size, then upload:
```python
content = await file.read()
if len(content) > 10 * 1024 * 1024:
    raise HTTPException(status_code=413, detail="File exceeds 10MB limit")
```

**Pre-flight ownership check via RLS** (analog: `skills.py:532-535`):
```python
client = get_supabase_authed_client(user["token"])
skill_result = client.table("skills").select("user_id").eq("id", skill_id).execute()
if not skill_result.data:
    raise HTTPException(status_code=404, detail="Skill not found")
if skill_result.data[0]["user_id"] != user["id"]:
    # D-P7-09 Storage RLS gate: only private-owned skills accept file mutations.
    # Globally-shared skills require unshare first.
    raise HTTPException(status_code=403, detail="Cannot modify files of a shared skill")
```

**Storage upload + DB insert** (analog **verbatim** from `skills.py:216-232`):
```python
# Storage path must be three flat segments: {user_id}/{skill_id}/{flat_name}
# (CHECK constraint: '^[a-zA-Z0-9_-]+/[0-9a-fA-F-]{36}/[^/]+$').
# Flatten relative_path (e.g. "scripts/foo.py") by replacing '/' with '__'.
flat_name = file.filename.replace("/", "__")
storage_path = f"{user['id']}/{skill_id}/{flat_name}"
try:
    client.storage.from_("skills-files").upload(
        storage_path,
        content,
        {"content-type": file.content_type or "application/octet-stream"},
    )
    insert_result = client.table("skill_files").insert({
        "skill_id": skill_id,
        "filename": flat_name,
        "size_bytes": len(content),
        "storage_path": storage_path,
        "mime_type": file.content_type or "application/octet-stream",
        "created_by": user["id"],
    }).execute()
except Exception as exc:
    raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")
```

**Audit logging** (analog: `skills.py:258-265`):
```python
log_action(
    user_id=user["id"],
    user_email=user["email"],
    action="upload_file",
    resource_type="skill_file",
    resource_id=insert_result.data[0]["id"],
    details={"skill_id": skill_id, "filename": flat_name, "size_bytes": len(content)},
)
```

**Response** (CONVENTIONS.md §Function Design — return the inserted row as a dict):
```python
return insert_result.data[0]
```

#### Endpoint B: `DELETE /skills/{skill_id}/files/{file_id}`

**Analog:** `skills.py:390-440` (`delete_skill`). Uses RLS-scoped client; `skill_files` DELETE policy gates on `private-skill owner` per migration 035.

**Pattern:**
```python
@router.delete("/{skill_id}/files/{file_id}", status_code=204)
async def delete_skill_file(
    skill_id: str,
    file_id: str,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    # Fetch first so we know the storage_path for cleanup
    file_row = (
        client.table("skill_files")
        .select("storage_path")
        .eq("id", file_id)
        .eq("skill_id", skill_id)
        .execute()
    )
    if not file_row.data:
        raise HTTPException(status_code=404, detail="File not found")
    storage_path = file_row.data[0]["storage_path"]
    # Delete DB row first (RLS gates this — only private-owned skills allowed)
    client.table("skill_files").delete().eq("id", file_id).execute()
    # Best-effort storage cleanup
    try:
        client.storage.from_("skills-files").remove([storage_path])
    except Exception as e:
        logger.warning("Storage cleanup failed for %s: %s", storage_path, e)
    log_action(...)
```

#### Endpoint C: `GET /skills/{skill_id}/files/{file_id}/content`

**This is the HTTP endpoint that backs the `read_skill_file` LLM tool.** Per D-P8-11/12/13.

**Analog (read path):** `skills.py:573-576`:
```python
# service-role: required to download files for globally-shared skills per D-P7-07
svc_storage = get_supabase_client()

def bytes_loader(path: str) -> bytes:
    return svc_storage.storage.from_("skills-files").download(path)
```

**Note** the analog uses **service-role** for downloads. Phase 8 must follow the same pattern for global-skill file reads — RLS-scoped reads on globally-shared skill files will still work (storage SELECT policy uses exact path JOIN per migration 035 cycle-1 HIGH #1 fix), so prefer RLS-scoped first, fall back to service-role only if needed for D-P7-07 parity.

**Endpoint pattern:**
```python
@router.get("/{skill_id}/files/{file_id}/content")
async def get_skill_file_content(
    skill_id: str,
    file_id: str,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_authed_client(user["token"])
    # RLS-gated fetch — globals readable by all enabled-skill users
    file_row = (
        client.table("skill_files")
        .select("filename, mime_type, size_bytes, storage_path")
        .eq("id", file_id)
        .eq("skill_id", skill_id)
        .execute()
    )
    if not file_row.data:
        raise HTTPException(status_code=404, detail="File not found")
    f = file_row.data[0]
    mime = f.get("mime_type") or "application/octet-stream"

    # D-P8-13: binary files return metadata only
    if not mime.startswith("text/"):
        return {
            "filename": f["filename"],
            "mime_type": mime,
            "size_bytes": f["size_bytes"],
            "readable": False,
            "message": "Binary file — cannot display inline. Available as a skill resource.",
        }

    # D-P8-12: text files inline, capped at 8000 chars
    raw = client.storage.from_("skills-files").download(f["storage_path"])
    text = raw.decode("utf-8", errors="replace")
    truncated = len(text) > 8000
    return {
        "filename": f["filename"],
        "content": text[:8000],
        "truncated": truncated,
        "total_bytes": f["size_bytes"],
        "message": "Content truncated at 8000 chars." if truncated else None,
    }
```

**Static-route ordering caveat** (PATTERN: 07-04 SUMMARY decision): `POST /skills/import` was placed before `/{skill_id}` routes so FastAPI matches static path first. New routes `POST /{skill_id}/files`, `DELETE /{skill_id}/files/{file_id}`, `GET /{skill_id}/files/{file_id}/content` are all under `/{skill_id}/files/...` — they do not collide with `/import` and can be appended at the end of the router file.

---

## Shared Patterns

### Authentication
**Source:** `backend/app/dependencies.py` (`get_current_user`)
**Apply to:** All 3 new endpoints in `skills.py`.
```python
async def upload_skill_file(
    skill_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
```
Returns `{id, email, token, role}`. Use `user["id"]` for predicates and `user["token"]` for RLS-scoped client.

### Database client selection
**Source:** `backend/app/database.py`; CONVENTIONS.md §FastAPI Dependency Patterns
**Apply to:** All 3 new endpoints + `skill_catalog_service` + new `tool_service` handlers.
```python
client = get_supabase_authed_client(user["token"])  # RLS-scoped — preferred for skill ops
svc = get_supabase_client()                          # service-role — only for global-skill download per D-P7-07
```

### Audit logging
**Source:** `backend/app/services/audit_service.py:log_action(...)`
**Apply to:** All mutating endpoints (`POST /files`, `DELETE /files/{id}`, the `save_skill` tool).
**Analog:** `skills.py:258-265` and `clause_library.py` (CONVENTIONS.md §How to Add New Code item 5).
```python
log_action(
    user_id=user["id"],
    user_email=user["email"],
    action="upload_file",
    resource_type="skill_file",
    resource_id=file_id,
    details={"skill_id": skill_id, "filename": flat_name},
)
```
Audit logging is fire-and-forget — never blocks the request (CONVENTIONS.md §Error Handling).

### Error responses
**Source:** CONVENTIONS.md §Error Handling
**Apply to:** All 3 new endpoints.
```python
raise HTTPException(status_code=404, detail="File not found")
raise HTTPException(status_code=403, detail="Cannot modify files of a shared skill")
raise HTTPException(status_code=413, detail="File exceeds 10MB limit")
raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")
```

For tool errors in `tool_service.py`, the convention is a plain dict (lines 335, 415):
```python
return {"error": "Unknown tool: {name}"}
return {"error": "name_conflict", "message": "...", "existing_skill_id": "...", "hint": "..."}
```

### Tracing
**Source:** `backend/app/services/tracing_service.py` (`@traced` decorator)
**Apply to:** All new private handlers in `tool_service.py`.
**Analog:** `tool_service.py:265, 337, 400, 429, 460`.
```python
@traced(name="tool_load_skill")
async def _execute_load_skill(self, ...): ...
```

### Storage path convention (D-P7-09)
**Source:** Migration 035 CHECK constraint + `skills.py:213-218`.
**Apply to:** `POST /files` upload only.
```
{user_id}/{skill_id}/{flat_name}
```
Where `flat_name` = `original_path.replace("/", "__")` to satisfy the 3-segment regex `^[a-zA-Z0-9_-]+/[0-9a-fA-F-]{36}/[^/]+$`.

### `name_conflict` error shape (D-P8-08)
**Source:** `skills.py:182-184` already handles 23505 via `PostgrestAPIError.code == "23505"`.
**Apply to:** `save_skill` tool handler when INSERT returns 23505.
```python
from postgrest.exceptions import APIError as PostgrestAPIError
try:
    insert_result = client.table("skills").insert({...}).execute()
except PostgrestAPIError as exc:
    if exc.code == "23505":
        # D-P8-08: return existing_skill_id so LLM can retry with update=true
        existing = client.table("skills").select("id").eq("name", name).eq("user_id", user_id).execute()
        return {
            "error": "name_conflict",
            "message": f"Skill '{name}' already exists.",
            "existing_skill_id": existing.data[0]["id"] if existing.data else None,
            "hint": "Use a different name, or resend with update=true and skill_id=<existing_id> to update.",
        }
    return {"error": str(exc.message)}
```

---

## No Analog Found

| File / Component | Reason | Fallback |
|------------------|--------|----------|
| `build_skill_catalog_block` exact analog | No prior service exists that combines (a) RLS-scoped DB read with (b) prompt-fragment string output. The closest precedent is `get_pii_guidance_block` (string-only, no DB) and `skills.py` SELECT (no string-formatting). | Compose the two patterns as shown above. |
| `read_skill_file` 8000-char truncation | No precedent for truncation+metadata response shape in `tool_service.py`. | Use D-P8-12 schema verbatim — first of its kind. |
| `save_skill` create-or-update flow inside a tool | `skills.py` has separate `POST /skills` and `PATCH /skills/{id}` endpoints; no tool-side "upsert" precedent. | Implement two-branch logic inside `_execute_save_skill` per D-P8-09: `update=False` → INSERT (handle 23505 per D-P8-08); `update=True + skill_id` → PATCH-equivalent UPDATE on RLS-scoped client (RLS gates ownership automatically). |

---

## Cross-File Integration Notes

1. **`token` plumbing through `execute_tool`:** the largest cross-cutting change. Phase 5 already added the `registry` kwarg the same way (commit cdd3470). Use that as the migration template — add `token: str | None = None` keyword arg, update all call sites in `chat.py` (`_run_tool_loop` invocations at lines ~451 and ~512, plus the one inside `_run_tool_loop` itself).
2. **`user["token"]` is in scope at every `execute_tool` call site** in `chat.py` (the `user` dict comes from `Depends(get_current_user)` at the top of `stream_chat`). No new dependency needed.
3. **Migration 035 storage RLS** already supports the new endpoints unchanged — `POST /files` insert is gated on `s.user_id = auth.uid()` (private-skill only); `GET /files/.../content` is gated on parent-skill visibility (private-owned OR global). Phase 8 introduces no new SQL.
4. **Skill-tool dispatch is unconditional (D-P8-04):** `get_available_tools` does not need a new flag. The 3 new entries in `TOOL_DEFINITIONS` are always returned (subject only to existing `web_search`-specific gating which doesn't apply here).
5. **D-P8-02 invariant:** when a user has 0 enabled skills, `build_skill_catalog_block` returns `""`, which makes the system prompt byte-identical to current behavior for that user. SC#5-style guarantee holds.

---

## Metadata

**Analog search scope:**
- `backend/app/routers/chat.py` (665 lines)
- `backend/app/services/tool_service.py` (727 lines)
- `backend/app/routers/skills.py` (588 lines)
- `backend/app/routers/documents.py` (UploadFile pattern reference)
- `backend/app/services/redaction/prompt_guidance.py` (empty-string return convention)
- `.planning/codebase/CONVENTIONS.md` (router skeleton, error handling, audit pattern)
- Phase 7 SUMMARY files (07-01..07-05) for migration/RLS context

**Files scanned:** 6 source files + 7 planning docs
**Pattern extraction date:** 2026-04-30
**Verified against:** HEAD `3219acd` (master)

---

*Phase: 08-llm-tool-integration-discovery*
*Pattern map: ready for planner consumption*
