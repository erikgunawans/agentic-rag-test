# Phase 22: Contract Review Harness + DOCX Deliverable — Pattern Map

**Mapped:** 2026-05-04
**Files analyzed:** 12 new/modified
**Analogs found:** 12 / 12 (100%)

Phase 22 is composition over construction: the engine, dispatchers, gatekeeper, sandbox, RAG tools, workspace, and frontend banner/panel are all built. New code follows the analogs below verbatim. **No new migration. No new RLS. No new SSE events.**

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/harnesses/contract_review.py` (NEW) | harness module | event-driven (8-phase state machine) | `backend/app/harnesses/smoke_echo.py` | exact (4-phase analog of 8-phase target) |
| `backend/app/harnesses/contract_review_docx.py` (NEW, optional split) | utility/script holder | request-response (sandbox call) | `backend/sandbox/tool_client.py` + `backend/sandbox/Dockerfile` | role-match |
| `backend/app/services/gatekeeper.py` (MODIFY — D-22-01..03) | service | request-response (LLM stream) | self (additive patch to `build_system_prompt`, `run_gatekeeper`) | exact |
| `backend/app/config.py` (MODIFY — flag) | config | n/a | self (existing `harness_enabled` / `harness_smoke_enabled`) | exact |
| `backend/sandbox/Dockerfile` (MODIFY — DOCX-01) | config | n/a | self (add `pip install python-docx PyPDF2`) | exact |
| `backend/tests/services/test_gatekeeper_eval.py` (NEW — D-22-04) | test | request-response | `backend/tests/services/test_gatekeeper.py` (existing 12-case suite) | role-match |
| `backend/tests/harnesses/test_contract_review.py` (NEW) | test | event-driven | existing `backend/tests/harnesses/` smoke tests | role-match |
| `frontend/src/components/chat/MessageView.tsx` (MODIFY — D-22-14 download chip) | component | request-response | self (post lines 142-150 bubble; new `attachment` slot) | exact |
| `frontend/src/hooks/useChatState.ts` (MODIFY — possible `harness_artifact` slice) | state hook | event-driven (SSE) | existing `harnessRun`/`batchProgress` slice | exact |
| `frontend/src/components/chat/WorkspacePanel.tsx` (NO CHANGE — DOCX appears automatically) | component | event-driven | n/a — already lists workspace files via existing `workspace_updated` SSE | n/a |
| `backend/app/services/post_harness.py` (NO CHANGE — POST-* already covers CR-08 streaming) | service | streaming | n/a | n/a |
| `backend/app/routers/chat.py` HIL branch (NO CHANGE — CR-03 reuses existing logic) | router | request-response | n/a — Phase 21 line ~365 already handles paused harness resume | n/a |

**Open Question 1 from CONTEXT.md (DOCX script location):** Two viable patterns — (a) inline string constant in `contract_review_docx.py` sent to the sandbox via `ToolClient` POST, (b) separate `.py` file inside `backend/sandbox/` baked at image-build time. Pattern (a) is preferred because the sandbox image rebuild cycle is slow (Railway manual deploy gotcha) and python-docx generation logic will need iteration; the script-as-string approach is what `_execute_code` already supports.

---

## Pattern Assignments

### `backend/app/harnesses/contract_review.py` (NEW — harness module)

**Analog:** `backend/app/harnesses/smoke_echo.py`

**Imports + module preamble** (smoke_echo.py lines 14-31):
```python
from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

from app.config import get_settings
from app.harnesses.types import (
    HarnessDefinition,
    HarnessPrerequisites,
    PhaseDefinition,
    PhaseType,
)
from app.services.harness_registry import register
from app.services.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)
```

**Pydantic schemas for `llm_single` phases (HARN-05 enforcement)** (smoke_echo.py lines 35-37):
```python
class EchoSummary(BaseModel):
    echo_count: int = Field(..., ge=0, description="Number of files referenced in echo.md")
    summary: str = Field(..., min_length=1, max_length=2000, description="One-paragraph summary")
```
For Phase 22, define `ContractClassification` (CR-02), `ExecutiveSummary` (CR-08) with the same pattern. CR-02 must enforce `parties: list[str]` with `min_length=2` and non-empty `contract_type` per ROADMAP success criteria.

**Programmatic phase executor signature** (smoke_echo.py lines 51-106):
```python
async def _phase1_echo(
    *, inputs: dict[str, str], token: str, thread_id: str, harness_run_id: str
) -> dict:
    """List workspace files (uploads/), write echo.md with metadata..."""
    ws = WorkspaceService(token=token)
    try:
        files = await ws.list_files(thread_id)
    except Exception as exc:
        logger.error("...", exc_info=True)
        return {"error": "list_files_failed", "code": "WS_LIST_ERROR", "detail": str(exc)[:500]}
    # ...
    return {
        "content": echo_content,  # engine writes this to PhaseDefinition.workspace_output
        "echo_count": len(uploads),
    }
```
**Key invariant:** programmatic executor MUST return a dict with `content` field — engine at `harness_engine.py:509-518` writes `output["content"]` to `phase.workspace_output`. CR-01 (Document Intake) and CR-05 (Clause Extraction) follow this exact shape. CR-05's internal LLM-per-chunk pattern can call OpenRouterService inside this same executor (no new phase type needed).

**HarnessDefinition shape** (smoke_echo.py lines 110-189):
```python
SMOKE_ECHO = HarnessDefinition(
    name="smoke-echo",                     # registry key — must be unique
    display_name="Smoke Echo",             # UI label (gatekeeper uses this in prompt)
    prerequisites=HarnessPrerequisites(
        requires_upload=True,
        upload_description="any DOCX or PDF file (used for engine smoke-test only — content not analyzed)",
        accepted_mime_types=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        min_files=1,
        max_files=1,
        harness_intro="Hi! This is the Smoke Echo harness — ...",
    ),
    phases=[
        PhaseDefinition(
            name="echo",
            description="...",
            phase_type=PhaseType.PROGRAMMATIC,
            tools=[],
            workspace_inputs=[],
            workspace_output="echo.md",
            executor=_phase1_echo,
            timeout_seconds=60,
        ),
        PhaseDefinition(
            name="summarize",
            phase_type=PhaseType.LLM_SINGLE,
            system_prompt_template="You are summarizing... Return ONLY the JSON object — no prose.",
            workspace_inputs=["echo.md"],
            workspace_output="summary.json",
            output_schema=EchoSummary,    # Pydantic class — engine validates via response_format=json_schema
            timeout_seconds=120,
        ),
        PhaseDefinition(
            name="ask-label",
            phase_type=PhaseType.LLM_HUMAN_INPUT,
            system_prompt_template='Generate ONE short clarifying question... Respond as JSON {"question": "..."}.',
            workspace_inputs=["echo.md"],
            workspace_output="test-answer.md",
            timeout_seconds=86_400,        # 24h pause budget
        ),
        PhaseDefinition(
            name="batch-process",
            phase_type=PhaseType.LLM_BATCH_AGENTS,
            system_prompt_template="...",
            workspace_inputs=["test-items.md"],
            workspace_output="test-batch.json",
            batch_size=2,
            timeout_seconds=600,
        ),
    ],
)
```

**For Phase 22 specifically — CR-04 / CR-06 / CR-07 each need `tools=["search_documents", "analyze_document"]`** so the sub-agent dispatch (LLM_AGENT in CR-04, LLM_BATCH_AGENTS in CR-06/07) inherits the right RAG tools. Engine's `_dispatch_phase` at `harness_engine.py:633-634` (LLM_AGENT) and `harness_engine.py:845-848` (LLM_BATCH_AGENTS) curates `phase.tools` against `PANEL_LOCKED_EXCLUDED_TOOLS` and propagates to each sub-agent via `parent_tool_context={"phase_tools": curated_tools}` — no new wiring needed.

**CR-08 needs `post_execute=...`** — the only new field beyond what smoke-echo uses. Type signature from `types.py:67`:
```python
post_execute: Callable[..., Awaitable[Any]] | None = None
```
This callable is invoked by the engine after the phase's normal LLM call completes (post-CR-08-llm_single, before harness_complete). DOCX-01 lives here. Note: the engine source (`harness_engine.py`) does NOT currently invoke `post_execute` anywhere — Phase 22 must add the invocation site. The cleanest place is between line ~423 (`yield phase_complete_evt`) and line ~425 (`await _append_progress(...)`), wrapped in try/except per D-22-15 (non-fatal fallback).

**Gated registration** (smoke_echo.py lines 192-197):
```python
if get_settings().harness_smoke_enabled:
    register(SMOKE_ECHO)
    logger.info("smoke_echo: registered (HARNESS_SMOKE_ENABLED=True)")
else:
    logger.info("smoke_echo: NOT registered (HARNESS_SMOKE_ENABLED=False)")
```
For Phase 22, gate Contract Review on **`harness_enabled`** alone (the master flag at `config.py:189`). No new flag required unless we want to dark-launch contract review independently of smoke-echo. Recommend adding `contract_review_enabled: bool = False` in `config.py` next to `harness_smoke_enabled` (line 195) for symmetry, but defaulting to `True` when `harness_enabled=True`.

**Auto-discovery confirmation** (`backend/app/harnesses/__init__.py` lines 20-34): the package `__init__.py` walks every `.py` in `app/harnesses/` and imports it at startup (gated on `harness_enabled`). Drop `contract_review.py` next to `smoke_echo.py` and `types.py` and it's auto-imported. **CR-21-01 circular import lesson:** `harness_registry.py:14-23` uses `TYPE_CHECKING` + `from __future__ import annotations` to avoid circular imports — preserve this pattern in `contract_review.py`.

---

### `backend/app/services/gatekeeper.py` (MODIFY — D-22-01, D-22-02, D-22-03)

**Analog:** itself (the modifications are additive patches — do not refactor existing logic).

**Workspace block injection — D-22-01 / D-22-02 patch site** in `build_system_prompt()` (gatekeeper.py lines 57-83):

The existing function builds the system prompt from `prereq.requires_upload`, `prereq.upload_description`, and `prereq.harness_intro`. **D-22-01** changes the call site, not the function: `run_gatekeeper()` must call `WorkspaceService(token=token).list_files(thread_id)` BEFORE building the prompt and pass the file list as a new parameter to `build_system_prompt()`.

Existing signature to extend:
```python
def build_system_prompt(harness: HarnessDefinition) -> str:
    prereq = harness.prerequisites
    if prereq.requires_upload:
        upload_block = (
            f"BEFORE STARTING, the user must upload: {prereq.upload_description}\n"
            f"Accepted file types: ..."
        )
    else:
        upload_block = "No file uploads required to begin.\n"
    return (
        f"You are the gatekeeper for the {harness.display_name} harness.\n\n"
        f"INTRO: {prereq.harness_intro}\n\n"
        f"{upload_block}\n"
        f"GUIDANCE:\n"
        ...
    )
```

**Patch shape — extend signature with `workspace_files`:**
```python
def build_system_prompt(
    harness: HarnessDefinition,
    workspace_files: list[dict] | None = None,    # NEW — D-22-01
) -> str:
    prereq = harness.prerequisites
    # ... existing upload_block logic unchanged ...

    # D-22-01 / D-22-02: workspace block (filename + size only, no content)
    if workspace_files is not None and len(workspace_files) > 0:
        items = ", ".join(
            f"{f['file_path']} ({f['size_bytes'] // 1024} KB)"
            for f in workspace_files
        )
        workspace_block = f"Workspace: {items}\n"
    else:
        workspace_block = "Workspace: (empty — user has not uploaded yet)\n"

    # D-22-03: few-shot examples (use harness.display_name in template)
    few_shots = (
        "EXAMPLES (intent-match, not literal):\n"
        f"  user: 'Review this contract' + workspace non-empty → emit {SENTINEL}\n"
        f"  user: 'Check this for risks' + workspace non-empty → emit {SENTINEL}\n"
        f"  user: 'I uploaded a contract' + workspace non-empty → emit {SENTINEL}\n"
        f"  user: 'Help me with this NDA' + DOCX present → emit {SENTINEL}\n"
        f"  user: 'Hello' / 'What's this app do?' → DO NOT emit {SENTINEL}\n"
    )

    return (
        f"You are the gatekeeper for the {harness.display_name} harness.\n\n"
        f"INTRO: {prereq.harness_intro}\n\n"
        f"{upload_block}"
        f"{workspace_block}\n"
        f"{few_shots}\n"
        f"GUIDANCE:\n"
        # ... existing guidance lines unchanged ...
    )
```

**Patch site in `run_gatekeeper()`** (gatekeeper.py lines 220-228):
```python
# Before:
messages = [
    {"role": "system", "content": build_system_prompt(harness)},
    *history,
]

# After:
ws = WorkspaceService(token=token)
try:
    workspace_files = await ws.list_files(thread_id)
except Exception as exc:
    logger.warning("gatekeeper: list_files failed thread_id=%s: %s", thread_id, exc)
    workspace_files = []   # graceful degradation — falls back to "empty" block

messages = [
    {"role": "system", "content": build_system_prompt(harness, workspace_files)},
    *history,
]
```

**KV-cache friendliness (DEEP-05 analogous):** the workspace block changes per turn but is deterministic (no timestamps); few-shot block is static across turns. Place few-shots BEFORE the workspace block in the prompt so the prefix stays cacheable.

---

### `backend/app/harnesses/contract_review_docx.py` (NEW — DOCX-01..08)

**Analog:** sandbox client invocation pattern from `backend/sandbox/tool_client.py` + `_execute_code` in `tool_service.py:521-530`.

**Sandbox invocation — `ToolClient.call(...)` returns dict on success, `{"error": "bridge_error"}` on failure** (tool_client.py lines 23-70):
```python
class ToolClient:
    def call(self, tool_name: str, **kwargs: Any) -> dict:
        bridge_url = os.environ.get("BRIDGE_URL", "")
        bridge_token = os.environ.get("BRIDGE_TOKEN", "")
        timeout = int(os.environ.get("BRIDGE_TIMEOUT", "30"))
        # ... POST to /bridge/call, return JSON or {"error": "bridge_error", ...} ...
```

**However — for DOCX generation we are CALLING the sandbox FROM the backend, not from inside the sandbox.** The right primitive is `ToolService._execute_code` (tool_service.py:521-530), which wraps `sandbox_service` to run a Python script. The DOCX `post_execute` callback should:

1. Read all artifact markdown files from workspace via `WorkspaceService.read_file()`
2. Build a Python script string that uses `python-docx` to generate the file
3. Submit via `sandbox_service` (existing service at `backend/app/services/sandbox_service.py:528 → get_sandbox_service()`)
4. On success, retrieve the binary output, then call `WorkspaceService.write_binary_file(thread_id, "contract-review-{run_id_short}.docx", content_bytes, mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", user_id=..., source="harness")` — see workspace_service.py lines 511-571

**Workspace binary write pattern** (workspace_service.py:511-571):
```python
async def write_binary_file(
    self,
    thread_id: str,
    file_path: str,
    content_bytes: bytes,
    mime_type: str,
    user_id: str,
    source: str = "upload",
) -> dict:
    # 4-segment storage path: {user_id}/{thread_id}/{row_id}/{filename}
    # Returns {"ok": True, "operation": "create", "size_bytes": N, "file_path": str, "storage_path": str}
```
DOCX uses `source="harness"` (D-22-14) so the workspace panel shows it correctly via `SOURCE_COLORS` map in `WorkspacePanel.tsx:80-84`.

**Critical: filename pattern** — D-22-14 specifies `contract-review-{harness_run_id-short}.docx`. Confirm `harness_run_id` is a UUID; use `harness_run_id[:8]` for the short form. Validates clean against `validate_workspace_path` (no `/`, no `..`, ends in `.docx`).

**Non-fatal fallback shape — D-22-15** mirrors the engine's per-phase error wrapper (harness_engine.py:497-507):
```python
async def _generate_docx_post_execute(
    *, harness_run_id: str, thread_id: str, user_id: str, token: str, ...
) -> dict:
    try:
        # 1. Read artifacts
        # 2. Build Python script
        # 3. Sandbox run
        # 4. Workspace write_binary_file
        return {"ok": True, "docx_path": "contract-review-xxxxx.docx"}
    except Exception as exc:
        logger.warning(
            "docx post_execute failed harness_run=%s: %s",
            harness_run_id, exc, exc_info=True,
        )
        return {
            "error": "docx_generation_failed",
            "code": "DOCX_FAILED",
            "detail": str(exc)[:500],
            "fallback_message": (
                "DOCX export unavailable right now — "
                "the full markdown summary is above. "
                "Retry by re-running the harness if needed."
            ),
        }
```

The post_execute callback must NOT raise. Engine treats a non-raising failure as a degradation, leaves `harness_runs.status='completed'` (D-22-15 invariant), and `summarize_harness_run` still streams the markdown summary (post_harness.py is unchanged).

---

### `backend/sandbox/Dockerfile` (MODIFY — DOCX-01 dependency)

**Current state** (Dockerfile lines 1-26):
```dockerfile
FROM python:3.12-slim

# Create sandbox output directory
RUN mkdir -p /sandbox/output

# Pre-bake ToolClient — stdlib only, no pip installs needed
COPY tool_client.py /sandbox/tool_client.py

# Make /sandbox writeable so runtime stub injection can write /sandbox/stubs.py
RUN chmod 777 /sandbox

# Default working directory for executed code
WORKDIR /sandbox
```

**Patch shape** — add a single layer before `chmod 777`:
```dockerfile
# DOCX-01 / Phase 22: python-docx for DOCX report generation,
# PyPDF2 for any contract-text fallback parsing inside the sandbox.
RUN pip install --no-cache-dir python-docx==1.1.2 PyPDF2==3.0.1
```

**Cold-start budget consideration** (Open Question 4 from CONTEXT.md): adding ~5 MB to the image is acceptable; the sandbox image is rebuilt rarely. Layer-only-on-Contract-Review-runs is over-engineering — ship the deps in the base image.

**Backend Dockerfile gotcha** (CLAUDE.md Gotcha #4): the BACKEND `backend/Dockerfile` is a separate image used by Railway. python-docx may already be installed there (used by `UPL-03` text extraction during file upload — see `register_uploaded_file`). Verify before duplicating in `requirements.txt`.

---

### `backend/tests/services/test_gatekeeper_eval.py` (NEW — D-22-04)

**Analog:** existing pytest patterns in `backend/tests/services/test_gatekeeper.py` (12-case suite).

**Eval set structure** (D-22-04 spec):
```python
EVAL_PHRASINGS = [
    # Should-trigger Contract Review (5)
    {"text": "Review this contract", "harness": "contract-review", "workspace": ["contract.docx"], "expected": True},
    {"text": "Check this for risks", "harness": "contract-review", "workspace": ["contract.docx"], "expected": True},
    {"text": "I uploaded a contract", "harness": "contract-review", "workspace": ["contract.docx"], "expected": True},
    {"text": "Help me with this NDA", "harness": "contract-review", "workspace": ["nda.pdf"], "expected": True},
    {"text": "Tolong cek kontrak ini", "harness": "contract-review", "workspace": ["kontrak.pdf"], "expected": True},  # Indonesian
    # Should-trigger Smoke Echo (5) — guard against Phase 21 regression
    {"text": "Run smoke echo", "harness": "smoke-echo", "workspace": ["any.pdf"], "expected": True},
    # ... etc
    # Should-NOT-trigger (5) — neutral chat
    {"text": "Hello", "harness": "contract-review", "workspace": [], "expected": False},
    {"text": "What's this app do?", "harness": "contract-review", "workspace": [], "expected": False},
    # ... etc
]
```

Parametrize via `@pytest.mark.parametrize`. Mock the LLM (CI cost) but use realistic responses — gpt-4o-mini's actual sentinel-emission behavior under each prompt is the eval target; CI stub verifies the system prompt structure is correct, not the LLM's intelligence.

---

### `frontend/src/components/chat/MessageView.tsx` (MODIFY — D-22-14 download chip)

**Analog:** itself — extend the existing assistant bubble.

**Existing post-bubble slot for additions** (MessageView.tsx lines 142-150 + 151-166 ask-user pattern):
```tsx
<div
  className={`rounded-lg px-4 py-2 text-sm ${
    msg.role === 'user'
      ? 'bg-gradient-to-br from-primary to-[oklch(0.40_0.15_260)]...'
      : 'bg-muted/80 text-foreground backdrop-blur-sm'
  }`}
>
  <div className="whitespace-pre-wrap break-words">{msg.content}</div>
</div>
{/* Phase 19 / ASK-02 / D-27: question-bubble for unmatched ask_user tool call.
    Rendered AFTER normal content (UI-SPEC L235). No reply-mode UI — UI-SPEC L394. */}
{(() => {
  const askUser = isAskUserQuestion(msg, toolResults)
  if (!askUser.is || !askUser.question) return null
  return (
    <div role="note" aria-label={...} className="flex items-start gap-2 border-l-[3px] border-primary pl-3 mt-2">
      <MessageCircleQuestion size={16} className="text-primary shrink-0 mt-1" aria-hidden="true" />
      <p className="text-sm text-foreground leading-relaxed">{askUser.question}</p>
    </div>
  )
})()}
```

**Patch shape — add a new IIFE block after the ask-user block, gated on `msg.harness_artifact`** (Open Question 3 — recommend a new `attachments` field on the message OR a discrete `harness_artifact` SSE event captured into a slice):
```tsx
{/* Phase 22 / D-22-14: DOCX download chip on post-harness summary message */}
{(() => {
  const artifact = msg.harness_artifact   // new optional field
  if (!artifact?.file_path || !artifact?.signed_url) return null
  return (
    <a
      href={artifact.signed_url}
      download={artifact.file_path}
      role="link"
      aria-label={t('harness.docx.downloadAriaLabel')}
      className="flex items-center gap-2 mt-2 px-3 py-2 rounded border border-border/50 hover:bg-accent/50 transition-colors text-sm text-foreground"
      data-testid="harness-docx-chip"
    >
      <FileText size={16} className="text-primary shrink-0" aria-hidden="true" />
      <span className="flex-1 truncate">{artifact.file_path}</span>
      <Download size={14} className="text-muted-foreground" aria-hidden="true" />
    </a>
  )
})()}
```

**Recommendation — Open Question 3:** use a new `harness_artifact` SSE event emitted by the engine after `post_execute` succeeds, and surface it on the post-harness assistant message via `useChatState` reducer. This avoids parsing markdown links and keeps the artifact metadata structured. The frontend SSE handler already routes harness events through `useChatState` (precedent: `harnessRun`, `batchProgress` slices in HarnessBanner).

Imports to add at top of MessageView.tsx (line 2 has the existing lucide imports):
```tsx
import { GitFork, ChevronLeft, ChevronRight, ShieldAlert, MessageCircleQuestion, FileText, Download } from 'lucide-react'
```

**Glass rule reminder (CLAUDE.md):** the chip is a persistent element — NO `backdrop-blur`. Use `bg-accent/50` for hover only, not as a base.

---

### `frontend/src/components/chat/WorkspacePanel.tsx` (NO CHANGE)

**Already handles DOCX appearance automatically.** The DOCX is written to workspace_files via `write_binary_file` with `source="harness"`, and `register_sandbox_files`/the workspace SSE listener fires `workspace_updated` which triggers re-fetch of file list. The `SOURCE_COLORS` map at lines 80-84 currently has `agent`, `sandbox`, `upload` only — Phase 22 should add a `harness` entry. Patch site:
```tsx
const SOURCE_COLORS: Record<WorkspaceFile['source'], string> = {
  agent: 'bg-purple-500/20 text-purple-300',
  sandbox: 'bg-blue-500/20 text-blue-300',
  upload: 'bg-zinc-500/20 text-zinc-300',
  harness: 'bg-green-500/20 text-green-300',  // NEW — Phase 22
}
```
Also extend `i18n` `workspace.source.harness` translation key. The `WorkspaceFile['source']` type union (defined in `frontend/src/hooks/useChatState.ts`) needs `'harness'` added.

Click handler at lines 121-151 already routes binaries to a download via `window.open(...)` with the GET endpoint that 307-redirects to a signed URL — DOCX falls through this path unchanged.

---

## Shared Patterns (Cross-Cutting)

### B4 Single-Registry Invariant (SEC-04)

**Source:** `backend/app/routers/chat.py:1851-1928` (`_gatekeeper_stream_wrapper`)
**Apply to:** Any new code path that makes LLM calls during a harness turn

The same `ConversationRegistry` instance is built ONCE at the top of `_gatekeeper_stream_wrapper` and passed verbatim to gatekeeper, run_harness_engine, and summarize_harness_run. **Never re-mint.** If Phase 22's `post_execute` DOCX generator needs to call an LLM (it shouldn't — it's a sandbox python-docx script), it MUST receive the same registry.

```python
registry = await _get_or_build_conversation_registry(thread_id, sys_settings)
# ...
async for ev in run_harness_engine(..., registry=registry, ...):
async for ev in summarize_harness_run(..., registry=registry, ...):  # SAME instance
```

### Egress Filter Wrap (SEC-04)

**Source:** `backend/app/services/harness_engine.py:543-554` (LLM_SINGLE pre-call) + `backend/app/services/post_harness.py:212-229` (post-summary pre-call)
**Apply to:** Any new LLM call site
```python
if registry is not None:
    payload = json.dumps(messages, ensure_ascii=False)
    er = egress_filter(payload, registry, None)
    if er.tripped:
        # Return error / refusal — never let blocked payload reach the LLM
        return {"error": "egress_blocked", "code": "PII_EGRESS_BLOCKED", ...}
```
Gatekeeper, engine, post_harness, sub_agent_loop all already do this. Phase 22 inherits the protection — no new wiring needed for the harness phases. The only NEW LLM calls Phase 22 introduces are CR-04's max-10-round agent (already covered by sub_agent_loop's egress wrapper) and CR-05's per-chunk LLM (covered if it routes through `OpenRouterService.complete_with_tools` which the engine's LLM_SINGLE dispatcher uses).

### Programmatic Phase Error Contract

**Source:** `backend/app/harnesses/smoke_echo.py:60-66`
**Apply to:** CR-01 (Document Intake), CR-05 (Clause Extraction)
```python
try:
    files = await ws.list_files(thread_id)
except Exception as exc:
    logger.error("...", exc_info=True)
    return {"error": "<descriptive_key>", "code": "<UPPER_SNAKE>", "detail": str(exc)[:500]}
```
**500-char detail cap** is the project convention — it limits SSE payload bloat and avoids leaking stack traces (D-19 sanitization invariant from harness_engine.py:159).

### Audit Logging (OBS-02)

**Source:** `backend/app/services/gatekeeper.py:245-251` + `backend/app/services/post_harness.py:220-226`
**Apply to:** Any new mutation or sensitive operation
```python
audit_service.log_action(
    user_id=user_id,
    user_email=user_email,
    action="contract_review_docx_generated",   # snake_case
    resource_type="harness_runs",
    resource_id=harness_run_id,
)
```
Phase 22 should log: `contract_review_started` (gatekeeper trigger), `contract_review_docx_generated` (post_execute success), `contract_review_docx_failed` (post_execute fallback), `contract_review_completed`.

### Feature-Flag Dark Launch (D-16)

**Source:** `backend/app/config.py:184-195` (harness_enabled, harness_smoke_enabled)
**Apply to:** Any new behavior gated by a flag
```python
# Phase 22 / v1.3 (CR-*, DOCX-*; D-16): Contract Review harness flag.
# When False: Contract Review not registered in HarnessRegistry, gatekeeper
# never sees it as a candidate, post_execute DOCX path inert. Codebase
# byte-identical to pre-Phase-22 (D-16 invariant).
contract_review_enabled: bool = False
```
**OFF-mode invariant:** the codebase must be byte-identical to pre-Phase-22 when both `harness_enabled=False` AND `contract_review_enabled=False`. Test this with a fixture that snapshots the registered harness list.

### Tool Curation via `phase.tools`

**Source:** `backend/app/services/harness_engine.py:633-634` (LLM_AGENT) + `harness_engine.py:845-848, 965` (LLM_BATCH_AGENTS)
**Apply to:** CR-04 (LLM_AGENT, max 10 rounds), CR-06 (LLM_BATCH_AGENTS, batch_size=5), CR-07 (LLM_BATCH_AGENTS, batch_size=5)

Engine already strips `PANEL_LOCKED_EXCLUDED_TOOLS` and propagates curated tools to sub-agents. Phase 22 just sets:
```python
PhaseDefinition(
    name="load-playbook",   # CR-04
    phase_type=PhaseType.LLM_AGENT,
    tools=["search_documents", "analyze_document"],  # only these reach sub-agent
    ...
)
```

### `search_documents` filter parameters (D-22-05, D-22-06)

**Source:** `backend/app/services/tool_service.py:51-67` (tool definition) + `tool_service.py:534-558` (impl)
**Apply to:** CR-04, CR-06, CR-07 sub-agent prompts

```python
# Tool definition (tool_service.py:39-71)
{
    "name": "search_documents",
    "parameters": {
        "properties": {
            "query": {"type": "string"},
            "filter_tags": {"type": "array", "items": {"type": "string"}},  # D-22-05 uses this
            "filter_folder_id": {"type": "string"},
            "filter_date_from": {"type": "string"},
            "filter_date_to": {"type": "string"},
            # NOTE: filter_doc_ids does NOT currently exist in this tool def
        },
    },
},
```

**IMPORTANT GAP — D-22-06 (`filter_doc_ids`):** the existing `search_documents` tool def at `tool_service.py:39-71` does NOT currently expose `filter_doc_ids`. CR-06/07's per-clause grounding strategy (D-22-06 — call `search_documents(query=clause_text, filter_doc_ids=clause_category_to_playbook[category])`) requires either:
1. Adding `filter_doc_ids` to the tool definition + plumbing through to `HybridRetrievalService.retrieve()`
2. OR using the existing `filter_tags` + a per-doc tag scheme

**Recommendation:** Tool Registry adapter-wrap invariant (CLAUDE.md line ~178: never edit `tool_service.py` lines 1-1283). Adding a parameter to the `search_documents` tool definition at line 39-71 IS within the protected range. Phase 22 must either (a) get explicit approval for this edit (it's an additive parameter, not a behavioral change) or (b) implement filter_doc_ids via a NEW adapter-wrapped tool registered AFTER line 1283. Planner must resolve this — call out as a gating decision in plan 22-01 or 22-02.

### Tool Registry adapter-wrap invariant (CLAUDE.md gotcha)

```
backend/app/services/tool_service.py lines 1-1283 are PROTECTED.
Verify: head -n 1283 backend/app/services/tool_service.py | shasum -a 256
```
Any new tool registers via `tool_registry.register()` adapter-wrap APPENDED below that boundary. If Phase 22 adds `filter_doc_ids` to `search_documents`, it must either:
- Get explicit invariant exemption (additive parameter, not behavioral)
- OR ship a new tool `search_documents_by_doc_ids` registered below line 1283

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | | | Every Phase 22 file has a clean analog. The infrastructure shipped in Phases 20-21 covers all primitives. |

---

## Frontend Type Update (small but load-bearing)

**File:** `frontend/src/hooks/useChatState.ts` (likely — check exact path)
**Patch:** the `WorkspaceFile['source']` type union must add `'harness'` so `WorkspacePanel.tsx`'s `SOURCE_COLORS` keying compiles. Also add a new SSE event handler for `harness_artifact` if Open Question 3 resolves toward the dedicated-event path.

Existing SSE event types are declared in `frontend/src/lib/database.types.ts` per a recent fix (`fix(types): widen SSEEvent union to include Phase 20-21 harness events`, commit `956af2e` per gitStatus). Phase 22 may need to widen it again for `harness_artifact`.

---

## Metadata

**Analog search scope:**
- `backend/app/harnesses/` (3 files — `__init__.py`, `types.py`, `smoke_echo.py`)
- `backend/app/services/` (gatekeeper.py, harness_engine.py, post_harness.py, workspace_service.py, harness_registry.py, tool_service.py)
- `backend/app/routers/chat.py` (HIL resume + gatekeeper wrapper)
- `backend/sandbox/` (Dockerfile, tool_client.py)
- `backend/app/config.py` (feature flags)
- `frontend/src/components/chat/` (HarnessBanner.tsx, MessageView.tsx, WorkspacePanel.tsx)

**Files scanned:** 12 source files + ~6 grep verifications

**Pattern extraction date:** 2026-05-04

**Key invariants captured for planner:**
1. B4 single-registry invariant (chat.py:1851-1928)
2. CR-21-01 circular-import lesson (harness_registry.py:14-23 uses TYPE_CHECKING)
3. PANEL-03 tool exclusion via `PANEL_LOCKED_EXCLUDED_TOOLS` (types.py:106)
4. D-16 OFF-mode byte-identical (config.py + auto-import gating)
5. HARN-05 Pydantic schema enforcement via `response_format=json_schema` strict mode (harness_engine.py:564-575)
6. D-22-15 non-fatal DOCX fallback — error dict, NOT exception
7. SEC-04 egress filter wrap on every cloud-LLM payload
8. Tool Registry adapter-wrap invariant (tool_service.py:1-1283 frozen) — `filter_doc_ids` for D-22-06 must resolve this
