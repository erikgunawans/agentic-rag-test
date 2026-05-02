from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action
from app.services.openai_service import OpenAIService

router = APIRouter(prefix="/threads", tags=["threads"])
openai_service = OpenAIService()


class CreateThreadRequest(BaseModel):
    title: str = "New Thread"


class UpdateThreadRequest(BaseModel):
    title: str


class ThreadResponse(BaseModel):
    id: str
    title: str
    openai_thread_id: str | None
    last_response_id: str | None
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=list[ThreadResponse])
async def list_threads(user: dict = Depends(get_current_user)):
    client = get_supabase_client()
    result = (
        client.table("threads")
        .select("*")
        .eq("user_id", user["id"])
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data


@router.post("", response_model=ThreadResponse)
async def create_thread(
    body: CreateThreadRequest,
    user: dict = Depends(get_current_user),
):
    openai_thread_id = await openai_service.create_thread()
    client = get_supabase_client()
    result = (
        client.table("threads")
        .insert(
            {
                "user_id": user["id"],
                "title": body.title,
                "openai_thread_id": openai_thread_id,
            }
        )
        .execute()
    )
    thread = result.data[0]
    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="create",
        resource_type="thread",
        resource_id=str(thread["id"]),
    )
    return thread


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: str,
    body: UpdateThreadRequest,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_client()
    result = (
        client.table("threads")
        .update({"title": body.title})
        .eq("id", thread_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    return result.data[0]


@router.delete("/{thread_id}")
async def delete_thread(
    thread_id: str,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_client()
    result = (
        client.table("threads")
        .delete()
        .eq("id", thread_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Thread not found")
    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="delete",
        resource_type="thread",
        resource_id=thread_id,
    )
    return {"ok": True}


@router.get("/{thread_id}/todos")
async def get_thread_todos(
    thread_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Phase 17 / TODO-07 — Hydrate Plan Panel on thread reload.

    Read-only: the LLM is the sole writer via the write_todos tool (D-27).
    RLS-scoped via get_supabase_authed_client: User A cannot read User B's todos.
    Returns {"todos": [...]} ordered by position ASC, shape matches todos_updated SSE (D-17).
    """
    authed = get_supabase_authed_client(user["token"])
    result = (
        authed.table("agent_todos")
        .select("id, content, status, position")
        .eq("thread_id", thread_id)
        .order("position")
        .execute()
    )
    return {"todos": result.data or []}
