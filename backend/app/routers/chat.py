import asyncio
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_client, get_supabase_authed_client
from app.services.openrouter_service import OpenRouterService
from app.services.tool_service import ToolService
from app.services import agent_service
from app.config import get_settings
from app.services.system_settings_service import get_system_settings
from app.services.redaction.prompt_guidance import get_pii_guidance_block
from app.services.skill_catalog_service import build_skill_catalog_block
from app.services.audit_service import log_action
from app.models.tools import ToolCallRecord, ToolCallSummary

# Phase 5 — chat-loop redaction integration (D-83..D-97)
from app.services.redaction import (
    ConversationRegistry,
    anonymize_tool_output,
    deanonymize_tool_args,
    filter_tool_output_by_registry,
)
from app.services.redaction.egress import egress_filter
from app.services.redaction_service import get_redaction_service
from app.services.llm_provider import LLMProviderClient
# Phase 19 / 19-04 (D-30): sub-agent loop — imported at module level so
# tests can patch 'app.routers.chat.run_sub_agent_loop'. When sub_agent_enabled
# is False the branch in run_deep_mode_loop never executes (D-17 byte-identical fallback).
from app.services.sub_agent_loop import run_sub_agent_loop
# Phase 19 / 19-05 (D-04): agent_runs_service — imported at module level so
# tests can patch 'app.routers.chat.agent_runs_service'. When sub_agent_enabled
# is False the resume-detection branch never executes (D-17 byte-identical fallback).
from app.services import agent_runs_service
# Phase 20 / Plan 20-04: harness routing — harness_runs_service + harness_registry.
# Imported at module level so tests can patch 'app.routers.chat.harness_runs_service'
# and 'app.routers.chat.harness_registry'. When harness_enabled is False none of
# the new branches activate (byte-identical OFF mode).
from app.services import harness_runs_service, harness_registry
# Phase 20 / Plan 20-05: post-harness summary + gatekeeper + engine — imported at module
# level so tests can patch 'app.routers.chat.run_gatekeeper',
# 'app.routers.chat.run_harness_engine', and 'app.routers.chat.summarize_harness_run'.
from app.services.gatekeeper import run_gatekeeper
from app.services.harness_engine import run_harness_engine
from app.services.post_harness import summarize_harness_run
# Phase 21 / Plan 21-04 (HIL-04): WorkspaceService imported at module level so
# tests can patch 'app.routers.chat.WorkspaceService' for the HIL resume branch.
from app.services.workspace_service import WorkspaceService
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class EgressBlockedAbort(Exception):
    """Phase 5 D-94: egress filter tripped at a cloud LLM call site.

    Raised inside _run_tool_loop or event_generator when the pre-flight
    egress filter detects a registered real_value substring in the
    serialized messages payload. Caught by event_generator's outer
    handler which emits the redaction_status:blocked event and the
    delta:{done:true} terminator.

    Router-internal exception — not part of any service contract.
    """


def compute_web_search_effective(
    system_enabled: bool,
    user_default: bool,
    message_override: bool | None,
) -> bool:
    """ADR-0008: compute effective web_search toggle for one request.

    L1 (system) AND (L3 message override if provided else L2 user default).
    """
    if not system_enabled:
        return False
    if message_override is not None:
        return bool(message_override)
    return bool(user_default)


# Phase 11 Plan 11-04 (D-P11-08): derive ToolCallRecord.status from outcome.
# Module-level helper so it can be unit-tested without booting the FastAPI app
# (mirrors the `_run_tool_loop_for_test` extraction pattern from Plan 10-05).
def _derive_tool_status(
    tool_name: str,
    tool_output: dict | str | None,
    *,
    exception_caught: bool = False,
) -> str:
    """Derive ToolCallRecord.status from a tool execution outcome.

    Sandbox `execute_code`:
      - 'timeout' if `error_type == 'timeout'`
      - 'error'   if `error_type` is truthy OR `exit_code` is non-None and != 0
      - 'success' otherwise
    Non-sandbox tools:
      - 'error'   if exception caught
      - 'success' otherwise
    """
    if exception_caught:
        return "error"
    if tool_name == "execute_code" and isinstance(tool_output, dict):
        if tool_output.get("error_type") == "timeout":
            return "timeout"
        exit_code = tool_output.get("exit_code")
        if tool_output.get("error_type") or (
            exit_code is not None and exit_code != 0
        ):
            return "error"
        return "success"
    return "success"


# Phase 11 Plan 11-04 (D-P11-03 / D-P11-07 / D-P11-10): expand a persisted
# `messages` row into LLM-format items for history-load reconstruction.
def _expand_history_row(row: dict) -> list[dict]:
    """Expand a `messages` row into one or more LLM-format dicts.

    Modern row (every entry in `tool_calls.calls[]` carries `tool_call_id`):
      emits the OpenAI triplet —
        - {role:"assistant", content:"", tool_calls:[…]}
        - {role:"tool", tool_call_id, content} × N
        - optional {role:"assistant", content} if `row.content` non-empty
    Legacy row (any call missing `tool_call_id`, OR no tool_calls at all):
      emits a single {role, content} item — flat fallback (D-P11-03).

    Every emitted dict carries a 'content' key (empty string is valid)
    so the redaction batch at chat.py ~L485 stays index-aligned (D-P11-10).
    """
    tc = row.get("tool_calls") or {}
    calls = tc.get("calls") or []
    if calls and all(c.get("tool_call_id") for c in calls):
        items: list[dict] = [{
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": c["tool_call_id"],
                    "type": "function",
                    "function": {
                        "name": c["tool"],
                        "arguments": json.dumps(c.get("input") or {}),
                    },
                }
                for c in calls
            ],
        }]
        for c in calls:
            output = c.get("output")
            # Phase 12 / HIST-06 / D-P12-16: when persisted call carries
            # sub_agent_state or code_execution_state, embed them into the
            # OpenAI {role:"tool", content} payload so the LLM's follow-up
            # reasoning has the same context it saw live.
            sub_agent_state = c.get("sub_agent_state")
            code_execution_state = c.get("code_execution_state")
            if sub_agent_state is not None or code_execution_state is not None:
                tool_payload: dict = {}
                if isinstance(output, dict):
                    tool_payload.update(output)
                elif output is not None:
                    tool_payload["output"] = output
                if sub_agent_state is not None:
                    tool_payload["sub_agent_state"] = sub_agent_state
                if code_execution_state is not None:
                    tool_payload["code_execution_state"] = code_execution_state
                content = json.dumps(tool_payload, ensure_ascii=False)
            elif isinstance(output, str):
                # Avoid double-encoding when output was already collapsed to
                # a string by the Plan 11-01 truncation validator.
                content = output
            else:
                content = json.dumps(output, ensure_ascii=False)
            items.append({
                "role": "tool",
                "tool_call_id": c["tool_call_id"],
                "content": content,
            })
        if row.get("content"):
            items.append({"role": "assistant", "content": row["content"]})
        return items
    # Legacy / no-tool-calls path — unchanged shape.
    return [{"role": row.get("role"), "content": row.get("content") or ""}]


def _persist_round_message(
    client,
    *,
    thread_id: str,
    user_id: str,
    parent_message_id: str,
    content: str,
    tool_records: list[ToolCallRecord],
    agent_name: str | None,
    deep_mode: bool = False,
) -> str:
    """Phase 12 / HIST-01 / D-P12-11 / D-P12-12: insert ONE assistant
    messages row for a single agentic round.

    Each round's row carries that round's tool_records only — NOT the
    cumulative array. Returns the new message_id; this becomes the next
    round's parent_message_id, building the natural created_at-ordered
    chain that the frontend reconstructs into an interleaved transcript.

    Empty rounds (no content AND no tool_records AND no agent_name) are
    a no-op — return parent_message_id unchanged.

    Phase 17 / DEEP-04: deep_mode=True is set on assistant rows produced
    by run_deep_mode_loop. Standard callers leave it at the default False
    (DEEP-03 byte-identical invariant — existing rows are unaffected).
    """
    if not content and not tool_records and not agent_name:
        return parent_message_id
    insert_data = {
        "thread_id": thread_id,
        "user_id": user_id,
        "role": "assistant",
        "content": content,
        "parent_message_id": parent_message_id,
        "deep_mode": deep_mode,
    }
    if tool_records or agent_name:
        insert_data["tool_calls"] = ToolCallSummary(
            agent=agent_name,
            calls=tool_records,
        ).model_dump()
    result = client.table("messages").insert(insert_data).execute()
    return result.data[0]["id"]


router = APIRouter(prefix="/chat", tags=["chat"])
openrouter_service = OpenRouterService()
tool_service = ToolService()
settings = get_settings()

# Phase 5 — module-level singletons.
# get_redaction_service is itself an @lru_cache singleton (Phase 1 D-15).
# LLMProviderClient.__init__ does no I/O (lazy AsyncOpenAI clients in
# llm_provider._get_client), so module-level construction is safe.
_llm_provider_client = LLMProviderClient()

SYSTEM_PROMPT = """You are a helpful assistant with access to tools.

When the user asks a question:
1. If it's about the content of their uploaded documents, use the search_documents tool.
2. If it's about document metadata (counts, categories, file sizes, titles), use the query_database tool.
3. If your documents don't have the answer, or the question is about current events or general knowledge, use the web_search tool.
4. For general conversation (greetings, simple questions), respond directly without tools.

Always cite your sources. For document searches, mention the source filename. For web searches, include the source URLs."""


class SendMessageRequest(BaseModel):
    thread_id: str
    message: str
    parent_message_id: str | None = None
    web_search: bool | None = None  # ADR-0008 L3: per-message override
    # Phase 17 / DEEP-01: optional per-message Deep Mode flag.
    # When True, routes to run_deep_mode_loop (MAX_DEEP_ROUNDS=50, extended prompt, todos tools).
    # When False or absent, behavior is byte-identical to v1.2 (DEEP-03 invariant).
    deep_mode: bool = False


@router.post("/stream")
async def stream_chat(
    body: SendMessageRequest,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_client()

    # Validate thread ownership
    thread_result = (
        client.table("threads")
        .select("id")
        .eq("id", body.thread_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    if not thread_result.data:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Phase 19 / D-04: resume-detection branch (gated by SUB_AGENT_ENABLED AND DEEP_MODE_ENABLED).
    # When a thread has a waiting_for_user run, body.message is the user's answer to the
    # pending ask_user question. body.deep_mode is IGNORED for resume (D-04 explicit):
    # the original run already set the mode.
    if settings.sub_agent_enabled and settings.deep_mode_enabled:
        active_run = await agent_runs_service.get_active_run(body.thread_id, user["token"])
        if active_run and active_run["status"] == "waiting_for_user":
            # Transition before re-entering the loop — race-mitigation guard is inside service.
            await agent_runs_service.transition_status(
                run_id=active_run["id"],
                new_status="working",
                token=user["token"],
                user_id=user["id"],
                user_email=user.get("email", ""),
            )
            # Reload history for the resumed loop (same as normal path below)
            flat_rows_resume = (
                client.table("messages")
                .select("role, content, tool_calls")
                .eq("thread_id", body.thread_id)
                .eq("user_id", user["id"])
                .order("created_at")
                .execute()
            ).data or []
            from app.services.system_settings_service import get_system_settings as _gss  # already imported above
            _sys_settings_resume = get_system_settings()
            _llm_model_resume = _sys_settings_resume["llm_model"]
            _user_prefs_resume = (
                client.table("user_preferences")
                .select("web_search_default")
                .eq("user_id", user["id"])
                .maybe_single()
                .execute()
            )
            _up_data = (getattr(_user_prefs_resume, "data", None) or {}) if _user_prefs_resume else {}
            _web_search_resume = compute_web_search_effective(
                system_enabled=bool(_sys_settings_resume.get("web_search_enabled", True)),
                user_default=bool(_up_data.get("web_search_default", False)),
                message_override=body.web_search,
            )
            _history_resume = []
            for _m in flat_rows_resume:
                _history_resume.extend(_expand_history_row(_m))
            _user_msg_resume = client.table("messages").insert({
                "thread_id": body.thread_id,
                "user_id": user["id"],
                "role": "user",
                "content": body.message,
                "parent_message_id": body.parent_message_id,
            }).execute()
            _user_msg_id_resume = _user_msg_resume.data[0]["id"]
            _tool_context_resume = {
                "top_k": settings.rag_top_k,
                "threshold": settings.rag_similarity_threshold,
                "embedding_model": _sys_settings_resume.get("custom_embedding_model") or _sys_settings_resume["embedding_model"],
                "llm_model": _llm_model_resume,
                "thread_id": body.thread_id,
            }
            return StreamingResponse(
                run_deep_mode_loop(
                    messages=_history_resume,
                    user_message=body.message,
                    user_id=user["id"],
                    user_email=user.get("email", ""),
                    token=user["token"],
                    tool_context=_tool_context_resume,
                    thread_id=body.thread_id,
                    user_msg_id=_user_msg_id_resume,
                    client=client,
                    sys_settings=_sys_settings_resume,
                    web_search_effective=_web_search_resume,
                    resume_run_id=active_run["id"],
                    resume_tool_result=body.message,
                    resume_round_index=active_run["last_round_index"] + 1,
                ),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    # Phase 21 / D-01, D-02: HIL resume detection.
    # When a harness is paused on an llm_human_input phase, treat the next user
    # message as the HIL answer: write to phase.workspace_output, advance phase
    # via resume_from_pause (NOT advance_phase — its guard rejects paused rows),
    # then resume run_harness_engine from current_phase + 1.
    # MUST run BEFORE the 409 block so paused falls through to resume rather
    # than triggering a stale 409.
    if settings.harness_enabled:
        paused_run = await harness_runs_service.get_active_run(
            thread_id=body.thread_id, token=user["token"]
        )
        if paused_run is not None and paused_run.get("status") == "paused":
            harness_type = paused_run["harness_type"]
            current_phase_idx = paused_run["current_phase"]
            try:
                h = harness_registry.get_harness(harness_type)
            except Exception as exc:
                logger.warning(
                    "HIL resume: harness lookup failed type=%s: %s", harness_type, exc
                )
                h = None
            if h is not None and 0 <= current_phase_idx < len(h.phases):
                current_phase = h.phases[current_phase_idx]

                # 1. Write user's answer to current phase's workspace_output.
                ws = WorkspaceService(token=user["token"])
                try:
                    await ws.write_text_file(
                        body.thread_id,
                        current_phase.workspace_output,
                        body.message,
                        source="harness",
                    )
                except Exception as exc:
                    logger.warning(
                        "HIL resume: workspace write failed phase=%s: %s",
                        current_phase.name, exc,
                    )

                # 2. Persist user's message with harness_mode tag (mirrors
                #    post_harness convention so history reconstruction shows
                #    the Q→A exchange).
                authed_client = get_supabase_authed_client(user["token"])
                try:
                    authed_client.table("messages").insert({
                        "thread_id": body.thread_id,
                        "user_id": user["id"],
                        "role": "user",
                        "content": body.message,
                        "harness_mode": harness_type,
                        "parent_message_id": getattr(body, "parent_message_id", None),
                    }).execute()
                except Exception as exc:
                    logger.warning("HIL resume: messages insert failed: %s", exc)

                # 3. Advance harness phase via resume_from_pause (BLOCKER-2 fix —
                #    advance_phase's transactional guard rejects paused rows).
                try:
                    updated_row = await harness_runs_service.resume_from_pause(
                        run_id=paused_run["id"],
                        new_phase_index=current_phase_idx + 1,
                        phase_results_patch={
                            str(current_phase_idx): {
                                "phase_name": current_phase.name,
                                "output": {"answer": body.message[:500]},
                            }
                        },
                        user_id=user["id"],
                        user_email=user.get("email", ""),
                        token=user["token"],
                    )
                except Exception as exc:
                    logger.error(
                        "HIL resume: resume_from_pause failed run=%s: %s",
                        paused_run["id"], exc,
                    )
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": "hil_resume_advance_failed",
                            "detail": str(exc)[:300],
                        },
                    )

                # 3b. Stale-state guard — None means the row was no longer paused
                #     (cancelled/completed/failed in a parallel request).
                if updated_row is None:
                    logger.warning(
                        "HIL resume: resume_from_pause returned None run=%s — "
                        "row no longer paused",
                        paused_run["id"],
                    )
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": "hil_resume_state_invalid",
                            "detail": "harness run is no longer paused (cancelled or terminal)",
                        },
                    )

                # 4. Resume the engine from the next phase via the new
                #    _resume_harness_engine_sse wrapper. The wrapper internally
                #    reuses _get_or_build_conversation_registry (chat.py:1695) —
                #    B4 invariant: never mint a fresh registry on resume.
                cancellation_event = asyncio.Event()
                _hil_sys_settings = get_system_settings()
                return StreamingResponse(
                    _resume_harness_engine_sse(
                        harness=h,
                        harness_run_id=paused_run["id"],
                        thread_id=body.thread_id,
                        user_id=user["id"],
                        user_email=user.get("email", ""),
                        token=user["token"],
                        sys_settings=_hil_sys_settings,
                        start_phase_index=current_phase_idx + 1,
                        cancellation_event=cancellation_event,
                    ),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

    # Phase 20 / D-02: reject new chat messages while a harness is active.
    # Per HARN-01 partial unique index, at most one active harness_run exists per thread.
    # When user sends a new message during harness execution, return structured 409 JSON;
    # frontend surfaces a banner per UI-SPEC reject-while-active toast.
    # Phase 21 / D-01: condition narrowed to ("pending", "running") — paused rows
    # are handled by the HIL resume branch above.
    if settings.harness_enabled:
        active_harness = await harness_runs_service.get_active_run(
            thread_id=body.thread_id, token=user["token"]
        )
        if active_harness is not None and active_harness.get("status") in ("pending", "running"):
            phase_idx = active_harness.get("current_phase", 0)
            phase_name = "—"
            try:
                h = harness_registry.get_harness(active_harness["harness_type"])
                if h and phase_idx < len(h.phases):
                    phase_name = h.phases[phase_idx].name
            except Exception:
                phase_name = "—"
            return JSONResponse(
                status_code=409,
                content={
                    "error": "harness_in_progress",
                    "harness_type": active_harness["harness_type"],
                    "current_phase": phase_idx,
                    "phase_name": phase_name,
                    "phase_count": len(h.phases) if h else 0,
                },
            )

    # Phase 20 / D-05 (GATE-01, GATE-05): gatekeeper-eligibility branch.
    # Run gatekeeper ONLY when:
    #   (a) HARNESS_ENABLED is True
    #   (b) HarnessRegistry has at least one registered harness
    #   (c) get_latest_for_thread returns None (no active OR terminal run for this thread)
    #   (d) The single registered harness has prerequisites.requires_upload=True
    #       (GATE-05: harnesses without prerequisites skip gatekeeper entirely).
    # For v1.3, registry holds at most one user-facing harness at a time (D-06); pick the first.
    if settings.harness_enabled:
        latest = await harness_runs_service.get_latest_for_thread(
            thread_id=body.thread_id, token=user["token"]
        )
        if latest is None:
            _harnesses = harness_registry.list_harnesses()
            if _harnesses:
                # D-06: pick first registered (single-harness invariant for v1.3)
                _target_harness = _harnesses[0]
                # GATE-05: skip gatekeeper if harness has no prerequisites requiring upload
                if _target_harness.prerequisites.requires_upload:
                    # sys_settings not yet loaded at this point — load now for registry helper
                    _sys_settings_gk = get_system_settings()
                    return StreamingResponse(
                        _gatekeeper_stream_wrapper(
                            harness=_target_harness,
                            thread_id=body.thread_id,
                            user_id=user["id"],
                            user_email=user.get("email", ""),
                            user_message=body.message,
                            token=user["token"],
                            sys_settings=_sys_settings_gk,
                        ),
                        media_type="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                    )

    # Load chat history — branch-aware when parent_message_id is provided.
    # Phase 11 Plan 11-04 (MEM-01..03): both SELECT calls widened to include
    # `tool_calls` JSONB so `_expand_history_row` can reconstruct the OpenAI
    # tool-call triplet for rows whose calls carry `tool_call_id`. Legacy
    # rows fall back to flat {role, content} per D-P11-03.
    if body.parent_message_id:
        # Branch mode: walk ancestor chain from the specified parent
        all_messages = (
            client.table("messages")
            .select("id, role, content, parent_message_id, tool_calls")
            .eq("thread_id", body.thread_id)
            .eq("user_id", user["id"])
            .execute()
        ).data or []
        msg_map = {m["id"]: m for m in all_messages}
        chain = []
        visited: set[str] = set()
        current_id = body.parent_message_id
        while current_id and current_id in msg_map and current_id not in visited:
            visited.add(current_id)
            chain.append(msg_map[current_id])
            current_id = msg_map[current_id].get("parent_message_id")
        chain.reverse()
        history = []
        for m in chain:
            history.extend(_expand_history_row(m))
    else:
        # Flat mode: all messages in order (existing behavior)
        flat_rows = (
            client.table("messages")
            .select("role, content, tool_calls")
            .eq("thread_id", body.thread_id)
            .eq("user_id", user["id"])
            .order("created_at")
            .execute()
        ).data or []
        history = []
        for m in flat_rows:
            history.extend(_expand_history_row(m))

    # Load system-level model config
    sys_settings = get_system_settings()
    llm_model = sys_settings["llm_model"]

    # ADR-0008: compute effective web_search toggle for this request.
    # L1 (system) AND (L3 message override if provided else L2 user default).
    user_prefs_resp = (
        client.table("user_preferences")
        .select("web_search_default")
        .eq("user_id", user["id"])
        .maybe_single()
        .execute()
    )
    user_prefs = (
        getattr(user_prefs_resp, "data", None) or {}
    ) if user_prefs_resp is not None else {}
    web_search_effective = compute_web_search_effective(
        system_enabled=bool(sys_settings.get("web_search_enabled", True)),
        user_default=bool(user_prefs.get("web_search_default", False)),
        message_override=body.web_search,
    )

    # Persist user message before streaming (with parent link for branching)
    user_msg_result = client.table("messages").insert({
        "thread_id": body.thread_id,
        "user_id": user["id"],
        "role": "user",
        "content": body.message,
        "parent_message_id": body.parent_message_id,
    }).execute()
    user_msg_id = user_msg_result.data[0]["id"]

    # Tool execution context (passed to search_documents tool, used by execute_code tool for thread routing)
    tool_context = {
        "top_k": settings.rag_top_k,
        "threshold": settings.rag_similarity_threshold,
        "embedding_model": sys_settings.get("custom_embedding_model") or sys_settings["embedding_model"],
        "llm_model": llm_model,
        "thread_id": body.thread_id,   # Phase 10 D-P10-04: needed by execute_code handler for session routing
    }

    async def _dispatch_tool(
        name: str,
        arguments: dict,
        user_id: str,
        context: dict | None = None,
        *,
        registry=None,
        token: str | None = None,
        stream_callback=None,
        workspace_callback=None,
    ):
        """Phase 13 D-P13-05 Option A: registry-first dispatch.

        When tool_registry_enabled and the tool is in the registry, delegate
        to its executor (so tool_search and future skill/MCP executors drive
        dispatch). Otherwise fall through to legacy tool_service.execute_tool
        (preserves byte-identical TOOL-05 behavior on flag-off).

        Note: the registry's native executors themselves delegate back to
        ToolService.execute_tool, so this layer only changes behavior for
        tool_search (and future deferred/skill/MCP tools).
        """
        if settings.tool_registry_enabled:
            from app.services import tool_registry  # lazy
            if name in tool_registry._REGISTRY:
                tool_def = tool_registry._REGISTRY[name]
                return await tool_def.executor(
                    arguments,
                    user_id,
                    context,
                    registry=registry,
                    token=token,
                    stream_callback=stream_callback,
                    workspace_callback=workspace_callback,
                )
        return await tool_service.execute_tool(
            name, arguments, user_id, context,
            registry=registry, token=token, stream_callback=stream_callback,
            workspace_callback=workspace_callback,
        )

    async def _run_tool_loop(
        messages, tools, max_iterations, user_id, tool_context,
        *, registry=None, redaction_service=None, redaction_on=False,
        available_tool_names=None,
        token: str | None = None,   # Phase 8 D-P8-XX: enables RLS-scoped DB access for skill tools
    ):
        """Shared tool-calling loop used by both agent and non-agent paths.

        Phase 5 (D-89/D-91/D-94 site #1) — when ``redaction_on`` is True:
          - Pre-flight egress filter wraps the per-iteration
            ``complete_with_tools`` call (defense-in-depth against an
            upstream NER miss). On trip: B4-compliant log + raise
            ``EgressBlockedAbort`` (caught by event_generator's outer handler).
          - ``deanonymize_tool_args`` runs BEFORE ``execute_tool``;
            ``anonymize_tool_output`` runs AFTER.
          - ``execute_tool`` is called with ``registry=registry`` for D-86 symmetry.
          - tool_start / tool_result emits are SKELETON form
            (``{type, tool}`` with NO input/output) per D-89.

        When OFF: behavior is byte-identical to the Phase 0 baseline.

        Phase 12 (HIST-01 / CTX-01 / D-P12-11/12) — yields one
        ``("round", {"content", "tool_records", "usage"})`` event per LLM
        iteration that produced tool_calls. The outer caller persists
        each round and chains parent_message_id forward, and accumulates
        usage across rounds for the terminal SSE event.
        """
        tool_records = []
        for _iteration in range(max_iterations):
            if not tools:
                break

            # Phase 5 D-94 site #1: pre-flight egress filter on the
            # per-iteration tool-calling LLM. Trips raise EgressBlockedAbort
            # which propagates to event_generator's outer handler.
            if redaction_on and registry is not None:
                payload = json.dumps(messages, ensure_ascii=False)
                egress_result = egress_filter(payload, registry, None)
                if egress_result.tripped:
                    logger.warning(
                        "egress_blocked event=egress_blocked feature=tool_loop "
                        "match_count=%d",
                        egress_result.match_count,
                    )
                    raise EgressBlockedAbort("tool_loop egress blocked")

            result = await openrouter_service.complete_with_tools(
                messages, tools, model=llm_model
            )

            # Phase 12 / CTX-01 / CTX-06: surface usage from every round even
            # when this iteration produced no tool_calls (terminal text round).
            # The outer event_generator accumulates this for the SSE usage event.
            if not result["tool_calls"]:
                yield "round_usage", {"usage": result.get("usage")}
                break

            # Phase 12 / HIST-01 / D-P12-12: track which tool_records were
            # added in THIS iteration so the per-round messages row carries
            # only this round's calls (not the cumulative array).
            iteration_start_idx = len(tool_records)

            for tc in result["tool_calls"]:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    func_args = {}

                # Phase 5 D-89: skeleton emit when redaction is ON
                # ({type, tool} ONLY — NO 'input'); full payload when OFF.
                if redaction_on:
                    yield "tool_start", {
                        "type": "tool_start", "tool": func_name,
                    }
                else:
                    yield "tool_start", {
                        "type": "tool_start", "tool": func_name, "input": func_args,
                    }

                # Phase 10 D-P10-05/06: queue adapter for execute_code streaming.
                # Planner alert #1 resolution: _run_tool_loop is itself an async
                # generator, so the callback CANNOT yield directly. Instead, the
                # callback enqueues; we drain the queue between tool_start and
                # tool_result while awaiting the execute_tool task.
                sandbox_event_queue: asyncio.Queue | None = None
                sandbox_callback = None
                workspace_event_callback = None
                if func_name == "execute_code":
                    # Phase 14 / BRIDGE-06 (D-P14-07): emit code_mode_start once per stream
                    if _bridge_active and not _bridge_event_sent:
                        _bridge_event_sent = True
                        _bridge_tools: list[str] = []
                        try:
                            from app.services import tool_registry as _tr
                            _bridge_tools = [n for n in _tr._REGISTRY if n != "tool_search"]
                        except Exception:
                            pass
                        yield f"data: {json.dumps({'type': 'code_mode_start', 'tools': _bridge_tools})}\n\n"
                    sandbox_event_queue = asyncio.Queue()

                    async def sandbox_stream_callback(event_type: str, line: str):
                        """D-P10-05/06: enqueue code_stdout/code_stderr lines.

                        Planner alert #2 resolution: when redaction_on=True, anonymize
                        the line before enqueue so SSE never emits real PII (D-89
                        invariant). Per-line anonymization (option b from alert #2) —
                        different from tool_start/tool_result skeleton-emit because
                        SANDBOX-03 requires meaningful streaming output.
                        Skeleton-only would defeat the streaming UX.
                        """
                        emit_line = line
                        if redaction_on and registry is not None:
                            try:
                                anon = await anonymize_tool_output(
                                    {"line": line}, registry, redaction_service,
                                )
                                # anonymize_tool_output returns same shape; extract line
                                if isinstance(anon, dict):
                                    emit_line = anon.get("line", line)
                            except Exception as _exc:
                                logger.warning(
                                    "sandbox stream anon failed err=%s — emitting skeleton",
                                    _exc,
                                )
                                emit_line = ""  # skeleton fallback (D-89 safer default)
                        await sandbox_event_queue.put({
                            "type": event_type,
                            "line": emit_line,
                            "tool_call_id": tc["id"],
                        })

                    sandbox_callback = sandbox_stream_callback

                    # Phase 18 / WS-10: workspace_callback enqueues workspace_updated
                    # events into the same queue. Synchronous put_nowait — safe because
                    # _collect_and_upload_files runs in async context.
                    def _workspace_event_callback(event: dict) -> None:
                        sandbox_event_queue.put_nowait(event)

                    workspace_event_callback = _workspace_event_callback

                try:
                    # ADR-0008 defense-in-depth: agent attempted a tool not in
                    # the effective catalog. Skip dispatch and synthesize a
                    # polite refusal as tool output.
                    if (
                        available_tool_names is not None
                        and func_name not in available_tool_names
                    ):
                        tool_output = {
                            "blocked": True,
                            "reason": f"Tool '{func_name}' is not available for this request.",
                        }
                    # Phase 5 D-91: walker wrap when redaction is ON.
                    elif redaction_on and registry is not None:
                        if func_name == "web_search":
                            # ADR-0008 + ADR-0004: keep surrogate form for
                            # external API. Tavily must NEVER receive
                            # registry-known real PII. Search quality may
                            # degrade for PII-laden queries; users disable PII
                            # redaction explicitly if they need exact-name web
                            # search.
                            real_args = func_args  # surrogates flow to Tavily
                        else:
                            real_args = await deanonymize_tool_args(
                                func_args, registry, redaction_service,
                            )
                        # Phase 10 D-P10-05: use Task + queue drain for execute_code;
                        # direct await for all other tools (sandbox_callback is None).
                        # Phase 13 D-P13-05: dispatch through registry-first wrapper.
                        if sandbox_event_queue is not None:
                            tool_output_task = asyncio.create_task(
                                _dispatch_tool(
                                    func_name, real_args, user_id, tool_context,
                                    registry=registry,
                                    token=token,
                                    stream_callback=sandbox_callback,
                                    workspace_callback=workspace_event_callback,
                                )
                            )
                            # Drain sandbox events while execute_tool runs.
                            while not tool_output_task.done():
                                try:
                                    evt = await asyncio.wait_for(
                                        sandbox_event_queue.get(), timeout=0.1,
                                    )
                                    yield evt["type"], evt
                                except asyncio.TimeoutError:
                                    continue
                            # Drain any remaining queued events after task completes
                            while not sandbox_event_queue.empty():
                                evt = sandbox_event_queue.get_nowait()
                                yield evt["type"], evt
                            tool_output = await tool_output_task
                        else:
                            tool_output = await _dispatch_tool(
                                func_name, real_args, user_id, tool_context,
                                registry=registry,
                                token=token,
                                stream_callback=None,
                            )
                        # tool_records keep the surrogate-form func_args
                        # (LLM-emitted) so persistence and downstream
                        # consumers see the LLM's actual emission.
                        if func_name == "web_search":
                            # Fix D: replace registry-known real values with
                            # surrogates WITHOUT registering new Tavily entities.
                            # Prevents user PII appearing incidentally in Tavily
                            # results from reaching the LLM unmasked.
                            #
                            # Residual (Codex [P2]): if a Faker surrogate
                            # coincidentally matches a real public figure name
                            # in Tavily results, de_anonymize_text will still
                            # map it back to the user's real value in synthesis.
                            # Full fix requires collision detection at surrogate
                            # generation time — deferred.
                            tool_output = filter_tool_output_by_registry(
                                tool_output, registry,
                            )
                        else:
                            tool_output = await anonymize_tool_output(
                                tool_output, registry, redaction_service,
                            )
                    else:
                        # Phase 10 D-P10-05: use Task + queue drain for execute_code;
                        # direct await for all other tools (sandbox_callback is None).
                        # Phase 13 D-P13-05: dispatch through registry-first wrapper.
                        if sandbox_event_queue is not None:
                            tool_output_task = asyncio.create_task(
                                _dispatch_tool(
                                    func_name, func_args, user_id, tool_context,
                                    token=token,
                                    stream_callback=sandbox_callback,
                                    workspace_callback=workspace_event_callback,
                                )
                            )
                            # Drain sandbox events while execute_tool runs.
                            while not tool_output_task.done():
                                try:
                                    evt = await asyncio.wait_for(
                                        sandbox_event_queue.get(), timeout=0.1,
                                    )
                                    yield evt["type"], evt
                                except asyncio.TimeoutError:
                                    continue
                            # Drain any remaining queued events after task completes
                            while not sandbox_event_queue.empty():
                                evt = sandbox_event_queue.get_nowait()
                                yield evt["type"], evt
                            tool_output = await tool_output_task
                        else:
                            tool_output = await _dispatch_tool(
                                func_name, func_args, user_id, tool_context,
                                token=token,
                                stream_callback=None,
                            )
                    # ADR-0008 audit: record toggle state for every web_search
                    # dispatch (only when actually dispatched, not blocked).
                    if (
                        func_name == "web_search"
                        and not (
                            isinstance(tool_output, dict)
                            and tool_output.get("blocked")
                        )
                    ):
                        try:
                            log_action(
                                user_id=user_id,
                                user_email=user.get("email") if isinstance(user, dict) else None,
                                action="web_search_dispatch",
                                resource_type="chat_message",
                                resource_id=body.thread_id,
                                details={
                                    "system_enabled": bool(sys_settings.get("web_search_enabled", True)),
                                    "user_default": bool(user_prefs.get("web_search_default", False)),
                                    "message_override": body.web_search,
                                    "effective": web_search_effective,
                                    "redaction_on": redaction_on,
                                },
                            )
                        except Exception:
                            pass  # audit is fire-and-forget per existing pattern
                    # Phase 11 Plan 11-04 (D-P11-08): persist tool_call_id +
                    # derived status so the next turn's history-load can
                    # reconstruct the OpenAI tool-call triplet (MEM-01..03).
                    tool_records.append(ToolCallRecord(
                        tool=func_name,
                        input=func_args,
                        output=tool_output,
                        tool_call_id=tc["id"],
                        status=_derive_tool_status(func_name, tool_output),
                    ))
                except EgressBlockedAbort:
                    # Bubble up to event_generator's outer handler — DO NOT
                    # swallow here (D-94: trip aborts the entire turn).
                    raise
                except Exception as e:
                    tool_output = {"error": str(e)}
                    tool_records.append(ToolCallRecord(
                        tool=func_name,
                        input=func_args,
                        output={},
                        error=str(e),
                        tool_call_id=tc["id"],
                        status=_derive_tool_status(
                            func_name, None, exception_caught=True,
                        ),
                    ))

                # Phase 5 D-89: skeleton emit when redaction is ON
                # ({type, tool} ONLY — NO 'output'); full payload when OFF.
                if redaction_on:
                    yield "tool_result", {
                        "type": "tool_result", "tool": func_name,
                    }
                else:
                    yield "tool_result", {
                        "type": "tool_result", "tool": func_name, "output": tool_output,
                    }

                # Phase 18 / WS-10: emit workspace_updated for successful workspace mutations.
                # Payload contains only metadata (path, size, source) — no file content.
                # Flows through the same SSE translation layer as tool_start/tool_result.
                if (
                    func_name in ("write_file", "edit_file")
                    and isinstance(tool_output, dict)
                    and tool_output.get("ok")
                    and settings.workspace_enabled
                ):
                    yield "workspace_updated", {
                        "type": "workspace_updated",
                        "file_path": tool_output.get("file_path"),
                        "operation": tool_output.get("operation"),
                        "size_bytes": tool_output.get("size_bytes"),
                        "source": "agent",
                    }

                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tc],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_output),
                })

            # Phase 12 / HIST-01 / D-P12-11/D-P12-12: yield this round's
            # records + content + usage so the outer caller can persist
            # ONE messages row per agentic round (not the cumulative array).
            iteration_tool_records = tool_records[iteration_start_idx:]
            yield "round", {
                "content": result.get("content") or "",
                "tool_records": iteration_tool_records,
                "usage": result.get("usage"),
            }

        # Expose collected records for persistence (legacy — retained for
        # any consumer; outer event_generator now drives persistence via
        # the per-round "round" events).
        yield "records", tool_records

    async def event_generator():
        tool_records = []
        full_response = ""
        agent_name = None

        # Phase 13 D-P13-05: per-request active set for tool_search dynamic activation.
        # Owner of lifetime = this event_generator scope. Closes when SSE stream ends.
        # Flag-off path leaves _registry_active_set = None and never imports tool_registry
        # (TOOL-05 byte-identical fallback).
        _registry_active_set: set[str] | None = None
        if settings.tool_registry_enabled:
            from app.services import tool_registry  # lazy — flag-off never imports
            _registry_active_set = tool_registry.make_active_set()

        # Phase 14 / BRIDGE-06 (D-P14-07): track whether code_mode_start has been emitted.
        # Emitted at most once per SSE stream — before the FIRST execute_code call when bridge active.
        _bridge_event_sent = False
        _bridge_active = settings.sandbox_enabled and settings.tool_registry_enabled

        # Phase 12 / HIST-01 / D-P12-12: per-round persistence chains via
        # parent_message_id; each round produces its own messages row.
        current_parent_id = user_msg_id
        # Phase 12 / CTX-01 / D-P12-01: usage tracking across all LLM rounds.
        # last_prompt_tokens uses the LAST round's snapshot (most accurate);
        # cumulative_completion_tokens sums every round's completion.
        last_prompt_tokens: int | None = None
        cumulative_completion_tokens = 0
        any_usage_seen = False

        def _accumulate_usage(usage: dict | None) -> None:
            """CTX-01: accumulate usage from one round (helper to keep both
            tool-loop and stream_response sites symmetric)."""
            nonlocal last_prompt_tokens, cumulative_completion_tokens, any_usage_seen
            if usage is None:
                return
            any_usage_seen = True
            prompt = usage.get("prompt_tokens")
            completion = usage.get("completion_tokens")
            if prompt is not None:
                last_prompt_tokens = prompt
            if completion is not None:
                cumulative_completion_tokens += completion

        # Phase 5 D-83/D-84/D-86/D-93: per-turn redaction setup chokepoint.
        # When OFF: identity passthrough — anonymized_history is the loaded
        # `history`, anonymized_message is body.message. No registry load,
        # no SSE redaction events, no buffering. SC#5 byte-identical baseline.
        # Plan 05-08: redaction toggle migrated from config.py env var to
        # system_settings DB column (admin-toggleable, 60s cached). sys_settings
        # is loaded above at line ~121 — single read per turn; no extra DB hit.
        redaction_on = bool(sys_settings.get("pii_redaction_enabled", True))
        redaction_service = get_redaction_service()
        if redaction_on:
            # D-86: ConversationRegistry.load called ONCE per turn (chokepoint).
            registry = await ConversationRegistry.load(body.thread_id)
            # D-93: single batched history anon under one asyncio.Lock.
            # Order is preserved by redact_text_batch (T-05-01-2 mitigation),
            # so we rebuild history items by index.
            raw_strings = [m["content"] for m in history] + [body.message]
            anonymized_strings = await redaction_service.redact_text_batch(
                raw_strings, registry
            )
            anonymized_history = [
                {**h, "content": a}
                for h, a in zip(history, anonymized_strings[:-1])
            ]
            anonymized_message = anonymized_strings[-1]
        else:
            registry = None
            anonymized_history = history
            anonymized_message = body.message

        try:
            # Phase 5 D-88: redaction_status:anonymizing — exactly ONE event per turn,
            # emitted after agent_start in branch A (comes after the agent_start yield
            # inside the if-block) or before messages in branch B. Placed here so
            # grep returns exactly 1 source occurrence (both branches share this guard).
            if redaction_on:
                yield f"data: {json.dumps({'type': 'redaction_status', 'stage': 'anonymizing'})}\n\n"

            # ADR-0008: compute available tool catalog up front so it can be
            # fed to the orchestrator classifier and the tool loop.
            # Phase 13 (TOOL-04): when tool_registry_enabled, build the tools
            # array from the unified registry (natives + skills + tool_search).
            # Flag-off preserves the legacy tool_service.get_available_tools path
            # byte-identically (TOOL-05).
            if settings.tools_enabled and settings.tool_registry_enabled:
                from app.services import tool_registry  # lazy
                from app.services.skill_catalog_service import register_user_skills
                # Per-request skill registration (D-P13-02): RLS-scoped fresh query.
                await register_user_skills(user["id"], user["token"])
                assert _registry_active_set is not None  # initialized above with same flag
                all_tools = tool_registry.build_llm_tools(
                    active_set=_registry_active_set,
                    web_search_enabled=web_search_effective,
                    sandbox_enabled=settings.sandbox_enabled,
                    agent_allowed_tools=None,  # multi-agent path narrows below
                )
            elif settings.tools_enabled:
                all_tools = tool_service.get_available_tools(
                    web_search_enabled=web_search_effective
                )
            else:
                all_tools = []
            available_tool_names = [t["function"]["name"] for t in all_tools]

            if settings.agents_enabled:
                # --- Multi-agent path ---
                # 1. Orchestrator classification
                try:
                    orch_model = settings.agents_orchestrator_model or llm_model
                    classification = await agent_service.classify_intent(
                        anonymized_message,
                        anonymized_history,
                        openrouter_service,
                        orch_model,
                        registry=registry,
                        available_tool_names=available_tool_names,
                    )
                    agent_name = classification.agent
                except Exception:
                    agent_name = "general"

                agent_def = agent_service.get_agent(agent_name)

                # 2. SSE: agent_start
                yield f"data: {json.dumps({'type': 'agent_start', 'agent': agent_name, 'display_name': agent_def.display_name})}\n\n"

                # 3. Build messages with agent's system prompt.
                # Phase 8 D-P8-03: append the enabled-skills catalog. Returns "" when
                # the user has 0 enabled skills (D-P8-02), so this is byte-identical
                # to pre-Phase-8 behavior in that case.
                # Phase 13 (TOOL-01, TOOL-04, D-P13-06): when flag is on, use the
                # unified registry catalog filtered by agent.tool_names.
                if settings.tool_registry_enabled:
                    from app.services import tool_registry  # lazy
                    catalog_block = await tool_registry.build_catalog_block(
                        agent_allowed_tools=agent_def.tool_names,
                    )
                    # Narrow the LLM tools array to this agent's filter (D-P13-06).
                    assert _registry_active_set is not None
                    all_tools = tool_registry.build_llm_tools(
                        active_set=_registry_active_set,
                        web_search_enabled=web_search_effective,
                        sandbox_enabled=settings.sandbox_enabled,
                        agent_allowed_tools=agent_def.tool_names,
                    )
                    available_tool_names = [t["function"]["name"] for t in all_tools]
                else:
                    catalog_block = await build_skill_catalog_block(user["id"], user["token"])
                messages = (
                    [{"role": "system", "content": agent_def.system_prompt + catalog_block}]
                    + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
                    + [{"role": "user", "content": anonymized_message}]
                )

                # 4. Get agent's tool subset (filtered from the effective catalog).
                # Phase 13: when flag is on, all_tools was already filtered by
                # agent.tool_names in build_llm_tools; agent_service.get_agent_tools
                # is a pass-through here. Flag-off path preserves legacy behavior.
                if settings.tool_registry_enabled:
                    agent_tools = all_tools
                else:
                    agent_tools = agent_service.get_agent_tools(agent_def, all_tools)

                # 5. Sub-agent tool loop
                # When redaction is ON: buffer tool_start/tool_result events and
                # only flush after the loop completes without an EgressBlockedAbort.
                # Prevents corrupt partial-turn UI state when a later iteration's
                # egress filter trips after earlier tool events were already emitted.
                # Phase 13 D-P13-05: thread per-request active_set + agent filter
                # to executors via tool_context. Flag-off path skips these keys
                # (preserves byte-identical context dict shape for TOOL-05).
                if settings.tool_registry_enabled:
                    tool_context["active_set"] = _registry_active_set
                    tool_context["agent_allowed_tools"] = agent_def.tool_names
                tool_loop_buffer = []
                async for event_type, data in _run_tool_loop(
                    messages, agent_tools, agent_def.max_iterations,
                    user["id"], tool_context,
                    registry=registry,
                    redaction_service=redaction_service,
                    redaction_on=redaction_on,
                    available_tool_names=available_tool_names,
                    token=user["token"],
                ):
                    if event_type == "records":
                        tool_records = data
                    elif event_type == "round":
                        # Phase 12 / HIST-01 / D-P12-12: persist this round
                        # immediately; chain parent_message_id forward.
                        new_parent = _persist_round_message(
                            client,
                            thread_id=body.thread_id,
                            user_id=user["id"],
                            parent_message_id=current_parent_id,
                            content=data["content"],
                            tool_records=data["tool_records"],
                            agent_name=agent_name,
                        )
                        current_parent_id = new_parent
                        _accumulate_usage(data.get("usage"))
                    elif event_type == "round_usage":
                        # Phase 12 / CTX-01: terminal-text-only round produced
                        # no tool_calls but may carry usage data.
                        _accumulate_usage(data.get("usage"))
                    elif event_type in ("code_stdout", "code_stderr"):
                        # Phase 10 SANDBOX-03: stream sandbox lines live regardless of redaction_on.
                        # Lines are already anonymized inside sandbox_stream_callback (alert #2).
                        # Bypassing buffer here ensures real-time streaming UX for execute_code.
                        yield f"data: {json.dumps(data)}\n\n"
                    elif redaction_on:
                        tool_loop_buffer.append(data)
                    else:
                        yield f"data: {json.dumps(data)}\n\n"
                for buffered in tool_loop_buffer:
                    yield f"data: {json.dumps(buffered)}\n\n"

                # 6. Stream final text response
                # Phase 5 D-94 site #2: pre-flight egress filter on branch A stream_response.
                if redaction_on:
                    payload = json.dumps(messages, ensure_ascii=False)
                    egress_result = egress_filter(payload, registry, None)
                    if egress_result.tripped:
                        logger.warning(
                            "egress_blocked event=egress_blocked feature=stream_response_branch_a "
                            "match_count=%d",
                            egress_result.match_count,
                        )
                        raise EgressBlockedAbort("branch A stream_response egress blocked")

                # Phase 5 D-87: buffer all chunks when redaction is ON;
                # emit progressive deltas only when OFF (SC#5 byte-identical baseline).
                async for chunk in openrouter_service.stream_response(messages, model=llm_model):
                    if not chunk["done"]:
                        full_response += chunk["delta"]
                        if not redaction_on:
                            yield f"data: {json.dumps({'type': 'delta', 'delta': chunk['delta'], 'done': False})}\n\n"
                    else:
                        # Phase 12 / CTX-01: capture usage from terminal chunk if present.
                        _accumulate_usage(chunk.get("usage"))

            else:
                # --- Single-agent path (Module 7 behavior) ---
                # Phase 4 D-79/D-80: append PII guidance to SYSTEM_PROMPT when
                # redaction is enabled. Plan 05-08: use the local redaction_on
                # variable (sourced from sys_settings DB column, not config.py).
                pii_guidance = get_pii_guidance_block(
                    redaction_enabled=redaction_on,
                )
                # Phase 8 D-P8-01: append enabled-skills catalog. Returns "" when
                # the user has 0 enabled skills (D-P8-02 SC#5-style invariant —
                # behavior identical to pre-Phase-8 when feature unused).
                # Phase 13 (TOOL-01): when flag is on, use the unified registry
                # catalog (no agent filter — single-agent path sees everything).
                if settings.tool_registry_enabled:
                    from app.services import tool_registry  # lazy
                    catalog_block = await tool_registry.build_catalog_block(
                        agent_allowed_tools=None,
                    )
                else:
                    catalog_block = await build_skill_catalog_block(user["id"], user["token"])
                messages = (
                    [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance + catalog_block}]
                    + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
                    + [{"role": "user", "content": anonymized_message}]
                )

                # ADR-0008: reuse the effective catalog computed above.
                tools = all_tools

                # Agentic tool-calling loop
                # When redaction is ON: buffer tool_start/tool_result events and
                # only flush after the loop completes without an EgressBlockedAbort
                # (defense-in-depth against PII leak via tool events emitted before
                # a later iteration trips the egress filter).
                # Phase 13 D-P13-05: thread per-request active_set into tool_context
                # so the tool_search executor can mutate it. Single-agent path:
                # agent_allowed_tools=None (no filter).
                if settings.tool_registry_enabled:
                    tool_context["active_set"] = _registry_active_set
                    tool_context["agent_allowed_tools"] = None
                tool_loop_buffer = []
                async for event_type, data in _run_tool_loop(
                    # D-15: use max_tool_rounds (default 25) — migrated from
                    # tools_max_iterations (legacy default 5). Deprecated alias
                    # in config.py back-fills max_tool_rounds for one milestone.
                    messages, tools, settings.max_tool_rounds,
                    user["id"], tool_context,
                    registry=registry,
                    redaction_service=redaction_service,
                    redaction_on=redaction_on,
                    available_tool_names=available_tool_names,
                    token=user["token"],
                ):
                    if event_type == "records":
                        tool_records = data
                    elif event_type == "round":
                        # Phase 12 / HIST-01 / D-P12-12: persist this round
                        # immediately; chain parent_message_id forward.
                        new_parent = _persist_round_message(
                            client,
                            thread_id=body.thread_id,
                            user_id=user["id"],
                            parent_message_id=current_parent_id,
                            content=data["content"],
                            tool_records=data["tool_records"],
                            agent_name=agent_name,
                        )
                        current_parent_id = new_parent
                        _accumulate_usage(data.get("usage"))
                    elif event_type == "round_usage":
                        # Phase 12 / CTX-01: terminal-text-only round produced
                        # no tool_calls but may carry usage data.
                        _accumulate_usage(data.get("usage"))
                    elif event_type in ("code_stdout", "code_stderr"):
                        # Phase 10 SANDBOX-03: stream sandbox lines live regardless of redaction_on.
                        # Lines are already anonymized inside sandbox_stream_callback (alert #2).
                        # Bypassing buffer here ensures real-time streaming UX for execute_code.
                        yield f"data: {json.dumps(data)}\n\n"
                    elif redaction_on:
                        tool_loop_buffer.append(data)
                    else:
                        yield f"data: {json.dumps(data)}\n\n"
                for buffered in tool_loop_buffer:
                    yield f"data: {json.dumps(buffered)}\n\n"

                # Stream final text response
                # Phase 5 D-94 site #3: pre-flight egress filter on branch B stream_response.
                if redaction_on:
                    payload = json.dumps(messages, ensure_ascii=False)
                    egress_result = egress_filter(payload, registry, None)
                    if egress_result.tripped:
                        logger.warning(
                            "egress_blocked event=egress_blocked feature=stream_response_branch_b "
                            "match_count=%d",
                            egress_result.match_count,
                        )
                        raise EgressBlockedAbort("branch B stream_response egress blocked")

                # Phase 5 D-87: buffer all chunks when redaction is ON;
                # emit progressive deltas only when OFF (SC#5 byte-identical baseline).
                async for chunk in openrouter_service.stream_response(messages, model=llm_model):
                    if not chunk["done"]:
                        full_response += chunk["delta"]
                        if not redaction_on:
                            yield f"data: {json.dumps({'type': 'delta', 'delta': chunk['delta'], 'done': False})}\n\n"
                    else:
                        # Phase 12 / CTX-01: capture usage from terminal chunk if present.
                        _accumulate_usage(chunk.get("usage"))

        except EgressBlockedAbort:
            yield f"data: {json.dumps({'type': 'redaction_status', 'stage': 'blocked'})}\n\n"
            yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"
            return
        except Exception as exc:
            logger.error("event_generator error: %s", exc, exc_info=True)

        # Phase 5 D-87 + D-88 + D-90: buffered de-anon and single-batch delta emit.
        # When redaction ON: emit deanonymizing status, run de_anonymize_text with
        # graceful degrade (D-90), then emit ONE delta event with the full de-anon'd
        # text. When OFF: full_response was streamed progressively; skip this block.
        if redaction_on and full_response:
            yield f"data: {json.dumps({'type': 'redaction_status', 'stage': 'deanonymizing'})}\n\n"
            try:
                deanon_text = await redaction_service.de_anonymize_text(
                    full_response, registry, mode=settings.fuzzy_deanon_mode,
                )
            except Exception as exc:  # D-90 graceful degrade
                logger.warning(
                    "deanon_degraded event=deanon_degraded feature=deanonymize_text "
                    "fallback_mode=none error_class=%s",
                    type(exc).__name__,
                )
                deanon_text = await redaction_service.de_anonymize_text(
                    full_response, registry, mode="none",
                )
            full_response = deanon_text
            yield f"data: {json.dumps({'type': 'delta', 'delta': full_response, 'done': False})}\n\n"

        # SSE: agent_done (always emitted if agent was started)
        if agent_name:
            yield f"data: {json.dumps({'type': 'agent_done', 'agent': agent_name})}\n\n"

        # Phase 12 / HIST-01 / D-P12-12: persist the FINAL round — the
        # user-visible streamed text. tool_records=[] because tool calls (if
        # any) were already persisted in earlier rounds via the "round" event
        # handler above. parent_message_id chains from the last round (or the
        # user message id when this exchange had no tool rounds).
        if full_response:
            # Edge case: legacy callers (no rounds yielded) still need a
            # tool_records-bearing final row for backwards-compatible
            # history reconstruction. When current_parent_id is still
            # user_msg_id (no rounds happened) AND tool_records is non-empty
            # (defensive — shouldn't happen post-Phase-12), include them.
            final_records = (
                tool_records
                if (current_parent_id == user_msg_id and tool_records)
                else []
            )
            current_parent_id = _persist_round_message(
                client,
                thread_id=body.thread_id,
                user_id=user["id"],
                parent_message_id=current_parent_id,
                content=full_response,
                tool_records=final_records,
                agent_name=agent_name,
            )

        # Auto-generate thread title on first exchange
        if full_response:
            try:
                thread_row = client.table("threads").select("title").eq("id", body.thread_id).single().execute()
                if thread_row.data and thread_row.data["title"] == "New Thread":
                    # Phase 5 D-96: title-gen migrates to LLMProviderClient.
                    # When redaction ON: re-anonymize full_response for title LLM
                    # input (full_response is REAL form here after de-anon in Step 2).
                    if redaction_on:
                        anon_for_title = await redaction_service.redact_text_batch(
                            [full_response], registry,
                        )
                        title_input = anon_for_title[0]
                    else:
                        title_input = full_response
                    title_messages = [
                        {"role": "system", "content": "Generate a short title (max 6 words) for this chat conversation. Respond with ONLY the title text, no quotes, no punctuation at the end. If the message is in Indonesian, generate the title in Indonesian."},
                        {"role": "user", "content": anonymized_message},
                        {"role": "assistant", "content": title_input},
                    ]
                    title_result = await _llm_provider_client.call(
                        feature="title_gen",
                        messages=title_messages,
                        registry=registry,
                    )
                    new_title_raw = (
                        title_result.get("title")
                        or title_result.get("content")
                        or title_result.get("raw")
                        or ""
                    ).strip().strip('"\'')[:80]
                    # D-96: de-anon the LLM-emitted title BEFORE both persist and emit.
                    if redaction_on and new_title_raw:
                        new_title = await redaction_service.de_anonymize_text(
                            new_title_raw, registry, mode="none",
                        )
                    else:
                        new_title = new_title_raw
                    if new_title:
                        client.table("threads").update({"title": new_title}).eq("id", body.thread_id).execute()
                        yield f"data: {json.dumps({'type': 'thread_title', 'title': new_title, 'thread_id': body.thread_id})}\n\n"
            except Exception as _title_exc:
                # D-P6-12: 6-word template fallback — never crash the chat loop (NFR-3)
                try:
                    stub = " ".join(anonymized_message.split()[:6]) or "New Thread"
                    if redaction_on and stub != "New Thread":
                        stub = await redaction_service.de_anonymize_text(stub, registry, mode="none")
                    if stub:
                        client.table("threads").update({"title": stub}).eq("id", body.thread_id).execute()
                        yield f"data: {json.dumps({'type': 'thread_title', 'title': stub, 'thread_id': body.thread_id})}\n\n"
                    logger.info(
                        "chat.title_gen_fallback event=title_gen_fallback thread_id=%s error_class=%s",
                        body.thread_id, type(_title_exc).__name__,
                    )
                except Exception as _fb_exc:
                    logger.warning(
                        "event=title_gen_fallback_failed thread_id=%s error_class=%s",
                        body.thread_id, type(_fb_exc).__name__,
                    )

        # Phase 12 / CTX-02 / D-P12-01: emit one terminal usage event when
        # any round captured usage. CTX-06 graceful no-op when no provider
        # emitted usage data — terminal {done:true} fires unchanged.
        if any_usage_seen and last_prompt_tokens is not None:
            total_tokens = last_prompt_tokens + cumulative_completion_tokens
            yield f"data: {json.dumps({'type': 'usage', 'prompt_tokens': last_prompt_tokens, 'completion_tokens': cumulative_completion_tokens, 'total_tokens': total_tokens})}\n\n"

        yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"

    # Phase 17 / DEEP-01 / T-17-09 front-gate:
    # When deep_mode=True is requested, validate the feature flag and dispatch
    # to run_deep_mode_loop (a separate async generator with its own loop cap,
    # extended prompt, and todos tools). Standard event_generator is unchanged.
    if body.deep_mode:
        if not settings.deep_mode_enabled:
            raise HTTPException(
                status_code=400,
                detail="deep mode disabled",
            )
        return StreamingResponse(
            run_deep_mode_loop(
                messages=history,
                user_message=body.message,
                user_id=user["id"],
                user_email=user.get("email", ""),
                token=user["token"],
                tool_context=tool_context,
                thread_id=body.thread_id,
                user_msg_id=user_msg_id,
                client=client,
                sys_settings=sys_settings,
                web_search_effective=web_search_effective,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Phase 10 test helper — module-level re-export of _run_tool_loop for unit tests.
#
# _run_tool_loop is defined as an inner async generator inside stream_chat so
# it can close over body / user / sys_settings / web_search_effective.  Unit
# tests cannot call it directly.  This module-level generator mirrors its
# public interface exactly (same parameter names and defaults) but does NOT
# depend on any outer-scope closure variables.  The caller supplies
# ``tool_context`` directly and the web_search audit-log branch is skipped
# (tests never assert on that side-effect).
#
# ONLY import / call this from test code.
# ---------------------------------------------------------------------------

async def _run_tool_loop_for_test(
    messages,
    tools,
    max_iterations,
    user_id,
    tool_context,
    *,
    registry=None,
    redaction_service=None,
    redaction_on=False,
    available_tool_names=None,
    token=None,
):
    """Test-only async generator: mirrors _run_tool_loop without closure deps."""
    tool_records = []
    for _iteration in range(max_iterations):
        if not tools:
            break

        if redaction_on and registry is not None:
            payload = json.dumps(messages, ensure_ascii=False)
            egress_result = egress_filter(payload, registry, None)
            if egress_result.tripped:
                raise EgressBlockedAbort("tool_loop egress blocked")

        result = await openrouter_service.complete_with_tools(
            messages, tools, model=tool_context.get("llm_model", "openai/gpt-4o-mini")
        )

        # Phase 12 / CTX-01: surface usage even when this round had no tool_calls.
        if not result["tool_calls"]:
            yield "round_usage", {"usage": result.get("usage")}
            break

        # Phase 12 / HIST-01 / D-P12-12: track this iteration's records slice.
        iteration_start_idx = len(tool_records)

        for tc in result["tool_calls"]:
            func_name = tc["function"]["name"]
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                func_args = {}

            if redaction_on:
                yield "tool_start", {"type": "tool_start", "tool": func_name}
            else:
                yield "tool_start", {"type": "tool_start", "tool": func_name, "input": func_args}

            # Phase 10 D-P10-05/06: queue adapter for execute_code streaming.
            sandbox_event_queue: asyncio.Queue | None = None
            sandbox_callback = None
            workspace_event_callback = None
            if func_name == "execute_code":
                # Phase 14 / BRIDGE-06 (D-P14-07): emit code_mode_start once per stream
                # _bridge_active is a closure-local of event_generator; always False here
                if False and not _bridge_event_sent:
                    _bridge_event_sent = True
                    _bridge_tools_b: list[str] = []
                    try:
                        from app.services import tool_registry as _tr_b
                        _bridge_tools_b = [n for n in _tr_b._REGISTRY if n != "tool_search"]
                    except Exception:
                        pass
                    yield f"data: {json.dumps({'type': 'code_mode_start', 'tools': _bridge_tools_b})}\n\n"
                sandbox_event_queue = asyncio.Queue()

                async def sandbox_stream_callback_test(event_type: str, line: str):
                    emit_line = line
                    if redaction_on and registry is not None:
                        try:
                            anon = await anonymize_tool_output(
                                {"line": line}, registry, redaction_service,
                            )
                            if isinstance(anon, dict):
                                emit_line = anon.get("line", line)
                        except Exception as _exc:
                            logger.warning(
                                "sandbox stream anon failed err=%s — emitting skeleton", _exc,
                            )
                            emit_line = ""
                    await sandbox_event_queue.put({
                        "type": event_type,
                        "line": emit_line,
                        "tool_call_id": tc["id"],
                    })

                sandbox_callback = sandbox_stream_callback_test

                # Phase 18 / WS-10: workspace_callback for sandbox-emitted workspace_updated.
                def _workspace_event_callback_test(event: dict) -> None:
                    sandbox_event_queue.put_nowait(event)

                workspace_event_callback = _workspace_event_callback_test

            try:
                if (
                    available_tool_names is not None
                    and func_name not in available_tool_names
                ):
                    tool_output = {
                        "blocked": True,
                        "reason": f"Tool '{func_name}' is not available for this request.",
                    }
                elif redaction_on and registry is not None:
                    if func_name == "web_search":
                        real_args = func_args
                    else:
                        real_args = await deanonymize_tool_args(
                            func_args, registry, redaction_service,
                        )
                    if sandbox_event_queue is not None:
                        tool_output_task = asyncio.create_task(
                            tool_service.execute_tool(
                                func_name, real_args, user_id, tool_context,
                                registry=registry,
                                token=token,
                                stream_callback=sandbox_callback,
                                workspace_callback=workspace_event_callback,
                            )
                        )
                        while not tool_output_task.done():
                            try:
                                evt = await asyncio.wait_for(
                                    sandbox_event_queue.get(), timeout=0.1,
                                )
                                yield evt["type"], evt
                            except asyncio.TimeoutError:
                                continue
                        while not sandbox_event_queue.empty():
                            evt = sandbox_event_queue.get_nowait()
                            yield evt["type"], evt
                        tool_output = await tool_output_task
                    else:
                        tool_output = await tool_service.execute_tool(
                            func_name, real_args, user_id, tool_context,
                            registry=registry,
                            token=token,
                            stream_callback=None,
                        )
                    if func_name == "web_search":
                        tool_output = filter_tool_output_by_registry(tool_output, registry)
                    else:
                        tool_output = await anonymize_tool_output(
                            tool_output, registry, redaction_service,
                        )
                else:
                    if sandbox_event_queue is not None:
                        tool_output_task = asyncio.create_task(
                            tool_service.execute_tool(
                                func_name, func_args, user_id, tool_context,
                                token=token,
                                stream_callback=sandbox_callback,
                                workspace_callback=workspace_event_callback,
                            )
                        )
                        while not tool_output_task.done():
                            try:
                                evt = await asyncio.wait_for(
                                    sandbox_event_queue.get(), timeout=0.1,
                                )
                                yield evt["type"], evt
                            except asyncio.TimeoutError:
                                continue
                        while not sandbox_event_queue.empty():
                            evt = sandbox_event_queue.get_nowait()
                            yield evt["type"], evt
                        tool_output = await tool_output_task
                    else:
                        tool_output = await tool_service.execute_tool(
                            func_name, func_args, user_id, tool_context,
                            token=token,
                            stream_callback=None,
                        )
                # Phase 11 Plan 11-04 (MEM-01): persist successful multi-agent
                # tool call. Pre-Phase-11 only the exception path below
                # appended a record — the success path was a silent gap.
                from app.models.tools import ToolCallRecord
                tool_records.append(ToolCallRecord(
                    tool=func_name,
                    input=func_args,
                    output=tool_output,
                    tool_call_id=tc["id"],
                    status=_derive_tool_status(func_name, tool_output),
                ))
            except EgressBlockedAbort:
                raise
            except Exception as e:
                tool_output = {"error": str(e)}
                from app.models.tools import ToolCallRecord
                tool_records.append(ToolCallRecord(
                    tool=func_name,
                    input=func_args,
                    output={},
                    error=str(e),
                    tool_call_id=tc["id"],
                    status=_derive_tool_status(
                        func_name, None, exception_caught=True,
                    ),
                ))

            if redaction_on:
                yield "tool_result", {"type": "tool_result", "tool": func_name}
            else:
                yield "tool_result", {"type": "tool_result", "tool": func_name, "output": tool_output}

            # Phase 18 / WS-10: emit workspace_updated for successful workspace mutations.
            if (
                func_name in ("write_file", "edit_file")
                and isinstance(tool_output, dict)
                and tool_output.get("ok")
                and settings.workspace_enabled
            ):
                yield "workspace_updated", {
                    "type": "workspace_updated",
                    "file_path": tool_output.get("file_path"),
                    "operation": tool_output.get("operation"),
                    "size_bytes": tool_output.get("size_bytes"),
                    "source": "agent",
                }

            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [tc],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(tool_output),
            })

        # Phase 12 / HIST-01 / D-P12-12: yield this round's records + content + usage.
        iteration_tool_records = tool_records[iteration_start_idx:]
        yield "round", {
            "content": result.get("content") or "",
            "tool_records": iteration_tool_records,
            "usage": result.get("usage"),
        }

    yield "records", tool_records


# ---------------------------------------------------------------------------
# Phase 20 / Plan 20-04 (B4 fix): single canonical ConversationRegistry helper.
#
# Mirrors the inline blocks at:
#   - chat.py event_generator (pii_redaction_enabled → ConversationRegistry.load)
#   - chat.py run_deep_mode_loop (same pattern)
#
# Extracted to DRY across 4 LLM call sites added in Phase 20:
# gatekeeper, harness_engine, post_harness (Plan 20-05), and any future sites.
# Returns the parent ConversationRegistry when PII redaction is on;
# returns None when redaction is off (egress_filter is a no-op with None registry).
# ---------------------------------------------------------------------------

async def _get_or_build_conversation_registry(
    thread_id: str,
    sys_settings: dict | None = None,
):
    """Load the parent ConversationRegistry for this thread.

    Equivalent to the inline block at chat.py event_generator (redaction setup
    chokepoint). Use ONE call per request — registry is per-turn state, not per-call.

    Args:
        thread_id: Thread UUID to load registry for.
        sys_settings: Pre-loaded system settings dict. If None, loads from DB (60s cache).

    Returns:
        ConversationRegistry instance when pii_redaction_enabled is True; None otherwise.
    """
    if sys_settings is None:
        sys_settings = get_system_settings()
    redaction_on = bool(sys_settings.get("pii_redaction_enabled", True))
    if not redaction_on:
        return None
    return await ConversationRegistry.load(thread_id)


# ---------------------------------------------------------------------------
# Phase 20 / Plan 20-04 — Gatekeeper stream wrapper
# (module-level, not a closure, so tests can patch cleanly)
# ---------------------------------------------------------------------------

async def _gatekeeper_stream_wrapper(
    *,
    harness,
    thread_id: str,
    user_id: str,
    user_email: str,
    user_message: str,
    token: str,
    sys_settings: dict,
):
    """SSE wrapper: run gatekeeper, then if triggered → run harness engine in same stream.

    B4 fix: single canonical registry built once and passed to both gatekeeper
    and harness engine (SAME object instance — verified by test_gatekeeper_stream_wrapper_
    passes_same_registry_to_gatekeeper_and_engine). This ensures SEC-04 egress coverage
    is consistent across all 4 LLM call sites.

    Post-harness summary (Plan 20-05) fires inline after harness_complete,
    sharing the same registry instance (B4 invariant).
    """
    # B4 fix: single canonical registry — used by gatekeeper, engine, and post_harness.
    # All 4 LLM call sites of this turn share this SAME object instance.
    registry = await _get_or_build_conversation_registry(thread_id, sys_settings)

    triggered = False
    harness_run_id = None
    async for ev in run_gatekeeper(
        harness=harness,
        thread_id=thread_id,
        user_id=user_id,
        user_email=user_email,
        user_message=user_message,
        token=token,
        registry=registry,
    ):
        if ev.get("type") == "gatekeeper_complete":
            triggered = ev.get("triggered", False)
            harness_run_id = ev.get("harness_run_id")
            yield f"data: {json.dumps(ev)}\n\n"
            continue
        yield f"data: {json.dumps(ev)}\n\n"

    if not triggered or not harness_run_id:
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # In-stream handoff per D-07: drive harness engine in the same SSE stream.
    cancellation_event = asyncio.Event()
    async for ev in run_harness_engine(
        harness=harness,
        harness_run_id=harness_run_id,
        thread_id=thread_id,
        user_id=user_id,
        user_email=user_email,
        token=token,
        registry=registry,   # SAME registry — B4 invariant (SEC-04 across all 4 LLM call sites)
        cancellation_event=cancellation_event,
    ):
        yield f"data: {json.dumps(ev)}\n\n"

    # Plan 20-05 / D-09: inline post-harness summary handoff.
    # B4 invariant: REUSE the `registry` instance built at the top of this wrapper —
    # do NOT call _get_or_build_conversation_registry again (would create a fresh
    # registry, splitting egress state across the 4 LLM call sites of this turn).
    refreshed = await harness_runs_service.get_run_by_id(run_id=harness_run_id, token=token)
    if refreshed is not None:
        async for ev in summarize_harness_run(
            harness=harness,
            harness_run=refreshed,
            thread_id=thread_id,
            user_id=user_id,
            user_email=user_email,
            token=token,
            registry=registry,  # B4 — SAME object as gatekeeper + engine
        ):
            yield f"data: {json.dumps(ev)}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ---------------------------------------------------------------------------
# Phase 21 / Plan 21-04 (HIL-04) — Resume harness engine SSE wrapper
# Mirrors _gatekeeper_stream_wrapper's SSE serialization shape but skips the
# gatekeeper LLM round-trip (we already know we're resuming an existing run).
# Reuses _get_or_build_conversation_registry (chat.py:1695) — B4 invariant:
# never mint a fresh registry on resume.
# ---------------------------------------------------------------------------

async def _resume_harness_engine_sse(
    *,
    harness,
    harness_run_id: str,
    thread_id: str,
    user_id: str,
    user_email: str,
    token: str,
    sys_settings: dict,
    start_phase_index: int,
    cancellation_event: asyncio.Event,
):
    """Yields SSE-encoded events from run_harness_engine resumed at start_phase_index.

    B4 invariant: loads the parent ConversationRegistry once via
    _get_or_build_conversation_registry — same single-registry helper used by
    _gatekeeper_stream_wrapper. The egress filter wraps all subsequent LLM
    calls in run_harness_engine.
    """
    registry = await _get_or_build_conversation_registry(thread_id, sys_settings)
    async for ev in run_harness_engine(
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
        yield f"data: {json.dumps(ev)}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ---------------------------------------------------------------------------
# Phase 20 / Plan 20-04 — Harness cancel + active-harness endpoints
# ---------------------------------------------------------------------------

@router.post("/threads/{thread_id}/harness/cancel")
async def cancel_harness(thread_id: str, user: dict = Depends(get_current_user)):
    """Cancel the active harness run for this thread (D-03 + B3 dual-layer cancellation).

    How cancellation propagates to a running engine (HARN-07):
      - This endpoint flips `harness_runs.status='cancelled'` in the DB.
      - The engine (Plan 20-03 Task 4) checks two channels BEFORE each phase:
          (1) An in-process asyncio.Event passed by reference from the SAME
              request's _gatekeeper_stream_wrapper. This handles the rare case
              of a same-process Cancel from a code path holding the event ref.
          (2) A DB poll via harness_runs_service.get_run_by_id — checks the
              .status field. THIS is the channel triggered by the Cancel
              button in the frontend, which fires this endpoint on a SEPARATE
              HTTP request from the SSE stream that owns the engine generator.
      - Combined: the user clicks Cancel → this endpoint flips DB row →
        engine notices at the next phase boundary (typically <60s) → engine
        yields harness_phase_error{reason='cancelled_by_user'} → engine exits.
      - Workspace artifacts produced by completed phases are preserved
        (the engine does not roll back phase_results on cancel).
    """
    if not settings.harness_enabled:
        raise HTTPException(status_code=404, detail="harness_disabled")
    active = await harness_runs_service.get_active_run(
        thread_id=thread_id, token=user["token"]
    )
    if active is None:
        raise HTTPException(status_code=404, detail={"error": "no_active_run"})
    await harness_runs_service.cancel(
        run_id=active["id"],
        user_id=user["id"],
        user_email=user.get("email", ""),
        token=user["token"],
    )
    return {"ok": True, "harness_run_id": active["id"], "status": "cancelled"}


@router.get("/threads/{thread_id}/harness/active")
async def get_active_harness(thread_id: str, user: dict = Depends(get_current_user)):
    """Return the active harness run state for frontend rehydration (Plan 20-09)."""
    if not settings.harness_enabled:
        return {"harnessRun": None}
    active = await harness_runs_service.get_active_run(
        thread_id=thread_id, token=user["token"]
    )
    if active is None:
        return {"harnessRun": None}
    h = harness_registry.get_harness(active["harness_type"])
    return {
        "harnessRun": {
            "id": active["id"],
            "harnessType": active["harness_type"],
            "status": active["status"],
            "currentPhase": active["current_phase"],
            "phaseCount": len(h.phases) if h else 0,
            "phaseName": (
                h.phases[active["current_phase"]].name
                if h and active["current_phase"] < len(h.phases)
                else "—"
            ),
            "errorDetail": active.get("error_detail"),
        }
    }


# ---------------------------------------------------------------------------
# Phase 17 / DEEP-02 — Deep Mode loop (run_deep_mode_loop)
#
# A NEW module-level async generator that mirrors the _run_tool_loop_for_test
# pattern but:
#   - Uses max_deep_rounds (default 50) as the iteration cap (DEEP-02).
#   - Assembles an extended system prompt via build_deep_mode_system_prompt
#     (DEEP-05, TODO-04 — deterministic, KV-cache-friendly, no timestamps).
#   - Loads write_todos and read_todos as additional deep-mode tools (D-10).
#   - After every successful write_todos / read_todos call, emits a
#     todos_updated SSE event with the full list snapshot (D-17, D-18, TODO-03).
#   - On iteration max_deep_rounds - 1, swaps tools to [] and injects a
#     "summarize and deliver" system message (DEEP-06).
#   - Persists assistant message rows with deep_mode=True (DEEP-04 / MIG-04).
#   - Routes every LLM call through the egress filter (D-32, T-17-10).
#   - Mid-loop interrupt safety: write_todos commits to DB before SSE event
#     is emitted, so a disconnect after a write preserves the committed todos
#     (DEEP-07). Reuses the per-round persistence pattern from chat.py.
#
# DEEP-03 invariant: the standard event_generator is UNCHANGED. All deep-mode
# behavior lives exclusively in this function. The byte-identical fallback
# (deep_mode=False or absent) sees NO change in tools, prompt, or events.
# ---------------------------------------------------------------------------


async def run_deep_mode_loop(
    messages: list[dict],
    user_message: str,
    user_id: str,
    user_email: str,
    token: str,
    tool_context: dict,
    thread_id: str,
    user_msg_id: str,
    client,
    sys_settings: dict,
    web_search_effective: bool,
    *,
    resume_run_id: str | None = None,
    resume_tool_result: str | None = None,
    resume_round_index: int = 0,
):
    """Phase 17 / DEEP-02: Deep Mode agent loop.

    Async generator that produces SSE event strings (yielded directly to
    StreamingResponse). Mirrors the event format of the standard event_generator:
    ``data: {json}\\n\\n`` for each SSE event.

    Args:
        messages: Pre-built history list (already loaded by stream_chat).
        user_message: The raw user message string (pre-redaction).
        user_id: Authenticated user's UUID.
        user_email: Authenticated user's email (for audit log).
        token: JWT access token for RLS-scoped Supabase calls.
        tool_context: Per-request tool context dict (thread_id, top_k, etc.).
        thread_id: Current thread UUID.
        user_msg_id: The message_id of the persisted user message (parent chain start).
        client: Supabase client.
        sys_settings: System settings dict (llm_model, pii_redaction_enabled, ...).
        web_search_effective: ADR-0008 computed web_search toggle.
        resume_run_id: Phase 19 / D-04 — run_id of a waiting_for_user agent_runs row.
            When set, the loop is resuming from a prior ask_user pause.
        resume_tool_result: Phase 19 / D-04/D-15 — user's reply to the pending ask_user
            question, injected verbatim as the tool result in loop_messages.
        resume_round_index: Phase 19 / D-04 — loop iteration to start from on resume.
    """
    from app.services.deep_mode_prompt import build_deep_mode_system_prompt
    from app.services.redaction import (
        ConversationRegistry,
        anonymize_tool_output,
        deanonymize_tool_args,
        filter_tool_output_by_registry,
    )
    from app.services.redaction_service import get_redaction_service

    llm_model = sys_settings.get("llm_model", settings.openrouter_model)
    max_iterations = settings.max_deep_rounds  # DEEP-02: 50 rounds

    # --- Phase 17 / D-32: egress filter + redaction setup (mirrors event_generator) ---
    redaction_on = bool(sys_settings.get("pii_redaction_enabled", True))
    redaction_service = get_redaction_service()
    if redaction_on:
        registry = await ConversationRegistry.load(thread_id)
        raw_strings = [m["content"] for m in messages if m.get("content")] + [user_message]
        anonymized_strings = await redaction_service.redact_text_batch(raw_strings, registry)
        anon_history = [
            {**h, "content": anonymized_strings[i]}
            for i, h in enumerate(m for m in messages if m.get("content"))
        ]
        anonymized_message = anonymized_strings[-1]
        yield f"data: {json.dumps({'type': 'redaction_status', 'stage': 'anonymizing'})}\n\n"
    else:
        registry = None
        anon_history = messages
        anonymized_message = user_message

    # --- Build deep-mode tools list (D-10: standard tools + write_todos + read_todos) ---
    if settings.tools_enabled and settings.tool_registry_enabled:
        from app.services import tool_registry as _tr
        _deep_active_set = _tr.make_active_set()
        from app.services.skill_catalog_service import register_user_skills
        await register_user_skills(user_id, token)
        deep_tools = _tr.build_llm_tools(
            active_set=_deep_active_set,
            web_search_enabled=web_search_effective,
            sandbox_enabled=settings.sandbox_enabled,
            agent_allowed_tools=None,
        )
        # write_todos and read_todos are loading="immediate" in tool_registry Phase 17 block
        # — they are already included in deep_tools above.
        catalog_block = await _tr.build_catalog_block(agent_allowed_tools=None)
    else:
        deep_tools = tool_service.get_available_tools(web_search_enabled=web_search_effective)
        catalog_block = await build_skill_catalog_block(user_id, token)

    available_tool_names = [t["function"]["name"] for t in deep_tools]

    # --- Phase 17 / DEEP-05 + TODO-04: assemble extended system prompt ---
    pii_guidance = get_pii_guidance_block(redaction_enabled=redaction_on)
    extended_system_prompt = build_deep_mode_system_prompt(
        SYSTEM_PROMPT + pii_guidance + catalog_block
    )

    # --- Build initial messages array ---
    loop_messages: list[dict] = (
        [{"role": "system", "content": extended_system_prompt}]
        + [{"role": m["role"], "content": m.get("content") or ""} for m in anon_history]
        + [{"role": "user", "content": anonymized_message}]
    )

    # run_id is initialised below inside the try block (Site A).
    # Declared here so the except handler's `if run_id is not None` guard always
    # has a binding, even if the try block raises before Site A executes.
    run_id = None

    # --- Phase 19 / D-04/D-15: resume injection ---
    # When resuming from a waiting_for_user pause, inject the user's reply as the
    # ask_user tool result. The ask_user tool_call was already persisted in the
    # previous round's messages row (tool_calls JSONB). We reconstruct the synthetic
    # ask_user tool_result message so the LLM sees the full context.
    # D-15: body.message is passed through VERBATIM — no filtering.
    if resume_run_id is not None and resume_tool_result is not None:
        # Inject a synthetic ask_user tool_result into loop_messages.
        # Use a stable sentinel tool_call_id so the LLM can pair it.
        _resume_tool_call_id = f"resume-ask-user-{resume_run_id}"
        loop_messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": _resume_tool_call_id,
                "type": "function",
                "function": {
                    "name": "ask_user",
                    "arguments": json.dumps({"question": ""}),
                },
            }],
        })
        loop_messages.append({
            "role": "tool",
            "tool_call_id": _resume_tool_call_id,
            "content": resume_tool_result,
        })

    # --- Wire user_email + token into tool_context for write_todos/read_todos audit (D-34) ---
    tool_context = {**tool_context, "user_email": user_email, "token": token}
    if settings.tools_enabled and settings.tool_registry_enabled:
        from app.services import tool_registry as _tr2
        tool_context["active_set"] = _tr2.make_active_set()
        tool_context["agent_allowed_tools"] = None

    # --- Per-round state ---
    current_parent_id = user_msg_id
    tool_records: list[ToolCallRecord] = []
    full_response = ""
    last_prompt_tokens: int | None = None
    cumulative_completion_tokens = 0
    any_usage_seen = False

    def _accumulate_usage_dm(usage: dict | None) -> None:
        nonlocal last_prompt_tokens, cumulative_completion_tokens, any_usage_seen
        if usage is None:
            return
        any_usage_seen = True
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        if prompt is not None:
            last_prompt_tokens = prompt
        if completion is not None:
            cumulative_completion_tokens += completion

    # current_tools is mutable — swapped to [] on final iteration (DEEP-06)
    current_tools = list(deep_tools)
    tool_loop_buffer: list[dict] = []

    try:
        # --- Phase 19 / 19-06 / D-16 Site A: agent_runs lifecycle + working emission ---
        # ALL site A behavior (agent_runs.start_run + agent_status yield) gated by
        # settings.sub_agent_enabled per D-17 byte-identical fallback invariant.
        # Phase 19 / D-16 Site B (waiting_for_user) — OWNED by 19-05's ask_user dispatch handler.
        # This plan does NOT emit a second waiting_for_user event. The verify gate below
        # asserts exactly 1 emission location across chat.py (in the ask_user handler).
        # IMPORTANT: kept INSIDE try so start_run DB errors are caught by the except
        # handler below and a proper agent_status:error + done event is emitted (C-01 fix).
        if settings.sub_agent_enabled:
            if resume_run_id is None:
                run_record = await agent_runs_service.start_run(
                    thread_id=thread_id, user_id=user_id, user_email=user_email, token=token,
                )
                run_id = run_record["id"]
            else:
                run_id = resume_run_id
            yield f"data: {json.dumps({'type': 'agent_status', 'status': 'working'})}\n\n"
        # else: run_id stays None — SUB_AGENT_ENABLED off, no agent_runs lifecycle

        for _iteration in range(max_iterations):
            # --- Phase 17 / DEEP-06: force summarize on final iteration ---
            if _iteration == max_iterations - 1 and current_tools:
                loop_messages.append({
                    "role": "system",
                    "content": (
                        "You have reached the iteration limit. "
                        "Please summarize what you have completed and deliver "
                        "a final answer to the user."
                    ),
                })
                current_tools = []  # force terminal text round

            if not current_tools and _iteration > 0:
                break  # no tools → terminal text round via stream_response below

            # --- Phase 17 / D-32 / T-17-10: egress filter before LLM call ---
            if redaction_on and registry is not None:
                payload = json.dumps(loop_messages, ensure_ascii=False)
                egress_result = egress_filter(payload, registry, None)
                if egress_result.tripped:
                    logger.warning(
                        "egress_blocked event=egress_blocked feature=deep_mode_loop "
                        "iteration=%d match_count=%d",
                        _iteration,
                        egress_result.match_count,
                    )
                    raise EgressBlockedAbort("deep_mode_loop egress blocked")

            # --- LLM call (with tools) ---
            result = await openrouter_service.complete_with_tools(
                loop_messages, current_tools, model=llm_model
            )

            # Terminal: no tool_calls → accumulate text and exit loop
            if not result["tool_calls"]:
                _accumulate_usage_dm(result.get("usage"))
                chunk_text = result.get("content") or ""
                if chunk_text:
                    full_response += chunk_text
                    if not redaction_on:
                        yield f"data: {json.dumps({'type': 'delta', 'delta': chunk_text, 'done': False})}\n\n"
                break

            iteration_start_idx = len(tool_records)
            iteration_tool_records: list[ToolCallRecord] = []

            # --- Process each tool call ---
            for tc in result["tool_calls"]:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    func_args = {}

                # SSE: tool_start
                tool_start_evt: dict = (
                    {"type": "tool_start", "tool": func_name}
                    if redaction_on
                    else {"type": "tool_start", "tool": func_name, "input": func_args}
                )
                if redaction_on:
                    tool_loop_buffer.append(tool_start_evt)
                else:
                    yield f"data: {json.dumps(tool_start_evt)}\n\n"

                try:
                    # --- Phase 19 / 19-05: ask_user dispatch (D-01, D-16, D-23, ASK-02/04) ---
                    # CANONICAL OWNER of Site B agent_status='waiting_for_user' emission (D-16).
                    # Intercepts BEFORE task and _dispatch_tool_deep. Returns immediately
                    # (closes generator) per D-01. Does NOT persist a tool_result messages row
                    # for the ask_user round (D-15) — persisted state is agent_runs.last_round_index.
                    if func_name == "ask_user" and settings.sub_agent_enabled:
                        question = func_args.get("question", "")

                        # D-23: audit — fire-and-forget, never raises
                        log_action(
                            user_id=user_id,
                            user_email=user_email,
                            action="ask_user",
                            resource_type="agent_runs",
                            resource_id=thread_id,
                            details={"question": question[:200]},
                        )

                        # Persist pending state via 19-02 service
                        _active = await agent_runs_service.get_active_run(thread_id, token)
                        if _active is None:
                            _active = await agent_runs_service.start_run(
                                thread_id, user_id, user_email, token
                            )
                        await agent_runs_service.set_pending_question(
                            run_id=_active["id"],
                            question=question,
                            last_round_index=_iteration,
                            token=token,
                        )

                        # Phase 19 / D-16 Site B — CANONICAL OWNER.
                        # Exactly one emission of agent_status='waiting_for_user' in chat.py.
                        # 19-06 documents this ownership; it does NOT emit a second copy.
                        yield f"data: {json.dumps({'type': 'agent_status', 'status': 'waiting_for_user', 'detail': question})}\n\n"
                        yield f"data: {json.dumps({'type': 'ask_user', 'question': question})}\n\n"
                        yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"
                        return  # close generator cleanly per D-01

                    # --- Phase 19 / 19-04: task tool dispatch (D-05, D-06, D-12, D-23) ---
                    # Intercept BEFORE the standard _dispatch_tool_deep path so the sub-agent
                    # SSE event forwarding can yield directly to the parent's generator.
                    elif func_name == "task" and settings.sub_agent_enabled:
                        import uuid as _uuid  # noqa: PLC0415
                        task_id = str(_uuid.uuid4())  # server-generated UUID (Discretion default)
                        description = func_args.get("description", "")
                        context_files = func_args.get("context_files", [])

                        # D-23: audit log — fire-and-forget, never raises
                        log_action(
                            user_id=user_id,
                            user_email=user_email,
                            action="task",
                            resource_type="agent_runs",
                            resource_id=thread_id,
                            details={"task_id": task_id, "description": description[:200]},
                        )

                        yield f"data: {json.dumps({'type': 'task_start', 'task_id': task_id, 'description': description, 'context_files': context_files})}\n\n"

                        # Forward sub-agent SSE events, tagging nested events with task_id (D-06)
                        sub_gen = run_sub_agent_loop(
                            description=description,
                            context_files=context_files,
                            parent_user_id=user_id,
                            parent_user_email=user_email,
                            parent_token=token,
                            parent_tool_context=tool_context,
                            parent_thread_id=thread_id,
                            parent_user_msg_id=user_msg_id,
                            client=client,
                            sys_settings=sys_settings,
                            web_search_effective=web_search_effective,
                            task_id=task_id,
                            parent_redaction_registry=registry,  # D-21 — share parent's registry
                        )
                        final_result = None
                        async for evt in sub_gen:
                            if isinstance(evt, dict) and "_terminal_result" in evt:
                                final_result = evt["_terminal_result"]
                            else:
                                # D-06: tag nested tool_start/tool_result events with task_id
                                tagged = {**evt, "task_id": task_id}
                                yield f"data: {json.dumps(tagged)}\n\n"

                        if final_result and "error" in final_result:
                            # D-12: structured error → task_error SSE + parent tool_output
                            yield f"data: {json.dumps({'type': 'task_error', 'task_id': task_id, **final_result})}\n\n"
                            tool_output = final_result
                        else:
                            text_result = (final_result or {}).get("text", "")
                            yield f"data: {json.dumps({'type': 'task_complete', 'task_id': task_id, 'result': text_result})}\n\n"
                            tool_output = {"result": text_result}

                    elif func_name not in available_tool_names:
                        tool_output: dict = {
                            "blocked": True,
                            "reason": f"Tool '{func_name}' is not available for this request.",
                        }
                    elif redaction_on and registry is not None:
                        real_args = (
                            func_args if func_name == "web_search"
                            else await deanonymize_tool_args(func_args, registry, redaction_service)
                        )
                        tool_output = await _dispatch_tool_deep(
                            func_name, real_args, user_id, tool_context, token=token
                        )
                        if func_name == "web_search":
                            tool_output = filter_tool_output_by_registry(tool_output, registry)
                        else:
                            tool_output = await anonymize_tool_output(
                                tool_output, registry, redaction_service
                            )
                    else:
                        tool_output = await _dispatch_tool_deep(
                            func_name, func_args, user_id, tool_context, token=token
                        )

                    # --- Phase 17 / D-17 / D-18 / TODO-03: todos_updated SSE ---
                    # Emitted AFTER DB write commits (write_todos is already awaited above),
                    # BEFORE tool_result. Satisfies DEEP-07 mid-loop interrupt safety.
                    if func_name in ("write_todos", "read_todos") and isinstance(tool_output, dict):
                        todos_snapshot = tool_output.get("todos", [])
                        yield f"data: {json.dumps({'type': 'todos_updated', 'todos': todos_snapshot})}\n\n"

                    record = ToolCallRecord(
                        tool=func_name,
                        input=func_args,
                        output=tool_output,
                        tool_call_id=tc["id"],
                        status=_derive_tool_status(func_name, tool_output),
                    )
                except EgressBlockedAbort:
                    raise
                except Exception as exc:
                    tool_output = {"error": str(exc)}
                    record = ToolCallRecord(
                        tool=func_name,
                        input=func_args,
                        output={},
                        error=str(exc),
                        tool_call_id=tc["id"],
                        status=_derive_tool_status(func_name, None, exception_caught=True),
                    )

                tool_records.append(record)
                iteration_tool_records.append(record)

                # SSE: tool_result
                tool_result_evt: dict = (
                    {"type": "tool_result", "tool": func_name}
                    if redaction_on
                    else {"type": "tool_result", "tool": func_name, "output": tool_output}
                )
                if redaction_on:
                    tool_loop_buffer.append(tool_result_evt)
                else:
                    yield f"data: {json.dumps(tool_result_evt)}\n\n"

                # Phase 18 / WS-10: emit workspace_updated for successful workspace mutations.
                # Deep-mode: emit directly (same pattern as todos_updated at L1709-1714).
                if (
                    func_name in ("write_file", "edit_file")
                    and isinstance(tool_output, dict)
                    and tool_output.get("ok")
                    and settings.workspace_enabled
                ):
                    workspace_evt = {
                        "type": "workspace_updated",
                        "file_path": tool_output.get("file_path"),
                        "operation": tool_output.get("operation"),
                        "size_bytes": tool_output.get("size_bytes"),
                        "source": "agent",
                    }
                    if redaction_on:
                        tool_loop_buffer.append(workspace_evt)
                    else:
                        yield f"data: {json.dumps(workspace_evt)}\n\n"

                loop_messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tc],
                })
                loop_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_output),
                })

            # --- Phase 12 / HIST-01 / DEEP-04: per-round persistence ---
            round_content = result.get("content") or ""
            _accumulate_usage_dm(result.get("usage"))
            new_parent = _persist_round_message(
                client,
                thread_id=thread_id,
                user_id=user_id,
                parent_message_id=current_parent_id,
                content=round_content,
                tool_records=iteration_tool_records,
                agent_name=None,
                deep_mode=True,  # DEEP-04: tag each round row with deep_mode=True
            )
            current_parent_id = new_parent

        # Flush buffered tool events (redaction ON path)
        for buffered in tool_loop_buffer:
            yield f"data: {json.dumps(buffered)}\n\n"

        # --- Final streaming response (terminal text after tools exhausted) ---
        if not full_response:
            if redaction_on and registry is not None:
                payload = json.dumps(loop_messages, ensure_ascii=False)
                egress_result = egress_filter(payload, registry, None)
                if egress_result.tripped:
                    logger.warning(
                        "egress_blocked event=egress_blocked feature=deep_mode_stream "
                        "match_count=%d",
                        egress_result.match_count,
                    )
                    raise EgressBlockedAbort("deep_mode stream_response egress blocked")

            async for chunk in openrouter_service.stream_response(loop_messages, model=llm_model):
                if not chunk["done"]:
                    full_response += chunk["delta"]
                    if not redaction_on:
                        yield f"data: {json.dumps({'type': 'delta', 'delta': chunk['delta'], 'done': False})}\n\n"
                else:
                    _accumulate_usage_dm(chunk.get("usage"))

    except EgressBlockedAbort:
        yield f"data: {json.dumps({'type': 'redaction_status', 'stage': 'blocked'})}\n\n"
        yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"
        return
    except Exception as exc:
        logger.error("run_deep_mode_loop error: %s", exc, exc_info=True)
        # Phase 19 / D-16 site D — error transition + SSE. Gated by sub_agent_enabled (D-17).
        if settings.sub_agent_enabled:
            if run_id is not None:
                try:
                    await agent_runs_service.error(
                        run_id, token, user_id, user_email,
                        error_detail=str(exc)[:500],  # D-19 sanitized — no stack trace
                    )
                except Exception:
                    logger.exception("failed to record agent_runs error")
            yield f"data: {json.dumps({'type': 'agent_status', 'status': 'error', 'detail': str(exc)[:200]})}\n\n"
        # legacy done emission preserved in BOTH branches (D-17 byte-identical fallback)
        yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"
        return

    # --- De-anonymize and emit final response (redaction ON) ---
    if redaction_on and full_response:
        yield f"data: {json.dumps({'type': 'redaction_status', 'stage': 'deanonymizing'})}\n\n"
        try:
            deanon_text = await redaction_service.de_anonymize_text(
                full_response, registry, mode=settings.fuzzy_deanon_mode,
            )
        except Exception as exc:
            logger.warning(
                "deanon_degraded feature=deep_mode_loop error_class=%s", type(exc).__name__,
            )
            deanon_text = await redaction_service.de_anonymize_text(
                full_response, registry, mode="none",
            )
        full_response = deanon_text
        yield f"data: {json.dumps({'type': 'delta', 'delta': full_response, 'done': False})}\n\n"

    # --- Persist final text row (DEEP-04: deep_mode=True) ---
    if full_response:
        _persist_round_message(
            client,
            thread_id=thread_id,
            user_id=user_id,
            parent_message_id=current_parent_id,
            content=full_response,
            tool_records=[],
            agent_name=None,
            deep_mode=True,  # DEEP-04
        )

    # --- Auto-title (mirrors standard path) ---
    try:
        thread_row = client.table("threads").select("title").eq("id", thread_id).single().execute()
        if thread_row.data and thread_row.data["title"] == "New Thread":
            title_input = full_response
            if redaction_on and full_response:
                anon_for_title = await redaction_service.redact_text_batch([full_response], registry)
                title_input = anon_for_title[0]
            title_messages_dm = [
                {"role": "system", "content": "Generate a short title (max 6 words) for this chat conversation. Respond with ONLY the title text, no quotes, no punctuation at the end. If the message is in Indonesian, generate the title in Indonesian."},
                {"role": "user", "content": anonymized_message},
                {"role": "assistant", "content": title_input},
            ]
            title_result = await _llm_provider_client.call(
                feature="title_gen",
                messages=title_messages_dm,
                registry=registry,
            )
            new_title_raw = (
                title_result.get("title")
                or title_result.get("content")
                or title_result.get("raw")
                or ""
            ).strip().strip('"\'')[:80]
            if redaction_on and new_title_raw:
                new_title = await redaction_service.de_anonymize_text(
                    new_title_raw, registry, mode="none",
                )
            else:
                new_title = new_title_raw
            if new_title:
                client.table("threads").update({"title": new_title}).eq("id", thread_id).execute()
                yield f"data: {json.dumps({'type': 'thread_title', 'title': new_title, 'thread_id': thread_id})}\n\n"
    except Exception as _title_exc:
        try:
            stub = " ".join(user_message.split()[:6]) or "New Thread"
            if stub:
                client.table("threads").update({"title": stub}).eq("id", thread_id).execute()
                yield f"data: {json.dumps({'type': 'thread_title', 'title': stub, 'thread_id': thread_id})}\n\n"
            logger.info(
                "chat.title_gen_fallback event=title_gen_fallback thread_id=%s error_class=%s",
                thread_id, type(_title_exc).__name__,
            )
        except Exception:
            pass

    # --- Terminal SSE: usage + done ---
    if any_usage_seen and last_prompt_tokens is not None:
        total_tokens = last_prompt_tokens + cumulative_completion_tokens
        yield f"data: {json.dumps({'type': 'usage', 'prompt_tokens': last_prompt_tokens, 'completion_tokens': cumulative_completion_tokens, 'total_tokens': total_tokens})}\n\n"

    # Phase 19 / D-16 site C — emit complete before final done. Gated by sub_agent_enabled (D-17).
    if settings.sub_agent_enabled:
        if run_id is not None:
            await agent_runs_service.complete(run_id, token, user_id, user_email)
        yield f"data: {json.dumps({'type': 'agent_status', 'status': 'complete'})}\n\n"
    yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"  # emitted in BOTH branches (D-17)


async def _dispatch_tool_deep(
    name: str,
    arguments: dict,
    user_id: str,
    context: dict | None = None,
    *,
    token: str | None = None,
):
    """Tool dispatch for run_deep_mode_loop — registry-first, same pattern as _dispatch_tool.

    Separate module-level function (not a closure) so run_deep_mode_loop can be
    module-level. The registry already has write_todos and read_todos registered
    (Phase 17 Plan 17-03). All calls route through the same adapter-wrap invariant.
    """
    if settings.tool_registry_enabled:
        from app.services import tool_registry as _tr
        if name in _tr._REGISTRY:
            tool_def = _tr._REGISTRY[name]
            return await tool_def.executor(
                arguments,
                user_id,
                context,
                token=token,
            )
    return await tool_service.execute_tool(
        name, arguments, user_id, context, token=token,
    )
