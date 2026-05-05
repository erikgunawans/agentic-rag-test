"""Phase 22 / Plan 22-05 — Gatekeeper trigger eval suite (D-22-04).

Parametrized eval over backend/tests/data/gatekeeper_eval_set.json (15 phrasings):
  5 should-trigger Contract Review
  5 should-trigger Smoke Echo  (Phase 21 regression guard)
  5 should-NOT-trigger

Mocked-LLM CI test — verifies SYSTEM PROMPT structure is correct, not the LLM
intelligence. Real-LLM eval lives in backend/scripts/eval_gatekeeper_live.py.

Test strategy:
  The mock LLM yields [TRIGGER_HARNESS] as the final token IFF expected_triggered=True.
  For not-triggered phrasings, it yields a polite clarification (no sentinel).
  This verifies:
    1. The gatekeeper_complete event's `triggered` field matches expected_triggered.
    2. The system prompt passed to the LLM contains the correct workspace block.
    3. The system prompt contains the harness display_name.
"""
from __future__ import annotations

import json
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.types import HarnessDefinition, HarnessPrerequisites, PhaseDefinition, PhaseType
from app.services.gatekeeper import SENTINEL, run_gatekeeper

EVAL_SET_PATH = pathlib.Path(__file__).parents[1] / "data" / "gatekeeper_eval_set.json"
EVAL_SET = json.loads(EVAL_SET_PATH.read_text())
PHRASINGS = EVAL_SET["phrasings"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_harness(harness_name: str) -> HarnessDefinition:
    """Build a HarnessDefinition from eval set metadata."""
    meta = EVAL_SET["harnesses"][harness_name]
    display_name = meta["display_name"]
    prereqs = HarnessPrerequisites(
        requires_upload=True,
        upload_description="any DOCX or PDF",
        accepted_mime_types=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        min_files=meta["min_files"],
        max_files=meta["max_files"],
        harness_intro=f"This is the {display_name} harness.",
    )
    return HarnessDefinition(
        name=harness_name,
        display_name=display_name,
        prerequisites=prereqs,
        phases=[
            PhaseDefinition(name="Phase 1", phase_type=PhaseType.PROGRAMMATIC),
        ],
    )


async def _drain(gen) -> list[dict]:
    events = []
    async for ev in gen:
        events.append(ev)
    return events


def _make_stream_chunk(content: str):
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = content
    return chunk


async def _async_iter(items):
    for item in items:
        yield item


def _make_supabase_chain_mock(return_data=None):
    """Fluent Supabase query-builder mock, returns row id on insert."""
    mock = MagicMock()
    chain = MagicMock()
    mock.table.return_value = chain
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    result = MagicMock()
    result.data = return_data if return_data is not None else [{"id": "row-1"}]
    chain.execute.return_value = result
    return mock


def _make_llm_stream(triggered: bool):
    """Return an async iterator yielding LLM chunks.

    If triggered=True, end with [TRIGGER_HARNESS] sentinel.
    Otherwise, yield a polite clarification message.
    """
    if triggered:
        chunks = list("Great, I can see your file is ready. ") + [SENTINEL]
    else:
        chunks = list("Please upload your contract file to get started.")
    return _async_iter([_make_stream_chunk(c) for c in chunks])


def _make_client_factory():
    """Returns a factory that yields supabase mocks in call order:
       call 1 → persist user msg (returns id row)
       call 2 → load history (returns [])
       call 3 → persist assistant msg (returns id row)
    """
    call_count = [0]

    def factory(token):
        call_count[0] += 1
        if call_count[0] == 2:
            # load_gatekeeper_history — empty list
            return _make_supabase_chain_mock(return_data=[])
        return _make_supabase_chain_mock(return_data=[{"id": f"row-{call_count[0]}"}])

    return factory


# ---------------------------------------------------------------------------
# Parametrized eval test — 15 phrasings, mocked LLM
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("phrasing", PHRASINGS, ids=[p["id"] for p in PHRASINGS])
async def test_gatekeeper_trigger_matches_expected(phrasing):
    """For each phrasing: assert triggered==expected_triggered and system prompt structure."""
    harness = _build_harness(phrasing["harness"])
    workspace_fixture = phrasing["workspace"]
    expected_triggered = phrasing["expected_triggered"]

    # Capture system prompt passed to the LLM
    captured_system_prompt: list[str] = []

    # Build a mock completions.create that records the messages arg and returns fixture stream
    async def mock_create(messages, model, stream, **kwargs):
        system_msgs = [m["content"] for m in messages if m["role"] == "system"]
        if system_msgs:
            captured_system_prompt.append(system_msgs[0])
        return _make_llm_stream(expected_triggered)

    mock_completions = MagicMock()
    mock_completions.create = mock_create

    mock_or_client = MagicMock()
    mock_or_client.chat.completions = mock_completions

    mock_or_svc = MagicMock()
    mock_or_svc.client = mock_or_client

    # Mock WorkspaceService to return the fixture's workspace list
    mock_ws_instance = MagicMock()
    mock_ws_instance.list_files = AsyncMock(return_value=workspace_fixture)

    with patch("app.services.gatekeeper.get_supabase_authed_client",
               side_effect=_make_client_factory()), \
         patch("app.services.gatekeeper.OpenRouterService", return_value=mock_or_svc), \
         patch("app.services.gatekeeper.WorkspaceService", return_value=mock_ws_instance), \
         patch("app.services.gatekeeper.harness_runs_service.start_run",
               new_callable=AsyncMock, return_value="run-id"):

        events = await _drain(run_gatekeeper(
            harness=harness,
            thread_id=f"eval-thread-{phrasing['id']}",
            user_id="eval-user",
            user_email="eval@test.com",
            user_message=phrasing["text"],
            token="eval-token",
            registry=None,
        ))

    # --- Primary assertion: triggered matches expected ---
    complete_events = [e for e in events if e["type"] == "gatekeeper_complete"]
    assert len(complete_events) == 1, (
        f"[{phrasing['id']}] expected 1 gatekeeper_complete event, got {len(complete_events)}"
    )
    actual_triggered = complete_events[0]["triggered"]
    assert actual_triggered == expected_triggered, (
        f"[{phrasing['id']}] triggered={actual_triggered!r} but expected={expected_triggered!r}. "
        f"rationale: {phrasing['rationale']}"
    )

    # --- Structural assertions on the system prompt ---
    assert len(captured_system_prompt) == 1, (
        f"[{phrasing['id']}] expected system prompt to be captured once"
    )
    sys_prompt = captured_system_prompt[0]

    # Harness display_name must appear in system prompt
    display_name = EVAL_SET["harnesses"][phrasing["harness"]]["display_name"]
    assert display_name in sys_prompt, (
        f"[{phrasing['id']}] display_name '{display_name}' not in system prompt"
    )

    # Workspace block must reflect the fixture
    if not workspace_fixture:
        assert "(empty" in sys_prompt, (
            f"[{phrasing['id']}] empty workspace should produce '(empty...' block"
        )
    else:
        for ws_file in workspace_fixture:
            fp = ws_file["file_path"]
            kb = ws_file["size_bytes"] // 1024
            assert fp in sys_prompt, (
                f"[{phrasing['id']}] file_path '{fp}' not in system prompt workspace block"
            )
            assert f"{kb} KB" in sys_prompt, (
                f"[{phrasing['id']}] size '{kb} KB' not in system prompt workspace block"
            )
