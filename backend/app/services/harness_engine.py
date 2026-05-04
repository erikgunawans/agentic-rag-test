"""Phase 20 / v1.3 — Harness Engine (HARN-02..09, PANEL-01, PANEL-03, OBS-01, D-12).

Async-generator dispatcher that drives a HarnessDefinition through its phases,
persists state via harness_runs_service, emits harness_phase_* SSE events,
and writes single-writer progress.md after each phase transition.

Three peer execution modes at chat.py top: standard / deep_mode / harness_engine.
Phase 19's sub_agent_loop is REUSED VERBATIM for llm_agent phases (no duplication).

--- HARN-09 SSE event suite (B1 fix — explicit documentation) ---
Phase 20 emits 6 of the 9 HARN-09 events:
  [Phase 20] harness_phase_start          — emitted at the start of every phase dispatch
  [Phase 20] harness_phase_complete       — emitted after a phase returns success
  [Phase 20] harness_phase_error          — emitted on timeout / crash / cancellation / egress block
  [Phase 20] harness_complete             — emitted once at engine end (status: completed/failed/cancelled)
  [Phase 20] harness_sub_agent_start      — wraps run_sub_agent_loop drain (llm_agent phase only)
  [Phase 20] harness_sub_agent_complete   — emitted after sub_agent_loop returns its terminal_result

Phase 21 reserves but does NOT emit:
  [Phase 21 - deferred] harness_batch_start         — for LLM_BATCH_AGENTS
  [Phase 21 - deferred] harness_batch_complete      — for LLM_BATCH_AGENTS
  [Phase 21 - deferred] harness_human_input_required — for LLM_HUMAN_INPUT

The Phase 21 reserved event names are listed below as constants for forward
compatibility, but if a Phase-21-only PhaseType is dispatched in v1.3 the
engine returns {error: 'phase_type_not_implemented', code: 'PHASE21_PENDING'}
and the frontend treats those event names as no-ops.

--- HARN-07 cancellation (B3 fix — dual-layer arms) ---
Two independent cancellation channels feed the same `return` exit:
  Layer 1 (in-process): asyncio.Event passed by reference from caller.
                        Fast same-stream cancel (rarely used in v1.3, single
                        SSE per thread).
  Layer 2 (cross-request DB poll): before each phase dispatch the engine
                        calls harness_runs_service.get_run_by_id and checks
                        .status == 'cancelled'. This is how the Cancel
                        button on a SEPARATE HTTP request takes effect (the
                        cancel endpoint flips the DB row, the engine notices
                        at the next phase boundary). Polling cost: 1 row per
                        phase × ~5 phases per smoke run = trivial.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.harnesses.types import (
    DEFAULT_TIMEOUT_SECONDS,
    PANEL_LOCKED_EXCLUDED_TOOLS,
    HarnessDefinition,
    PhaseDefinition,
    PhaseType,
)
from app.services import harness_runs_service, agent_todos_service
from app.services.workspace_service import WorkspaceService
from app.services.sub_agent_loop import run_sub_agent_loop
from app.services.redaction.egress import egress_filter

logger = logging.getLogger(__name__)

settings = get_settings()

# OBS-01: single-writer progress.md path
PROGRESS_PATH = "progress.md"

# ---------------------------------------------------------------------------
# HARN-09 SSE event-name constants
# ---------------------------------------------------------------------------

# [Phase 20] — implemented
EVT_PHASE_START = "harness_phase_start"
EVT_PHASE_COMPLETE = "harness_phase_complete"
EVT_PHASE_ERROR = "harness_phase_error"
EVT_COMPLETE = "harness_complete"
EVT_SUB_AGENT_START = "harness_sub_agent_start"        # B1 fix
EVT_SUB_AGENT_COMPLETE = "harness_sub_agent_complete"  # B1 fix

# [Phase 21] — implemented in Plan 21-02 (HIL) and Plan 21-03 (batch)
EVT_BATCH_START = "harness_batch_start"                 # [Phase 21] — Plan 21-03
EVT_BATCH_COMPLETE = "harness_batch_complete"           # [Phase 21] — Plan 21-03
EVT_HUMAN_INPUT_REQUIRED = "harness_human_input_required"  # [Phase 21] — Plan 21-02
EVT_BATCH_ITEM_START = "harness_batch_item_start"       # Phase 21 D-08 — Plan 21-03
EVT_BATCH_ITEM_COMPLETE = "harness_batch_item_complete"  # Phase 21 D-08 — Plan 21-03


# ---------------------------------------------------------------------------
# Pydantic models for structured LLM output
# ---------------------------------------------------------------------------

class HumanInputQuestion(BaseModel):
    """Output schema for LLM_HUMAN_INPUT phase question generation (HIL-01)."""
    question: str = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_harness_engine(
    *,
    harness: HarnessDefinition,
    harness_run_id: str,
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    registry,                          # parent ConversationRegistry — egress (SEC-04)
    cancellation_event: asyncio.Event,
    start_phase_index: int = 0,        # Phase 21 D-03 — HIL resume passes current_phase + 1
) -> AsyncIterator[dict]:
    """Drive harness phases. Yields SSE-shaped dicts the chat.py SSE generator forwards.

    Args:
        harness:            HarnessDefinition to execute.
        harness_run_id:     UUID of the harness_runs row (created by caller before invoke).
        thread_id:          Thread UUID — for workspace + todos + DB scoping.
        user_id:            Authenticated user UUID.
        user_email:         Authenticated user email (for audit log).
        token:              JWT access token (parent token, never minted fresh — D-22).
        registry:           Parent ConversationRegistry — egress filter (D-21/SEC-04).
        cancellation_event: In-process cancellation arm (Layer 1, HARN-07).
        start_phase_index:  Phase 21 D-03 — phase index to start from (default 0
                            preserves byte-identical behavior for all existing
                            callers). HIL resume passes current_phase + 1 so the
                            engine skips already-completed phases on resume.

    Yields:
        SSE-shaped dicts. Every event carries harness_run_id for frontend correlation.
        Final yield is always {"type": "harness_complete", ...} unless a checkpoint
        or Phase 21 gate is hit (not applicable in v1.3).
    """
    try:
        async for event in _run_harness_engine_inner(
            harness=harness,
            harness_run_id=harness_run_id,
            thread_id=thread_id,
            user_id=user_id,
            user_email=user_email,
            token=token,
            registry=registry,
            cancellation_event=cancellation_event,
            start_phase_index=start_phase_index,
        ):
            yield event
    except Exception as exc:
        logger.error(
            "harness_engine crash harness_run_id=%s exc=%s",
            harness_run_id,
            exc,
            exc_info=True,
        )
        # D-19: sanitized — no stack trace in SSE payload
        yield {
            "type": EVT_PHASE_ERROR,
            "harness_run_id": harness_run_id,
            "phase_index": -1,
            "code": "ENGINE_CRASH",
            "detail": str(exc)[:500],
        }
        yield {"type": EVT_COMPLETE, "harness_run_id": harness_run_id, "status": "failed"}


async def _run_harness_engine_inner(
    *,
    harness: HarnessDefinition,
    harness_run_id: str,
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    registry,
    cancellation_event: asyncio.Event,
    start_phase_index: int = 0,
) -> AsyncIterator[dict]:
    """Inner harness engine — phase loop + dual-layer cancellation + PANEL-01 todos."""

    # --- 1. Initialize agent_todos for all phases (PANEL-01) ---
    todos = [
        {
            "content": f"[{harness.display_name}] {phase.name}",
            "status": "pending",
            "position": idx,
        }
        for idx, phase in enumerate(harness.phases)
    ]
    try:
        await agent_todos_service.write_todos(thread_id, todos, token)
        yield {"type": "todos_updated", "todos": todos}
    except Exception as exc:
        logger.warning(
            "harness_engine: write_todos (init) failed harness_run_id=%s: %s",
            harness_run_id,
            exc,
        )

    # --- 2. Initial progress.md write (OBS-01) ---
    ws: WorkspaceService | None = None
    try:
        ws = WorkspaceService(token=token)
        await ws.write_text_file(
            thread_id,
            PROGRESS_PATH,
            f"# Harness Progress: {harness.display_name}\n",
            source="harness",
        )
    except Exception as exc:
        logger.warning(
            "harness_engine: initial progress.md write failed harness_run_id=%s: %s",
            harness_run_id,
            exc,
        )

    # --- 3. Phase loop ---
    for phase_index, phase in enumerate(harness.phases):
        if phase_index < start_phase_index:
            continue   # Phase 21 D-03 — already recorded in phase_results from prior run

        # === B3 dual-layer cancellation check (HARN-07) ===

        # Layer 1: in-process asyncio.Event (fast, same-process Cancel)
        if cancellation_event.is_set():
            yield {
                "type": EVT_PHASE_ERROR,
                "harness_run_id": harness_run_id,
                "phase_index": phase_index,
                "code": "cancelled",
                "detail": "Cancelled in-process before phase",
            }
            try:
                await harness_runs_service.cancel(
                    run_id=harness_run_id,
                    user_id=user_id,
                    user_email=user_email,
                    token=token,
                )
            except Exception as exc:
                logger.warning("harness_engine: cancel() failed: %s", exc)
            yield {"type": EVT_COMPLETE, "harness_run_id": harness_run_id, "status": "cancelled"}
            return

        # Layer 2: cross-request DB poll (Cancel button on separate HTTP request — B3)
        try:
            current_run = await harness_runs_service.get_run_by_id(
                run_id=harness_run_id, token=token
            )
        except Exception as exc:
            logger.warning(
                "harness_engine: get_run_by_id failed harness_run_id=%s: %s",
                harness_run_id,
                exc,
            )
            current_run = None

        if current_run is not None and current_run.get("status") == "cancelled":
            yield {
                "type": EVT_PHASE_ERROR,
                "harness_run_id": harness_run_id,
                "phase_index": phase_index,
                "code": "cancelled",
                "reason": "cancelled_by_user",
                "detail": "Cancelled by user via /cancel-harness endpoint",
            }
            # Status already 'cancelled' in DB — do not re-call cancel()
            yield {"type": EVT_COMPLETE, "harness_run_id": harness_run_id, "status": "cancelled"}
            return

        # --- Mark this phase as in_progress ---
        todos[phase_index]["status"] = "in_progress"
        try:
            await agent_todos_service.write_todos(thread_id, todos, token)
        except Exception as exc:
            logger.warning("harness_engine: write_todos (in_progress) failed: %s", exc)
        yield {"type": "todos_updated", "todos": todos}

        yield {
            "type": EVT_PHASE_START,
            "harness_run_id": harness_run_id,
            "phase_index": phase_index,
            "phase_name": phase.name,
            "phase_type": phase.phase_type.value,
        }

        timeout = phase.timeout_seconds or DEFAULT_TIMEOUT_SECONDS[phase.phase_type]

        # --- Dispatch phase with timeout ---
        result: dict | None = None
        try:
            async with asyncio.timeout(timeout):
                async for sub_ev in _dispatch_phase(
                    phase=phase,
                    harness_run_id=harness_run_id,
                    thread_id=thread_id,
                    user_id=user_id,
                    user_email=user_email,
                    token=token,
                    registry=registry,
                    phase_index=phase_index,
                ):
                    if sub_ev.get("_terminal_phase_result") is not None:
                        result = sub_ev["_terminal_phase_result"]
                        break
                    # Forward sub-agent events (harness_sub_agent_start/complete etc.)
                    yield sub_ev
        except asyncio.TimeoutError:
            result = {
                "error": "phase_timeout",
                "code": "TIMEOUT",
                "detail": f"Phase '{phase.name}' exceeded {timeout}s",
            }
        except Exception as exc:
            logger.error(
                "harness_engine: phase crash harness_run_id=%s phase=%s exc=%s",
                harness_run_id,
                phase.name,
                exc,
                exc_info=True,
            )
            result = {
                "error": "phase_crash",
                "code": "EXCEPTION",
                "detail": str(exc)[:500],
            }

        if result is None:
            result = {"error": "phase_no_result", "code": "NO_RESULT", "detail": "Phase returned no result"}

        # Phase 21 HIL-03: paused terminal short-circuits the entire engine.
        # Do NOT yield EVT_PHASE_COMPLETE, do NOT call advance_phase, do NOT call complete().
        # The harness_runs row was already transitioned to 'paused' by the dispatcher.
        if isinstance(result, dict) and result.get("paused"):
            yield {
                "type": EVT_COMPLETE,
                "harness_run_id": harness_run_id,
                "status": "paused",
            }
            return

        # --- Check for phase failure ---
        if isinstance(result, dict) and "error" in result:
            todos[phase_index]["status"] = "completed"
            try:
                await agent_todos_service.write_todos(thread_id, todos, token)
            except Exception as exc:
                logger.warning("harness_engine: write_todos (error) failed: %s", exc)

            yield {
                "type": EVT_PHASE_ERROR,
                "harness_run_id": harness_run_id,
                "phase_index": phase_index,
                "code": result.get("code", "UNKNOWN"),
                "detail": result.get("detail", ""),
            }

            try:
                await harness_runs_service.fail(
                    run_id=harness_run_id,
                    user_id=user_id,
                    user_email=user_email,
                    error_detail=result.get("detail", "")[:500],
                    token=token,
                )
            except Exception as exc:
                logger.warning("harness_engine: fail() DB call failed: %s", exc)

            await _append_progress(
                thread_id=thread_id,
                token=token,
                phase_index=phase_index,
                phase_name=phase.name,
                status="failed",
                detail=result.get("detail", "")[:500],
                workspace=ws,
            )
            yield {"type": EVT_COMPLETE, "harness_run_id": harness_run_id, "status": "failed"}
            return

        # --- Phase succeeded — advance state ---
        try:
            await harness_runs_service.advance_phase(
                run_id=harness_run_id,
                new_phase_index=phase_index + 1,
                phase_results_patch={
                    str(phase_index): {
                        "phase_name": phase.name,
                        "output": result,
                    }
                },
                token=token,
            )
        except Exception as exc:
            logger.warning(
                "harness_engine: advance_phase failed harness_run_id=%s: %s",
                harness_run_id,
                exc,
            )

        todos[phase_index]["status"] = "completed"
        try:
            await agent_todos_service.write_todos(thread_id, todos, token)
        except Exception as exc:
            logger.warning("harness_engine: write_todos (completed) failed: %s", exc)
        yield {"type": "todos_updated", "todos": todos}

        yield {
            "type": EVT_PHASE_COMPLETE,
            "harness_run_id": harness_run_id,
            "phase_index": phase_index,
            "phase_name": phase.name,
        }

        await _append_progress(
            thread_id=thread_id,
            token=token,
            phase_index=phase_index,
            phase_name=phase.name,
            status="completed",
            detail=_summarize_output(result, max_len=300),
            workspace=ws,
        )

    # --- All phases done ---
    try:
        await harness_runs_service.complete(
            run_id=harness_run_id,
            user_id=user_id,
            user_email=user_email,
            token=token,
        )
    except Exception as exc:
        logger.warning(
            "harness_engine: complete() DB call failed harness_run_id=%s: %s",
            harness_run_id,
            exc,
        )

    yield {"type": EVT_COMPLETE, "harness_run_id": harness_run_id, "status": "completed"}


# ---------------------------------------------------------------------------
# Per-phase dispatch (internal async generator)
# ---------------------------------------------------------------------------

async def _dispatch_phase(
    *,
    phase: PhaseDefinition,
    harness_run_id: str,
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    registry,
    phase_index: int,
) -> AsyncIterator[dict]:
    """Dispatch a single phase by PhaseType. Yields one or more dict events.

    For PROGRAMMATIC and LLM_SINGLE: yields exactly one {"_terminal_phase_result": ...}.
    For LLM_AGENT: yields harness_sub_agent_start → (sub-agent events) →
                   harness_sub_agent_complete → {"_terminal_phase_result": ...}.
    For Phase 21 reserved types: yields {"_terminal_phase_result": error dict}.
    """
    if phase.phase_type == PhaseType.PROGRAMMATIC:
        # Invoke synchronous/async programmatic executor
        if phase.executor is None:
            yield {
                "_terminal_phase_result": {
                    "error": "config_error",
                    "code": "MISSING_EXECUTOR",
                    "detail": f"PROGRAMMATIC phase '{phase.name}' has no executor",
                }
            }
            return

        inputs = await _read_workspace_files(thread_id, phase.workspace_inputs, token)
        if isinstance(inputs, dict) and "error" in inputs:
            yield {"_terminal_phase_result": inputs}
            return

        try:
            output = await phase.executor(
                inputs=inputs,
                token=token,
                thread_id=thread_id,
                harness_run_id=harness_run_id,
            )
        except Exception as exc:
            yield {
                "_terminal_phase_result": {
                    "error": "executor_failed",
                    "code": "EXECUTOR_ERROR",
                    "detail": str(exc)[:500],
                }
            }
            return

        if phase.workspace_output and isinstance(output, dict) and "content" in output:
            try:
                ws = WorkspaceService(token=token)
                await ws.write_text_file(
                    thread_id, phase.workspace_output, output["content"], source="harness"
                )
            except Exception as exc:
                logger.warning(
                    "_dispatch_phase: workspace write failed phase=%s: %s", phase.name, exc
                )

        yield {"_terminal_phase_result": output}
        return

    if phase.phase_type == PhaseType.LLM_SINGLE:
        # HARN-05: structured output via response_format=json_schema + Pydantic validation
        if phase.output_schema is None:
            yield {
                "_terminal_phase_result": {
                    "error": "config_error",
                    "code": "MISSING_SCHEMA",
                    "detail": f"llm_single phase '{phase.name}' requires output_schema",
                }
            }
            return

        inputs = await _read_workspace_files(thread_id, phase.workspace_inputs, token)
        if isinstance(inputs, dict) and "error" in inputs:
            yield {"_terminal_phase_result": inputs}
            return

        messages = _build_llm_single_messages(phase, inputs)

        # SEC-04: egress filter pre-call
        if registry is not None:
            payload = json.dumps(messages, ensure_ascii=False)
            er = egress_filter(payload, registry, None)
            if er.tripped:
                yield {
                    "_terminal_phase_result": {
                        "error": "egress_blocked",
                        "code": "PII_EGRESS_BLOCKED",
                        "detail": "PII detected in llm_single payload",
                    }
                }
                return

        schema = phase.output_schema.model_json_schema()

        # Import here to avoid circular dependency at module level
        from app.services.openrouter_service import OpenRouterService
        or_svc = OpenRouterService()

        try:
            llm_result = await or_svc.complete_with_tools(
                messages=messages,
                tools=None,
                model=None,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": phase.output_schema.__name__,
                        "schema": schema,
                        "strict": True,
                    },
                },
            )
        except Exception as exc:
            yield {
                "_terminal_phase_result": {
                    "error": "llm_call_failed",
                    "code": "LLM_ERROR",
                    "detail": str(exc)[:500],
                }
            }
            return

        try:
            parsed = phase.output_schema.model_validate_json(
                llm_result.get("content", "")
            )
        except (ValidationError, Exception) as ve:
            yield {
                "_terminal_phase_result": {
                    "error": "schema_validation_failed",
                    "code": "INVALID_OUTPUT",
                    "detail": str(ve)[:500],
                }
            }
            return

        if phase.validator is not None:
            try:
                phase.validator(parsed)
            except Exception as exc:
                yield {
                    "_terminal_phase_result": {
                        "error": "validator_failed",
                        "code": "VALIDATOR",
                        "detail": str(exc)[:500],
                    }
                }
                return

        output_dict = parsed.model_dump()

        if phase.workspace_output:
            try:
                ws = WorkspaceService(token=token)
                await ws.write_text_file(
                    thread_id,
                    phase.workspace_output,
                    json.dumps(output_dict, ensure_ascii=False, indent=2),
                    source="harness",
                )
            except Exception as exc:
                logger.warning(
                    "_dispatch_phase: workspace write failed phase=%s: %s", phase.name, exc
                )

        yield {"_terminal_phase_result": output_dict}
        return

    if phase.phase_type == PhaseType.LLM_AGENT:
        # PANEL-03 LLM-side defense: strip excluded tools from this phase's list
        curated_tools = [t for t in phase.tools if t not in PANEL_LOCKED_EXCLUDED_TOOLS]
        description = phase.system_prompt_template or phase.description or phase.name

        # === B1 fix — wrap sub_agent_loop drain with start/complete events ===
        yield {
            "type": EVT_SUB_AGENT_START,
            "harness_run_id": harness_run_id,
            "phase_index": phase_index,
            "phase_name": phase.name,
            "task_id": harness_run_id,
        }

        collected_text: list[str] = []
        sub_status = "completed"
        sub_result: dict = {}

        # sub_agent_loop requires an OpenRouter-compatible async client
        from app.services.openrouter_service import OpenRouterService
        or_svc = OpenRouterService()

        # sys_settings minimal dict for sub_agent_loop
        from app.services.system_settings_service import get_system_settings
        try:
            sys_settings = get_system_settings()
        except Exception:
            sys_settings = {}

        try:
            async for ev in run_sub_agent_loop(
                description=description,
                context_files=phase.workspace_inputs,
                parent_user_id=user_id,
                parent_user_email=user_email,
                parent_token=token,
                parent_tool_context={},
                parent_thread_id=thread_id,
                parent_user_msg_id=harness_run_id,   # SSE correlation — use run_id
                client=or_svc.client,
                sys_settings=sys_settings,
                web_search_effective=False,           # harness phases don't inherit web_search
                task_id=harness_run_id,
                parent_redaction_registry=registry,  # exact kwarg from sub_agent_loop signature
            ):
                if "_terminal_result" in ev:
                    tr = ev["_terminal_result"]
                    if "error" in tr:
                        sub_status = "failed"
                        sub_result = tr
                    else:
                        collected_text.append(tr.get("text", ""))
                        sub_result = {"text": "\n".join(collected_text)}
                    break
                # Forward non-terminal events (tool_start, tool_result, workspace_updated etc.)
                yield ev
        except Exception as exc:
            logger.error(
                "_dispatch_phase: sub_agent_loop crash phase=%s: %s", phase.name, exc, exc_info=True
            )
            sub_status = "failed"
            sub_result = {
                "error": "sub_agent_crashed",
                "code": "TASK_LOOP_CRASH",
                "detail": str(exc)[:500],
            }
        finally:
            # Always emit complete event — even on early break or exception (B1)
            yield {
                "type": EVT_SUB_AGENT_COMPLETE,
                "harness_run_id": harness_run_id,
                "phase_index": phase_index,
                "phase_name": phase.name,
                "task_id": harness_run_id,
                "status": sub_status,
                "result_summary": (
                    sub_result.get("text", "")[:200]
                    if isinstance(sub_result, dict) else ""
                ),
            }

        if sub_status == "failed":
            yield {"_terminal_phase_result": sub_result}
            return

        output: dict = {"text": "\n".join(collected_text)}
        if phase.workspace_output:
            try:
                ws = WorkspaceService(token=token)
                await ws.write_text_file(
                    thread_id, phase.workspace_output, output["text"], source="harness"
                )
            except Exception as exc:
                logger.warning(
                    "_dispatch_phase: workspace write failed phase=%s: %s", phase.name, exc
                )

        yield {"_terminal_phase_result": output}
        return

    # Phase 21 / HIL-01..03: LLM_HUMAN_INPUT dispatch.
    if phase.phase_type == PhaseType.LLM_HUMAN_INPUT:
        # 1. Read prior-phase context files (informs the LLM-generated question)
        inputs = await _read_workspace_files(thread_id, phase.workspace_inputs, token)
        if isinstance(inputs, dict) and inputs.get("error"):
            yield {"_terminal_phase_result": inputs}
            return

        # 2. Build messages (system prompt asks for one question; user content = inputs).
        messages = _build_llm_single_messages(phase, inputs)

        # 3. Egress filter (SEC-04 / T-21-02-01) — mirrors LLM_SINGLE pattern.
        if registry is not None:
            payload = json.dumps(messages, ensure_ascii=False)
            er = egress_filter(payload, registry, None)
            if er.tripped:
                yield {
                    "_terminal_phase_result": {
                        "error": "egress_blocked",
                        "code": "PII_EGRESS_BLOCKED",
                        "detail": "PII detected in llm_human_input payload",
                    }
                }
                return

        # 4. LLM call with json_schema response_format against HumanInputQuestion.
        schema = HumanInputQuestion.model_json_schema()

        from app.services.openrouter_service import OpenRouterService
        or_svc = OpenRouterService()

        try:
            llm_result = await or_svc.complete_with_tools(
                messages=messages,
                tools=None,
                model=None,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "HumanInputQuestion",
                        "schema": schema,
                        "strict": True,
                    },
                },
            )
        except Exception as exc:
            logger.error(
                "_dispatch_phase: HIL LLM call failed phase=%s: %s", phase.name, exc
            )
            yield {
                "_terminal_phase_result": {
                    "error": "hil_llm_failed",
                    "code": "HIL_LLM_FAILED",
                    "detail": str(exc)[:500],
                }
            }
            return

        # 5. Validate via Pydantic (T-21-02-02 — caps oversized question).
        try:
            parsed = HumanInputQuestion.model_validate_json(llm_result.get("content", ""))
        except Exception as exc:
            yield {
                "_terminal_phase_result": {
                    "error": "hil_invalid_question",
                    "code": "HIL_VALIDATION_FAILED",
                    "detail": str(exc)[:500],
                }
            }
            return

        question_text = parsed.question

        # 6. Stream the question as delta events (HIL-02 — chat-bubble, NOT phase panel).
        for chunk in _chunk_for_delta(question_text):
            yield {"type": "delta", "content": chunk, "harness_run_id": harness_run_id}

        # 7. Emit harness_human_input_required event (D-04 sequence).
        yield {
            "type": EVT_HUMAN_INPUT_REQUIRED,
            "question": question_text,
            "workspace_output_path": phase.workspace_output,
            "harness_run_id": harness_run_id,
        }

        # 8. DB transition to 'paused' BEFORE returning (HIL-03 / D-21 ordering).
        #    Uses Task 0's new harness_runs_service.pause() helper — NOT advance_phase
        #    (whose guard rejects the paused transition).
        try:
            await harness_runs_service.pause(
                run_id=harness_run_id,
                user_id=user_id,
                user_email=user_email,
                token=token,
            )
        except Exception as exc:
            logger.warning(
                "_dispatch_phase: HIL pause transition failed run=%s: %s",
                harness_run_id, exc,
            )

        # 9. Special HIL terminal marker — outer loop must NOT advance to next phase.
        yield {"_terminal_phase_result": {"paused": True, "question": question_text}}
        return

    # [Phase 21 - Plan 21-03 deferred] — LLM_BATCH_AGENTS still stubbed.
    if phase.phase_type == PhaseType.LLM_BATCH_AGENTS:
        yield {
            "_terminal_phase_result": {
                "error": "phase_type_not_implemented",
                "code": "PHASE21_PENDING",
                "detail": "LLM_BATCH_AGENTS reserved for Plan 21-03",
            }
        }
        return

    yield {
        "_terminal_phase_result": {
            "error": "unknown_phase_type",
            "code": "UNKNOWN_PHASE",
            "detail": f"Unrecognized phase_type {phase.phase_type}",
        }
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _read_workspace_files(
    thread_id: str,
    paths: list[str],
    token: str,
) -> dict[str, str] | dict:
    """Read workspace files by path. Returns dict[path, content] or error dict."""
    if not paths:
        return {}
    ws = WorkspaceService(token=token)
    result: dict[str, str] = {}
    for path in paths:
        read_result = await ws.read_file(thread_id, path)
        if "error" in read_result:
            return {
                "error": read_result["error"],
                "code": "WS_READ_ERROR",
                "detail": read_result.get("detail", "workspace read failed"),
                "file_path": path,
            }
        result[path] = read_result.get("content", "")
    return result


def _build_llm_single_messages(
    phase: PhaseDefinition,
    inputs: dict[str, str],
) -> list[dict]:
    """Build the messages list for an llm_single LLM call."""
    system_content = phase.system_prompt_template or (
        f"You are a precise AI assistant. Complete the task: {phase.description}"
    )
    user_parts = []
    for path, content in inputs.items():
        user_parts.append(f'<context_file path="{path}">\n{content}\n</context_file>')
    if user_parts:
        user_content = "\n\n".join(user_parts)
    else:
        user_content = "Please complete the task as described in the system prompt."

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def _chunk_for_delta(text: str, chunk_size: int = 32) -> list[str]:
    """Split a question into chunks for delta streaming (Phase 21 HIL-02).

    The frontend renders consecutive `delta` events into a single assistant
    message bubble — same UX as the standard chat loop. Splitting the question
    into ~32-char chunks gives a typewriter feel without spamming events.
    """
    if not text:
        return []
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


def _summarize_output(result: dict, max_len: int = 300) -> str:
    """Produce a short summary string for progress.md."""
    if not isinstance(result, dict):
        return str(result)[:max_len]
    # Prefer 'text' or 'summary' keys; fall back to JSON dump
    for key in ("text", "summary", "content"):
        val = result.get(key)
        if val and isinstance(val, str):
            return val[:max_len]
    dumped = json.dumps(result, ensure_ascii=False)
    return dumped[:max_len]


async def _append_progress(
    *,
    thread_id: str,
    token: str,
    phase_index: int,
    phase_name: str,
    status: str,
    detail: str,
    workspace: WorkspaceService | None = None,
) -> None:
    """Append a phase-transition section to progress.md (OBS-01 single-writer)."""
    ws = workspace or WorkspaceService(token=token)
    try:
        existing = await ws.read_file(thread_id, PROGRESS_PATH)
        body = (
            existing.get("content", "# Harness Progress\n")
            if isinstance(existing, dict) and "content" in existing
            else "# Harness Progress\n"
        )
    except Exception:
        body = "# Harness Progress\n"

    status_emoji = "completed" if status == "completed" else "failed"
    body += f"\n## Phase {phase_index}: {phase_name}\nStatus: {status_emoji}\n{detail}\n"

    try:
        await ws.write_text_file(thread_id, PROGRESS_PATH, body, source="harness")
    except Exception as exc:
        logger.warning("harness_engine: _append_progress write failed: %s", exc)
