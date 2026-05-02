---
phase: 14-sandbox-http-bridge-code-mode
plan: 03
type: execute
wave: 2
depends_on:
  - "14-01"
  - "14-02"
files_modified:
  - backend/app/routers/bridge.py
  - backend/tests/unit/test_bridge_router.py
autonomous: true
requirements:
  - BRIDGE-02
  - BRIDGE-03
must_haves:
  truths:
    - "backend/app/routers/bridge.py exists with router = APIRouter(prefix='/bridge', tags=['Bridge'])"
    - "POST /bridge/call endpoint exists: accepts BridgeCallRequest with tool_name, arguments, session_token; validates JWT via get_current_user; validates session_token via sandbox_bridge_service.validate_token; dispatches to tool_registry; returns BridgeCallResponse"
    - "GET /bridge/catalog endpoint exists: accepts session_token query param; validates JWT and session_token; returns list of available tool catalog entries"
    - "GET /bridge/health endpoint exists: returns {'status': 'ok'} without auth"
    - "POST /bridge/call returns HTTP 401 when session_token is missing, expired, or user_id mismatch"
    - "POST /bridge/call returns HTTP 404 when tool_name is not found in registry"
    - "POST /bridge/call dispatches to tool_registry.execute() and returns the result dict"
    - "test_bridge_router.py covers: health endpoint returns ok, call rejects missing token (401), call rejects wrong user (401), call dispatches to registry and returns result, catalog returns tool list"
  artifacts:
    - path: "backend/app/routers/bridge.py"
      provides: "Bridge router with /bridge/call, /bridge/catalog, /bridge/health endpoints"
      contains: "router = APIRouter(prefix='/bridge'"
    - path: "backend/tests/unit/test_bridge_router.py"
      provides: "Unit tests for bridge router auth and dispatch logic"
      contains: "def test_bridge_health_returns_ok"
---

# Plan 14-03: Bridge Router — `/bridge/call`, `/bridge/catalog`, `/bridge/health`

## Objective

Create `backend/app/routers/bridge.py` with three endpoints that implement the sandbox HTTP bridge API (BRIDGE-02, BRIDGE-03). The router is NOT registered in `main.py` in this plan — that wiring happens in Plan 14-04.

This plan also writes unit tests for the router's auth and dispatch logic.

## Tasks

<task id="14-03-T1" name="Create bridge router with three endpoints">
<read_first>
- backend/app/routers/code_execution.py (analog pattern: APIRouter, Depends, get_current_user, Pydantic models)
- backend/app/routers/skills.py (analog pattern: request/response models, HTTPException usage)
- backend/app/services/sandbox_bridge_service.py (validate_token, revoke_token — just created in Plan 14-01)
- backend/app/services/tool_registry.py (registry execute API from Phase 13)
- backend/app/dependencies.py (get_current_user dependency signature)
- .planning/phases/14-sandbox-http-bridge-code-mode/14-CONTEXT.md (D-P14-09: two-layer auth, D-P14-05: dual-flag gate)
- docs/superpowers/PRD-advanced-tool-calling.md §Feature 4 (endpoint specifications: BRIDGE-02, BRIDGE-03)
</read_first>
<action>
Create `backend/app/routers/bridge.py`:

```python
"""Sandbox HTTP Bridge Router — Phase 14 / BRIDGE-02, BRIDGE-03 (D-P14-09).

Exposes three endpoints for LLM-generated code running inside the sandbox
to call platform tools through the host-side bridge:

  POST /bridge/call      — execute a tool by name with arguments
  GET  /bridge/catalog   — list available tools for the session
  GET  /bridge/health    — liveness check (no auth required)

Auth model (D-P14-09 — two layers):
  Outer: Supabase JWT validated by get_current_user (same as all routers).
  Inner: session_token validated by sandbox_bridge_service.validate_token()
         — ensures the request comes from the container that owns the session,
         not another user who somehow obtained a valid JWT.

This router is only mounted in main.py when:
  settings.sandbox_enabled AND settings.tool_registry_enabled (D-P14-05).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.services import sandbox_bridge_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bridge", tags=["Bridge"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class BridgeCallRequest(BaseModel):
    """Body for POST /bridge/call."""
    tool_name: str
    arguments: dict = {}
    session_token: str


class BridgeCallResponse(BaseModel):
    """Response from POST /bridge/call — always a dict from the tool executor."""
    result: dict


class BridgeCatalogEntry(BaseModel):
    """Single tool entry in the bridge catalog."""
    name: str
    source: str
    description: str


class BridgeCatalogResponse(BaseModel):
    """Response from GET /bridge/catalog."""
    tools: list[BridgeCatalogEntry]


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _validate_bridge_token(session_token: str, user_id: str) -> None:
    """Validate the bridge session token against the stored entry.

    Raises HTTP 401 if the token is invalid or user_id mismatches.
    This is the INNER auth layer (outer layer = get_current_user JWT check).
    """
    if not sandbox_bridge_service.validate_token(session_token, user_id):
        logger.warning(
            "bridge auth failed: invalid or mismatched token user_id=%s", user_id
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid, expired, or mismatched bridge session token.",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def bridge_health():
    """Liveness check — no auth required. Used by ToolClient to verify connectivity."""
    return {"status": "ok"}


@router.get("/catalog", response_model=BridgeCatalogResponse)
async def bridge_catalog(
    session_token: str = Query(..., description="Bridge session token from BRIDGE_TOKEN env var"),
    user: dict = Depends(get_current_user),
):
    """List available tools for this bridge session.

    Returns the same tools that were available when the session started.
    The LLM-generated code can call this to discover tools programmatically.
    """
    user_id = user["id"]
    _validate_bridge_token(session_token, user_id)

    # Import registry lazily (TOOL-05: only imported when flag is on)
    try:
        from app.services import tool_registry
    except ImportError:
        raise HTTPException(status_code=503, detail="Tool registry not available.")

    # Build catalog entries from the registry (same data as system-prompt catalog)
    tools = []
    for name, tool_def in tool_registry._REGISTRY.items():
        if name == "tool_search":
            continue  # Exclude meta-tool from catalog (D-P13-04)
        tools.append(BridgeCatalogEntry(
            name=name,
            source=tool_def.source,
            description=tool_def.description[:120],
        ))

    tools.sort(key=lambda t: t.name)
    return BridgeCatalogResponse(tools=tools)


@router.post("/call", response_model=BridgeCallResponse)
async def bridge_call(
    body: BridgeCallRequest,
    user: dict = Depends(get_current_user),
):
    """Execute a platform tool from sandbox code.

    The sandbox container sends this request with its session_token
    (injected as BRIDGE_TOKEN env var). The bridge validates both:
      1. The JWT in the Authorization header (user identity).
      2. The session_token in the body (container identity).

    Tool dispatch goes through the unified tool registry (Phase 13).
    Credentials (Supabase service-role keys, API keys) never leave the host.
    """
    user_id = user["id"]
    _validate_bridge_token(body.session_token, user_id)

    # Lazy import (TOOL-05)
    try:
        from app.services import tool_registry
    except ImportError:
        raise HTTPException(status_code=503, detail="Tool registry not available.")

    # Look up tool in registry
    tool_def = tool_registry._REGISTRY.get(body.tool_name)
    if tool_def is None:
        logger.warning(
            "bridge_call: unknown tool tool_name=%s user_id=%s",
            body.tool_name,
            user_id,
        )
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{body.tool_name}' not found in registry.",
        )

    # Build execution context (mirrors chat.py tool dispatch context)
    ctx = {
        "user_id": user_id,
        "token": user["token"],
        "thread_id": None,  # Bridge calls are stateless per-call
    }

    # Dispatch through the registry executor (D-P13-01: executor delegates to ToolService.execute_tool)
    try:
        result = await tool_def.executor(body.arguments, ctx)
        # Normalize result to dict (executors may return str or dict)
        if isinstance(result, str):
            result = {"output": result}
        elif not isinstance(result, dict):
            result = {"output": str(result)}
    except Exception as exc:
        logger.error(
            "bridge_call: tool executor raised tool=%s err=%s",
            body.tool_name,
            exc,
            exc_info=True,
        )
        # BRIDGE-07: errors return as structured dicts, never leak exceptions
        result = {
            "error": "tool_execution_error",
            "message": str(exc),
        }

    return BridgeCallResponse(result=result)
```
</action>
<acceptance_criteria>
- `test -f backend/app/routers/bridge.py` exits 0
- `grep "router = APIRouter(prefix='/bridge'" backend/app/routers/bridge.py` returns that line
- `grep "def bridge_health" backend/app/routers/bridge.py` returns the health endpoint
- `grep "def bridge_catalog" backend/app/routers/bridge.py` returns the catalog endpoint
- `grep "def bridge_call" backend/app/routers/bridge.py` returns the call endpoint
- `grep "_validate_bridge_token" backend/app/routers/bridge.py` returns at least 2 occurrences (definition + 2 call sites)
- `python -c "from app.routers.bridge import router; print('OK')"` exits 0 from backend/ with venv active
</acceptance_criteria>
</task>

<task id="14-03-T2" name="Write unit tests for bridge router">
<read_first>
- backend/app/routers/bridge.py (just created)
- backend/tests/unit/ (check for httpx TestClient pattern or FastAPI test patterns)
</read_first>
<action>
Create `backend/tests/unit/test_bridge_router.py`:

```python
"""Unit tests for bridge router — Phase 14 / BRIDGE-02, BRIDGE-03.

Uses FastAPI TestClient with dependency overrides to test auth and routing
without requiring a live Docker sandbox or Supabase connection.
"""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.bridge import router
from app.dependencies import get_current_user


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def make_user(user_id: str = "user-1") -> dict:
    return {"id": user_id, "email": "test@test.com", "token": "test-jwt", "role": "user"}


def make_app(user_id: str = "user-1") -> FastAPI:
    """Create a minimal FastAPI app with the bridge router and a mocked user dependency."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: make_user(user_id)
    return app


# ---------------------------------------------------------------------------
# Health endpoint (no auth)
# ---------------------------------------------------------------------------

class TestBridgeHealth:
    def test_health_returns_ok(self):
        app = make_app()
        with TestClient(app) as client:
            r = client.get("/bridge/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Auth rejection
# ---------------------------------------------------------------------------

class TestBridgeAuth:
    def test_call_rejects_invalid_token_401(self):
        app = make_app(user_id="user-1")
        with (
            patch("app.routers.bridge.sandbox_bridge_service.validate_token", return_value=False),
            patch("app.routers.bridge.tool_registry", create=True),
            TestClient(app) as client,
        ):
            r = client.post("/bridge/call", json={
                "tool_name": "search_documents",
                "arguments": {"query": "test"},
                "session_token": "bad-token",
            })
        assert r.status_code == 401

    def test_catalog_rejects_invalid_token_401(self):
        app = make_app(user_id="user-1")
        with (
            patch("app.routers.bridge.sandbox_bridge_service.validate_token", return_value=False),
            TestClient(app) as client,
        ):
            r = client.get("/bridge/catalog", params={"session_token": "bad-token"})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

class TestBridgeCall:
    def _make_registry_with_tool(self, tool_name: str, result: dict):
        executor = AsyncMock(return_value=result)
        tool_def = MagicMock()
        tool_def.executor = executor
        tool_def.source = "native"
        registry = {tool_name: tool_def}
        return registry, executor

    def test_call_unknown_tool_returns_404(self):
        app = make_app(user_id="user-1")
        with (
            patch("app.routers.bridge.sandbox_bridge_service.validate_token", return_value=True),
            patch("app.routers.bridge.tool_registry") as mock_registry,
            TestClient(app) as client,
        ):
            mock_registry._REGISTRY = {}
            r = client.post("/bridge/call", json={
                "tool_name": "nonexistent_tool",
                "arguments": {},
                "session_token": "valid-token",
            })
        assert r.status_code == 404

    def test_call_dispatches_to_executor_and_returns_result(self):
        expected_result = {"documents": [{"id": "doc-1", "content": "test"}]}
        app = make_app(user_id="user-1")
        registry, executor = self._make_registry_with_tool("search_documents", expected_result)
        with (
            patch("app.routers.bridge.sandbox_bridge_service.validate_token", return_value=True),
            patch("app.routers.bridge.tool_registry") as mock_registry,
            TestClient(app) as client,
        ):
            mock_registry._REGISTRY = registry
            r = client.post("/bridge/call", json={
                "tool_name": "search_documents",
                "arguments": {"query": "revenue"},
                "session_token": "valid-token",
            })
        assert r.status_code == 200
        data = r.json()
        assert "result" in data
        assert data["result"] == expected_result
        executor.assert_called_once()

    def test_call_executor_exception_returns_structured_error(self):
        app = make_app(user_id="user-1")
        executor = AsyncMock(side_effect=RuntimeError("tool blew up"))
        tool_def = MagicMock()
        tool_def.executor = executor
        with (
            patch("app.routers.bridge.sandbox_bridge_service.validate_token", return_value=True),
            patch("app.routers.bridge.tool_registry") as mock_registry,
            TestClient(app) as client,
        ):
            mock_registry._REGISTRY = {"search_documents": tool_def}
            r = client.post("/bridge/call", json={
                "tool_name": "search_documents",
                "arguments": {},
                "session_token": "valid-token",
            })
        assert r.status_code == 200  # BRIDGE-07: errors return as dicts, not HTTP errors
        data = r.json()
        assert data["result"]["error"] == "tool_execution_error"
        assert "tool blew up" in data["result"]["message"]
```
</action>
<acceptance_criteria>
- `test -f backend/tests/unit/test_bridge_router.py` exits 0
- `cd backend && source venv/bin/activate && python -m pytest tests/unit/test_bridge_router.py -v --tb=short 2>&1 | tail -5` shows all tests PASSED with exit 0
- Health test exists and passes
- Auth rejection tests for both /bridge/call and /bridge/catalog exist and pass
- Tool dispatch and error handling tests exist and pass
</acceptance_criteria>
</task>

## Verification

```bash
# From backend/ with venv active:

# 1. Import smoke test
python -c "from app.routers.bridge import router; print('bridge router import OK')"
python -c "from app.main import app; print('main import OK')"

# 2. Unit tests
python -m pytest tests/unit/test_bridge_router.py -v --tb=short

# 3. Verify router is NOT yet in main.py (Plan 14-04 handles this)
grep "bridge" backend/app/main.py | head -5  # should return nothing until Plan 14-04
```

<threat_model>
## Threat Model (ASVS L1)

| Threat | Mitigation |
|--------|-----------|
| Unauthenticated tool call | `get_current_user` dependency rejects requests without valid Supabase JWT (HTTP 401) |
| Cross-user tool call with stolen JWT | Inner `validate_token(session_token, user_id)` requires both token AND correct user_id; mismatch = 401 |
| Calling tools not in registry | HTTP 404 before any execution — tool_def lookup returns None |
| Tool executor exception leaking stack traces to container | Exception caught, wrapped in structured `{"error": ..., "message": ...}` dict (BRIDGE-07) |
| Container calling /bridge/call without a session token | BridgeCallRequest.session_token is required (Pydantic validation) — 422 if missing |
| SSRF via tool dispatch | Tool executors come from the registry (controlled list); no URL is accepted as input to the bridge call itself |
</threat_model>
