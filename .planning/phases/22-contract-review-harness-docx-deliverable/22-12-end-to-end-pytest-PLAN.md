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
autonomous: true
requirements: [CR-01, CR-02, CR-03, CR-04, CR-05, CR-06, CR-07, CR-08, DOCX-01, DOCX-02, DOCX-03, DOCX-04, DOCX-05, DOCX-06, DOCX-07, DOCX-08]
must_haves:
  truths:
    - "End-to-end pytest exercises all 9 phases (8 user-visible CR-XX + 1 programmatic filter) through to DOCX generation"
    - "Synthetic 3-clause DOCX fixture covers Liability + Confidentiality + Payment categories"
    - "Test asserts: 9 harness_phase_complete events emitted in order [intake, classify, gather-context, load-playbook, extract-clauses, risk-analysis, filter-redline-candidates, redline-generation, executive-summary], exactly one harness_artifact event with ok=true, harness_runs.status='completed'"
    - "DOCX bytes parsed back via python-docx confirm CONFIDENTIAL marker + 3 risk-colored rows + GREEN section"
    - "Off-mode test: with contract_review_enabled=False, harness is NOT in registry — gatekeeper never sees it"
    - "Non-fatal fallback test: with sandbox stub returning non-zero exit_code, harness_runs.status still 'completed' AND harness_artifact has ok=false"
    - "Off-mode invariant for gatekeeper PROMPT structure is verified by plan 22-05's test_gatekeeper_eval.py (5 smoke-echo phrasings ensure regression safety); this plan's Test 2 verifies only registration-side off-mode (D-22-15 narrowed)"
  artifacts:
    - path: "backend/tests/harnesses/test_contract_review_e2e.py"
      provides: "End-to-end pytest covering all 16 REQ-IDs in a single integration test"
    - path: "backend/tests/harnesses/conftest.py"
      provides: "sandbox_in_process_stub fixture + httpx file:// patch for fetching auto-collected DOCX bytes"
    - path: "backend/tests/data/synth-contract.docx"
      provides: "3-clause synthetic contract fixture for E2E test"
  key_links:
    - from: "Test fixture seeding workspace_files (source='upload')"
      to: "CR-01 reading the upload"
      via: "WorkspaceService.read_binary_file"
      pattern: "synth-contract\\.docx"
---

<objective>
Build the end-to-end integration test that ties all 9 phases together (8 user-visible CR-XX + 1 programmatic filter). Exercises the full pipeline from synthetic DOCX upload through DOCX deliverable generation, plus a 2-test pair covering off-mode invariant and D-22-15 non-fatal fallback.

Purpose: Smoke-grade regression suite for Phase 22. Catches breakage in any single CR-* phase, the filter step, or the inter-phase data flow.
Output: One large parameterized E2E test + 2 invariant tests + 1 fixture DOCX + 1 conftest fixture pair.
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
@backend/app/harnesses/contract_review.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create synthetic 3-clause DOCX fixture</name>
  <files>backend/tests/data/synth-contract.docx</files>
  <read_first>
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md (CR-05 13 categories — pick 3 for the fixture)
  </read_first>
  <action>
    Build the fixture programmatically (so the .docx is reproducible from git diff) by adding a one-time generator script `backend/tests/data/_generate_synth_contract.py` that produces `backend/tests/data/synth-contract.docx`. Run it once and commit the binary.

    The fixture content (3 clauses, ~4-5 paragraphs total):
    ```
    MASTER SERVICES AGREEMENT

    This agreement is entered into as of January 1, 2026, between Acme Corp ("Provider")
    and Beta Inc ("Customer").

    1. LIABILITY
    Each party's total liability under this agreement shall not exceed USD 100,000 in the
    aggregate. Customer waives all consequential, indirect, and punitive damages.

    2. CONFIDENTIALITY
    Each party shall hold the other party's confidential information in strict confidence
    for a period of five (5) years following termination.

    3. PAYMENT
    Customer shall pay Provider within thirty (30) days of receipt of invoice. Late payments
    accrue interest at 1.5% per month.

    Governing Law: This agreement is governed by the laws of the Republic of Indonesia.
    Jurisdiction: The courts of Jakarta shall have exclusive jurisdiction.
    ```

    Generator script:
    ```python
    """Generate backend/tests/data/synth-contract.docx — 3-clause MSA fixture for E2E tests.

    Run once: `cd backend && python tests/data/_generate_synth_contract.py`
    The resulting .docx is committed to git as a binary fixture.
    """
    from docx import Document

    doc = Document()
    doc.add_heading("MASTER SERVICES AGREEMENT", level=1)
    doc.add_paragraph(
        'This agreement is entered into as of January 1, 2026, between Acme Corp '
        '("Provider") and Beta Inc ("Customer").'
    )
    doc.add_heading("1. LIABILITY", level=2)
    doc.add_paragraph(
        "Each party's total liability under this agreement shall not exceed USD 100,000 "
        "in the aggregate. Customer waives all consequential, indirect, and punitive damages."
    )
    doc.add_heading("2. CONFIDENTIALITY", level=2)
    doc.add_paragraph(
        "Each party shall hold the other party's confidential information in strict "
        "confidence for a period of five (5) years following termination."
    )
    doc.add_heading("3. PAYMENT", level=2)
    doc.add_paragraph(
        "Customer shall pay Provider within thirty (30) days of receipt of invoice. "
        "Late payments accrue interest at 1.5% per month."
    )
    doc.add_paragraph("Governing Law: This agreement is governed by the laws of the Republic of Indonesia.")
    doc.add_paragraph("Jurisdiction: The courts of Jakarta shall have exclusive jurisdiction.")

    import pathlib
    out = pathlib.Path(__file__).parent / "synth-contract.docx"
    doc.save(str(out))
    print(f"Wrote {out} ({out.stat().st_size} bytes)")
    ```

    Run the generator from `backend/` once (`python tests/data/_generate_synth_contract.py`) and commit BOTH the script AND the resulting .docx. The script staying in git lets future devs regenerate if the binary diverges.
  </action>
  <verify>
    <automated>cd backend && python -c "from docx import Document; d = Document('tests/data/synth-contract.docx'); paragraphs = [p.text for p in d.paragraphs if p.text.strip()]; assert any('LIABILITY' in p for p in paragraphs); assert any('CONFIDENTIALITY' in p for p in paragraphs); assert any('PAYMENT' in p for p in paragraphs); print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/tests/data/synth-contract.docx` exists, is a valid DOCX
    - `backend/tests/data/_generate_synth_contract.py` exists and is reproducible
    - Reading the .docx shows the 3 expected headings (LIABILITY, CONFIDENTIALITY, PAYMENT)
    - File size between 5 KB and 50 KB
  </acceptance_criteria>
  <done>Synthetic fixture committed; reproducible via generator script.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: End-to-end test exercising all 9 phases + invariants</name>
  <files>backend/tests/harnesses/test_contract_review_e2e.py, backend/tests/harnesses/conftest.py</files>
  <read_first>
    - backend/app/harnesses/contract_review.py + contract_review_docx.py (full files post-Plans 22-06..22-10)
    - backend/app/services/harness_engine.py (run_harness_engine signature + sequence of yielded events)
    - backend/tests/services/test_harness_engine_post_execute.py (analog test infra from plan 22-03)
    - backend/tests/data/synth-contract.docx (fixture from Task 1)
  </read_first>
  <behavior>
    - Test 1 (E2E happy path): seed workspace with synth-contract.docx, run harness engine through all 9 phases with mocked LLM responses, assert:
      * 9 `harness_phase_complete` events emitted in order [intake, classify, gather-context, load-playbook, extract-clauses, risk-analysis, filter-redline-candidates, redline-generation, executive-summary]
      * Exactly one `harness_artifact` event with `ok=true`
      * harness_runs.status ends as `completed`
      * `contract-review-{run_id_short}.docx` written to workspace_files with source='harness'
      * Parse the DOCX bytes back; assert `CONFIDENTIAL` text present, table with 3 rows (3 clauses graded), at least one row with GREEN/YELLOW/RED fill
    - Test 2 (off-mode REGISTRATION invariant — D-22-15 narrowed scope): with `contract_review_enabled=False`, assert `harness_registry.get_harness('contract-review') is None`. The Contract Review harness is NOT registered. Note: gatekeeper PROMPT structure is regression-tested by plan 22-05's test_gatekeeper_eval.py (5 smoke-echo phrasings) — this Test 2 verifies ONLY the registration-side off-mode invariant, NOT gatekeeper-prompt byte-identical behavior.
    - Test 3 (D-22-15 non-fatal fallback): same E2E but stub sandbox to return `{"exit_code": 1, "stderr": "boom", "files": []}`. Assert harness_artifact event has `ok=false`, `code='DOCX_FAILED'`, `fallback_message` non-empty. harness_runs.status STILL `completed` (not failed).
  </behavior>
  <action>
    Create `backend/tests/harnesses/test_contract_review_e2e.py`. Header:

    ```python
    """Phase 22 / Plan 22-12 — Contract Review end-to-end pytest.

    Exercises ALL 9 phases (8 user-visible CR-01..08 + 1 programmatic filter step)
    through to DOCX deliverable (DOCX-01..08).

    3 tests:
    1. test_e2e_full_9_phase_pipeline_happy_path — covers all 16 REQ-IDs
    2. test_off_mode_registration_invariant      — D-16 invariant (registration-side only)
    3. test_d_22_15_sandbox_failure_non_fatal    — D-22-15 non-fatal fallback
    """
    from __future__ import annotations
    import asyncio, base64, io, json, pathlib
    import pytest
    from unittest.mock import AsyncMock, MagicMock, patch
    from docx import Document
    ```

    **Test 1 (happy path)** — long but rote. Mock structure:
    ```python
    @pytest.mark.asyncio
    async def test_e2e_full_9_phase_pipeline_happy_path(monkeypatch, sandbox_in_process_stub, phase_routed_llm_mock):
        # Enable both flags for this test
        from app.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "harness_enabled", True, raising=False)
        monkeypatch.setattr(s, "contract_review_enabled", True, raising=False)

        # Reload harnesses module so contract_review registers
        import importlib, app.harnesses.contract_review as cr_mod
        importlib.reload(cr_mod)

        from app.services.harness_registry import get_harness
        harness = get_harness("contract-review")
        assert harness is not None
        assert len(harness.phases) == 9

        # Load synthetic DOCX
        fixture_bytes = (pathlib.Path("backend/tests/data/synth-contract.docx")).read_bytes()

        # Mock workspace
        ws = MagicMock()
        artifacts = {}  # in-memory simulation of workspace_files
        captured_write_binary_calls = []
        ws.list_files = AsyncMock(return_value=[
            {"file_path": "contract.docx", "source": "upload", "size_bytes": len(fixture_bytes),
             "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ])
        ws.read_binary_file = AsyncMock(return_value=fixture_bytes)
        async def _write_text(thread_id, file_path, content, source="agent"):
            artifacts[file_path] = content
            return {"ok": True, "size_bytes": len(content)}
        ws.write_text_file = AsyncMock(side_effect=_write_text)
        async def _read(thread_id, file_path):
            return {"content": artifacts.get(file_path, "")}
        ws.read_file = AsyncMock(side_effect=_read)
        async def _write_binary(*, thread_id, file_path, content_bytes, **kwargs):
            captured_write_binary_calls.append({
                "file_path": file_path, "content_bytes": content_bytes, **kwargs,
            })
            return {"ok": True, "size_bytes": len(content_bytes)}
        ws.write_binary_file = AsyncMock(side_effect=_write_binary)
        ws.get_signed_url = AsyncMock(return_value="https://example.com/signed")

        # Patch OpenRouterService LLM dispatch with phase-routed mock (fixture)
        # ...wire patches based on which phase calls OpenRouterService...
        # ...assert events list has 9 harness_phase_complete + 1 harness_artifact (ok=true)...
        # ...read back DOCX bytes from captured_write_binary_calls and parse with python-docx...
    ```

    The `canned_responses` map captures the minimum LLM stubs needed:
    ```python
    canned_responses = {
        "classify": json.dumps({
            "contract_type": "MSA",
            "parties": ["Acme Corp", "Beta Inc"],
            "effective_date": "2026-01-01",
            "expiration_date": None,
            "governing_law": "Republic of Indonesia",
            "jurisdiction": "Jakarta",
            "summary": "Master Services Agreement between Acme Corp and Beta Inc.",
        }),
        "gather-context-question": json.dumps({"question": "Which side are you, deadline pressure, focus areas, and deal context?"}),
        "load-playbook": "# Playbook Context\n```json\n" + json.dumps({
            "playbook_docs": [],
            "clause_category_to_playbook": {c: [] for c in ["Liability","Indemnification","IP","Data Protection","Confidentiality","Warranties","Term/Termination","Governing Law","Insurance","Assignment","Force Majeure","Payment","Other"]},
            "context_quality": "unfounded",
            "notes": "No playbook materials found in test fixture.",
        }) + "\n```",
        "extract-clauses": json.dumps({
            "clauses": [
                {"category": "Liability", "heading": "1. LIABILITY", "text": "Each party's total liability...", "position": 0},
                {"category": "Confidentiality", "heading": "2. CONFIDENTIALITY", "text": "Each party shall hold...", "position": 200},
                {"category": "Payment", "heading": "3. PAYMENT", "text": "Customer shall pay...", "position": 400},
            ],
            "chunk_index": 0, "total_chunks": 1,
        }),
        "risk": json.dumps({
            "clause_index": 0, "clause_category": "Liability", "clause_heading": "1. LIABILITY",
            "risk_grade": "RED",
            "rationale": "Liability cap of USD 100k is materially adverse for Customer; unfounded — generic standards.",
            "alternative_language": "Total liability shall not exceed USD 1,000,000.",
            "grounding_doc_ids": [],
        }),
        "redline": json.dumps({
            "clause_index": 0, "clause_category": "Liability",
            "original_text": "Each party's total liability shall not exceed USD 100,000.",
            "proposed_text": "Each party's total liability shall not exceed USD 1,000,000.",
            "rationale": "Higher cap better reflects industry norms for MSAs of this size.",
            "fallback_positions": ["USD 500,000", "USD 250,000"],
        }),
        "exec_summary": json.dumps({
            "overall_risk": "RED",
            "recommendation": "Negotiate the liability cap upward before signing — current USD 100k cap is materially adverse.",
            "key_findings": ["Liability cap too low", "Confidentiality term acceptable", "Payment terms standard"],
            "risk_breakdown": {"GREEN": 2, "YELLOW": 0, "RED": 1},
            "next_steps": ["Apply redline to clause 1 (Liability)", "Confirm jurisdiction with senior counsel"],
        }),
    }
    ```

    For the DOCX bytes assertion, intercept the `ws.write_binary_file` call (mock captures the bytes argument), feed those bytes back to `Document(io.BytesIO(captured_bytes))`, and assert structure:
    ```python
    docx_bytes = captured_write_binary_calls[-1]["content_bytes"]
    parsed = Document(io.BytesIO(docx_bytes))
    text_full = "\n".join(p.text for p in parsed.paragraphs)
    assert "CONFIDENTIAL" in text_full
    ```

    **ISSUE-07 PINNED — concrete sandbox stub strategy via conftest.py:**

    Create `backend/tests/harnesses/conftest.py` (if not present) with a `sandbox_in_process_stub` fixture that runs the REAL `DOCX_GENERATION_SCRIPT_BODY` constant in-process, returning the SandboxService.execute() shape, AND patches httpx to handle file:// URLs (httpx does not support file:// natively):

    ```python
    import os, subprocess, sys, tempfile
    import httpx
    import pytest
    from unittest.mock import AsyncMock, MagicMock, patch


    @pytest.fixture
    def sandbox_in_process_stub(monkeypatch, tmp_path):
        """In-process stub: runs DOCX_GENERATION_SCRIPT_BODY via subprocess, returns
        {exit_code, stdout, stderr, files} matching SandboxService.execute() shape."""
        async def _run(*, code, thread_id, user_id, token=None, **kwargs):
            # The script writes to /sandbox/output/contract-review.docx — redirect via path replacement.
            # Use argv form (no shell interpolation).
            test_code = code.replace("/sandbox/output/", f"{tmp_path}/")
            proc = subprocess.run(
                [sys.executable, "-c", test_code],
                capture_output=True, timeout=60,
            )
            files_out = []
            for fname in os.listdir(tmp_path):
                fpath = os.path.join(str(tmp_path), fname)
                if os.path.isfile(fpath):
                    files_out.append({
                        "filename": fname,
                        "size_bytes": os.path.getsize(fpath),
                        "signed_url": f"file://{fpath}",  # local fixture URL
                        "storage_path": fpath,
                    })
            return {
                "stdout": proc.stdout.decode("utf-8", errors="replace"),
                "stderr": proc.stderr.decode("utf-8", errors="replace"),
                "exit_code": proc.returncode,
                "error_type": None,
                "execution_ms": 0,
                "files": files_out,
                "execution_id": "test-exec",
            }

        sandbox_mock = MagicMock()
        sandbox_mock.execute = AsyncMock(side_effect=_run)
        monkeypatch.setattr(
            "backend.app.services.sandbox_service.get_sandbox_service",
            lambda: sandbox_mock,
        )
        # Also patch the import path used in contract_review_docx.py
        monkeypatch.setattr(
            "app.services.sandbox_service.get_sandbox_service",
            lambda: sandbox_mock,
            raising=False,
        )

        # Patch httpx.AsyncClient.get to handle file:// URLs (httpx doesn't support file:// natively).
        # _generate_docx_post_execute uses httpx.AsyncClient().get(signed_url) per plan 22-10's
        # PINNED API to fetch DOCX bytes from sandbox auto-collected files.
        real_get = httpx.AsyncClient.get

        async def _patched_get(self, url, **kw):
            if isinstance(url, str) and url.startswith("file://"):
                path = url[len("file://"):]
                resp = MagicMock()
                with open(path, "rb") as fh:
                    resp.content = fh.read()
                resp.raise_for_status = lambda: None
                resp.status_code = 200
                return resp
            return await real_get(self, url, **kw)

        monkeypatch.setattr(httpx.AsyncClient, "get", _patched_get)

        yield sandbox_mock
    ```

    **ISSUE-07 phase-routed LLM mock fixture (also in conftest.py):**

    ```python
    @pytest.fixture
    def phase_routed_llm_mock():
        """Inspects system prompt to pick the right canned response per CR phase."""
        canned = {
            "classifying a legal contract": canned_responses["classify"],
            "single combined free-form question": canned_responses["gather-context-question"],
            "playbook loader for a Contract Review": canned_responses["load-playbook"],
            "extracting every distinct legal clause": canned_responses["extract-clauses"],
            "assessing a single contract clause for risk": canned_responses["risk"],
            "drafting a precise redline": canned_responses["redline"],
            "writing the executive summary for a Contract Review": canned_responses["exec_summary"],
        }
        async def _route(messages=None, **kwargs):
            sys_msg = (messages[0]["content"] if messages else "")
            for marker, response in canned.items():
                if marker in sys_msg:
                    return {"content": response}
            return {"content": '{"error": "phase_unknown_in_test"}'}
        return _route
    ```

    Use this fixture in Test 1 by patching `OpenRouterService.complete_with_tools` (or `.complete`) with `AsyncMock(side_effect=phase_routed_llm_mock)`.

    **ISSUE-07 inter-phase data flow assertions** — the test must explicitly verify data flowed correctly between phases:

    ```python
    # After run_harness completes:
    assert "classification" in artifacts.get("classification.md", "")  # contract_type field
    assert "Acme Corp" in artifacts.get("classification.md", "")       # CR-02 found Acme

    # CR-04's playbook-context.md should reference doc IDs from canned RAG response
    pb_text = artifacts.get("playbook-context.md", "")
    assert "context_quality" in pb_text  # the structured field

    # CR-05 should produce 3 clauses (Liability, Confidentiality, Payment)
    clauses = json.loads(artifacts["clauses.json"])  # ISSUE-04 / ISSUE-25 sibling
    assert len(clauses) == 3
    assert {c["category"] for c in clauses} >= {"Liability", "Confidentiality", "Payment"}

    # CR-06 (risk-analysis) merges to risk-analysis.json — array of merge rows
    risks = json.loads(artifacts["risk-analysis.json"])
    assert len(risks) >= 1

    # phases[6] (filter-redline-candidates) wrote redline-candidates.json with YELLOW/RED only
    candidates = json.loads(artifacts["redline-candidates.json"])
    assert all(c.get("risk_grade") in ("YELLOW", "RED") for c in candidates)

    # DOCX bytes parsed back via python-docx
    docx_bytes = captured_write_binary_calls[-1]["content_bytes"]
    parsed = Document(io.BytesIO(docx_bytes))
    text_full = "\n".join(p.text for p in parsed.paragraphs)
    assert "CONFIDENTIAL" in text_full
    ```

    **Test 2 (off-mode registration invariant):**
    ```python
    def test_off_mode_registration_invariant(monkeypatch):
        from app.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "harness_enabled", True, raising=False)
        monkeypatch.setattr(s, "contract_review_enabled", False, raising=False)
        import importlib, app.harnesses.contract_review as cr_mod
        importlib.reload(cr_mod)
        from app.services.harness_registry import get_harness
        assert get_harness("contract-review") is None, "contract_review_enabled=False MUST NOT register harness"
    ```

    **Test 3 (D-22-15 non-fatal):** same as Test 1 but stub `sandbox_service.get_sandbox_service().execute` (PINNED API — NOT execute_code) to return `{"exit_code": 1, "stderr": "boom", "files": []}`. Assert:
    - harness_artifact event has `ok=false`, `code="DOCX_FAILED"`
    - `harness_runs_service.complete` was called with `status="completed"` (NOT "failed")
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/harnesses/test_contract_review_e2e.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/harnesses/test_contract_review_e2e.py -v` exits 0 with 3 tests passing
    - `grep -c "harness_phase_complete\|harness_artifact" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 4`
    - `grep -c "synth-contract.docx" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 1`
    - `grep -c "DOCX_FAILED\|fallback_message" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 1`
    - `grep -c "CONFIDENTIAL" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 1`
    - `grep -c "filter-redline-candidates" backend/tests/harnesses/test_contract_review_e2e.py` returns `>= 1`
    - `grep -c "file://" backend/tests/harnesses/conftest.py` returns `>= 1` (httpx file:// patch present)
  </acceptance_criteria>
  <done>3 E2E tests pass — full 9-phase pipeline + off-mode + non-fatal fallback covered. conftest.py provides sandbox stub with httpx file:// patch for the PINNED auto-collected files retrieval path.</done>
</task>

</tasks>

<truths>
- All 16 Phase 22 REQ-IDs (CR-01..08, DOCX-01..08) appear in this plan's `requirements` field — the E2E test exercises the full pipeline.
- D-16 OFF-mode invariant explicitly tested via Test 2 (registration-side only; gatekeeper PROMPT structure regression-tested by plan 22-05).
- D-22-15 non-fatal fallback explicitly tested via Test 3 (harness_runs.status stays 'completed').
- Synthetic fixture chosen for size + 3 distinct clause categories (Liability=RED, Confidentiality=GREEN, Payment=GREEN per canned LLM responses).
- B4 single-registry NOT exercised in test (no real cloud-LLM calls); the wrap is verified by plan 22-04 + plan 22-09 unit tests.
- LangSmith tracing (OBS-03) NOT verified at test time — relies on existing instrumentation.
- 9-phase pipeline order: intake → classify → gather-context → load-playbook → extract-clauses → risk-analysis → filter-redline-candidates → redline-generation → executive-summary.
- conftest.py httpx file:// patch is necessary because plan 22-10's PINNED `_generate_docx_post_execute` uses `httpx.AsyncClient().get(signed_url)` to fetch auto-collected DOCX bytes; the in-process sandbox stub returns `file://` URLs which httpx does not handle natively.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Test fixture (synthetic DOCX) → CR-01 extractor | Fully synthetic; no real PII |
| Mocked LLM responses → engine validation | All canned JSON; no live LLM exposure |
| In-process sandbox stub → workspace.write_binary_file mock | Subprocess argv form runs trusted DOCX_GENERATION_SCRIPT_BODY; no shell interpolation |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-12-01 | Tampering | Test relies on flag-flip via monkeypatch | mitigate | Tests use monkeypatch.setattr; importlib.reload to ensure fresh registration; test 2 explicitly verifies the off-mode codepath |
| T-22-12-02 | Information Disclosure | Test fixtures committed to git might contain placeholder data interpreted as real | accept | Synthetic Acme Corp / Beta Inc are universally-recognized fictional names; no real PII |
</threat_model>

<verification>
1. `pytest backend/tests/harnesses/test_contract_review_e2e.py -v` exits 0 with 3 tests
2. `pytest backend/tests/harnesses/ backend/tests/services/test_harness_engine_post_execute.py backend/tests/services/test_gatekeeper_eval.py -v` exits 0 (full Phase 22 regression)
3. `python -c "from docx import Document; d = Document('backend/tests/data/synth-contract.docx'); print('OK')"` prints `OK`
</verification>

<success_criteria>
- All 9 phases (8 user-visible CR-XX + 1 programmatic filter) compose end-to-end through DOCX delivery
- Off-mode registration invariant explicitly verified (gatekeeper PROMPT structure covered by plan 22-05)
- D-22-15 non-fatal fallback explicitly verified (PINNED `exit_code != 0` path)
- DOCX bytes parse back successfully showing all required sections
- conftest.py provides reusable sandbox stub + httpx file:// patch for the auto-collected DOCX retrieval path
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-12-SUMMARY.md`.
</output>
