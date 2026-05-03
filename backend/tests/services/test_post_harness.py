"""Phase 20 / v1.3 — Tests for post_harness.py (POST-01..05, D-09, D-10, SEC-04, W9).

11 tests:
1.  test_truncation_empty_dict_returns_empty_json
2.  test_truncation_under_threshold_returns_full
3.  test_truncation_over_threshold_truncates_early_phases
4.  test_truncation_marker_exact_text
5.  test_summarize_builds_messages_with_phase_results_in_system
6.  test_summarize_harness_run_egress_filter_called_with_exact_parent_registry
7.  test_summarize_harness_run_negative_control_no_registry_means_no_egress
8.  test_summarize_egress_blocked_yields_refusal_no_openrouter
9.  test_summarize_happy_path_yields_delta_then_summary_complete
10. test_summarize_happy_path_persists_message_with_harness_mode
11. test_summarize_system_prompt_contains_concise_guidance
"""
from __future__ import annotations

import json
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.types import HarnessDefinition, HarnessPrerequisites, PhaseDefinition, PhaseType
from app.services.post_harness import (
    TRUNCATION_MARKER,
    _truncate_phase_results,
    summarize_harness_run,
)
from app.services.redaction.egress import EgressResult


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_harness() -> HarnessDefinition:
    return HarnessDefinition(
        name="smoke-echo",
        display_name="Smoke Echo",
        prerequisites=HarnessPrerequisites(
            harness_intro="Smoke echo harness.",
        ),
        phases=[
            PhaseDefinition(name="echo", phase_type=PhaseType.PROGRAMMATIC),
            PhaseDefinition(name="summarize", phase_type=PhaseType.LLM_SINGLE),
        ],
    )


def _make_run(phase_results: dict | None = None) -> dict:
    return {
        "id": "run-abc",
        "harness_type": "smoke-echo",
        "phase_results": phase_results or {},
    }


class _Chunk:
    """Minimal streaming chunk mock matching openai.types.chat.ChatCompletionChunk shape."""
    def __init__(self, text: str):
        self.choices = [type("C", (), {"delta": type("D", (), {"content": text})()})()]


async def _async_iter_chunks(texts: list[str]):
    for t in texts:
        yield _Chunk(t)


# ---------------------------------------------------------------------------
# Test 1: truncation — empty dict edge case
# ---------------------------------------------------------------------------

def test_truncation_empty_dict_returns_empty_json():
    result = _truncate_phase_results({})
    assert result == "{}"


# ---------------------------------------------------------------------------
# Test 2: truncation — under threshold returns full JSON
# ---------------------------------------------------------------------------

def test_truncation_under_threshold_returns_full():
    # 3 phases, each ~100 chars — well under 30k
    phase_results = {
        "0": {"phase_name": "p0", "output": "x" * 100},
        "1": {"phase_name": "p1", "output": "y" * 100},
        "2": {"phase_name": "p2", "output": "z" * 100},
    }
    result = _truncate_phase_results(phase_results)
    # Should be valid JSON equal to the original
    parsed = json.loads(result)
    assert parsed == phase_results


# ---------------------------------------------------------------------------
# Test 3: truncation — over threshold truncates early phases, keeps last 2
# ---------------------------------------------------------------------------

def test_truncation_over_threshold_truncates_early_phases():
    # 5 phases each ~10k chars → total ~50k > 30k threshold
    phase_results = {
        str(i): {"phase_name": f"phase_{i}", "output": "A" * 10_000}
        for i in range(5)
    }
    result = _truncate_phase_results(phase_results, max_chars=30_000)
    # Phases 0, 1, 2 should be truncated (markers present)
    assert TRUNCATION_MARKER in result
    # Phases 3 and 4 should be full (10k 'A' chars each)
    assert "A" * 10_000 in result


# ---------------------------------------------------------------------------
# Test 4: truncation — marker contains exact text
# ---------------------------------------------------------------------------

def test_truncation_marker_exact_text():
    assert TRUNCATION_MARKER == "...[truncated, see workspace artifact]"


# ---------------------------------------------------------------------------
# Test 5: summarize builds messages with phase_results in SYSTEM prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_builds_messages_with_phase_results_in_system(monkeypatch):
    captured_messages: list[dict] = []

    mock_egress = MagicMock(return_value=MagicMock(tripped=False, match_count=0))
    monkeypatch.setattr("app.services.post_harness.egress_filter", mock_egress)

    async def _fake_create(messages, model, stream, **kwargs):
        captured_messages.extend(messages)
        return _async_iter_chunks(["summary text"])

    monkeypatch.setattr(
        "app.services.post_harness.openrouter_service.client.chat.completions.create",
        _fake_create,
    )

    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-1"}]
    monkeypatch.setattr("app.services.post_harness.get_supabase_authed_client", lambda *a: mock_client)

    harness = _make_harness()
    harness_run = _make_run({"0": {"phase_name": "echo", "output": "hello world"}})

    events = []
    async for ev in summarize_harness_run(
        harness=harness,
        harness_run=harness_run,
        thread_id="thread-1",
        user_id="u-1",
        user_email="u@e.com",
        token="tok",
        registry=MagicMock(),
    ):
        events.append(ev)

    assert len(captured_messages) >= 1
    # First message must be system role
    assert captured_messages[0]["role"] == "system"
    # System prompt must include phase_results content
    assert "echo" in captured_messages[0]["content"] or "hello world" in captured_messages[0]["content"]


# ---------------------------------------------------------------------------
# Test 6: egress filter called with EXACT parent_registry (W9 rigor)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_harness_run_egress_filter_called_with_exact_parent_registry(monkeypatch):
    # (a) Non-None registry — guards against silent-skip regression
    parent_registry = MagicMock()
    parent_registry.thread_id = "thread-abc"

    # (b) Mocks
    mock_egress = MagicMock(return_value=MagicMock(tripped=False, match_count=0))
    monkeypatch.setattr("app.services.post_harness.egress_filter", mock_egress)

    mock_create = AsyncMock()
    mock_create.return_value = _async_iter_chunks(["Summary text"])
    monkeypatch.setattr(
        "app.services.post_harness.openrouter_service.client.chat.completions.create",
        mock_create,
    )

    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-1"}]
    monkeypatch.setattr("app.services.post_harness.get_supabase_authed_client", lambda *a: mock_client)

    # Drive
    events = []
    async for ev in summarize_harness_run(
        harness=_make_harness(),
        harness_run={"id": "run-1", "phase_results": {"0": {"phase_name": "p0", "output": "x"}}},
        thread_id="thread-abc",
        user_id="u-1",
        user_email="u@e.com",
        token="tok",
        registry=parent_registry,
    ):
        events.append(ev)

    # (c) egress called
    assert mock_egress.called, "egress_filter must be called BEFORE the LLM call"

    # (d) Object identity — SAME parent_registry instance
    assert mock_egress.call_args[0][1] is parent_registry, (
        "egress_filter must receive the EXACT parent ConversationRegistry — "
        "not a copy, not a fresh load, not None"
    )

    # (e) Order: egress was called, and openrouter was also called (happy path)
    assert mock_create.called, "openrouter must be called on happy path"


# ---------------------------------------------------------------------------
# Test 7: negative control — registry=None means no egress (W9 part f)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_harness_run_negative_control_no_registry_means_no_egress(monkeypatch):
    """Negative control (W9 part f): when registry=None, egress_filter is NOT
    called. This pins the OFF-mode behavior — also serves as the inverse witness
    that the positive test above is meaningful."""
    mock_egress = MagicMock()
    monkeypatch.setattr("app.services.post_harness.egress_filter", mock_egress)

    monkeypatch.setattr(
        "app.services.post_harness.openrouter_service.client.chat.completions.create",
        AsyncMock(return_value=_async_iter_chunks(["text"])),
    )

    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-1"}]
    monkeypatch.setattr("app.services.post_harness.get_supabase_authed_client", lambda *a: mock_client)

    async for _ in summarize_harness_run(
        harness=_make_harness(),
        harness_run={"id": "run-1", "phase_results": {}},
        thread_id="thread-abc",
        user_id="u-1",
        user_email="u@e.com",
        token="tok",
        registry=None,
    ):
        pass

    assert not mock_egress.called, (
        "When registry=None (PII redaction off), egress_filter MUST NOT be called "
        "— this matches the existing OFF-mode no-op contract."
    )


# ---------------------------------------------------------------------------
# Test 8: egress blocked → refusal, no openrouter call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_egress_blocked_yields_refusal_no_openrouter(monkeypatch):
    mock_egress = MagicMock(return_value=EgressResult(
        tripped=True, match_count=1, entity_types=["PERSON"], match_hashes=["abc123"]
    ))
    monkeypatch.setattr("app.services.post_harness.egress_filter", mock_egress)

    mock_create = MagicMock()
    monkeypatch.setattr(
        "app.services.post_harness.openrouter_service.client.chat.completions.create",
        mock_create,
    )

    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-1"}]
    monkeypatch.setattr("app.services.post_harness.get_supabase_authed_client", lambda *a: mock_client)

    mock_audit = MagicMock()
    monkeypatch.setattr("app.services.post_harness.audit_service", mock_audit)

    events = []
    async for ev in summarize_harness_run(
        harness=_make_harness(),
        harness_run={"id": "run-1", "phase_results": {}},
        thread_id="thread-1",
        user_id="u-1",
        user_email="u@e.com",
        token="tok",
        registry=MagicMock(),
    ):
        events.append(ev)

    # Must yield refusal delta + summary_complete
    types = [e["type"] for e in events]
    assert "delta" in types
    assert "summary_complete" in types

    # summary_complete with None msg_id (no persist on egress block)
    sc_events = [e for e in events if e["type"] == "summary_complete"]
    assert sc_events[0]["assistant_message_id"] is None

    # openrouter must NOT have been called
    assert not mock_create.called, "openrouter MUST NOT be called when egress is blocked"


# ---------------------------------------------------------------------------
# Test 9: happy path — yields ≥1 delta then summary_complete with msg_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_happy_path_yields_delta_then_summary_complete(monkeypatch):
    monkeypatch.setattr(
        "app.services.post_harness.egress_filter",
        MagicMock(return_value=MagicMock(tripped=False, match_count=0)),
    )
    monkeypatch.setattr(
        "app.services.post_harness.openrouter_service.client.chat.completions.create",
        AsyncMock(return_value=_async_iter_chunks(["Hello ", "world."])),
    )

    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-xyz"}]
    monkeypatch.setattr("app.services.post_harness.get_supabase_authed_client", lambda *a: mock_client)

    events = []
    async for ev in summarize_harness_run(
        harness=_make_harness(),
        harness_run=_make_run(),
        thread_id="t-1",
        user_id="u-1",
        user_email="u@e.com",
        token="tok",
        registry=MagicMock(),
    ):
        events.append(ev)

    types = [e["type"] for e in events]
    assert "delta" in types
    assert types[-1] == "summary_complete"

    # summary_complete must carry an assistant_message_id
    sc = events[-1]
    assert sc["assistant_message_id"] == "msg-xyz"


# ---------------------------------------------------------------------------
# Test 10: happy path persists message with harness_mode=harness.name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_happy_path_persists_message_with_harness_mode(monkeypatch):
    monkeypatch.setattr(
        "app.services.post_harness.egress_filter",
        MagicMock(return_value=MagicMock(tripped=False, match_count=0)),
    )
    monkeypatch.setattr(
        "app.services.post_harness.openrouter_service.client.chat.completions.create",
        AsyncMock(return_value=_async_iter_chunks(["Summary."])),
    )

    inserted_payload: dict = {}
    mock_insert = MagicMock()
    mock_insert.execute.return_value.data = [{"id": "msg-persist"}]

    mock_table = MagicMock()
    mock_table.insert.side_effect = lambda payload: (inserted_payload.update(payload) or mock_insert)

    mock_client = MagicMock()
    mock_client.table.return_value = mock_table
    monkeypatch.setattr("app.services.post_harness.get_supabase_authed_client", lambda *a: mock_client)

    async for _ in summarize_harness_run(
        harness=_make_harness(),
        harness_run=_make_run(),
        thread_id="t-1",
        user_id="u-1",
        user_email="u@e.com",
        token="tok",
        registry=MagicMock(),
    ):
        pass

    assert inserted_payload.get("harness_mode") == "smoke-echo"
    assert inserted_payload.get("role") == "assistant"


# ---------------------------------------------------------------------------
# Test 11: system prompt contains concise guidance text (D-10 soft 500-token)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarize_system_prompt_contains_concise_guidance(monkeypatch):
    captured_messages: list[dict] = []

    mock_egress = MagicMock(return_value=MagicMock(tripped=False, match_count=0))
    monkeypatch.setattr("app.services.post_harness.egress_filter", mock_egress)

    async def _fake_create(messages, model, stream, **kwargs):
        captured_messages.extend(messages)
        return _async_iter_chunks(["ok"])

    monkeypatch.setattr(
        "app.services.post_harness.openrouter_service.client.chat.completions.create",
        _fake_create,
    )

    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "msg-1"}]
    monkeypatch.setattr("app.services.post_harness.get_supabase_authed_client", lambda *a: mock_client)

    async for _ in summarize_harness_run(
        harness=_make_harness(),
        harness_run=_make_run(),
        thread_id="t-1",
        user_id="u-1",
        user_email="u@e.com",
        token="tok",
        registry=MagicMock(),
    ):
        pass

    assert captured_messages, "No messages captured"
    system_content = captured_messages[0]["content"]
    assert "Be concise — 3-5 short paragraphs. Reference workspace files by path." in system_content
