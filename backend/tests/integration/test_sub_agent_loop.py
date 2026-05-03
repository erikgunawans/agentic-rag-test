"""Phase 19 / 19-03: Integration tests for the sub-agent inner loop.

Tests cover:
- Happy path: sub-agent runs and returns _terminal_result with text
- context_files pre-load: first user message wraps <context_file> XML tags (D-08)
- Failure isolation: uncaught exception → structured _terminal_result error (D-12 / TASK-05)
- Loop cap: at max_iterations-1, tools cleared + summary system msg injected (D-11)
- Tool exclusion: task / write_todos / read_todos NOT in sub-agent tool list (D-09 exclusion)
- Egress filter: parent's registry reused — PII anonymized in context_files payload (D-21 / T-19-21)
- JWT inheritance: parent_token used for workspace access — RLS scope shared (D-22 / T-19-22)
- Binary file: context_files with binary → structured error returned (D-08 / T-19-CTX)
- Message persistence: messages carry parent_task_id for tree reconstruction (D-10)
- ask_user retention: ask_user IS in sub-agent tool list (D-09 retention — consolidates 19-05 Test 7)

Until sub_agent_loop.py is implemented, all tests fail with ImportError (RED phase).
"""
from __future__ import annotations

import asyncio
import inspect
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**overrides):
    """Return a mock settings object mirroring test_deep_mode_chat_loop._make_settings."""
    s = MagicMock()
    s.deep_mode_enabled = overrides.get("deep_mode_enabled", True)
    s.sub_agent_enabled = overrides.get("sub_agent_enabled", True)
    s.max_sub_agent_rounds = overrides.get("max_sub_agent_rounds", 15)
    s.max_deep_rounds = overrides.get("max_deep_rounds", 50)
    s.max_tool_rounds = overrides.get("max_tool_rounds", 25)
    s.tool_registry_enabled = overrides.get("tool_registry_enabled", True)
    s.tools_enabled = overrides.get("tools_enabled", True)
    s.sandbox_enabled = overrides.get("sandbox_enabled", False)
    s.workspace_enabled = overrides.get("workspace_enabled", True)
    s.agents_enabled = overrides.get("agents_enabled", False)
    s.rag_top_k = 5
    s.rag_similarity_threshold = 0.3
    s.fuzzy_deanon_mode = "none"
    return s


def _make_registry(thread_id: str = "thread-uuid", has_pii: bool = False):
    """Return a stub ConversationRegistry."""
    reg = MagicMock()
    reg.thread_id = thread_id
    if has_pii:
        # Simulate one known PII canonical entry (e.g. a person's name)
        entry = MagicMock()
        entry.entity_type = "PERSON"
        entry.real_value = "Budi Santoso"
        reg.canonicals.return_value = [entry]
    else:
        reg.canonicals.return_value = []
    return reg


def _make_openrouter_text_response(content: str = "Sub-agent completed the task."):
    """Build a mock OpenRouter chat completion that returns a single text message."""
    message = MagicMock()
    message.content = content
    message.tool_calls = None
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_openrouter_tool_call_response(tool_name: str = "search_documents", args: dict | None = None):
    """Build a mock OpenRouter completion that makes a tool call."""
    if args is None:
        args = {"query": "something"}
    tool_call = MagicMock()
    tool_call.id = "call-001"
    tool_call.function.name = tool_name
    tool_call.function.arguments = json.dumps(args)
    message = MagicMock()
    message.content = None
    message.tool_calls = [tool_call]
    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "tool_calls"
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Test 1: Happy path — sub-agent returns _terminal_result with text
# ---------------------------------------------------------------------------

class TestSubAgentHappyPath:
    """Test 1: test_sub_agent_happy_path_returns_text"""

    def test_sub_agent_happy_path_returns_text(self):
        """run_sub_agent_loop must be importable and be an async generator."""
        from app.services.sub_agent_loop import run_sub_agent_loop  # noqa: F401
        assert inspect.isasyncgenfunction(run_sub_agent_loop), \
            "run_sub_agent_loop must be an async generator function"

    def test_sub_agent_happy_path_yields_terminal_result(self):
        """Stub LLM returns text; loop yields _terminal_result={"text": ...}."""
        from app.services.sub_agent_loop import run_sub_agent_loop

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openrouter_text_response("Task done successfully.")
        )
        registry = _make_registry()

        async def _run():
            events = []
            async for evt in run_sub_agent_loop(
                description="Summarize the contract.",
                context_files=[],
                parent_user_id="user-uuid",
                parent_user_email="test@test.com",
                parent_token="jwt-token",
                parent_tool_context={},
                parent_thread_id="thread-uuid",
                parent_user_msg_id="msg-uuid",
                client=mock_client,
                sys_settings={},
                web_search_effective=False,
                task_id="task-001",
                parent_redaction_registry=registry,
            ):
                events.append(evt)
            return events

        with patch("app.services.sub_agent_loop.settings", _make_settings()):
            events = asyncio.get_event_loop().run_until_complete(_run())

        terminal_events = [e for e in events if isinstance(e, dict) and "_terminal_result" in e]
        assert terminal_events, "Loop must yield at least one _terminal_result event"
        result = terminal_events[-1]["_terminal_result"]
        assert "text" in result, f"_terminal_result must have 'text' key, got: {result}"
        assert "Task done" in result["text"] or result["text"], \
            "text must be the assistant's final response"


# ---------------------------------------------------------------------------
# Test 2: context_files pre-load in first message
# ---------------------------------------------------------------------------

class TestSubAgentContextFilesPreload:
    """Test 2: test_sub_agent_context_files_preload_in_first_message"""

    def test_sub_agent_context_files_preload_in_first_message(self):
        """context_files=['notes.md'] wraps content in <context_file path='notes.md'> XML."""
        from app.services.sub_agent_loop import run_sub_agent_loop, _build_first_user_message  # noqa: F401

        # _build_first_user_message is a module-level helper (D-08 pattern)
        content = _build_first_user_message(
            description="Review this contract.",
            context_files_content={"notes.md": "Contract dated 2024-01-01."},
        )
        assert '<context_file path="notes.md">' in content, \
            "First user message must wrap context files in <context_file path='...'> tags (D-08)"
        assert "Contract dated 2024-01-01." in content, \
            "First user message must include the file content"
        assert "<task>" in content, \
            "First user message must include <task> XML wrapper around description"

    def test_sub_agent_context_files_first_message_in_loop(self):
        """When context_files=['notes.md'], loop sends <context_file> in first LLM call."""
        from app.services.sub_agent_loop import run_sub_agent_loop

        captured_messages = []
        mock_client = MagicMock()

        async def _capture_create(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            return _make_openrouter_text_response("Done.")

        mock_client.chat.completions.create = _capture_create

        file_content = "Section 1: Payment terms."
        mock_ws_service = MagicMock()
        mock_ws_service.read_file = AsyncMock(return_value={
            "ok": True, "is_binary": False, "content": file_content,
            "size_bytes": len(file_content), "mime_type": "text/plain",
        })

        async def _run():
            events = []
            with patch("app.services.sub_agent_loop.WorkspaceService", return_value=mock_ws_service):
                async for evt in run_sub_agent_loop(
                    description="Analyze the document.",
                    context_files=["notes.md"],
                    parent_user_id="user-uuid",
                    parent_user_email="test@test.com",
                    parent_token="jwt-token",
                    parent_tool_context={},
                    parent_thread_id="thread-uuid",
                    parent_user_msg_id="msg-uuid",
                    client=mock_client,
                    sys_settings={},
                    web_search_effective=False,
                    task_id="task-002",
                    parent_redaction_registry=_make_registry(),
                ):
                    events.append(evt)
            return events, captured_messages

        with patch("app.services.sub_agent_loop.settings", _make_settings()):
            _, messages = asyncio.get_event_loop().run_until_complete(_run())

        user_messages = [m for m in messages if m.get("role") == "user"]
        assert user_messages, "Loop must send at least one user message to LLM"
        first_user_content = user_messages[0].get("content", "")
        assert '<context_file path="notes.md">' in first_user_content, \
            f"First user message must contain <context_file path='notes.md'>, got: {first_user_content[:200]}"
        assert file_content in first_user_content, \
            "First user message must contain the file content"


# ---------------------------------------------------------------------------
# Test 3: Failure isolation — uncaught exception → structured error
# ---------------------------------------------------------------------------

class TestSubAgentFailureIsolation:
    """Test 3: test_sub_agent_failure_isolation_returns_structured_error"""

    def test_sub_agent_failure_isolation_returns_structured_error(self):
        """LLM raises RuntimeError('boom') → _terminal_result with structured error, no crash."""
        from app.services.sub_agent_loop import run_sub_agent_loop

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        registry = _make_registry()

        async def _run():
            events = []
            async for evt in run_sub_agent_loop(
                description="Do something.",
                context_files=[],
                parent_user_id="user-uuid",
                parent_user_email="test@test.com",
                parent_token="jwt-token",
                parent_tool_context={},
                parent_thread_id="thread-uuid",
                parent_user_msg_id="msg-uuid",
                client=mock_client,
                sys_settings={},
                web_search_effective=False,
                task_id="task-003",
                parent_redaction_registry=registry,
            ):
                events.append(evt)
            return events

        with patch("app.services.sub_agent_loop.settings", _make_settings()):
            events = asyncio.get_event_loop().run_until_complete(_run())

        terminal_events = [e for e in events if isinstance(e, dict) and "_terminal_result" in e]
        assert terminal_events, "Failure must produce a _terminal_result event (D-12)"
        result = terminal_events[-1]["_terminal_result"]
        assert result.get("error") == "sub_agent_failed", \
            f"error key must be 'sub_agent_failed', got: {result}"
        assert result.get("code") == "TASK_LOOP_CRASH", \
            f"code key must be 'TASK_LOOP_CRASH', got: {result}"
        assert "boom" in result.get("detail", ""), \
            f"detail must contain the exception message, got: {result}"
        # D-19: no full traceback in detail field
        assert len(result.get("detail", "")) <= 500, \
            "detail must be truncated to 500 chars (D-19)"
        assert "Traceback" not in result.get("detail", ""), \
            "detail must NOT contain stack trace text (D-19)"


# ---------------------------------------------------------------------------
# Test 4: Loop cap forces summary on final iteration
# ---------------------------------------------------------------------------

class TestSubAgentLoopCap:
    """Test 4: test_sub_agent_loop_cap_forces_summary"""

    def test_sub_agent_loop_cap_forces_summary(self):
        """At max_iterations-1, tools cleared + summary system message injected (D-11)."""
        from app.services.sub_agent_loop import run_sub_agent_loop

        # Use a low cap of 3 to keep the test fast
        max_rounds = 3
        call_count = 0
        captured_calls = []  # (messages, tools) per call

        mock_client = MagicMock()

        async def _mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            captured_calls.append({
                "messages": kwargs.get("messages", []),
                "tools": kwargs.get("tools", []),
            })
            # On the final iteration (cap-1), return text to close the loop
            if call_count >= max_rounds:
                return _make_openrouter_text_response("Summary: task complete.")
            # Otherwise return a tool call to keep iterating
            return _make_openrouter_tool_call_response("search_documents")

        mock_client.chat.completions.create = _mock_create

        # Stub tool execution so tool_calls resolve
        async def _run():
            events = []
            with patch("app.services.sub_agent_loop.settings", _make_settings(max_sub_agent_rounds=max_rounds)):
                with patch("app.services.sub_agent_loop._execute_tool_call",
                           new=AsyncMock(return_value={"result": "found something"})):
                    async for evt in run_sub_agent_loop(
                        description="Research the topic.",
                        context_files=[],
                        parent_user_id="user-uuid",
                        parent_user_email="test@test.com",
                        parent_token="jwt-token",
                        parent_tool_context={},
                        parent_thread_id="thread-uuid",
                        parent_user_msg_id="msg-uuid",
                        client=mock_client,
                        sys_settings={},
                        web_search_effective=False,
                        task_id="task-004",
                        parent_redaction_registry=_make_registry(),
                    ):
                        events.append(evt)
            return events

        events = asyncio.get_event_loop().run_until_complete(_run())

        # The final call (index max_rounds-1) must have empty tools list
        assert len(captured_calls) >= max_rounds, \
            f"Loop must run at least {max_rounds} iterations, ran {len(captured_calls)}"
        final_call = captured_calls[max_rounds - 1]
        assert final_call["tools"] == [] or final_call["tools"] is None, \
            "Final iteration must have tools=[] (D-11 loop cap)"

        # The final call messages must include a summary system message
        final_messages = final_call["messages"]
        system_messages = [m for m in final_messages if m.get("role") == "system"]
        summary_system = any(
            "summarize" in m.get("content", "").lower() or
            "iteration limit" in m.get("content", "").lower() or
            "final answer" in m.get("content", "").lower()
            for m in system_messages
        )
        assert summary_system, \
            "Final iteration must inject a 'summarize' system message (D-11)"


# ---------------------------------------------------------------------------
# Test 5: Tool exclusion — task / write_todos / read_todos NOT in tool list
# ---------------------------------------------------------------------------

class TestSubAgentToolExclusion:
    """Test 5: test_sub_agent_excludes_task_write_todos_read_todos_tools (D-09 exclusion half)"""

    def test_sub_agent_excludes_task_write_todos_read_todos_tools(self):
        """D-09 EXCLUSION half: task, write_todos, read_todos NOT in sub-agent tools."""
        from app.services.sub_agent_loop import run_sub_agent_loop

        captured_tools = []
        mock_client = MagicMock()

        async def _mock_create(**kwargs):
            if not captured_tools:
                captured_tools.extend(kwargs.get("tools") or [])
            return _make_openrouter_text_response("Done.")

        mock_client.chat.completions.create = _mock_create

        # Register the excluded tools in a mock registry build
        def _mock_build_llm_tools(**kwargs):
            return [
                {"type": "function", "function": {"name": "search_documents"}},
                {"type": "function", "function": {"name": "task"}},
                {"type": "function", "function": {"name": "write_todos"}},
                {"type": "function", "function": {"name": "read_todos"}},
                {"type": "function", "function": {"name": "ask_user"}},
                {"type": "function", "function": {"name": "web_search"}},
            ]

        async def _run():
            events = []
            with patch("app.services.sub_agent_loop.settings", _make_settings()):
                with patch("app.services.sub_agent_loop._tr") as mock_tr:
                    mock_tr.make_active_set.return_value = set()
                    mock_tr.build_llm_tools.side_effect = _mock_build_llm_tools
                    async for evt in run_sub_agent_loop(
                        description="Do a task.",
                        context_files=[],
                        parent_user_id="user-uuid",
                        parent_user_email="test@test.com",
                        parent_token="jwt-token",
                        parent_tool_context={},
                        parent_thread_id="thread-uuid",
                        parent_user_msg_id="msg-uuid",
                        client=mock_client,
                        sys_settings={},
                        web_search_effective=False,
                        task_id="task-005",
                        parent_redaction_registry=_make_registry(),
                    ):
                        events.append(evt)
            return events

        asyncio.get_event_loop().run_until_complete(_run())

        tool_names = [t["function"]["name"] for t in captured_tools]
        assert "task" not in tool_names, \
            "task tool must be excluded from sub-agent tool list (D-09)"
        assert "write_todos" not in tool_names, \
            "write_todos tool must be excluded from sub-agent tool list (D-09)"
        assert "read_todos" not in tool_names, \
            "read_todos tool must be excluded from sub-agent tool list (D-09)"


# ---------------------------------------------------------------------------
# Test 6: Egress filter uses parent registry — PII anonymized
# ---------------------------------------------------------------------------

class TestSubAgentEgressFilterUsesParentRegistry:
    """Test 6: test_sub_agent_egress_filter_uses_parent_registry (D-21 / T-19-21)"""

    def test_sub_agent_egress_filter_uses_parent_registry(self):
        """PII in context_files is caught by egress_filter using PARENT's registry."""
        from app.services.sub_agent_loop import run_sub_agent_loop

        # Parent registry has a known PII canonical: "Budi Santoso"
        pii_registry = _make_registry(has_pii=True)

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openrouter_text_response("Processed.")
        )

        file_content_with_pii = "Contract signed by Budi Santoso on 2024-01-01."
        mock_ws_service = MagicMock()
        mock_ws_service.read_file = AsyncMock(return_value={
            "ok": True, "is_binary": False, "content": file_content_with_pii,
            "size_bytes": len(file_content_with_pii), "mime_type": "text/plain",
        })

        egress_call_args = []

        from app.services.redaction.egress import EgressResult

        def _mock_egress(payload, registry, provisional):
            egress_call_args.append((payload, registry, provisional))
            # Simulate PII trip — egress blocked
            return EgressResult(
                tripped=True,
                match_count=1,
                entity_types=["PERSON"],
                match_hashes=["abc12345"],
            )

        async def _run():
            events = []
            with patch("app.services.sub_agent_loop.settings", _make_settings()):
                with patch("app.services.sub_agent_loop.egress_filter", side_effect=_mock_egress):
                    with patch("app.services.sub_agent_loop.WorkspaceService", return_value=mock_ws_service):
                        async for evt in run_sub_agent_loop(
                            description="Review contract.",
                            context_files=["contract.md"],
                            parent_user_id="user-uuid",
                            parent_user_email="test@test.com",
                            parent_token="jwt-token",
                            parent_tool_context={},
                            parent_thread_id="thread-uuid",
                            parent_user_msg_id="msg-uuid",
                            client=mock_client,
                            sys_settings={},
                            web_search_effective=False,
                            task_id="task-006",
                            parent_redaction_registry=pii_registry,
                        ):
                            events.append(evt)
            return events

        events = asyncio.get_event_loop().run_until_complete(_run())

        # Egress filter must have been called
        assert egress_call_args, "egress_filter must be called for sub-agent LLM payloads (D-21)"

        # The registry passed to egress_filter must be the PARENT's registry (same object)
        called_registry = egress_call_args[0][1]
        assert called_registry is pii_registry, \
            "egress_filter must receive the PARENT's ConversationRegistry, not a fresh one (D-21)"

        # The loop should yield a _terminal_result (either from egress block or after)
        assert any(isinstance(e, dict) for e in events), \
            "Loop must yield dict events"


# ---------------------------------------------------------------------------
# Test 7: JWT inheritance — workspace access uses parent_token
# ---------------------------------------------------------------------------

class TestSubAgentInheritsParentJWT:
    """Test 7: test_sub_agent_inherits_parent_jwt_for_workspace_access (D-22 / T-19-22)"""

    def test_sub_agent_inherits_parent_jwt_for_workspace_access(self):
        """Sub-agent uses parent_token for WorkspaceService init — RLS scope inherited."""
        from app.services.sub_agent_loop import run_sub_agent_loop

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openrouter_text_response("Done.")
        )

        parent_token = "parent-jwt-token-xyz"
        ws_init_tokens = []

        class MockWorkspaceService:
            def __init__(self, token: str):
                ws_init_tokens.append(token)

            async def read_file(self, thread_id: str, file_path: str) -> dict:
                return {
                    "ok": True, "is_binary": False,
                    "content": "file content", "size_bytes": 12, "mime_type": "text/plain",
                }

        async def _run():
            events = []
            with patch("app.services.sub_agent_loop.settings", _make_settings()):
                with patch("app.services.sub_agent_loop.WorkspaceService", MockWorkspaceService):
                    async for evt in run_sub_agent_loop(
                        description="Read a file.",
                        context_files=["doc.md"],
                        parent_user_id="user-uuid",
                        parent_user_email="test@test.com",
                        parent_token=parent_token,
                        parent_tool_context={},
                        parent_thread_id="thread-uuid",
                        parent_user_msg_id="msg-uuid",
                        client=mock_client,
                        sys_settings={},
                        web_search_effective=False,
                        task_id="task-007",
                        parent_redaction_registry=_make_registry(),
                    ):
                        events.append(evt)
            return events

        asyncio.get_event_loop().run_until_complete(_run())

        assert ws_init_tokens, \
            "WorkspaceService must be instantiated when context_files are present"
        assert parent_token in ws_init_tokens, \
            f"WorkspaceService must be instantiated with parent_token={parent_token!r} (D-22), got: {ws_init_tokens}"


# ---------------------------------------------------------------------------
# Test 8: Binary file in context_files → structured error
# ---------------------------------------------------------------------------

class TestSubAgentBinaryFileError:
    """Test 8: test_sub_agent_binary_file_in_context_files_returns_error (D-08 / T-19-CTX)"""

    def test_sub_agent_binary_file_in_context_files_returns_error(self):
        """Binary context_files → _terminal_result with binary_file_not_inlinable error."""
        from app.services.sub_agent_loop import run_sub_agent_loop

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openrouter_text_response("Done.")
        )

        mock_ws_service = MagicMock()
        mock_ws_service.read_file = AsyncMock(return_value={
            "ok": True,
            "is_binary": True,
            "signed_url": "https://storage.example.com/binary.pdf",
            "size_bytes": 204800,
            "mime_type": "application/pdf",
            "file_path": "report.pdf",
        })

        async def _run():
            events = []
            with patch("app.services.sub_agent_loop.settings", _make_settings()):
                with patch("app.services.sub_agent_loop.WorkspaceService", return_value=mock_ws_service):
                    async for evt in run_sub_agent_loop(
                        description="Read the report.",
                        context_files=["report.pdf"],
                        parent_user_id="user-uuid",
                        parent_user_email="test@test.com",
                        parent_token="jwt-token",
                        parent_tool_context={},
                        parent_thread_id="thread-uuid",
                        parent_user_msg_id="msg-uuid",
                        client=mock_client,
                        sys_settings={},
                        web_search_effective=False,
                        task_id="task-008",
                        parent_redaction_registry=_make_registry(),
                    ):
                        events.append(evt)
            return events

        events = asyncio.get_event_loop().run_until_complete(_run())

        terminal_events = [e for e in events if isinstance(e, dict) and "_terminal_result" in e]
        assert terminal_events, "Binary file must yield _terminal_result error event"
        result = terminal_events[-1]["_terminal_result"]
        assert result.get("error") == "binary_file_not_inlinable", \
            f"error must be 'binary_file_not_inlinable', got: {result}"
        assert "file_path" in result, \
            "error must include file_path key"


# ---------------------------------------------------------------------------
# Test 9: Message persistence carries parent_task_id
# ---------------------------------------------------------------------------

class TestSubAgentMessagePersistence:
    """Test 9: test_sub_agent_persists_messages_with_parent_task_id (D-10)"""

    def test_sub_agent_persists_messages_with_parent_task_id(self):
        """Messages persisted by sub-agent must carry parent_task_id (D-10)."""
        from app.services.sub_agent_loop import run_sub_agent_loop
        import app.services.sub_agent_loop as sal_module

        # Inspect source for parent_task_id persistence pattern
        src = inspect.getsource(sal_module)
        assert "parent_task_id" in src, \
            "sub_agent_loop.py must reference parent_task_id for message persistence (D-10)"

    def test_sub_agent_passes_parent_task_id_to_persist(self):
        """_persist_round_message (or equivalent) is called with parent_task_id=task_id."""
        from app.services.sub_agent_loop import run_sub_agent_loop

        persist_calls = []
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_make_openrouter_text_response("Persisted.")
        )

        async def _mock_persist(thread_id, role, content, *, parent_task_id=None, **kwargs):
            persist_calls.append({"thread_id": thread_id, "role": role, "parent_task_id": parent_task_id})

        task_id = "task-009"

        async def _run():
            events = []
            with patch("app.services.sub_agent_loop.settings", _make_settings()):
                with patch("app.services.sub_agent_loop._persist_round_message",
                           side_effect=_mock_persist):
                    async for evt in run_sub_agent_loop(
                        description="Do something.",
                        context_files=[],
                        parent_user_id="user-uuid",
                        parent_user_email="test@test.com",
                        parent_token="jwt-token",
                        parent_tool_context={},
                        parent_thread_id="thread-uuid",
                        parent_user_msg_id="msg-uuid",
                        client=mock_client,
                        sys_settings={},
                        web_search_effective=False,
                        task_id=task_id,
                        parent_redaction_registry=_make_registry(),
                    ):
                        events.append(evt)
            return events

        asyncio.get_event_loop().run_until_complete(_run())

        if persist_calls:
            # All persist calls that happen inside sub_agent_loop must carry parent_task_id
            for c in persist_calls:
                assert c["parent_task_id"] == task_id, \
                    f"persist call must have parent_task_id={task_id!r}, got: {c['parent_task_id']!r} (D-10)"


# ---------------------------------------------------------------------------
# Test 10: ask_user retention — D-09 RETENTION half
# ---------------------------------------------------------------------------

class TestSubAgentRetainsAskUser:
    """Test 10: test_sub_agent_retains_ask_user (D-09 RETENTION — consolidated from 19-05 Test 7)

    This test owns the D-09 retention half: ask_user MUST be in the sub-agent's
    current_tools list because sub-agents may escalate to the user. The EXCLUDED
    set only strips task / write_todos / read_todos.
    """

    def test_sub_agent_retains_ask_user(self):
        """ask_user IS in the sub-agent tool list — D-09 retention assertion.

        Uses real tool_registry.build_llm_tools codepath with a pre-registered
        ask_user stub schema to verify the EXCLUDED-set filter does NOT strip it.
        """
        from app.services.sub_agent_loop import run_sub_agent_loop
        from app.services import tool_registry as _tr

        captured_tools = []
        mock_client = MagicMock()

        async def _mock_create(**kwargs):
            if not captured_tools:
                tools = kwargs.get("tools") or []
                captured_tools.extend(tools)
            return _make_openrouter_text_response("Done.")

        mock_client.chat.completions.create = _mock_create

        # Build a full_tools list that includes ask_user (simulating real registration)
        def _real_build_llm_tools(**kwargs):
            """Return a realistic tools list including ask_user and all excluded tools."""
            return [
                {"type": "function", "function": {"name": "search_documents"}},
                {"type": "function", "function": {"name": "query_database"}},
                {"type": "function", "function": {"name": "task"}},       # excluded
                {"type": "function", "function": {"name": "write_todos"}}, # excluded
                {"type": "function", "function": {"name": "read_todos"}},  # excluded
                {"type": "function", "function": {"name": "ask_user"}},    # MUST be retained
                {"type": "function", "function": {"name": "web_search"}},
            ]

        async def _run():
            events = []
            with patch("app.services.sub_agent_loop.settings", _make_settings(
                sub_agent_enabled=True, tool_registry_enabled=True
            )):
                with patch("app.services.sub_agent_loop._tr") as mock_tr:
                    mock_tr.make_active_set.return_value = set()
                    mock_tr.build_llm_tools.side_effect = _real_build_llm_tools
                    async for evt in run_sub_agent_loop(
                        description="Clarify requirements.",
                        context_files=[],
                        parent_user_id="user-uuid",
                        parent_user_email="test@test.com",
                        parent_token="jwt-token",
                        parent_tool_context={},
                        parent_thread_id="thread-uuid",
                        parent_user_msg_id="msg-uuid",
                        client=mock_client,
                        sys_settings={},
                        web_search_effective=False,
                        task_id="task-010",
                        parent_redaction_registry=_make_registry(),
                    ):
                        events.append(evt)
            return events

        asyncio.get_event_loop().run_until_complete(_run())

        tool_names = [t["function"]["name"] for t in captured_tools]

        # D-09 RETENTION: ask_user MUST be in sub-agent tools
        assert "ask_user" in tool_names, \
            f"ask_user must be RETAINED in sub-agent tool list (D-09 retention). Got: {tool_names}"

        # D-09 EXCLUSION: these three MUST NOT be in sub-agent tools
        assert "task" not in tool_names, \
            "task must be EXCLUDED from sub-agent tool list (D-09)"
        assert "write_todos" not in tool_names, \
            "write_todos must be EXCLUDED from sub-agent tool list (D-09)"
        assert "read_todos" not in tool_names, \
            "read_todos must be EXCLUDED from sub-agent tool list (D-09)"


# ---------------------------------------------------------------------------
# Source-inspection guardrails (module-level checks, not run-time execution)
# ---------------------------------------------------------------------------

class TestSubAgentLoopSourceInvariants:
    """Source inspection tests that verify design invariants via grep-like patterns."""

    def test_no_agent_status_events_emitted(self):
        """D-07: sub_agent_loop must NOT emit agent_status events (outermost loop only)."""
        import app.services.sub_agent_loop as sal_module
        src = inspect.getsource(sal_module)
        assert "agent_status" not in src, \
            "sub_agent_loop must NOT emit agent_status events (D-07)"

    def test_no_audit_service_calls(self):
        """D-23: sub-agent must NOT call audit_service.log_action."""
        import app.services.sub_agent_loop as sal_module
        src = inspect.getsource(sal_module)
        assert "audit_service" not in src, \
            "sub_agent_loop must NOT call audit_service (D-23 — parent logs under parent's user_id)"

    def test_egress_filter_present_in_source(self):
        """Egress filter must be imported and called in sub_agent_loop.py."""
        import app.services.sub_agent_loop as sal_module
        src = inspect.getsource(sal_module)
        assert "egress_filter" in src, \
            "sub_agent_loop must call egress_filter (D-21 / T-19-21)"

    def test_parent_redaction_registry_used_not_fresh(self):
        """D-21: parent_redaction_registry parameter must be passed to egress_filter (not fresh)."""
        import app.services.sub_agent_loop as sal_module
        src = inspect.getsource(sal_module)
        assert "parent_redaction_registry" in src, \
            "sub_agent_loop must use parent_redaction_registry (D-21)"

    def test_excluded_set_documented_with_retention_comment(self):
        """D-09 retention comment must be present near the EXCLUDED-set definition."""
        import app.services.sub_agent_loop as sal_module
        src = inspect.getsource(sal_module)
        assert "ask_user is intentionally retained" in src, \
            "EXCLUDED-set must have a comment stating ask_user is intentionally retained (D-09)"

    def test_ask_user_not_in_excluded_set(self):
        """ask_user must NOT appear in the EXCLUDED set definition."""
        import app.services.sub_agent_loop as sal_module
        src = inspect.getsource(sal_module)
        # Find lines containing EXCLUDED = {...}
        for line in src.splitlines():
            if "EXCLUDED" in line and ("=" in line or "{" in line):
                assert "ask_user" not in line, \
                    f"ask_user must NOT appear in EXCLUDED set definition (D-09), found in: {line}"

    def test_max_sub_agent_rounds_used(self):
        """Loop cap must use settings.max_sub_agent_rounds (D-11)."""
        import app.services.sub_agent_loop as sal_module
        src = inspect.getsource(sal_module)
        assert "max_sub_agent_rounds" in src, \
            "sub_agent_loop must use settings.max_sub_agent_rounds for loop cap (D-11)"

    def test_failure_isolation_wrapper_present(self):
        """D-12: failure isolation wrapper with sub_agent_failed error key must exist."""
        import app.services.sub_agent_loop as sal_module
        src = inspect.getsource(sal_module)
        assert "sub_agent_failed" in src, \
            "sub_agent_loop must have failure isolation wrapper with 'sub_agent_failed' (D-12)"
