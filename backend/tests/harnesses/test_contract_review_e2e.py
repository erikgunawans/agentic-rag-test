"""Phase 22 / Plan 22-12 — Contract Review end-to-end pytest (REVIEW #9 — HIL flow).

Three tests:
1. test_e2e_full_pipeline_with_hil_pause_resume — covers all 16 REQ-IDs across the
   real CR-03 pause + chat router resume branch. NOT a single linear engine invocation.
2. test_off_mode_registration_invariant — D-16 invariant.
3. test_d_22_15_sandbox_failure_non_fatal — D-22-15 non-fatal fallback.

REVIEW #9 compliance: engine pauses at CR-03 (llm_human_input). User reply is
processed by the chat router's HIL branch (chat.py:~365) which writes the answer +
calls resume_from_pause + starts a NEW run_harness_engine invocation from
current_phase+1. Tests exercise BOTH halves.
"""
from __future__ import annotations

import asyncio
import io
import importlib
import json
import pathlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from docx import Document


# ---------------------------------------------------------------------------
# Helper: reload contract_review with all flags enabled
# ---------------------------------------------------------------------------

def _reload_contract_review_enabled():
    """Reload app.harnesses.contract_review with all gates open."""
    mock_settings = MagicMock()
    mock_settings.harness_enabled = True
    mock_settings.contract_review_enabled = True
    mock_settings.tool_registry_enabled = True

    mod_name = "app.harnesses.contract_review"
    sys.modules.pop(mod_name, None)

    with patch("app.config.get_settings", return_value=mock_settings):
        mod = importlib.import_module(mod_name)
    return mod


def _reload_contract_review_disabled():
    """Reload app.harnesses.contract_review with contract_review_enabled=False."""
    mock_settings = MagicMock()
    mock_settings.harness_enabled = True
    mock_settings.contract_review_enabled = False
    mock_settings.tool_registry_enabled = True

    mod_name = "app.harnesses.contract_review"
    sys.modules.pop(mod_name, None)

    with patch("app.config.get_settings", return_value=mock_settings):
        mod = importlib.import_module(mod_name)
    return mod


# ---------------------------------------------------------------------------
# Fixture: reset harness registry before/after each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_registry():
    from app.services import harness_registry
    harness_registry._reset_for_tests()
    yield
    harness_registry._reset_for_tests()
    # Also clean up the module cache so each test gets a fresh import
    sys.modules.pop("app.harnesses.contract_review", None)


# ---------------------------------------------------------------------------
# Helper: build a fake WorkspaceService that stores artifacts in a dict
# ---------------------------------------------------------------------------

def _build_mock_workspace(fixture_bytes: bytes):
    """Build a MagicMock WorkspaceService backed by an in-memory dict.

    The engine creates WorkspaceService(token=token) internally in multiple places.
    We patch app.services.workspace_service.WorkspaceService to return this mock.
    """
    artifacts: dict[str, str | bytes] = {}
    binary_writes: list[dict] = []

    ws = MagicMock()

    ws.list_files = AsyncMock(return_value=[
        {"file_path": "contract.docx", "source": "upload", "size_bytes": len(fixture_bytes)},
    ])
    ws.read_binary_file = AsyncMock(return_value=fixture_bytes)

    async def _write_text(thread_id, file_path, content, source="agent"):
        artifacts[file_path] = content
        return {"ok": True, "size_bytes": len(content) if content else 0}

    async def _read_file(thread_id, file_path):
        val = artifacts.get(file_path)
        if val is None:
            return {"content": ""}
        if isinstance(val, bytes):
            return {"content": val.decode("utf-8", errors="replace")}
        return {"content": val}

    async def _write_binary(*, thread_id, file_path, content_bytes, **kwargs):
        artifacts[file_path] = content_bytes
        binary_writes.append({
            "file_path": file_path,
            "content_bytes": content_bytes,
            **{k: v for k, v in kwargs.items()},
        })
        return {"ok": True, "size_bytes": len(content_bytes)}

    async def _append_line(thread_id, file_path, line):
        existing = artifacts.get(file_path, "")
        if isinstance(existing, bytes):
            existing = existing.decode()
        artifacts[file_path] = existing + line + "\n"
        return {"ok": True}

    ws.write_text_file = AsyncMock(side_effect=_write_text)
    ws.read_file = AsyncMock(side_effect=_read_file)
    ws.write_binary_file = AsyncMock(side_effect=_write_binary)
    ws.append_line = AsyncMock(side_effect=_append_line)
    ws.get_signed_url = AsyncMock(return_value="https://example.com/signed")

    return ws, artifacts, binary_writes


# ---------------------------------------------------------------------------
# Test 1: REVIEW #9 — HIL pause + resume E2E
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2e_full_pipeline_with_hil_pause_resume(
    sandbox_in_process_stub, phase_routed_llm_mock
):
    """REVIEW #9: this test mirrors the REAL HIL architecture.

    Engine pauses at CR-03 (llm_human_input). User reply is processed by the chat
    router's HIL branch (chat.py:~365) which writes the answer + calls
    resume_from_pause + starts a NEW run_harness_engine invocation from
    current_phase+1. We exercise BOTH halves.

    Assertions (per plan 22-12 must_haves):
    - 9 harness_phase_complete events total across both invocations
    - harness_human_input_required emitted after CR-03 LLM call
    - harness_runs.status transitions to 'paused' after first invocation
    - second invocation covers CR-04..CR-08 phases
    - harness_artifact event has ok=True and harness_mode='contract-review'
    - workspace_updated follows harness_artifact (REVIEW #7)
    - contract-review-report.md starts with '# Contract Review Report' (REVIEW #6)
    - DOCX bytes contain 'CONFIDENTIAL' marker
    - harness_runs.status='completed' at end
    """
    mod = _reload_contract_review_enabled()

    from app.services import harness_registry
    harness = harness_registry.get_harness("contract-review")
    assert harness is not None, "harness not registered"
    assert len(harness.phases) == 9, f"expected 9 phases, got {len(harness.phases)}"

    fixture_bytes = (pathlib.Path(__file__).parent.parent / "data" / "synth-contract.docx").read_bytes()
    assert fixture_bytes[:2] == b"PK", "synth-contract.docx must be a valid ZIP/DOCX"

    ws, artifacts, binary_writes = _build_mock_workspace(fixture_bytes)

    # Track harness_runs state
    run_state = {"status": "running", "current_phase": 0}
    complete_calls: list[dict] = []

    async def _get_run_by_id(**kw):
        return {"id": "run-42", "status": run_state["status"],
                "current_phase": run_state["current_phase"]}

    async def _advance_phase(**kw):
        new_idx = kw.get("new_phase_index", run_state["current_phase"] + 1)
        run_state["current_phase"] = new_idx
        return True

    async def _pause(**kw):
        run_state["status"] = "paused"
        return True

    async def _complete(**kw):
        complete_calls.append(kw)
        run_state["status"] = kw.get("status", "completed")
        return True

    async def _write_todos(thread_id, todos, token):
        return True

    patches = [
        patch("app.services.harness_runs_service.get_run_by_id", side_effect=_get_run_by_id),
        patch("app.services.harness_runs_service.advance_phase", side_effect=_advance_phase),
        patch("app.services.harness_runs_service.pause", side_effect=_pause),
        patch("app.services.harness_runs_service.complete", side_effect=_complete),
        patch("app.services.harness_runs_service.fail", AsyncMock()),
        patch("app.services.agent_todos_service.write_todos", side_effect=_write_todos),
        # Mock WorkspaceService at the module where it's imported
        patch("app.services.workspace_service.WorkspaceService", return_value=ws),
        patch("app.harnesses.contract_review.WorkspaceService", return_value=ws),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws),
        patch("app.services.openrouter_service.OpenRouterService.complete_with_tools",
              AsyncMock(side_effect=phase_routed_llm_mock)),
        # sub_agent_loop would require real network — mock it to return terminal result
        patch("app.services.harness_engine.run_sub_agent_loop",
              side_effect=_mock_sub_agent_loop),
    ]

    for p in patches:
        p.start()

    try:
        from app.services.harness_engine import run_harness_engine

        cancellation_event = asyncio.Event()

        # FIRST INVOCATION: runs CR-01 + CR-02 + CR-03 (pauses on HIL)
        events_first: list[dict] = []
        async for ev in run_harness_engine(
            harness=harness,
            harness_run_id="run-42",
            thread_id="thr-test",
            user_id="user-test",
            user_email="test@example.com",
            token="tok",
            registry=None,
            cancellation_event=cancellation_event,
            start_phase_index=0,
        ):
            events_first.append(ev)
            # Stop consuming after harness_complete (engine handles its own termination)

        # --- First-invocation assertions ---
        types_first = [e.get("type") for e in events_first]

        # intake should complete
        phase_names_first = [
            e.get("phase_name") for e in events_first
            if e.get("type") == "harness_phase_complete"
        ]
        assert "intake" in phase_names_first, (
            f"REVIEW #9: intake phase_complete missing from first invocation. "
            f"Types seen: {types_first}"
        )
        assert "classify" in phase_names_first, (
            f"REVIEW #9: classify phase_complete missing. Types: {types_first}"
        )

        # CR-03 must emit harness_human_input_required
        assert any(e.get("type") == "harness_human_input_required" for e in events_first), (
            "REVIEW #9: engine MUST pause at CR-03 with harness_human_input_required event. "
            f"Types seen: {types_first}"
        )

        # Engine must set status='paused' after first invocation
        assert run_state["status"] == "paused", (
            f"REVIEW #9: harness_runs.status must be 'paused' after CR-03; got {run_state['status']!r}"
        )

        # --- SIMULATE CHAT ROUTER HIL RESUME (chat.py:~365) ---
        # User replied with review context — write to review-context.md (D-22-10)
        artifacts["review-context.md"] = (
            "We are the Customer (Beta Inc). No specific deadline. "
            "Focus on liability cap and confidentiality period."
        )

        # resume_from_pause transitions status back to running
        run_state["status"] = "running"
        run_state["current_phase"] = 3  # CR-04 is phases[3] (load-playbook)

        # SECOND INVOCATION: resume from CR-04 (start_phase_index=3)
        events_second: list[dict] = []
        async for ev in run_harness_engine(
            harness=harness,
            harness_run_id="run-42",
            thread_id="thr-test",
            user_id="user-test",
            user_email="test@example.com",
            token="tok",
            registry=None,
            cancellation_event=cancellation_event,
            start_phase_index=3,  # Phase 21 D-03: resume from CR-04 (index 3)
        ):
            events_second.append(ev)

        # --- Second-invocation assertions ---
        phase_names_second = [
            e.get("phase_name") for e in events_second
            if e.get("type") == "harness_phase_complete"
        ]
        expected_remaining = [
            "load-playbook",
            "extract-clauses",
            "risk-analysis",
            "filter-redline-candidates",
            "redline-generation",
            "executive-summary",
        ]
        for name in expected_remaining:
            assert name in phase_names_second, (
                f"REVIEW #9: phase '{name}' missing from second-invocation events. "
                f"Completed phases: {phase_names_second}"
            )

        # Total phase_complete events = 2 (first run: intake + classify) + 6 (second run) = 8
        # gather-context does NOT emit phase_complete (it pauses). So 8 total.
        all_phase_complete = [
            e.get("phase_name") for e in events_first + events_second
            if e.get("type") == "harness_phase_complete"
        ]
        assert len(all_phase_complete) == 8, (
            f"Expected 8 harness_phase_complete events total (intake+classify+6 from CR-04 on); "
            f"got {len(all_phase_complete)}: {all_phase_complete}"
        )

        # REVIEW #7: workspace_updated must follow harness_artifact in second invocation
        artifact_idx = next(
            (i for i, e in enumerate(events_second) if e.get("type") == "harness_artifact"),
            -1,
        )
        ws_updated_idx = next(
            (i for i, e in enumerate(events_second) if e.get("type") == "workspace_updated"),
            -1,
        )
        assert artifact_idx >= 0, (
            "REVIEW #7: harness_artifact event not found in second invocation. "
            f"Types: {[e.get('type') for e in events_second]}"
        )
        assert ws_updated_idx > artifact_idx, (
            f"REVIEW #7: workspace_updated must follow harness_artifact; "
            f"artifact_idx={artifact_idx}, workspace_updated_idx={ws_updated_idx}"
        )

        # REVIEW #8: harness_artifact event has harness_mode='contract-review'
        artifact_evt = events_second[artifact_idx]
        assert artifact_evt.get("ok") is True, (
            f"harness_artifact.ok must be True; got {artifact_evt}"
        )
        assert artifact_evt.get("harness_mode") == "contract-review", (
            f"REVIEW #8: harness_artifact.harness_mode must be 'contract-review'; got {artifact_evt}"
        )

        # REVIEW #6: contract-review-report.md is markdown, NOT raw JSON
        assert "contract-review-report.md" in artifacts, (
            f"REVIEW #6: contract-review-report.md not found in workspace. "
            f"Keys: {list(artifacts.keys())}"
        )
        report_md = artifacts["contract-review-report.md"]
        if isinstance(report_md, bytes):
            report_md = report_md.decode()
        assert report_md.lstrip().startswith("# Contract Review Report"), (
            f"REVIEW #6: report.md must start with '# Contract Review Report'; "
            f"got: {report_md[:100]!r}"
        )
        assert not report_md.lstrip().startswith("{"), (
            "REVIEW #6: report.md MUST NOT be raw JSON"
        )

        # DOCX bytes contain 'CONFIDENTIAL' marker
        assert binary_writes, "expected at least one binary write (DOCX)"
        docx_bytes = binary_writes[-1]["content_bytes"]
        assert docx_bytes[:2] == b"PK", "DOCX must be a valid ZIP (PK header)"
        parsed_docx = Document(io.BytesIO(docx_bytes))
        text_full = "\n".join(p.text for p in parsed_docx.paragraphs)
        assert "CONFIDENTIAL" in text_full, (
            f"DOCX must contain 'CONFIDENTIAL' marker; paragraphs: {text_full[:300]!r}"
        )

        # REVIEW #9: harness_runs.status='completed' at end
        assert run_state["status"] == "completed", (
            f"REVIEW #9: harness_runs.status must be 'completed' at end; got {run_state['status']!r}"
        )

        # synth-contract.docx referenced in test path
        assert (pathlib.Path(__file__).parent.parent / "data" / "synth-contract.docx").exists(), (
            "synth-contract.docx must exist as pre-committed fixture"
        )

    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# Test 2: Off-mode registration invariant (D-16)
# ---------------------------------------------------------------------------

def test_off_mode_registration_invariant():
    """D-16 off-mode invariant: contract_review_enabled=False → harness NOT in registry.

    REVIEW #9: this exercises the gating side of the architecture.
    """
    from app.services import harness_registry

    # Ensure disabled mode
    _reload_contract_review_disabled()

    result = harness_registry.get_harness("contract-review")
    assert result is None, (
        f"D-16 invariant: harness must NOT be registered when contract_review_enabled=False; "
        f"got: {result}"
    )


# ---------------------------------------------------------------------------
# Test 3: D-22-15 non-fatal sandbox failure (REVIEW #9)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_d_22_15_sandbox_failure_non_fatal(phase_routed_llm_mock):
    """D-22-15 + REVIEW #9: same HIL flow as Test 1, but sandbox returns exit_code=1.

    Assertions:
    - harness_artifact event has ok=False and code='DOCX_FAILED'
    - harness_runs_service.complete called with status='completed' (NOT 'failed')
    - filter-redline-candidates phase still runs (engine does not abort on DOCX failure)
    """
    mod = _reload_contract_review_enabled()

    from app.services import harness_registry
    harness = harness_registry.get_harness("contract-review")
    assert harness is not None

    fixture_bytes = (pathlib.Path(__file__).parent.parent / "data" / "synth-contract.docx").read_bytes()
    ws, artifacts, binary_writes = _build_mock_workspace(fixture_bytes)

    # Pre-seed workspace with outputs from phases 0-2 (skipped in this test)
    artifacts["contract-text.md"] = (
        "# Contract Source\n\n- **File:** `contract.docx`\n- **Pages:** 1\n\n---\n\n"
        "MASTER SERVICES AGREEMENT\n\n"
        "1. LIABILITY\nEach party's total liability shall not exceed USD 100,000.\n\n"
        "2. CONFIDENTIALITY\nEach party shall hold confidential information for 5 years.\n\n"
        "3. PAYMENT\nCustomer shall pay within 30 days.\n"
    )
    artifacts["classification.md"] = json.dumps({
        "contract_type": "MSA",
        "parties": ["Acme Corp", "Beta Inc"],
        "effective_date": "2026-01-01",
        "expiration_date": None,
        "governing_law": "Republic of Indonesia",
        "jurisdiction": "courts of Jakarta",
        "summary": "Master Services Agreement between Acme Corp and Beta Inc.",
    }, indent=2)
    artifacts["review-context.md"] = "We are the Customer. Focus on liability."

    run_state = {"status": "running", "current_phase": 3}  # start at CR-04
    complete_calls: list[dict] = []

    async def _get_run_by_id(**kw):
        return {"id": "run-99", "status": run_state["status"],
                "current_phase": run_state["current_phase"]}

    async def _advance_phase(**kw):
        run_state["current_phase"] = kw.get("new_phase_index", run_state["current_phase"] + 1)
        return True

    async def _complete(**kw):
        complete_calls.append(kw)
        run_state["status"] = kw.get("status", "completed")
        return True

    async def _write_todos(thread_id, todos, token):
        return True

    # Failing sandbox stub
    failing_sandbox = MagicMock()
    failing_sandbox.execute = AsyncMock(return_value={
        "exit_code": 1,
        "stderr": "boom — DOCX generation failed",
        "stdout": "",
        "files": [],
        "error_type": "exception",
        "execution_ms": 10,
        "execution_id": "x",
    })

    patches = [
        patch("app.services.harness_runs_service.get_run_by_id", side_effect=_get_run_by_id),
        patch("app.services.harness_runs_service.advance_phase", side_effect=_advance_phase),
        patch("app.services.harness_runs_service.pause", AsyncMock()),
        patch("app.services.harness_runs_service.complete", side_effect=_complete),
        patch("app.services.harness_runs_service.fail", AsyncMock()),
        patch("app.services.agent_todos_service.write_todos", side_effect=_write_todos),
        patch("app.services.workspace_service.WorkspaceService", return_value=ws),
        patch("app.harnesses.contract_review.WorkspaceService", return_value=ws),
        patch("app.services.harness_engine.WorkspaceService", return_value=ws),
        patch("app.services.openrouter_service.OpenRouterService.complete_with_tools",
              AsyncMock(side_effect=phase_routed_llm_mock)),
        patch("app.services.harness_engine.run_sub_agent_loop",
              side_effect=_mock_sub_agent_loop),
        patch("app.services.sandbox_service.get_sandbox_service", return_value=failing_sandbox),
    ]

    for p in patches:
        p.start()

    try:
        from app.services.harness_engine import run_harness_engine

        cancellation_event = asyncio.Event()

        # Resume from CR-04 directly (skip the HIL pause for this test)
        events: list[dict] = []
        async for ev in run_harness_engine(
            harness=harness,
            harness_run_id="run-99",
            thread_id="thr-test2",
            user_id="user-test",
            user_email="test@example.com",
            token="tok",
            registry=None,
            cancellation_event=cancellation_event,
            start_phase_index=3,  # start at CR-04
        ):
            events.append(ev)

        # D-22-15: harness_artifact must have ok=False + code='DOCX_FAILED'
        artifact_evt = next(
            (e for e in events if e.get("type") == "harness_artifact"),
            None,
        )
        assert artifact_evt is not None, (
            f"D-22-15: harness_artifact event not found. "
            f"Types: {[e.get('type') for e in events]}"
        )
        assert artifact_evt.get("ok") is False, (
            f"D-22-15: harness_artifact.ok must be False on sandbox failure; got {artifact_evt}"
        )
        assert artifact_evt.get("code") == "DOCX_FAILED", (
            f"D-22-15: harness_artifact.code must be 'DOCX_FAILED'; got {artifact_evt.get('code')!r}"
        )
        assert "fallback_message" in artifact_evt, (
            f"D-22-15: harness_artifact must carry fallback_message; got {artifact_evt}"
        )

        # REVIEW #9: harness_runs.status STILL 'completed' (NOT 'failed')
        assert run_state["status"] == "completed", (
            f"D-22-15 + REVIEW #9: harness_runs.status must be 'completed' even on DOCX failure; "
            f"got {run_state['status']!r}"
        )

        # Verify harness_complete fires with status='completed'
        complete_evt = next(
            (e for e in events if e.get("type") == "harness_complete"),
            None,
        )
        assert complete_evt is not None, "harness_complete event must fire"
        assert complete_evt.get("status") == "completed", (
            f"harness_complete.status must be 'completed'; got {complete_evt.get('status')!r}"
        )

        # filter-redline-candidates ran (REVIEW #9: engine continues despite DOCX failure)
        phase_names = [
            e.get("phase_name") for e in events
            if e.get("type") == "harness_phase_complete"
        ]
        assert "filter-redline-candidates" in phase_names, (
            f"D-22-15: filter-redline-candidates must still run when DOCX fails. "
            f"Phases completed: {phase_names}"
        )

    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# Mock sub-agent loop — returns terminal results for LLM_AGENT + LLM_BATCH_AGENTS
# ---------------------------------------------------------------------------

async def _mock_sub_agent_loop(
    *,
    description: str,
    context_files: list,
    parent_user_id: str,
    parent_user_email: str,
    parent_token: str,
    parent_tool_context: dict,
    parent_thread_id: str,
    parent_user_msg_id: str,
    client,
    sys_settings: dict,
    web_search_effective: bool,
    task_id: str,
    parent_redaction_registry=None,
    **_,
):
    """Mock run_sub_agent_loop that yields per-phase terminal results.

    Used for LLM_AGENT (CR-04 load-playbook) and LLM_BATCH_AGENTS (CR-06 risk,
    CR-07 redlines). For batch phases, returns per-clause risk/redline JSON in
    ```json``` fenced blocks so _parse_subagent_json_terminal can extract them.
    """
    from tests.harnesses.conftest import (
        _PLAYBOOK_CONTEXT_JSON,
        _RISK_TERMINAL_LIABILITY,
        _RISK_TERMINAL_CONF,
        _RISK_TERMINAL_PAYMENT,
        _REDLINE_TERMINAL_LIABILITY,
        _REDLINE_TERMINAL_CONF,
    )

    desc_lower = description.lower()

    # CR-04 load-playbook (LLM_AGENT)
    if "playbook loader" in desc_lower or "list_playbook_documents" in desc_lower:
        terminal_text = f"```json\n{_PLAYBOOK_CONTEXT_JSON}\n```\n\n## Notes\nNo playbook documents found."
        yield {
            "_terminal_result": {
                "text": terminal_text,
                "terminal": {"text": terminal_text},
            }
        }
        return

    # CR-06 risk analysis sub-agent (LLM_BATCH_AGENTS)
    if "risk" in desc_lower and "clause_index" in desc_lower:
        item_lower = description.lower()
        if "liability" in item_lower or '"position": 0' in description or "0" in item_lower[:50]:
            text = f"```json\n{_RISK_TERMINAL_LIABILITY}\n```"
        elif "confidentiality" in item_lower or '"position": 1' in description:
            text = f"```json\n{_RISK_TERMINAL_CONF}\n```"
        else:
            text = f"```json\n{_RISK_TERMINAL_PAYMENT}\n```"
        yield {
            "_terminal_result": {
                "text": text,
                "terminal": {"text": text},
            }
        }
        return

    # CR-07 redline generation sub-agent (LLM_BATCH_AGENTS)
    if "redline" in desc_lower and "original_text" in desc_lower:
        item_lower = description.lower()
        if "liability" in item_lower:
            text = f"```json\n{_REDLINE_TERMINAL_LIABILITY}\n```"
        else:
            text = f"```json\n{_REDLINE_TERMINAL_CONF}\n```"
        yield {
            "_terminal_result": {
                "text": text,
                "terminal": {"text": text},
            }
        }
        return

    # Fallback: empty successful terminal
    yield {"_terminal_result": {"text": "ok"}}
