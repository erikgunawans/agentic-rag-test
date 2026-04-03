from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_client

router = APIRouter(tags=["preferences"])


class PreferencesUpdate(BaseModel):
    theme: str | None = None
    notifications_enabled: bool | None = None


def _get_or_create_preferences(user_id: str) -> dict:
    client = get_supabase_client()
    result = (
        client.table("user_preferences")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]
    defaults = {
        "user_id": user_id,
        "theme": "system",
        "notifications_enabled": True,
    }
    client.table("user_preferences").insert(defaults).execute()
    return defaults


@router.get("/preferences")
async def get_preferences(user: dict = Depends(get_current_user)):
    return _get_or_create_preferences(user["id"])


@router.patch("/preferences")
async def patch_preferences(
    body: PreferencesUpdate,
    user: dict = Depends(get_current_user),
):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return _get_or_create_preferences(user["id"])
    _get_or_create_preferences(user["id"])  # ensure row exists
    client = get_supabase_client()
    result = (
        client.table("user_preferences")
        .update(updates)
        .eq("user_id", user["id"])
        .execute()
    )
    return result.data[0] if result.data else {}
