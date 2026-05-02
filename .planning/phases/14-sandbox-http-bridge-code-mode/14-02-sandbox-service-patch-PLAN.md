---
phase: 14-sandbox-http-bridge-code-mode
plan: 02
type: execute
wave: 2
depends_on:
  - "14-01"
files_modified:
  - backend/app/services/sandbox_service.py
  - backend/tests/unit/test_sandbox_service_bridge.py
autonomous: true
requirements:
  - BRIDGE-05
  - BRIDGE-07
must_haves:
  truths:
    - "SandboxSession dataclass has bridge_token: str | None = None field"
    - "_check_dangerous_imports(code) is a module-level function that returns the matched pattern string or None; it is called at the top of SandboxService.execute() before any container.run()"
    - "_check_dangerous_imports catches: subprocess module, socket module, __import__ with dangerous names; does NOT flag urllib.request or urllib.parse"
    - "When _check_dangerous_imports returns a non-None match, execute() returns {'error': 'security_violation', 'pattern': ..., 'message': 'Dangerous import blocked.'} without running any code"
    - "_create_container() injects BRIDGE_URL and BRIDGE_TOKEN env vars into the container environment when settings.sandbox_enabled AND settings.tool_registry_enabled are both True"
    - "_create_container() does NOT inject any env vars (bridge_active is False) when either flag is False"
    - "_cleanup_loop() calls sandbox_bridge_service.revoke_token(thread_id) after evicting each session"
    - "test_sandbox_service_bridge.py covers: dangerous import detection for each pattern, urllib.request not flagged, env injection when both flags true, no env injection when flags false, revoke_token called on cleanup"
  artifacts:
    - path: "backend/app/services/sandbox_service.py"
      provides: "_check_dangerous_imports(), SandboxSession.bridge_token field, bridge env injection in _create_container(), revoke_token call in _cleanup_loop()"
      contains: "_check_dangerous_imports"
    - path: "backend/tests/unit/test_sandbox_service_bridge.py"
      provides: "Unit tests for dangerous import scanning and bridge env injection logic"
      contains: "def test_dangerous_import_subprocess"
---

# Plan 14-02: Sandbox Service Patch — Dangerous Import Scan, Bridge Token & Env Injection

## Objective

Patch `sandbox_service.py` to:
1. Add `bridge_token: str | None = None` to the `SandboxSession` dataclass
2. Add `_check_dangerous_imports(code)` — module-level regex function called before every `container.run()`
3. In `_create_container()`: inject `BRIDGE_URL` and `BRIDGE_TOKEN` into the container environment when both flags are active
4. In `_cleanup_loop()`: call `sandbox_bridge_service.revoke_token(thread_id)` when evicting sessions

This plan must NOT break the existing sandbox behavior when `SANDBOX_ENABLED=true` but `TOOL_REGISTRY_ENABLED=false` — the byte-identical fallback invariant (D-P14-05, TOOL-05).

## Tasks

<task id="14-02-T1" name="Add bridge_token field to SandboxSession dataclass">
<read_first>
- backend/app/services/sandbox_service.py (full file — read before any edit; locate SandboxSession @dataclass definition)
</read_first>
<action>
Open `backend/app/services/sandbox_service.py`. Locate the `SandboxSession` dataclass. It currently reads:

```python
@dataclass
class SandboxSession:
    """Per-thread sandbox state. `container` is the opaque llm-sandbox handle."""

    container: object       # llm-sandbox BaseSession instance (opened)
    last_used: datetime
    thread_id: str
```

Add `bridge_token: str | None = None` as the last field:

```python
@dataclass
class SandboxSession:
    """Per-thread sandbox state. `container` is the opaque llm-sandbox handle."""

    container: object       # llm-sandbox BaseSession instance (opened)
    last_used: datetime
    thread_id: str
    bridge_token: str | None = None  # Phase 14 D-P14-03: ephemeral bridge token UUID
```

The `= None` default means existing code constructing `SandboxSession(container=..., last_used=..., thread_id=...)` continues to work without change (backward compatible).
</action>
<acceptance_criteria>
- `grep "bridge_token: str | None = None" backend/app/services/sandbox_service.py` returns that line
- `python -c "from app.services.sandbox_service import SandboxSession; from datetime import datetime; s = SandboxSession(container=object(), last_used=datetime.utcnow(), thread_id='t1'); assert s.bridge_token is None; print('OK')"` exits 0 from backend/ with venv active
</acceptance_criteria>
</task>

<task id="14-02-T2" name="Add _check_dangerous_imports() module-level function">
<read_first>
- backend/app/services/sandbox_service.py (read current imports and module-level constants — add after existing module-level constants)
- backend/app/services/tool_service.py (lines around _WRITE_KEYWORDS — model for compiled regex pattern)
- .planning/phases/14-sandbox-http-bridge-code-mode/14-CONTEXT.md (D-P14-06: dangerous import scan spec)
</read_first>
<action>
In `backend/app/services/sandbox_service.py`, after the existing module-level constants block (after `_OUTPUT_DIR = "/sandbox/output"`), add:

```python
# ── Security: dangerous import scanner (Phase 14 / BRIDGE-07, D-P14-06) ─────
# PRD §Security: "existing security policy blocks dangerous imports".
# This scanner is called at the top of execute() before container.run().
# Pattern covers: subprocess, raw sockets, __import__ with dangerous names.
# Does NOT flag urllib.request or urllib.parse (used by bridge ToolClient).
_DANGEROUS_IMPORT_PATTERNS = re.compile(
    r"import\s+subprocess"
    r"|from\s+subprocess\s+import"
    r"|import\s+socket"
    r"|from\s+socket\s+import"
    r"|__import__\s*\(\s*['\"]subprocess"
    r"|__import__\s*\(\s*['\"]socket",
    re.IGNORECASE,
)


def _check_dangerous_imports(code: str) -> str | None:
    """Scan submitted code for dangerous import patterns.

    Returns the matched pattern string if found, else None.
    Called at the top of SandboxService.execute() before container.run().

    Safe: urllib.request, urllib.parse (used by bridge ToolClient stubs).
    Blocked: subprocess, socket, __import__ with those names.
    """
    m = _DANGEROUS_IMPORT_PATTERNS.search(code)
    return m.group(0) if m else None
```

Also ensure `import re` is present at the top of the file (it should already be there since it's used by `_WRITE_KEYWORDS` pattern — verify before adding).
</action>
<acceptance_criteria>
- `grep "_DANGEROUS_IMPORT_PATTERNS" backend/app/services/sandbox_service.py` returns the compiled regex line
- `grep "def _check_dangerous_imports" backend/app/services/sandbox_service.py` returns the function definition
- `python -c "from app.services.sandbox_service import _check_dangerous_imports; assert _check_dangerous_imports('import subprocess') is not None; assert _check_dangerous_imports('import socket') is not None; assert _check_dangerous_imports('import urllib.request') is None; assert _check_dangerous_imports('from urllib.request import urlopen') is None; print('OK')"` exits 0 from backend/ with venv active
</acceptance_criteria>
</task>

<task id="14-02-T3" name="Patch execute() to check dangerous imports before running">
<read_first>
- backend/app/services/sandbox_service.py (locate async def execute() — check its current opening)
</read_first>
<action>
In `backend/app/services/sandbox_service.py`, locate the `async def execute()` method of `SandboxService`. At the very top of the method body (after the docstring, before `await self._ensure_cleanup_task()`), add the dangerous import check:

```python
async def execute(
    self,
    *,
    code: str,
    thread_id: str,
    user_id: str,
    stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
) -> dict:
    """Run `code` in the thread's sandbox container.
    ... (existing docstring)
    """
    # Phase 14 / BRIDGE-07 (D-P14-06): dangerous import scan before any execution.
    dangerous_match = _check_dangerous_imports(code)
    if dangerous_match:
        logger.warning(
            "sandbox_execute: dangerous import blocked pattern=%r thread_id=%s",
            dangerous_match,
            thread_id,
        )
        return {
            "error": "security_violation",
            "pattern": dangerous_match,
            "message": f"Dangerous import blocked: {dangerous_match!r}",
            "stdout": "",
            "stderr": f"SecurityError: import of '{dangerous_match}' is not allowed in the sandbox.",
            "exit_code": -1,
            "files": [],
        }
    # ... rest of existing execute() body (unchanged)
```

The `await self._ensure_cleanup_task()` and all subsequent lines remain untouched.
</action>
<acceptance_criteria>
- `grep "dangerous_match = _check_dangerous_imports" backend/app/services/sandbox_service.py` returns that line within the execute method
- `grep "security_violation" backend/app/services/sandbox_service.py` returns the return dict line
- `python -c "from app.main import app; print('OK')"` exits 0 from backend/ with venv active (import smoke test passes)
</acceptance_criteria>
</task>

<task id="14-02-T4" name="Patch _create_container() to inject bridge env vars">
<read_first>
- backend/app/services/sandbox_service.py (locate _create_container() — read the current SandboxSession(...) constructor call)
- backend/app/services/sandbox_bridge_service.py (create_bridge_token function — just created in Plan 14-01)
- .planning/phases/14-sandbox-http-bridge-code-mode/14-CONTEXT.md (D-P14-05: dual-flag gate pattern)
</read_first>
<action>
In `backend/app/services/sandbox_service.py`, locate `def _create_container(self) -> object:`. The method needs to accept `thread_id` and `user_id` parameters so it can create a bridge token. Change its signature from `def _create_container(self) -> object:` to `def _create_container(self, thread_id: str, user_id: str) -> tuple[object, str | None]:`.

The method returns a tuple `(container, bridge_token_or_None)`.

Add the import at the top of the file (in the app-local imports section):
```python
# Phase 14: bridge service — lazy import to honor TOOL-05 byte-identical fallback
# (imported only when bridge_active is True inside _create_container)
```

Updated `_create_container` body:

```python
def _create_container(self, thread_id: str, user_id: str) -> tuple[object, str | None]:
    """Construct and open an llm-sandbox session bound to settings.sandbox_image.

    D-P10-02: honors DOCKER_HOST env var for Railway socket mount.
    D-P10-01: Docker backend, Python language.
    Phase 14 D-P14-02/D-P14-05: injects BRIDGE_URL + BRIDGE_TOKEN into container
    environment when both SANDBOX_ENABLED and TOOL_REGISTRY_ENABLED are True.

    Returns:
        (container, bridge_token): container is the opened llm-sandbox session;
        bridge_token is the UUID string if bridge is active, else None.
    """
    settings = get_settings()
    # D-P10-02: set DOCKER_HOST so docker-py picks up the correct socket
    os.environ.setdefault("DOCKER_HOST", settings.sandbox_docker_host)

    # D-P14-05: bridge only active when BOTH flags are True
    bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
    env: dict[str, str] = {}
    bridge_token: str | None = None

    if bridge_active:
        # Lazy import (TOOL-05): only imported when flag is on
        from app.services.sandbox_bridge_service import create_bridge_token
        bridge_token = create_bridge_token(thread_id, user_id)
        bridge_url = f"http://host.docker.internal:{settings.bridge_port}"
        env = {"BRIDGE_URL": bridge_url, "BRIDGE_TOKEN": bridge_token}
        logger.debug(
            "_create_container: bridge active bridge_url=%s thread_id=%s",
            bridge_url,
            thread_id,
        )

    # llm-sandbox v0.3.39: SandboxSession is a factory alias for create_session().
    # Use `keep_template=True` so the container is kept alive after each run()
    # call, enabling variable persistence (D-P10-04 / SANDBOX-02).
    # environment= param injects env vars into the container (bridge token/URL).
    container = SandboxSession(
        backend=SandboxBackend.DOCKER,
        lang=SupportedLanguage.PYTHON,
        image=settings.sandbox_image,
        keep_template=True,    # preserve container between run() calls
        verbose=False,
        **({"environment": env} if env else {}),
    )
    # Explicitly open the session so it's ready for run() calls.
    container.open()
    return container, bridge_token
```

Update `_get_or_create_session()` to pass `thread_id` and `user_id` and store the bridge_token:

```python
async def _get_or_create_session(self, thread_id: str, user_id: str) -> SandboxSession:
    """D-P10-04: one container per thread, lazy-create on first call."""
    async with self._lock:
        sess = self._sessions.get(thread_id)
        if sess is not None:
            return sess
        container, bridge_token = self._create_container(thread_id, user_id)
        sess = SandboxSession(
            container=container,
            last_used=datetime.utcnow(),
            thread_id=thread_id,
            bridge_token=bridge_token,  # Phase 14 D-P14-03
        )
        self._sessions[thread_id] = sess
        return sess
```

Update `execute()` to pass `user_id` to `_get_or_create_session()`:

```python
session = await self._get_or_create_session(thread_id=thread_id, user_id=user_id)
```

(The `execute()` method already receives `user_id` as a parameter — just pass it through.)
</action>
<acceptance_criteria>
- `grep "bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled" backend/app/services/sandbox_service.py` returns that line
- `grep "bridge_token = create_bridge_token" backend/app/services/sandbox_service.py` returns the create_bridge_token call
- `grep "BRIDGE_URL.*host.docker.internal" backend/app/services/sandbox_service.py` returns the env var assignment
- `grep "bridge_token=bridge_token" backend/app/services/sandbox_service.py` returns the SandboxSession constructor line
- `python -c "from app.main import app; print('OK')"` exits 0 from backend/ with venv active
</acceptance_criteria>
</task>

<task id="14-02-T5" name="Patch _cleanup_loop() to revoke bridge tokens on session eviction">
<read_first>
- backend/app/services/sandbox_service.py (locate _cleanup_loop() — find where sess.container.close() is called)
</read_first>
<action>
In `backend/app/services/sandbox_service.py`, locate `async def _cleanup_loop(self)`. Find the loop where stale sessions are evicted (the block that calls `sess.container.close()`). Add a `revoke_token` call after removing the session from `_sessions` but before closing the container:

```python
for tid in stale_ids:
    sess = self._sessions.pop(tid, None)
    if sess is None:
        continue
    # Phase 14 D-P14-03: revoke bridge token when session is evicted
    try:
        from app.services.sandbox_bridge_service import revoke_token
        revoke_token(tid)
    except Exception as exc:
        logger.warning("bridge revoke_token failed tid=%s err=%s", tid, exc)
    # Close the container (existing code)
    try:
        sess.container.close()
    except Exception as exc:
        logger.warning(...)
```

The lazy import (`from app.services.sandbox_bridge_service import revoke_token`) ensures this is a no-op when bridge is not active (import succeeds but `_TOKEN_STORE` is empty, so `revoke_token` is a no-op).
</action>
<acceptance_criteria>
- `grep "revoke_token(tid)" backend/app/services/sandbox_service.py` returns that call line
- `grep "from app.services.sandbox_bridge_service import revoke_token" backend/app/services/sandbox_service.py` returns the lazy import
- `python -c "from app.main import app; print('OK')"` exits 0 from backend/ with venv active
</acceptance_criteria>
</task>

<task id="14-02-T6" name="Write unit tests for sandbox service bridge patches">
<read_first>
- backend/app/services/sandbox_service.py (patched version — read to understand the new functions)
- backend/tests/unit/ (check for test pattern used in Phase 13 plans)
</read_first>
<action>
Create `backend/tests/unit/test_sandbox_service_bridge.py`:

```python
"""Unit tests for sandbox_service bridge patches — Phase 14 / BRIDGE-05, BRIDGE-07.

Tests:
  - _check_dangerous_imports: subprocess, socket blocked; urllib not blocked
  - _create_container bridge_active logic (mocked)
  - revoke_token called on cleanup (mocked)

Note: Full execute() integration tests require a live Docker daemon —
those belong in integration/E2E tests. These unit tests cover the
pure-logic branches that don't need Docker.
"""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.sandbox_service import _check_dangerous_imports


class TestDangerousImportScanner:
    """Tests for the _check_dangerous_imports module-level function."""

    # --- Blocked patterns ---
    def test_blocks_import_subprocess(self):
        assert _check_dangerous_imports("import subprocess") is not None

    def test_blocks_from_subprocess_import(self):
        assert _check_dangerous_imports("from subprocess import run") is not None

    def test_blocks_import_socket(self):
        assert _check_dangerous_imports("import socket") is not None

    def test_blocks_from_socket_import(self):
        assert _check_dangerous_imports("from socket import create_connection") is not None

    def test_blocks_dunder_import_subprocess(self):
        assert _check_dangerous_imports("__import__('subprocess')") is not None

    def test_blocks_dunder_import_socket(self):
        assert _check_dangerous_imports('__import__("socket")') is not None

    def test_blocks_case_insensitive(self):
        assert _check_dangerous_imports("IMPORT SUBPROCESS") is not None

    # --- Safe patterns (must NOT be blocked) ---
    def test_allows_urllib_request(self):
        assert _check_dangerous_imports("import urllib.request") is None

    def test_allows_urllib_parse(self):
        assert _check_dangerous_imports("import urllib.parse") is None

    def test_allows_from_urllib_request(self):
        assert _check_dangerous_imports("from urllib.request import urlopen") is None

    def test_allows_clean_code(self):
        code = "x = 1 + 2\nprint(x)"
        assert _check_dangerous_imports(code) is None

    def test_allows_math_import(self):
        assert _check_dangerous_imports("import math") is None

    def test_returns_none_on_empty_string(self):
        assert _check_dangerous_imports("") is None


class TestBridgeActiveFlag:
    """Tests for bridge_active dual-flag logic in _create_container."""

    def _make_settings(self, sandbox_enabled: bool, tool_registry_enabled: bool):
        m = MagicMock()
        m.sandbox_enabled = sandbox_enabled
        m.tool_registry_enabled = tool_registry_enabled
        m.bridge_port = 8002
        m.sandbox_image = "lexcore-sandbox:latest"
        m.sandbox_docker_host = "unix:///var/run/docker.sock"
        return m

    def test_bridge_active_when_both_flags_true(self):
        settings = self._make_settings(True, True)
        bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
        assert bridge_active is True

    def test_bridge_inactive_when_sandbox_only(self):
        settings = self._make_settings(True, False)
        bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
        assert bridge_active is False

    def test_bridge_inactive_when_registry_only(self):
        settings = self._make_settings(False, True)
        bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
        assert bridge_active is False

    def test_bridge_inactive_when_both_false(self):
        settings = self._make_settings(False, False)
        bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled
        assert bridge_active is False
```
</action>
<acceptance_criteria>
- `test -f backend/tests/unit/test_sandbox_service_bridge.py` exits 0
- `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_sandbox_service_bridge.py -v --tb=short 2>&1 | tail -5` shows all tests PASSED with exit 0
- The test class `TestDangerousImportScanner` has at least 12 test methods covering blocked and safe patterns
</acceptance_criteria>
</task>

## Verification

```bash
# From backend/ with venv active:

# 1. Import smoke test
python -c "from app.main import app; print('OK')"

# 2. _check_dangerous_imports correctness
python -c "
from app.services.sandbox_service import _check_dangerous_imports
# blocked
assert _check_dangerous_imports('import subprocess') is not None
assert _check_dangerous_imports('import socket') is not None
# safe
assert _check_dangerous_imports('import urllib.request') is None
assert _check_dangerous_imports('import math') is None
print('dangerous_import scanner OK')
"

# 3. SandboxSession bridge_token field
python -c "
from app.services.sandbox_service import SandboxSession
from datetime import datetime
s = SandboxSession(container=object(), last_used=datetime.utcnow(), thread_id='t1')
assert s.bridge_token is None
s2 = SandboxSession(container=object(), last_used=datetime.utcnow(), thread_id='t2', bridge_token='test-uuid')
assert s2.bridge_token == 'test-uuid'
print('SandboxSession.bridge_token OK')
"

# 4. Unit tests
python -m pytest tests/unit/test_sandbox_service_bridge.py -v --tb=short
```

<threat_model>
## Threat Model (ASVS L1)

| Threat | Mitigation |
|--------|-----------|
| LLM-generated code importing subprocess to escape sandbox | `_check_dangerous_imports()` blocks at the Python level before code reaches container.run() |
| Raw socket I/O from sandbox | `import socket` and `from socket import ...` blocked by scanner |
| __import__ bypass attempt | `__import__('subprocess')` and `__import__("socket")` patterns explicitly covered |
| Bridge env vars leaking to non-bridge sessions | `bridge_active` guard ensures `env={}` (no BRIDGE_TOKEN) when either flag is off |
| Token surviving session TTL eviction | `_cleanup_loop()` calls `revoke_token(thread_id)` before closing container |
| Race condition: two requests creating bridge token for same thread | `_get_or_create_session()` is already guarded by `self._lock` — token creation happens inside the lock |
</threat_model>
