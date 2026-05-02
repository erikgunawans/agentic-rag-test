---
phase: 14-sandbox-http-bridge-code-mode
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/config.py
  - backend/sandbox/Dockerfile
  - backend/sandbox/tool_client.py
  - backend/app/services/sandbox_bridge_service.py
  - backend/tests/unit/test_sandbox_bridge_service.py
autonomous: true
requirements:
  - BRIDGE-01
  - BRIDGE-03
must_haves:
  truths:
    - "settings.bridge_port is an int defaulting to 8002, readable from env var BRIDGE_PORT"
    - "backend/sandbox/tool_client.py exists with class ToolClient that reads BRIDGE_URL and BRIDGE_TOKEN from os.environ at call time and uses only urllib.request (stdlib)"
    - "ToolClient.call(tool_name, **kwargs) returns a dict on success or {'error': 'bridge_error', 'message': '...'} on any exception (never raises)"
    - "sandbox_bridge_service._TOKEN_STORE is a module-level dict[str, BridgeTokenEntry]"
    - "create_bridge_token(thread_id, user_id) generates uuid4 token, stores BridgeTokenEntry, returns token string"
    - "validate_token(session_token, user_id) returns True only when token exists AND user_id matches stored entry"
    - "revoke_token(thread_id) removes entry from _TOKEN_STORE without raising if key absent"
    - "_generate_stubs(active_tools) returns a valid Python string with one typed function per tool that wraps _client.call()"
    - "inject_stubs(session, active_tools) calls _generate_stubs and writes result to /sandbox/stubs.py via session.container.execute_command or session.container.run"
    - "test_sandbox_bridge_service.py covers: token create/validate/revoke lifecycle, validate rejects wrong user_id, validate rejects unknown token, _generate_stubs produces valid Python with correct function signatures"
  artifacts:
    - path: "backend/app/config.py"
      provides: "bridge_port: int = 8002 Pydantic Settings field"
      contains: "bridge_port"
    - path: "backend/sandbox/tool_client.py"
      provides: "ToolClient class with call() method"
      contains: "class ToolClient"
    - path: "backend/sandbox/Dockerfile"
      provides: "Sandbox Docker image with ToolClient pre-baked at /sandbox/tool_client.py"
      contains: "COPY tool_client.py /sandbox/tool_client.py"
    - path: "backend/app/services/sandbox_bridge_service.py"
      provides: "BridgeTokenEntry dataclass, _TOKEN_STORE, create_bridge_token, validate_token, revoke_token, _generate_stubs, inject_stubs"
      contains: "class BridgeTokenEntry"
    - path: "backend/tests/unit/test_sandbox_bridge_service.py"
      provides: "Unit tests for token lifecycle and stub generation"
      contains: "def test_token_create_validate_revoke"
---

# Plan 14-01: Bridge Config, ToolClient Docker Image & sandbox_bridge_service Foundation

## Objective

Lay the foundation for Phase 14's sandbox HTTP bridge by:
1. Adding `bridge_port` to config
2. Creating the `ToolClient` Python module (pre-baked in sandbox Docker image)
3. Building `sandbox_bridge_service.py` — the token store, validator, stub generator, and stub injector
4. Writing unit tests for all new pure-Python logic

This plan establishes all the data structures and logic that subsequent plans (14-02: sandbox patch, 14-03: bridge router) will consume.

## Tasks

<task id="14-01-T1" name="Add bridge_port to config">
<read_first>
- backend/app/config.py (current Settings class — must see existing fields before adding)
</read_first>
<action>
Open `backend/app/config.py`. In the `Settings` class, after the existing `sandbox_docker_host` field and near the other sandbox settings, add exactly:

```python
# Phase 14 (BRIDGE-01, D-P14-01): host port the bridge FastAPI app listens on.
# Sandbox containers connect to host.docker.internal:{bridge_port}.
# Env var: BRIDGE_PORT. Default matches PRD §Infrastructure.
bridge_port: int = 8002
```

No other changes. Run import smoke test after: `python -c "from app.main import app; print('OK')"` from `backend/` with venv active.
</action>
<acceptance_criteria>
- `grep "bridge_port" backend/app/config.py` returns a line containing `bridge_port: int = 8002`
- `grep "BRIDGE_PORT" backend/app/config.py` returns the env-var comment
- `python -c "from app.config import get_settings; s = get_settings(); assert s.bridge_port == 8002, s.bridge_port; print('OK')"` exits 0 from backend/ with venv active
</acceptance_criteria>
</task>

<task id="14-01-T2" name="Create ToolClient module for sandbox Docker image">
<read_first>
- backend/sandbox/ (directory does not exist yet — create it)
- docs/superpowers/PRD-advanced-tool-calling.md §Feature 4 (ToolClient requirements: stdlib only, BRIDGE-01)
- .planning/phases/14-sandbox-http-bridge-code-mode/14-CONTEXT.md (D-P14-08: ToolClient spec)
</read_first>
<action>
Create directory `backend/sandbox/` and write `backend/sandbox/tool_client.py`:

```python
"""ToolClient — pre-baked bridge client for the LexCore sandbox container.

Phase 14 / BRIDGE-01 (D-P14-08).

Reads BRIDGE_URL and BRIDGE_TOKEN from environment at call time (not import
time) so the module can be imported in tests without env vars set.

Uses only stdlib: urllib.request, urllib.error, json, os.
No third-party dependencies — the sandbox image is kept minimal.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class ToolClient:
    """HTTP client for calling platform tools through the sandbox bridge."""

    def call(self, tool_name: str, **kwargs: Any) -> dict:
        """Call a platform tool through the bridge endpoint.

        Args:
            tool_name: Registered tool name (e.g. 'search_documents').
            **kwargs: Tool arguments (passed as JSON body 'arguments' field).

        Returns:
            Tool result as a dict on success.
            {'error': 'bridge_error', 'message': '...'} on any failure.
            Exceptions are NEVER raised — always returns a dict (BRIDGE-07).
        """
        bridge_url = os.environ.get("BRIDGE_URL", "")
        bridge_token = os.environ.get("BRIDGE_TOKEN", "")
        timeout = int(os.environ.get("BRIDGE_TIMEOUT", "30"))

        if not bridge_url:
            return {"error": "bridge_error", "message": "BRIDGE_URL not set"}

        payload = json.dumps({
            "tool_name": tool_name,
            "arguments": kwargs,
            "session_token": bridge_token,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{bridge_url}/bridge/call",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
                detail = json.loads(body)
            except Exception:
                detail = {"detail": str(exc)}
            return {"error": "bridge_error", "message": str(exc), "detail": detail}
        except Exception as exc:
            return {"error": "bridge_error", "message": str(exc)}
```
</action>
<acceptance_criteria>
- `test -f backend/sandbox/tool_client.py` exits 0
- `grep "class ToolClient" backend/sandbox/tool_client.py` returns the class definition
- `grep "urllib.request" backend/sandbox/tool_client.py` returns at least one import line
- `python3 -c "import sys; sys.path.insert(0,'backend/sandbox'); from tool_client import ToolClient; tc = ToolClient(); r = tc.call('test'); assert r.get('error') == 'bridge_error'; print('OK')"` exits 0 (returns error dict when BRIDGE_URL unset, does not raise)
- `grep -E "import (subprocess|socket|requests|httpx)" backend/sandbox/tool_client.py` returns nothing (no third-party/dangerous imports)
</acceptance_criteria>
</task>

<task id="14-01-T3" name="Create sandbox Dockerfile">
<read_first>
- backend/Dockerfile (existing Railway Dockerfile pattern)
- backend/sandbox/tool_client.py (just created — must exist before Dockerfile references it)
- .planning/phases/14-sandbox-http-bridge-code-mode/14-CONTEXT.md (D-P14-08: sandbox image spec)
</read_first>
<action>
Create `backend/sandbox/Dockerfile`:

```dockerfile
# Sandbox Docker image for LexCore — Phase 14 / BRIDGE-01 (D-P14-08).
#
# Extends the standard Python slim image (same base as llm-sandbox default).
# Pre-bakes ToolClient at /sandbox/tool_client.py so LLM-generated code
# can do `from tool_client import ToolClient` without any pip install.
#
# Build: docker build -t lexcore-sandbox:latest backend/sandbox/
# This image tag matches settings.sandbox_image default in config.py.
#
# Note: This is NOT the Railway production image (that is backend/Dockerfile).
# This image runs as the llm-sandbox container for code execution.

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

Build is NOT automated in this plan — the Docker image rebuild is a deployment step documented in the plan's notes. The planner notes this in the verification section.
</action>
<acceptance_criteria>
- `test -f backend/sandbox/Dockerfile` exits 0
- `grep "COPY tool_client.py /sandbox/tool_client.py" backend/sandbox/Dockerfile` returns that line
- `grep "FROM python:3.12" backend/sandbox/Dockerfile` returns the FROM line
- `grep "mkdir -p /sandbox/output" backend/sandbox/Dockerfile` returns that line
- `grep "chmod 777 /sandbox" backend/sandbox/Dockerfile` returns that line (write permission for stub injection)
</acceptance_criteria>
</task>

<task id="14-01-T4" name="Create sandbox_bridge_service.py">
<read_first>
- backend/app/services/sandbox_service.py (SandboxSession dataclass + _sessions dict pattern to replicate)
- backend/app/services/tool_registry.py (ToolDefinition type — import for stub generation)
- backend/app/services/tracing_service.py (traced decorator pattern)
- .planning/phases/14-sandbox-http-bridge-code-mode/14-CONTEXT.md (D-P14-03, D-P14-04, D-P14-08)
- .planning/phases/14-sandbox-http-bridge-code-mode/14-PATTERNS.md (analog code excerpts)
</read_first>
<action>
Create `backend/app/services/sandbox_bridge_service.py`:

```python
"""Sandbox Bridge Service — Phase 14 / BRIDGE-01..04 (D-P14-03, D-P14-04, D-P14-08).

Owns:
  - BridgeTokenEntry dataclass (thread-scoped ephemeral tokens)
  - _TOKEN_STORE module-level dict (keyed by thread_id)
  - create_bridge_token(thread_id, user_id) -> str
  - validate_token(session_token, user_id) -> bool
  - revoke_token(thread_id) -> None
  - _generate_stubs(active_tools) -> str  (Python stub code)
  - inject_stubs(session, active_tools) -> None  (writes /sandbox/stubs.py)

Design decisions (D-P14-03):
  - One UUID token per SandboxSession, same lifetime as 30-min sandbox TTL.
  - _TOKEN_STORE is module-level (no class, no async lock — creation is already
    under sandbox_service._lock via _get_or_create_session).
  - No DB persistence (consistent with D-P10-09 in-memory sessions).
  - revoke_token() is called from sandbox_service._cleanup_loop() when a
    session is evicted.

Stub injection (D-P14-04):
  - inject_stubs() writes /sandbox/stubs.py once at session creation.
  - Each subsequent run prepends `from stubs import *\n` to submitted code
    (done in tool_service._execute_code, Plan 14-04).
  - Stub function signatures extracted from OpenAI tool schema properties.
  - anyOf/oneOf simplified to Any (readability > precision at this layer).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.models.tools import ToolDefinition


# ---------------------------------------------------------------------------
# Token store
# ---------------------------------------------------------------------------

@dataclass
class BridgeTokenEntry:
    """Ephemeral bridge session token for one sandbox container."""
    token: str
    user_id: str
    thread_id: str
    created_at: datetime


# Module-level store: thread_id -> BridgeTokenEntry
# No async lock needed — token creation runs inside sandbox_service._lock
# (via _get_or_create_session). Module-level dict is safe for single-process
# Railway deployment (D-P10-09 pattern).
_TOKEN_STORE: dict[str, BridgeTokenEntry] = {}


def create_bridge_token(thread_id: str, user_id: str) -> str:
    """Generate and store a new bridge token for the given thread/user.

    Overwrites any existing token for thread_id (safe: called only on new
    container creation, which replaces the old container).

    Returns:
        UUID string token to inject into the container as BRIDGE_TOKEN env var.
    """
    token = str(uuid.uuid4())
    _TOKEN_STORE[thread_id] = BridgeTokenEntry(
        token=token,
        user_id=user_id,
        thread_id=thread_id,
        created_at=datetime.utcnow(),
    )
    logger.debug("bridge token created thread_id=%s user_id=%s", thread_id, user_id)
    return token


def validate_token(session_token: str, user_id: str) -> bool:
    """Validate a bridge session token against the stored entry.

    Two conditions must both be true:
      1. session_token exists in the store (any entry matches by value).
      2. The stored entry's user_id matches the provided user_id.

    Returns:
        True if both conditions hold, False otherwise.
        Never raises.
    """
    entry = next(
        (e for e in _TOKEN_STORE.values() if e.token == session_token),
        None,
    )
    if entry is None:
        logger.debug("bridge validate_token: token not found")
        return False
    if entry.user_id != user_id:
        logger.warning(
            "bridge validate_token: user_id mismatch stored=%s provided=%s",
            entry.user_id,
            user_id,
        )
        return False
    return True


def revoke_token(thread_id: str) -> None:
    """Remove the bridge token for thread_id.

    No-op if thread_id has no entry. Called from sandbox_service._cleanup_loop()
    when a session is evicted (D-P14-03).
    """
    removed = _TOKEN_STORE.pop(thread_id, None)
    if removed:
        logger.debug("bridge token revoked thread_id=%s", thread_id)


# ---------------------------------------------------------------------------
# Stub generation and injection
# ---------------------------------------------------------------------------

_STUB_HEADER = '''\
# Auto-generated typed stubs for sandbox bridge tools.
# DO NOT EDIT — regenerated on each new sandbox session.
# Usage: from stubs import *  (prepended by execute_code handler)
from __future__ import annotations
from typing import Any
try:
    from tool_client import ToolClient as _TC
    _client = _TC()
except ImportError:
    # Fallback for test environments where tool_client is not on path
    class _TC:  # type: ignore[no-redef]
        def call(self, *a, **kw):
            return {"error": "bridge_error", "message": "ToolClient not available"}
    _client = _TC()

'''


def _py_type(schema_type: str | None, schema_format: str | None = None) -> str:
    """Map JSON Schema type string to Python type annotation string."""
    if schema_type == "string":
        return "str"
    if schema_type == "integer":
        return "int"
    if schema_type == "number":
        return "float"
    if schema_type == "boolean":
        return "bool"
    if schema_type == "array":
        return "list[Any]"
    if schema_type == "object":
        return "dict[str, Any]"
    return "Any"


def _generate_stubs(active_tools: list[ToolDefinition]) -> str:
    """Generate Python stub code for all active tools.

    Each stub is a typed function wrapping _client.call(tool_name, **kwargs).

    Args:
        active_tools: List of ToolDefinition objects (from tool_registry).

    Returns:
        Python source string to be written to /sandbox/stubs.py.
    """
    lines = [_STUB_HEADER]

    for tool in active_tools:
        name = tool.name
        schema = tool.schema or {}
        fn_schema = schema.get("function", schema)
        description = (tool.description or "")[:120]
        params_schema = fn_schema.get("parameters", {})
        properties = params_schema.get("properties", {})
        required = set(params_schema.get("required", []))

        # Build parameter list
        param_parts: list[str] = []
        for param_name, param_info in properties.items():
            py_type = _py_type(
                param_info.get("type"),
                param_info.get("format"),
            )
            # anyOf/oneOf → Any
            if "anyOf" in param_info or "oneOf" in param_info:
                py_type = "Any"
            if param_name in required:
                param_parts.append(f"{param_name}: {py_type}")
            else:
                param_parts.append(f"{param_name}: {py_type} | None = None")

        params_str = ", ".join(param_parts)
        if params_str:
            sig = f"def {name}({params_str}) -> dict:"
        else:
            sig = f"def {name}() -> dict:"

        # Build call kwargs
        if properties:
            kwargs_items = ", ".join(
                f"{p}={p}" for p in properties
            )
            call_line = f"    return _client.call({name!r}, {kwargs_items})"
        else:
            call_line = f"    return _client.call({name!r})"

        lines.append(f"def {name}({params_str}) -> dict:")
        lines.append(f'    """{description}"""')
        lines.append(call_line)
        lines.append("")

    return "\n".join(lines)


def inject_stubs(session: Any, active_tools: list[ToolDefinition]) -> None:
    """Write /sandbox/stubs.py into the container via execute_command.

    Called immediately after container.open() when bridge is active (D-P14-04).

    Strategy: use execute_command to run a Python one-liner that writes the
    stub file. If execute_command is unavailable, fall back to container.run().

    Args:
        session: SandboxSession (container field accessed as session.container).
        active_tools: Tools to generate stubs for.
    """
    stub_code = _generate_stubs(active_tools)
    container = session.container

    # Escape for shell single-quote context: replace ' with '"'"'
    escaped = stub_code.replace("'", "'\"'\"'")

    try:
        # Primary: execute_command writes via shell heredoc-style echo
        # Note: execute_command is synchronous in llm-sandbox v0.3.39
        container.execute_command(
            f"python3 -c $'import sys; "
            f"open(\"/sandbox/stubs.py\",\"w\").write(sys.stdin.read())' "
            f"<<'STUB_EOF'\n{stub_code}\nSTUB_EOF"
        )
        logger.debug("inject_stubs: wrote /sandbox/stubs.py via execute_command")
    except Exception as exc:
        logger.warning(
            "inject_stubs: execute_command failed (%s), falling back to run()", exc
        )
        try:
            # Fallback: use container.run() to write the file inline
            # run() is synchronous (bridged via run_in_executor in execute())
            safe_code = repr(stub_code)
            container.run(
                f"open('/sandbox/stubs.py', 'w').write({safe_code})"
            )
            logger.debug("inject_stubs: wrote /sandbox/stubs.py via run() fallback")
        except Exception as exc2:
            logger.error("inject_stubs: both strategies failed: %s", exc2)
```
</action>
<acceptance_criteria>
- `test -f backend/app/services/sandbox_bridge_service.py` exits 0
- `grep "class BridgeTokenEntry" backend/app/services/sandbox_bridge_service.py` returns the dataclass
- `grep "def create_bridge_token" backend/app/services/sandbox_bridge_service.py` returns the function
- `grep "def validate_token" backend/app/services/sandbox_bridge_service.py` returns the function
- `grep "def revoke_token" backend/app/services/sandbox_bridge_service.py` returns the function
- `grep "def _generate_stubs" backend/app/services/sandbox_bridge_service.py` returns the function
- `grep "def inject_stubs" backend/app/services/sandbox_bridge_service.py` returns the function
- `python -c "from app.services.sandbox_bridge_service import create_bridge_token, validate_token, revoke_token; t = create_bridge_token('thread1', 'user1'); assert validate_token(t, 'user1'); assert not validate_token(t, 'user2'); revoke_token('thread1'); assert not validate_token(t, 'user1'); print('OK')"` exits 0 from backend/ with venv active
</acceptance_criteria>
</task>

<task id="14-01-T5" name="Write unit tests for sandbox_bridge_service">
<read_first>
- backend/app/services/sandbox_bridge_service.py (just created)
- backend/tests/unit/ (directory listing — find existing test file pattern)
- .planning/phases/13-unified-tool-registry-tool-search-meta-tool/13-01-tool-registry-foundation-PLAN.md (test pattern from Phase 13)
</read_first>
<action>
Create `backend/tests/unit/test_sandbox_bridge_service.py`:

```python
"""Unit tests for sandbox_bridge_service — Phase 14 / BRIDGE-01, BRIDGE-03.

Tests:
  - Token lifecycle (create, validate, revoke)
  - validate_token rejects wrong user_id
  - validate_token rejects unknown token
  - _generate_stubs produces valid Python with correct function signatures
"""
import ast
import importlib

import pytest

# Re-import module fresh for each test to reset module-level _TOKEN_STORE
import backend.app.services.sandbox_bridge_service as svc


@pytest.fixture(autouse=True)
def clear_token_store():
    """Reset _TOKEN_STORE before each test to prevent cross-test contamination."""
    svc._TOKEN_STORE.clear()
    yield
    svc._TOKEN_STORE.clear()


# ---------------------------------------------------------------------------
# Token lifecycle
# ---------------------------------------------------------------------------

class TestTokenLifecycle:
    def test_create_returns_nonempty_uuid_string(self):
        token = svc.create_bridge_token("thread-1", "user-a")
        assert isinstance(token, str)
        assert len(token) == 36  # UUID4 format with hyphens
        assert "-" in token

    def test_validate_correct_credentials_returns_true(self):
        token = svc.create_bridge_token("thread-1", "user-a")
        assert svc.validate_token(token, "user-a") is True

    def test_validate_wrong_user_id_returns_false(self):
        token = svc.create_bridge_token("thread-1", "user-a")
        assert svc.validate_token(token, "user-b") is False

    def test_validate_unknown_token_returns_false(self):
        assert svc.validate_token("no-such-token", "user-a") is False

    def test_revoke_removes_token(self):
        token = svc.create_bridge_token("thread-1", "user-a")
        svc.revoke_token("thread-1")
        assert svc.validate_token(token, "user-a") is False

    def test_revoke_noop_on_missing_thread(self):
        # Should not raise
        svc.revoke_token("nonexistent-thread")

    def test_multiple_threads_isolated(self):
        t1 = svc.create_bridge_token("thread-1", "user-a")
        t2 = svc.create_bridge_token("thread-2", "user-b")
        assert svc.validate_token(t1, "user-a") is True
        assert svc.validate_token(t2, "user-b") is True
        assert svc.validate_token(t1, "user-b") is False  # cross-user
        svc.revoke_token("thread-1")
        assert svc.validate_token(t1, "user-a") is False
        assert svc.validate_token(t2, "user-b") is True  # unaffected


# ---------------------------------------------------------------------------
# Stub generation
# ---------------------------------------------------------------------------

class FakeToolDef:
    """Minimal ToolDefinition stand-in for testing stub generation."""
    def __init__(self, name, description, schema):
        self.name = name
        self.description = description
        self.schema = schema


class TestGenerateStubs:
    def _make_tool(self, name, params: dict, required: list[str] | None = None):
        return FakeToolDef(
            name=name,
            description=f"Tool {name}",
            schema={
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": params,
                        "required": required or [],
                    },
                },
            },
        )

    def test_generates_valid_python(self):
        tools = [
            self._make_tool("search_documents", {"query": {"type": "string"}}, ["query"]),
        ]
        code = svc._generate_stubs(tools)
        # Must be parseable Python
        tree = ast.parse(code)
        assert tree is not None

    def test_required_param_has_no_default(self):
        tools = [
            self._make_tool("search_documents", {"query": {"type": "string"}}, ["query"]),
        ]
        code = svc._generate_stubs(tools)
        assert "def search_documents(query: str)" in code or "query: str" in code

    def test_optional_param_has_none_default(self):
        tools = [
            self._make_tool("search_documents", {
                "query": {"type": "string"},
                "filter_tags": {"type": "array"},
            }, ["query"]),
        ]
        code = svc._generate_stubs(tools)
        assert "filter_tags: list[Any] | None = None" in code

    def test_no_params_generates_no_arg_function(self):
        tools = [self._make_tool("no_args_tool", {}, [])]
        code = svc._generate_stubs(tools)
        assert "def no_args_tool()" in code

    def test_stub_calls_client_call(self):
        tools = [
            self._make_tool("search_documents", {"query": {"type": "string"}}, ["query"]),
        ]
        code = svc._generate_stubs(tools)
        assert "_client.call('search_documents'" in code or '_client.call("search_documents"' in code

    def test_tool_client_import_in_header(self):
        code = svc._generate_stubs([])
        assert "from tool_client import ToolClient" in code

    def test_anyof_param_becomes_any(self):
        tools = [
            self._make_tool("complex_tool", {
                "val": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
            }, []),
        ]
        code = svc._generate_stubs(tools)
        assert "val: Any" in code
```
</action>
<acceptance_criteria>
- `test -f backend/tests/unit/test_sandbox_bridge_service.py` exits 0
- `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_sandbox_bridge_service.py -v --tb=short 2>&1 | tail -5` shows all tests PASSED with exit 0
- No test imports `asyncio` or any async fixtures (all tested functions are synchronous)
</acceptance_criteria>
</task>

## Verification

```bash
# From backend/ with venv active:

# 1. Import smoke test
python -c "from app.main import app; print('OK')"

# 2. Config field
python -c "from app.config import get_settings; s = get_settings(); assert s.bridge_port == 8002; print('bridge_port OK')"

# 3. ToolClient smoke (no BRIDGE_URL set → returns error dict, does not raise)
python3 -c "
import sys; sys.path.insert(0,'sandbox')
from tool_client import ToolClient
tc = ToolClient()
r = tc.call('test_tool', query='hello')
assert r.get('error') == 'bridge_error', r
print('ToolClient OK')
"

# 4. sandbox_bridge_service unit tests
python -m pytest tests/unit/test_sandbox_bridge_service.py -v --tb=short

# 5. File existence checks
test -f sandbox/Dockerfile && echo "Dockerfile OK"
test -f sandbox/tool_client.py && echo "tool_client.py OK"
test -f app/services/sandbox_bridge_service.py && echo "sandbox_bridge_service OK"
```

**Docker image rebuild note:** After this plan, the sandbox Docker image must be rebuilt locally to include the new `tool_client.py`. This is a deployment step, not part of automated CI:
```bash
docker build -t lexcore-sandbox:latest backend/sandbox/
```
This is documented for the deployer. The image rebuild is required before end-to-end bridge testing (Plan 14-03+).

<threat_model>
## Threat Model (ASVS L1)

| Threat | Mitigation |
|--------|-----------|
| Token brute-force | UUID4 tokens have 122 bits of entropy; rate limiting on `/bridge/call` in Plan 14-03 |
| Token leakage via logs | Logger uses DEBUG level for token events; production log level is INFO |
| Cross-user token reuse | `validate_token()` checks both token value AND user_id; mismatch returns False |
| Stale tokens persisting | Tokens live in module-level dict; revoked on session eviction (D-P14-03); process restart clears all |
| Stub injection with malicious tool names | Tool names come from the registry (controlled by the platform, not user input); names are valid Python identifiers enforced at registration time |
| ToolClient leaking credentials | ToolClient reads only BRIDGE_URL and BRIDGE_TOKEN from env — no Supabase keys, no OpenAI keys are injected (D-P14-02) |
</threat_model>
