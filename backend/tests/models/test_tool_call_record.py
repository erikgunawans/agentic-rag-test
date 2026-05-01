"""Phase 11 Plan 11-01 — unit tests for ToolCallRecord extensions.

Covers:
  - tool_call_id / status fields default to None (legacy backwards compat)
  - explicit field round-trip via model_dump
  - status Literal validation rejects unknown values
  - 50 KB head-truncate validator on `output` (dict + str inputs)
  - Truncation marker shape: "\\n…[truncated, N more bytes]\\n" with U+2026
  - UTF-8 byte-length measurement (not character length)
  - ToolCallSummary backwards compat with default-None fields per call

D-P11-04 / D-P11-08 / D-P11-11.
"""
import json

import pytest
from pydantic import ValidationError

from app.models.tools import MAX_OUTPUT_BYTES, ToolCallRecord, ToolCallSummary


def test_optional_fields_default_none():
    r = ToolCallRecord(tool="x", input={}, output={})
    assert r.tool_call_id is None
    assert r.status is None


def test_explicit_fields_round_trip():
    r = ToolCallRecord(
        tool="execute_code",
        input={"code": "print(1)"},
        output={"stdout": "1"},
        tool_call_id="call_abc",
        status="success",
    )
    d = r.model_dump()
    assert d["tool_call_id"] == "call_abc"
    assert d["status"] == "success"
    assert d["output"] == {"stdout": "1"}


def test_status_literal_rejects_unknown():
    with pytest.raises(ValidationError):
        ToolCallRecord(tool="x", input={}, output={}, status="weird")


def test_dict_output_under_cap_unchanged():
    payload = {"k": "v" * 100}
    r = ToolCallRecord(tool="x", input={}, output=payload)
    assert r.output == payload


def test_str_output_under_cap_unchanged():
    s = "x" * 1000
    r = ToolCallRecord(tool="x", input={}, output=s)
    assert r.output == s


def test_dict_output_over_cap_truncated_to_string():
    big = {"data": "y" * 60_000}
    serialized = json.dumps(big, ensure_ascii=False)
    overflow = len(serialized.encode("utf-8")) - MAX_OUTPUT_BYTES
    r = ToolCallRecord(tool="x", input={}, output=big)
    assert isinstance(r.output, str)
    assert "\n…[truncated, " in r.output
    assert r.output.endswith(" more bytes]\n")
    assert f"{overflow} more bytes" in r.output


def test_str_output_over_cap_truncated():
    s = "z" * 60_000
    r = ToolCallRecord(tool="x", input={}, output=s)
    overflow = 60_000 - MAX_OUTPUT_BYTES
    assert isinstance(r.output, str)
    assert r.output.startswith("z" * 100)  # head preserved
    assert f"\n…[truncated, {overflow} more bytes]\n" in r.output


def test_truncation_marker_uses_unicode_ellipsis():
    s = "a" * 60_000
    r = ToolCallRecord(tool="x", input={}, output=s)
    assert "…" in r.output
    assert "..." not in r.output  # ASCII triple-dot must NOT appear


def test_truncation_byte_count_in_marker():
    s = "a" * 51_234
    r = ToolCallRecord(tool="x", input={}, output=s)
    assert "1234 more bytes" in r.output


def test_legacy_summary_round_trip():
    summary = ToolCallSummary(
        agent=None,
        calls=[ToolCallRecord(tool="x", input={}, output={})],
    )
    d = summary.model_dump()
    assert d["calls"][0]["tool_call_id"] is None
    assert d["calls"][0]["status"] is None


def test_byte_size_uses_utf8():
    # 30000 'é' chars = 60000 UTF-8 bytes (over 50KB cap)
    s = "é" * 30_000
    r = ToolCallRecord(tool="x", input={}, output=s)
    assert isinstance(r.output, str)
    assert "…[truncated" in r.output
