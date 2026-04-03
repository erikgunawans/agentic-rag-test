import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_client
from app.services.openrouter_service import OpenRouterService
from app.services.tool_service import ToolService
from app.config import get_settings
from app.routers.user_settings import get_or_create_settings
from app.models.tools import ToolCallRecord, ToolCallSummary

router = APIRouter(prefix="/chat", tags=["chat"])
openrouter_service = OpenRouterService()
tool_service = ToolService()
settings = get_settings()

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

    # Load full chat history for this thread (stateless — send every time)
    history = (
        client.table("messages")
        .select("role, content")
        .eq("thread_id", body.thread_id)
        .eq("user_id", user["id"])
        .order("created_at")
        .execute()
    ).data or []

    # Load user's model preferences
    user_settings = get_or_create_settings(client, user["id"])
    llm_model = user_settings["llm_model"]

    # Persist user message before streaming
    client.table("messages").insert({
        "thread_id": body.thread_id,
        "user_id": user["id"],
        "role": "user",
        "content": body.message,
    }).execute()

    # Tool execution context (passed to search_documents tool)
    tool_context = {
        "top_k": settings.rag_top_k,
        "threshold": settings.rag_similarity_threshold,
        "embedding_model": user_settings["embedding_model"],
        "llm_model": llm_model,
    }

    async def event_generator():
        # Assemble messages: [system] + history + current user message
        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + [{"role": m["role"], "content": m["content"]} for m in history]
            + [{"role": "user", "content": body.message}]
        )

        tools = tool_service.get_available_tools() if settings.tools_enabled else []
        tool_records = []
        full_response = ""

        try:
            # Agentic tool-calling loop
            if tools:
                for _iteration in range(settings.tools_max_iterations):
                    result = await openrouter_service.complete_with_tools(
                        messages, tools, model=llm_model
                    )

                    if not result["tool_calls"]:
                        # LLM chose to respond with text — break to stream final response
                        break

                    # Process each tool call
                    for tc in result["tool_calls"]:
                        func_name = tc["function"]["name"]
                        try:
                            func_args = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                            func_args = {}

                        # Send tool_start SSE event
                        yield f"data: {json.dumps({'type': 'tool_start', 'tool': func_name, 'input': func_args})}\n\n"

                        # Execute the tool
                        try:
                            tool_output = await tool_service.execute_tool(
                                func_name, func_args, user["id"], tool_context
                            )
                            tool_records.append(ToolCallRecord(
                                tool=func_name, input=func_args, output=tool_output
                            ))
                        except Exception as e:
                            tool_output = {"error": str(e)}
                            tool_records.append(ToolCallRecord(
                                tool=func_name, input=func_args, output={}, error=str(e)
                            ))

                        # Send tool_result SSE event
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': func_name, 'output': tool_output})}\n\n"

                        # Append assistant tool call + tool result to messages for next LLM call
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

            # Stream final text response
            async for chunk in openrouter_service.stream_response(messages, model=llm_model):
                if not chunk["done"]:
                    full_response += chunk["delta"]
                    yield f"data: {json.dumps({'type': 'delta', 'delta': chunk['delta'], 'done': False})}\n\n"
        except Exception:
            pass

        # Persist assistant message after streaming completes (only if we got a response)
        if full_response:
            insert_data = {
                "thread_id": body.thread_id,
                "user_id": user["id"],
                "role": "assistant",
                "content": full_response,
            }
            if tool_records:
                insert_data["tool_calls"] = ToolCallSummary(calls=tool_records).model_dump()
            client.table("messages").insert(insert_data).execute()

        yield f"data: {json.dumps({'type': 'delta', 'delta': '', 'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
