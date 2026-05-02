"""Phase 11 + 12 + 13 — extends ToolCallRecord with persistence helpers and
introduces ToolDefinition for the Phase 13 unified tool registry.

Phase 11 (D-P11-04 / D-P11-08 / D-P11-11): tool_call_id, status, and 50 KB
head-truncate validator on `output`.

Phase 12 (D-P12-14): two optional JSONB sub-keys for HIST-02 / HIST-03 —
sub_agent_state and code_execution_state. The latter has its own validator
that head-truncates the `stdout` and `stderr` keys to 50 KB each (D-P12-14
parity with D-P11-04). sub_agent_state has no cap in v1 (typical <5 KB).

Phase 13 (TOOL-04, TOOL-06; D-P13-01, D-P13-02): ToolDefinition is the
registry entry shared by native tools (adapter wrap), skills (parameterless),
and MCP tools (deferred per-connect).

Truncation lives inside the model so every caller (chat.py multi-agent branch,
sandbox tool dispatch, tests, future tool consumers) gets it for free —
no per-call utility.
"""
import json
from typing import Awaitable, Callable, Literal

from pydantic import BaseModel, ConfigDict, field_validator

# D-P11-04: 50 KB cap measured in UTF-8 bytes (~12.5K tokens).
MAX_OUTPUT_BYTES = 50_000


def _head_truncate_string(data: str, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
    """Phase 11 / 12 shared head-truncate helper. Returns the original string
    if under the cap; otherwise returns the head with a marker appended.
    """
    data_bytes = data.encode("utf-8")
    n_bytes = len(data_bytes)
    if n_bytes <= max_bytes:
        return data
    overflow = n_bytes - max_bytes
    head_bytes = data_bytes[:max_bytes]
    head = head_bytes.decode("utf-8", errors="ignore")
    return f"{head}\n…[truncated, {overflow} more bytes]\n"


class ToolCallRecord(BaseModel):
    """Persisted record of a single tool execution.

    Phase 11 additions (D-P11-08):
      - tool_call_id: OpenAI tool-call UUID — required for new rows; legacy
        rows have None and fall back to flat history reconstruction (D-P11-03).
      - status: success / error / timeout. Sandbox calls derive from
        Phase 10 tool_result error_type/exit_code; non-sandbox calls use
        success or error.

    Phase 12 additions (D-P12-14):
      - sub_agent_state: optional JSONB for HIST-02 (sub-agent panels at
        history reload). No cap in v1 (typical <5 KB).
      - code_execution_state: optional JSONB for HIST-03 (code-execution
        panels at history reload). stdout/stderr keys head-truncated to 50 KB
        each via dedicated validator (parity with D-P11-04).
    No schema migration: messages.tool_calls is JSONB.
    """
    tool: str
    input: dict
    output: dict | str
    error: str | None = None
    tool_call_id: str | None = None
    status: Literal["success", "error", "timeout"] | None = None
    # D-P12-14: optional JSONB sub-keys — write-time materialization for
    # HIST-02 (sub-agent panels at history reload) and HIST-03 (code-execution
    # panels at history reload). No schema migration: messages.tool_calls is JSONB.
    sub_agent_state: dict | None = None
    code_execution_state: dict | None = None

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

    @field_validator("code_execution_state")
    @classmethod
    def truncate_code_execution_streams(cls, v):
        """D-P12-14: head-truncate stdout and stderr to 50 KB each.

        Other keys (code, exit_code, execution_ms, files, error_type) are
        passed through unchanged. Missing stdout/stderr keys are tolerated
        (some callers may persist partial state).
        """
        if v is None:
            return None
        # Mutate a shallow copy so we don't surprise callers holding the dict.
        out = dict(v)
        for stream_key in ("stdout", "stderr"):
            stream_val = out.get(stream_key)
            if isinstance(stream_val, str):
                out[stream_key] = _head_truncate_string(stream_val)
        return out


class ToolCallSummary(BaseModel):
    """Stored in messages.tool_calls JSONB."""
    agent: str | None = None
    calls: list[ToolCallRecord]


class ToolDefinition(BaseModel):
    """Phase 13 (TOOL-04, TOOL-06): registry entry for native, skill, or MCP tools.

    D-P13-01: native tools register via adapter wrap (executor delegates to ToolService.execute_tool).
    D-P13-02: skills register as first-class tools with schema={} (parameterless).
    Loading: 'immediate' = registered at startup; 'deferred' = registered per-request or per-connect.

    Note: `protected_namespaces=()` is required because `schema` shadows
    pydantic.BaseModel's reserved `schema()` classmethod. The field is the
    OpenAI tool-call schema dict; renaming it would propagate the rename
    through every register() callsite (D-P13-01..02) and the LLM-tools-array
    builder, so we silence the warning instead.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())
    name: str
    description: str
    schema: dict
    source: Literal["native", "skill", "mcp"]
    loading: Literal["immediate", "deferred"]
    executor: Callable[..., Awaitable[dict | str]]
