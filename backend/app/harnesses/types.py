"""Phase 20 / v1.3 — Harness type definitions (HARN-10, PANEL-03).

Provides:
  - PhaseType enum: string-valued for JSON serialization + forward-compat Phase 21 members.
  - HarnessPrerequisites: Pydantic model for gatekeeper requirements + harness_intro.
  - PhaseDefinition: Pydantic model for a single phase — type, prompt, tools, schema, etc.
  - HarnessDefinition: Top-level model bundling name + prerequisites + phases list.
  - DEFAULT_TIMEOUT_SECONDS: per-PhaseType timeout override table (HARN-06).
  - PANEL_LOCKED_EXCLUDED_TOOLS: frozenset of tool names stripped from every llm_agent phase
    tool list (PANEL-03 LLM-side defense — write_todos/read_todos cannot be called by harness).
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# PhaseType enum
# ---------------------------------------------------------------------------

class PhaseType(str, Enum):
    PROGRAMMATIC = "programmatic"
    LLM_SINGLE = "llm_single"
    LLM_AGENT = "llm_agent"
    # Reserved for Phase 21 — engine MUST raise NotImplementedError if dispatched
    LLM_BATCH_AGENTS = "llm_batch_agents"
    LLM_HUMAN_INPUT = "llm_human_input"


# ---------------------------------------------------------------------------
# HarnessPrerequisites
# ---------------------------------------------------------------------------

class HarnessPrerequisites(BaseModel):
    """Gatekeeper requirements for a harness — drives multi-turn dialogue."""

    requires_upload: bool = False
    upload_description: str = ""                # e.g. "your contract DOCX or PDF"
    accepted_mime_types: list[str] = Field(default_factory=list)
    min_files: int = 1
    max_files: int = 1
    harness_intro: str                          # gatekeeper system-prompt fragment


# ---------------------------------------------------------------------------
# PhaseDefinition
# ---------------------------------------------------------------------------

class PhaseDefinition(BaseModel):
    """Definition of a single harness phase (HARN-10)."""

    model_config = {"arbitrary_types_allowed": True}

    name: str
    description: str = ""
    phase_type: PhaseType
    system_prompt_template: str = ""            # 5-15 lines per HARN-10
    tools: list[str] = Field(default_factory=list)  # tool names — curated subset
    output_schema: type[BaseModel] | None = None    # Pydantic class for llm_single
    validator: Callable[[BaseModel], None] | None = None  # optional, raises on invalid
    workspace_inputs: list[str] = Field(default_factory=list)
    workspace_output: str = ""                  # workspace path (no leading /)
    batch_size: int = 5                         # Phase 21 only
    post_execute: Callable[..., Awaitable[Any]] | None = None
    timeout_seconds: int = 120                  # default; per-PhaseType override below
    # PROGRAMMATIC executor — async callable receiving
    # (inputs: dict, token: str, thread_id: str, harness_run_id: str) → output dict
    executor: Callable[..., Awaitable[dict]] | None = None


# ---------------------------------------------------------------------------
# HarnessDefinition
# ---------------------------------------------------------------------------

class HarnessDefinition(BaseModel):
    """Top-level harness definition registered with HarnessRegistry."""

    model_config = {"arbitrary_types_allowed": True}

    name: str                                   # registry key, e.g. 'smoke-echo'
    display_name: str                           # UI label, e.g. 'Smoke Echo'
    prerequisites: HarnessPrerequisites
    phases: list[PhaseDefinition]


# ---------------------------------------------------------------------------
# Per-PhaseType default timeouts (HARN-06)
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_SECONDS: dict[PhaseType, int] = {
    PhaseType.PROGRAMMATIC: 60,
    PhaseType.LLM_SINGLE: 120,
    PhaseType.LLM_AGENT: 300,
    PhaseType.LLM_BATCH_AGENTS: 600,       # Phase 21
    PhaseType.LLM_HUMAN_INPUT: 86_400,     # Phase 21 — 24h human response window
}


# ---------------------------------------------------------------------------
# PANEL-03: tools excluded from every llm_agent phase (LLM-side defense)
# ---------------------------------------------------------------------------

PANEL_LOCKED_EXCLUDED_TOOLS: frozenset[str] = frozenset({"write_todos", "read_todos"})
