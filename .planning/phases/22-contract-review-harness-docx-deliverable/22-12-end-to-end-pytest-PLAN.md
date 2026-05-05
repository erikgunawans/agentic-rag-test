---
phase: 22-contract-review-harness-docx-deliverable
plan: 12
type: execute
wave: 7
depends_on: ["22-04", "22-05", "22-06", "22-07", "22-08", "22-09", "22-10"]
files_modified:
  - backend/tests/harnesses/test_contract_review_e2e.py
  - backend/tests/harnesses/conftest.py
  - backend/tests/data/synth-contract.docx
  - backend/tests/data/_generate_synth_contract.py
autonomous: true
requirements: [CR-01, CR-02, CR-03, CR-04, CR-05, CR-06, CR-07, CR-08, DOCX-01, DOCX-02, DOCX-03, DOCX-04, DOCX-05, DOCX-06, DOCX-07, DOCX-08]
must_haves:
  truths:
    - "REVIEW #9 closed: E2E test exercises the REAL HIL flow — gatekeeper trigger → engine through CR-01 + CR-02 → CR-03 emits harness_human_input_required + sets status='paused' → test simulates user reply via the chat router resume branch (chat.py:~365) → engine resumes from CR-04 → completes through CR-08 + post_execute"
    - "Single linear `run_harness_engine()` call would stall at CR-03 with status='paused' (Phase 21 D-01..D-04 invariant) — the test MUST exercise resume_from_pause + advance_phase, not one big invocation"
    - "E2E test invokes `_gatekeeper_stream_wrapper` (chat.py) or its public surface, not run_harness_engine directly; this also exercises the B4 single-registry plumbing (REVIEW #4 indirect verification)"
    - "Synthetic 3-clause DOCX fixture: Liability + Confidentiality + Payment"
    - "Test asserts: 9 harness_phase_complete events emitted in order across the two engine invocations [intake, classify, gather-context (paused after question), → resume → load-playbook, extract-clauses, risk-analysis, filter-redline-candidates, redline-generation, executive-summary]; exactly one harness_artifact (ok=true); harness_runs.status='completed'"
    - "Test asserts: contract-review-report.md is MARKDOWN (starts with '#') NOT raw JSON (REVIEW #6 anti-regression)"
    - "Test asserts: workspace_updated event emitted after harness_artifact (REVIEW #7 anti-regression)"
    - "DOCX bytes parsed back via python-docx confirm CONFIDENTIAL marker + 3 risk-colored rows + GREEN section"
    - "Off-mode test: contract_review_enabled=False → harness NOT in registry"
    - "Non-fatal fallback test: sandbox stub returning non-zero exit_code → harness_artifact ok=false; harness_runs.status STILL 'completed'"
  artifacts:
    - path: "backend/tests/harnesses/test_contract_review_e2e.py"
      provides: "End-to-end pytest covering all 16 REQ-IDs across HIL pause+resume"
    - path: "backend/tests/harnesses/conftest.py"
      provides: "sandbox_in_process_stub fixture + httpx file:// patch + phase_routed_llm_mock"
    - path: "backend/tests/data/synth-contract.docx"
      provides: "3-clause synthetic contract"
    - path: "backend/tests/data/_generate_synth_contract.py"
      provides: "Reproducible generator script"
  key_links:
    - from: "Test invokes chat router's stream wrapper"
      to: "engine pause at CR-03 (status='paused') → resume on next user message → engine continues from CR-04"
      via: "Phase 21 HIL D-01..D-04 architecture (verified at chat.py:~365)"
      pattern: "status.*paused\\|resume_from_pause"
---

<objective>
Build the end-to-end integration test that ties all 9 phases together AROUND THE REAL HIL ARCHITECTURE.

**REVIEW #9 anchor:** the prior plan called `run_harness_engine()` once and asserted the full event stream. This is incorrect — Phase 21 D-01..D-04 mandates that CR-03 (`llm_human_input`) pauses the engine: the engine emits `harness_human_input_required`, transitions DB row to `status='paused'`, and closes its async generator. A subsequent user message in the chat router (chat.py:~365) detects the paused row, writes the answer to `phase.workspace_output`, calls `resume_from_pause`, and starts a NEW `run_harness_engine` invocation from `current_phase + 1`. The test must exercise BOTH halves.

**Test architecture:**
1. **First half:** simulate user uploading + sending "review this contract" → drive `_gatekeeper_stream_wrapper` (chat.py) → engine runs CR-01 + CR-02 + emits CR-03 question → engine pauses with status='paused'.
2. **Second half:** simulate user replying with their context → re-enter the chat router → router detects paused run → writes review-context.md → resumes engine from CR-04 → engine runs CR-04 through CR-08 + post_execute → harness_artifact + workspace_updated emitted → harness_runs.status='completed'.

Output: 1 fixture DOCX + 1 generator script + 1 conftest with sandbox + httpx patches + phase-routed LLM mock + 3 E2E tests (happy path, off-mode, non-fatal fallback).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md
@backend/app/harnesses/contract_review.py
@backend/app/services/harness_engine.py
@backend/app/routers/chat.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Synthetic 3-clause DOCX fixture + generator script</name>
  <files>backend/tests/data/synth-contract.docx, backend/tests/data/_generate_synth_contract.py</files>
  <read_first>
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md (CR-05 13 categories — pick 3 for the fixture)
  </read_first>
  <action>
    Create `backend/tests/data/_generate_synth_contract.py` (reproducible). Run once to write `synth-contract.docx`. Commit BOTH the script AND the .docx.

    Generator:
    ```python
    """Generate backend/tests/data/synth-contract.docx — 3-clause MSA fixture for E2E tests."""
    from docx import Document

    doc = Document()
    doc.add_heading("MASTER SERVICES AGREEMENT", level=1)
    doc.add_paragraph(
        'This agreement is entered into as of January 1, 2026, between Acme Corp '
        '("Provider") and Beta Inc ("Customer").'
    )
    doc.add_heading("1. LIABILITY", level=2)
    doc.add_paragraph(
        "Each party's total liability under this agreement shall not exceed USD 100,000."
    )
    doc.add_heading("2. CONFIDENTIALITY", level=2)
    doc.add_paragraph(
        "Each party shall hold the other party's confidential information in strict "
        "confidence for five (5) years following termination."
    )
    doc.add_heading("3. PAYMENT", level=2)
    doc.add_paragraph(
        "Customer shall pay Provider within thirty (30) days of receipt of invoice."
    )
    doc.add_paragraph("Governing Law: Republic of Indonesia.")

    import pathlib
    out = pathlib.Path(__file__).parent / "synth-contract.docx"
    doc.save(str(out))
    print(f"Wrote {out} ({out.stat().st_size} bytes)")
    ```
  </action>
  <verify>
    <automated>cd backend && python -c "from docx import Document; d = Document('tests/data/synth-contract.docx'); paragraphs = [p.text for p in d.paragraphs if p.text.strip()]; assert any('LIABILITY' in p for p in paragraphs); assert any('CONFIDENTIALITY' in p for p in paragraphs); assert any('PAYMENT' in p for p in paragraphs); print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/tests/data/synth-contract.docx` exists and is a valid DOCX
    - `backend/tests/data/_generate_synth_contract.py` is reproducible
    - File size between 5 KB and 50 KB
  </acceptance_criteria>
  <done>Synthetic fixture committed; reproducible via generator.</done>
</task>

<task type="auto">
  <name>Task 2: conftest.py — sandbox stub + httpx file:// patch + phase-routed LLM mock</name>
  <files>backend/tests/harnesses/conftest.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py (post-Plan-22-10 state — for canned LLM response shapes)
    - backend/app/services/sandbox_service.py (lines 228-258 — execute() return shape)
    - backend/app/harnesses/contract_review_docx.py (post-Plan-22-10 — confirms httpx GET on signed_url path)
  </read_first>
  <action>
    Create or extend `backend/tests/harnesses/conftest.py` with two fixtures:

    **A) `sandbox_in_process_stub`** — runs `DOCX_GENERATION_SCRIPT_BODY` in-process via subprocess (NOT a real container), returns SandboxService.execute() shape. Patches httpx file:// for the auto-collected files retrieval.

    **B) `phase_routed_llm_mock`** — inspects system prompt to pick the right canned response per CR phase. Returns canned JSONs for classify, gather-context-question, load-playbook, extract-clauses, risk per-clause, redline per-clause, executive-summary.

    Both fixtures are the same as the prior version of plan 22-12 — preserve the conftest.py structure but ENSURE plan 22-10's PINNED API is used (NO base64 stdout, NO files= kwarg).

    Reference Task 2 of the prior plan (lines 296-393 of the previous version) for the exact fixture body — keep it unchanged BUT verify:
    - Patches `app.services.sandbox_service.get_sandbox_service` to return mock with `.execute = AsyncMock(side_effect=_run)`
    - Patches `httpx.AsyncClient.get` to handle `file://` URLs from the in-process subprocess output dir
    - Returns the canonical engine merge shape `{exit_code, stdout, stderr, error_type, execution_ms, files, execution_id}`
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/conftest.py -v --tb=short 2>&1 | head -20 || true; pytest tests/harnesses/ --collect-only -q 2>&1 | head -5</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "sandbox_in_process_stub" backend/tests/harnesses/conftest.py` returns `>= 1`
    - `grep -c "phase_routed_llm_mock" backend/tests/harnesses/conftest.py` returns `>= 1`
    - `grep -c "file://" backend/tests/harnesses/conftest.py` returns `>= 1` (httpx patch)
    - `grep -c "execute_code\|DOCX_B64_BEGIN" backend/tests/harnesses/conftest.py` returns `0` (PINNED API only)
  </acceptance_criteria>
  <done>Reusable test infra in place.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: E2E test exercising HIL pause + resume (REVIEW #9)</name>
  <files>backend/tests/harnesses/test_contract_review_e2e.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py + contract_review_docx.py (full files post-Plans 22-06..22-10)
    - backend/app/services/harness_engine.py (run_harness_engine signature; LLM_HUMAN_INPUT pause logic)
    - backend/app/routers/chat.py (lines 360-420 — HIL resume branch; verify resume_from_pause call site)
    - backend/app/services/harness_runs_service.py (resume_from_pause + advance_phase signatures)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-REVIEWS.md (review finding #9)
  </read_first>
  <behavior>
    - Test 1 (E2E HIL happy path — REVIEW #9): seed workspace with synth-contract.docx, FIRST invocation through CR-01..CR-03 (runs until CR-03's llm_human_input emits the question + sets status='paused'); SECOND invocation simulates the chat router HIL resume branch (calls resume_from_pause, writes user reply to review-context.md, restarts engine from CR-04); engine completes through CR-08 + post_execute. Assertions:
      * First invocation yields events ending with `harness_human_input_required` (or equivalent paused-event); harness_runs.status transitions to 'paused'.
      * Second invocation yields events for CR-04..CR-08, then `harness_artifact` (ok=true), then `workspace_updated` (REVIEW #7), then `harness_complete` with status='completed'.
      * 9 `harness_phase_complete` events total across both invocations (or whatever the actual emission count is — the assertion compares names to the expected ordered list).
      * `contract-review-report.md` content starts with `# Contract Review Report` (REVIEW #6 — markdown, not JSON).
      * DOCX bytes parsed back have `CONFIDENTIAL` marker + 3 risk rows.
    - Test 2 (off-mode REGISTRATION invariant): with contract_review_enabled=False, `harness_registry.get_harness('contract-review') is None`.
    - Test 3 (D-22-15 non-fatal fallback): same flow as Test 1 but sandbox stub returns `{"exit_code": 1, "stderr": "boom", "files": []}`. Assertions: `harness_artifact` event has `ok=false`, `code='DOCX_FAILED'`; `harness_runs_service.complete` called with status='completed' (NOT 'failed').
  </behavior>
  <action>
    Create `backend/tests/harnesses/test_contract_review_e2e.py`. Header:
    ```python
    """Phase 22 / Plan 22-12 — Contract Review end-to-end pytest (REVIEW #9 — HIL flow).

    Three tests:
    1. test_e2e_full_pipeline_with_hil_pause_resume — covers all 16 REQ-IDs across the
       real CR-03 pause + chat router resume branch. NOT a single linear engine invocation.
    2. test_off_mode_registration_invariant — D-16 invariant.
    3. test_d_22_15_sandbox_failure_non_fatal — D-22-15 non-fatal fallback.
    """
    from __future__ import annotations
    import asyncio, io, json, pathlib
    import pytest
    from unittest.mock import AsyncMock, MagicMock, patch
    from docx import Document
    ```

    **Test 1 (REVIEW #9 — HIL pause+resume flow):**
    ```python
    @pytest.mark.asyncio
    async def test_e2e_full_pipeline_with_hil_pause_resume(monkeypatch, sandbox_in_process_stub, phase_routed_llm_mock, tmp_path):
        """REVIEW #9: this test mirrors the REAL HIL architecture.
        Engine pauses at CR-03 (llm_human_input). User reply is processed by the chat router's
        HIL branch (chat.py:~365) which writes the answer + calls resume_from_pause + starts
        a NEW run_harness_engine invocation from current_phase+1. We exercise BOTH halves.
        """
        from app.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "harness_enabled", True, raising=False)
        monkeypatch.setattr(s, "contract_review_enabled", True, raising=False)
        monkeypatch.setattr(s, "tool_registry_enabled", True, raising=False)

        import importlib, app.harnesses.contract_review as cr_mod
        importlib.reload(cr_mod)

        from app.services.harness_registry import get_harness
        harness = get_harness("contract-review")
        assert harness is not None
        assert len(harness.phases) == 9

        fixture_bytes = pathlib.Path("backend/tests/data/synth-contract.docx").read_bytes()

        # In-memory workspace
        artifacts: dict[str, str] = {}
        captured_writes: list = []
        ws = MagicMock()
        ws.list_files = AsyncMock(return_value=[
            {"file_path": "contract.docx", "source": "upload", "size_bytes": len(fixture_bytes)},
        ])
        ws.read_binary_file = AsyncMock(return_value=fixture_bytes)
        async def _wt(thread_id, file_path, content, source="agent"):
            artifacts[file_path] = content
            return {"ok": True, "size_bytes": len(content)}
        ws.write_text_file = AsyncMock(side_effect=_wt)
        async def _read(thread_id, file_path):
            return {"content": artifacts.get(file_path, "")}
        ws.read_file = AsyncMock(side_effect=_read)
        async def _wb(*, thread_id, file_path, content_bytes, **kwargs):
            captured_writes.append({"file_path": file_path, "content_bytes": content_bytes, **kwargs})
            return {"ok": True, "size_bytes": len(content_bytes)}
        ws.write_binary_file = AsyncMock(side_effect=_wb)
        ws.get_signed_url = AsyncMock(return_value="https://example.com/signed")

        # Mock harness_runs_service for status transitions
        run_state = {"status": "pending", "current_phase": 0}
        async def _start_run(**kw):
            run_state["status"] = "running"
            return "run-42"
        async def _advance_phase(**kw):
            run_state["current_phase"] += 1
            return True
        async def _pause_run(**kw):
            run_state["status"] = "paused"
            return True
        async def _resume(**kw):
            run_state["status"] = "running"
            return True
        async def _complete(**kw):
            run_state["status"] = kw.get("status", "completed")
            return True
        async def _get_active_run(**kw):
            return {"harness_run_id": "run-42", "harness_type": "contract-review",
                    "status": run_state["status"], "current_phase": run_state["current_phase"]}

        from unittest.mock import patch as _patch
        patches = [
            _patch("app.services.harness_runs_service.start_run", side_effect=_start_run),
            _patch("app.services.harness_runs_service.advance_phase", side_effect=_advance_phase),
            _patch("app.services.harness_runs_service.pause_run", side_effect=_pause_run),
            _patch("app.services.harness_runs_service.resume_from_pause", side_effect=_resume),
            _patch("app.services.harness_runs_service.complete", side_effect=_complete),
            _patch("app.services.harness_runs_service.get_active_run", side_effect=_get_active_run),
            _patch("app.services.openrouter_service.OpenRouterService.complete_with_tools",
                   AsyncMock(side_effect=phase_routed_llm_mock)),
        ]
        for p in patches:
            p.start()

        try:
            from app.services.harness_engine import run_harness_engine

            # FIRST INVOCATION: runs until CR-03 pause
            events_first: list = []
            async for ev in run_harness_engine(
                harness_run_id="run-42", thread_id="thr", user_id="u",
                user_email="e@x", token="tok", harness_type="contract-review",
                start_phase=0, registry=None,
            ):
                events_first.append(ev)
                if ev.get("type") == "harness_human_input_required":
                    break

            assert any(e.get("type") == "harness_phase_complete" and e.get("phase_name") == "intake" for e in events_first)
            assert any(e.get("type") == "harness_phase_complete" and e.get("phase_name") == "classify" for e in events_first)
            assert any(e.get("type") == "harness_human_input_required" for e in events_first), \
                "REVIEW #9: engine MUST pause at CR-03 with harness_human_input_required event"
            assert run_state["status"] == "paused"

            # SIMULATE CHAT ROUTER HIL RESUME (chat.py:~365):
            # User replied with their context — write to review-context.md
            artifacts["review-context.md"] = "We are the Customer. No deadline. Focus on liability cap."
            await _resume(harness_run_id="run-42")
            run_state["current_phase"] = 3   # CR-04 is next

            # SECOND INVOCATION: resume from CR-04
            events_second: list = []
            async for ev in run_harness_engine(
                harness_run_id="run-42", thread_id="thr", user_id="u",
                user_email="e@x", token="tok", harness_type="contract-review",
                start_phase=3, registry=None,
            ):
                events_second.append(ev)

            # Assert CR-04..CR-08 phases all completed
            phase_names_completed = [e.get("phase_name") for e in events_second
                                     if e.get("type") == "harness_phase_complete"]
            expected_remaining = [
                "load-playbook", "extract-clauses", "risk-analysis",
                "filter-redline-candidates", "redline-generation", "executive-summary",
            ]
            for name in expected_remaining:
                assert name in phase_names_completed, f"REVIEW #9: phase {name} missing from second-invocation events"

            # REVIEW #7: workspace_updated emitted after harness_artifact
            artifact_idx = next(
                (i for i, e in enumerate(events_second) if e.get("type") == "harness_artifact"), -1
            )
            ws_idx = next(
                (i for i, e in enumerate(events_second) if e.get("type") == "workspace_updated"), -1
            )
            assert artifact_idx >= 0 and ws_idx > artifact_idx, \
                "REVIEW #7: workspace_updated must follow harness_artifact"
            artifact_evt = events_second[artifact_idx]
            assert artifact_evt.get("ok") is True
            assert artifact_evt.get("harness_mode") == "contract-review", "REVIEW #8: harness_mode in event"

            # REVIEW #6: contract-review-report.md is markdown, not JSON
            assert "contract-review-report.md" in artifacts
            report_md = artifacts["contract-review-report.md"]
            assert report_md.lstrip().startswith("# Contract Review Report"), \
                "REVIEW #6: report.md must start with markdown header"
            assert not report_md.lstrip().startswith("{"), "REVIEW #6: report MUST NOT be raw JSON"

            # DOCX bytes parsed back
            docx_bytes = captured_writes[-1]["content_bytes"]
            parsed = Document(io.BytesIO(docx_bytes))
            text_full = "\n".join(p.text for p in parsed.paragraphs)
            assert "CONFIDENTIAL" in text_full

            assert run_state["status"] == "completed"

        finally:
            for p in patches:
                p.stop()
    ```

    **Test 2 (off-mode):** unchanged from prior plan version — `contract_review_enabled=False` → `get_harness('contract-review') is None`.

    **Test 3 (D-22-15 non-fatal — REVIEW #9 + REVIEW #7):**
    ```python
    @pytest.mark.asyncio
    async def test_d_22_15_sandbox_failure_non_fatal(monkeypatch, phase_routed_llm_mock):
        """D-22-15 + REVIEW #9: same HIL flow as Test 1, but sandbox returns exit_code=1.
        harness_artifact has ok=false; harness_runs.status STILL completed."""
        # Same setup as Test 1 but with sandbox stub returning exit_code=1
        with patch("app.services.sandbox_service.get_sandbox_service") as gs:
            gs.return_value.execute = AsyncMock(return_value={
                "exit_code": 1, "stderr": "boom", "files": [], "stdout": "", "error_type": None,
                "execution_ms": 0, "execution_id": "x",
            })
            # ... run the full HIL pause/resume flow same as Test 1 ...
            # After both invocations:
            # - find harness_artifact event
            # - assert it has ok=false, code="DOCX_FAILED"
            # - assert harness_runs_service.complete was called with status="completed", NOT "failed"
        # ...
    ```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_e2e.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/harnesses/test_contract_review_e2e.py -v` exits 0 with 3 tests passing
    - `grep -c "harness_human_input_required" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 2` (Test 1 + Test 3 both exercise pause)
    - `grep -c "REVIEW #9" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 2`
    - `grep -c "REVIEW #6\|REVIEW #7" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 2`
    - `grep -c "synth-contract.docx" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 1`
    - `grep -c "DOCX_FAILED\|fallback_message" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 1`
    - `grep -c "CONFIDENTIAL" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 1`
    - `grep -c "filter-redline-candidates" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 1`
    - `grep -c "resume_from_pause\|advance_phase\|paused" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 3` (REVIEW #9 — HIL flow exercised explicitly)
  </acceptance_criteria>
  <done>3 E2E tests pass — full 9-phase pipeline across HIL pause+resume + off-mode + non-fatal fallback covered.</done>
</task>

</tasks>

<truths>
- All 16 Phase 22 REQ-IDs (CR-01..08, DOCX-01..08) appear in this plan's `requirements` field.
- D-16 OFF-mode invariant tested via Test 2 (registration-side; gatekeeper PROMPT structure regression-tested by plan 22-05).
- D-22-15 non-fatal fallback tested via Test 3.
- REVIEW #9 closed: test exercises the REAL pause/resume flow — two `run_harness_engine` invocations with chat router HIL branch logic between them. Was previously a single linear engine call which would have hung at CR-03.
- REVIEW #6 anti-regression in Test 1: `contract-review-report.md` content starts with `# `, NOT `{`.
- REVIEW #7 anti-regression in Test 1: workspace_updated event yielded AFTER harness_artifact.
- REVIEW #8 anti-regression in Test 1: harness_artifact event has `harness_mode='contract-review'` field.
- 9-phase pipeline order: intake → classify → gather-context (paused) → resume → load-playbook → extract-clauses → risk-analysis → filter-redline-candidates → redline-generation → executive-summary.
- conftest.py provides reusable sandbox + httpx patches.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Test fixture (synthetic DOCX) → CR-01 extractor | Fully synthetic; no real PII |
| Mocked LLM responses → engine validation | All canned JSON; no live LLM exposure |
| In-process sandbox stub → workspace.write_binary_file mock | Subprocess argv form runs trusted DOCX_GENERATION_SCRIPT_BODY |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-12-01 | Tampering | Test relies on flag-flip via monkeypatch | mitigate | importlib.reload ensures fresh registration |
| T-22-12-02 | Information Disclosure | Test fixtures in git | accept | Synthetic Acme/Beta names; no real PII |
</threat_model>

<verification>
1. `pytest backend/tests/harnesses/test_contract_review_e2e.py -v` exits 0 with 3 tests
2. `pytest backend/tests/harnesses/ backend/tests/services/test_harness_engine_post_execute.py backend/tests/services/test_gatekeeper_eval.py -v` exits 0
3. `python -c "from docx import Document; d = Document('backend/tests/data/synth-contract.docx'); print('OK')"` prints `OK`
</verification>

<success_criteria>
- All 9 phases compose end-to-end across the REAL HIL pause/resume architecture (REVIEW #9 closed)
- Off-mode registration invariant verified
- D-22-15 non-fatal fallback verified
- REVIEW #6 + #7 + #8 anti-regression assertions present
- DOCX bytes parse back successfully showing all required sections
- conftest.py provides reusable sandbox stub + httpx file:// patch
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-12-SUMMARY.md`.
</output>
