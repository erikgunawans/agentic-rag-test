---
phase: 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co
plan: 02
subsystem: redaction
tags: [pii, redaction, tool-symmetry, walker, recursive, tool-service, d-86, d-91, d-92]
requires:
  - 05-01-redaction-text-batch-primitive  # D-92 redact_text_batch
  - 04-03-fuzzy-deanonymization            # Pass-1 longest-surrogate-first transform reference
  - 02-conversation-scoped-registry        # ConversationRegistry.entries() / EntityMapping
provides:
  - tool_io_walker_module                  # backend/app/services/redaction/tool_redaction.py
  - execute_tool_registry_plumbing         # ToolService.execute_tool *, registry kwarg (D-86)
  - redaction_barrel_walker_re_exports     # from app.services.redaction import deanonymize_tool_args, anonymize_tool_output
affects:
  - backend/app/services/redaction/tool_redaction.py        # NEW (285 lines)
  - backend/app/services/tool_service.py                    # signature + TYPE_CHECKING import
  - backend/app/services/redaction/__init__.py              # +1 import line, +2 __all__ entries
  - backend/tests/unit/test_tool_redaction.py               # NEW (466 lines, 23 tests)
  - backend/tests/unit/test_tool_service_signature.py       # NEW (125 lines, 8 tests)
  - backend/tests/unit/test_redaction_barrel_walker.py      # NEW (72 lines, 8 tests)
tech-stack:
  added:
    - "no new dependencies — pure stdlib (re, typing)"
  patterns:
    - "TYPE_CHECKING-gated import for circular-import-prone type-only references (D-86 plumbing in tool_service.py + the same pattern landed inside tool_redaction.py during Task 3 to break a barrel-induced cycle)"
    - "Two-phase walk: collect leaves into flat list with marker-tuple shadow tree -> ONE batched redact_text_batch call -> re-zip via shape-detected marker tuples"
    - "Pass-1 longest-surrogate-first registry transform (mirrors redaction_service.py:865-885) for the de-anon direction"
key-files:
  created:
    - backend/app/services/redaction/tool_redaction.py
    - backend/tests/unit/test_tool_redaction.py
    - backend/tests/unit/test_tool_service_signature.py
    - backend/tests/unit/test_redaction_barrel_walker.py
  modified:
    - backend/app/services/tool_service.py
    - backend/app/services/redaction/__init__.py
decisions:
  - "D-86 plumbing: ToolService.execute_tool gains keyword-only registry param with default None; positional callers unaffected"
  - "D-91 walker centralization: tool_service.py stays redaction-unaware; the walker is the single integration point in chat.py"
  - "D-92 batch-once: anon walker collects all transformable leaves and runs ONE redact_text_batch call, holding the per-thread asyncio.Lock for the full batch (single contention window)"
  - "B4 invariant honored: NO logger calls in the walker module — @traced spans are the only observability surface"
  - "TYPE_CHECKING in tool_redaction.py: RedactionService import gated under TYPE_CHECKING to prevent the circular import that emerges once the barrel re-exports the walker module (Rule 1 deviation discovered during Task 3 — see Deviations)"
metrics:
  duration: ~9 minutes (single uninterrupted execution; no checkpoints)
  completed: 2026-04-27 21:56 GMT+7
  tests_added: 39
  tests_total: 133 / 133 unit tests green
  lines_added: 948 (285 walker + 663 test code)
---

# Phase 05 Plan 02: Tool I/O Symmetry Walker + ToolService.execute_tool Plumbing Summary

D-91 centralized walker (`deanonymize_tool_args` + `anonymize_tool_output`) plus D-86 `ToolService.execute_tool(*, registry=None)` plumbing — shipped as three additive commits with TDD RED/GREEN per task. Plan 05-04 (chat.py `_run_tool_loop`) is now unblocked: it can wrap every `tool_service.execute_tool(...)` call with `deanonymize_tool_args` BEFORE and `anonymize_tool_output` AFTER, with zero per-tool wiring.

## Tasks Completed

| Task | Name                                              | Commit (test)  | Commit (impl)  |
|------|---------------------------------------------------|----------------|----------------|
| 1    | Create `tool_redaction.py` walker module          | `3963e19`      | `1bf794a`      |
| 2    | Add `*, registry` kwarg to `execute_tool`         | `4a3cd37`      | `cdd3470`      |
| 3    | Re-export walkers from `redaction/__init__.py`    | `7c3a1d5`      | `d560a63`      |

All 6 commits land on the worktree branch base `f852d15` (Wave 1 merged).

## What Shipped

### Task 1 — `tool_redaction.py` (285 lines)

Two public async entry points:

- `deanonymize_tool_args(args, registry, redaction_service) -> dict[str, Any]`
  - Recursive walk over dict/list/tuple; leaf-string transform via Pass-1 longest-surrogate-first registry lookup.
  - Pure (no NER, no DB, no LLM call) — synchronous body wrapped in async signature for `@traced` symmetry.
- `anonymize_tool_output(output, registry, redaction_service) -> Any`
  - Two-phase walk:
    1. **Collect** transformable leaves into flat `list[str]`, building a SHADOW tree with marker tuples `("__PII_LEAF__", idx)`.
    2. **Batch** via `await redaction_service.redact_text_batch(leaves, registry)` — ONE call (D-92 single-lock-acquisition primitive shipped in Plan 05-01).
    3. **Re-zip** via shape-detected marker-tuple replacement.
  - Empty-leaves fast path skips the batch call entirely.

Skip rules at every leaf-string boundary:
- `_UUID_RE.fullmatch(s)` (strict lowercase-hex anchored regex) → identity.
- `len(s) < _MIN_LEN` (3) → identity.

Hard depth limit `_MAX_DEPTH = 10` — past the limit, the node is returned identity (no raise; D-90-style soft fail).

Both public functions decorated with `@traced(name="redaction.deanonymize_tool_args" / "redaction.anonymize_tool_output")` per Phase 1 D-16 OBS convention.

**Span attributes**: NONE explicitly set inside the walker. The `@traced` decorator (`backend/app/services/tracing_service.py:129`) provides automatic latency capture via the LangSmith span; the walker emits no extra attributes (counts could be added later but were intentionally deferred — keeps walker pure, B4 invariant strict). Plan 05-04 may add `leaf_count` / `hard_redacted_total` if telemetry shows it's useful.

### Task 2 — `ToolService.execute_tool` signature plumbing (D-86)

Exact diff:

```diff
+from typing import TYPE_CHECKING
+
 import httpx
+
 from app.services.tracing_service import traced
 ...
+if TYPE_CHECKING:
+    from app.services.redaction.registry import ConversationRegistry
+
 logger = logging.getLogger(__name__)
 ...
 @traced(name="execute_tool")
 async def execute_tool(
     self,
     name: str,
     arguments: dict,
     user_id: str,
     context: dict | None = None,
+    *,
+    registry: "ConversationRegistry | None" = None,  # Phase 5 D-86 / D-91
 ) -> dict:
-    """Dispatch tool execution by name."""
+    """Dispatch tool execution by name.
+
+    Phase 5 D-86: Accepts an optional ``registry: ConversationRegistry``
+    keyword arg from the chat router for symmetry with the centralized
+    walker in ``app.services.redaction.tool_redaction`` (D-91). [...]
+    """
     # body unchanged — byte-identical dispatch switch (D-91 invariant)
```

- **Keyword-only** via `*,` marker — existing positional callers in chat.py / agent_service.py / etc. are unaffected.
- **Default `None`** preserves backward-compat.
- **TYPE_CHECKING-gated import** prevents `tool_service → redaction → ... → tool_service` runtime cycle.
- **String forward-ref** annotation `"ConversationRegistry | None"` works at runtime under PEP 563 / `from __future__ import annotations` (which this file does NOT use, hence the explicit string quoting).
- **Dispatch switch unchanged** — none of the 8 `_execute_*` helpers receive `registry`. The walker is the single integration point.
- **`@traced(name="execute_tool")` decorator name unchanged** (OBS audit continuity).

### Task 3 — Barrel re-export

Exact diff for `backend/app/services/redaction/__init__.py`:

```diff
 from app.services.redaction.errors import RedactionError
 from app.services.redaction.registry import ConversationRegistry, EntityMapping
+from app.services.redaction.tool_redaction import (  # Phase 5 D-91
+    anonymize_tool_output,
+    deanonymize_tool_args,
+)

 __all__ = [
-    "RedactionError",
     "ConversationRegistry",
     "EntityMapping",
+    "RedactionError",
+    "anonymize_tool_output",  # Phase 5 D-91
+    "deanonymize_tool_args",  # Phase 5 D-91
 ]
```

`__all__` reordered alphabetically and extended with the two new names. Pre-existing `RedactionError` / `ConversationRegistry` / `EntityMapping` re-exports preserved. `RedactionService` / `RedactionResult` / `get_redaction_service` are NOT re-exported (per the existing module docstring's circular-import guard).

Plan 05-04 can now write `from app.services.redaction import deanonymize_tool_args, anonymize_tool_output` directly.

## Test Status

| Suite                                  | Count   | Status |
|----------------------------------------|---------|--------|
| Pre-existing Phase 1+2+3+4 unit tests  | 94/94   | green  |
| `test_tool_redaction.py` (NEW)         | 23/23   | green  |
| `test_tool_service_signature.py` (NEW) | 8/8     | green  |
| `test_redaction_barrel_walker.py` (NEW)| 8/8     | green  |
| **Total**                              | **133/133** | **green**  |

Note: the plan referenced "135/135 Phase 1+2+3+4 baseline" — actual baseline at `f852d15` is 94 unit tests. The discrepancy is documentation drift (likely api/integration tests counted in earlier waves); 94 → 133 represents purely additive growth, with zero regressions.

`from app.main import app` succeeds; `from app.services.redaction import deanonymize_tool_args, anonymize_tool_output` succeeds.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Circular import in `tool_redaction.py` once the barrel re-exports it**

- **Found during:** Task 3 RED → GREEN transition. After committing the Task 3 barrel update, the test suite errored with `ImportError: cannot import name 'RedactionService' from partially initialized module 'app.services.redaction_service'`.
- **Root cause:** Task 1 imported `RedactionService` at module-load time as a regular type annotation. As long as `tool_redaction.py` had no callers at the package boundary, this was fine — but Task 3's barrel re-export pulls `tool_redaction` into the package's `__init__.py`, forming the cycle:
  ```
  redaction.__init__ -> tool_redaction -> redaction_service
                                      -> anonymization
                                      -> ... -> redaction.__init__ (mid-load)
  ```
  This is precisely the cycle the existing `redaction/__init__.py` docstring (lines 11-21) warned about for `RedactionService` re-exports.
- **Fix:** Moved `from app.services.redaction_service import RedactionService` under `if TYPE_CHECKING:` in `tool_redaction.py`. The walker references `RedactionService` only as a type annotation; the actual call (`redaction_service.redact_text_batch(...)`) is duck-typed via the passed-in instance. `from __future__ import annotations` (already present at the top of the module) makes the runtime annotation a string. Same pattern as Task 2's `tool_service.py` for `ConversationRegistry`.
- **Files modified:** `backend/app/services/redaction/tool_redaction.py` (single import block).
- **Commit:** Bundled with Task 3 GREEN (`d560a63`) — the fix is needed to make Task 3 work, so committing them together preserves a buildable state on every commit.

**Lessons for downstream Plan 05-04:** The chat router will import `from app.services.redaction import deanonymize_tool_args, anonymize_tool_output, RedactionService` (mixed barrel + leaf). Importing `RedactionService` from the leaf module `app.services.redaction_service` continues to work — the barrel never re-exports it. The walker functions can be safely imported from either the barrel or the leaf module `app.services.redaction.tool_redaction`.

### Authentication Gates
None — all work was offline / static.

### Architectural Changes
None — Plan was purely additive (one new file + signature extension + barrel update).

## Patterns Observed for Plan 05-04

1. **Walker invocation site (chat.py):** Plan 05-04 should call the walker BEFORE `tool_service.execute_tool(...)` and AFTER it returns. The pattern:
   ```python
   real_args = await deanonymize_tool_args(llm_args, registry, redaction_service)
   raw_result = await tool_service.execute_tool(
       name, real_args, user_id, context, registry=registry,
   )
   surrogate_result = await anonymize_tool_output(raw_result, registry, redaction_service)
   ```
   The `registry=` kwarg threading is for symmetry with future per-tool needs (sub-agents per D-95) — `tool_service.execute_tool` itself ignores the param.

2. **Off-mode short-circuit (D-84) is delegated:** When `PII_REDACTION_ENABLED=false`, the walker still walks but `redact_text_batch` returns `list(texts)` verbatim (D-84 gate at the primitive). The de-anon walker over an empty registry naturally returns identity (the registry's `entries()` is empty → no transforms applied). For absolute byte-identical Phase 0 behavior in chat.py, Plan 05-04 should ALSO short-circuit before calling the walker (skip both walker calls entirely when `not settings.pii_redaction_enabled`) — this avoids the (small) recursion overhead and the registry-empty Pass-1 sort. The walker correctness is preserved either way; Plan 05-04 just gets a perf/clarity win.

3. **Marker-tuple shape `("__PII_LEAF__", idx)`:** Could collide if a tool returns a literal 2-tuple whose first element is the string `"__PII_LEAF__"` and second element is an int. The walker test `test_marker_tuple_does_not_collide_with_real_tuple` exercises this case: the literal `"__PII_LEAF__"` string is len-13, transformable, so it gets anonymized; the int is identity; the tuple type is preserved — no collision in practice. If a future tool emits this pattern intentionally and we need the literal to survive, switch the marker to a private class (`_LeafMarker(idx=i)`); v1 chose the tuple shape because it survives `dict`/`list`/`tuple` JSON-serialization in any tool that round-trips through json.dumps.

4. **Tuple type preservation:** Tools rarely return tuples (most use dicts and lists), but the walker preserves them. If Plan 05-04 sees tool outputs as `dict | list[str]` via type hints, the tuple branch is dead code in production — kept for spec compliance and future tools.

5. **Phase 4 fuzzy de-anon path is NOT used in tool args:** The de-anon walker uses Pass-1 only (longest-surrogate-first registry exact-match), NOT the 3-pass fuzzy + LLM resolution shipped in Plan 04-03. Tool args from the LLM should be exact surrogate strings (the LLM saw the surrogates verbatim in the chat history and is just echoing them back). If LLM hallucination corrupts surrogates, the registry lookup will silently return identity for the corrupted leaf; D-94's pre-flight egress filter at the next LLM call site is the runtime backstop.

## Threat Flags

None — the plan introduced no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The walker is in-process pure recursion + one call to an existing primitive (`redact_text_batch`); the `execute_tool` signature change is purely additive type plumbing.

## Self-Check: PASSED

- File exists: `backend/app/services/redaction/tool_redaction.py` ✓
- File exists: `backend/tests/unit/test_tool_redaction.py` ✓
- File exists: `backend/tests/unit/test_tool_service_signature.py` ✓
- File exists: `backend/tests/unit/test_redaction_barrel_walker.py` ✓
- Commit `3963e19` (Task 1 RED) in git log ✓
- Commit `1bf794a` (Task 1 GREEN) in git log ✓
- Commit `4a3cd37` (Task 2 RED) in git log ✓
- Commit `cdd3470` (Task 2 GREEN) in git log ✓
- Commit `7c3a1d5` (Task 3 RED) in git log ✓
- Commit `d560a63` (Task 3 GREEN + circular-import fix) in git log ✓
- 133/133 unit tests green ✓
- `from app.main import app` succeeds ✓
- `from app.services.redaction import deanonymize_tool_args, anonymize_tool_output` succeeds ✓
- `inspect.signature(ToolService.execute_tool).parameters['registry'].kind == KEYWORD_ONLY` ✓
- B4 invariant: zero `import logging` / `logger.` / `logging.` strings in `tool_redaction.py` ✓

## TDD Gate Compliance

Per-task RED/GREEN/REFACTOR cycle observed:

- **Task 1**: RED commit `3963e19` (test file created, `ModuleNotFoundError`); GREEN commit `1bf794a` (module added; 23/23 tests green).
- **Task 2**: RED commit `4a3cd37` (signature tests fail); GREEN commit `cdd3470` (signature added; 8/8 tests green).
- **Task 3**: RED commit `7c3a1d5` (barrel tests fail with `ImportError`); GREEN commit `d560a63` (barrel + circular-import fix; 8/8 tests green).

No REFACTOR phase needed — implementations passed verification on first GREEN attempt; the circular-import fix in Task 3 was a Rule 1 bug fix, not a refactor.
