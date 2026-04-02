import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_client
from app.services.openrouter_service import OpenRouterService
from app.services.embedding_service import EmbeddingService
from app.config import get_settings
from app.routers.user_settings import get_or_create_settings

router = APIRouter(prefix="/chat", tags=["chat"])
openrouter_service = OpenRouterService()
embedding_service = EmbeddingService()
settings = get_settings()

SYSTEM_PROMPT = "You are a helpful assistant."


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

    # Retrieve relevant document chunks via pgvector (using user's embedding model)
    chunks = await embedding_service.retrieve_chunks(
        query=body.message,
        user_id=user["id"],
        top_k=settings.rag_top_k,
        threshold=settings.rag_similarity_threshold,
        model=user_settings["embedding_model"],
    )

    # Build system prompt — inject RAG context when available
    if chunks:
        context_text = "\n\n---\n\n".join(chunks)
        system_content = (
            f"{SYSTEM_PROMPT} Use the following context to answer when relevant:\n\n"
            f"{context_text}\n\n---"
        )
    else:
        system_content = SYSTEM_PROMPT

    # Assemble messages: [system] + history + current user message
    messages = (
        [{"role": "system", "content": system_content}]
        + [{"role": m["role"], "content": m["content"]} for m in history]
        + [{"role": "user", "content": body.message}]
    )

    # Persist user message before streaming
    client.table("messages").insert({
        "thread_id": body.thread_id,
        "user_id": user["id"],
        "role": "user",
        "content": body.message,
    }).execute()

    async def event_generator():
        full_response = ""

        try:
            async for chunk in openrouter_service.stream_response(messages, model=user_settings["llm_model"]):
                if not chunk["done"]:
                    full_response += chunk["delta"]
                    yield f"data: {json.dumps({'delta': chunk['delta'], 'done': False})}\n\n"
        except Exception:
            pass

        # Persist assistant message after streaming completes (only if we got a response)
        if full_response:
            client.table("messages").insert({
                "thread_id": body.thread_id,
                "user_id": user["id"],
                "role": "assistant",
                "content": full_response,
            }).execute()

        yield f"data: {json.dumps({'delta': '', 'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
