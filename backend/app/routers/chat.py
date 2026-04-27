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
from app.models.tools import ToolCallRecord, ToolCallSummary

# Phase 5 — chat-loop redaction integration (D-83..D-97)
from app.services.redaction import (
    ConversationRegistry,
    anonymize_tool_output,
    deanonymize_tool_args,
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

    async def _run_tool_loop(messages, tools, max_iterations, user_id, tool_context):
        """Shared tool-calling loop used by both agent and non-agent paths."""
        tool_records = []
        for _iteration in range(max_iterations):
            if not tools:
                break
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

                yield "tool_start", {
                    "type": "tool_start", "tool": func_name, "input": func_args,
                }

                try:
                    tool_output = await tool_service.execute_tool(
                        func_name, func_args, user_id, tool_context
                    )
                    tool_records.append(ToolCallRecord(
                        tool=func_name, input=func_args, output=tool_output
                    ))
                except Exception as e:
                    tool_output = {"error": str(e)}
                    tool_records.append(ToolCallRecord(
                        tool=func_name, input=func_args, output={}, error=str(e)
                    ))

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

        try:
            if settings.agents_enabled:
                # --- Multi-agent path ---
                # 1. Orchestrator classification
                try:
                    orch_model = settings.agents_orchestrator_model or llm_model
                    classification = await agent_service.classify_intent(
                        body.message, history, openrouter_service, orch_model
                    )
                    agent_name = classification.agent
                except Exception:
                    agent_name = "general"

                agent_def = agent_service.get_agent(agent_name)

                # 2. SSE: agent_start
                yield f"data: {json.dumps({'type': 'agent_start', 'agent': agent_name, 'display_name': agent_def.display_name})}\n\n"

                # 3. Build messages with agent's system prompt
                messages = (
                    [{"role": "system", "content": agent_def.system_prompt}]
                    + [{"role": m["role"], "content": m["content"]} for m in history]
                    + [{"role": "user", "content": body.message}]
                )

                # 4. Get agent's tool subset
                all_tools = tool_service.get_available_tools() if settings.tools_enabled else []
                agent_tools = agent_service.get_agent_tools(agent_def, all_tools)

                # 5. Sub-agent tool loop
                async for event_type, data in _run_tool_loop(
                    messages, agent_tools, agent_def.max_iterations,
                    user["id"], tool_context,
                ):
                    if event_type == "records":
                        tool_records = data
                    else:
                        yield f"data: {json.dumps(data)}\n\n"

                # 6. Stream final text response
                async for chunk in openrouter_service.stream_response(messages, model=llm_model):
                    if not chunk["done"]:
                        full_response += chunk["delta"]
                        yield f"data: {json.dumps({'type': 'delta', 'delta': chunk['delta'], 'done': False})}\n\n"

            else:
                # --- Single-agent path (Module 7 behavior) ---
                # Phase 4 D-79/D-80: append PII guidance to SYSTEM_PROMPT when
                # redaction is enabled. Phase 5 will swap to per-thread flag.
                pii_guidance = get_pii_guidance_block(
                    redaction_enabled=settings.pii_redaction_enabled,
                )
                messages = (
                    [{"role": "system", "content": SYSTEM_PROMPT + pii_guidance}]
                    + [{"role": m["role"], "content": m["content"]} for m in history]
                    + [{"role": "user", "content": body.message}]
                )

                tools = tool_service.get_available_tools() if settings.tools_enabled else []

                # Agentic tool-calling loop
                async for event_type, data in _run_tool_loop(
                    messages, tools, settings.tools_max_iterations,
                    user["id"], tool_context,
                ):
                    if event_type == "records":
                        tool_records = data
                    else:
                        yield f"data: {json.dumps(data)}\n\n"

                # Stream final text response
                async for chunk in openrouter_service.stream_response(messages, model=llm_model):
                    if not chunk["done"]:
                        full_response += chunk["delta"]
                        yield f"data: {json.dumps({'type': 'delta', 'delta': chunk['delta'], 'done': False})}\n\n"
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("event_generator error: %s", exc, exc_info=True)

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
                    title_messages = [
                        {"role": "system", "content": "Generate a short title (max 6 words) for this chat conversation. Respond with ONLY the title text, no quotes, no punctuation at the end. If the message is in Indonesian, generate the title in Indonesian."},
                        {"role": "user", "content": body.message},
                    ]
                    title_result = await openrouter_service.complete_with_tools(title_messages)
                    new_title = (title_result["content"] or "").strip().strip('"\'')[:80]
                    if new_title:
                        client.table("threads").update({"title": new_title}).eq("id", body.thread_id).execute()
                        yield f"data: {json.dumps({'type': 'thread_title', 'title': new_title, 'thread_id': body.thread_id})}\n\n"
            except Exception:
                pass  # Non-blocking — default title stays

        yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
