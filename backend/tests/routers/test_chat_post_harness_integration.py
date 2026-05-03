"""Phase 20 / Plan 20-05 — Integration tests for post-harness summary wiring in chat.py.

4 tests:
1. test_post_harness_fires_after_engine_completion
2. test_post_harness_skipped_when_run_fetch_fails
3. test_post_harness_summary_yields_delta_events_after_engine
4. test_post_harness_receives_same_registry_instance_as_engine  (B4)
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.harnesses.types import (
    HarnessDefinition,
    HarnessPrerequisites,
    PhaseDefinition,
    PhaseType,
)
from app.routers.chat import _gatekeeper_stream_wrapper


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_harness() -> HarnessDefinition:
    return HarnessDefinition(
        name="smoke-echo",
        display_name="Smoke Echo",
        prerequisites=HarnessPrerequisites(
            requires_upload=False,
            harness_intro="Smoke echo for testing.",
        ),
        phases=[
            PhaseDefinition(name="echo", phase_type=PhaseType.PROGRAMMATIC),
        ],
    )


def _make_sys_settings(redaction_on: bool = True) -> dict:
    return {"pii_redaction_enabled": redaction_on}


async def _drain(gen) -> list[str]:
    """Collect all SSE lines from an async generator."""
    events = []
    async for chunk in gen:
        events.append(chunk)
    return events


def _parse_events(sse_chunks: list[str]) -> list[dict]:
    """Parse SSE-formatted chunks into dicts."""
    result = []
    for chunk in sse_chunks:
        chunk = chunk.strip()
        if chunk.startswith("data: "):
            payload = chunk[len("data: "):]
            try:
                result.append(json.loads(payload))
            except json.JSONDecodeError:
                pass
    return result


# ---------------------------------------------------------------------------
# Test 1: post_harness fires after engine completion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_harness_fires_after_engine_completion(monkeypatch):
    """After harness_complete SSE event, summarize_harness_run must be invoked."""
    harness = _make_harness()

    # Mock gatekeeper: triggers harness with run_id
    async def _mock_gatekeeper(**kwargs):
        yield {"type": "delta", "content": "Starting harness now."}
        yield {
            "type": "gatekeeper_complete",
            "triggered": True,
            "harness_run_id": "run-001",
            "user_message_id": "um-1",
            "assistant_message_id": "am-1",
            "phase_count": 1,
        }

    monkeypatch.setattr("app.routers.chat.run_gatekeeper", _mock_gatekeeper)

    # Mock harness engine: yields harness_complete
    async def _mock_engine(**kwargs):
        yield {"type": "harness_phase_start", "phase": 0}
        yield {"type": "harness_phase_complete", "phase": 0}
        yield {"type": "harness_complete", "status": "completed", "harness_run_id": "run-001"}

    monkeypatch.setattr("app.routers.chat.run_harness_engine", _mock_engine)

    # Mock get_run_by_id: return completed run
    refreshed_run = {
        "id": "run-001",
        "harness_type": "smoke-echo",
        "phase_results": {"0": {"phase_name": "echo", "output": "hello"}},
    }
    mock_get_run_by_id = AsyncMock(return_value=refreshed_run)
    monkeypatch.setattr(
        "app.routers.chat.harness_runs_service.get_run_by_id",
        mock_get_run_by_id,
    )

    # Mock summarize_harness_run: track whether it was called
    summarize_called_with = {}
    async def _mock_summarize(**kwargs):
        summarize_called_with.update(kwargs)
        yield {"type": "delta", "content": "Summary here."}
        yield {"type": "summary_complete", "assistant_message_id": "sum-1"}

    monkeypatch.setattr("app.routers.chat.summarize_harness_run", _mock_summarize)

    # Mock registry build
    mock_registry = MagicMock(name="MockRegistry")
    monkeypatch.setattr(
        "app.routers.chat._get_or_build_conversation_registry",
        AsyncMock(return_value=mock_registry),
    )

    sse_chunks = await _drain(
        _gatekeeper_stream_wrapper(
            harness=harness,
            thread_id="thread-1",
            user_id="u-1",
            user_email="u@e.com",
            user_message="go",
            token="tok",
            sys_settings=_make_sys_settings(),
        )
    )

    # summarize_harness_run must have been called
    assert summarize_called_with, "summarize_harness_run was not called"
    assert summarize_called_with["harness_run"]["id"] == "run-001"

    # mock_get_run_by_id must have been called with the correct run_id
    mock_get_run_by_id.assert_called_once_with(run_id="run-001", token="tok")


# ---------------------------------------------------------------------------
# Test 2: post_harness skipped when run fetch fails (get_run_by_id returns None)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_harness_skipped_when_run_fetch_fails(monkeypatch):
    """When get_run_by_id returns None, summarize_harness_run is NOT called."""
    harness = _make_harness()

    async def _mock_gatekeeper(**kwargs):
        yield {"type": "delta", "content": "go"}
        yield {
            "type": "gatekeeper_complete",
            "triggered": True,
            "harness_run_id": "run-002",
            "user_message_id": "um-1",
            "assistant_message_id": "am-1",
            "phase_count": 1,
        }

    monkeypatch.setattr("app.routers.chat.run_gatekeeper", _mock_gatekeeper)

    async def _mock_engine(**kwargs):
        yield {"type": "harness_complete", "status": "completed", "harness_run_id": "run-002"}

    monkeypatch.setattr("app.routers.chat.run_harness_engine", _mock_engine)

    # get_run_by_id returns None → simulate fetch failure
    monkeypatch.setattr(
        "app.routers.chat.harness_runs_service.get_run_by_id",
        AsyncMock(return_value=None),
    )

    summarize_called = False

    async def _mock_summarize(**kwargs):
        nonlocal summarize_called
        summarize_called = True
        yield {"type": "summary_complete", "assistant_message_id": None}

    monkeypatch.setattr("app.routers.chat.summarize_harness_run", _mock_summarize)

    monkeypatch.setattr(
        "app.routers.chat._get_or_build_conversation_registry",
        AsyncMock(return_value=None),
    )

    sse_chunks = await _drain(
        _gatekeeper_stream_wrapper(
            harness=harness,
            thread_id="thread-1",
            user_id="u-1",
            user_email="u@e.com",
            user_message="go",
            token="tok",
            sys_settings=_make_sys_settings(),
        )
    )

    # summarize must NOT have been called
    assert not summarize_called, "summarize_harness_run must not be called when run fetch returns None"

    # done event must still be emitted
    events = _parse_events(sse_chunks)
    types = [e["type"] for e in events]
    assert "done" in types


# ---------------------------------------------------------------------------
# Test 3: SSE event order — harness_complete → delta (summary) → summary_complete → done
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_harness_summary_yields_delta_events_after_engine(monkeypatch):
    """Full pipeline: assert SSE event order harness_complete → delta → summary_complete → done."""
    harness = _make_harness()

    async def _mock_gatekeeper(**kwargs):
        yield {"type": "delta", "content": "starting"}
        yield {
            "type": "gatekeeper_complete",
            "triggered": True,
            "harness_run_id": "run-003",
            "user_message_id": "um-1",
            "assistant_message_id": "am-1",
            "phase_count": 1,
        }

    monkeypatch.setattr("app.routers.chat.run_gatekeeper", _mock_gatekeeper)

    async def _mock_engine(**kwargs):
        yield {"type": "harness_phase_start", "phase": 0}
        yield {"type": "harness_complete", "status": "completed", "harness_run_id": "run-003"}

    monkeypatch.setattr("app.routers.chat.run_harness_engine", _mock_engine)

    refreshed = {"id": "run-003", "harness_type": "smoke-echo", "phase_results": {}}
    monkeypatch.setattr(
        "app.routers.chat.harness_runs_service.get_run_by_id",
        AsyncMock(return_value=refreshed),
    )

    async def _mock_summarize(**kwargs):
        yield {"type": "delta", "content": "Here is the summary."}
        yield {"type": "summary_complete", "assistant_message_id": "sum-abc"}

    monkeypatch.setattr("app.routers.chat.summarize_harness_run", _mock_summarize)

    monkeypatch.setattr(
        "app.routers.chat._get_or_build_conversation_registry",
        AsyncMock(return_value=None),
    )

    sse_chunks = await _drain(
        _gatekeeper_stream_wrapper(
            harness=harness,
            thread_id="thread-1",
            user_id="u-1",
            user_email="u@e.com",
            user_message="go",
            token="tok",
            sys_settings=_make_sys_settings(),
        )
    )

    events = _parse_events(sse_chunks)
    types = [e["type"] for e in events]

    # Required events must all be present
    assert "harness_complete" in types
    assert "delta" in types
    assert "summary_complete" in types
    assert "done" in types

    # harness_complete must come before the summary delta
    hc_idx = next(i for i, e in enumerate(events) if e["type"] == "harness_complete")
    delta_idx = next(
        (i for i, e in enumerate(events) if e["type"] == "delta" and "summary" in e.get("content", "").lower()),
        None,
    )
    sc_idx = next(i for i, e in enumerate(events) if e["type"] == "summary_complete")
    done_idx = next(i for i, e in enumerate(events) if e["type"] == "done")

    assert hc_idx < sc_idx < done_idx, "harness_complete must precede summary_complete, which must precede done"
    if delta_idx is not None:
        assert hc_idx < delta_idx, "harness_complete must precede summary delta"


# ---------------------------------------------------------------------------
# Test 4 (B4): both engine and summarize_harness_run receive the SAME registry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_harness_receives_same_registry_instance_as_engine(monkeypatch):
    """B4 invariant: the registry passed to run_harness_engine and to
    summarize_harness_run must be the EXACT same object (identity).

    Sentinel: _get_or_build_conversation_registry returns a named MagicMock;
    both consumers are expected to receive id(sentinel) == id(registry they got).
    """
    harness = _make_harness()

    # Sentinel registry
    registry_sentinel = MagicMock(name="RegistrySentinel")

    monkeypatch.setattr(
        "app.routers.chat._get_or_build_conversation_registry",
        AsyncMock(return_value=registry_sentinel),
    )

    # Track the registry received by engine and summarize
    engine_registry_received = {}
    summarize_registry_received = {}

    async def _mock_gatekeeper(**kwargs):
        yield {"type": "delta", "content": "go"}
        yield {
            "type": "gatekeeper_complete",
            "triggered": True,
            "harness_run_id": "run-b4",
            "user_message_id": "um",
            "assistant_message_id": "am",
            "phase_count": 1,
        }

    monkeypatch.setattr("app.routers.chat.run_gatekeeper", _mock_gatekeeper)

    async def _mock_engine(**kwargs):
        engine_registry_received["registry"] = kwargs.get("registry")
        yield {"type": "harness_complete", "status": "completed", "harness_run_id": "run-b4"}

    monkeypatch.setattr("app.routers.chat.run_harness_engine", _mock_engine)

    refreshed = {"id": "run-b4", "harness_type": "smoke-echo", "phase_results": {}}
    monkeypatch.setattr(
        "app.routers.chat.harness_runs_service.get_run_by_id",
        AsyncMock(return_value=refreshed),
    )

    async def _mock_summarize(**kwargs):
        summarize_registry_received["registry"] = kwargs.get("registry")
        yield {"type": "summary_complete", "assistant_message_id": "sum-b4"}

    monkeypatch.setattr("app.routers.chat.summarize_harness_run", _mock_summarize)

    await _drain(
        _gatekeeper_stream_wrapper(
            harness=harness,
            thread_id="thread-b4",
            user_id="u-b4",
            user_email="u@b4.com",
            user_message="go",
            token="tok-b4",
            sys_settings=_make_sys_settings(),
        )
    )

    # Both consumers must have received a registry
    assert "registry" in engine_registry_received, "engine did not receive a registry kwarg"
    assert "registry" in summarize_registry_received, "summarize_harness_run did not receive a registry kwarg"

    # Identity check: SAME object, not just equal
    assert engine_registry_received["registry"] is registry_sentinel, (
        "run_harness_engine received a different registry object than the sentinel"
    )
    assert summarize_registry_received["registry"] is registry_sentinel, (
        "summarize_harness_run received a different registry object than the sentinel — B4 violated"
    )
    assert engine_registry_received["registry"] is summarize_registry_received["registry"], (
        "engine and summarize_harness_run received different registry instances — B4 invariant broken"
    )
