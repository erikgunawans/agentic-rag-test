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


def _generate_stubs(active_tools: list) -> str:
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
            # anyOf/oneOf → Any
            if "anyOf" in param_info or "oneOf" in param_info:
                py_type = "Any"
            else:
                py_type = _py_type(
                    param_info.get("type"),
                    param_info.get("format"),
                )
            if param_name in required:
                param_parts.append(f"{param_name}: {py_type}")
            else:
                param_parts.append(f"{param_name}: {py_type} | None = None")

        params_str = ", ".join(param_parts)

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


def inject_stubs(session: Any, active_tools: list) -> None:
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

    try:
        # Primary: execute_command writes via Python that reads from a repr literal
        safe_code = repr(stub_code)
        container.execute_command(
            f"python3 -c \"open('/sandbox/stubs.py','w').write({safe_code})\""
        )
        logger.debug("inject_stubs: wrote /sandbox/stubs.py via execute_command")
    except Exception as exc:
        logger.warning(
            "inject_stubs: execute_command failed (%s), falling back to run()", exc
        )
        try:
            # Fallback: use container.run() to write the file inline
            safe_code = repr(stub_code)
            container.run(
                f"open('/sandbox/stubs.py', 'w').write({safe_code})"
            )
            logger.debug("inject_stubs: wrote /sandbox/stubs.py via run() fallback")
        except Exception as exc2:
            logger.error("inject_stubs: both strategies failed: %s", exc2)
