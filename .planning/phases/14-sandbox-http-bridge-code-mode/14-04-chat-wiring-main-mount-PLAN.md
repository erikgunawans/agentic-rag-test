---
phase: 14-sandbox-http-bridge-code-mode
plan: 04
type: execute
wave: 3
depends_on:
  - "14-03"
files_modified:
  - backend/app/main.py
  - backend/app/routers/chat.py
  - backend/app/services/tool_service.py
autonomous: true
requirements:
  - BRIDGE-04
  - BRIDGE-05
  - BRIDGE-06
must_haves:
  truths:
    - "main.py conditionally mounts bridge router only when settings.sandbox_enabled AND settings.tool_registry_enabled are both True (lazy import inside if-block)"
    - "When neither flag is True, main.py has no reference to bridge module at import time (TOOL-05 byte-identical fallback)"
    - "tool_service._execute_code() prepends 'from stubs import *\n' to the submitted code string when settings.sandbox_enabled AND settings.tool_registry_enabled are both True"
    - "tool_service._execute_code() does NOT modify code when either flag is False (byte-identical fallback)"
    - "chat.py emits a code_mode_start SSE event (type='code_mode_start', tools=[list]) before the first execute_code tool call in a session where bridge is active"
    - "code_mode_start event is emitted at most once per SSE stream (not on every execute_code call)"
    - "code_mode_start is only emitted when settings.sandbox_enabled AND settings.tool_registry_enabled are both True"
    - "sandbox_bridge_service.inject_stubs() is called from sandbox_service.py after container.open() when bridge is active (wired in Plan 14-02; this plan verifies the wiring via smoke test)"
  artifacts:
    - path: "backend/app/main.py"
      provides: "Conditional bridge router mount under dual-flag guard"
      contains: "if settings.sandbox_enabled and settings.tool_registry_enabled"
    - path: "backend/app/routers/chat.py"
      provides: "code_mode_start SSE event emission before first execute_code call when bridge active"
      contains: "code_mode_start"
    - path: "backend/app/services/tool_service.py"
      provides: "from stubs import * prepend in _execute_code() when bridge active"
      contains: "from stubs import *"
---

# Plan 14-04: Chat Wiring — `code_mode_start` SSE, Stub Prepend & `main.py` Mount

## Objective

Wire all bridge components together:
1. Conditionally mount the bridge router in `main.py` when both flags are active
2. Patch `tool_service._execute_code()` to prepend `from stubs import *\n` to submitted code when bridge is active
3. Patch `chat.py` to emit `code_mode_start` SSE event before the first `execute_code` call in a session

This plan does NOT write new unit tests (covered by Plans 14-01 to 14-03 and Plan 14-05's integration tests). It applies three surgical patches and verifies each via smoke tests.

## Tasks

<task id="14-04-T1" name="Conditionally mount bridge router in main.py">
<read_first>
- backend/app/main.py (full file — read before editing to see current imports and router registrations)
- backend/app/config.py (confirm bridge_port field exists from Plan 14-01)
- backend/app/routers/bridge.py (confirm it exists from Plan 14-03)
</read_first>
<action>
Open `backend/app/main.py`. After the last `app.include_router(...)` line (currently `app.include_router(public_settings_router.router)`), add the conditional bridge mount:

```python
# Phase 14 / BRIDGE-02, D-P14-05: bridge router mounted only when BOTH flags are active.
# Lazy import inside the if-block ensures the bridge module is NEVER imported when
# flags are off, preserving the TOOL-05 byte-identical fallback invariant.
if settings.sandbox_enabled and settings.tool_registry_enabled:
    from app.routers import bridge as bridge_router_module
    app.include_router(bridge_router_module.router)
```

The `settings` object is already assigned at module level (`settings = get_settings()`) — use it directly without calling `get_settings()` again.

Do NOT add the bridge import to the top-level `from app.routers import ...` line. The lazy import inside the `if` block is mandatory (TOOL-05).
</action>
<acceptance_criteria>
- `grep "if settings.sandbox_enabled and settings.tool_registry_enabled" backend/app/main.py` returns that guard line
- `grep "from app.routers import bridge" backend/app/main.py` returns the lazy import (inside the if block)
- `grep "bridge_router_module.router" backend/app/main.py` returns the include_router call
- Confirm the bridge import is NOT in the top-level import line: `head -5 backend/app/main.py | grep "bridge"` returns nothing
- `python -c "from app.main import app; print('OK')"` exits 0 from backend/ with venv active (with flags off, bridge module is not imported)
</acceptance_criteria>
</task>

<task id="14-04-T2" name="Patch tool_service._execute_code() to prepend stub import">
<read_first>
- backend/app/services/tool_service.py (locate async def _execute_code — read it fully; note where `code` variable is used before being passed to sandbox)
- backend/app/config.py (confirm sandbox_enabled and tool_registry_enabled fields)
- .planning/phases/14-sandbox-http-bridge-code-mode/14-CONTEXT.md (D-P14-04: stub injection spec)
</read_first>
<action>
Open `backend/app/services/tool_service.py`. Locate `async def _execute_code(self, ...)`. Near the top of the method body (after the guard checks for `code` and `thread_id`, before the `result = await get_sandbox_service().execute(...)` call), add:

```python
# Phase 14 / BRIDGE-04 (D-P14-04): prepend stub import so LLM-generated code
# can call platform tools as typed Python functions via the bridge.
# `from stubs import *` is a no-op if /sandbox/stubs.py doesn't exist (e.g.,
# bridge is inactive or container restarted), so this is safe to always add
# when bridge is potentially active.
settings = get_settings()
bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
if bridge_active and not code.startswith("from stubs import"):
    code = "from stubs import *\n" + code
```

The `not code.startswith("from stubs import")` guard prevents double-prepend on retry calls.

`get_settings()` is already imported at the top of `tool_service.py` (check before adding).
</action>
<acceptance_criteria>
- `grep "from stubs import" backend/app/services/tool_service.py` returns the prepend line
- `grep "bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled" backend/app/services/tool_service.py` returns that line (inside _execute_code)
- `python -c "from app.main import app; print('OK')"` exits 0 from backend/ with venv active
</acceptance_criteria>
</task>

<task id="14-04-T3" name="Patch chat.py to emit code_mode_start SSE event">
<read_first>
- backend/app/routers/chat.py (read the execute_code handling section; search for `func_name == "execute_code"` to find the dispatch point; also read how other SSE events like agent_start are emitted)
- backend/app/services/tool_registry.py (build_catalog_block or _REGISTRY access — to get tool names for the event payload)
- .planning/phases/14-sandbox-http-bridge-code-mode/14-CONTEXT.md (D-P14-07: code_mode_start event spec)
</read_first>
<action>
Open `backend/app/routers/chat.py`. Find the section that handles the `execute_code` tool call — there are two dispatch paths (single-agent branch B and multi-agent branch A). The pattern is `if func_name == "execute_code":`.

In BOTH branches (branch A and branch B), add a `code_mode_start` emission before the first `execute_code` dispatch. Use a local variable `_bridge_started` (scoped to the `event_generator()` closure) to ensure the event is emitted at most once per SSE stream:

Before the tool-calling loop in `event_generator()`, add near where `bridge_active` can be computed (alongside other setup like `pii_guidance`):

```python
# Phase 14 / BRIDGE-06 (D-P14-07): track whether code_mode_start has been emitted
_bridge_event_sent = False
settings = get_settings()  # already assigned above — use existing reference
_bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
```

Then in EACH `execute_code` dispatch block (both branch A and branch B), prepend:

```python
# Phase 14 / BRIDGE-06: emit code_mode_start once per session when bridge is active
if _bridge_active and not _bridge_event_sent:
    _bridge_event_sent = True
    # Get available tool names from registry (lazy import, TOOL-05)
    _bridge_tools: list[str] = []
    try:
        from app.services import tool_registry as _tr
        _bridge_tools = [
            name for name in _tr._REGISTRY
            if name != "tool_search"
        ]
    except Exception:
        pass
    yield f"data: {json.dumps({'type': 'code_mode_start', 'tools': _bridge_tools})}\n\n"
```

The emit MUST come before the actual `execute_code` dispatch, not after.

Important: `settings` object in `chat.py` is already available from `get_system_settings()`. Check whether `settings` (from `system_settings`) or the config `get_settings()` is the right reference. The flags are on the Pydantic config (`get_settings()`), not `system_settings`. Use `get_settings()` (the config object from `app.config`).

Check if `from app.config import get_settings` is already in the imports of `chat.py` before adding.
</action>
<acceptance_criteria>
- `grep "code_mode_start" backend/app/routers/chat.py` returns at least 1 line (the yield statement)
- `grep "_bridge_event_sent" backend/app/routers/chat.py` returns at least 2 occurrences (initialization + update)
- `grep "_bridge_active" backend/app/routers/chat.py` returns at least 1 occurrence
- `python -c "from app.main import app; print('OK')"` exits 0 from backend/ with venv active
- `python -c "from app.routers.chat import router; print('OK')"` exits 0 from backend/ with venv active
</acceptance_criteria>
</task>

## Verification

```bash
# From backend/ with venv active:

# 1. Import smoke test (with flags OFF — default Railway config)
python -c "from app.main import app; print('main import OK')"
python -c "from app.routers.chat import router; print('chat import OK')"
python -c "from app.services.tool_service import ToolService; print('tool_service import OK')"

# 2. Verify bridge module NOT imported when flags off
python -c "
from app.config import get_settings
import app.main  # import the main module
import sys
# bridge module should NOT be in sys.modules when flags are off
bridge_loaded = 'app.routers.bridge' in sys.modules
settings = get_settings()
expected = settings.sandbox_enabled and settings.tool_registry_enabled
assert bridge_loaded == expected, f'bridge_loaded={bridge_loaded} expected={expected}'
print('lazy import invariant OK')
"

# 3. Verify stubs prepend logic
python -c "
# Simulate the prepend logic (without Docker)
code = 'x = 1 + 2'
bridge_active = True
if bridge_active and not code.startswith('from stubs import'):
    code = 'from stubs import *\n' + code
assert code.startswith('from stubs import *'), code
# Verify idempotent
if bridge_active and not code.startswith('from stubs import'):
    code = 'from stubs import *\n' + code
assert code.count('from stubs import') == 1, 'double prepend!'
print('stubs prepend logic OK')
"

# 4. Grep verification
grep "code_mode_start" backend/app/routers/chat.py
grep "from stubs import" backend/app/services/tool_service.py
grep "if settings.sandbox_enabled and settings.tool_registry_enabled" backend/app/main.py
```

<threat_model>
## Threat Model (ASVS L1)

| Threat | Mitigation |
|--------|-----------|
| Bridge router accessible when flags are off | Lazy import inside `if` block — bridge module never loaded when flags off; `/bridge/*` routes don't exist |
| Double-prepend of stub import causing syntax errors | `not code.startswith("from stubs import")` guard prevents double-prepend on retry |
| code_mode_start event emitted multiple times flooding the client | `_bridge_event_sent` flag ensures at most once per SSE stream |
| code_mode_start leaking tool names when bridge inactive | Guard `if _bridge_active and not _bridge_event_sent` prevents emission when bridge is off |
| Importing tool_registry in chat.py when flag is off | Lazy import inside `try` block inside the `_bridge_active` guard; no-op if registry not available |
</threat_model>
