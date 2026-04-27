---
phase: 1
plan_number: 01
title: "Tracing service migration: langsmith_service.py → tracing_service.py with @traced shim"
wave: 1
depends_on: []
requirements: [OBS-01]
files_modified:
  - backend/app/services/tracing_service.py
  - backend/app/services/langsmith_service.py
  - backend/app/main.py
  - backend/app/services/pdp_service.py
  - backend/app/services/hybrid_retrieval_service.py
  - backend/app/services/agent_service.py
  - backend/app/services/bjr_service.py
  - backend/app/services/openrouter_service.py
  - backend/app/services/graph_service.py
  - backend/app/services/vision_service.py
  - backend/app/services/openai_service.py
  - backend/app/services/embedding_service.py
  - backend/app/services/ingestion_service.py
  - backend/app/services/metadata_service.py
  - backend/app/services/document_tool_service.py
  - backend/app/services/tool_service.py
autonomous: true
must_haves:
  - "Backend cold-start cleanly initialises a tracing provider via TRACING_PROVIDER (langsmith | langfuse | empty); empty value yields a no-op @traced decorator with zero overhead."
  - "Every existing @traceable(name=...) call site is migrated to @traced(name=...) imported from app.services.tracing_service in the SAME commit (Phase 1 SC#5 dependency)."
  - "No file under backend/app/ still imports from app.services.langsmith_service or uses bare @traceable."
---

<objective>
Replace the hard-coded LangSmith wiring (`backend/app/services/langsmith_service.py`) with a pluggable tracing layer that switches between LangSmith, Langfuse, or a no-op decorator at import time based on `TRACING_PROVIDER`. Migrate ALL 39 existing `@traceable(name=...)` call sites in `backend/app/services/` to use the new `@traced(name=...)` decorator imported from `app.services.tracing_service` in the same commit, so subsequent Phase 1 plans can decorate the new redaction service consistently.

Purpose: Phase 1 Success Criterion #5 requires every redaction call to appear as a span in the configured provider. The shim is the foundation for that; provider switching also satisfies OBS-01. Doing the migration in this plan removes provider-coupling debt before any new code is written.

Output: New `tracing_service.py` (provider switch + `configure_tracing()` + `@traced` shim), deleted `langsmith_service.py`, and 14 service files updated to import from the new module.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md
@backend/app/services/langsmith_service.py
@backend/app/main.py
@backend/app/config.py

<interfaces>
<!-- Existing tracing surface (only 13 lines today): -->
```python
# backend/app/services/langsmith_service.py
import os
from app.config import get_settings

def configure_langsmith() -> None:
    settings = get_settings()
    if not settings.langsmith_api_key:
        return
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    print(f"LangSmith tracing enabled — project: {settings.langsmith_project}")
```

<!-- Existing call sites (39 total) use either form: -->
```python
from langsmith import traceable

@traceable(name="hybrid_retrieve")  # most common
@traceable                            # bare form (4 sites in embedding_service.py + 1 in ingestion_service.py)
```

<!-- Target shim signature for the @traced decorator: -->
```python
# backend/app/services/tracing_service.py
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec("P")
R = TypeVar("R")

def configure_tracing() -> None: ...

def traced(name: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]: ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Create tracing_service.py with provider switch and @traced shim; delete langsmith_service.py</name>
  <files>backend/app/services/tracing_service.py, backend/app/services/langsmith_service.py</files>
  <read_first>
    - backend/app/services/langsmith_service.py (current 13-line implementation — preserve env-var setup behaviour for langsmith mode)
    - backend/app/config.py (existing Settings class — note langsmith_api_key, langsmith_project fields are already present)
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-16, D-17 — provider switch contract)
    - backend/app/main.py (lifespan calls configure_langsmith() at line 12 — the new module must expose configure_tracing() with the same call-site contract)
  </read_first>
  <behavior>
    - When TRACING_PROVIDER="" (or unset), @traced(name=...) returns a no-op decorator: applying it to a function returns the function unchanged with zero added overhead.
    - When TRACING_PROVIDER="langsmith", configure_tracing() sets the same three env vars langsmith_service.py sets today (LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT, LANGSMITH_API_KEY) and @traced(name=X) wraps langsmith.traceable(name=X).
    - When TRACING_PROVIDER="langfuse", configure_tracing() initialises the langfuse client and @traced(name=X) wraps langfuse.observe(name=X). langfuse is a hard dependency per Plan 03; the import is unconditional inside the langfuse branch. A single defensive `try/except ImportError` around the import emits a CLEAR error message (`raise RuntimeError("TRACING_PROVIDER=langfuse but langfuse package not installed; check requirements.txt")`) so misconfigured deploys fail fast rather than silently downgrading.
    - When TRACING_PROVIDER is any other value, log a WARNING and behave as empty (no-op).
    - @traced supports both @traced(name="foo") and bare @traced (no parens) usage — the 4 sites in embedding_service.py and 1 in ingestion_service.py use the bare form.
  </behavior>
  <action>
Create `backend/app/services/tracing_service.py` containing:

1. Module docstring explaining the provider switch.
2. `import logging` and `logger = logging.getLogger(__name__)` per project convention (CONVENTIONS.md §Logging).
3. `from app.config import get_settings` and read `settings.tracing_provider` (added in Plan 02; if not yet present, fall back to `os.getenv("TRACING_PROVIDER", "").strip().lower()`).
4. Module-level constant `_PROVIDER = (settings.tracing_provider or os.getenv("TRACING_PROVIDER", "")).strip().lower()` — resolved once at import time per D-16.
5. Provider-specific bootstrapping:
   - `langsmith` branch: imports `langsmith.traceable`; `configure_tracing()` preserves the exact 3 env-var assignments from the current `configure_langsmith()` (LANGCHAIN_TRACING_V2 = "true", LANGCHAIN_PROJECT = settings.langsmith_project, LANGSMITH_API_KEY = settings.langsmith_api_key); guard with `if not settings.langsmith_api_key: return` to match current behaviour.
   - `langfuse` branch: import `from langfuse import observe` UNCONDITIONALLY inside the branch (langfuse is a hard dependency per Plan 03 / D-17). Wrap the import in a single defensive `try/except ImportError` that re-raises with a CLEAR message: `raise RuntimeError("TRACING_PROVIDER=langfuse but langfuse package not installed; check requirements.txt") from exc`. `configure_tracing()` is a no-op (langfuse SDK auto-reads `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` env vars).
   - empty / `""` / `"none"`: `configure_tracing()` is a no-op; logs `INFO "Tracing disabled (TRACING_PROVIDER empty)"`.
   - any other string: `logger.warning("Unknown TRACING_PROVIDER=%s — disabling tracing", _PROVIDER)` and behave as empty.
6. Implement `traced` as a decorator that supports BOTH `@traced` (bare, no parens) and `@traced(name="x")` (with parens). Use the standard pattern:
```python
def traced(arg=None, *, name: str | None = None):
    # Called as @traced (bare) — arg is the function
    if callable(arg) and name is None:
        return _wrap(arg, name=arg.__name__)
    # Called as @traced(name=...) or @traced() — return a decorator
    resolved_name = name if name is not None else (arg if isinstance(arg, str) else None)
    def decorator(fn):
        return _wrap(fn, name=resolved_name or fn.__name__)
    return decorator
```
   `_wrap(fn, name)` dispatches on `_PROVIDER`:
   - `langsmith`: `from langsmith import traceable; return traceable(name=name)(fn)`
   - `langfuse`: `return observe(name=name)(fn)` (the `observe` symbol was imported at module load inside the langfuse branch above; if the import fell through to the RuntimeError, the process never reached `_wrap`).
   - default: return `fn` unchanged.
7. Public exports: `configure_tracing`, `traced`. Module-level `__all__ = ["configure_tracing", "traced"]`.
8. Delete `backend/app/services/langsmith_service.py` entirely (`git rm` semantics — no shim file left behind; per D-17 this is a hard rename).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.services.tracing_service import configure_tracing, traced; print(traced); print(configure_tracing)"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/app/services/tracing_service.py` exists.
    - `grep -n "def configure_tracing" backend/app/services/tracing_service.py` returns at least one match.
    - `grep -n "def traced" backend/app/services/tracing_service.py` returns at least one match.
    - `grep -n "__all__" backend/app/services/tracing_service.py` shows `__all__ = ["configure_tracing", "traced"]` (or equivalent ordering).
    - File `backend/app/services/langsmith_service.py` does NOT exist (`test ! -f backend/app/services/langsmith_service.py` exits 0).
    - `cd backend && source venv/bin/activate && python -c "from app.services.tracing_service import traced; f = traced(name='t')(lambda: 42); print(f())"` prints `42` (no-op path works; single-line lambda form).
    - Running `cd backend && python -c "from app.main import app; print('OK')"` exits 0 (the rest of the migration in Task 2 may be needed for this; if main.py still imports langsmith_service, this acceptance is verified at end of Task 2 instead).
  </acceptance_criteria>
  <done>tracing_service.py exports configure_tracing + traced; supports bare and named forms; provider switch resolved at import time; old langsmith_service.py deleted from disk.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Migrate all @traceable call sites and configure_langsmith import to use tracing_service</name>
  <files>backend/app/main.py, backend/app/services/pdp_service.py, backend/app/services/hybrid_retrieval_service.py, backend/app/services/agent_service.py, backend/app/services/bjr_service.py, backend/app/services/openrouter_service.py, backend/app/services/graph_service.py, backend/app/services/vision_service.py, backend/app/services/openai_service.py, backend/app/services/embedding_service.py, backend/app/services/ingestion_service.py, backend/app/services/metadata_service.py, backend/app/services/document_tool_service.py, backend/app/services/tool_service.py</files>
  <read_first>
    - backend/app/main.py (line 6: `from app.services.langsmith_service import configure_langsmith` and line 12 call site)
    - backend/app/services/tracing_service.py (created in Task 1 — this is what every site now imports from)
    - backend/app/services/hybrid_retrieval_service.py (read once and replace all sites in one Edit pass)
    - backend/app/services/tool_service.py (densest cluster; read once and replace all sites in one Edit pass)
    - backend/app/services/embedding_service.py (uses BARE `@traceable` form, NOT `@traceable(name=...)`)
    - backend/app/services/ingestion_service.py (also uses bare `@traceable`)
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-17 — "Existing @traceable(name=...) call sites across the codebase migrate to the new @traced import in the same Phase 1 commit")
  </read_first>
  <action>
For each of the 14 files in `files_modified` (excluding `tracing_service.py` and `langsmith_service.py` which are handled in Task 1):

1. Replace any line matching `from langsmith import traceable` with `from app.services.tracing_service import traced`.
2. Replace any line matching `from app.services.langsmith_service import configure_langsmith` with `from app.services.tracing_service import configure_tracing`.
3. Replace every occurrence of `@traceable(name="X")` with `@traced(name="X")` (preserving the X string verbatim).
4. Replace every occurrence of bare `@traceable` (no parens) with bare `@traced` — applies to the 5 sites in `embedding_service.py` (4) and `ingestion_service.py` (1).
5. In `backend/app/main.py` specifically:
   - The langsmith_service import line: `from app.services.langsmith_service import configure_langsmith` → `from app.services.tracing_service import configure_tracing`
   - The `configure_langsmith()` call inside `lifespan`: change to `configure_tracing()`
6. Approximate site inventory at planning time was 39 sites across 13 service files (densest clusters in `tool_service.py` and `hybrid_retrieval_service.py`; bare-form sites in `embedding_service.py` and `ingestion_service.py`). The grep at execution time is authoritative — replace EVERY remaining `@traceable` regardless of count drift.

7. Do NOT modify any decorator argument other than the symbol name itself. The `name="..."` strings are unchanged so existing dashboards keep grouping spans by the same names.

8. After all edits, the PostToolUse hook will auto-run import-check on each `.py` edit — if the hook fails on any file, fix the import in that specific file before continuing.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')" && grep -rn "from app.services.langsmith_service\|from langsmith import traceable\|@traceable" backend/app/ ; test $? -eq 1</automated>
  </verify>
  <acceptance_criteria>
    - `grep -rn "from app.services.langsmith_service" backend/app/` exits with status 1 (no matches).
    - `grep -rn "from langsmith import traceable" backend/app/` exits with status 1 (no matches).
    - `grep -rn "@traceable" backend/app/` exits with status 1 (no matches — every occurrence migrated to @traced).
    - `grep -rn "@traced" backend/app/` returns at least 35 matches (one per migrated site; planning-time inventory was 39 — execution-time grep is authoritative).
    - `grep -n "configure_langsmith" backend/app/main.py` exits with status 1 (no matches).
    - `grep -n "configure_tracing" backend/app/main.py` returns at least 1 match (the import) and at least 1 match (the call inside lifespan).
    - `grep -n "from app.services.tracing_service" backend/app/services/embedding_service.py` returns 1 match.
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` exits 0.
    - `cd backend && source venv/bin/activate && TRACING_PROVIDER="" python -c "from app.services.tracing_service import traced; f = traced(name='t')(lambda: 1); print(f())"` prints `1` (no-op path returns wrapped fn that still works).
  </acceptance_criteria>
  <done>All 39 @traceable sites migrated to @traced; main.py uses configure_tracing; backend imports cleanly; grep verifies zero residual langsmith_service or @traceable references.</done>
</task>

</tasks>

<verification>
After both tasks complete, run:
```bash
cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"
grep -rn "from app.services.langsmith_service\|from langsmith import traceable\|@traceable" backend/app/  # must exit 1 (no matches)
grep -rn "@traced" backend/app/ | wc -l  # must report >= 35 (planning-time inventory was 39)
test ! -f backend/app/services/langsmith_service.py  # file deleted
```
</verification>

<success_criteria>
1. `tracing_service.py` exists with `configure_tracing` + `traced` shim; `langsmith_service.py` deleted.
2. `TRACING_PROVIDER` switches between langsmith / langfuse / no-op at import time without crashing the backend.
3. All 39 existing `@traceable` sites migrated to `@traced`; zero residual references in `backend/app/`.
4. Backend boots cleanly: `python -c "from app.main import app; print('OK')"` exits 0.
5. Phase 1 Success Criterion #5 ("every redaction call appears as a span in the configured tracing provider") becomes achievable — Plan 06's `RedactionService` will decorate its methods with `@traced(name="redaction.X")` from the new module.
</success_criteria>

<output>
After completion, create `.planning/phases/01-detection-anonymization-foundation/01-01-SUMMARY.md` capturing:
- Final shape of the `@traced` decorator (signature, both bare and named-form support)
- The 14 files migrated and total site count (planning-time inventory: 39 sites)
- Any deviations from the planned site list (e.g., if grep at execution time finds new @traceable usages introduced after planning)
- Confirmation that `TRACING_PROVIDER=""` boot path is exercised
</output>
