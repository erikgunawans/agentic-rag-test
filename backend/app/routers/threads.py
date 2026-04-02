from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_client
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
    return result.data[0]


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
    return {"ok": True}
