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
