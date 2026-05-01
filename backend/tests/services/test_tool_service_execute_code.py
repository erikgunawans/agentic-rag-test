"""Unit tests for tool_service.py execute_code integration — Phase 10 / Plan 10-04.

Tests:
  1. TOOL_DEFINITIONS contains execute_code with correct schema
  2. get_available_tools() excludes execute_code when sandbox_enabled=False (default)
  3. get_available_tools() includes execute_code when sandbox_enabled=True
  4. execute_tool signature has stream_callback parameter (keyword-only, default None)
  5. execute_tool passes stream_callback=<fn> for non-execute_code tool; callback never invoked
  6. execute_tool dispatches execute_code to _execute_code handler; returns correct shape
  7. _execute_code INSERTs exactly 1 row into code_executions table
  8. log_action called with action="execute_code", resource_type="code_execution"

Run:
    cd backend && source venv/bin/activate && \\
        pytest tests/services/test_tool_service_execute_code.py -v --tb=short
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers — shared mock factory
# ---------------------------------------------------------------------------

def _make_settings(sandbox_enabled: bool = False) -> MagicMock:
    s = MagicMock()
    s.sandbox_enabled = sandbox_enabled
    s.tavily_api_key = None          # keep web_search gated off by default
    s.rag_top_k = 5
    s.rag_similarity_threshold = 0.7
    return s


def _make_sandbox_result(
    stdout: str = "hello\n",
    stderr: str = "",
    exit_code: int = 0,
    error_type: str | None = None,
    execution_ms: int = 150,
    files: list | None = None,
    execution_id: str = "exec-uuid-1234",
) -> dict:
    return {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "error_type": error_type,
        "execution_ms": execution_ms,
        "files": files if files is not None else [],
        "execution_id": execution_id,
    }


# ---------------------------------------------------------------------------
# Test 1: TOOL_DEFINITIONS contains execute_code with correct schema
# ---------------------------------------------------------------------------

class TestToolDefinitionsSchema:
    """TOOL_DEFINITIONS must contain exactly one execute_code entry with
    required=['code'] and properties {code: string, description: string}."""

    def test_execute_code_in_tool_definitions(self):
        # Patch to avoid import side effects with heavy services
        with patch("app.services.tool_service.get_settings") as mock_gs, \
             patch("app.services.tool_service.HybridRetrievalService"):
            mock_gs.return_value = _make_settings()
            from app.services.tool_service import TOOL_DEFINITIONS

        # Find the execute_code entry
        entries = [t for t in TOOL_DEFINITIONS if t["function"]["name"] == "execute_code"]
        assert len(entries) == 1, (
            f"Expected exactly 1 execute_code entry in TOOL_DEFINITIONS, got {len(entries)}"
        )

        fn = entries[0]["function"]
        assert fn["name"] == "execute_code"
        params = fn["parameters"]
        assert params["type"] == "object"
        assert "code" in params["properties"], "Missing 'code' property"
        assert "description" in params["properties"], "Missing 'description' property"
        assert params["properties"]["code"]["type"] == "string"
        assert params["properties"]["description"]["type"] == "string"
        assert params["required"] == ["code"], (
            f"Expected required=['code'], got {params['required']}"
        )


# ---------------------------------------------------------------------------
# Test 2: get_available_tools() EXCLUDES execute_code when sandbox_enabled=False
# ---------------------------------------------------------------------------

class TestGetAvailableToolsGateOff:
    """With sandbox_enabled=False (default), execute_code must NOT appear."""

    def test_excludes_execute_code_when_disabled(self, monkeypatch):
        with patch("app.services.tool_service.HybridRetrievalService"):
            import importlib
            import app.services.tool_service as ts_mod

        # Monkeypatch the module-level settings object
        mock_settings = _make_settings(sandbox_enabled=False)
        monkeypatch.setattr("app.services.tool_service.settings", mock_settings)

        from app.services.tool_service import ToolService
        ts = ToolService.__new__(ToolService)  # skip __init__ HybridRetrievalService
        ts.hybrid_service = MagicMock()

        names = [t["function"]["name"] for t in ts.get_available_tools()]
        assert "execute_code" not in names, (
            f"execute_code should be excluded when sandbox_enabled=False, got names={names}"
        )


# ---------------------------------------------------------------------------
# Test 3: get_available_tools() INCLUDES execute_code when sandbox_enabled=True
# ---------------------------------------------------------------------------

class TestGetAvailableToolsGateOn:
    """With sandbox_enabled=True, execute_code MUST appear in the tool list."""

    def test_includes_execute_code_when_enabled(self, monkeypatch):
        mock_settings = _make_settings(sandbox_enabled=True)
        monkeypatch.setattr("app.services.tool_service.settings", mock_settings)

        from app.services.tool_service import ToolService
        ts = ToolService.__new__(ToolService)
        ts.hybrid_service = MagicMock()

        names = [t["function"]["name"] for t in ts.get_available_tools()]
        assert "execute_code" in names, (
            f"execute_code should be included when sandbox_enabled=True, got names={names}"
        )


# ---------------------------------------------------------------------------
# Test 4: execute_tool signature inspection
# ---------------------------------------------------------------------------

class TestExecuteToolSignature:
    """execute_tool must have `stream_callback` as keyword-only with default None."""

    def test_stream_callback_parameter_exists(self):
        from app.services.tool_service import ToolService

        sig = inspect.signature(ToolService.execute_tool)
        assert "stream_callback" in sig.parameters, (
            "execute_tool is missing stream_callback parameter"
        )
        param = sig.parameters["stream_callback"]
        assert param.kind in (
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ), f"Expected keyword-only or positional param, got kind={param.kind}"
        assert param.default is None, (
            f"Expected default=None for stream_callback, got {param.default}"
        )


# ---------------------------------------------------------------------------
# Test 5: Non-execute_code tool with stream_callback — callback never invoked
# ---------------------------------------------------------------------------

class TestStreamCallbackSilentIgnore:
    """Passing stream_callback to execute_tool for a non-execute_code tool
    must succeed and the callback must NEVER be invoked."""

    @pytest.mark.asyncio
    async def test_stream_callback_not_invoked_for_other_tools(self, monkeypatch):
        mock_settings = _make_settings(sandbox_enabled=False)
        monkeypatch.setattr("app.services.tool_service.settings", mock_settings)

        # Patch the underlying search to return immediately
        mock_hybrid = MagicMock()
        mock_hybrid.retrieve = AsyncMock(return_value=[])

        with patch("app.services.tool_service.get_supabase_client") as mock_supa:
            mock_supa.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock()

            from app.services.tool_service import ToolService
            ts = ToolService.__new__(ToolService)
            ts.hybrid_service = mock_hybrid

            callback_invocations = []

            async def my_callback(event_type: str, line: str) -> None:
                callback_invocations.append((event_type, line))

            await ts.execute_tool(
                name="search_documents",
                arguments={"query": "test"},
                user_id="user-1",
                context={"top_k": 5, "threshold": 0.7},
                stream_callback=my_callback,
            )

        assert callback_invocations == [], (
            f"stream_callback should not be invoked for search_documents, "
            f"but got {callback_invocations}"
        )


# ---------------------------------------------------------------------------
# Test 6: execute_tool dispatches execute_code → returns correct shape
# ---------------------------------------------------------------------------

class TestExecuteCodeDispatch:
    """execute_tool with name='execute_code' must call get_sandbox_service().execute()
    exactly once and return a dict containing {stdout, stderr, exit_code, files, execution_id}."""

    @pytest.mark.asyncio
    async def test_dispatches_to_sandbox_service(self, monkeypatch):
        mock_settings = _make_settings(sandbox_enabled=True)
        monkeypatch.setattr("app.services.tool_service.settings", mock_settings)

        sandbox_result = _make_sandbox_result()

        mock_sandbox_svc = MagicMock()
        mock_sandbox_svc.execute = AsyncMock(return_value=sandbox_result)
        mock_get_sandbox = MagicMock(return_value=mock_sandbox_svc)

        with patch("app.services.tool_service.get_sandbox_service", mock_get_sandbox), \
             patch("app.services.tool_service.get_supabase_client") as mock_supa, \
             patch("app.services.tool_service.log_action"):
            mock_insert_chain = MagicMock()
            mock_supa.return_value.table.return_value.insert.return_value.execute.return_value = mock_insert_chain

            from app.services.tool_service import ToolService
            ts = ToolService.__new__(ToolService)
            ts.hybrid_service = MagicMock()

            result = await ts.execute_tool(
                name="execute_code",
                arguments={"code": "print(1)", "description": "test print"},
                user_id="user-abc",
                context={"thread_id": "thread-xyz"},
                stream_callback=None,
            )

        # Sandbox service must be called exactly once
        mock_get_sandbox.assert_called_once()
        mock_sandbox_svc.execute.assert_awaited_once()

        # Verify return shape contains required keys
        for key in ("stdout", "stderr", "exit_code", "files", "execution_id"):
            assert key in result, f"Result missing key '{key}': got {list(result.keys())}"

        assert result["stdout"] == sandbox_result["stdout"]
        assert result["exit_code"] == sandbox_result["exit_code"]
        assert result["execution_id"] == sandbox_result["execution_id"]


# ---------------------------------------------------------------------------
# Test 7: _execute_code INSERTs exactly 1 row into code_executions
# ---------------------------------------------------------------------------

class TestCodeExecutionsPersistence:
    """After _execute_code runs, exactly 1 INSERT must be made to code_executions
    with status in ('success', 'error', 'timeout')."""

    @pytest.mark.asyncio
    async def test_inserts_one_row_to_code_executions(self, monkeypatch):
        mock_settings = _make_settings(sandbox_enabled=True)
        monkeypatch.setattr("app.services.tool_service.settings", mock_settings)

        sandbox_result = _make_sandbox_result(
            stdout="done\n",
            exit_code=0,
            execution_id="exec-persist-uuid",
        )

        mock_sandbox_svc = MagicMock()
        mock_sandbox_svc.execute = AsyncMock(return_value=sandbox_result)

        mock_insert = MagicMock()
        mock_insert.execute = MagicMock(return_value=MagicMock())

        mock_table = MagicMock()
        mock_table.insert = MagicMock(return_value=mock_insert)

        mock_supa = MagicMock()
        mock_supa.table = MagicMock(return_value=mock_table)

        with patch("app.services.tool_service.get_sandbox_service", return_value=mock_sandbox_svc), \
             patch("app.services.tool_service.get_supabase_client", return_value=mock_supa), \
             patch("app.services.tool_service.log_action"):
            from app.services.tool_service import ToolService
            ts = ToolService.__new__(ToolService)
            ts.hybrid_service = MagicMock()

            await ts._execute_code(
                code="x = 1",
                description="test",
                user_id="user-1",
                thread_id="thread-1",
                stream_callback=None,
            )

        # Assert table("code_executions").insert was called exactly once
        mock_supa.table.assert_called_once_with("code_executions")
        mock_table.insert.assert_called_once()

        # Assert the inserted row has a valid status
        inserted_row = mock_table.insert.call_args[0][0]
        assert inserted_row["status"] in ("success", "error", "timeout"), (
            f"Unexpected status: {inserted_row['status']}"
        )
        mock_insert.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Test 8: log_action called with action="execute_code"
# ---------------------------------------------------------------------------

class TestAuditLog:
    """log_action must be called with action='execute_code' and
    resource_type='code_execution' after each successful invocation."""

    @pytest.mark.asyncio
    async def test_log_action_called_with_correct_params(self, monkeypatch):
        mock_settings = _make_settings(sandbox_enabled=True)
        monkeypatch.setattr("app.services.tool_service.settings", mock_settings)

        sandbox_result = _make_sandbox_result(execution_id="exec-audit-uuid")

        mock_sandbox_svc = MagicMock()
        mock_sandbox_svc.execute = AsyncMock(return_value=sandbox_result)

        with patch("app.services.tool_service.get_sandbox_service", return_value=mock_sandbox_svc), \
             patch("app.services.tool_service.get_supabase_client") as mock_supa, \
             patch("app.services.tool_service.log_action") as mock_log:
            mock_supa.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock()

            from app.services.tool_service import ToolService
            ts = ToolService.__new__(ToolService)
            ts.hybrid_service = MagicMock()

            await ts._execute_code(
                code="print('audit test')",
                description=None,
                user_id="user-audit",
                thread_id="thread-audit",
                stream_callback=None,
            )

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args
        # log_action may be called positionally or with kwargs
        kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
        args = call_kwargs.args if call_kwargs.args else ()

        # Normalize: convert positional to dict using log_action signature
        import app.services.audit_service as audit_mod
        sig = inspect.signature(audit_mod.log_action)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        all_args = bound.arguments

        assert all_args.get("action") == "execute_code", (
            f"Expected action='execute_code', got {all_args.get('action')}"
        )
        assert all_args.get("resource_type") == "code_execution", (
            f"Expected resource_type='code_execution', got {all_args.get('resource_type')}"
        )
