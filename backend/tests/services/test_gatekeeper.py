"""Phase 20 / v1.3 — Tests for gatekeeper.py (GATE-01..05, D-05..D-08, SEC-04, W8).

11 tests:
1.  test_build_system_prompt_includes_intro
2.  test_build_system_prompt_includes_upload_block_when_required
3.  test_load_gatekeeper_history_returns_prior_turns
4.  test_run_gatekeeper_no_sentinel_yields_full_buffer
5.  test_run_gatekeeper_sentinel_at_end_strips_and_triggers
6.  test_run_gatekeeper_sentinel_with_trailing_whitespace_still_triggers
7.  test_run_gatekeeper_sentinel_mid_stream_does_NOT_trigger
8.  test_run_gatekeeper_egress_blocked_emits_refusal
9.  test_run_gatekeeper_persists_user_and_assistant_messages_with_harness_mode
10. test_run_gatekeeper_calls_start_run_on_trigger
11. test_run_gatekeeper_complete_event_includes_phase_count  (W8)
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.harnesses.types import HarnessDefinition, HarnessPrerequisites, PhaseDefinition, PhaseType
from app.services.gatekeeper import (
    SENTINEL,
    build_system_prompt,
    load_gatekeeper_history,
    run_gatekeeper,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_prereqs(requires_upload: bool = True) -> HarnessPrerequisites:
    return HarnessPrerequisites(
        requires_upload=requires_upload,
        upload_description="your contract DOCX or PDF",
        accepted_mime_types=["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
        min_files=1,
        max_files=1,
        harness_intro="This harness reviews your contract.",
    )


def _make_harness(n_phases: int = 2, requires_upload: bool = True) -> HarnessDefinition:
    phases = [
        PhaseDefinition(
            name=f"Phase {i}",
            phase_type=PhaseType.PROGRAMMATIC,
        )
        for i in range(n_phases)
    ]
    return HarnessDefinition(
        name="smoke-echo",
        display_name="Smoke Echo",
        prerequisites=_make_prereqs(requires_upload=requires_upload),
        phases=phases,
    )


def _make_supabase_mock(return_data: list | None = None) -> MagicMock:
    """Fluent Supabase query-builder mock."""
    mock = MagicMock()
    chain = MagicMock()
    mock.table.return_value = chain
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain

    execute_result = MagicMock()
    execute_result.data = return_data or []
    chain.execute.return_value = execute_result
    return mock


async def _drain(gen) -> list[dict]:
    events = []
    async for ev in gen:
        events.append(ev)
    return events


def _make_stream_chunk(content: str):
    """Create a mock OpenAI streaming chunk."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = content
    return chunk


async def _async_iter(items):
    """Wrap a list as an async iterator."""
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# 1. test_build_system_prompt_includes_intro
# ---------------------------------------------------------------------------

def test_build_system_prompt_includes_intro():
    harness = _make_harness()
    prompt = build_system_prompt(harness)
    assert "This harness reviews your contract." in prompt
    assert harness.display_name in prompt
    assert SENTINEL in prompt


# ---------------------------------------------------------------------------
# 2. test_build_system_prompt_includes_upload_block_when_required
# ---------------------------------------------------------------------------

def test_build_system_prompt_includes_upload_block_when_required():
    harness = _make_harness(requires_upload=True)
    prompt = build_system_prompt(harness)
    assert "your contract DOCX or PDF" in prompt
    assert "application/pdf" in prompt
    assert "min files: 1" in prompt.lower()


# ---------------------------------------------------------------------------
# 3. test_load_gatekeeper_history_returns_prior_turns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_gatekeeper_history_returns_prior_turns():
    rows = [
        {"role": "user", "content": "Hello", "created_at": "2026-01-01T00:00:00Z"},
        {"role": "assistant", "content": "Please upload your file.", "created_at": "2026-01-01T00:00:01Z"},
        {"role": "user", "content": "Here it is.", "created_at": "2026-01-01T00:00:02Z"},
    ]
    mock_client = _make_supabase_mock(return_data=rows)

    with patch("app.services.gatekeeper.get_supabase_authed_client", return_value=mock_client):
        history = await load_gatekeeper_history(
            thread_id="thread-1",
            harness_name="smoke-echo",
            token="tok",
        )

    assert len(history) == 3
    assert history[0] == {"role": "user", "content": "Hello"}
    assert history[1] == {"role": "assistant", "content": "Please upload your file."}
    assert history[2] == {"role": "user", "content": "Here it is."}


# ---------------------------------------------------------------------------
# 4. test_run_gatekeeper_no_sentinel_yields_full_buffer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_gatekeeper_no_sentinel_yields_full_buffer():
    harness = _make_harness(n_phases=2)
    user_msg_row = {"id": "user-msg-1"}
    asst_msg_row = {"id": "asst-msg-1"}

    # Mock messages: first call inserts user msg, second inserts assistant msg
    mock_client_1 = _make_supabase_mock(return_data=[user_msg_row])
    mock_client_2 = _make_supabase_mock(return_data=[])   # load_history returns []
    mock_client_3 = _make_supabase_mock(return_data=[asst_msg_row])  # persist assistant

    call_count = [0]

    def mock_get_client(token):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_client_1   # persist user message
        elif call_count[0] == 2:
            return mock_client_2   # load history
        else:
            return mock_client_3   # persist assistant message

    stream_text = "Hello! Please upload your contract first."
    chunks = [_make_stream_chunk(c) for c in stream_text]

    mock_stream = _async_iter(chunks)
    mock_completions = AsyncMock()
    mock_completions.create.return_value = mock_stream

    mock_or_client = MagicMock()
    mock_or_client.chat.completions = mock_completions

    mock_or_svc = MagicMock()
    mock_or_svc.client = mock_or_client

    mock_registry = None  # redaction off for simplicity

    with patch("app.services.gatekeeper.get_supabase_authed_client", side_effect=mock_get_client), \
         patch("app.services.gatekeeper.OpenRouterService", return_value=mock_or_svc):
        events = await _drain(run_gatekeeper(
            harness=harness,
            thread_id="thread-1",
            user_id="user-1",
            user_email="user@test.com",
            user_message="Let me start.",
            token="tok",
            registry=mock_registry,
        ))

    # Collect all delta text
    delta_text = "".join(e["content"] for e in events if e["type"] == "delta")
    assert stream_text in delta_text

    # Last event should be gatekeeper_complete with triggered=False
    complete_events = [e for e in events if e["type"] == "gatekeeper_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["triggered"] is False
    assert complete_events[0]["harness_run_id"] is None
    assert complete_events[0]["phase_count"] == 2


# ---------------------------------------------------------------------------
# 5. test_run_gatekeeper_sentinel_at_end_strips_and_triggers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_gatekeeper_sentinel_at_end_strips_and_triggers():
    harness = _make_harness(n_phases=3)
    user_msg_row = {"id": "user-msg-2"}
    asst_msg_row = {"id": "asst-msg-2"}
    harness_run_row = "harness-run-1"

    call_count = [0]
    mock_client_history = _make_supabase_mock(return_data=[])
    mock_client_user = _make_supabase_mock(return_data=[user_msg_row])
    mock_client_asst = _make_supabase_mock(return_data=[asst_msg_row])

    def mock_get_client(token):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_client_user   # persist user message
        elif call_count[0] == 2:
            return mock_client_history  # load history
        else:
            return mock_client_asst  # persist assistant

    stream_text = "OK starting now [TRIGGER_HARNESS]"
    chunks = [_make_stream_chunk(c) for c in stream_text]

    mock_stream = _async_iter(chunks)
    mock_completions = AsyncMock()
    mock_completions.create.return_value = mock_stream
    mock_or_client = MagicMock()
    mock_or_client.chat.completions = mock_completions
    mock_or_svc = MagicMock()
    mock_or_svc.client = mock_or_client

    with patch("app.services.gatekeeper.get_supabase_authed_client", side_effect=mock_get_client), \
         patch("app.services.gatekeeper.OpenRouterService", return_value=mock_or_svc), \
         patch("app.services.gatekeeper.harness_runs_service.start_run", new_callable=AsyncMock, return_value=harness_run_row) as mock_start:
        events = await _drain(run_gatekeeper(
            harness=harness,
            thread_id="thread-2",
            user_id="user-1",
            user_email="user@test.com",
            user_message="I want to start.",
            token="tok",
            registry=None,
        ))

    # Sentinel must NOT appear in any delta
    delta_text = "".join(e["content"] for e in events if e["type"] == "delta")
    assert "[TRIGGER_HARNESS]" not in delta_text

    complete_events = [e for e in events if e["type"] == "gatekeeper_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["triggered"] is True
    assert complete_events[0]["harness_run_id"] == harness_run_row
    assert complete_events[0]["phase_count"] == 3

    mock_start.assert_called_once()


# ---------------------------------------------------------------------------
# 6. test_run_gatekeeper_sentinel_with_trailing_whitespace_still_triggers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_gatekeeper_sentinel_with_trailing_whitespace_still_triggers():
    harness = _make_harness(n_phases=2)

    # call 1: persist user msg → returns row with id
    # call 2: load_gatekeeper_history → returns empty history
    # call 3: persist assistant msg → returns row with id
    call_count = [0]
    def mock_get_client(token):
        call_count[0] += 1
        if call_count[0] == 2:
            # load_gatekeeper_history — return empty list
            return _make_supabase_mock(return_data=[])
        return _make_supabase_mock(return_data=[{"id": f"row-{call_count[0]}"}])

    stream_text = "Begin [TRIGGER_HARNESS]   \n"
    chunks = [_make_stream_chunk(c) for c in stream_text]
    mock_stream = _async_iter(chunks)
    mock_completions = AsyncMock()
    mock_completions.create.return_value = mock_stream
    mock_or_client = MagicMock()
    mock_or_client.chat.completions = mock_completions
    mock_or_svc = MagicMock()
    mock_or_svc.client = mock_or_client

    with patch("app.services.gatekeeper.get_supabase_authed_client", side_effect=mock_get_client), \
         patch("app.services.gatekeeper.OpenRouterService", return_value=mock_or_svc), \
         patch("app.services.gatekeeper.harness_runs_service.start_run", new_callable=AsyncMock, return_value="run-ws"):
        events = await _drain(run_gatekeeper(
            harness=harness,
            thread_id="thread-3",
            user_id="user-1",
            user_email="user@test.com",
            user_message="Start it.",
            token="tok",
            registry=None,
        ))

    complete_events = [e for e in events if e["type"] == "gatekeeper_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["triggered"] is True


# ---------------------------------------------------------------------------
# 7. test_run_gatekeeper_sentinel_mid_stream_does_NOT_trigger
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_gatekeeper_sentinel_mid_stream_does_NOT_trigger():
    """Sentinel is regex-anchored to end-of-stream; mid-stream occurrence does NOT trigger."""
    harness = _make_harness(n_phases=2)

    call_count = [0]
    def mock_get_client(token):
        call_count[0] += 1
        if call_count[0] == 2:
            return _make_supabase_mock(return_data=[])
        return _make_supabase_mock(return_data=[{"id": f"row-{call_count[0]}"}])

    # Sentinel in the middle — the full text does NOT end with it
    stream_text = "I might [TRIGGER_HARNESS] but actually wait"
    chunks = [_make_stream_chunk(c) for c in stream_text]
    mock_stream = _async_iter(chunks)
    mock_completions = AsyncMock()
    mock_completions.create.return_value = mock_stream
    mock_or_client = MagicMock()
    mock_or_client.chat.completions = mock_completions
    mock_or_svc = MagicMock()
    mock_or_svc.client = mock_or_client

    with patch("app.services.gatekeeper.get_supabase_authed_client", side_effect=mock_get_client), \
         patch("app.services.gatekeeper.OpenRouterService", return_value=mock_or_svc), \
         patch("app.services.gatekeeper.harness_runs_service.start_run", new_callable=AsyncMock) as mock_start:
        events = await _drain(run_gatekeeper(
            harness=harness,
            thread_id="thread-4",
            user_id="user-1",
            user_email="user@test.com",
            user_message="Will you start?",
            token="tok",
            registry=None,
        ))

    complete_events = [e for e in events if e["type"] == "gatekeeper_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["triggered"] is False

    mock_start.assert_not_called()


# ---------------------------------------------------------------------------
# 8. test_run_gatekeeper_egress_blocked_emits_refusal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_gatekeeper_egress_blocked_emits_refusal():
    harness = _make_harness(n_phases=2)

    call_count = [0]
    def mock_get_client(token):
        call_count[0] += 1
        if call_count[0] == 2:
            return _make_supabase_mock(return_data=[])
        return _make_supabase_mock(return_data=[{"id": f"row-{call_count[0]}"}])

    from app.services.redaction.egress import EgressResult
    mock_egress_result = EgressResult(
        tripped=True,
        match_count=1,
        entity_types=["PERSON"],
        match_hashes=["abc12345"],
    )

    mock_registry = MagicMock()
    mock_registry.thread_id = "thread-5"

    with patch("app.services.gatekeeper.get_supabase_authed_client", side_effect=mock_get_client), \
         patch("app.services.gatekeeper.egress_filter", return_value=mock_egress_result) as mock_egress, \
         patch("app.services.gatekeeper.audit_service.log_action") as mock_audit:
        events = await _drain(run_gatekeeper(
            harness=harness,
            thread_id="thread-5",
            user_id="user-1",
            user_email="user@test.com",
            user_message="My name is John Smith.",
            token="tok",
            registry=mock_registry,
        ))

    # Should emit the refusal text as a delta
    delta_events = [e for e in events if e["type"] == "delta"]
    assert len(delta_events) >= 1
    refusal_text = "".join(e["content"] for e in delta_events)
    assert "sensitive data" in refusal_text.lower() or "cannot process" in refusal_text.lower()

    # Completion event should have triggered=False
    complete_events = [e for e in events if e["type"] == "gatekeeper_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["triggered"] is False

    # Audit log should be called
    mock_audit.assert_called_once()
    call_kwargs = mock_audit.call_args
    assert "gatekeeper_egress_blocked" in str(call_kwargs)


# ---------------------------------------------------------------------------
# 9. test_run_gatekeeper_persists_user_and_assistant_messages_with_harness_mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_gatekeeper_persists_user_and_assistant_messages_with_harness_mode():
    """Assert both user and assistant messages inserted with harness_mode=harness.name."""
    harness = _make_harness(n_phases=2)

    insert_calls: list[dict] = []

    def mock_get_client(token):
        mock = MagicMock()
        chain = MagicMock()
        mock.table.return_value = chain
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain

        def capture_insert(data):
            insert_calls.append(data)
            result = MagicMock()
            result.data = [{"id": f"msg-{len(insert_calls)}"}]
            chain2 = MagicMock()
            chain2.execute.return_value = result
            return chain2

        chain.insert.side_effect = capture_insert
        execute_result = MagicMock()
        execute_result.data = []
        chain.execute.return_value = execute_result
        return mock

    stream_text = "Please upload your file."
    chunks = [_make_stream_chunk(c) for c in stream_text]
    mock_stream = _async_iter(chunks)
    mock_completions = AsyncMock()
    mock_completions.create.return_value = mock_stream
    mock_or_client = MagicMock()
    mock_or_client.chat.completions = mock_completions
    mock_or_svc = MagicMock()
    mock_or_svc.client = mock_or_client

    with patch("app.services.gatekeeper.get_supabase_authed_client", side_effect=mock_get_client), \
         patch("app.services.gatekeeper.OpenRouterService", return_value=mock_or_svc):
        await _drain(run_gatekeeper(
            harness=harness,
            thread_id="thread-6",
            user_id="user-1",
            user_email="user@test.com",
            user_message="I want to begin.",
            token="tok",
            registry=None,
        ))

    # Both user and assistant inserts should have harness_mode = harness.name
    harness_mode_inserts = [d for d in insert_calls if "harness_mode" in d]
    assert len(harness_mode_inserts) >= 2

    for ins in harness_mode_inserts:
        assert ins["harness_mode"] == harness.name


# ---------------------------------------------------------------------------
# 10. test_run_gatekeeper_calls_start_run_on_trigger
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_gatekeeper_calls_start_run_on_trigger():
    harness = _make_harness(n_phases=2)

    call_count = [0]
    def mock_get_client(token):
        call_count[0] += 1
        if call_count[0] == 2:
            return _make_supabase_mock(return_data=[])
        return _make_supabase_mock(return_data=[{"id": f"row-{call_count[0]}"}])

    stream_text = "All set. [TRIGGER_HARNESS]"
    chunks = [_make_stream_chunk(c) for c in stream_text]
    mock_stream = _async_iter(chunks)
    mock_completions = AsyncMock()
    mock_completions.create.return_value = mock_stream
    mock_or_client = MagicMock()
    mock_or_client.chat.completions = mock_completions
    mock_or_svc = MagicMock()
    mock_or_svc.client = mock_or_client

    with patch("app.services.gatekeeper.get_supabase_authed_client", side_effect=mock_get_client), \
         patch("app.services.gatekeeper.OpenRouterService", return_value=mock_or_svc), \
         patch("app.services.gatekeeper.harness_runs_service.start_run", new_callable=AsyncMock, return_value="new-run-id") as mock_start:
        events = await _drain(run_gatekeeper(
            harness=harness,
            thread_id="thread-7",
            user_id="user-1",
            user_email="user@test.com",
            user_message="Ready.",
            token="tok",
            registry=None,
        ))

    mock_start.assert_called_once_with(
        thread_id="thread-7",
        user_id="user-1",
        user_email="user@test.com",
        harness_type=harness.name,
        input_file_ids=None,
        token="tok",
    )

    complete_events = [e for e in events if e["type"] == "gatekeeper_complete"]
    assert complete_events[0]["triggered"] is True
    assert complete_events[0]["harness_run_id"] == "new-run-id"


# ---------------------------------------------------------------------------
# 11. test_run_gatekeeper_complete_event_includes_phase_count (W8)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_gatekeeper_complete_event_includes_phase_count():
    """W8 fix: gatekeeper_complete includes phase_count == len(harness.phases)
    on BOTH the triggered and non-triggered paths."""
    # ---- triggered path (3 phases) ----
    harness_3 = _make_harness(n_phases=3)

    call_count = [0]

    def mock_get_client_triggered(token):
        call_count[0] += 1
        if call_count[0] == 2:
            return _make_supabase_mock(return_data=[])
        return _make_supabase_mock(return_data=[{"id": f"row-{call_count[0]}"}])

    stream_text_trigger = "Ready to go. [TRIGGER_HARNESS]"
    chunks_trigger = [_make_stream_chunk(c) for c in stream_text_trigger]
    mock_stream_trigger = _async_iter(chunks_trigger)
    mock_completions_t = AsyncMock()
    mock_completions_t.create.return_value = mock_stream_trigger
    mock_or_client_t = MagicMock()
    mock_or_client_t.chat.completions = mock_completions_t
    mock_or_svc_t = MagicMock()
    mock_or_svc_t.client = mock_or_client_t

    with patch("app.services.gatekeeper.get_supabase_authed_client", side_effect=mock_get_client_triggered), \
         patch("app.services.gatekeeper.OpenRouterService", return_value=mock_or_svc_t), \
         patch("app.services.gatekeeper.harness_runs_service.start_run", new_callable=AsyncMock, return_value="run-3"):
        events_triggered = await _drain(run_gatekeeper(
            harness=harness_3,
            thread_id="thread-w8-1",
            user_id="user-1",
            user_email="user@test.com",
            user_message="Go.",
            token="tok",
            registry=None,
        ))

    complete_triggered = [e for e in events_triggered if e["type"] == "gatekeeper_complete"]
    assert len(complete_triggered) == 1
    assert complete_triggered[0]["phase_count"] == 3
    assert complete_triggered[0]["triggered"] is True

    # ---- non-triggered path (3 phases) ----
    call_count2 = [0]

    def mock_get_client_no_trigger(token):
        call_count2[0] += 1
        if call_count2[0] == 2:
            return _make_supabase_mock(return_data=[])
        return _make_supabase_mock(return_data=[{"id": f"row2-{call_count2[0]}"}])

    stream_text_no = "Please upload your contract first."
    chunks_no = [_make_stream_chunk(c) for c in stream_text_no]
    mock_stream_no = _async_iter(chunks_no)
    mock_completions_no = AsyncMock()
    mock_completions_no.create.return_value = mock_stream_no
    mock_or_client_no = MagicMock()
    mock_or_client_no.chat.completions = mock_completions_no
    mock_or_svc_no = MagicMock()
    mock_or_svc_no.client = mock_or_client_no

    with patch("app.services.gatekeeper.get_supabase_authed_client", side_effect=mock_get_client_no_trigger), \
         patch("app.services.gatekeeper.OpenRouterService", return_value=mock_or_svc_no):
        events_no = await _drain(run_gatekeeper(
            harness=harness_3,
            thread_id="thread-w8-2",
            user_id="user-1",
            user_email="user@test.com",
            user_message="Let's start.",
            token="tok",
            registry=None,
        ))

    complete_no = [e for e in events_no if e["type"] == "gatekeeper_complete"]
    assert len(complete_no) == 1
    assert complete_no[0]["phase_count"] == 3
    assert complete_no[0]["triggered"] is False


# ---------------------------------------------------------------------------
# CR-01 regression: test_run_gatekeeper_sentinel_with_9_trailing_spaces_no_leak
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_gatekeeper_sentinel_with_9_trailing_spaces_no_leak():
    """CR-01 regression: 9 trailing spaces after sentinel must not leak [TRIGGER_HARNESS] to delta events."""
    harness = _make_harness(n_phases=2)

    call_count = [0]
    def mock_get_client(token):
        call_count[0] += 1
        if call_count[0] == 2:
            return _make_supabase_mock(return_data=[])
        return _make_supabase_mock(return_data=[{"id": f"row-{call_count[0]}"}])

    # 9 trailing spaces — old _WINDOW_SIZE=25 was insufficient (17+9=26 > 25)
    stream_text = "Ready to begin. [TRIGGER_HARNESS]" + " " * 9
    chunks = [_make_stream_chunk(c) for c in stream_text]
    mock_stream = _async_iter(chunks)
    mock_completions = AsyncMock()
    mock_completions.create.return_value = mock_stream
    mock_or_client = MagicMock()
    mock_or_client.chat.completions = mock_completions
    mock_or_svc = MagicMock()
    mock_or_svc.client = mock_or_client

    with patch("app.services.gatekeeper.get_supabase_authed_client", side_effect=mock_get_client), \
         patch("app.services.gatekeeper.OpenRouterService", return_value=mock_or_svc), \
         patch("app.services.gatekeeper.harness_runs_service.start_run", new_callable=AsyncMock, return_value="run-cr01"):
        events = await _drain(run_gatekeeper(
            harness=harness,
            thread_id="thread-cr01",
            user_id="user-1",
            user_email="user@test.com",
            user_message="Start it.",
            token="tok",
            registry=None,
        ))

    # Sentinel must NOT appear in any delta event
    delta_text = "".join(e["content"] for e in events if e["type"] == "delta")
    assert "[TRIGGER_HARNESS]" not in delta_text

    # Trigger must have fired despite the trailing spaces
    complete_events = [e for e in events if e["type"] == "gatekeeper_complete"]
    assert len(complete_events) == 1
    assert complete_events[0]["triggered"] is True
