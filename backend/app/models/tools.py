"""Phase 11 — extends ToolCallRecord with tool_call_id, status, and a 50 KB
head-truncate validator on `output`. D-P11-04 / D-P11-08 / D-P11-11.

Truncation lives inside the model so every caller (chat.py both branches,
tests, future tool consumers) gets it for free — no per-call utility.
"""
import json
from typing import Literal

from pydantic import BaseModel, field_validator

# D-P11-04: 50 KB cap measured in UTF-8 bytes (~12.5K tokens).
MAX_OUTPUT_BYTES = 50_000


class ToolCallRecord(BaseModel):
    """Persisted record of a single tool execution.

    Phase 11 additions (D-P11-08):
      - tool_call_id: OpenAI tool-call UUID — required for new rows; legacy
        rows have None and fall back to flat history reconstruction (D-P11-03).
      - status: success / error / timeout. Sandbox calls derive from
        Phase 10 tool_result error_type/exit_code; non-sandbox calls use
        success or error.
    """
    tool: str
    input: dict
    output: dict | str
    error: str | None = None
    tool_call_id: str | None = None
    status: Literal["success", "error", "timeout"] | None = None

    @field_validator("output")
    @classmethod
    def truncate_output(cls, v):
        """D-P11-04 / D-P11-11: head-truncate serialized output to 50 KB.

        Both `dict` and `str` are accepted. When the serialized form fits in
        the cap, `dict` is returned unchanged (preserves callers reading
        structured fields like .stdout / .files). When the cap is exceeded,
        the value is collapsed to a STRING with the marker
        ``"\\n…[truncated, N more bytes]\\n"`` appended, where N is the byte
        overflow. Head (not middle/tail) is preserved per D-P11-04 — the
        start of search results / file listings / stdout is what follow-up
        questions reference.

        Marker uses Unicode U+2026 (single ellipsis) per CONTEXT.md §Specifics.
        """
        if isinstance(v, str):
            data_bytes = v.encode("utf-8")
        else:
            data_bytes = json.dumps(v, ensure_ascii=False).encode("utf-8")
        n_bytes = len(data_bytes)
        if n_bytes <= MAX_OUTPUT_BYTES:
            return v  # under cap — return original (preserves dict shape)
        overflow = n_bytes - MAX_OUTPUT_BYTES
        head_bytes = data_bytes[:MAX_OUTPUT_BYTES]
        # Decode safely on a partial UTF-8 boundary.
        head = head_bytes.decode("utf-8", errors="ignore")
        return f"{head}\n…[truncated, {overflow} more bytes]\n"


class ToolCallSummary(BaseModel):
    """Stored in messages.tool_calls JSONB."""
    agent: str | None = None
    calls: list[ToolCallRecord]
