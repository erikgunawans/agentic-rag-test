"""Phase 22 / DOCX-01..08 / REVIEW #6 + #7 — Tests for CR-08 executive summary
and the _generate_docx_post_execute callable in contract_review_docx.py.

Tests lock three review findings:
  REVIEW #6: CR-08 writes executive-summary.json (JSON), NOT contract-review-report.md.
             A deterministic _render_summary_markdown step (called in post_execute) renders
             the actual markdown report. This test verifies the rendered content starts with
             '# Contract Review Report', NOT '{' (raw JSON).
  REVIEW #7: post_execute returns wrote_binary=True + size_bytes so the engine (plan 22-03)
             emits workspace_updated after the DOCX write.
  D-22-15:   post_execute NEVER raises; error dict on sandbox failure.
  ISSUE-05 PIN: SandboxService.execute(*, code, thread_id, user_id, token) — no files=,
             no timeout_seconds=.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: valid ExecutiveSummary dict
# ---------------------------------------------------------------------------

def _valid_exec_summary_dict():
    return {
        "overall_risk": "YELLOW",
        "recommendation": "Sign with redlines applied for two YELLOW clauses.",
        "key_findings": ["IP too broad", "Liability cap too low"],
        "risk_breakdown": {"GREEN": 5, "YELLOW": 2, "RED": 0},
        "next_steps": ["Apply redlines 1-2", "Confirm with legal"],
    }


# ---------------------------------------------------------------------------
# Task 1 tests — ExecutiveSummary schema + CR-08 phase definition
# ---------------------------------------------------------------------------

class TestExecutiveSummarySchema:
    """Tests 1-2 (Task 1 behaviors 1-2)."""

    def test_executive_summary_accepts_valid_instance(self):
        """Test 1: ExecutiveSummary accepts a fully-populated valid instance."""
        from app.harnesses.contract_review import ExecutiveSummary, RiskGrade
        e = ExecutiveSummary(**_valid_exec_summary_dict())
        assert e.overall_risk == RiskGrade.YELLOW
        assert len(e.key_findings) == 2
        assert e.risk_breakdown["GREEN"] == 5

    def test_executive_summary_rejects_empty_key_findings(self):
        """Test 2: ExecutiveSummary rejects empty key_findings (min_length=1)."""
        from pydantic import ValidationError
        from app.harnesses.contract_review import ExecutiveSummary
        d = _valid_exec_summary_dict()
        d["key_findings"] = []
        with pytest.raises(ValidationError):
            ExecutiveSummary(**d)


class TestCR08PhaseDefinition:
    """Tests 3-5 (Task 1 behaviors 3-5)."""

    def test_cr08_phase_has_executive_summary_schema(self):
        """Test 3: CR-08 phase has output_schema=ExecutiveSummary."""
        from app.harnesses.contract_review import CONTRACT_REVIEW, ExecutiveSummary
        phase = CONTRACT_REVIEW.phases[8]
        assert phase.output_schema is ExecutiveSummary

    def test_cr08_workspace_output_is_json_not_markdown(self):
        """Test 4 (REVIEW #6): CR-08 workspace_output == 'executive-summary.json', NOT .md."""
        from app.harnesses.contract_review import CONTRACT_REVIEW
        phase = CONTRACT_REVIEW.phases[8]
        assert phase.workspace_output == "executive-summary.json", (
            "REVIEW #6: LLM_SINGLE writes raw JSON; must NOT pretend to be markdown"
        )
        assert phase.workspace_output != "contract-review-report.md"

    def test_cr08_prompt_mentions_six_input_files(self):
        """Test 5: CR-08 prompt mentions reading the 6 input files."""
        from app.harnesses.contract_review import CONTRACT_REVIEW
        phase = CONTRACT_REVIEW.phases[8]
        prompt = phase.system_prompt_template
        for f in ["classification.md", "review-context.md", "playbook-context.md",
                  "clauses.md", "risk-analysis.json", "redlines.json"]:
            assert f in prompt, f"CR-08 prompt must mention {f}"

    def test_cr08_has_post_execute_wired(self):
        """CR-08 phase must have post_execute set (not None stub)."""
        from app.harnesses.contract_review import CONTRACT_REVIEW
        phase = CONTRACT_REVIEW.phases[8]
        assert phase.post_execute is not None, "CR-08 post_execute must be wired"


# ---------------------------------------------------------------------------
# Task 1 tests — _render_summary_markdown helper
# ---------------------------------------------------------------------------

class TestRenderSummaryMarkdown:
    """Tests 6-8 (Task 1 behaviors 6-8 — REVIEW #6)."""

    @pytest.mark.asyncio
    async def test_render_summary_markdown_produces_required_sections(self):
        """Test 6: _render_summary_markdown produces markdown with the 5 required sections."""
        from app.harnesses.contract_review import _render_summary_markdown
        ws = MagicMock()
        ws.write_text_file = AsyncMock(return_value={"ok": True})

        result = await _render_summary_markdown(
            executive_summary=_valid_exec_summary_dict(),
            classification={"contract_type": "NDA", "parties": ["Acme", "Beta"], "governing_law": "Indonesia"},
            playbook={},
            risks=[],
            redlines=[],
            workspace=ws,
            thread_id="thr-1",
        )

        assert "# Contract Review Report" in result
        assert "## Executive Summary" in result
        assert "## Risk Breakdown" in result
        assert "## Key Findings" in result
        assert "## Recommended Next Steps" in result

    @pytest.mark.asyncio
    async def test_render_summary_markdown_writes_report_to_workspace(self):
        """Test 7: _render_summary_markdown writes contract-review-report.md via write_text_file."""
        from app.harnesses.contract_review import _render_summary_markdown
        captured = {}
        ws = MagicMock()

        async def _capture_write(thread_id, file_path, content, source="agent"):
            captured[file_path] = content
            return {"ok": True}

        ws.write_text_file = AsyncMock(side_effect=_capture_write)

        await _render_summary_markdown(
            executive_summary=_valid_exec_summary_dict(),
            classification={},
            playbook={},
            risks=[],
            redlines=[],
            workspace=ws,
            thread_id="thr-1",
        )

        assert "contract-review-report.md" in captured, "Must write to contract-review-report.md"

    @pytest.mark.asyncio
    async def test_render_summary_markdown_not_raw_json(self):
        """Test 8 (REVIEW #6 anti-regression): rendered output starts with '# ' (markdown),
        NOT '{' (raw JSON)."""
        from app.harnesses.contract_review import _render_summary_markdown
        ws = MagicMock()
        ws.write_text_file = AsyncMock(return_value={"ok": True})

        result = await _render_summary_markdown(
            executive_summary=_valid_exec_summary_dict(),
            classification={},
            playbook={},
            risks=[],
            redlines=[],
            workspace=ws,
            thread_id="thr-1",
        )

        assert result.lstrip().startswith("# "), (
            "REVIEW #6: rendered markdown must start with '# ' header, NOT JSON '{'")
        assert not result.lstrip().startswith("{"), (
            "REVIEW #6: report must NOT be raw JSON")


# ---------------------------------------------------------------------------
# Task 2 tests — _generate_docx_post_execute + DOCX_GENERATION_SCRIPT_BODY
# ---------------------------------------------------------------------------

class TestDocxGenerationScriptBody:
    """Tests 7 + 9 (Task 2 behaviors 7 + 9 — script content + pinned API)."""

    def test_docx_script_body_contains_required_content(self):
        """Test 7: DOCX_GENERATION_SCRIPT_BODY contains python-docx usage + colors + CONFIDENTIAL."""
        from app.harnesses.contract_review_docx import DOCX_GENERATION_SCRIPT_BODY
        assert "from docx import Document" in DOCX_GENERATION_SCRIPT_BODY
        assert "add_heading" in DOCX_GENERATION_SCRIPT_BODY
        assert "add_table" in DOCX_GENERATION_SCRIPT_BODY
        assert "E6F4EA" in DOCX_GENERATION_SCRIPT_BODY  # pastel green
        assert "FEF7E0" in DOCX_GENERATION_SCRIPT_BODY  # pastel yellow
        assert "FCE8E6" in DOCX_GENERATION_SCRIPT_BODY  # pastel red
        assert "CONFIDENTIAL" in DOCX_GENERATION_SCRIPT_BODY

    def test_pinned_api_no_forbidden_patterns(self):
        """Test 9 (ISSUE-05 PIN): module does NOT use forbidden patterns.

        Forbidden: execute_code, DOCX_B64_BEGIN, 'files=' kwarg.
        Required: .execute( + exit_code field.
        """
        import inspect
        from app.harnesses import contract_review_docx as m
        source = inspect.getsource(m)
        assert ".execute(" in source, "Must call SandboxService .execute("
        assert "exit_code" in source, "Must check exit_code"
        assert "execute_code" not in source, "ISSUE-05: execute_code does not exist"
        assert "DOCX_B64_BEGIN" not in source, "ISSUE-05: DOCX_B64_BEGIN removed"

    def test_module_has_no_openrouter_imports(self):
        """Test 8: post_execute makes NO LLM calls (Test 8 behavior — no OpenRouter)."""
        import inspect
        from app.harnesses import contract_review_docx as m
        source = inspect.getsource(m)
        assert "OpenRouterService" not in source
        assert "chat_completion" not in source


# ---------------------------------------------------------------------------
# Task 2 tests — _generate_docx_post_execute success path
# ---------------------------------------------------------------------------

def _make_workspace_mock(exec_summary_json: str | None = None):
    """Return a MagicMock workspace with standard read/write behavior."""
    ws = MagicMock()

    if exec_summary_json is None:
        exec_summary_json = json.dumps(_valid_exec_summary_dict())

    ws.read_file = AsyncMock(return_value={"content": exec_summary_json})
    ws.write_text_file = AsyncMock(return_value={"ok": True})
    ws.write_binary_file = AsyncMock(return_value={"ok": True})
    ws.get_signed_url = AsyncMock(return_value="https://example.com/signed")
    return ws


def _make_sandbox_success_mock():
    """Return a patched sandbox that succeeds with a DOCX file."""
    sb = MagicMock()
    sb.execute = AsyncMock(return_value={
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "files": [
            {
                "filename": "contract-review.docx",
                "size_bytes": 9876,
                "signed_url": "https://sandbox.example/abc.docx",
                "storage_path": "u/thr/exec/contract-review.docx",
            }
        ],
        "execution_id": "exec-1",
        "execution_ms": 1200,
    })
    return sb


@pytest.mark.asyncio
async def test_post_execute_returns_wrote_binary_true_on_success():
    """Test 4 (REVIEW #7): post_execute return must include wrote_binary=True + size_bytes
    so the engine (plan 22-03) emits workspace_updated."""
    from app.harnesses.contract_review_docx import _generate_docx_post_execute
    ws = _make_workspace_mock()

    with patch("app.services.sandbox_service.get_sandbox_service") as gs:
        gs.return_value = _make_sandbox_success_mock()
        with patch("httpx.AsyncClient") as hc_cls:
            hc_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=MagicMock(
                    content=b"FAKE_DOCX_BYTES",
                    raise_for_status=lambda: None,
                )
            )
            result = await _generate_docx_post_execute(
                harness_run_id="abc12345",
                thread_id="thr",
                user_id="u",
                user_email="e@x",
                token="tok",
                phase_results={},
                workspace=ws,
            )

    assert result["ok"] is True, f"Expected ok=True, got: {result}"
    assert result["wrote_binary"] is True, (
        "REVIEW #7: must signal engine to emit workspace_updated"
    )
    assert result["size_bytes"] == len(b"FAKE_DOCX_BYTES")
    assert result["docx_path"] == "contract-review-abc12345.docx"


@pytest.mark.asyncio
async def test_post_execute_reads_all_six_artifacts():
    """Test 1: post_execute reads classification.md, review-context.md, playbook-context.md,
    executive-summary.json, risk-analysis.json, redlines.json from workspace."""
    from app.harnesses.contract_review_docx import _generate_docx_post_execute
    ws = _make_workspace_mock()

    with patch("app.services.sandbox_service.get_sandbox_service") as gs:
        gs.return_value = _make_sandbox_success_mock()
        with patch("httpx.AsyncClient") as hc_cls:
            hc_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=MagicMock(
                    content=b"PK\x03\x04FAKE_DOCX",
                    raise_for_status=lambda: None,
                )
            )
            await _generate_docx_post_execute(
                harness_run_id="run-1",
                thread_id="thr",
                user_id="u",
                user_email="e@x",
                token="tok",
                phase_results={},
                workspace=ws,
            )

    called_paths = {call.args[1] for call in ws.read_file.call_args_list}
    for expected in [
        "classification.md", "review-context.md", "playbook-context.md",
        "executive-summary.json", "risk-analysis.json", "redlines.json",
    ]:
        assert expected in called_paths, f"Must read {expected}"


@pytest.mark.asyncio
async def test_post_execute_calls_render_summary_markdown():
    """Test 2: post_execute calls _render_summary_markdown → contract-review-report.md written (REVIEW #6)."""
    from app.harnesses.contract_review_docx import _generate_docx_post_execute
    ws = _make_workspace_mock()

    with patch("app.services.sandbox_service.get_sandbox_service") as gs:
        gs.return_value = _make_sandbox_success_mock()
        with patch("httpx.AsyncClient") as hc_cls:
            hc_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=MagicMock(
                    content=b"PK\x03\x04FAKE",
                    raise_for_status=lambda: None,
                )
            )
            with patch("app.harnesses.contract_review._render_summary_markdown",
                       new_callable=AsyncMock) as mock_render:
                mock_render.return_value = "# Contract Review Report\n..."
                await _generate_docx_post_execute(
                    harness_run_id="run-1",
                    thread_id="thr",
                    user_id="u",
                    user_email="e@x",
                    token="tok",
                    phase_results={},
                    workspace=ws,
                )

    mock_render.assert_called_once()


@pytest.mark.asyncio
async def test_post_execute_writes_docx_to_workspace():
    """Test 3: On sandbox success, calls write_binary_file with correct path and source='harness'."""
    from app.harnesses.contract_review_docx import _generate_docx_post_execute
    ws = _make_workspace_mock()

    with patch("app.services.sandbox_service.get_sandbox_service") as gs:
        gs.return_value = _make_sandbox_success_mock()
        with patch("httpx.AsyncClient") as hc_cls:
            hc_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=MagicMock(
                    content=b"PK\x03\x04FAKE_DOCX",
                    raise_for_status=lambda: None,
                )
            )
            await _generate_docx_post_execute(
                harness_run_id="abc12345",
                thread_id="thr",
                user_id="u",
                user_email="e@x",
                token="tok",
                phase_results={},
                workspace=ws,
            )

    ws.write_binary_file.assert_called_once()
    call_kwargs = ws.write_binary_file.call_args
    # Accept both positional and keyword argument style
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
    args = call_kwargs.args if call_kwargs.args else ()
    # file_path is either 2nd positional arg or keyword
    file_path = kwargs.get("file_path") or (args[1] if len(args) > 1 else None)
    source = kwargs.get("source") or (args[5] if len(args) > 5 else None)
    assert file_path == "contract-review-abc12345.docx"
    assert source == "harness"


# ---------------------------------------------------------------------------
# Task 2 tests — failure path (D-22-15 non-fatal fallback)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_execute_returns_error_dict_on_sandbox_failure():
    """Test 5: On sandbox non-zero exit_code, returns error dict (does NOT raise).
    wrote_binary is absent or False."""
    from app.harnesses.contract_review_docx import _generate_docx_post_execute
    ws = _make_workspace_mock()

    failed_sb = MagicMock()
    failed_sb.execute = AsyncMock(return_value={
        "exit_code": 1,
        "stdout": "",
        "stderr": "ModuleNotFoundError: No module named 'docx'",
        "files": [],
        "execution_ms": 500,
    })

    with patch("app.services.sandbox_service.get_sandbox_service") as gs:
        gs.return_value = failed_sb
        result = await _generate_docx_post_execute(
            harness_run_id="run-fail",
            thread_id="thr",
            user_id="u",
            user_email="e@x",
            token="tok",
            phase_results={},
            workspace=ws,
        )

    assert "error" in result, "Must return error dict, not raise"
    assert result.get("code") == "DOCX_FAILED"
    assert "fallback_message" in result
    assert result.get("wrote_binary", False) is False


@pytest.mark.asyncio
async def test_post_execute_logs_audit_on_success_and_failure():
    """Test 6: Audit log fires contract_review_docx_generated on success,
    contract_review_docx_failed on failure."""
    from app.harnesses.contract_review_docx import _generate_docx_post_execute

    # --- success audit ---
    ws = _make_workspace_mock()
    with patch("app.services.sandbox_service.get_sandbox_service") as gs:
        gs.return_value = _make_sandbox_success_mock()
        with patch("httpx.AsyncClient") as hc_cls:
            hc_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=MagicMock(content=b"docx", raise_for_status=lambda: None)
            )
            with patch("app.services.audit_service.log_action") as mock_audit:
                await _generate_docx_post_execute(
                    harness_run_id="run-ok",
                    thread_id="thr",
                    user_id="u",
                    user_email="e@x",
                    token="tok",
                    phase_results={},
                    workspace=ws,
                )
    actions_ok = [c.kwargs.get("action") or c.args[2] for c in mock_audit.call_args_list]
    assert "contract_review_docx_generated" in actions_ok

    # --- failure audit ---
    ws2 = _make_workspace_mock()
    failed_sb = MagicMock()
    failed_sb.execute = AsyncMock(return_value={
        "exit_code": 1, "stderr": "crash", "files": [], "execution_ms": 100,
    })
    with patch("app.services.sandbox_service.get_sandbox_service") as gs2:
        gs2.return_value = failed_sb
        with patch("app.services.audit_service.log_action") as mock_audit2:
            await _generate_docx_post_execute(
                harness_run_id="run-fail",
                thread_id="thr",
                user_id="u",
                user_email="e@x",
                token="tok",
                phase_results={},
                workspace=ws2,
            )
    actions_fail = [c.kwargs.get("action") or c.args[2] for c in mock_audit2.call_args_list]
    assert "contract_review_docx_failed" in actions_fail


# ---------------------------------------------------------------------------
# REVIEW #6 — markdown rendered, not JSON (end-to-end in post_execute)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_execute_writes_markdown_not_json_to_report_file():
    """Test 10 (REVIEW #6): contract-review-report.md must be MARKDOWN (starts with '# '),
    NOT raw JSON in a .md file. The deterministic _render_summary_markdown step ensures this."""
    from app.harnesses.contract_review_docx import _generate_docx_post_execute

    captured_writes: dict[str, str] = {}
    ws = MagicMock()
    ws.read_file = AsyncMock(return_value={"content": json.dumps({
        "overall_risk": "RED",
        "recommendation": "Negotiate the liability cap upward before signing the contract.",
        "key_findings": ["Liability cap too low"],
        "risk_breakdown": {"GREEN": 1, "YELLOW": 0, "RED": 1},
        "next_steps": ["Apply redline 1"],
    })})

    async def _wt(thread_id, file_path, content, source="agent"):
        captured_writes[file_path] = content
        return {"ok": True}

    ws.write_text_file = AsyncMock(side_effect=_wt)
    ws.write_binary_file = AsyncMock(return_value={"ok": True})
    ws.get_signed_url = AsyncMock(return_value="https://example.com/signed")

    with patch("app.services.sandbox_service.get_sandbox_service") as gs:
        gs.return_value = _make_sandbox_success_mock()
        with patch("httpx.AsyncClient") as hc_cls:
            hc_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=MagicMock(
                    content=b"docx",
                    raise_for_status=lambda: None,
                )
            )
            await _generate_docx_post_execute(
                harness_run_id="r",
                thread_id="thr",
                user_id="u",
                user_email="e@x",
                token="tok",
                phase_results={},
                workspace=ws,
            )

    assert "contract-review-report.md" in captured_writes, (
        "REVIEW #6: contract-review-report.md must be written by post_execute"
    )
    report_md = captured_writes["contract-review-report.md"]
    assert report_md.lstrip().startswith("# Contract Review Report"), (
        "REVIEW #6: report must start with markdown header, NOT JSON"
    )
    assert not report_md.lstrip().startswith("{"), "Report must NOT be raw JSON"


# ---------------------------------------------------------------------------
# DOCX structure test — bytes start with PK magic (valid ZIP/DOCX)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_execute_writes_valid_docx_bytes_to_workspace():
    """On sandbox success with valid bytes, write_binary_file receives non-empty bytes
    that start with PK\\x03\\x04 (DOCX is a ZIP archive)."""
    from app.harnesses.contract_review_docx import _generate_docx_post_execute
    ws = _make_workspace_mock()

    # Real-ish DOCX magic bytes prefix
    fake_docx = b"PK\x03\x04" + b"\x00" * 100

    with patch("app.services.sandbox_service.get_sandbox_service") as gs:
        gs.return_value = _make_sandbox_success_mock()
        with patch("httpx.AsyncClient") as hc_cls:
            hc_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=MagicMock(
                    content=fake_docx,
                    raise_for_status=lambda: None,
                )
            )
            result = await _generate_docx_post_execute(
                harness_run_id="abc12345",
                thread_id="thr",
                user_id="u",
                user_email="e@x",
                token="tok",
                phase_results={},
                workspace=ws,
            )

    ws.write_binary_file.assert_called_once()
    call_args = ws.write_binary_file.call_args
    kwargs = call_args.kwargs or {}
    args = call_args.args or ()
    # content_bytes is 3rd positional or keyword
    content_bytes = kwargs.get("content_bytes") or (args[2] if len(args) > 2 else None)
    assert content_bytes is not None
    assert content_bytes[:4] == b"PK\x03\x04", "DOCX bytes must start with ZIP magic"
    assert result["size_bytes"] == len(fake_docx)


# ---------------------------------------------------------------------------
# DOCX module acceptance criteria checks
# ---------------------------------------------------------------------------

class TestModuleAcceptanceCriteria:
    """Quick grep-style checks as Python code — verify static patterns."""

    def test_module_has_confidential_and_color_codes(self):
        """CONFIDENTIAL + 3 pastel hex codes must appear in module source."""
        import inspect
        from app.harnesses import contract_review_docx as m
        source = inspect.getsource(m)
        for token in ["CONFIDENTIAL", "E6F4EA", "FEF7E0", "FCE8E6"]:
            assert token in source, f"Missing {token!r} in contract_review_docx module"

    def test_render_summary_markdown_called_from_docx_module(self):
        """_render_summary_markdown must be imported/called in contract_review_docx."""
        import inspect
        from app.harnesses import contract_review_docx as m
        source = inspect.getsource(m)
        assert "_render_summary_markdown" in source, (
            "REVIEW #6: _render_summary_markdown must be called in contract_review_docx"
        )

    def test_wrote_binary_in_module(self):
        """REVIEW #7: wrote_binary flag must appear in contract_review_docx."""
        import inspect
        from app.harnesses import contract_review_docx as m
        source = inspect.getsource(m)
        assert "wrote_binary" in source

    def test_audit_actions_in_module(self):
        """Both audit actions must be in the module."""
        import inspect
        from app.harnesses import contract_review_docx as m
        source = inspect.getsource(m)
        assert "contract_review_docx_generated" in source
        assert "contract_review_docx_failed" in source
