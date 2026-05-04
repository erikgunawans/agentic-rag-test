"""Phase 20 / Plan 20-07 — Unit tests for the smoke-echo harness.

10 test cases covering:
1. Definition shape (name, display_name, 2 phases)
2. Prerequisites (requires_upload, MIME types)
3. Phase 1 type (PROGRAMMATIC)
4. Phase 2 type (LLM_SINGLE)
5. Phase 2 Pydantic output schema (EchoSummary)
6. Phase 1 executor: 2 uploads → correct content + echo_count
7. Phase 1 executor: no uploads → echo_count==0 + placeholder line
8. Phase 1 executor: WorkspaceService failure → error dict
9. Registration when HARNESS_SMOKE_ENABLED=True
10. No registration when HARNESS_SMOKE_ENABLED=False
"""
from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_registry():
    """Clear the harness registry before each test."""
    from app.services import harness_registry
    harness_registry._reset_for_tests()
    yield
    harness_registry._reset_for_tests()


def _make_upload_file(file_path: str, size_bytes: int = 1024, mime_type: str = "application/pdf") -> dict:
    return {
        "file_path": file_path,
        "size_bytes": size_bytes,
        "source": "upload",
        "mime_type": mime_type,
    }


# ---------------------------------------------------------------------------
# Tests 1-5: Definition shape and static properties
# ---------------------------------------------------------------------------

class TestSmokeEchoDefinitionShape:
    def test_smoke_echo_definition_shape(self):
        from app.harnesses.smoke_echo import SMOKE_ECHO
        assert SMOKE_ECHO.name == "smoke-echo"
        assert SMOKE_ECHO.display_name == "Smoke Echo"
        # Phase 21 / Plan 21-06 extended the harness from 2 to 4 phases
        # (added llm_human_input + llm_batch_agents at indexes 2 + 3).
        assert len(SMOKE_ECHO.phases) == 4

    def test_smoke_echo_prerequisites_require_upload(self):
        from app.harnesses.smoke_echo import SMOKE_ECHO
        prereqs = SMOKE_ECHO.prerequisites
        assert prereqs.requires_upload is True
        assert "application/pdf" in prereqs.accepted_mime_types
        assert (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            in prereqs.accepted_mime_types
        )

    def test_smoke_echo_phase1_phase_type_is_programmatic(self):
        from app.harnesses.smoke_echo import SMOKE_ECHO
        from app.harnesses.types import PhaseType
        assert SMOKE_ECHO.phases[0].phase_type == PhaseType.PROGRAMMATIC

    def test_smoke_echo_phase2_phase_type_is_llm_single(self):
        from app.harnesses.smoke_echo import SMOKE_ECHO
        from app.harnesses.types import PhaseType
        assert SMOKE_ECHO.phases[1].phase_type == PhaseType.LLM_SINGLE

    def test_smoke_echo_phase2_has_pydantic_output_schema(self):
        from app.harnesses.smoke_echo import SMOKE_ECHO, EchoSummary
        assert SMOKE_ECHO.phases[1].output_schema is EchoSummary


# ---------------------------------------------------------------------------
# Tests 6-8: Phase 1 executor behaviour
# ---------------------------------------------------------------------------

class TestSmokeEchoPhase1Executor:
    @pytest.mark.asyncio
    async def test_smoke_echo_phase1_executor_writes_metadata(self):
        """Two upload files → echo_count==2, content includes both paths."""
        from app.harnesses.smoke_echo import _phase1_echo

        files = [
            _make_upload_file("uploads/contract.pdf", size_bytes=2048),
            _make_upload_file("uploads/annex.docx", size_bytes=512, mime_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )),
        ]

        mock_ws = AsyncMock()
        mock_ws.list_files = AsyncMock(return_value=files)

        with patch("app.harnesses.smoke_echo.WorkspaceService", return_value=mock_ws):
            result = await _phase1_echo(
                inputs={}, token="tok", thread_id="t1", harness_run_id="r1"
            )

        assert result["echo_count"] == 2
        assert "uploads/contract.pdf" in result["content"]
        assert "uploads/annex.docx" in result["content"]
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_smoke_echo_phase1_executor_handles_no_uploads(self):
        """Empty list → echo_count==0, placeholder line present."""
        from app.harnesses.smoke_echo import _phase1_echo

        mock_ws = AsyncMock()
        mock_ws.list_files = AsyncMock(return_value=[])

        with patch("app.harnesses.smoke_echo.WorkspaceService", return_value=mock_ws):
            result = await _phase1_echo(
                inputs={}, token="tok", thread_id="t1", harness_run_id="r1"
            )

        assert result["echo_count"] == 0
        assert "(no uploaded files in workspace)" in result["content"]
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_smoke_echo_phase1_executor_returns_error_on_ws_failure(self):
        """WorkspaceService.list_files raises → returns error dict."""
        from app.harnesses.smoke_echo import _phase1_echo

        mock_ws = AsyncMock()
        mock_ws.list_files = AsyncMock(side_effect=RuntimeError("connection refused"))

        with patch("app.harnesses.smoke_echo.WorkspaceService", return_value=mock_ws):
            result = await _phase1_echo(
                inputs={}, token="tok", thread_id="t1", harness_run_id="r1"
            )

        assert result["error"] == "list_files_failed"
        assert result["code"] == "WS_LIST_ERROR"
        assert "connection refused" in result["detail"]


# ---------------------------------------------------------------------------
# Tests 9-10: Gated registration
# ---------------------------------------------------------------------------

class TestSmokeEchoRegistration:
    def test_smoke_echo_registers_when_smoke_flag_true(self, monkeypatch):
        """With harness_smoke_enabled=True, registry contains 'smoke-echo'."""
        from app.services import harness_registry
        from app.config import get_settings

        harness_registry._reset_for_tests()

        settings = get_settings()
        monkeypatch.setattr(settings, "harness_smoke_enabled", True)

        with patch("app.harnesses.smoke_echo.get_settings", return_value=settings):
            import app.harnesses.smoke_echo as mod
            importlib.reload(mod)

        assert harness_registry.get_harness("smoke-echo") is not None

    def test_smoke_echo_does_not_register_when_smoke_flag_false(self, monkeypatch):
        """With harness_smoke_enabled=False, registry does NOT contain 'smoke-echo'."""
        from app.services import harness_registry
        from app.config import get_settings

        harness_registry._reset_for_tests()

        settings = get_settings()
        monkeypatch.setattr(settings, "harness_smoke_enabled", False)

        with patch("app.harnesses.smoke_echo.get_settings", return_value=settings):
            import app.harnesses.smoke_echo as mod
            importlib.reload(mod)

        assert harness_registry.get_harness("smoke-echo") is None
