"""Phase 18 Plan 06 / WS-10: workspace_updated SSE event tests.

Tests that the workspace_updated SSE event is emitted correctly from the chat-loop
when write_file or edit_file tools succeed, and that it is NOT emitted for read-only
tools or when WORKSPACE_ENABLED=False.

Coverage:
  Test 1: write_file tool call produces workspace_updated SSE event with correct payload.
  Test 2: WORKSPACE_ENABLED=False — write_file does NOT produce workspace_updated events.
  Test 3: read-only tool (list_files) does NOT produce workspace_updated events.

Design notes:
  - Mirrors the Phase 5 integration test harness (test_phase5_integration.py):
    patch app.routers.chat.settings, mock complete_with_tools, mock DB via Supabase stub.
  - Workspace tool executors are mocked via patch to avoid live DB connections.
  - The test drives the standard _run_tool_loop path (not deep-mode or test-skeleton).
  - tool_registry_enabled=True so workspace tools are dispatched via the registry executor.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_current_user
from app.main import app

# ──────────────────────────── Constants ────────────────────────────────────

_TEST_USER_ID = "00000000-0000-0000-0000-workspace001"
_TEST_USER_EMAIL = "test@test.com"
_FAKE_TOKEN = "test-token-workspace-sse"
_THREAD_ID = "workspace-sse-thread-001"

# Minimal system_settings mock (matches what chat.py reads from get_system_settings).
_MOCK_SYS_SETTINGS = {
    "llm_model": "openai/gpt-4o-mini",
    "embedding_model": "text-embedding-3-small",
    "custom_embedding_model": None,
    "pii_redaction_enabled": False,  # OFF — keep test simple (no anonymization)
}


# ──────────────────────────── Helpers ──────────────────────────────────────


def _make_settings(*, workspace_enabled: bool = True, tool_registry_enabled: bool = True) -> SimpleNamespace:
    """Build a Settings stub with workspace_enabled flag set as requested."""
    real = get_settings()
    overrides = {f: getattr(real, f) for f in real.model_dump().keys()}
    overrides["workspace_enabled"] = workspace_enabled
    overrides["tool_registry_enabled"] = tool_registry_enabled
    overrides["tools_enabled"] = True
    overrides["tools_max_iterations"] = 2
    overrides["max_tool_rounds"] = 2
    overrides["agents_enabled"] = False
    overrides["sandbox_enabled"] = False
    overrides["deep_mode_enabled"] = False
    return SimpleNamespace(**overrides)


def _make_supabase_stub(thread_id: str) -> MagicMock:
    """Minimal Supabase client stub for chat.py DB calls (mirrors Phase 5 pattern)."""
    client = MagicMock()

    def _make_chain(table_name: str, op: str = "select"):
        chain_stub = MagicMock()
        chain_stub._op = op

        def _execute():
            if table_name == "threads":
                return MagicMock(data=[{"id": thread_id, "title": "Test Thread"}])
            elif table_name == "messages":
                if op == "insert":
                    return MagicMock(data=[{"id": "msg-001"}])
                else:
                    return MagicMock(data=[])
            return MagicMock(data=[])

        chain_stub.execute = _execute

        def _insert(*a, **kw):
            return _make_chain(table_name, "insert")

        def _update(*a, **kw):
            return _make_chain(table_name, "update")

        def _passthrough(*a, **kw):
            return _make_chain(table_name, op)

        chain_stub.select = _passthrough
        chain_stub.eq = _passthrough
        chain_stub.order = _passthrough
        chain_stub.limit = _passthrough
        chain_stub.single = _passthrough
        chain_stub.insert = _insert
        chain_stub.update = _update
        chain_stub.delete = _passthrough
        return chain_stub

    def _table_factory(table_name: str):
        tbl = MagicMock()
        tbl.select = lambda *a, **kw: _make_chain(table_name, "select")
        tbl.insert = lambda *a, **kw: _make_chain(table_name, "insert")
        tbl.update = lambda *a, **kw: _make_chain(table_name, "update")
        tbl.delete = lambda *a, **kw: _make_chain(table_name, "select")
        tbl.eq = lambda *a, **kw: _make_chain(table_name, "select")
        return tbl

    client.table = _table_factory
    return client


def _consume_sse(response) -> list[dict]:
    """Parse SSE response into list of event dicts (strips data: prefix)."""
    events: list[dict] = []
    for raw_line in response.iter_lines():
        line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8")
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                continue
    return events


# ──────────────────────────── Fixtures ─────────────────────────────────────


@pytest.fixture(autouse=True)
def _auth_override():
    """Bypass FastAPI get_current_user dependency for all workspace SSE tests."""
    async def _fake_current_user():
        return {
            "id": _TEST_USER_ID,
            "email": _TEST_USER_EMAIL,
            "token": _FAKE_TOKEN,
            "role": "user",
        }

    app.dependency_overrides[get_current_user] = _fake_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _clear_llm_client_cache():
    """Reset the AsyncOpenAI client cache between tests."""
    from app.services import llm_provider

    if hasattr(llm_provider, "_clients"):
        llm_provider._clients.clear()
    yield
    if hasattr(llm_provider, "_clients"):
        llm_provider._clients.clear()


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset tool registry to clean state before each test."""
    from app.services import tool_registry

    tool_registry._clear_for_tests()
    yield
    tool_registry._clear_for_tests()


# ──────────────────────────── Tests ────────────────────────────────────────



# ──────────────────────────── Mock tool schema helpers ─────────────────────

# OpenAI-compatible tool schema for write_file
_WRITE_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Create or overwrite a workspace text file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["file_path", "content"],
        },
    },
}

# OpenAI-compatible tool schema for list_files
_LIST_FILES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "List all workspace files.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def _make_registry_entry(executor, schema: dict) -> MagicMock:
    """Build a ToolDefinition-like mock with correct schema + executor fields."""
    entry = MagicMock()
    entry.executor = executor
    entry.loading = "immediate"
    entry.source = "native"
    entry.available = True
    entry.schema = schema
    entry.name = schema["function"]["name"]
    return entry


class TestWorkspaceSSEEvents:
    """WS-10: workspace_updated SSE events from the chat-loop."""

    def test_write_file_emits_workspace_updated(self):
        """WS-10 / Test 1: write_file tool call produces a workspace_updated SSE event.

        Drives the standard _run_tool_loop path (tool_registry_enabled=True).
        Mocks complete_with_tools to return a write_file tool call (round 1),
        then a final text response (round 2).
        Mocks the workspace tool executor to return ok=True without hitting DB.
        Asserts at least one workspace_updated event in the SSE stream.
        """
        thread_id = _THREAD_ID
        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _make_settings(workspace_enabled=True, tool_registry_enabled=True)

        # write_file tool call return shape (from WorkspaceService.write_file)
        write_file_result = {
            "ok": True,
            "file_path": "notes/auto.md",
            "operation": "create",
            "size_bytes": 5,
        }

        call_count = 0

        async def _mock_complete_with_tools(messages, tools, *, model=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Round 1: return write_file tool call
                return {
                    "tool_calls": [{
                        "id": "tc-ws-01",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps({
                                "file_path": "notes/auto.md",
                                "content": "hello",
                            }),
                        },
                    }],
                    "content": None,
                    "usage": None,
                }
            else:
                # Round 2: final answer (no more tool calls)
                return {
                    "tool_calls": [],
                    "content": "Done — wrote notes/auto.md.",
                    "usage": None,
                }

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Done — wrote notes/auto.md.", "done": False}
            yield {"delta": "", "done": True}

        # Mock the workspace write_file executor to return ok=True without DB.
        async def _mock_write_file_executor(arguments, user_id, context=None, *, token=None, **kwargs):
            return write_file_result

        mock_registry = {
            "write_file": _make_registry_entry(_mock_write_file_executor, _WRITE_FILE_SCHEMA),
        }

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings", return_value=_MOCK_SYS_SETTINGS),
            patch("app.services.openrouter_service.OpenRouterService.complete_with_tools",
                  side_effect=_mock_complete_with_tools),
            patch("app.services.openrouter_service.OpenRouterService.stream_response",
                  side_effect=_mock_stream_response),
            # Patch the registry and build_llm_tools so write_file appears in available_tool_names.
            patch("app.services.tool_registry._REGISTRY", mock_registry),
            patch("app.services.tool_registry.build_llm_tools", return_value=[_WRITE_FILE_SCHEMA]),
            patch("app.services.tool_registry.build_catalog_block", return_value=""),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={
                    "thread_id": thread_id,
                    "message": "Write a note",
                },
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            events = _consume_sse(response)

        workspace_events = [e for e in events if e.get("type") == "workspace_updated"]
        assert len(workspace_events) >= 1, (
            f"Expected at least 1 workspace_updated event; got 0. "
            f"All event types: {[e.get('type') for e in events]}"
        )
        evt = workspace_events[0]
        assert evt["file_path"] == "notes/auto.md", f"Expected file_path='notes/auto.md', got {evt.get('file_path')!r}"
        assert evt["operation"] in ("create", "update"), f"Expected operation create/update, got {evt.get('operation')!r}"
        assert evt["size_bytes"] == 5, f"Expected size_bytes=5, got {evt.get('size_bytes')!r}"
        assert evt["source"] == "agent", f"Expected source='agent', got {evt.get('source')!r}"
        assert evt["type"] == "workspace_updated", f"Expected type='workspace_updated', got {evt.get('type')!r}"

    def test_workspace_disabled_no_workspace_updated_events(self):
        """WS-10 / Test 2: WORKSPACE_ENABLED=False — no workspace_updated events emitted.

        When workspace_enabled=False in settings, the workspace_updated emission
        is gated and must not appear in the SSE stream.
        """
        thread_id = "workspace-sse-thread-002"
        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _make_settings(workspace_enabled=False, tool_registry_enabled=True)

        write_file_result = {
            "ok": True,
            "file_path": "notes/disabled.md",
            "operation": "create",
            "size_bytes": 7,
        }

        call_count = 0

        async def _mock_complete_with_tools(messages, tools, *, model=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "tool_calls": [{
                        "id": "tc-ws-02",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps({
                                "file_path": "notes/disabled.md",
                                "content": "testing",
                            }),
                        },
                    }],
                    "content": None,
                    "usage": None,
                }
            else:
                return {
                    "tool_calls": [],
                    "content": "Done.",
                    "usage": None,
                }

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Done.", "done": False}
            yield {"delta": "", "done": True}

        async def _mock_write_file_executor(arguments, user_id, context=None, *, token=None, **kwargs):
            return write_file_result

        mock_registry = {
            "write_file": _make_registry_entry(_mock_write_file_executor, _WRITE_FILE_SCHEMA),
        }

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings", return_value=_MOCK_SYS_SETTINGS),
            patch("app.services.openrouter_service.OpenRouterService.complete_with_tools",
                  side_effect=_mock_complete_with_tools),
            patch("app.services.openrouter_service.OpenRouterService.stream_response",
                  side_effect=_mock_stream_response),
            patch("app.services.tool_registry._REGISTRY", mock_registry),
            patch("app.services.tool_registry.build_llm_tools", return_value=[_WRITE_FILE_SCHEMA]),
            patch("app.services.tool_registry.build_catalog_block", return_value=""),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={
                    "thread_id": thread_id,
                    "message": "Write a note (workspace disabled)",
                },
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            events = _consume_sse(response)

        workspace_events = [e for e in events if e.get("type") == "workspace_updated"]
        assert len(workspace_events) == 0, (
            f"Expected 0 workspace_updated events when workspace_enabled=False; "
            f"got {len(workspace_events)}. Events: {workspace_events}"
        )

    def test_list_files_no_workspace_updated_events(self):
        """WS-10 / Test 3: read-only tool (list_files) does NOT produce workspace_updated events.

        list_files is a read operation and must never trigger workspace_updated SSE.
        """
        thread_id = "workspace-sse-thread-003"
        supabase_stub = _make_supabase_stub(thread_id)
        stub_settings = _make_settings(workspace_enabled=True, tool_registry_enabled=True)

        list_files_result = {
            "ok": True,
            "files": [
                {"file_path": "notes/existing.md", "size_bytes": 100, "source": "agent"},
            ],
            "count": 1,
        }

        call_count = 0

        async def _mock_complete_with_tools(messages, tools, *, model=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "tool_calls": [{
                        "id": "tc-ws-03",
                        "type": "function",
                        "function": {
                            "name": "list_files",
                            "arguments": json.dumps({}),
                        },
                    }],
                    "content": None,
                    "usage": None,
                }
            else:
                return {
                    "tool_calls": [],
                    "content": "Here are your workspace files.",
                    "usage": None,
                }

        async def _mock_stream_response(messages, *, model=None, **kwargs):
            yield {"delta": "Here are your workspace files.", "done": False}
            yield {"delta": "", "done": True}

        async def _mock_list_files_executor(arguments, user_id, context=None, *, token=None, **kwargs):
            return list_files_result

        mock_registry = {
            "list_files": _make_registry_entry(_mock_list_files_executor, _LIST_FILES_SCHEMA),
        }

        with (
            patch("app.routers.chat.settings", stub_settings),
            patch("app.routers.chat.get_supabase_client", return_value=supabase_stub),
            patch("app.services.system_settings_service.get_system_settings",
                  return_value=_MOCK_SYS_SETTINGS),
            patch("app.routers.chat.get_system_settings", return_value=_MOCK_SYS_SETTINGS),
            patch("app.services.openrouter_service.OpenRouterService.complete_with_tools",
                  side_effect=_mock_complete_with_tools),
            patch("app.services.openrouter_service.OpenRouterService.stream_response",
                  side_effect=_mock_stream_response),
            patch("app.services.tool_registry._REGISTRY", mock_registry),
            patch("app.services.tool_registry.build_llm_tools", return_value=[_LIST_FILES_SCHEMA]),
            patch("app.services.tool_registry.build_catalog_block", return_value=""),
        ):
            client = TestClient(app)
            response = client.post(
                "/chat/stream",
                json={
                    "thread_id": thread_id,
                    "message": "List my workspace files",
                },
                headers={"Authorization": f"Bearer {_FAKE_TOKEN}"},
            )
            events = _consume_sse(response)

        workspace_events = [e for e in events if e.get("type") == "workspace_updated"]
        assert len(workspace_events) == 0, (
            f"Expected 0 workspace_updated events for list_files (read-only); "
            f"got {len(workspace_events)}. Events: {workspace_events}"
        )
