import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_client
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

    # Load chat history — branch-aware when parent_message_id is provided
    if body.parent_message_id:
        # Branch mode: walk ancestor chain from the specified parent
        all_messages = (
            client.table("messages")
            .select("id, role, content, parent_message_id")
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
        history = [{"role": m["role"], "content": m["content"]} for m in chain]
    else:
        # Flat mode: all messages in order (existing behavior)
        history = (
            client.table("messages")
            .select("role, content")
            .eq("thread_id", body.thread_id)
            .eq("user_id", user["id"])
            .order("created_at")
            .execute()
        ).data or []

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

    # Tool execution context (passed to search_documents tool)
    tool_context = {
        "top_k": settings.rag_top_k,
        "threshold": settings.rag_similarity_threshold,
        "embedding_model": sys_settings.get("custom_embedding_model") or sys_settings["embedding_model"],
        "llm_model": llm_model,
    }

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

            if not result["tool_calls"]:
                break

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
                        tool_output = await tool_service.execute_tool(
                            func_name, real_args, user_id, tool_context,
                            registry=registry,
                            token=token,
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
                        tool_output = await tool_service.execute_tool(
                            func_name, func_args, user_id, tool_context,
                            token=token,
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
                    tool_records.append(ToolCallRecord(
                        tool=func_name, input=func_args, output=tool_output
                    ))
                except EgressBlockedAbort:
                    # Bubble up to event_generator's outer handler — DO NOT
                    # swallow here (D-94: trip aborts the entire turn).
                    raise
                except Exception as e:
                    tool_output = {"error": str(e)}
                    tool_records.append(ToolCallRecord(
                        tool=func_name, input=func_args, output={}, error=str(e)
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

        # Expose collected records for persistence
        yield "records", tool_records

    async def event_generator():
        tool_records = []
        full_response = ""
        agent_name = None

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
            all_tools = (
                tool_service.get_available_tools(web_search_enabled=web_search_effective)
                if settings.tools_enabled else []
            )
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
                skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
                messages = (
                    [{"role": "system", "content": agent_def.system_prompt + skill_catalog}]
                    + [{"role": m["role"], "content": m["content"]} for m in anonymized_history]
                    + [{"role": "user", "content": anonymized_message}]
                )

                # 4. Get agent's tool subset (filtered from the effective catalog)
                agent_tools = agent_service.get_agent_tools(agent_def, all_tools)

                # 5. Sub-agent tool loop
                # When redaction is ON: buffer tool_start/tool_result events and
                # only flush after the loop completes without an EgressBlockedAbort.
                # Prevents corrupt partial-turn UI state when a later iteration's
                # egress filter trips after earlier tool events were already emitted.
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
                skill_catalog = await build_skill_catalog_block(user["id"], user["token"])
                messages = (
                    [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance + skill_catalog}]
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
                tool_loop_buffer = []
                async for event_type, data in _run_tool_loop(
                    messages, tools, settings.tools_max_iterations,
                    user["id"], tool_context,
                    registry=registry,
                    redaction_service=redaction_service,
                    redaction_on=redaction_on,
                    available_tool_names=available_tool_names,
                    token=user["token"],
                ):
                    if event_type == "records":
                        tool_records = data
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

        # Persist assistant message after streaming completes (chained to user message)
        if full_response:
            insert_data = {
                "thread_id": body.thread_id,
                "user_id": user["id"],
                "role": "assistant",
                "content": full_response,
                "parent_message_id": user_msg_id,
            }
            if tool_records or agent_name:
                insert_data["tool_calls"] = ToolCallSummary(
                    agent=agent_name,
                    calls=tool_records,
                ).model_dump()
            client.table("messages").insert(insert_data).execute()

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

        yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
