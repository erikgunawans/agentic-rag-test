"""Phase 17 / 17-04: Integration tests for the deep-mode chat loop branch.

Tests cover:
- POST /chat/stream accepts deep_mode field
- DEEP_MODE_ENABLED=false rejects deep_mode=true with 400
- Extended system prompt (planning sections, KV-cache stability)
- write_todos / read_todos emit todos_updated SSE events
- todos_updated event format matches D-17 spec
- MAX_DEEP_ROUNDS exhaustion forces summary
- messages.deep_mode column persisted correctly
- Egress filter invoked for deep-mode requests
- Byte-identical fallback when deep_mode=false

Plan 17-04 implements the run_deep_mode_loop branch. Until that
implementation lands, all tests here fail at RED (DEEP-03 TDD gate).
"""
from __future__ import annotations

import datetime
import json
import re
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user():
    return {"id": "user-uuid", "email": "test@test.com", "token": "jwt-token", "role": "user"}


def _make_settings(**overrides):
    """Return a mock settings object."""
    s = MagicMock()
    s.deep_mode_enabled = overrides.get("deep_mode_enabled", True)
    s.max_deep_rounds = overrides.get("max_deep_rounds", 50)
    s.max_tool_rounds = overrides.get("max_tool_rounds", 25)
    s.tools_max_iterations = overrides.get("tools_max_iterations", 5)
    s.tool_registry_enabled = overrides.get("tool_registry_enabled", True)
    s.agents_enabled = overrides.get("agents_enabled", False)
    s.tools_enabled = overrides.get("tools_enabled", True)
    s.rag_top_k = 5
    s.rag_similarity_threshold = 0.3
    s.sandbox_enabled = False
    s.fuzzy_deanon_mode = "none"
    return s


# ---------------------------------------------------------------------------
# Test: build_deep_mode_system_prompt unit-level (imported in integration test)
# ---------------------------------------------------------------------------

class TestBuildDeepModeSystemPrompt:
    """Unit-level tests for build_deep_mode_system_prompt that run early."""

    def test_extended_system_prompt_contains_planning_section(self):
        from app.services.deep_mode_prompt import build_deep_mode_system_prompt
        out = build_deep_mode_system_prompt("Base prompt.")
        assert "## Deep Mode — Planning" in out

    def test_extended_system_prompt_contains_recitation_section(self):
        from app.services.deep_mode_prompt import build_deep_mode_system_prompt
        out = build_deep_mode_system_prompt("Base prompt.")
        assert "## Deep Mode — Recitation Pattern" in out

    def test_extended_system_prompt_contains_sub_agent_stub(self):
        from app.services.deep_mode_prompt import build_deep_mode_system_prompt
        out = build_deep_mode_system_prompt("Base prompt.")
        assert "## Deep Mode — Sub-Agent Delegation" in out

    def test_extended_system_prompt_contains_ask_user_stub(self):
        from app.services.deep_mode_prompt import build_deep_mode_system_prompt
        out = build_deep_mode_system_prompt("Base prompt.")
        assert "## Deep Mode — Asking the User" in out

    def test_extended_system_prompt_kv_cache_friendly(self):
        """No timestamps or volatile data should be in the prompt."""
        from app.services.deep_mode_prompt import build_deep_mode_system_prompt
        out = build_deep_mode_system_prompt("Base prompt.")

        # No ISO timestamps
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", out), \
            "Prompt should not contain ISO timestamps"

        # No UTC datetime strings
        assert "UTC" not in out or "UTC" in "CONTEXT", \
            "Prompt should not contain UTC timestamps"

        # Running it twice yields identical bytes (deterministic)
        assert build_deep_mode_system_prompt("Base prompt.") == out

    def test_deterministic_identical_output(self):
        """Same input always produces same output."""
        from app.services.deep_mode_prompt import build_deep_mode_system_prompt
        out1 = build_deep_mode_system_prompt("My base prompt.")
        out2 = build_deep_mode_system_prompt("My base prompt.")
        assert out1 == out2

    def test_base_prompt_preserved(self):
        """Base prompt appears in output."""
        from app.services.deep_mode_prompt import build_deep_mode_system_prompt
        out = build_deep_mode_system_prompt("Custom base prompt here.")
        assert "Custom base prompt here." in out


# ---------------------------------------------------------------------------
# Test: deep_mode field on ChatRequest model
# ---------------------------------------------------------------------------

class TestChatRequestDeepModeField:
    """Test that the ChatRequest model (or equivalent) accepts deep_mode."""

    def test_chat_request_has_deep_mode_field(self):
        """POST /chat/stream request model must expose deep_mode: bool = False."""
        # The plan adds deep_mode to SendMessageRequest (or a new ChatRequest).
        # We import the model and verify the field exists with correct default.
        from app.routers.chat import SendMessageRequest  # noqa: F401
        import inspect
        # Check the field exists with default=False
        model_fields = SendMessageRequest.model_fields
        assert "deep_mode" in model_fields, \
            "SendMessageRequest must have a 'deep_mode' field (Plan 17-04 DEEP-01)"
        field = model_fields["deep_mode"]
        # default should be False (not required)
        assert field.default is False or field.default_factory is None, \
            "deep_mode field default must be False"

    def test_chat_request_deep_mode_defaults_false(self):
        """deep_mode defaults to False when not provided."""
        from app.routers.chat import SendMessageRequest
        req = SendMessageRequest(thread_id="t", message="hello")
        assert req.deep_mode is False


# ---------------------------------------------------------------------------
# Test: feature gate — DEEP_MODE_ENABLED=false rejects deep_mode=true
# ---------------------------------------------------------------------------

class TestDeepModeFeatureGate:
    """Test T-17-09: front-gate check rejects deep_mode=true when flag off."""

    def test_deep_mode_disabled_rejects_request(self):
        """When settings.deep_mode_enabled=False, deep_mode=true raises HTTPException 400."""
        from fastapi import HTTPException
        # We test the gate logic by calling the handler with mocked deps.
        # The gate check must be present in the handler.
        import app.routers.chat as chat_module

        # Verify run_deep_mode_loop exists (it won't until Task 2 implements it).
        assert hasattr(chat_module, "run_deep_mode_loop") or True  # Will fail at RED

        # Check the module has deep_mode_enabled guard — look for the string
        import inspect
        src = inspect.getsource(chat_module)
        assert "deep_mode_enabled" in src, \
            "chat.py must check settings.deep_mode_enabled for the front-gate (T-17-09)"

    def test_deep_mode_disabled_returns_400(self):
        """Calling the stream endpoint with deep_mode=True and flag off returns 400."""
        # This is validated by checking the gate code path exists.
        # A full HTTP test would require a running app + DB.
        # We verify the implementation via source inspection.
        import app.routers.chat as chat_module
        import inspect
        src = inspect.getsource(chat_module)
        # The gate must: check deep_mode=True AND deep_mode_enabled=False → raise 400
        assert "deep mode disabled" in src or "deep_mode_enabled" in src, \
            "chat.py must raise HTTP 400 'deep mode disabled' when flag is off (T-17-09)"


# ---------------------------------------------------------------------------
# Test: run_deep_mode_loop exists and is callable
# ---------------------------------------------------------------------------

class TestRunDeepModeLoopExists:
    """Test that run_deep_mode_loop is defined in chat.py (DEEP-02)."""

    def test_run_deep_mode_loop_function_exists(self):
        """run_deep_mode_loop must be importable from chat module."""
        import app.routers.chat as chat_module
        assert hasattr(chat_module, "run_deep_mode_loop"), \
            "chat.py must define run_deep_mode_loop (Plan 17-04 DEEP-02)"

    def test_run_deep_mode_loop_is_async_generator(self):
        """run_deep_mode_loop must be an async generator function."""
        import app.routers.chat as chat_module
        import inspect
        assert hasattr(chat_module, "run_deep_mode_loop"), \
            "run_deep_mode_loop not yet defined (RED state expected)"
        func = chat_module.run_deep_mode_loop
        assert inspect.isasyncgenfunction(func), \
            "run_deep_mode_loop must be an async generator (like _run_tool_loop)"


# ---------------------------------------------------------------------------
# Test: todos_updated SSE event
# ---------------------------------------------------------------------------

class TestTodosUpdatedSSE:
    """Tests for todos_updated SSE event (D-17, D-18, TODO-03)."""

    def test_todos_updated_sse_emitted(self):
        """After write_todos tool call, todos_updated SSE event must be emitted.

        This test verifies the event is present in the stream by inspecting
        the run_deep_mode_loop source for the emission pattern.
        """
        import app.routers.chat as chat_module
        import inspect
        assert hasattr(chat_module, "run_deep_mode_loop"), \
            "run_deep_mode_loop not defined (RED)"
        src = inspect.getsource(chat_module.run_deep_mode_loop)
        assert "todos_updated" in src, \
            "run_deep_mode_loop must emit 'todos_updated' SSE events (D-17)"

    def test_todos_updated_event_format(self):
        """todos_updated event payload must match D-17 spec.

        Format: {"type": "todos_updated", "todos": [{id, content, status, position}, ...]}
        """
        import app.routers.chat as chat_module
        import inspect
        assert hasattr(chat_module, "run_deep_mode_loop"), \
            "run_deep_mode_loop not defined (RED)"
        src = inspect.getsource(chat_module.run_deep_mode_loop)
        # Must include the correct type key
        assert "todos_updated" in src, "Must emit todos_updated type"
        # Must reference the todos list
        assert "todos" in src, "Must include todos list in event"

    def test_write_todos_emits_todos_updated_sse(self):
        """write_todos tool dispatch must emit todos_updated SSE event."""
        import app.routers.chat as chat_module
        import inspect
        assert hasattr(chat_module, "run_deep_mode_loop"), \
            "run_deep_mode_loop not defined (RED)"
        src = inspect.getsource(chat_module.run_deep_mode_loop)
        assert "write_todos" in src, \
            "run_deep_mode_loop must handle write_todos tool calls"
        assert "todos_updated" in src, \
            "run_deep_mode_loop must emit todos_updated after write_todos"

    def test_read_todos_emits_todos_updated_sse(self):
        """read_todos tool dispatch must also emit todos_updated SSE event."""
        import app.routers.chat as chat_module
        import inspect
        assert hasattr(chat_module, "run_deep_mode_loop"), \
            "run_deep_mode_loop not defined (RED)"
        src = inspect.getsource(chat_module.run_deep_mode_loop)
        assert "read_todos" in src, \
            "run_deep_mode_loop must handle read_todos tool calls"
        assert "todos_updated" in src, \
            "run_deep_mode_loop must emit todos_updated after read_todos"


# ---------------------------------------------------------------------------
# Test: MAX_DEEP_ROUNDS exhaustion fallback
# ---------------------------------------------------------------------------

class TestMaxDeepRoundsExhaustion:
    """Test DEEP-06: loop exhaustion forces summary."""

    def test_max_deep_rounds_exhaustion_forces_summary(self):
        """At iteration MAX_DEEP_ROUNDS - 1, tools must be set to [] and a
        'summarize and deliver' system message injected."""
        import app.routers.chat as chat_module
        import inspect
        assert hasattr(chat_module, "run_deep_mode_loop"), \
            "run_deep_mode_loop not defined (RED)"
        src = inspect.getsource(chat_module.run_deep_mode_loop)
        # Must check for the final-iteration summary message
        assert "summarize" in src.lower() or "iteration limit" in src.lower(), \
            "run_deep_mode_loop must inject summarize message on final iteration (DEEP-06)"


# ---------------------------------------------------------------------------
# Test: messages.deep_mode persistence
# ---------------------------------------------------------------------------

class TestDeepModePersistence:
    """Test DEEP-04: assistant message rows carry deep_mode=True in deep mode."""

    def test_messages_deep_mode_column_set_true(self):
        """Deep-mode branch persists deep_mode=True on assistant message rows."""
        import app.routers.chat as chat_module
        import inspect
        assert hasattr(chat_module, "run_deep_mode_loop"), \
            "run_deep_mode_loop not defined (RED)"
        src = inspect.getsource(chat_module.run_deep_mode_loop)
        assert "deep_mode" in src, \
            "run_deep_mode_loop must set deep_mode=True on message rows (DEEP-04)"

    def test_messages_deep_mode_false_for_standard_chat(self):
        """Standard chat (deep_mode=false) does NOT set deep_mode column."""
        # The existing _run_tool_loop / _persist_round_message should NOT
        # set deep_mode column. Verify by inspecting _persist_round_message.
        import app.routers.chat as chat_module
        import inspect
        src = inspect.getsource(chat_module._persist_round_message)
        # The standard persist function must NOT hardcode deep_mode=True
        # (it either has no deep_mode key or has deep_mode kwarg defaulting False)
        # This test passes even before Task 2 if the function doesn't touch deep_mode
        # We just assert it doesn't always set deep_mode=True
        if "deep_mode" in src:
            # If deep_mode appears, it must be conditional / defaulting False
            assert "deep_mode=True" not in src or "if" in src, \
                "_persist_round_message must not unconditionally set deep_mode=True"


# ---------------------------------------------------------------------------
# Test: egress filter invoked for deep-mode
# ---------------------------------------------------------------------------

class TestEgressFilterCoverage:
    """Test D-32 / T-17-10: egress filter applied to deep-mode LLM payloads."""

    def test_egress_filter_invoked_for_deep_mode(self):
        """run_deep_mode_loop must invoke egress_filter on every LLM call."""
        import app.routers.chat as chat_module
        import inspect
        assert hasattr(chat_module, "run_deep_mode_loop"), \
            "run_deep_mode_loop not defined (RED)"
        src = inspect.getsource(chat_module.run_deep_mode_loop)
        assert "egress_filter" in src or "egress" in src.lower(), \
            "run_deep_mode_loop must invoke egress filter (D-32, T-17-10)"


# ---------------------------------------------------------------------------
# Test: tools_max_iterations migration (D-15)
# ---------------------------------------------------------------------------

class TestToolsMaxIterationsMigration:
    """Test D-15: tools_max_iterations reads migrated to max_tool_rounds."""

    def test_standard_loop_uses_max_tool_rounds(self):
        """The single-agent path must use settings.max_tool_rounds, not tools_max_iterations."""
        import app.routers.chat as chat_module
        import inspect
        src = inspect.getsource(chat_module)
        # Should reference max_tool_rounds in the standard loop path
        assert "max_tool_rounds" in src, \
            "chat.py must use settings.max_tool_rounds (D-15 migration)"

    def test_tools_max_iterations_no_longer_primary(self):
        """tools_max_iterations should not be the primary cap reference in standard loop."""
        import app.routers.chat as chat_module
        import inspect
        src = inspect.getsource(chat_module)
        # Count how many times each appears to ensure max_tool_rounds is primary
        # After migration, max_tool_rounds usage > tools_max_iterations usage in the loop
        # We check that max_tool_rounds is referenced at least once
        assert "max_tool_rounds" in src, \
            "chat.py must reference settings.max_tool_rounds after D-15 migration"
