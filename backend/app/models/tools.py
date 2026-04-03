from pydantic import BaseModel


class ToolCallRecord(BaseModel):
    """Persisted record of a single tool execution."""
    tool: str
    input: dict
    output: dict | str
    error: str | None = None


class ToolCallSummary(BaseModel):
    """Stored in messages.tool_calls JSONB."""
    calls: list[ToolCallRecord]
