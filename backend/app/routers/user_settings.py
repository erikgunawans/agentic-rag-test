from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.dependencies import get_current_user
from app.database import get_supabase_client
from app.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])
config = get_settings()

# Models restricted to 1536-dim vectors to stay compatible with existing DB column
ALLOWED_EMBEDDING_MODELS = {
    "text-embedding-3-small",
    "text-embedding-ada-002",
}


def get_or_create_settings(client, user_id: str) -> dict:
    """Fetch user settings, creating defaults on first access."""
    result = client.table("user_settings").select("*").eq("user_id", user_id).limit(1).execute()
    if result.data:
        return result.data[0]

    # First access — insert defaults and return them
    defaults = {
        "user_id": user_id,
        "llm_model": config.openrouter_model,
        "embedding_model": config.openai_embedding_model,
    }
    client.table("user_settings").insert(defaults).execute()
    return defaults


@router.get("")
async def get_settings_endpoint(user: dict = Depends(get_current_user)):
    client = get_supabase_client()
    settings = get_or_create_settings(client, user["id"])

    # Embedding model is locked once the user has indexed any documents
    chunks = (
        client.table("document_chunks")
        .select("id", count="exact")
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    embedding_locked = (chunks.count or 0) > 0

    return {
        "llm_model": settings["llm_model"],
        "embedding_model": settings["embedding_model"],
        "embedding_locked": embedding_locked,
    }


class UpdateSettingsRequest(BaseModel):
    llm_model: str | None = None
    embedding_model: str | None = None


@router.patch("")
async def update_settings(
    body: UpdateSettingsRequest,
    user: dict = Depends(get_current_user),
):
    client = get_supabase_client()
    get_or_create_settings(client, user["id"])  # ensure row exists

    updates: dict = {}

    if body.llm_model is not None:
        if not body.llm_model.strip():
            raise HTTPException(status_code=400, detail="llm_model cannot be empty")
        updates["llm_model"] = body.llm_model.strip()

    if body.embedding_model is not None:
        if body.embedding_model not in ALLOWED_EMBEDDING_MODELS:
            raise HTTPException(
                status_code=400,
                detail=f"embedding_model must be one of: {', '.join(sorted(ALLOWED_EMBEDDING_MODELS))}",
            )
        # Lock check: reject if user already has indexed chunks
        chunks = (
            client.table("document_chunks")
            .select("id", count="exact")
            .eq("user_id", user["id"])
            .limit(1)
            .execute()
        )
        if (chunks.count or 0) > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cannot change embedding model while documents are indexed. "
                    "Delete all documents first to switch embedding models."
                ),
            )
        updates["embedding_model"] = body.embedding_model

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = (
        client.table("user_settings")
        .update(updates)
        .eq("user_id", user["id"])
        .execute()
    )
    return result.data[0]
