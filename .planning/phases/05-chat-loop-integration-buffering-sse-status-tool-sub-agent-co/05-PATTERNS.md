# Phase 5: Chat-Loop Integration — Pattern Map

**Mapped:** 2026-04-27
**Files analyzed:** 10 (1 NEW backend helper + 5 MODIFY backend + 1 MODIFY backend `__init__.py` + 2 MODIFY frontend + 1 NEW backend test)
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/services/redaction/tool_redaction.py` (NEW) | service helper / recursive walker | transform | `backend/app/services/redaction_service.py` (`de_anonymize_text` Pass 1) + `backend/app/services/redaction/registry.py` patterns | role-match (no recursive-walker analog yet; closest is the per-string registry-driven transform) |
| `backend/app/routers/chat.py` (MODIFY) | router / SSE event-driven streamer | event-driven streaming + tool-loop | itself (extending in place) — companion analog: `backend/app/services/redaction_service.py:348` `redact_text` for the lock + traced + degrade pattern | exact (extending current shape) |
| `backend/app/services/agent_service.py` (MODIFY) | service / classifier | request-response (single LLM call) | itself + `backend/app/services/llm_provider.py:172` (`call`) for the egress-wrapped LLM-call pattern | exact (extending current shape) |
| `backend/app/services/redaction_service.py` (MODIFY — early-return gate + `redact_text_batch` + `de_anonymize_text` degrade tags) | service / batch transform | batch transform | itself (`redact_text` at line 348 = single-string analog; `_redact_text_with_registry` reused inside batch) | exact |
| `backend/app/services/tool_service.py` (MODIFY — signature change only) | service / dispatcher | request-response | itself (signature gains `*, registry=None` keyword-only) | exact |
| `backend/app/services/redaction/__init__.py` (MODIFY — re-export) | package barrel | n/a | itself (current Phase 1-2 re-export shape at lines 29-36) | exact |
| `frontend/src/lib/database.types.ts` (MODIFY — add `RedactionStatusEvent` variant) | TS types | n/a | itself (current `SSEEvent` discriminated union at lines 35-64) | exact |
| `frontend/src/hooks/useChatState.ts` (MODIFY — dispatch case + status state) | React hook / SSE consumer | event-driven | itself (current dispatch chain at lines 155-181) | exact |
| `backend/tests/api/test_phase5_integration.py` (NEW) | pytest integration suite | request-response + SSE consumption | `backend/tests/api/test_phase4_integration.py` (Phase 4 SC#1..SC#5 + B4 + Soft-Fail mirror) | exact (mirror layout) |

---

## Pattern Assignments

### 1. `backend/app/services/redaction/tool_redaction.py` (NEW — service helper / transform)

**Closest analog:** `backend/app/services/redaction_service.py` Pass-1 sort-by-length-DESC pattern (lines 743-763) for the per-string transform; `backend/app/services/redaction/__init__.py` lines 27-31 for the from-future-imports / module-doc shape.

**Imports & module-doc pattern to copy** (mirror `redaction_service.py:1-35` style and `prompt_guidance.py` minimal-deps shape):

```python
"""Phase 5 D-91 / D-92: tool I/O symmetry walkers.

Recursive walkers over arbitrary JSON-shaped tool args (LLM -> real) and
tool outputs (real -> surrogate). Centralized so tool_service.py stays
tool-agnostic. Skip rules: UUID regex (^[0-9a-f-]{36}$) and len(s) < 3.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from app.services.tracing_service import traced
from app.services.redaction.registry import ConversationRegistry
from app.services.redaction_service import RedactionService

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_MIN_LEN = 3
_MAX_DEPTH = 10  # Claude's discretion — pathological-input guard
```

**Recursive walker shape to replicate** (model on the imperative tree-walk style used in `_redact_text_with_registry` — collect strings, transform, re-zip):

```python
@traced(name="redaction.deanonymize_tool_args")
async def deanonymize_tool_args(
    args: Mapping[str, Any],
    registry: ConversationRegistry,
    redaction_service: RedactionService,
) -> dict[str, Any]:
    """LLM-emitted surrogate-form args -> real values for tool execution."""
    return await _walk(args, registry, redaction_service, direction="deanon", depth=0)
```

**De-anon transform leaf pattern to copy from `redaction_service.py:749-763`** (Pass-1-only registry exact-match, longest-surrogate-wins):

```python
# Sort entries longest-surrogate-first to prevent partial-overlap corruption
entries_sorted = sorted(
    registry.entries(),
    key=lambda m: (len(m.surrogate_value), len(m.real_value)),
    reverse=True,
)
out = leaf_string
for m in entries_sorted:
    out = re.sub(re.escape(m.surrogate_value), m.real_value, out, flags=re.IGNORECASE)
return out
```

**Anon-side leaf pattern: collect-then-batch (D-92 batch entry)** — gather every leaf string into a list, call `redaction_service.redact_text_batch(strings, registry)` ONCE, then re-zip back into the structure.

**What shape to replicate:** Single file with two `@traced` async public functions + a private `_walk(node, registry, svc, direction, depth)` recursive helper. Skip rules applied at every leaf-string boundary (`if _UUID_RE.fullmatch(s) or len(s) < _MIN_LEN: return s`). Recursion handles `dict`, `list`, `tuple`; everything else returned identity. Depth-limited to `_MAX_DEPTH`.

**What NOT to do:**
- DO NOT import `tool_service` (circular). The walker is invoked by the chat router, not by tools.
- DO NOT call `redaction_service.redact_text` per-leaf in a loop on the anon side — N lock acquisitions vs the single-acquisition batch (D-92).
- DO NOT recurse into `bytes`, Pydantic models, or arbitrary objects — only `dict`/`list`/`tuple` (matches actual tool-output shapes from `tool_service.py`).
- DO NOT mutate the input structure in place; return a new dict (matches Phase 1 D-13/D-14 immutability convention).
- DO NOT log any leaf string content (B4 — counts and types only).

---

### 2. `backend/app/routers/chat.py` (MODIFY — top-level redaction branch + buffering + SSE status + walker invocations + degrade + title-gen migration)

**Closest analog:** the file itself (`chat.py:164-291`). For the new `try/except` graceful-degrade wrapper (D-90), copy the shape from `chat.py:269-283` (title-gen `try/except: pass` non-blocking pattern). For SSE event encoding shape, every line at `chat.py:185, 206, 212, 250, 281, 285` is the canonical emit format.

**Top-level branch pattern to introduce after thread validation, BEFORE history-load** (D-83 / D-84 / D-86 / D-93):

```python
# Phase 5 D-86: per-turn registry load (one DB SELECT per turn).
from app.services.redaction.registry import ConversationRegistry
from app.services.redaction_service import get_redaction_service
from app.services.redaction.tool_redaction import (
    deanonymize_tool_args, anonymize_tool_output,
)
registry = await ConversationRegistry.load(body.thread_id)
redaction_service = get_redaction_service()
redaction_on = settings.pii_redaction_enabled  # D-83 global env var
```

**Batch history-anon pattern (D-93)** — replaces per-message redact in a loop. Mirrors the existing branch-aware history shape at `chat.py:75 / 85`:

```python
if redaction_on:
    raw = [m["content"] for m in history] + [body.message]
    anonymized = await redaction_service.redact_text_batch(raw, registry)
    history = [{**h, "content": a} for h, a in zip(history, anonymized[:-1])]
    anonymized_message = anonymized[-1]
else:
    anonymized_message = body.message
```

**SSE emit pattern to copy verbatim** (chat.py:185 / 206 / 250 / 281):

```python
yield f"data: {json.dumps({'type': 'redaction_status', 'stage': 'anonymizing'})}\n\n"
# ... after stream buffer completes, before de-anon runs:
yield f"data: {json.dumps({'type': 'redaction_status', 'stage': 'deanonymizing'})}\n\n"
```

**Buffering pattern (D-87)** — replace the current progressive yield at `chat.py:209-212` and `chat.py:240-243`:

```python
full_response = ""
async for chunk in openrouter_service.stream_response(messages, model=llm_model):
    if not chunk["done"]:
        full_response += chunk["delta"]
        if not redaction_on:
            # Phase 0 verbatim path — progressive deltas
            yield f"data: {json.dumps({'type': 'delta', 'delta': chunk['delta'], 'done': False})}\n\n"
# Redaction-on path: emit one batch after de-anon
if redaction_on:
    yield f"data: {json.dumps({'type': 'redaction_status', 'stage': 'deanonymizing'})}\n\n"
    try:
        deanon_text = await redaction_service.de_anonymize_text(
            full_response, registry, mode=settings.fuzzy_deanon_mode,
        )
    except Exception as exc:  # D-90 graceful degrade
        logger.warning(
            "deanon_degraded feature=deanonymize_text fallback_mode=none "
            "error_class=%s", type(exc).__name__,
        )
        deanon_text = await redaction_service.de_anonymize_text(
            full_response, registry, mode="none",
        )
    full_response = deanon_text
    yield f"data: {json.dumps({'type': 'delta', 'delta': full_response, 'done': False})}\n\n"
```

**Tool-loop walker invocation (D-91)** — wrap around the existing `tool_service.execute_tool` at `chat.py:134-136`:

```python
if redaction_on:
    real_args = await deanonymize_tool_args(func_args, registry, redaction_service)
    tool_output = await tool_service.execute_tool(
        func_name, real_args, user_id, tool_context, registry=registry,
    )
    tool_output = await anonymize_tool_output(tool_output, registry, redaction_service)
else:
    tool_output = await tool_service.execute_tool(
        func_name, func_args, user_id, tool_context,
    )
```

**Tool-event skeleton emit pattern (D-89)** — modify chat.py:129-131 + chat.py:146-148:

```python
if redaction_on:
    yield f"data: {json.dumps({'type': 'tool_start', 'tool': func_name})}\n\n"
else:
    yield f"data: {json.dumps({'type': 'tool_start', 'tool': func_name, 'input': func_args})}\n\n"
```

**Pre-flight egress wrapper pattern (D-94)** — copy from `llm_provider.py:185-198` (the proven cloud-mode pattern). Apply at three sites: `_run_tool_loop`'s `complete_with_tools` (chat.py:115-117), branch A's `stream_response` (chat.py:209), branch B's `stream_response` (chat.py:240):

```python
from app.services.redaction.egress import egress_filter, _EgressBlocked
if redaction_on:
    payload = json.dumps(messages, ensure_ascii=False)
    result = egress_filter(payload, registry, provisional_surrogates=None)
    if result.tripped:
        logger.warning(
            "egress_blocked event=egress_blocked feature=chat_stream "
            "entity_count=%d", result.entity_count,
        )
        yield f"data: {json.dumps({'type': 'redaction_status', 'stage': 'blocked'})}\n\n"
        yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"
        return  # abort cleanly — D-94: no algorithmic fallback
```

**Title-gen migration (D-96)** — replace `chat.py:277` `openrouter_service.complete_with_tools(title_messages)` with:

```python
from app.services.llm_provider import LLMProviderClient
llm_provider_client = LLMProviderClient()
# title_messages already use anonymized body.message from D-93 batch
title_result = await llm_provider_client.call(
    feature="title_gen", messages=title_messages, registry=registry,
)
new_title_raw = (title_result.get("title") or title_result.get("raw") or "").strip().strip('"\'')[:80]
if redaction_on and new_title_raw:
    new_title = await redaction_service.de_anonymize_text(new_title_raw, registry, mode="none")
else:
    new_title = new_title_raw
```

**What NOT to do:**
- DO NOT modify `OpenRouterService` (D-94 explicit: wrap at call site only — refactor is Phase 6+).
- DO NOT split the buffer into fake-stream chunks (D-87 / FR-6.3 verbatim violation; misleads LangSmith spans).
- DO NOT emit `redaction_status` per-call (only ONCE per stage — anonymizing / deanonymizing). FR-6.2 is singular.
- DO NOT include `input` / `output` in `tool_start` / `tool_result` when redaction is ON (D-89 — payloads are surrogate-form).
- DO NOT run `de_anonymize_text` over `tool_start` / `tool_result` payloads (D-89 explicit: skeleton mode is the intentional choice).
- DO NOT skip the egress filter on the chat LLM call (NFR-2 explicit defense-in-depth).
- DO NOT call `redact_text` per-history-message in a loop (D-93 — batch primitive only; N lock acquisitions otherwise).
- DO NOT change the user-message persistence shape (D-85 — `body.message` real form, line 96 unchanged).
- DO NOT add a `provisional_surrogates` argument to the egress filter on the chat path (D-94 explicit: `provisional=None` because D-93 commits everything before any cloud contact).
- DO NOT swallow the de-anon exception silently — log per D-90 + tag the @traced span.

---

### 3. `backend/app/services/agent_service.py` (MODIFY — input anonymization for `classify_intent` + pre-flight egress wrapper + retire per-thread TODO)

**Closest analog:** the file itself, lines 135-166 (`classify_intent`). For the egress wrapper, copy the cloud-mode pre-flight pattern from `llm_provider.py:185-198`.

**Signature stays shape-identical** (D-96 — caller in chat.py passes already-anonymized strings):

```python
@traced(name="classify_intent")
async def classify_intent(
    message: str,        # ← caller passes anonymized body.message (D-93)
    history: list[dict], # ← caller passes anonymized history items (D-93)
    openrouter_service,
    model: str,
    registry: "ConversationRegistry | None" = None,  # NEW — for egress filter
) -> OrchestratorResult:
```

**Pre-flight egress wrapper to add inside the `try:` block before `complete_with_tools`** (D-94 reused at this auxiliary call site):

```python
if registry is not None and get_settings().pii_redaction_enabled:
    from app.services.redaction.egress import egress_filter
    payload = json.dumps(messages, ensure_ascii=False)
    result = egress_filter(payload, registry, provisional_surrogates=None)
    if result.tripped:
        logger.warning(
            "egress_blocked event=egress_blocked feature=classify_intent "
            "entity_count=%d", result.entity_count,
        )
        return OrchestratorResult(agent="general", reasoning="egress_blocked")
```

**TODO retirement (D-83)** — delete the `Phase 5 may move to per-thread when per-thread flags ship` comment block at lines 10-15. The import-time `_PII_GUIDANCE` binding STAYS — it's correct under D-83's static-process-lifetime contract (the env var is set once at process start).

**What NOT to do:**
- DO NOT anonymize inside `classify_intent` itself (D-93 chokepoint principle — caller passes already-anonymized values).
- DO NOT migrate `classify_intent` to `LLMProviderClient` (D-96 explicit — `response_format=json_object` stays on `OpenRouterService`; only `title_gen` migrates).
- DO NOT raise on egress trip — fall back to `OrchestratorResult(agent="general")` (matches existing fallback at line 165-166).
- DO NOT re-bind `_PII_GUIDANCE` per-call (Phase 5 D-83 keeps import-time semantics correct).
- DO NOT touch the 4 `AgentDefinition` system_prompt suffixes (`+ _PII_GUIDANCE` at lines 30, 50, 65, 85) — Phase 4 D-79 already wires them correctly.

---

### 4. `backend/app/services/redaction_service.py` (MODIFY — early-return gate at line 388-393 + new `redact_text_batch` + degrade tags on `de_anonymize_text`)

**Closest analog:** the file itself. `redact_text` (line 348) is the single-string analog for the new batch primitive. The existing `_get_thread_lock` (line 340) is reused. The TODO comment at lines 388-393 is the literal site for D-84.

**Early-return gate pattern (D-84)** — materialize the existing TODO at lines 388-393, BEFORE `_get_thread_lock`:

```python
@traced(name="redaction.redact_text")
async def redact_text(self, text, registry=None) -> RedactionResult:
    # Phase 5 D-84: lock-free off-mode early return.
    if not get_settings().pii_redaction_enabled:
        return RedactionResult(
            anonymized_text=text, entity_map={},
            hard_redacted_count=0, latency_ms=0.0,
        )
    if registry is None:
        return await self._redact_text_stateless(text)
    # ... existing lock + _redact_text_with_registry path unchanged
```

**New `redact_text_batch` shape to add (D-92)** — model on the lock-acquire pattern at `redact_text` lines 401-417:

```python
@traced(name="redaction.redact_text_batch")
async def redact_text_batch(
    self, texts: list[str], registry: ConversationRegistry,
) -> list[str]:
    """D-92: single asyncio.Lock acquisition spans the whole batch.
    Per-string _redact_text_with_registry runs internally (no NER refactor).
    Returns anonymized strings in the same order as input.
    """
    if not get_settings().pii_redaction_enabled:
        return list(texts)  # D-84 off-path identity
    lock = await self._get_thread_lock(registry.thread_id)
    async with lock:
        results: list[str] = []
        for t in texts:
            r = await self._redact_text_with_registry(t, registry)
            results.append(r.anonymized_text)
    return results
```

**Degrade-tag pattern on `de_anonymize_text` (D-90)** — tag the @traced span (per `tracing_service.py` convention, the @traced decorator at line 681 is reused unchanged; degrade context lives in the caller's wrapper at chat.py — see entry #2). Add WARNING log at the de-anon raise site only if internal pass-2 fuzzy-LLM raises; that path is already inside `de_anonymize_text` and Phase 4 D-78 already handles soft-fail there. NO algorithmic change to the method itself in Phase 5 — D-90's wrapper lives in the chat router (entry #2).

**What NOT to do:**
- DO NOT add a `de_anonymize_text_batch` method (per-string de-anon is a pure registry lookup; no lock needed; D-92 explicit reasoning).
- DO NOT release the lock between strings inside `redact_text_batch` (Phase 6 micro-optimization — Claude's Discretion in CONTEXT explicitly defers).
- DO NOT change the existing `_redact_text_with_registry` signature (Phase 4 already shipped — re-entrant call is safe per memory observation #3221).
- DO NOT add Presidio-level batch NER (Phase 6 PERF-02 deferred per CONTEXT).
- DO NOT bypass the `INSERT-ON-CONFLICT-DO-NOTHING` upsert (Phase 2 D-32 — re-runs absorb correctly).
- DO NOT refactor `de_anonymize_text` to add a `try/except` for D-90 — the wrapper lives at the chat.py call site (D-90 explicit) so the method's existing 3-pass contract stays auditable.

---

### 5. `backend/app/services/tool_service.py` (MODIFY — signature change only)

**Closest analog:** the file itself. The dispatch switch (lines 254-305) stays UNCHANGED.

**Signature change (D-86 / D-91)** — append a keyword-only `registry` param:

```python
@traced(name="execute_tool")
async def execute_tool(
    self,
    name: str,
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    registry: "ConversationRegistry | None" = None,  # NEW (D-86)
) -> dict:
    """Dispatch tool execution by name."""
    # Body UNCHANGED — D-91 keeps tool_service tool-agnostic.
    if name == "search_documents":
        return await self._execute_search_documents(...)
    # ... etc
```

**What NOT to do:**
- DO NOT thread `registry` into the per-tool `_execute_*` helpers (D-91 — centralized walker; per-tool wiring sprawl is exactly what the walker prevents).
- DO NOT add any redaction calls inside this file (`tool_service.py` stays redaction-unaware).
- DO NOT make `registry` a positional parameter (keyword-only `*` keeps existing call sites at chat.py:134 backward-compatible during migration).
- DO NOT import `ConversationRegistry` at runtime — use `TYPE_CHECKING` import (matches `llm_provider.py:46-47` pattern).
- DO NOT change the `@traced(name="execute_tool")` decorator — the span tag stays stable for OBS audit continuity.

---

### 6. `backend/app/services/redaction/__init__.py` (MODIFY — re-export `deanonymize_tool_args` + `anonymize_tool_output`)

**Closest analog:** the file itself. Current shape at lines 27-36 is the canonical Phase 1-2 re-export pattern.

**Pattern to extend (continuation of lines 29-36):**

```python
from app.services.redaction.errors import RedactionError
from app.services.redaction.registry import ConversationRegistry, EntityMapping
from app.services.redaction.tool_redaction import (  # NEW (D-91)
    anonymize_tool_output,
    deanonymize_tool_args,
)

__all__ = [
    "RedactionError",
    "ConversationRegistry",
    "EntityMapping",
    "anonymize_tool_output",   # NEW
    "deanonymize_tool_args",   # NEW
]
```

**What NOT to do:**
- DO NOT re-export `RedactionService` or `get_redaction_service` here (the file's docstring at lines 11-21 explicitly forbids it — circular-import via `__init__ → redaction_service → anonymization → detection → uuid_filter → __init__`).
- DO NOT re-export `RedactionResult` (same reason — leaf module only).
- DO NOT add `from __future__ import annotations` removal — keep line 27 intact.

---

### 7. `frontend/src/lib/database.types.ts` (MODIFY — add `RedactionStatusEvent` variant + extend `SSEEvent` union)

**Closest analog:** the file itself, lines 35-64. `AgentStartEvent` (line 47-51) and `ThreadTitleEvent` (line 58-62) are the canonical discriminated-union variant shape.

**Pattern to extend (insert before line 64):**

```typescript
export interface RedactionStatusEvent {
  type: 'redaction_status'
  stage: 'anonymizing' | 'deanonymizing' | 'blocked'
}

export type SSEEvent =
  | DeltaEvent
  | ToolStartEvent
  | ToolResultEvent
  | AgentStartEvent
  | AgentDoneEvent
  | ThreadTitleEvent
  | RedactionStatusEvent  // NEW (D-88 / D-94)
```

**Also relax `ToolStartEvent.input` and `ToolResultEvent.output`** to optional, since D-89's skeleton mode omits them when redaction is ON:

```typescript
export interface ToolStartEvent {
  type: 'tool_start'
  tool: string
  input?: Record<string, unknown>  // optional — omitted in D-89 skeleton mode
}

export interface ToolResultEvent {
  type: 'tool_result'
  tool: string
  output?: Record<string, unknown>  // optional — omitted in D-89 skeleton mode
}
```

**What NOT to do:**
- DO NOT collapse `redaction_status` into the existing `delta`/`agent_*` shape (CONTEXT line 185 — discriminated variant is the chosen design).
- DO NOT make `stage` `string` — keep the literal union for exhaustiveness checking in the dispatch switch (line 175 of useChatState.ts).
- DO NOT export the variant without adding it to the `SSEEvent` union (consumers do `event.type === 'redaction_status'` narrowing).
- DO NOT remove `input`/`output` entirely — when redaction is OFF, they're still populated (SC#5 backward-compat).

---

### 8. `frontend/src/hooks/useChatState.ts` (MODIFY — dispatch case for `redaction_status` + status state)

**Closest analog:** the file itself, lines 155-181. The `agent_start` / `agent_done` dispatch (lines 161-164) is the canonical shape for a status-only event with no payload accumulation.

**State to add near line 20** (mirrors `activeAgent` shape at line 20):

```typescript
const [redactionStage, setRedactionStage] = useState<
  'anonymizing' | 'deanonymizing' | 'blocked' | null
>(null)
```

**Reset alongside other streaming state** (line 117-121, line 198-201):

```typescript
setRedactionStage(null)  // add to both reset sites
```

**Dispatch case to add inside the `for (const line of lines)` block** (after line 173, before the `else` delta-accumulator at line 174):

```typescript
} else if (event.type === 'redaction_status') {
  setRedactionStage(event.stage)
  if (event.stage === 'blocked') {
    // Egress trip — turn aborted; UI shows error indicator
    setStreamingContent('') // clear partial text
  }
}
```

**Return new state from the hook** so consumers (`ChatPage` / message bubble) can render the spinner:

```typescript
return {
  // ... existing fields
  redactionStage,
}
```

**What NOT to do:**
- DO NOT change the existing `delta` accumulator path at line 174-181 (D-87 — single-batch delta renders identically to many small deltas; SC#5 backward-compat).
- DO NOT clear `streamingContent` on `anonymizing` / `deanonymizing` stages — only on `blocked` (the streaming bubble stays mounted, status text overlays).
- DO NOT add a `useTransition` or `Suspense` wrapper (CONTEXT line 241 — Phase 5 minimum is plain conditional rendering; full UX polish deferred).
- DO NOT add i18n strings inline — defer to the `I18nProvider` (CONTEXT line 285-286 lists the 3 keys: "Anonymizing…" / "Restoring names…" / "Egress blocked"; that's the i18n maintainer's call).
- DO NOT swallow unknown event types — keep the `else` branch as the catch-all delta accumulator.

---

### 9. `backend/tests/api/test_phase5_integration.py` (NEW — 7 test classes mirroring Phase 4 layout)

**Closest analog:** `backend/tests/api/test_phase4_integration.py` (609 lines, 17 tests, SC#1..SC#5 + B4 + Soft-Fail). Direct mirror per D-97.

**Module-doc + imports pattern to copy from Phase 4 lines 1-52:**

```python
"""ROADMAP Phase 5 SC#1..SC#5 integration tests + B4 / Egress-Trip bonus coverage.

Mirrors backend/tests/api/test_phase4_integration.py (Phase 4 SC#1..SC#5 + B4) —
same per-SC test-class layout, same _patched_settings helper, same MagicMock +
AsyncMock mock pattern for AsyncOpenAI, same caplog B4 invariants. Tests run
against live Supabase qedhulpfezucnfadlfiz; cloud LLM is always mocked (no real
egress).

Coverage map:
  SC#1 → TestSC1_PrivacyInvariant       (LLM payload audit — registry.entries() ⊄ payload)
  SC#2 → TestSC2_BufferingAndStatus     (SSE event sequence with redaction ON)
  SC#3 → TestSC3_SearchDocumentsTool    (search_documents de-anon args / re-anon output)
  SC#4 → TestSC4_SqlGrepAndSubAgent     (query_database + kb_grep + sub-agent registry threading)
  SC#5 → TestSC5_OffMode                (PII_REDACTION_ENABLED=false ⇒ baseline behavior)
  Bonus: TestB4_LogPrivacy_ChatLoop, TestEgressTrip_ChatPath
"""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.redaction.egress import _EgressBlocked
from app.services.redaction.registry import ConversationRegistry, EntityMapping
from app.services.redaction_service import RedactionService

pytestmark = pytest.mark.asyncio
```

**Patched-settings helper pattern to copy from Phase 4 lines 58-82** — extend with Phase 5 toggles:

```python
def _patched_settings(
    *,
    pii_redaction_enabled: bool = True,
    fuzzy_mode: str = "none",
    agents_enabled: bool = False,  # Phase 5 covers both branches
) -> SimpleNamespace:
    real = get_settings()
    overrides = {f: getattr(real, f) for f in real.model_dump().keys()}
    overrides["pii_redaction_enabled"] = pii_redaction_enabled
    overrides["fuzzy_deanon_mode"] = fuzzy_mode
    overrides["agents_enabled"] = agents_enabled
    return SimpleNamespace(**overrides)
```

**SSE consumption pattern (NEW — not in Phase 4)** — use `TestClient` and parse `data: ` lines:

```python
def _consume_sse(response) -> list[dict]:
    events = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events
```

**Privacy-invariant assertion pattern (SC#1)** — captures every recorded LLM payload:

```python
captured_payloads: list[str] = []
async def _capture_create(*args, **kwargs):
    captured_payloads.append(json.dumps(kwargs.get("messages", [])))
    return _mock_llm_response({"content": "ok"})
mock_client = MagicMock()
mock_client.chat.completions.create = AsyncMock(side_effect=_capture_create)
with patch("app.services.openrouter_service._get_client", return_value=mock_client):
    # ... run chat turn
    for entry in registry.entries():
        for payload in captured_payloads:
            assert entry.real_value not in payload, \
                f"PII LEAK: {entry.real_value!r} in payload"
```

**Class layout to copy from Phase 4** — `TestSC1_*`, `TestSC2_*`, ..., `TestB4_*` style with one-method-per-assertion, fixtures via `_patched_settings` + `_seed_cluster`.

**B4 caplog invariant pattern (Phase 4 lines 540-580 already shipped)** — extend with Phase 5's D-90 degrade log + D-94 egress trip log:

```python
def test_no_pii_in_logs_during_chat_turn(caplog):
    caplog.set_level(logging.DEBUG, logger="app")
    # ... run chat turn that triggers de-anon-degrade + egress-trip paths
    for record in caplog.records:
        for entry in registry.entries():
            assert entry.real_value not in record.getMessage()
```

**What NOT to do:**
- DO NOT use real Cloud LLM traffic — always patch `_get_client` (Phase 4 precedent at lines 23-29 of CONTEXT).
- DO NOT seed PII into the `messages` table via direct INSERT bypassing the chat router — tests must exercise the router to catch event-sequence regressions.
- DO NOT assert on absolute event-index positions (e.g. `events[3]`) — the count of `tool_start`/`tool_result` pairs varies; instead assert relative ordering (e.g. `agent_start` index < `redaction_status:anonymizing` index < first `tool_start` index).
- DO NOT mock `ConversationRegistry.load` — use the live Supabase test project (Phase 4 fixture pattern; D-97 explicit).
- DO NOT mock `RedactionService` itself — exercise the real service so the privacy invariant covers the actual code path (mocking it would test the test, not the system).
- DO NOT skip `_clear_llm_client_cache` autouse fixture (Phase 4 lines 99-110) — stale cached clients across tests cause flaky failures.
- DO NOT log raw PII inside the test code itself (B4 invariant applies to test logs too — assertions only).

---

## Shared Patterns

### Authentication / Authorization
**Source:** `backend/app/dependencies.get_current_user`
**Apply to:** all backend MODIFY targets (chat.py already wired at line 40 — no change).
**Pattern:** `user: dict = Depends(get_current_user)` — Phase 5 adds zero new auth surface.

### SSE Event Encoding
**Source:** `backend/app/routers/chat.py:185, 206, 212, 250, 281, 285`
**Apply to:** all new SSE emits in chat.py.
**Pattern:** `yield f"data: {json.dumps(payload_dict)}\n\n"` — single `data: ` line + double newline terminator. Headers at chat.py:290 (`Cache-Control: no-cache`, `X-Accel-Buffering: no`) preserve flush semantics — DO NOT change.

### Tracing / Observability
**Source:** `backend/app/services/tracing_service.py` `@traced` decorator
**Apply to:** every new public async function (`redact_text_batch`, `deanonymize_tool_args`, `anonymize_tool_output`).
**Pattern:** `@traced(name="redaction.<verb>")` immediately above the `async def`. Naming convention: `redaction.<method>` (matches `redaction_service.py:348, 681` style).

### Logging Privacy Invariant (B4)
**Source:** `backend/app/services/redaction_service.py:409-416, 449-458, 786-801`
**Apply to:** every new `logger.warning` / `logger.info` / `logger.debug` call in Phase 5.
**Pattern:** counts, latency_ms, mode strings, error_class names, 8-char SHA-256 hashes ONLY. NEVER raw text, real values, surrogate values, or matched span content. Phase 4 D-78 + Phase 5 D-90 + D-94 all extend this contract.

### Egress Filter (cloud-mode pre-flight)
**Source:** `backend/app/services/llm_provider.py:185-198`
**Apply to:** chat.py three call sites (D-94) + agent_service.py classify_intent (D-96).
**Pattern:** serialize `messages` to JSON via `json.dumps(messages, ensure_ascii=False)`, call `egress_filter(payload, registry, provisional_surrogates=None)`, on `result.tripped` log warning + emit error event + abort cleanly. NO algorithmic fallback on the chat path (D-94 explicit).

### Singleton Service Access
**Source:** `backend/app/services/redaction_service.py:1040-1041` (`@lru_cache get_redaction_service()`)
**Apply to:** all new chat.py / agent_service.py usage of `RedactionService`.
**Pattern:** `from app.services.redaction_service import get_redaction_service; svc = get_redaction_service()`. Module-level singleton — D-95's "share parent's redaction-service instance" is automatic.

### Per-Turn Registry Threading
**Source:** Phase 2 D-33 / `backend/app/services/redaction/registry.py` `ConversationRegistry.load(thread_id)`
**Apply to:** chat.py event_generator() top + signature plumbing into `_run_tool_loop`, `tool_service.execute_tool`, `agent_service.classify_intent`, walker invocations.
**Pattern:** ONE `await ConversationRegistry.load(body.thread_id)` per turn → instance threaded as parameter to every redaction call site. NO per-call-site `.load()` (N DB SELECTs).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | All 10 file targets have at least a role-match analog. The recursive-walker `tool_redaction.py` is the closest to "no analog" but it composes the existing `redact_text_batch` (new but modeled on `redact_text`) + Pass-1-only de-anon transform from `de_anonymize_text:749-763` — both proven-pattern composites, not from-scratch designs. |

---

## Metadata

**Analog search scope:** `backend/app/services/`, `backend/app/routers/`, `backend/app/services/redaction/`, `backend/tests/api/`, `frontend/src/lib/`, `frontend/src/hooks/`
**Files scanned:** 12 (chat.py, agent_service.py, redaction_service.py, redaction/__init__.py, redaction/egress.py, redaction/registry.py, tool_service.py, llm_provider.py, prompt_guidance.py, api.ts, database.types.ts, useChatState.ts, test_phase4_integration.py)
**Pattern extraction date:** 2026-04-27

---

## PATTERN MAPPING COMPLETE

**Phase:** 5 — Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage)
**Files classified:** 10 (1 NEW backend helper + 5 MODIFY backend + 1 MODIFY backend `__init__.py` + 2 MODIFY frontend + 1 NEW backend test)
**Analogs found:** 10 / 10

### Coverage
- Files with exact analog: 9 (all MODIFY targets + the test mirror of Phase 4)
- Files with role-match analog: 1 (`tool_redaction.py` — new recursive-walker, composes existing patterns)
- Files with no analog: 0

### Key Patterns Identified
- Per-turn `ConversationRegistry.load()` threaded as a parameter through every redaction call site (NO per-call-site loads — D-86 chokepoint).
- Single batched `redact_text_batch` at `event_generator()` top resolves all history + user message under ONE `asyncio.Lock` acquisition (D-92 / D-93).
- SSE emits follow the canonical `f"data: {json.dumps(payload)}\n\n"` shape; new `redaction_status` events use `{type, stage}` discriminated-variant form (D-88).
- Pre-flight `egress_filter(payload, registry, provisional_surrogates=None)` wraps every cloud LLM call site with `provisional=None` because D-93 commits all entities before any cloud contact (D-94).
- D-90 graceful-degrade wrapper (try / except → fall back to `de_anonymize_text(..., mode='none')`) lives at the chat.py call site, NOT inside `RedactionService` — preserves the method's auditable 3-pass contract.
- Tool I/O symmetry implemented by ONE central recursive walker (`tool_redaction.py`) — `tool_service.py` stays redaction-unaware; the only change there is a keyword-only `*, registry=None` parameter (D-91).
- B4 log-privacy invariant extends to every new logger call (counts / hashes / error_class only — NEVER raw values).
- Test suite mirrors Phase 4 layout exactly: 7 classes, `_patched_settings` helper, `_clear_llm_client_cache` autouse fixture, mocked `AsyncOpenAI` at the `_get_client` patch point.

### File Created
`/Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/.planning/phases/05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co/05-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns + line numbers in PLAN.md files for all 10 Phase 5 file targets.
