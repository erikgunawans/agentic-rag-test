from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.dependencies import get_current_user, require_admin
from app.database import get_supabase_authed_client, get_supabase_client
from app.services.audit_service import log_action

router = APIRouter(prefix="/notifications", tags=["notifications"])


class ChannelCreate(BaseModel):
    channel_type: str
    channel_value: str
    preferences: dict | None = None


class ChannelUpdate(BaseModel):
    is_enabled: bool | None = None
    preferences: dict | None = None


class NotificationSend(BaseModel):
    user_id: str
    notification_type: str
    title: str
    body: str


# --- Channels ---

@router.get("/channels")
async def list_channels(user: dict = Depends(get_current_user)):
    """List user's notification channels."""
    client = get_supabase_authed_client(user["token"])
    result = client.table("notification_channels").select("*").eq(
        "user_id", user["id"]
    ).order("created_at", desc=True).execute()
    return {"data": result.data}


@router.post("/channels", status_code=201)
async def create_channel(body: ChannelCreate, user: dict = Depends(get_current_user)):
    """Register a notification channel."""
    client = get_supabase_authed_client(user["token"])
    row = client.table("notification_channels").insert({
        "user_id": user["id"],
        "channel_type": body.channel_type,
        "channel_value": body.channel_value,
        "preferences": body.preferences or {},
        "is_verified": False,
        "is_enabled": True,
    }).execute()

    return row.data[0]


@router.patch("/channels/{channel_id}")
async def update_channel(
    channel_id: str,
    body: ChannelUpdate,
    user: dict = Depends(get_current_user),
):
    """Update channel preferences or enabled status."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    client = get_supabase_authed_client(user["token"])
    result = client.table("notification_channels").update(updates).eq(
        "id", channel_id
    ).eq("user_id", user["id"]).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Channel not found")

    return result.data[0]


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(channel_id: str, user: dict = Depends(get_current_user)):
    """Remove a notification channel."""
    client = get_supabase_authed_client(user["token"])
    result = client.table("notification_channels").delete().eq(
        "id", channel_id
    ).eq("user_id", user["id"]).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Channel not found")


# --- History ---

@router.get("/history")
async def list_history(
    notification_type: str | None = None,
    limit: int = Query(30, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """List user's notification log."""
    client = get_supabase_authed_client(user["token"])
    query = client.table("notification_log").select("*").eq("user_id", user["id"])

    if notification_type:
        query = query.eq("notification_type", notification_type)

    query = query.order("created_at", desc=True).limit(limit)
    result = query.execute()
    return {"data": result.data}


# --- Admin send ---

@router.post("/send", status_code=201)
async def send_notification(body: NotificationSend, user: dict = Depends(require_admin)):
    """Send a notification (admin only). Inserts into notification_log with status pending."""
    client = get_supabase_client()
    row = client.table("notification_log").insert({
        "user_id": body.user_id,
        "notification_type": body.notification_type,
        "title": body.title,
        "body": body.body,
        "status": "pending",
    }).execute()

    log_action(
        user_id=user["id"],
        user_email=user["email"],
        action="send_notification",
        resource_type="notification",
        resource_id=str(row.data[0]["id"]),
        details={"target_user_id": body.user_id, "notification_type": body.notification_type},
    )
    return row.data[0]
