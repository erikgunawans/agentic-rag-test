"""Phase 18 Plan 18-03: Tool dispatch tests for the four workspace tools.

Tests cover (11 behaviors):
1.  write_file executor happy path — ok=True, operation=create, size_bytes correct
2.  write_file executor with absolute path — returns path_invalid_leading_slash error
3.  write_file executor with content > 1 MB — returns text_content_too_large error
4.  read_file executor happy path — ok=True, is_binary=False, content present
5.  read_file executor on missing file — returns file_not_found error
6.  edit_file executor wires through to service — returns ok on unique match
7.  edit_file executor — returns edit_old_string_ambiguous on multi-occurrence
8.  list_files executor — returns ok=True, files=[], count=N
9.  WORKSPACE_ENABLED=False — none of the four tool names in _REGISTRY
10. WORKSPACE_ENABLED=True — all four tool names in _REGISTRY
11. Tool schemas conform to OpenAI tool-call format

Run (unit only, no DB required):
    cd backend && source venv/bin/activate &&
        pytest tests/tools/test_workspace_tools.py -v --tb=short

TDD Phase: RED (18-03 Task 2) — these tests are committed before the
implementation is verified green. They document the expected dispatch contract
between the tool registry executors and WorkspaceService.
"""

from __future__ import annotations

import importlib
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# 1. write_file executor happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_file_executor_happy_path():
    """Executor delegates to WorkspaceService.write_text_file and returns ok dict."""
    import app.services.tool_service as ts

    mock_ws = AsyncMock()
    mock_ws.write_text_file.return_value = {
        "ok": True,
        "operation": "create",
        "size_bytes": 5,
        "file_path": "notes/x.md",
    }

    with patch.object(
        sys.modules["app.services.tool_service"],
        "WorkspaceService",
        create=True,
        new=lambda token: mock_ws,
    ):
        # Patch WorkspaceService inside the executor's lazy import scope
        with patch.dict(
            sys.modules,
            {"app.services.workspace_service": MagicMock(WorkspaceService=lambda token: mock_ws)},
        ):
            result = await ts._workspace_write_file_executor(
                arguments={"file_path": "notes/x.md", "content": "hello"},
                user_id="user-1",
                context={"thread_id": "t1", "token": "tok"},
            )

    # Executor should return the service result unchanged
    assert result["ok"] is True
    assert result["operation"] == "create"
    assert result["size_bytes"] == 5


# ---------------------------------------------------------------------------
# 2. write_file executor — absolute path returns structured error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_file_executor_absolute_path():
    """Path validation error propagates from WorkspaceService as structured dict."""
    import app.services.tool_service as ts

    mock_ws = AsyncMock()
    mock_ws.write_text_file.return_value = {
        "error": "path_invalid_leading_slash",
        "detail": "path must be relative (no leading /)",
        "file_path": "/abs/path",
    }

    with patch.dict(
        sys.modules,
        {"app.services.workspace_service": MagicMock(WorkspaceService=lambda token: mock_ws)},
    ):
        result = await ts._workspace_write_file_executor(
            arguments={"file_path": "/abs/path", "content": "data"},
            user_id="user-1",
            context={"thread_id": "t1", "token": "tok"},
        )

    assert "error" in result
    assert result["error"] == "path_invalid_leading_slash"


# ---------------------------------------------------------------------------
# 3. write_file executor — content > 1 MB returns text_content_too_large
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_file_executor_content_too_large():
    """Oversized content error propagates from WorkspaceService."""
    import app.services.tool_service as ts

    oversize_content = "x" * (1024 * 1024 + 1)
    mock_ws = AsyncMock()
    mock_ws.write_text_file.return_value = {
        "error": "text_content_too_large",
        "limit_bytes": 1048576,
        "actual_bytes": len(oversize_content.encode("utf-8")),
        "file_path": "notes/big.md",
    }

    with patch.dict(
        sys.modules,
        {"app.services.workspace_service": MagicMock(WorkspaceService=lambda token: mock_ws)},
    ):
        result = await ts._workspace_write_file_executor(
            arguments={"file_path": "notes/big.md", "content": oversize_content},
            user_id="user-1",
            context={"thread_id": "t1", "token": "tok"},
        )

    assert result["error"] == "text_content_too_large"
    assert result["actual_bytes"] > 1048576


# ---------------------------------------------------------------------------
# 4. read_file executor — happy path returns text content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_file_executor_happy_path():
    """read_file executor returns ok=True with text content for text files."""
    import app.services.tool_service as ts

    mock_ws = AsyncMock()
    mock_ws.read_file.return_value = {
        "ok": True,
        "is_binary": False,
        "content": "hello world",
        "size_bytes": 11,
        "mime_type": "text/markdown",
        "file_path": "notes/hello.md",
    }

    with patch.dict(
        sys.modules,
        {"app.services.workspace_service": MagicMock(WorkspaceService=lambda token: mock_ws)},
    ):
        result = await ts._workspace_read_file_executor(
            arguments={"file_path": "notes/hello.md"},
            user_id="user-1",
            context={"thread_id": "t1", "token": "tok"},
        )

    assert result["ok"] is True
    assert result["is_binary"] is False
    assert result["content"] == "hello world"
    mock_ws.read_file.assert_awaited_once_with("t1", "notes/hello.md")


# ---------------------------------------------------------------------------
# 5. read_file executor — missing file returns file_not_found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_file_executor_not_found():
    """read_file returns file_not_found error when file does not exist."""
    import app.services.tool_service as ts

    mock_ws = AsyncMock()
    mock_ws.read_file.return_value = {
        "error": "file_not_found",
        "file_path": "missing.md",
    }

    with patch.dict(
        sys.modules,
        {"app.services.workspace_service": MagicMock(WorkspaceService=lambda token: mock_ws)},
    ):
        result = await ts._workspace_read_file_executor(
            arguments={"file_path": "missing.md"},
            user_id="user-1",
            context={"thread_id": "t1", "token": "tok"},
        )

    assert result["error"] == "file_not_found"


# ---------------------------------------------------------------------------
# 6. edit_file executor — successful edit (unique old_string)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_edit_file_executor_happy_path():
    """edit_file executor calls WorkspaceService.edit_file and returns ok."""
    import app.services.tool_service as ts

    mock_ws = AsyncMock()
    mock_ws.edit_file.return_value = {
        "ok": True,
        "operation": "update",
        "size_bytes": 15,
        "file_path": "notes/doc.md",
    }

    with patch.dict(
        sys.modules,
        {"app.services.workspace_service": MagicMock(WorkspaceService=lambda token: mock_ws)},
    ):
        result = await ts._workspace_edit_file_executor(
            arguments={
                "file_path": "notes/doc.md",
                "old_string": "hello",
                "new_string": "hello world",
            },
            user_id="user-1",
            context={"thread_id": "t1", "token": "tok"},
        )

    assert result["ok"] is True
    mock_ws.edit_file.assert_awaited_once_with("t1", "notes/doc.md", "hello", "hello world")


# ---------------------------------------------------------------------------
# 7. edit_file executor — ambiguous old_string returns error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_edit_file_executor_ambiguous():
    """edit_file returns edit_old_string_ambiguous when old_string appears > 1 time."""
    import app.services.tool_service as ts

    mock_ws = AsyncMock()
    mock_ws.edit_file.return_value = {
        "error": "edit_old_string_ambiguous",
        "occurrences": 3,
        "file_path": "notes/doc.md",
    }

    with patch.dict(
        sys.modules,
        {"app.services.workspace_service": MagicMock(WorkspaceService=lambda token: mock_ws)},
    ):
        result = await ts._workspace_edit_file_executor(
            arguments={
                "file_path": "notes/doc.md",
                "old_string": "foo",
                "new_string": "bar",
            },
            user_id="user-1",
            context={"thread_id": "t1", "token": "tok"},
        )

    assert result["error"] == "edit_old_string_ambiguous"
    assert result["occurrences"] == 3


# ---------------------------------------------------------------------------
# 8. list_files executor — returns structured ok dict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_files_executor_happy_path():
    """list_files executor wraps service list in {ok, files, count}."""
    import app.services.tool_service as ts

    file_list = [
        {"file_path": "notes/a.md", "size_bytes": 10, "source": "agent", "mime_type": "text/markdown", "updated_at": "2026-05-03T00:00:00Z"},
        {"file_path": "data/b.csv", "size_bytes": 200, "source": "sandbox", "mime_type": "text/csv", "updated_at": "2026-05-02T00:00:00Z"},
    ]
    mock_ws = AsyncMock()
    mock_ws.list_files.return_value = file_list

    with patch.dict(
        sys.modules,
        {"app.services.workspace_service": MagicMock(WorkspaceService=lambda token: mock_ws)},
    ):
        result = await ts._workspace_list_files_executor(
            arguments={},
            user_id="user-1",
            context={"thread_id": "t1", "token": "tok"},
        )

    assert result["ok"] is True
    assert result["count"] == 2
    assert len(result["files"]) == 2
    mock_ws.list_files.assert_awaited_once_with("t1")


# ---------------------------------------------------------------------------
# 9. WORKSPACE_ENABLED=False — tools absent from _REGISTRY
# ---------------------------------------------------------------------------

def test_workspace_enabled_false_unregisters(monkeypatch):
    """With WORKSPACE_ENABLED=False, workspace tools must NOT be in the registry."""
    # We need to reload modules with the flag set to false.
    # Save originals so we can restore.
    original_modules = {}
    for key in ["app.config", "app.services.tool_service",
                "app.services.tool_registry", "app.services.workspace_service"]:
        if key in sys.modules:
            original_modules[key] = sys.modules.pop(key)

    try:
        monkeypatch.setenv("TOOL_REGISTRY_ENABLED", "true")
        monkeypatch.setenv("WORKSPACE_ENABLED", "false")
        # Required env vars so Settings doesn't raise
        monkeypatch.setenv("SUPABASE_URL", "https://dummy.supabase.co")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "dummy_anon_key")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "dummy_svc_key")
        monkeypatch.setenv("OPENAI_API_KEY", "dummy_openai_key")

        import app.services.tool_registry as registry
        registry._REGISTRY.clear()
        registry._register_tool_search()

        import app.services.tool_service  # triggers _register_workspace_tools

        for name in ["write_file", "read_file", "edit_file", "list_files"]:
            assert name not in registry._REGISTRY, (
                f"{name} should NOT be registered when WORKSPACE_ENABLED=false"
            )
    finally:
        # Restore original modules
        for key in ["app.config", "app.services.tool_service",
                    "app.services.tool_registry", "app.services.workspace_service"]:
            sys.modules.pop(key, None)
        sys.modules.update(original_modules)


# ---------------------------------------------------------------------------
# 10. WORKSPACE_ENABLED=True — all four tools present in _REGISTRY
# ---------------------------------------------------------------------------

def test_workspace_enabled_true_registers(monkeypatch):
    """With WORKSPACE_ENABLED=True (and TOOL_REGISTRY_ENABLED=True), all 4 tools registered."""
    original_modules = {}
    for key in ["app.config", "app.services.tool_service",
                "app.services.tool_registry", "app.services.workspace_service"]:
        if key in sys.modules:
            original_modules[key] = sys.modules.pop(key)

    try:
        monkeypatch.setenv("TOOL_REGISTRY_ENABLED", "true")
        monkeypatch.setenv("WORKSPACE_ENABLED", "true")
        monkeypatch.setenv("SUPABASE_URL", "https://dummy.supabase.co")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "dummy_anon_key")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "dummy_svc_key")
        monkeypatch.setenv("OPENAI_API_KEY", "dummy_openai_key")

        import app.services.tool_registry as registry
        registry._REGISTRY.clear()
        registry._register_tool_search()

        import app.services.tool_service  # triggers _register_workspace_tools

        for name in ["write_file", "read_file", "edit_file", "list_files"]:
            assert name in registry._REGISTRY, (
                f"{name} MUST be registered when WORKSPACE_ENABLED=true"
            )
    finally:
        for key in ["app.config", "app.services.tool_service",
                    "app.services.tool_registry", "app.services.workspace_service"]:
            sys.modules.pop(key, None)
        sys.modules.update(original_modules)


# ---------------------------------------------------------------------------
# 11. Schema conformance — OpenAI tool-call format
# ---------------------------------------------------------------------------

def test_workspace_tool_schemas_conform_to_openai_format():
    """All four registered workspace tool schemas have required OpenAI structure."""
    import app.services.tool_service as ts  # ensure tools are registered
    from app.services import tool_registry

    workspace_tool_names = ["write_file", "read_file", "edit_file", "list_files"]

    for name in workspace_tool_names:
        if name not in tool_registry._REGISTRY:
            # If workspace tools aren't registered (WORKSPACE_ENABLED=false in env),
            # check the schema constants directly from tool_service
            schema_attr = f"_WORKSPACE_{name.upper().replace('_', '_')}_SCHEMA"
            # Map names to schema constants
            schema_map = {
                "write_file": ts._WORKSPACE_WRITE_FILE_SCHEMA,
                "read_file": ts._WORKSPACE_READ_FILE_SCHEMA,
                "edit_file": ts._WORKSPACE_EDIT_FILE_SCHEMA,
                "list_files": ts._WORKSPACE_LIST_FILES_SCHEMA,
            }
            schema = schema_map[name]
        else:
            schema = tool_registry._REGISTRY[name].schema

        assert schema["type"] == "function", (
            f"{name} schema must have type='function'"
        )
        fn = schema["function"]
        assert fn["name"] == name, (
            f"{name} schema function.name must equal '{name}'"
        )
        params = fn.get("parameters", {})
        assert params.get("type") == "object", (
            f"{name} schema parameters.type must be 'object'"
        )
        assert "properties" in params, (
            f"{name} schema parameters must have 'properties'"
        )
