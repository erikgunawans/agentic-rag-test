"""Phase 12 Plan 12-01 RED→GREEN tests for ToolCallRecord extensions.

Tests cover:
- New optional sub_agent_state and code_execution_state fields (HIST-02 / HIST-03)
- 50 KB head-truncate validator on code_execution_state.stdout / .stderr (D-P12-14)
- sub_agent_state non-cap rationale (D-P12-14)
- Phase 11 backwards compatibility (no regression on output validator, tool_call_id, status)
"""
import pytest
from pydantic import ValidationError
from app.models.tools import ToolCallRecord, ToolCallSummary, MAX_OUTPUT_BYTES


def test_optional_new_fields_default_none():
    r = ToolCallRecord(tool="x", input={}, output={})
    assert r.sub_agent_state is None
    assert r.code_execution_state is None


def test_sub_agent_state_round_trip():
    sub = {
        "mode": "explorer",
        "document_id": None,
        "reasoning": "Looking at the contract clauses",
        "explorer_tool_calls": [
            {"tool": "search_documents", "input": {"q": "indemnity"}, "output": "hits", "tool_call_id": "call_1"}
        ],
    }
    r = ToolCallRecord(
        tool="run_research_agent",
        input={"query": "q"},
        output={"answer": "a"},
        sub_agent_state=sub,
    )
    assert r.sub_agent_state == sub
    d = r.model_dump()
    assert d["sub_agent_state"] == sub


def test_code_execution_state_under_cap_unchanged():
    cs = {
        "code": "print(1)",
        "stdout": "1\n",
        "stderr": "",
        "exit_code": 0,
        "execution_ms": 12,
        "files": [],
        "error_type": None,
    }
    r = ToolCallRecord(tool="execute_code", input={"code": "print(1)"}, output={}, code_execution_state=cs)
    assert r.code_execution_state == cs


def test_code_execution_state_stdout_over_cap_truncated():
    big_stdout = "z" * 60_000
    cs = {
        "code": "loop()",
        "stdout": big_stdout,
        "stderr": "",
        "exit_code": 0,
        "execution_ms": 100,
        "files": [],
        "error_type": None,
    }
    r = ToolCallRecord(tool="execute_code", input={}, output={}, code_execution_state=cs)
    out = r.code_execution_state["stdout"]
    assert out.startswith("z" * 100)
    assert "\n…[truncated, 10000 more bytes]\n" in out
    # Other keys untouched
    assert r.code_execution_state["code"] == "loop()"
    assert r.code_execution_state["stderr"] == ""
    assert r.code_execution_state["exit_code"] == 0


def test_code_execution_state_stderr_over_cap_truncated():
    big_stderr = "e" * 70_000
    cs = {
        "code": "x",
        "stdout": "ok",
        "stderr": big_stderr,
        "exit_code": 1,
        "execution_ms": 5,
        "files": [],
        "error_type": "RuntimeError",
    }
    r = ToolCallRecord(tool="execute_code", input={}, output={}, code_execution_state=cs)
    err = r.code_execution_state["stderr"]
    assert err.startswith("e" * 100)
    assert "\n…[truncated, 20000 more bytes]\n" in err
    assert r.code_execution_state["stdout"] == "ok"  # untouched


def test_code_execution_state_both_streams_over_cap():
    cs = {
        "code": "x",
        "stdout": "a" * 55_000,
        "stderr": "b" * 65_000,
        "exit_code": 0,
        "execution_ms": 1,
        "files": [],
        "error_type": None,
    }
    r = ToolCallRecord(tool="execute_code", input={}, output={}, code_execution_state=cs)
    assert "\n…[truncated, 5000 more bytes]\n" in r.code_execution_state["stdout"]
    assert "\n…[truncated, 15000 more bytes]\n" in r.code_execution_state["stderr"]


def test_code_execution_state_truncation_marker_unicode_ellipsis():
    cs = {"code": "x", "stdout": "a" * 60_000, "stderr": "", "exit_code": 0, "execution_ms": 1, "files": [], "error_type": None}
    r = ToolCallRecord(tool="execute_code", input={}, output={}, code_execution_state=cs)
    assert "…" in r.code_execution_state["stdout"]
    assert "..." not in r.code_execution_state["stdout"]


def test_code_execution_state_byte_size_uses_utf8():
    # 30000 'é' chars = 60000 UTF-8 bytes
    cs = {"code": "x", "stdout": "é" * 30_000, "stderr": "", "exit_code": 0, "execution_ms": 1, "files": [], "error_type": None}
    r = ToolCallRecord(tool="execute_code", input={}, output={}, code_execution_state=cs)
    out = r.code_execution_state["stdout"]
    assert "…[truncated" in out


def test_sub_agent_state_no_truncation_in_v1():
    huge_reasoning = "x" * 100_000
    sub = {
        "mode": "analysis",
        "document_id": "doc-1",
        "reasoning": huge_reasoning,
        "explorer_tool_calls": [],
    }
    r = ToolCallRecord(tool="run_research_agent", input={}, output={}, sub_agent_state=sub)
    assert r.sub_agent_state["reasoning"] == huge_reasoning
    assert len(r.sub_agent_state["reasoning"]) == 100_000


def test_legacy_summary_round_trip_p12():
    summary = ToolCallSummary(
        agent=None,
        calls=[ToolCallRecord(tool="x", input={}, output={})],
    )
    d = summary.model_dump()
    assert d["calls"][0]["sub_agent_state"] is None
    assert d["calls"][0]["code_execution_state"] is None


def test_p11_tests_still_pass_regression(pytestconfig):
    # Sentinel: just constructs a Phase-11 shaped record to ensure import/serialization unchanged.
    r = ToolCallRecord(tool="x", input={}, output="ok", tool_call_id="call_1", status="success")
    assert r.tool_call_id == "call_1"
    assert r.status == "success"
    assert r.output == "ok"


def test_code_execution_state_missing_stdout_key_safe():
    cs_no_stdout = {"code": "x", "exit_code": 0, "execution_ms": 1, "files": [], "error_type": None}
    r = ToolCallRecord(tool="execute_code", input={}, output={}, code_execution_state=cs_no_stdout)
    # Should not raise — missing keys handled gracefully
    assert "stdout" not in r.code_execution_state or r.code_execution_state.get("stdout") is None
